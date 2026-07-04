"""
Ground soil-moisture sensor adapters.

The advisory pipeline can fuse a *real* in-field soil-moisture reading as the
highest-priority source (above modelled/satellite estimates). This package
defines the pluggable contract (`SoilSensor` + `SensorReading`) plus a
`MockSoilSensor` for development/tests and `RestSensor`/`MqttSensor` adapters
for real hardware/gateways.

Nothing here imports the heavy `jeevn` data stack — a sensor is pure device
I/O, so these adapters stay dependency-light (only `requests` for `RestSensor`,
and an *optional* `paho-mqtt` for `MqttSensor`).
"""

from .base import SensorReading, SoilSensor
from .mock import MockSoilSensor
from .rest import RestSensor
from .mqtt import MqttSensor

__all__ = [
    "SensorReading",
    "SoilSensor",
    "MockSoilSensor",
    "RestSensor",
    "MqttSensor",
]
