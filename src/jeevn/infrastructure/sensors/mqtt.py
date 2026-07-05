"""
MQTT soil-moisture sensor adapter (optional dependency).

MQTT is the de-facto transport for real IoT field devices: the probe/gateway
publishes readings to a broker topic, and this adapter keeps the last value seen
so `read()` is a cheap cache lookup. `paho-mqtt` is imported lazily so the rest
of the kit works without it installed.

    sensor = MqttSensor(
        host="broker.local", topic="farm/plot42/soil_moisture",
        moisture_key="soil_moisture", is_fraction=False,
    )
    sensor.start()          # connect + subscribe in a background thread
    ...
    reading = sensor.read() # most recent cached value (or None if none yet)
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from .base import SensorReading, SoilSensor


class MqttSensor(SoilSensor):
    """Cache the latest reading published to an MQTT topic.

    Payloads may be a bare number or a JSON object; when JSON, `moisture_key`
    (and optional `soil_temp_key`) select the fields.
    """

    def __init__(self, host: str, topic: str, port: int = 1883,
                 moisture_key: str = "soil_moisture", is_fraction: bool = False,
                 soil_temp_key: Optional[str] = None,
                 username: Optional[str] = None, password: Optional[str] = None):
        self.host = host
        self.port = port
        self.topic = topic
        self.moisture_key = moisture_key
        self.is_fraction = is_fraction
        self.soil_temp_key = soil_temp_key
        self.username = username
        self.password = password
        self._latest: Optional[SensorReading] = None
        self._client = None

    def start(self) -> None:
        """Connect to the broker and subscribe (non-blocking loop)."""
        try:
            import paho.mqtt.client as mqtt  # lazy optional dependency
        except ImportError as e:
            raise RuntimeError(
                "MqttSensor requires paho-mqtt: pip install paho-mqtt"
            ) from e

        client = mqtt.Client()
        if self.username:
            client.username_pw_set(self.username, self.password or "")
        client.on_connect = lambda c, u, f, rc: c.subscribe(self.topic)
        client.on_message = self._on_message
        client.connect(self.host, self.port, keepalive=60)
        client.loop_start()
        self._client = client

    def stop(self) -> None:
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None

    def _on_message(self, _client, _userdata, msg) -> None:
        reading = self._parse_payload(msg.payload)
        if reading is not None:
            self._latest = reading

    def _parse_payload(self, payload: bytes) -> Optional[SensorReading]:
        text = payload.decode("utf-8", errors="ignore").strip()
        moisture: Any = None
        soil_temp: Any = None
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                moisture = obj.get(self.moisture_key)
                if self.soil_temp_key:
                    soil_temp = obj.get(self.soil_temp_key)
            else:
                moisture = obj
        except json.JSONDecodeError:
            moisture = text  # maybe a bare number

        try:
            moisture = float(moisture)
        except (TypeError, ValueError):
            return None
        try:
            soil_temp = float(soil_temp) if soil_temp is not None else None
        except (TypeError, ValueError):
            soil_temp = None

        return SensorReading(
            soil_moisture=moisture,
            is_fraction=self.is_fraction,
            soil_temp_c=soil_temp,
            timestamp=datetime.now(timezone.utc),
        )

    def read(self) -> Optional[SensorReading]:
        return self._latest
