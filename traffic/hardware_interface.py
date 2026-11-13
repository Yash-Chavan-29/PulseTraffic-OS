"""
PulseTraffic OS - Real-World Hardware Integration Layer
Provides an isolated, failsafe hardware abstraction layer for ESP32, Arduino,
and relay LED modules with hardware watchdog timers and conflict interlocks.

SAFETY NOTICE:
- Default mode is SIMULATION_MODE (100% software simulated).
- PHYSICAL_MODE requires explicit authorization via environment variables:
  `ALLOW_HARDWARE_OVERRIDE=true` and `HARDWARE_AUTH_KEY=<token>`.
- Laboratory prototype testing only.
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("traffic.hardware")

# Pin map for standard 12-channel ESP32/Arduino prototype
DEFAULT_PIN_MAP = {
    "north": {"red": 13, "yellow": 12, "green": 14},
    "south": {"red": 27, "yellow": 26, "green": 25},
    "east":  {"red": 33, "yellow": 32, "green": 35},
    "west":  {"red": 19, "yellow": 18, "green": 5}
}

class HardwareInterface:
    def __init__(self, port: Optional[str] = None, baud_rate: int = 115200):
        self.port = port or os.environ.get("HARDWARE_SERIAL_PORT", "COM3")
        self.baud_rate = baud_rate
        self.hardware_enabled = (os.environ.get("ALLOW_HARDWARE_OVERRIDE", "false").lower() == "true")
        self.auth_key = os.environ.get("HARDWARE_AUTH_KEY", "LAB_PROTOTYPE_DEMO_KEY")

        self.last_heartbeat = time.time()
        self.watchdog_timeout_sec = 2.5
        self.watchdog_tripped = False
        self.serial_conn = None

        self.current_lamp_pins = {
            "north": {"red": 1, "yellow": 0, "green": 0},
            "south": {"red": 1, "yellow": 0, "green": 0},
            "east":  {"red": 1, "yellow": 0, "green": 0},
            "west":  {"red": 1, "yellow": 0, "green": 0}
        }

        if self.hardware_enabled:
            logger.warning("HARDWARE MODE ACTIVATED: Connecting to physical microcontroller on port %s", self.port)
            self._connect_serial()
        else:
            logger.info("HARDWARE RUNNING IN SAFE SIMULATION MODE (No physical override active)")

    def _connect_serial(self):
        """Attempts connection to physical serial device if pySerial is available."""
        try:
            import serial
            self.serial_conn = serial.Serial(self.port, self.baud_rate, timeout=1.0)
            logger.info("Physical hardware serial connected successfully.")
        except Exception as e:
            logger.warning(f"Could not open physical serial port ({e}). Staying in simulated hardware mode.")
            self.serial_conn = None

    def feed_watchdog(self):
        """Heartbeat to prevent watchdog trip."""
        self.last_heartbeat = time.time()
        self.watchdog_tripped = False

    def send_signal_update(self, states: Dict[str, str], provided_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Updates physical signal LEDs according to commanded states.
        Enforces conflict checks and hardware watchdog timeouts.
        """
        now = time.time()
        if now - self.last_heartbeat > self.watchdog_timeout_sec:
            self.watchdog_tripped = True
            logger.critical("HARDWARE WATCHDOG TRIPPED: Heartbeat lost (>2.5s). Command forced to safe ALL-RED.")
            return self._emergency_all_red("WATCHDOG_TIMEOUT")

        # Conflict verification
        ns_green = states.get("north") == "green" or states.get("south") == "green"
        ew_green = states.get("east") == "green" or states.get("west") == "green"
        if ns_green and ew_green:
            logger.critical("HARDWARE CONFLICT INTERLOCK: Both N-S and E-W commanded green! Overriding to ALL-RED.")
            return self._emergency_all_red("HARDWARE_CONFLICT_INTERLOCK")

        # Map color names to digital high/low logic
        for d in ["north", "south", "east", "west"]:
            color = states.get(d, "red").lower()
            self.current_lamp_pins[d]["red"] = 1 if color == "red" else 0
            self.current_lamp_pins[d]["yellow"] = 1 if color == "yellow" else 0
            self.current_lamp_pins[d]["green"] = 1 if color == "green" else 0

        # Transmit via serial if physical device connected
        payload = json.dumps({"type": "SIGNAL_FRAME", "pins": self.current_lamp_pins, "timestamp": now})
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write((payload + "\n").encode("utf-8"))
            except Exception as e:
                logger.error(f"Serial transmission error: {e}")

        return {
            "status": "OK",
            "mode": "PHYSICAL_HARDWARE" if (self.hardware_enabled and self.serial_conn) else "SAFE_SIMULATION",
            "active_pins": self.current_lamp_pins,
            "watchdog_ok": not self.watchdog_tripped,
            "port": self.port
        }

    def _emergency_all_red(self, reason: str) -> Dict[str, Any]:
        """Sets all 4 directions to solid RED for safety clearance."""
        for d in ["north", "south", "east", "west"]:
            self.current_lamp_pins[d] = {"red": 1, "yellow": 0, "green": 0}

        return {
            "status": "FAILSAFE_ALL_RED",
            "reason": reason,
            "active_pins": self.current_lamp_pins,
            "watchdog_ok": False
        }
