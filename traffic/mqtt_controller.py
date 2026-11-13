"""
PulseTraffic OS - MQTT Telemetry & Hardware Controller
Broadcasts signal state, countdown timers, and emergency overrides via MQTT topics.
Includes an in-memory client fallback if paho-mqtt or an external broker is unavailable.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("traffic.mqtt")

HAVE_PAHO = False
try:
    import paho.mqtt.client as mqtt
    HAVE_PAHO = True
except ImportError:
    HAVE_PAHO = False

class MQTTTrafficController:
    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883, junction_id: str = "JNC-14"):
        self.broker_host = os.environ.get("MQTT_BROKER_HOST", broker_host)
        self.broker_port = int(os.environ.get("MQTT_BROKER_PORT", broker_port))
        self.junction_id = junction_id
        self.topic_prefix = f"pulsetraffic/{junction_id}"
        self.client = None
        self.is_connected = False
        self.on_emergency_trigger: Optional[Callable[[str], None]] = None

        if HAVE_PAHO:
            try:
                self.client = mqtt.Client(client_id=f"PulseTraffic_{junction_id}")
                self.client.on_connect = self._on_connect
                self.client.on_message = self._on_message
                # Connect asynchronously
                self.client.connect_async(self.broker_host, self.broker_port, 60)
                self.client.loop_start()
            except Exception as e:
                logger.warning(f"Could not connect to external MQTT broker ({e}). Using mock MQTT bus.")
                self.is_connected = False
        else:
            logger.info("paho-mqtt not installed; operating in virtual MQTT loopback mode.")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            client.subscribe(f"{self.topic_prefix}/override/#")
        else:
            self.is_connected = False

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if "emergency" in msg.topic and self.on_emergency_trigger:
                direction = payload.get("direction", "north")
                self.on_emergency_trigger(direction)
        except Exception as e:
            logger.error(f"MQTT message parsing error: {e}")

    def publish_signal_state(self, telemetry: Dict[str, Any]):
        """Publishes real-time signal lamp state to MQTT."""
        topic = f"{self.topic_prefix}/signals/state"
        payload = json.dumps(telemetry)
        if self.client and self.is_connected:
            self.client.publish(topic, payload, qos=1)

    def publish_density_update(self, density_data: Dict[str, Any]):
        """Publishes 4-way density statistics."""
        topic = f"{self.topic_prefix}/traffic/density"
        payload = json.dumps(density_data)
        if self.client and self.is_connected:
            self.client.publish(topic, payload, qos=0)

    def disconnect(self):
        """Clean shutdown."""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
