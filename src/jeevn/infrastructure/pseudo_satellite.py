"""
Pseudo / synthetic fallback values for satellite + sensor inputs.

Whenever real satellite, weather, soil, or geographic data is unavailable, the
system substitutes values from this module. ANY VALUE PULLED FROM HERE IS
FABRICATED. The advisory report surfaces which fields were fabricated via
`data_quality.fabricated_fields`, and the UI shows a banner warning the user.

This is the single source of truth for fallback constants. Do NOT duplicate
these values in adapters, domain code, or UI — import from here instead.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List


# ── Vegetation / radar indices ───────────────────────────────────────────────
NDVI = 0.65            # Normalized Difference Vegetation Index
RVI = 0.65             # Radar Vegetation Index (typ. ~5–10% above NDVI)
RSM = 0.72             # Radar Soil Moisture (fraction of saturation)


# ── Soil ─────────────────────────────────────────────────────────────────────
SOIL_MOISTURE = 0.65   # Current moisture, fraction of field capacity

DEFAULT_SOIL_PROPERTIES: Dict[str, Any] = {
    "ph": 7.0,
    "ec": 0.4,                          # Electrical conductivity (dS/m)
    "organic_carbon_percent": 0.15,
    "texture": "loam",
    "water_holding_capacity": 18,        # mm per 30 cm depth
    "infiltration_rate": 12,             # mm / hour
    "bulk_density": 1.5,                 # g / cm³
    "soil_moisture_current": SOIL_MOISTURE,
}

GANGANAGAR_SOIL_PROPERTIES: Dict[str, Any] = {
    "ph": 7.2,
    "ec": 0.5,
    "organic_carbon_percent": 0.14,
    "texture": "sandy loam",
    "water_holding_capacity": 18,
    "infiltration_rate": 15,
    "bulk_density": 1.5,
    "soil_moisture_current": 0.72,
}


# ── Weather (semi-arid May baseline; used when Open-Meteo fails) ─────────────
DEFAULT_TIMEZONE = "Asia/Kolkata"
DEFAULT_WEATHER_DAILY: Dict[str, List] = {
    "temp_max": [35, 36, 37, 36, 35, 34, 33],
    "temp_min": [25, 26, 27, 26, 25, 24, 23],
    "temp_mean": [30, 31, 32, 31, 30, 29, 28],
    "rainfall": [0, 0, 0, 0, 0, 5, 0],
    "solar_radiation": [25, 26, 27, 26, 25, 22, 24],
    "wind_speed": [8, 8, 9, 8, 7, 6, 7],
}


# ── Geography ────────────────────────────────────────────────────────────────
DEFAULT_LOCATION: Dict[str, Any] = {
    "name": "Unknown",
    "city": "",
    "state": "",
    "country": "India",
    "timezone": DEFAULT_TIMEZONE,
}


# ── AOI / crop defaults ──────────────────────────────────────────────────────
DEFAULT_DAYS_SINCE_SOWING = 60
DEFAULT_AREA_ACRES = 0.421
DEFAULT_CROP_NAME = "apple"
DEFAULT_LATITUDE = 29.9        # Ganganagar, Rajasthan
DEFAULT_LONGITUDE = 73.9


# ── Builders ─────────────────────────────────────────────────────────────────
def make_default_weather(lat: float, lon: float) -> Dict[str, Any]:
    """Build a `{location, daily, _fabricated: True}` weather dict from the
    fallback series. Caller propagates `_fabricated` upward so the report can
    surface it via `data_quality.fabricated_fields`.
    """
    dates = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
             for i in range(7)]
    dates.reverse()

    return {
        "location": {
            "latitude": lat,
            "longitude": lon,
            "timezone": DEFAULT_TIMEZONE,
        },
        "daily": {"dates": dates, **DEFAULT_WEATHER_DAILY},
        "_fabricated": True,
    }


def make_default_soil(lat: float, lon: float,
                      location_name: str = "") -> Dict[str, Any]:
    """Build a `{location, properties, _fabricated: True}` soil dict, choosing
    region-specific properties when the location name matches a known region.
    """
    if location_name.lower() in ("ganganagar", "rajasthan"):
        props = GANGANAGAR_SOIL_PROPERTIES.copy()
    else:
        props = DEFAULT_SOIL_PROPERTIES.copy()

    return {
        "location": {
            "latitude": lat,
            "longitude": lon,
            "name": location_name,
        },
        "properties": props,
        "_fabricated": True,
    }


def make_default_location(lat: float, lon: float) -> Dict[str, Any]:
    """Build a default location info dict. Caller marks fabricated."""
    return {
        "latitude": lat,
        "longitude": lon,
        **DEFAULT_LOCATION,
        "_fabricated": True,
    }


# ── Human-readable descriptions for the UI banner ────────────────────────────
FABRICATED_FIELD_DESCRIPTIONS: Dict[str, str] = {
    "ndvi": "Normalized Difference Vegetation Index (no satellite reading available)",
    "rvi": "Radar Vegetation Index (derived from a fabricated NDVI)",
    "rsm": "Radar Soil Moisture (no satellite reading available)",
    "weather": "Weather data (Open-Meteo unreachable; using semi-arid May defaults)",
    "soil": "Soil properties (no soil database available; using region template)",
    "location": "Reverse-geocoded location (Nominatim unreachable)",
    "days_since_sowing": "Crop age (no sowing date provided; assumed 60 days)",
}


def describe(field: str) -> str:
    """Return a human-readable description for a fabricated-field key."""
    return FABRICATED_FIELD_DESCRIPTIONS.get(field, field)
