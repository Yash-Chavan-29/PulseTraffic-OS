"""
PulseTraffic OS - Queue Length Estimation Module
Measures stationary/slow vehicle queues at intersection stop lines
in physical meters and vehicle units.
"""

from typing import Dict, List, Any
from .vehicle_tracking import TrackedVehicle

# Average vehicle space including front-to-back safety buffer in meters
AVERAGE_VEHICLE_SPACE_METERS = 6.5

class QueueEstimator:
    def __init__(self, speed_threshold_px: float = 12.0):
        # Pixels per second threshold below which a vehicle is considered queued
        self.speed_threshold_px = speed_threshold_px

    def estimate_queues(self, tracked_vehicles: List[TrackedVehicle]) -> Dict[str, Dict[str, Any]]:
        """
        Calculates queue length (vehicle count & estimated meters)
        for each approach direction.
        """
        queues = {
            "north": {"queued_vehicles": 0, "queue_length_meters": 0.0, "max_wait_sec": 0.0},
            "south": {"queued_vehicles": 0, "queue_length_meters": 0.0, "max_wait_sec": 0.0},
            "east":  {"queued_vehicles": 0, "queue_length_meters": 0.0, "max_wait_sec": 0.0},
            "west":  {"queued_vehicles": 0, "queue_length_meters": 0.0, "max_wait_sec": 0.0}
        }

        for veh in tracked_vehicles:
            d = veh.direction.lower()
            if d not in queues:
                continue

            # Check if vehicle is stopped or moving very slowly in the queue
            if veh.speed_px_per_sec < self.speed_threshold_px or veh.dwell_time_sec > 3.0:
                queues[d]["queued_vehicles"] += 1
                queues[d]["queue_length_meters"] += AVERAGE_VEHICLE_SPACE_METERS
                if veh.dwell_time_sec > queues[d]["max_wait_sec"]:
                    queues[d]["max_wait_sec"] = round(veh.dwell_time_sec, 1)

        for d in queues:
            queues[d]["queue_length_meters"] = round(queues[d]["queue_length_meters"], 1)

        return queues
