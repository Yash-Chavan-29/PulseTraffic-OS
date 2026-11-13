"""
PulseTraffic OS - Signal Controller & Conflict Safety Monitor
Manages 4-way intersection signal state transitions with strict conflict prevention
and fail-safe intergreen clearance.
"""

from typing import Dict, Any, Optional, Callable
import time
import logging

logger = logging.getLogger("traffic.controller")

class SignalConflictError(Exception):
    """Raised if conflicting signal states are commanded simultaneously."""
    pass

class SignalController:
    # State constants
    PHASE_NS_GREEN = "NORTH_SOUTH_GREEN"
    PHASE_NS_YELLOW = "NORTH_SOUTH_YELLOW"
    PHASE_ALL_RED_1 = "ALL_RED_CLEARANCE_1"
    PHASE_EW_GREEN = "EAST_WEST_GREEN"
    PHASE_EW_YELLOW = "EAST_WEST_YELLOW"
    PHASE_ALL_RED_2 = "ALL_RED_CLEARANCE_2"

    def __init__(self):
        self.current_phase = self.PHASE_NS_GREEN
        self.remaining_seconds = 30
        self.allocated_green = {"NORTH_SOUTH": 30, "EAST_WEST": 30}
        self.yellow_duration = 3
        self.all_red_duration = 2
        self.is_emergency_override = False
        self.emergency_direction = None
        self.is_running = True
        self.on_state_change: Optional[Callable[[Dict[str, Any]], None]] = None

    def get_signal_states(self) -> Dict[str, str]:
        """
        Returns active lamp color ('red', 'yellow', 'green') for each approach:
        {"north": "green", "south": "green", "east": "red", "west": "red"}
        """
        if self.current_phase == self.PHASE_NS_GREEN:
            states = {"north": "green", "south": "green", "east": "red", "west": "red"}
        elif self.current_phase == self.PHASE_NS_YELLOW:
            states = {"north": "yellow", "south": "yellow", "east": "red", "west": "red"}
        elif self.current_phase in (self.PHASE_ALL_RED_1, self.PHASE_ALL_RED_2):
            states = {"north": "red", "south": "red", "east": "red", "west": "red"}
        elif self.current_phase == self.PHASE_EW_GREEN:
            states = {"north": "red", "south": "red", "east": "green", "west": "green"}
        elif self.current_phase == self.PHASE_EW_YELLOW:
            states = {"north": "red", "south": "red", "east": "yellow", "west": "yellow"}
        else:
            # Failsafe default
            states = {"north": "red", "south": "red", "east": "red", "west": "red"}

        # Conflict Safety Check
        self.verify_conflict_safety(states)
        return states

    def verify_conflict_safety(self, states: Dict[str, str]):
        """
        Strict hardware & logic conflict monitor:
        Throws SignalConflictError if conflicting movements are active.
        """
        ns_active = states.get("north") in ("green", "yellow") or states.get("south") in ("green", "yellow")
        ew_active = states.get("east") in ("green", "yellow") or states.get("west") in ("green", "yellow")

        if ns_active and ew_active:
            # Tripped fail-safe
            self.current_phase = self.PHASE_ALL_RED_1
            logger.critical("SIGNAL CONFLICT DETECTED: Conflicting green/yellow states! Tripping to ALL-RED fail-safe.")
            raise SignalConflictError("Severe conflict: North/South and East/West both active!")

    def set_allocated_timing(self, phase_name: str, green_sec: int):
        """Sets computed adaptive green time for target phase."""
        self.allocated_green[phase_name] = max(10, min(90, green_sec))

    def trigger_emergency(self, direction: str, duration_sec: int = 25):
        """Forces immediate preemption transition to clear emergency corridor."""
        self.is_emergency_override = True
        self.emergency_direction = direction.lower()

        target_phase = self.PHASE_NS_GREEN if direction.lower() in ("north", "south") else self.PHASE_EW_GREEN

        if self.current_phase != target_phase:
            # Immediate yellow transition if conflicting
            if self.current_phase == self.PHASE_NS_GREEN:
                self.current_phase = self.PHASE_NS_YELLOW
                self.remaining_seconds = 2
            elif self.current_phase == self.PHASE_EW_GREEN:
                self.current_phase = self.PHASE_EW_YELLOW
                self.remaining_seconds = 2
            else:
                self.current_phase = target_phase
                self.remaining_seconds = duration_sec
        else:
            self.remaining_seconds = duration_sec

    def tick_one_second(self) -> Dict[str, Any]:
        """Advances state machine by 1 second."""
        self.remaining_seconds -= 1

        if self.remaining_seconds <= 0:
            self._transition_next_phase()

        state_payload = self.get_telemetry()
        if self.on_state_change:
            self.on_state_change(state_payload)
        return state_payload

    def _transition_next_phase(self):
        """Cyclic intergreen state transitions."""
        if self.current_phase == self.PHASE_NS_GREEN:
            self.current_phase = self.PHASE_NS_YELLOW
            self.remaining_seconds = self.yellow_duration
        elif self.current_phase == self.PHASE_NS_YELLOW:
            self.current_phase = self.PHASE_ALL_RED_1
            self.remaining_seconds = self.all_red_duration
        elif self.current_phase == self.PHASE_ALL_RED_1:
            self.current_phase = self.PHASE_EW_GREEN
            self.remaining_seconds = self.allocated_green.get("EAST_WEST", 30)
            if self.is_emergency_override and self.emergency_direction in ("north", "south"):
                self.is_emergency_override = False
        elif self.current_phase == self.PHASE_EW_GREEN:
            self.current_phase = self.PHASE_EW_YELLOW
            self.remaining_seconds = self.yellow_duration
        elif self.current_phase == self.PHASE_EW_YELLOW:
            self.current_phase = self.PHASE_ALL_RED_2
            self.remaining_seconds = self.all_red_duration
        elif self.current_phase == self.PHASE_ALL_RED_2:
            self.current_phase = self.PHASE_NS_GREEN
            self.remaining_seconds = self.allocated_green.get("NORTH_SOUTH", 30)
            if self.is_emergency_override and self.emergency_direction in ("east", "west"):
                self.is_emergency_override = False

    def get_telemetry(self) -> Dict[str, Any]:
        """Provides full real-time telemetry of current signal state."""
        lamp_states = self.get_signal_states()
        next_dir = "EAST-WEST" if "NORTH_SOUTH" in self.current_phase else "NORTH-SOUTH"

        return {
            "current_phase": self.current_phase,
            "remaining_seconds": self.remaining_seconds,
            "signals": lamp_states,
            "active_corridor": "NORTH-SOUTH" if "NORTH_SOUTH" in self.current_phase else (
                "EAST-WEST" if "EAST_WEST" in self.current_phase else "CLEARANCE"
            ),
            "next_direction": next_dir,
            "is_emergency": self.is_emergency_override,
            "emergency_direction": self.emergency_direction,
            "allocated_timings": self.allocated_green
        }
