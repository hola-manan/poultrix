"""
AOI data composer — assembles weather + soil + geocoding + phenology
into the single dict shape consumed by the advisory service.

Each sub-adapter sets a private `_fabricated` flag when it falls back to
defaults; this composer hoists those flags into a top-level
`_fabricated_sources` list so callers can surface them in the report.
"""

import os
from datetime import datetime
from typing import Dict, Any, List

from .weather import WeatherDataFetcher
from .soil import SoilDataFetcher, field_capacity_from_texture
from .geocoding import GeographicDataFetcher
from .terrain import TerrainDataFetcher
from .nisar import NisarSoilMoistureClient
from .soil_nutrients import resolve_npk

# Phenology is pure domain data (no I/O) — infrastructure may depend on domain.
from jeevn.domain.crop.phenology import CropPhenologyDatabase
from jeevn.infrastructure import pseudo_satellite


def fetch_aoi_data(lat: float, lon: float, location_name: str = "",
                   start_date: str = None, end_date: str = None,
                   crop_name: str = "apple",
                   sowing_date: str = None,
                   sensor_soil_moisture: float = None,
                   sensor_is_fraction: bool = False,
                   soil_test: Dict[str, Any] = None,
                   growth_stage_override: str = None) -> Dict[str, Any]:
    """Fetch all required agricultural data for an AOI.

    Adds a top-level `_fabricated_sources` list naming each sub-source that
    fell back to pseudo defaults (`weather`, `soil`, `location`,
    `days_since_sowing`).

    Real-time overrides (optional):
      * `sensor_soil_moisture` — a fresh in-field reading. Raw volumetric
        (m³/m³) by default, or already fraction-of-field-capacity when
        `sensor_is_fraction=True`. Raw values are normalised here using the
        AOI's real SoilGrids texture, then used as the highest-priority
        soil-moisture source (above NISAR/Open-Meteo).
      * `soil_test` — host-DB soil test ({nutrient: 'low'|'medium'|'high' or a
        0..1 supply fraction}); top tier of the NPK resolver.
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

    # Forward 7-day forecast (distinct from the historical archive above) —
    # the irrigation scheduler subtracts per-day forecast rain from per-day
    # ETc. Archive data is backward-looking and can't gate a forward schedule.
    forecast = WeatherDataFetcher.fetch_forecast(lat, lon, days=7)
    if forecast.pop("_fabricated", False):
        fabricated.append("forecast")

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

    # Ground sensor override — highest-priority soil-moisture source. A fresh
    # in-field reading beats modelled and satellite estimates, so it overwrites
    # `soil_moisture_current` and clears the fabricated flag regardless of what
    # the weather overlay produced. Raw m³/m³ is normalised to
    # fraction-of-field-capacity using the AOI's real texture so it lands on the
    # same 0..1 scale the deficit / pest-weed thresholds expect.
    if sensor_soil_moisture is not None:
        if sensor_is_fraction:
            sensor_frac = float(sensor_soil_moisture)
        else:
            fc_m3m3 = field_capacity_from_texture(
                soil["properties"].get("texture", "loam"))
            sensor_frac = (float(sensor_soil_moisture) / fc_m3m3) if fc_m3m3 else 0.0
        sensor_frac = max(0.0, min(1.0, sensor_frac))
        soil["properties"]["soil_moisture_current"] = round(sensor_frac, 2)
        soil["properties"]["soil_moisture_source"] = "ground-sensor"
        if soil_fabricated_fields is not None:
            soil_fabricated_fields["soil_moisture_current"] = False
        fabricated = [f for f in fabricated if f != "soil.soil_moisture_current"]

    # Radar Soil Moisture (RSM) — tiered, retires the old fabricated 0.72
    # constant. Same fraction-of-field-capacity scale as soil_moisture_current
    # so the pest/weed thresholds keep working.
    #   1. NISAR SME2 L-band (m³/m³ -> fraction) — only attempted when
    #      Earthdata creds are present (search+download both pointless
    #      otherwise); currently dormant until SME2 production resumes.
    #   2. Open-Meteo soil_moisture_current (already a real fraction).
    #   3. Fabricated default (flagged).
    texture_for_rsm = soil["properties"].get("texture", "loam")
    fc_for_rsm = field_capacity_from_texture(texture_for_rsm)
    rsm: Dict[str, Any] = {"value": pseudo_satellite.RSM, "source": "fabricated"}

    # Tier 0: ground sensor (already a real fraction-of-field-capacity).
    if sensor_soil_moisture is not None:
        rsm = {
            "value": soil["properties"]["soil_moisture_current"],
            "source": "ground-sensor",
        }

    nisar_sm = None
    if rsm["source"] == "fabricated" and os.environ.get("EARTHDATA_USER") and os.environ.get("EARTHDATA_PASS"):
        nisar_sm = NisarSoilMoistureClient.fetch_sm_at(lat, lon)
    if nisar_sm is not None and fc_for_rsm:
        frac = max(0.0, min(1.0, nisar_sm["soil_moisture_m3m3"] / fc_for_rsm))
        rsm = {
            "value": round(frac, 2),
            "source": "nisar-sme2",
            "m3m3": nisar_sm["soil_moisture_m3m3"],
            "pass_date": nisar_sm["pass_date"],
            "algorithm": nisar_sm["algorithm"],
        }
    elif rsm["source"] == "fabricated":
        # Only fall to Open-Meteo when nothing higher-priority (ground sensor /
        # NISAR) already resolved the RSM.
        sm_current = soil["properties"].get("soil_moisture_current")
        sm_is_real = (soil_fabricated_fields or {}).get("soil_moisture_current") is False
        if sm_current is not None and sm_is_real:
            rsm = {"value": sm_current, "source": "open-meteo"}

    if rsm["source"] == "fabricated":
        fabricated.append("rsm")

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

    # Terrain (slope + aspect). Two-tier: Open-Elevation -> bundled DEM ->
    # fabricated defaults. The fetcher always returns a dict; the only
    # signal we surface is `_fabricated` (True iff both real sources
    # failed). The `source` field on the dict ("open-elevation",
    # "bundled-dem", "fabricated") tells downstream consumers where the
    # values came from.
    terrain = TerrainDataFetcher.fetch_terrain(lat, lon)
    if terrain.pop("_fabricated", False):
        fabricated.append("terrain")

    crop_data = CropPhenologyDatabase.get_crop_data(crop_name)
    t_base = crop_data.get("t_base", 10.0)

    accumulated_gdd = 0.0
    if "daily" in weather and "temp_mean" in weather["daily"]:
        for temp in weather["daily"]["temp_mean"]:
            if temp is not None:
                accumulated_gdd += max(0.0, float(temp) - t_base)

    # Tiered soil N/P/K supply profile (soil test → SHC district →
    # SoilGrids/pedotransfer). Consumed by the fertilizer requirement calc to
    # replace the legacy hardcoded "current levels" constant.
    soil_nutrients = resolve_npk(location, soil.get("properties", {}), soil_test)

    # Growth stage: derived from phenology (sowing date + GDD) by default, but a
    # host project can inject the authoritative stage from its own crop DB.
    growth_stage = CropPhenologyDatabase.get_current_growth_stage(
        crop_name, days_since_sowing, accumulated_gdd=accumulated_gdd)
    if growth_stage_override:
        growth_stage = {**growth_stage, "stage": growth_stage_override,
                        "source": "host-db-override"}

    return {
        "location": location,
        "weather": weather,
        "forecast": forecast,
        "soil": soil,
        "terrain": terrain,
        "radar_soil_moisture": rsm,
        "soil_nutrients": soil_nutrients,
        "crop": crop_data,
        "current_growth_stage": growth_stage,
        "sowing_date": sowing_date or datetime.now().strftime("%Y-%m-%d"),
        "days_since_sowing": days_since_sowing,
        "accumulated_gdd": round(accumulated_gdd, 1),
        "crop_name": crop_name,
        "_fabricated_sources": fabricated,
        "_alerts": alerts,
    }
