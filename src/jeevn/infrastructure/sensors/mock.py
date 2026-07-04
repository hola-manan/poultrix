"""
Mock soil-moisture sensor for development and tests.

Returns a deterministic (or optionally jittered) reading so the whole
real-time advisory path can be exercised end-to-end without hardware.
"""

import random
from datetime import datetime, timezone
from typing import Optional

from .base import SensorReading, SoilSensor


class MockSoilSensor(SoilSensor):
    """Emit a configurable soil-moisture reading.

    Args:
        soil_moisture: value to report (raw m³/m³ unless `is_fraction`).
        is_fraction: interpret `soil_moisture` as fraction-of-field-capacity.
        jitter: uniform +/- noise applied on each `read()` (0 = deterministic).
        soil_temp_c / air_temp_c: optional temperature fields.
        fail: if True, simulate a device error (`read()` returns None).
    """

    def __init__(self, soil_moisture: float = 0.18, is_fraction: bool = False,
                 jitter: float = 0.0, soil_temp_c: Optional[float] = 24.0,
                 air_temp_c: Optional[float] = None, fail: bool = False):
        self.soil_moisture = soil_moisture
        self.is_fraction = is_fraction
        self.jitter = jitter
        self.soil_temp_c = soil_temp_c
        self.air_temp_c = air_temp_c
        self.fail = fail

    def read(self) -> Optional[SensorReading]:
        if self.fail:
            return None
        value = self.soil_moisture
        if self.jitter:
            value = max(0.0, value + random.uniform(-self.jitter, self.jitter))
        return SensorReading(
            soil_moisture=value,
            is_fraction=self.is_fraction,
            soil_temp_c=self.soil_temp_c,
            air_temp_c=self.air_temp_c,
            timestamp=datetime.now(timezone.utc),
        )
