"""
Real-time advisory orchestrator.

Ties together the accurate `jeevn` report pipeline, a ground soil-moisture
sensor, low-latency rainfall, and the dry-spell detector to produce a live
advisory + alert set. Delivery is handled by a `Notifier` (Part 1 ships
`ConsoleNotifier`; SMS/WhatsApp is Part 2).

Flow:
  1. read the (optional) ground sensor; drop stale readings
  2. run the full accurate report (soil, irrigation, fertiliser, …) with the
     sensor fused as the top-priority soil-moisture source
  3. fetch low-latency recent + forward rainfall (forecast API `past_days`)
  4. compute the soil-water deficit from the fused moisture
  5. detect a dry spell (fail-safe on missing/fabricated weather)
  6. build + deliver alerts
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from jeevn.infrastructure.data_sources.weather import WeatherDataFetcher
from jeevn.infrastructure.data_sources.soil import field_capacity_from_texture
from jeevn.infrastructure.sensors.base import SoilSensor
from jeevn.domain.irrigation.et0 import IrrigationCalculator
from jeevn.domain.dry_spell import DrySpellDetector
from jeevn.application.advisory_service import AgriculturalReportGenerator
from jeevn.application.alerts import build_alerts
from jeevn.application.notifier import Notifier


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass
class AdvisoryConfig:
    past_days: int = 10          # recent-rain window for the "current dry run"
    forecast_days: int = 7       # forward horizon
    dry_day_mm: float = 1.0      # a day under this many mm counts as dry
    rain_prob_pct: float = 30.0  # forecast day with prob >= this is not "dry"
    dry_spell_days: int = 5      # threshold to flag a dry spell
    leach_rain_mm: float = 15.0  # >= this rain in 48h → hold fertigation
    sensor_max_age_min: int = 180  # readings older than this are ignored
    # Wilting point as a fraction of field capacity (loam-typical 0.12/0.25).
    wilting_fraction_of_fc: float = 0.48

    @classmethod
    def from_env(cls) -> "AdvisoryConfig":
        return cls(
            past_days=_env_int("PAST_DAYS", 10),
            forecast_days=_env_int("FORECAST_DAYS", 7),
            dry_day_mm=_env_float("DRY_DAY_MM", 1.0),
            rain_prob_pct=_env_float("RAIN_PROB_PCT", 30.0),
            dry_spell_days=_env_int("DRY_SPELL_DAYS", 5),
            leach_rain_mm=_env_float("LEACH_RAIN_MM", 15.0),
            sensor_max_age_min=_env_int("SENSOR_MAX_AGE_MIN", 180),
        )


class RealtimeAdvisor:
    """Produce a live irrigation/fertilisation advisory + alerts for one AOI."""

    def __init__(self, config: Optional[AdvisoryConfig] = None):
        self.config = config or AdvisoryConfig.from_env()

    def evaluate(self, lat: float, lon: float, crop: str = "apple",
                 sowing_date: Optional[str] = None, area_acres: float = 1.0,
                 sensor: Optional[SoilSensor] = None,
                 growth_stage_override: Optional[str] = None,
                 soil_test: Optional[Dict[str, Any]] = None,
                 location_name: str = "",
                 notifier: Optional[Notifier] = None) -> Dict[str, Any]:
        cfg = self.config

        # 1. Ground sensor — drop stale readings so we never trigger on old data.
        reading = None
        if sensor is not None:
            r = sensor.read()
            if r is not None and r.is_fresh(cfg.sensor_max_age_min):
                reading = r

        # 2. Full accurate report, with the sensor fused as top-priority moisture.
        report = AgriculturalReportGenerator.generate_report(
            lat=lat, lon=lon, area_acres=area_acres, crop_name=crop,
            sowing_date=sowing_date, location_name=location_name,
            sensor_reading=reading, growth_stage_override=growth_stage_override,
            soil_test=soil_test,
        )

        # 3. Low-latency recent + forward rainfall (fail-safe if fabricated).
        fc = WeatherDataFetcher.fetch_forecast(
            lat, lon, days=cfg.forecast_days, past_days=cfg.past_days)
        data_gap = bool(fc.get("_fabricated"))
        daily = fc.get("daily", {})
        dates = daily.get("dates", []) or []
        rain = daily.get("rainfall", []) or []
        prob = daily.get("rain_probability", []) or []
        today_idx = fc.get("today_index", 0) or 0
        today_idx = max(0, min(today_idx, len(rain)))
        recent_rain = rain[:today_idx]
        forecast_rain = rain[today_idx:]
        forecast_prob = prob[today_idx:]

        # 4. Soil-water deficit from the fused moisture (real reused function).
        deficit_mm = self._deficit_from_report(report)

        # 5. Dry-spell detection (gap-safe).
        dry_spell = DrySpellDetector.detect(
            recent_rain, forecast_rain, forecast_prob,
            dry_day_mm=cfg.dry_day_mm, rain_prob_pct=cfg.rain_prob_pct,
            min_dry_days=cfg.dry_spell_days,
            soil_moisture_deficit_mm=deficit_mm,
            data_gap=data_gap,
        )

        # 6. Leaching risk = rain in the next 48 h (skip on a data gap).
        leach_48h = None if data_gap else float(sum(
            (r or 0.0) for r in forecast_rain[:2]))

        location_label = (report.get("aoi_info", {}).get("location")
                          or location_name)
        alerts = build_alerts(
            report, dry_spell, deficit_mm, leach_48h,
            crop=crop, location=location_label,
            leach_threshold_mm=cfg.leach_rain_mm,
        )

        advisory = {
            "report": report,
            "dry_spell": dry_spell,
            "alerts": alerts,
            "crop": crop,
            "location": location_label,
            "sensor_used": reading is not None,
            "weather_data_gap": data_gap,
        }

        if notifier is not None:
            notifier.send(alerts)

        return advisory

    def _deficit_from_report(self, report: Dict[str, Any]) -> Optional[float]:
        """Convert the report's fraction-of-field-capacity soil moisture into a
        volumetric value and run the reused FAO deficit calc. Returns mm, or
        None when soil moisture is unavailable."""
        soil = report.get("environmental_context", {}).get("soil", {})
        props = soil.get("properties", {})
        frac = props.get("soil_moisture_current")
        if frac is None:
            return None
        texture = props.get("texture", "loam")
        fc_m3m3 = field_capacity_from_texture(texture)
        if not fc_m3m3:
            return None
        wp_m3m3 = fc_m3m3 * self.config.wilting_fraction_of_fc
        current_vol = float(frac) * fc_m3m3
        return IrrigationCalculator.calculate_soil_water_deficit(
            current_vol, field_capacity=fc_m3m3, wilting_point=wp_m3m3)
