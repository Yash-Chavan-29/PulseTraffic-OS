"""
PulseTraffic OS - Real-Time 4-Way Traffic Simulator
Simulates stochastic vehicle arrivals, queue accumulation, and vehicle discharge
for four approaches (North, South, East, West) under both Fixed and Adaptive signal control.
"""

import random
import time
from typing import Dict, Any, List

class DirectionApproach:
    def __init__(self, name: str, arrival_rate_per_min: float = 24.0, lanes: int = 2):
        self.name = name.lower()
        self.arrival_rate_per_min = arrival_rate_per_min  # Mean arrival rate
        self.lanes = lanes
        self.queued_vehicles = 15
        self.cumulative_wait_sec = 0.0
        self.total_discharged_vehicles = 0
        self.max_queue_observed = 15
        self.saturation_flow_rate_per_sec = 0.5 * lanes  # ~1800 veh/hr/lane

    def step_one_second(self, signal_state: str) -> Dict[str, Any]:
        """
        Advances simulation by 1 second.
        Arrivals occur probabilistically; discharges occur during green.
        """
        # 1. Stochastic vehicle arrival (Poisson-like)
        arrival_prob = self.arrival_rate_per_min / 60.0
        if random.random() < arrival_prob:
            self.queued_vehicles += 1
            if self.queued_vehicles > self.max_queue_observed:
                self.max_queue_observed = self.queued_vehicles

        # 2. Accumulate wait time for waiting vehicles
        if signal_state in ("red", "yellow") or self.queued_vehicles > 0:
            self.cumulative_wait_sec += float(self.queued_vehicles)

        # 3. Vehicle discharge during green
        discharged = 0
        if signal_state == "green" and self.queued_vehicles > 0:
            # Discharge rate
            if random.random() < self.saturation_flow_rate_per_sec:
                self.queued_vehicles = max(0, self.queued_vehicles - 1)
                self.total_discharged_vehicles += 1
                discharged = 1

        avg_wait = round(self.cumulative_wait_sec / max(1, self.total_discharged_vehicles + self.queued_vehicles), 1)

        return {
            "queued": self.queued_vehicles,
            "discharged": discharged,
            "avg_wait_sec": avg_wait,
            "max_queue": self.max_queue_observed
        }

class IntersectionSimulator:
    def __init__(self):
        self.approaches = {
            "north": DirectionApproach("north", arrival_rate_per_min=28.0),
            "south": DirectionApproach("south", arrival_rate_per_min=18.0),
            "east":  DirectionApproach("east", arrival_rate_per_min=34.0),
            "west":  DirectionApproach("west", arrival_rate_per_min=20.0)
        }
        self.sim_elapsed_seconds = 0
        self.is_paused = False

    def step(self, signal_states: Dict[str, str]) -> Dict[str, Any]:
        """
        Advances all 4 intersection approaches by 1 simulated second.
        """
        if self.is_paused:
            return self.get_summary()

        self.sim_elapsed_seconds += 1
        summary = {}

        for d, app in self.approaches.items():
            state = signal_states.get(d, "red")
            step_result = app.step_one_second(state)
            summary[d] = {
                "count": app.queued_vehicles,
                "queue_length_m": round(app.queued_vehicles * 6.5, 1),
                "avg_wait_sec": step_result["avg_wait_sec"],
                "max_queue": app.max_queue_observed,
                "discharged_total": app.total_discharged_vehicles
            }

        return summary

    def get_summary(self) -> Dict[str, Any]:
        """Returns instantaneous snapshot of the simulated intersection."""
        summary = {}
        total_q = 0
        for d, app in self.approaches.items():
            total_q += app.queued_vehicles
            summary[d] = {
                "count": app.queued_vehicles,
                "queue_length_m": round(app.queued_vehicles * 6.5, 1),
                "avg_wait_sec": round(app.cumulative_wait_sec / max(1, app.total_discharged_vehicles + app.queued_vehicles), 1),
                "max_queue": app.max_queue_observed,
                "discharged_total": app.total_discharged_vehicles
            }
        summary["total_queued"] = total_q
        summary["elapsed_sec"] = self.sim_elapsed_seconds
        return summary

    def reset(self):
        """Resets simulation counters to initial calibrated values."""
        self.__init__()

    def inject_traffic_burst(self, direction: str, vehicle_count: int = 15):
        """Simulates sudden congestion burst in a corridor."""
        if direction.lower() in self.approaches:
            self.approaches[direction.lower()].queued_vehicles += vehicle_count
