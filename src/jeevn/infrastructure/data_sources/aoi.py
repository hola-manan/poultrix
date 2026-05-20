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
from .soil import SoilDataFetcher
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
    if weather.pop("_fabricated", False):
        fabricated.append("weather")

    soil = SoilDataFetcher.fetch_soil_data(lat, lon, location_name)
    if soil.pop("_fabricated", False):
        fabricated.append("soil")

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
    }
