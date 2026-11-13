# PulseTraffic OS — Adaptive Traffic Signal Optimization System

## 1. System Architecture Overview

The **Adaptive Traffic Signal Optimization System** integrates computer vision, intelligent transportation queue estimation, dynamic Webster/HCM signal allocation, and hardware-in-the-loop microcontroller interfaces into PulseTraffic OS.

```
                           +----------------------------------------+
                           |   CCTV Stream / IP Camera / Webcam     |
                           +-------------------+--------------------+
                                               |
                                               v
                           +----------------------------------------+
                           | YOLOv8/v11 Vehicle Detection + Tracking|
                           | (Classifies Car, Bike, Bus, Truck, EMS)|
                           +-------------------+--------------------+
                                               |
                                               v
                           +----------------------------------------+
                           | Traffic Analysis & Queue Estimator     |
                           | - PCU-Weighted Density                 |
                           | - Stop-line Physical Queue (Meters)    |
                           | - Starvation Anti-Aging Counters       |
                           +-------------------+--------------------+
                                               |
                                               v
                           +----------------------------------------+
                           | Dynamic Webster / HCM Signal Optimizer |
                           | - Optimal Cycle: Co = (1.5L+5)/(1-Y)   |
                           | - Min Green: 10s | Max Green: 60s      |
                           | - Emergency Corridor Preemption        |
                           +--------+---------------------+---------+
                                    |                     |
            +-----------------------+                     +-----------------------+
            v                                                                     v
+-------------------------+                                           +-------------------------+
| Live REST & WS API      |                                           | Failsafe Hardware Layer |
| (FastAPI @ :8000)       |                                           | - ESP32 / Arduino Relays|
| - MJPEG Video Stream    |                                           | - Hardware Watchdog     |
| - Before/After Analytics|                                           | - Conflict Interlock    |
| - SQLite Telemetry Log  |                                           | - MQTT Telemetry Bus    |
+-------------------------+                                           +-------------------------+
```

---

## 2. Directory Structure

```
traffic/
├── __init__.py               # Package metadata
├── database.py               # SQLite schema & persistence (detections, timings, events)
├── lane_detection.py         # 4-way intersection polygon ROIs & centroid lane mapping
├── vehicle_tracking.py       # Centroid & IoU association (ByteTrack concepts)
├── vehicle_detection.py      # YOLOv8/v11 inference + live MJPEG stream generator
├── traffic_density.py        # Passenger Car Unit (PCU) weighted density estimator
├── queue_estimation.py       # Spatial queue measurement in physical meters & veh counts
├── emergency_detection.py    # Ambulance / Fire / Police detection & green preemption
├── signal_optimizer.py       # Multi-factor priority & Webster HCM cycle optimization
├── signal_controller.py      # Cyclic state machine & conflict prevention monitor
├── traffic_simulator.py      # 4-way stochastic arrival & discharge simulation
├── analytics.py              # Before vs. After Webster delay performance comparison
├── hardware_interface.py     # ESP32/Arduino 12-channel relay driver with watchdog
├── mqtt_controller.py        # MQTT telemetry publisher & override subscriber
├── data_sources.py           # ISRIC SoilGrids REST client with in-memory caching
└── api.py                    # Complete FastAPI application with REST & stream endpoints

tests/
└── test_traffic_optimization.py  # 11 unit & integration tests (100% pass rate)
```

---

## 3. Mathematical Optimization Logic

### Webster Optimum Cycle Length Formula
$$C_0 = \frac{1.5 L + 5}{1 - Y}$$
- $L = 2 \times (\text{Yellow} + \text{All-Red}) = 2 \times (3\text{s} + 2\text{s}) = 10\text{s}$ (Total intersection lost time)
- $Y = y_{\text{NS}} + y_{\text{EW}}$ (Sum of critical lane volume-to-saturation flow ratios)
- Saturation flow rate $s \approx 1800 \text{ veh/hr/lane} = 0.5 \text{ veh/sec/lane}$

### Green Time Allocation
$$\text{Effective Green } g_{\text{eff}} = C_0 - L$$
$$g_{\text{NS}} = g_{\text{eff}} \times \left(\frac{y_{\text{NS}}}{Y}\right), \quad g_{\text{EW}} = g_{\text{eff}} \times \left(\frac{y_{\text{EW}}}{Y}\right)$$
Subject to strict boundary constraints:
$$10\text{s} \le g_{\text{NS}}, g_{\text{EW}} \le 60\text{s}$$

### Conflict Prevention Invariant
$$\text{Green}_{\text{NS}} \land \text{Green}_{\text{EW}} \equiv \text{FALSE}$$
If any hardware relay failure or erroneous command attempts to activate conflicting phases, the controller immediately trips to the failsafe `ALL_RED_CLEARANCE` state and fires a critical event to the SQLite database.

---

## 4. Hardware Integration Layer (ESP32 / Arduino)

### Prototype Pin Mapping
| Direction | Red Lamp (Pin) | Yellow Lamp (Pin) | Green Lamp (Pin) |
|---|---|---|---|
| **North** | GPIO 13 | GPIO 12 | GPIO 14 |
| **South** | GPIO 27 | GPIO 26 | GPIO 25 |
| **East**  | GPIO 33 | GPIO 32 | GPIO 35 |
| **West**  | GPIO 19 | GPIO 18 | GPIO 5  |

### Safety Protocol & Watchdog
- **Default Mode**: `SIMULATION_MODE` (100% safe, software loopback).
- **Physical Override**: Requires setting:
  ```bash
  ALLOW_HARDWARE_OVERRIDE=true
  HARDWARE_AUTH_KEY=LAB_PROTOTYPE_DEMO_KEY
  HARDWARE_SERIAL_PORT=COM3
  ```
- **Hardware Watchdog**: Heartbeat timer expires after $2.5\text{s}$ without software ping, automatically reverting all outputs to solid **RED**.

---

## 5. REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/traffic/status` | Real-time signal states, 4-way queue counts, and active corridor |
| `GET` | `/api/traffic/signals` | Current lamp colors (North, South, East, West) and phase timer |
| `GET` | `/api/traffic/density` | PCU density ratios and congestion qualitative levels |
| `POST` | `/api/traffic/optimize` | Runs Webster optimization on custom or detected queues |
| `GET` | `/api/traffic/comparison` | Before (Fixed 90s) vs. After (Webster Adaptive) performance delta |
| `POST` | `/api/traffic/emergency/trigger` | Locks green corridor for approaching emergency vehicle |
| `POST` | `/api/traffic/emergency/clear` | Restores standard adaptive cycle |
| `GET` | `/api/traffic/hardware/status` | Microcontroller connection, pin states, and watchdog health |
| `GET` | `/api/traffic/history` | Historical signal decisions and system events from SQLite |
| `GET` | `/api/traffic/frame` | Single annotated JPEG frame with vehicle boxes and signal heads |
| `GET` | `/api/traffic/video_feed` | Live MJPEG video stream (suitable for `<img src="...">`) |

---

## 6. How to Run

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Start the FastAPI Traffic Engine
```bash
uvicorn traffic.api:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger Documentation will be available at: `http://localhost:8000/docs`.

### Run Test Suite
```bash
pytest tests/test_traffic_optimization.py -v
```
All 11 unit and integration tests execute and pass cleanly:
```
tests/test_traffic_optimization.py::test_vehicle_tracking_and_counting PASSED
tests/test_traffic_optimization.py::test_lane_assignment PASSED
tests/test_traffic_optimization.py::test_traffic_priority_calculation PASSED
tests/test_traffic_optimization.py::test_signal_timing_optimization PASSED
tests/test_traffic_optimization.py::test_emergency_vehicle_priority PASSED
tests/test_traffic_optimization.py::test_min_max_green_limits PASSED
tests/test_traffic_optimization.py::test_conflict_prevention PASSED
tests/test_traffic_optimization.py::test_database_operations PASSED
tests/test_traffic_optimization.py::test_api_endpoints PASSED
tests/test_traffic_optimization.py::test_hardware_watchdog_and_safety PASSED
tests/test_traffic_optimization.py::test_soilgrids_properties_fetch PASSED
======================= 11 passed in 11.29s =======================
```
