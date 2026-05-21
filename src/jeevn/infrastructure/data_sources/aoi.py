"""
AOI data composer — assembles weather + soil + geocoding + phenology
into the single dict shape consumed by the advisory service.

Each sub-adapter sets a private `_fabricated` flag when it falls back to
defaults; this composer hoists those flags into a top-level
`_fabricated_sources` list so callers can surface them in the report.
"""

from datetime import datetime
from typing import Dict, Any, List

from .weather import WeatherDataFetcher
from .soil import SoilDataFetcher, field_capacity_from_texture
from .geocoding import GeographicDataFetcher

# Phenology is pure domain data (no I/O) — infrastructure may depend on domain.
from jeevn.domain.crop.phenology import CropPhenologyDatabase
from jeevn.infrastructure import pseudo_satellite


def fetch_aoi_data(lat: float, lon: float, location_name: str = "",
                   start_date: str = None, end_date: str = None,
                   crop_name: str = "apple",
                   sowing_date: str = None) -> Dict[str, Any]:
    """Fetch all required agricultural data for an AOI.

    Adds a top-level `_fabricated_sources` list naming each sub-source that
    fell back to pseudo defaults (`weather`, `soil`, `location`,
    `days_since_sowing`).
    """
    fabricated: List[str] = []
    alerts: List[Dict[str, Any]] = []

    if sowing_date:
        sowing_dt = datetime.strptime(sowing_date, "%Y-%m-%d")
        days_since_sowing = (datetime.now() - sowing_dt).days
    else:
        days_since_sowing = pseudo_satellite.DEFAULT_DAYS_SINCE_SOWING
        fabricated.append("days_since_sowing")

    location = GeographicDataFetcher.get_location_info(lat, lon)
    if location.pop("_fabricated", False):
        fabricated.append("location")

    weather_start = start_date or sowing_date
    weather = WeatherDataFetcher.fetch_weather(lat, lon, weather_start, end_date)
    weather_fabricated = weather.pop("_fabricated", False)
    if weather_fabricated:
        fabricated.append("weather")

    soil = SoilDataFetcher.fetch_soil_data(lat, lon, location_name)
    # Soil now uses per-property fabrication tracking. Each property that is
    # still fabricated contributes a `soil.<property>` entry to the report's
    # data-quality list, so the UI can warn about exactly the missing pieces
    # (e.g. salinity) rather than the whole soil section.
    #
    # NOTE: we read but don't pop `_fabricated_fields` — the SM overlay
    # below needs to flip its `soil_moisture_current` flag in place, and
    # downstream consumers may want to inspect the per-field flags too.
    soil_fabricated_fields = soil.get("_fabricated_fields")
    if soil_fabricated_fields is None:
        # Legacy whole-dict flag (kept for backward compat with any caller
        # still using `_fabricated: True`).
        if soil.pop("_fabricated", False):
            fabricated.append("soil")
    else:
        for prop, is_fab in soil_fabricated_fields.items():
            if is_fab:
                fabricated.append(f"soil.{prop}")

    # Real surface soil moisture from Open-Meteo (m³/m³), normalised to a
    # fraction-of-field-capacity using SoilGrids' texture. Without the
    # texture-based conversion, raw m³/m³ values (typical 0.2-0.3) would
    # trip the < 0.5 thresholds in growth_yield/projection.py and produce
    # spurious "water stress" verdicts even on well-watered soil.
    sm_m3m3 = (weather.get("daily") or {}).get("soil_moisture_0_to_7cm_mean")
    if not weather_fabricated and sm_m3m3 is not None:
        texture = soil["properties"].get("texture", "loam")
        fc_m3m3 = field_capacity_from_texture(texture)
        sm_fraction = max(0.0, min(1.0, sm_m3m3 / fc_m3m3)) if fc_m3m3 else 0.0
        soil["properties"]["soil_moisture_current"] = round(sm_fraction, 2)
        soil["properties"]["soil_moisture_m3m3"] = round(sm_m3m3, 3)
        if soil_fabricated_fields is not None:
            soil_fabricated_fields["soil_moisture_current"] = False
        # Drop the now-stale `soil.soil_moisture_current` entry from the
        # top-level fabricated list (it was added a few lines above when
        # we first scanned `_fabricated_fields`).
        fabricated = [f for f in fabricated if f != "soil.soil_moisture_current"]

    # If SoilGrids said the AOI centroid is in built-up land, surface a
    # prominent alert so the UI tells the user to redraw the polygon over
    # actual cropland (per the project convention — see memory file
    # `feedback_no_data_in_city`).
    if soil.pop("_aoi_in_built_up_land", False):
        alerts.append({
            "kind": "aoi_in_built_up_land",
            "title": "AOI is in built-up land",
            "message": (
                "Your AOI centroid lies on a pixel that ISRIC SoilGrids has "
                "classified as built-up / non-soil (typically urban, water, "
                "or bare rock). Real soil properties cannot be retrieved for "
                "this location, so the soil section is using regional "
                "template values only."
            ),
            "action": (
                "Re-draw the AOI polygon over actual cropland and resubmit."
            ),
        })

    crop_data = CropPhenologyDatabase.get_crop_data(crop_name)
    t_base = crop_data.get("t_base", 10.0)

    accumulated_gdd = 0.0
    if "daily" in weather and "temp_mean" in weather["daily"]:
        for temp in weather["daily"]["temp_mean"]:
            if temp is not None:
                accumulated_gdd += max(0.0, float(temp) - t_base)

    return {
        "location": location,
        "weather": weather,
        "soil": soil,
        "crop": crop_data,
        "current_growth_stage": CropPhenologyDatabase.get_current_growth_stage(
            crop_name, days_since_sowing, accumulated_gdd=accumulated_gdd),
        "sowing_date": sowing_date or datetime.now().strftime("%Y-%m-%d"),
        "days_since_sowing": days_since_sowing,
        "accumulated_gdd": round(accumulated_gdd, 1),
        "crop_name": crop_name,
        "_fabricated_sources": fabricated,
        "_alerts": alerts,
    }
