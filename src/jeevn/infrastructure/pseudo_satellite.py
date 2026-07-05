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
    "sand_percent": 40.0,
    "silt_percent": 40.0,
    "clay_percent": 20.0,
    "texture": "loam",
    "cec": 12.0,                        # cation exchange capacity (cmol(+)/kg)
    "water_holding_capacity": 18,        # mm per 30 cm depth
    "infiltration_rate": 12,             # mm / hour
    "bulk_density": 1.5,                 # g / cm³
    "soil_moisture_current": SOIL_MOISTURE,
}

GANGANAGAR_SOIL_PROPERTIES: Dict[str, Any] = {
    "ph": 7.2,
    "ec": 0.5,
    "organic_carbon_percent": 0.14,
    "sand_percent": 60.0,
    "silt_percent": 25.0,
    "clay_percent": 15.0,
    "texture": "sandy loam",
    "cec": 10.0,
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


# ── Terrain (slope + aspect fallback) ───────────────────────────────────────
# Used by `data_sources/terrain.py` only when BOTH the Open-Elevation API
# and the bundled ETOPO India clip are unavailable. The default mimics the
# Indo-Gangetic plain (typical demo AOI): essentially flat, south-facing.
DEFAULT_TERRAIN: Dict[str, Any] = {
    "slope_percent": 0.5,
    "aspect_degrees": 180.0,
    "aspect_compass": "flat",
    "elevation_m": 200.0,
}


# ── AOI / crop defaults ──────────────────────────────────────────────────────
DEFAULT_DAYS_SINCE_SOWING = 60
DEFAULT_AREA_ACRES = 0.421
DEFAULT_CROP_NAME = "apple"
DEFAULT_LATITUDE = 29.92        # ~10 km east of Sri Ganganagar town —
DEFAULT_LONGITUDE = 73.97       #   real cropland with full SoilGrids coverage


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
        # `relative_humidity_mean: None` and an empty `hourly` block are
        # deliberate: with no real feed we do NOT synthesise hourly RH/temp,
        # so the disease models fall back to "data unavailable" rather than
        # presenting fabricated numbers as real (trust-pass principle).
        "daily": {"dates": dates, "relative_humidity_mean": None,
                  **DEFAULT_WEATHER_DAILY},
        "hourly": {"time": [], "temperature_2m": [],
                   "relative_humidity_2m": [], "precipitation": []},
        "_fabricated": True,
    }


def make_default_soil(lat: float, lon: float,
                      location_name: str = "") -> Dict[str, Any]:
    """Build a fully-fabricated soil dict (regional template) used as the
    fallback when no real soil data is available.

    Returned shape matches the SoilGrids-backed adapter:
        {location, properties, _fabricated_fields}
    where `_fabricated_fields` flags every property `True` since this entire
    record is the template, not a measurement.

    A caller that obtains real values overlays them onto `properties` and
    flips the corresponding `_fabricated_fields` entries to `False`.
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
        "_fabricated_fields": {k: True for k in props.keys()},
    }


def make_default_forecast(lat: float, lon: float, days: int = 7) -> Dict[str, Any]:
    """Build a fully-fabricated forward forecast (semi-arid May baseline,
    zero rain) used when Open-Meteo's forecast API is unreachable. Caller
    propagates `_fabricated` so the report flags the rain columns.
    """
    base = DEFAULT_WEATHER_DAILY
    dates = [(datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
             for i in range(days)]

    def _cycle(series: List, n: int) -> List:
        return [series[i % len(series)] for i in range(n)]

    return {
        "daily": {
            "dates": dates,
            "temp_max": _cycle(base["temp_max"], days),
            "temp_min": _cycle(base["temp_min"], days),
            "temp_mean": _cycle(base["temp_mean"], days),
            "rainfall": [0.0] * days,
            "rain_probability": [0.0] * days,
            "solar_radiation": _cycle(base["solar_radiation"], days),
            "wind_speed": _cycle(base["wind_speed"], days),
        },
        # Empty hourly block (no synthesised hourly weather) — the disease
        # models treat absent hourly data as "unavailable", not low-risk.
        "hourly": {"time": [], "temperature_2m": [],
                   "relative_humidity_2m": [], "precipitation": []},
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


def make_default_terrain() -> Dict[str, Any]:
    """Build a fully-fabricated terrain dict. Caller (TerrainDataFetcher)
    uses this as the last-resort fallback when both Open-Elevation and the
    bundled DEM raster are unavailable.
    """
    return {
        **DEFAULT_TERRAIN,
        "_fabricated": True,
    }


# ── Human-readable descriptions for the UI banner ────────────────────────────
FABRICATED_FIELD_DESCRIPTIONS: Dict[str, str] = {
    "ndvi": "Normalized Difference Vegetation Index (no satellite reading available)",
    "rvi": "Radar Vegetation Index (derived from a fabricated NDVI)",
    "rsm": "Radar Soil Moisture (no NISAR pass in window + Open-Meteo soil moisture unavailable; using fallback default)",
    "weather": "Weather data (Open-Meteo unreachable; using semi-arid May defaults)",
    "forecast": "7-day weather forecast (Open-Meteo forecast API unreachable; irrigation rain-adjustment using zero-rain defaults)",
    "soil": "Soil properties (SoilGrids unreachable; using region template)",
    "location": "Reverse-geocoded location (Nominatim unreachable)",
    "days_since_sowing": "Crop age (no sowing date provided; assumed 60 days)",

    # Per-property soil fabrications surfaced once we switched to granular
    # tracking. The granular keys are emitted by the soil adapter when only
    # *some* properties are fabricated (e.g. SoilGrids returned real pH but
    # we still have no real EC source).
    "soil.ph":                       "Soil pH (SoilGrids did not return a value at this location)",
    "soil.ec":                       "Soil EC / salinity (AOI is outside the bundled ISRIC salinity raster's bbox — using regional template)",
    "soil.organic_carbon_percent":   "Soil organic carbon (SoilGrids did not return a value at this location)",
    "soil.sand_percent":             "Soil sand % (SoilGrids unreachable)",
    "soil.silt_percent":             "Soil silt % (SoilGrids unreachable)",
    "soil.clay_percent":             "Soil clay % (SoilGrids unreachable)",
    "soil.texture":                  "Soil texture class (could not derive from sand/silt/clay)",
    "soil.cec":                      "Soil cation exchange capacity (SoilGrids did not return a value)",
    "soil.water_holding_capacity":   "Water-holding capacity (no real texture to derive from)",
    "soil.infiltration_rate":        "Infiltration rate (no real texture to derive from)",
    "soil.bulk_density":             "Bulk density (SoilGrids did not return a value)",
    "soil.soil_moisture_current":    "Soil moisture (Open-Meteo unreachable; using fallback default)",
    "soil.soil_moisture_m3m3":       "Raw soil moisture m³/m³ (Open-Meteo unreachable)",

    # Terrain (slope + aspect). Fabricated only when BOTH Open-Elevation
    # and the bundled ETOPO India clip failed — see data_sources/terrain.py.
    "terrain":                       "Slope + aspect (both Open-Elevation API and bundled DEM unavailable; using Indo-Gangetic plain default)",
}


def describe(field: str) -> str:
    """Return a human-readable description for a fabricated-field key."""
    return FABRICATED_FIELD_DESCRIPTIONS.get(field, field)
