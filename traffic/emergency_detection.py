"""
PulseTraffic OS - Emergency Vehicle Detection and Corridor Preemption
Identifies high-priority emergency vehicles (ambulances, fire engines, police)
and triggers instant green preemption locks to eliminate emergency delays.
"""

from typing import Dict, List, Optional
import time
from .vehicle_tracking import TrackedVehicle

EMERGENCY_CLASSES = {"ambulance", "fire truck", "fire_truck", "police", "police car", "emergency"}

class EmergencyDetector:
    def __init__(self):
        self.active_emergency_direction: Optional[str] = None
        self.emergency_detected_at: float = 0.0
        self.lock_duration_sec: float = 25.0
        self.active_vehicle_id: Optional[int] = None

    def check_for_emergency(self, tracked_vehicles: List[TrackedVehicle]) -> Optional[Dict]:
        """
        Scans current tracked vehicles for verified emergency classifications.
        Returns preemption payload if an emergency vehicle is detected.
        """
        # Check if existing lock is still valid
        if self.active_emergency_direction:
            elapsed = time.time() - self.emergency_detected_at
            if elapsed < self.lock_duration_sec:
                return {
                    "is_preempted": True,
                    "direction": self.active_emergency_direction,
                    "remaining_lock_sec": round(self.lock_duration_sec - elapsed, 1),
                    "vehicle_id": self.active_vehicle_id
                }
            else:
                # Lock expired
                self.active_emergency_direction = None

        for veh in tracked_vehicles:
            vtype = veh.vehicle_type.lower()
            if vtype in EMERGENCY_CLASSES:
                self.active_emergency_direction = veh.direction.lower()
                self.emergency_detected_at = time.time()
                self.active_vehicle_id = veh.track_id
                return {
                    "is_preempted": True,
                    "direction": self.active_emergency_direction,
                    "remaining_lock_sec": self.lock_duration_sec,
                    "vehicle_id": veh.track_id,
                    "newly_triggered": True
                }

        return None

    def manual_trigger(self, direction: str, duration_sec: float = 30.0):
        """Allows manual emergency corridor dispatch from dispatchers/dashboard."""
        self.active_emergency_direction = direction.lower()
        self.emergency_detected_at = time.time()
        self.lock_duration_sec = duration_sec
        self.active_vehicle_id = 9999

    def clear_preemption(self):
        """Clears active emergency lock."""
        self.active_emergency_direction = None
        self.active_vehicle_id = None
