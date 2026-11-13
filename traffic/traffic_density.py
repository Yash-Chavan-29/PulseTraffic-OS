"""
PulseTraffic OS - Traffic Density Analysis
Calculates Passenger Car Unit (PCU) weighted density, volume-to-capacity ratios,
and categorizes congestion levels across all 4 intersection approaches.
"""

from typing import Dict, List, Any
from .vehicle_tracking import TrackedVehicle

PCU_WEIGHTS = {
    "motorcycle": 0.5,
    "car": 1.0,
    "bus": 2.5,
    "truck": 3.0,
    "emergency": 1.5
}

class TrafficDensityAnalyzer:
    def __init__(self, lane_capacity_pcu: float = 25.0):
        # Default capacity per approach in simultaneous visible buffer ~25 PCU
        self.lane_capacity_pcu = lane_capacity_pcu

    def compute_density(self, tracked_vehicles: List[TrackedVehicle]) -> Dict[str, Dict[str, Any]]:
        """
        Aggregates vehicles by direction ('north', 'south', 'east', 'west')
        and calculates PCU density, count, congestion level, and waiting times.
        """
        results = {
            "north": {"count": 0, "pcu": 0.0, "types": {}, "avg_dwell_sec": 0.0},
            "south": {"count": 0, "pcu": 0.0, "types": {}, "avg_dwell_sec": 0.0},
            "east":  {"count": 0, "pcu": 0.0, "types": {}, "avg_dwell_sec": 0.0},
            "west":  {"count": 0, "pcu": 0.0, "types": {}, "avg_dwell_sec": 0.0}
        }

        dwell_accum = {"north": [], "south": [], "east": [], "west": []}

        for veh in tracked_vehicles:
            d = veh.direction.lower()
            if d not in results:
                continue

            results[d]["count"] += 1
            weight = PCU_WEIGHTS.get(veh.vehicle_type.lower(), 1.0)
            results[d]["pcu"] += weight

            vtype = veh.vehicle_type.lower()
            results[d]["types"][vtype] = results[d]["types"].get(vtype, 0) + 1
            dwell_accum[d].append(veh.dwell_time_sec)

        # Compute ratios and qualitative level
        for d in ["north", "south", "east", "west"]:
            dwells = dwell_accum[d]
            results[d]["avg_dwell_sec"] = round(sum(dwells) / len(dwells), 1) if dwells else 0.0

            ratio = min(1.0, results[d]["pcu"] / self.lane_capacity_pcu)
            results[d]["congestion_index"] = round(ratio, 2)

            if ratio < 0.25:
                results[d]["level"] = "FREE_FLOW"
                results[d]["color"] = "#10b981"
            elif ratio < 0.55:
                results[d]["level"] = "MODERATE"
                results[d]["color"] = "#3b82f6"
            elif ratio < 0.80:
                results[d]["level"] = "HEAVY"
                results[d]["color"] = "#f59e0b"
            else:
                results[d]["level"] = "CONGESTED"
                results[d]["color"] = "#ef4444"

        return results
