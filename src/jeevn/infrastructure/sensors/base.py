"""
Ground soil-moisture sensor contract.

`SensorReading` carries a soil-moisture value that is EITHER a raw volumetric
water content (`m³/m³`, `is_fraction=False`) OR an already-normalised
fraction-of-field-capacity (`0..1`, `is_fraction=True`). The advisory layer
normalises the raw form to a fraction using the AOI's real SoilGrids texture
(`field_capacity_from_texture`) so it lands on the same scale the downstream
deficit / RSM thresholds expect.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SensorReading:
    """A single soil-moisture (and optional temperature) reading."""

    soil_moisture: Optional[float]
    is_fraction: bool = False
    soil_temp_c: Optional[float] = None
    air_temp_c: Optional[float] = None
    timestamp: datetime = field(default_factory=_utcnow)

    def is_fresh(self, max_age_min: int) -> bool:
        """True if the reading is at most `max_age_min` minutes old.

        A stale reading is worse than none for real-time triggering, so the
        fusion layer discards readings that fail this check.
        """
        if self.soil_moisture is None:
            return False
        ts = self.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_s = (_utcnow() - ts).total_seconds()
        return 0 <= age_s <= max_age_min * 60


class SoilSensor(ABC):
    """A source of in-field soil-moisture readings.

    Implementations must be non-throwing: on any device/transport error
    `read()` returns `None` so the pipeline falls back to modelled/satellite
    soil moisture rather than crashing (or, worse, alerting on a bad value).
    """

    @abstractmethod
    def read(self) -> Optional[SensorReading]:
        ...
