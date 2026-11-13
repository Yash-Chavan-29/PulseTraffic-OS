"""
PulseTraffic OS - Database and Storage Module
Handles SQLite persistence for vehicle detections, density history,
signal timing decisions, system events, and optimization analytics.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("traffic.database")

DB_FILE = os.environ.get("TRAFFIC_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "traffic_optimization.db"))

def get_connection() -> sqlite3.Connection:
    """Returns a connection with Row factory enabled."""
    conn = sqlite3.connect(DB_FILE, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if tables do not exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Vehicle Detection Records
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            camera_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            lane_id INTEGER NOT NULL,
            vehicle_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            track_id INTEGER,
            bbox TEXT,
            is_emergency INTEGER DEFAULT 0
        )
        """)

        # 2. Traffic Density History
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_density_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            junction_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            vehicle_count INTEGER NOT NULL,
            density_level TEXT NOT NULL,
            queue_length REAL NOT NULL,
            avg_wait_time REAL NOT NULL,
            congestion_index REAL NOT NULL
        )
        """)

        # 3. Signal Timing History
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS signal_timing_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            junction_id TEXT NOT NULL,
            phase_name TEXT NOT NULL,
            active_direction TEXT NOT NULL,
            duration_sec REAL NOT NULL,
            min_green REAL NOT NULL,
            max_green REAL NOT NULL,
            yellow_sec REAL NOT NULL,
            all_red_sec REAL NOT NULL,
            trigger_reason TEXT,
            before_wait_avg REAL,
            after_wait_avg REAL
        )
        """)

        # 4. System Events & Hardware Logs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            metadata TEXT
        )
        """)

        # 5. Before vs After Optimization Metrics
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS optimization_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            junction_id TEXT NOT NULL,
            fixed_avg_wait REAL NOT NULL,
            adaptive_avg_wait REAL NOT NULL,
            delay_reduction_pct REAL NOT NULL,
            throughput_improvement_pct REAL NOT NULL,
            queue_reduction_pct REAL NOT NULL,
            sample_duration_min INTEGER DEFAULT 60
        )
        """)

        conn.commit()
        logger.info(f"Database initialized successfully at {DB_FILE}")

def log_vehicle_detection(camera_id: str, direction: str, lane_id: int, 
                          vehicle_type: str, confidence: float, track_id: Optional[int] = None,
                          bbox: Optional[List[int]] = None, is_emergency: bool = False):
    """Records a single vehicle detection event."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO vehicle_detections 
        (camera_id, direction, lane_id, vehicle_type, confidence, track_id, bbox, is_emergency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            camera_id, direction, lane_id, vehicle_type, confidence, track_id,
            json.dumps(bbox) if bbox else None, 1 if is_emergency else 0
        ))
        conn.commit()

def log_density_snapshot(junction_id: str, direction: str, vehicle_count: int,
                         density_level: str, queue_length: float, avg_wait_time: float,
                         congestion_index: float):
    """Logs spatial density and queue lengths for a direction."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO traffic_density_history 
        (junction_id, direction, vehicle_count, density_level, queue_length, avg_wait_time, congestion_index)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (junction_id, direction, vehicle_count, density_level, queue_length, avg_wait_time, congestion_index))
        conn.commit()

def log_signal_decision(junction_id: str, phase_name: str, active_direction: str,
                        duration_sec: float, min_green: float, max_green: float,
                        yellow_sec: float, all_red_sec: float, trigger_reason: str,
                        before_wait_avg: float, after_wait_avg: float):
    """Records an adaptive timing allocation decision."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO signal_timing_history
        (junction_id, phase_name, active_direction, duration_sec, min_green, max_green,
         yellow_sec, all_red_sec, trigger_reason, before_wait_avg, after_wait_avg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            junction_id, phase_name, active_direction, duration_sec, min_green, max_green,
            yellow_sec, all_red_sec, trigger_reason, before_wait_avg, after_wait_avg
        ))
        conn.commit()

def log_system_event(event_type: str, severity: str, message: str, metadata: Optional[Dict[str, Any]] = None):
    """Logs system events, hardware watchdog notices, or preemption triggers."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO system_events (event_type, severity, message, metadata)
        VALUES (?, ?, ?, ?)
        """, (event_type, severity, message, json.dumps(metadata) if metadata else None))
        conn.commit()

def record_optimization_metrics(junction_id: str, fixed_avg_wait: float, adaptive_avg_wait: float,
                                delay_reduction_pct: float, throughput_improvement_pct: float,
                                queue_reduction_pct: float, sample_duration_min: int = 60):
    """Records comparative before vs after evaluation data."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO optimization_metrics
        (junction_id, fixed_avg_wait, adaptive_avg_wait, delay_reduction_pct,
         throughput_improvement_pct, queue_reduction_pct, sample_duration_min)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            junction_id, fixed_avg_wait, adaptive_avg_wait, delay_reduction_pct,
            throughput_improvement_pct, queue_reduction_pct, sample_duration_min
        ))
        conn.commit()

def get_recent_metrics(limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves recent comparative performance snapshots."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM optimization_metrics ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_recent_events(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves recent system events and alerts."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM system_events ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

# Auto-initialize on module load
init_db()
