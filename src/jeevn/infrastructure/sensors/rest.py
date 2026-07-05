"""
REST soil-moisture sensor adapter.

Polls an HTTP endpoint that a field gateway / vendor cloud exposes and maps the
JSON response onto a `SensorReading`. This is the simplest real-hardware path:
most commercial soil probes (and DIY ESP32/LoRa gateways) can POST/serve a JSON
document with a moisture value.

The field mapping is configurable via dotted paths so you don't have to match a
specific vendor schema:

    RestSensor(
        url="https://gateway.local/api/plots/42/latest",
        moisture_path="data.soil_moisture",   # dotted path into the JSON
        is_fraction=False,                     # value is raw m³/m³
        timestamp_path="data.ts",              # optional ISO-8601 timestamp
    )
"""

from datetime import datetime, timezone
from typing import Any, Optional

import requests

from .base import SensorReading, SoilSensor


def _dig(obj: Any, dotted: Optional[str]) -> Any:
    if not dotted:
        return None
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


class RestSensor(SoilSensor):
    """Fetch the latest reading from a JSON HTTP endpoint."""

    def __init__(self, url: str, moisture_path: str = "soil_moisture",
                 is_fraction: bool = False, soil_temp_path: Optional[str] = None,
                 timestamp_path: Optional[str] = None, timeout_s: float = 8.0,
                 headers: Optional[dict] = None):
        self.url = url
        self.moisture_path = moisture_path
        self.is_fraction = is_fraction
        self.soil_temp_path = soil_temp_path
        self.timestamp_path = timestamp_path
        self.timeout_s = timeout_s
        self.headers = headers or {}

    def read(self) -> Optional[SensorReading]:
        try:
            resp = requests.get(self.url, headers=self.headers, timeout=self.timeout_s)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:  # non-throwing contract
            print(f"[WARN] RestSensor fetch failed: {e}")
            return None

        raw = _dig(payload, self.moisture_path)
        if raw is None:
            return None
        try:
            moisture = float(raw)
        except (TypeError, ValueError):
            return None

        soil_temp = _dig(payload, self.soil_temp_path)
        try:
            soil_temp = float(soil_temp) if soil_temp is not None else None
        except (TypeError, ValueError):
            soil_temp = None

        ts_raw = _dig(payload, self.timestamp_path)
        ts = _parse_ts(ts_raw)

        return SensorReading(
            soil_moisture=moisture,
            is_fraction=self.is_fraction,
            soil_temp_c=soil_temp,
            timestamp=ts,
        )


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)
