"""
PulseTraffic OS - Dynamic Adaptive Signal Timing Optimizer
Implements:
1. Multi-factor Weighted Priority Algorithm:
   Priority = w_density * D + w_queue * Q + w_wait * W + w_emergency * E
2. Webster / Highway Capacity Manual (HCM) optimum cycle allocation
3. Anti-starvation queue aging mechanism
4. Configurable min/max green, yellow, and all-red clearance intervals
5. Strict non-conflicting phase grouping (N-S vs E-W)
"""

from typing import Dict, Any, Optional, Tuple
import math

class SignalOptimizer:
    def __init__(
        self,
        min_green_sec: int = 10,
        max_green_sec: int = 60,
        yellow_sec: int = 3,
        all_red_sec: int = 2,
        weight_density: float = 0.35,
        weight_queue: float = 0.30,
        weight_wait: float = 0.25,
        weight_starvation: float = 0.10
    ):
        self.min_green_sec = min_green_sec
        self.max_green_sec = max_green_sec
        self.yellow_sec = yellow_sec
        self.all_red_sec = all_red_sec

        self.w_density = weight_density
        self.w_queue = weight_queue
        self.w_wait = weight_wait
        self.w_starvation = weight_starvation

        # Track consecutive red cycles to prevent starvation
        self.red_cycle_counts = {"north": 0, "south": 0, "east": 0, "west": 0}

    def compute_priorities(self, density_data: Dict[str, Any], queue_data: Dict[str, Any], emergency_data: Optional[Dict] = None) -> Dict[str, float]:
        """
        Calculates priority score for all four approaches.
        If an emergency vehicle is detected, that direction receives an immediate maximum score.
        """
        priorities = {}

        # Check emergency preemption first
        if emergency_data and emergency_data.get("is_preempted"):
            emg_dir = emergency_data.get("direction", "").lower()
            for d in ["north", "south", "east", "west"]:
                if d == emg_dir:
                    priorities[d] = 9999.0
                else:
                    priorities[d] = 0.0
            return priorities

        for d in ["north", "south", "east", "west"]:
            d_info = density_data.get(d, {})
            q_info = queue_data.get(d, {})

            pcu = d_info.get("pcu", 0.0)
            queued = q_info.get("queued_vehicles", 0)
            avg_dwell = d_info.get("avg_dwell_sec", 0.0)
            starve_count = self.red_cycle_counts.get(d, 0)

            # Normalized components (0 to 10 scale)
            norm_density = min(10.0, pcu * 0.4)
            norm_queue = min(10.0, queued * 0.5)
            norm_wait = min(10.0, avg_dwell * 0.15)
            norm_starve = min(10.0, starve_count * 2.5)

            score = (
                self.w_density * norm_density +
                self.w_queue * norm_queue +
                self.w_wait * norm_wait +
                self.w_starvation * norm_starve
            )
            priorities[d] = round(score, 3)

        return priorities

    def optimize_phase_durations(
        self,
        density_data: Dict[str, Any],
        queue_data: Dict[str, Any],
        emergency_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Computes dynamic green times and phase allocation between
        Phase 1 (North-South) and Phase 2 (East-West).
        """
        priorities = self.compute_priorities(density_data, queue_data, emergency_data)

        # Check for emergency preemption override
        if emergency_data and emergency_data.get("is_preempted"):
            emg_dir = emergency_data.get("direction", "").lower()
            target_phase = "NORTH_SOUTH" if emg_dir in ["north", "south"] else "EAST_WEST"
            return {
                "active_phase": target_phase,
                "reason": f"EMERGENCY_PREEMPTION: Ambulance in {emg_dir.upper()} corridor",
                "green_duration_sec": 30,
                "yellow_sec": self.yellow_sec,
                "all_red_sec": self.all_red_sec,
                "phase_splits": {
                    "NORTH_SOUTH": 30 if target_phase == "NORTH_SOUTH" else self.min_green_sec,
                    "EAST_WEST": 30 if target_phase == "EAST_WEST" else self.min_green_sec
                },
                "priorities": priorities,
                "is_emergency": True
            }

        # Pairwise demand grouping
        ns_demand = max(priorities.get("north", 0.1), priorities.get("south", 0.1))
        ew_demand = max(priorities.get("east", 0.1), priorities.get("west", 0.1))

        total_demand = ns_demand + ew_demand
        if total_demand < 0.1:
            total_demand = 0.1
            ns_demand = 0.05
            ew_demand = 0.05

        # Webster Optimum Cycle Formula Co = (1.5L + 5) / (1 - Y)
        # Lost time L = 2 * (yellow + all-red) = 2 * (3 + 2) = 10s
        lost_time = 2 * (self.yellow_sec + self.all_red_sec)
        saturation_ratio = min(0.85, max(0.20, total_demand / 15.0))
        optimal_cycle = (1.5 * lost_time + 5) / max(0.1, (1.0 - saturation_ratio))
        optimal_cycle = max(40, min(140, optimal_cycle))

        effective_green = max(20, optimal_cycle - lost_time)

        # Proportional green split
        ns_ratio = ns_demand / total_demand
        ew_ratio = ew_demand / total_demand

        green_ns = int(round(effective_green * ns_ratio))
        green_ew = int(round(effective_green * ew_ratio))

        # Clamp between configurable min and max green
        green_ns = max(self.min_green_sec, min(self.max_green_sec, green_ns))
        green_ew = max(self.min_green_sec, min(self.max_green_sec, green_ew))

        # Determine next higher priority phase
        selected_phase = "NORTH_SOUTH" if ns_demand >= ew_demand else "EAST_WEST"

        # Update starvation counters
        if selected_phase == "NORTH_SOUTH":
            self.red_cycle_counts["north"] = 0
            self.red_cycle_counts["south"] = 0
            self.red_cycle_counts["east"] += 1
            self.red_cycle_counts["west"] += 1
        else:
            self.red_cycle_counts["east"] = 0
            self.red_cycle_counts["west"] = 0
            self.red_cycle_counts["north"] += 1
            self.red_cycle_counts["south"] += 1

        return {
            "active_phase": selected_phase,
            "green_duration_sec": green_ns if selected_phase == "NORTH_SOUTH" else green_ew,
            "yellow_sec": self.yellow_sec,
            "all_red_sec": self.all_red_sec,
            "cycle_length_sec": green_ns + green_ew + lost_time,
            "phase_splits": {
                "NORTH_SOUTH": green_ns,
                "EAST_WEST": green_ew
            },
            "priorities": priorities,
            "is_emergency": False,
            "reason": f"Adaptive Webster Optimization (NS: {green_ns}s, EW: {green_ew}s, Y={round(saturation_ratio, 2)})"
        }
