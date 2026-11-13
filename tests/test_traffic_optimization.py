"""
PulseTraffic OS - Test Suite for Adaptive Traffic Signal Optimization System
Tests:
1. Vehicle counting & tracking
2. Lane assignment & spatial mapping
3. Traffic priority calculation
4. Signal timing optimization (Webster HCM model)
5. Emergency vehicle priority preemption
6. Minimum and maximum green limits
7. Conflict prevention safety invariant
8. Database operations (SQLite)
9. API endpoints (FastAPI TestClient)
10. Hardware communication & watchdog failure safe-state
11. SoilGrids data source stub resolution
"""

import pytest
import os
import time
from starlette.testclient import TestClient

from traffic.lane_detection import LaneDetector
from traffic.vehicle_tracking import VehicleTracker, calculate_iou
from traffic.traffic_density import TrafficDensityAnalyzer
from traffic.queue_estimation import QueueEstimator
from traffic.emergency_detection import EmergencyDetector
from traffic.signal_optimizer import SignalOptimizer
from traffic.signal_controller import SignalController, SignalConflictError
from traffic.traffic_simulator import IntersectionSimulator
from traffic.analytics import PerformanceAnalytics
from traffic.hardware_interface import HardwareInterface
from traffic.api import app
from traffic import database
from traffic.data_sources import fetch_soilgrids_properties

@pytest.fixture
def client():
    return TestClient(app)

# 1. Vehicle Counting & Tracking
def test_vehicle_tracking_and_counting():
    tracker = VehicleTracker(iou_threshold=0.3)
    frame1 = [
        {"bbox": [100, 100, 150, 160], "class": "car", "confidence": 0.9, "direction": "north", "lane_id": 1}
    ]
    tracks1 = tracker.update(frame1)
    assert len(tracks1) == 1
    t1_id = tracks1[0].track_id

    # Moving slightly in frame 2
    frame2 = [
        {"bbox": [102, 108, 152, 168], "class": "car", "confidence": 0.92, "direction": "north", "lane_id": 1}
    ]
    tracks2 = tracker.update(frame2)
    assert len(tracks2) == 1
    assert tracks2[0].track_id == t1_id  # Stable ID maintained, no duplicate count

# 2. Lane Assignment
def test_lane_assignment():
    detector = LaneDetector(frame_width=1280, frame_height=720)
    # North approach vehicle (top vertical)
    bbox_north = [550, 50, 600, 120]
    lane_info = detector.assign_lane(bbox_north)
    assert lane_info is not None
    assert lane_info[0] == "north"

    # East approach vehicle (right horizontal)
    bbox_east = [1000, 320, 1060, 360]
    lane_info_east = detector.assign_lane(bbox_east)
    assert lane_info_east is not None
    assert lane_info_east[0] == "east"

# 3. Traffic Priority Calculation
def test_traffic_priority_calculation():
    optimizer = SignalOptimizer()
    density = {
        "north": {"pcu": 18.0, "avg_dwell_sec": 30.0},
        "south": {"pcu": 5.0,  "avg_dwell_sec": 10.0},
        "east":  {"pcu": 25.0, "avg_dwell_sec": 45.0},
        "west":  {"pcu": 4.0,  "avg_dwell_sec": 8.0}
    }
    queues = {
        "north": {"queued_vehicles": 12},
        "south": {"queued_vehicles": 3},
        "east":  {"queued_vehicles": 22},
        "west":  {"queued_vehicles": 2}
    }
    priorities = optimizer.compute_priorities(density, queues)
    # East has highest demand -> highest score
    assert priorities["east"] > priorities["west"]
    assert priorities["east"] > priorities["south"]

# 4. Signal Timing Optimization (Webster HCM Model)
def test_signal_timing_optimization():
    optimizer = SignalOptimizer(min_green_sec=10, max_green_sec=60)
    density = {
        "north": {"pcu": 20.0, "avg_dwell_sec": 25.0},
        "south": {"pcu": 15.0, "avg_dwell_sec": 20.0},
        "east":  {"pcu": 10.0, "avg_dwell_sec": 15.0},
        "west":  {"pcu": 8.0,  "avg_dwell_sec": 10.0}
    }
    queues = {
        "north": {"queued_vehicles": 18},
        "south": {"queued_vehicles": 12},
        "east":  {"queued_vehicles": 6},
        "west":  {"queued_vehicles": 4}
    }
    result = optimizer.optimize_phase_durations(density, queues)
    assert result["active_phase"] == "NORTH_SOUTH"
    assert result["phase_splits"]["NORTH_SOUTH"] >= optimizer.min_green_sec
    assert result["phase_splits"]["NORTH_SOUTH"] <= optimizer.max_green_sec

# 5. Emergency Vehicle Priority
def test_emergency_vehicle_priority():
    optimizer = SignalOptimizer()
    emergency_data = {"is_preempted": True, "direction": "south"}
    density = {"north": {}, "south": {}, "east": {}, "west": {}}
    queues = {"north": {}, "south": {}, "east": {}, "west": {}}

    result = optimizer.optimize_phase_durations(density, queues, emergency_data)
    assert result["is_emergency"] is True
    assert result["active_phase"] == "NORTH_SOUTH"

# 6. Minimum and Maximum Green Limits
def test_min_max_green_limits():
    # Extreme low demand
    opt_low = SignalOptimizer(min_green_sec=12, max_green_sec=55)
    density_low = {d: {"pcu": 0.1, "avg_dwell_sec": 0.0} for d in ["north", "south", "east", "west"]}
    queues_low = {d: {"queued_vehicles": 0} for d in ["north", "south", "east", "west"]}
    res_low = opt_low.optimize_phase_durations(density_low, queues_low)
    assert res_low["phase_splits"]["NORTH_SOUTH"] >= 12
    assert res_low["phase_splits"]["EAST_WEST"] >= 12

    # Extreme high demand
    density_high = {d: {"pcu": 200.0, "avg_dwell_sec": 100.0} for d in ["north", "south", "east", "west"]}
    queues_high = {d: {"queued_vehicles": 150} for d in ["north", "south", "east", "west"]}
    res_high = opt_low.optimize_phase_durations(density_high, queues_high)
    assert res_high["phase_splits"]["NORTH_SOUTH"] <= 55
    assert res_high["phase_splits"]["EAST_WEST"] <= 55

# 7. Conflict Prevention Safety Invariant
def test_conflict_prevention():
    controller = SignalController()
    states = controller.get_signal_states()

    # In standard N-S green, E-W MUST be red
    assert states["north"] == "green"
    assert states["south"] == "green"
    assert states["east"] == "red"
    assert states["west"] == "red"

    # Conflicting state injection MUST raise SignalConflictError
    conflicting_states = {"north": "green", "south": "green", "east": "green", "west": "red"}
    with pytest.raises(SignalConflictError):
        controller.verify_conflict_safety(conflicting_states)

# 8. Database Operations
def test_database_operations():
    database.init_db()
    database.log_vehicle_detection(
        camera_id="CAM-NORTH", direction="north", lane_id=1,
        vehicle_type="car", confidence=0.91, is_emergency=False
    )
    database.log_system_event(
        event_type="TEST_RUN", severity="INFO", message="Automated unit test assertion"
    )
    events = database.get_recent_events(5)
    assert len(events) > 0
    assert any(e["event_type"] == "TEST_RUN" for e in events)

# 9. API Endpoints
def test_api_endpoints(client):
    res_status = client.get("/api/traffic/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert "signals" in data
    assert "density" in data

    res_opt = client.post("/api/traffic/optimize", json={"junction_id": "JNC-14", "queues": {"north": 25, "south": 10, "east": 30, "west": 12}})
    assert res_opt.status_code == 200
    opt_data = res_opt.json()
    assert "optimization" in opt_data
    assert "performance_comparison" in opt_data

    res_comp = client.get("/api/traffic/comparison?north=30&south=15&east=40&west=18")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert "before_optimization" in comp_data
    assert "after_optimization" in comp_data
    assert comp_data["performance_delta"]["waiting_time_reduction_percent"] > 0

# 10. Hardware Watchdog & Fail-Safe
def test_hardware_watchdog_and_safety():
    hw = HardwareInterface()
    hw.feed_watchdog()
    res = hw.send_signal_update({"north": "green", "south": "green", "east": "red", "west": "red"})
    assert res["status"] == "OK"

    # Simulate heartbeat timeout > 2.5s
    hw.last_heartbeat = time.time() - 5.0
    res_timeout = hw.send_signal_update({"north": "green", "south": "green", "east": "red", "west": "red"})
    assert res_timeout["status"] == "FAILSAFE_ALL_RED"
    assert res_timeout["active_pins"]["north"]["red"] == 1
    assert res_timeout["active_pins"]["north"]["green"] == 0

# 11. SoilGrids Data Source Implementation Check
def test_soilgrids_properties_fetch():
    # Test valid retrieval with fallback or live API
    data = fetch_soilgrids_properties(lat=15.85, lon=74.50)
    assert data is not None
    assert "status" in data
    assert "layers" in data
    assert len(data["layers"]) > 0
