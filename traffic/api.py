"""
PulseTraffic OS - Adaptive Traffic Signal Optimization REST API
Built with FastAPI. Exposes real-time traffic monitoring, signal optimization,
video stream endpoints, before/after analytics, and hardware watchdog status.
"""

import io
import time
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from .vehicle_detection import VehicleDetectionEngine
from .traffic_density import TrafficDensityAnalyzer
from .queue_estimation import QueueEstimator
from .emergency_detection import EmergencyDetector
from .signal_optimizer import SignalOptimizer
from .signal_controller import SignalController
from .traffic_simulator import IntersectionSimulator
from .analytics import PerformanceAnalytics
from .hardware_interface import HardwareInterface
from .mqtt_controller import MQTTTrafficController
from . import database

app = FastAPI(
    title="PulseTraffic OS - Adaptive Signal Optimization API",
    version="2.0.0",
    description="Intelligent transportation system for real-time computer vision, adaptive signal timing, and hardware control."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core singletons
detector = VehicleDetectionEngine(source="demo")
density_analyzer = TrafficDensityAnalyzer()
queue_estimator = QueueEstimator()
emergency_detector = EmergencyDetector()
optimizer = SignalOptimizer(min_green_sec=10, max_green_sec=60, yellow_sec=3, all_red_sec=2)
controller = SignalController()
simulator = IntersectionSimulator()
hardware = HardwareInterface()
mqtt_bus = MQTTTrafficController()

# Connect state change hook to hardware and MQTT
def on_signal_state_change(telemetry: Dict[str, Any]):
    hardware.feed_watchdog()
    hardware.send_signal_update(telemetry["signals"])
    mqtt_bus.publish_signal_state(telemetry)

controller.on_state_change = on_signal_state_change

# Pydantic Request Models
class OptimizeRequest(BaseModel):
    junction_id: str = "JNC-14"
    queues: Optional[Dict[str, int]] = None
    min_green: Optional[int] = 10
    max_green: Optional[int] = 60

class EmergencyRequest(BaseModel):
    direction: str = "north"
    duration_sec: int = 25

class BurstRequest(BaseModel):
    direction: str = "east"
    vehicle_count: int = 15

@app.get("/api/traffic/status")
def get_live_status():
    """Returns complete real-time status of signals, 4-way density, and queues."""
    # 1. Process latest frame from vision engine
    raw_dets, tracked_vehs = detector.process_frame()

    # 2. Check emergency
    emg_status = emergency_detector.check_for_emergency(tracked_vehs)

    # 3. Analyze density and queues
    density_data = density_analyzer.compute_density(tracked_vehs)
    queue_data = queue_estimator.estimate_queues(tracked_vehs)

    # 4. Advance 1s of simulation and signal controller
    controller.tick_one_second()
    sim_data = simulator.step(controller.get_signal_states())

    telemetry = controller.get_telemetry()

    return {
        "status": "online",
        "timestamp": time.time(),
        "signals": telemetry["signals"],
        "active_phase": telemetry["current_phase"],
        "active_corridor": telemetry["active_corridor"],
        "remaining_seconds": telemetry["remaining_seconds"],
        "next_direction": telemetry["next_direction"],
        "emergency": emg_status or {"is_preempted": False},
        "density": density_data,
        "queues": queue_data,
        "simulation": sim_data,
        "total_active_tracks": len(tracked_vehs)
    }

@app.get("/api/traffic/signals")
def get_signal_telemetry():
    """Returns detailed signal controller telemetry and current lamp states."""
    return controller.get_telemetry()

@app.get("/api/traffic/density")
def get_density_breakdown():
    """Returns 4-way PCU density, congestion level, and waiting times."""
    _, tracked_vehs = detector.process_frame()
    density = density_analyzer.compute_density(tracked_vehs)
    return {"density": density}

@app.post("/api/traffic/optimize")
def run_optimization(req: OptimizeRequest):
    """Executes dynamic Webster / weighted priority optimization."""
    if req.queues:
        queues = req.queues
    else:
        _, tracked_vehs = detector.process_frame()
        q_est = queue_estimator.estimate_queues(tracked_vehs)
        queues = {d: q_est[d]["queued_vehicles"] for d in ["north", "south", "east", "west"]}

    dummy_density = {
        d: {"pcu": queues[d] * 1.1, "avg_dwell_sec": queues[d] * 1.8}
        for d in ["north", "south", "east", "west"]
    }
    dummy_queues = {
        d: {"queued_vehicles": queues[d]}
        for d in ["north", "south", "east", "west"]
    }

    opt_result = optimizer.optimize_phase_durations(dummy_density, dummy_queues)
    comparison = PerformanceAnalytics.compare_performance(queues)

    # Apply allocated green to controller
    controller.set_allocated_timing("NORTH_SOUTH", opt_result["phase_splits"]["NORTH_SOUTH"])
    controller.set_allocated_timing("EAST_WEST", opt_result["phase_splits"]["EAST_WEST"])

    # Log to SQLite
    database.log_signal_decision(
        junction_id=req.junction_id,
        phase_name=opt_result["active_phase"],
        active_direction=opt_result["active_phase"],
        duration_sec=opt_result["green_duration_sec"],
        min_green=optimizer.min_green_sec,
        max_green=optimizer.max_green_sec,
        yellow_sec=optimizer.yellow_sec,
        all_red_sec=optimizer.all_red_sec,
        trigger_reason=opt_result["reason"],
        before_wait_avg=comparison["before_optimization"]["avg_waiting_time_sec"],
        after_wait_avg=comparison["after_optimization"]["avg_waiting_time_sec"]
    )

    return {
        "optimization": opt_result,
        "performance_comparison": comparison
    }

@app.get("/api/traffic/comparison")
def get_performance_comparison(
    north: int = Query(28, description="North queue"),
    south: int = Query(14, description="South queue"),
    east: int = Query(42, description="East queue"),
    west: int = Query(19, description="West queue")
):
    """Calculates comprehensive before-and-after performance metrics."""
    data = PerformanceAnalytics.compare_performance({"north": north, "south": south, "east": east, "west": west})
    return data

@app.post("/api/traffic/emergency/trigger")
def trigger_emergency_corridor(req: EmergencyRequest):
    """Preempts signal sequence to clear green corridor for emergency vehicle."""
    emergency_detector.manual_trigger(req.direction, float(req.duration_sec))
    controller.trigger_emergency(req.direction, req.duration_sec)
    database.log_system_event(
        event_type="EMERGENCY_PREEMPTION",
        severity="HIGH",
        message=f"Corridor locked green for emergency vehicle approaching {req.direction.upper()}"
    )
    return {"status": "PREEMPTION_ACTIVE", "direction": req.direction, "duration": req.duration_sec}

@app.post("/api/traffic/emergency/clear")
def clear_emergency_corridor():
    """Restores normal cyclic adaptive scheduling."""
    emergency_detector.clear_preemption()
    controller.is_emergency_override = False
    return {"status": "RESTORED_CYCLIC_OPERATION"}

@app.post("/api/traffic/simulation/burst")
def inject_traffic_burst(req: BurstRequest):
    """Simulates real-world traffic spike in target approach."""
    simulator.inject_traffic_burst(req.direction, req.vehicle_count)
    return {"status": "BURST_INJECTED", "direction": req.direction, "vehicles": req.vehicle_count}

@app.post("/api/traffic/simulation/reset")
def reset_simulation():
    """Resets simulator to baseline calibration."""
    simulator.reset()
    return {"status": "RESET_COMPLETED"}

@app.get("/api/traffic/hardware/status")
def get_hardware_status():
    """Returns physical controller status, pin mappings, and watchdog health."""
    hardware.feed_watchdog()
    return {
        "hardware_mode": hardware.hardware_enabled,
        "port": hardware.port,
        "watchdog_ok": not hardware.watchdog_tripped,
        "active_lamp_pins": hardware.current_lamp_pins
    }

@app.get("/api/traffic/history")
def get_history():
    """Fetches recent database events and optimization records from SQLite."""
    events = database.get_recent_events(15)
    metrics = database.get_recent_metrics(10)
    return {"events": events, "metrics": metrics}

@app.get("/api/traffic/frame")
def get_annotated_frame_jpeg():
    """Returns a single JPEG frame rendered with bounding boxes and 3-lamp heads."""
    _, tracked = detector.process_frame()
    img = detector.render_annotated_frame(tracked, controller.get_signal_states())
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")

@app.get("/api/traffic/video_feed")
def get_mjpeg_stream():
    """Live MJPEG stream for CCTV / dashboard preview."""
    def generate():
        while True:
            _, tracked = detector.process_frame()
            img = detector.render_annotated_frame(tracked, controller.get_signal_states())
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            frame_bytes = buf.getvalue()
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            time.sleep(0.08)  # ~12 fps

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")
