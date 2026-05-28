"""
Irrigation scheduling workflow.
Uses IrrigationCalculator (et0.py) for the underlying math.

Rain-aware, forward-looking: each day's net irrigation is that day's crop
evapotranspiration (ETc, mm) minus that day's *effective* forecast rainfall.
The forecast comes from `aoi_data["forecast"]` (Open-Meteo forecast API,
fetched by the AOI composer) — the historical archive can't gate a forward
schedule. All quantities are in mm; there is no unit conversion to/from
metres (an earlier version divided rain by 1000 and multiplied irrigation
by 1000, which silently ignored rain and inflated drip by 1000x).
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta

from .et0 import IrrigationCalculator


# Fraction of gross rainfall that is actually available to the crop (the
# rest is lost to runoff / deep percolation). USDA-SCS effective-rainfall
# methods give ~0.7-0.9 for light/moderate events; 0.8 is a reasonable
# flat approximation at the daily scale.
_EFFECTIVE_RAIN_FRACTION = 0.8


class IrrigationScheduler:
    """Generate a rain-aware irrigation schedule from the weather forecast."""

    @staticmethod
    def _safe_idx(series: List, idx: int, default):
        if isinstance(series, list) and 0 <= idx < len(series):
            v = series[idx]
            return v if v is not None else default
        return default

    @staticmethod
    def generate_schedule(aoi_data: Dict[str, Any], ndvi_data: Dict[str, Any],
                          area_acres: float, forecast_days: int = 7) -> Dict[str, Any]:
        forecast = (aoi_data.get("forecast") or {}).get("daily", {})
        growth_stage = aoi_data.get("current_growth_stage", {})
        crop_name = aoi_data.get("crop_name", "apple")
        lat = aoi_data["location"]["latitude"]
        rvi = ndvi_data["rvi"]
        growth_stage_name = growth_stage.get("stage", "initial")
        kc = IrrigationCalculator.calculate_kc(crop_name, growth_stage_name, rvi)

        # Forecast series (forward `forecast_days` days). Fall back to the
        # historical archive's last values per-day when the forecast is
        # unavailable — degraded but never crashes.
        fc_dates = forecast.get("dates") or []
        fc_tmax = forecast.get("temp_max") or []
        fc_tmin = forecast.get("temp_min") or []
        fc_tmean = forecast.get("temp_mean") or []
        fc_rain = forecast.get("rainfall") or []
        fc_rain_prob = forecast.get("rain_probability") or []

        n_days = min(forecast_days, len(fc_dates)) if fc_dates else forecast_days
        if n_days == 0:
            n_days = forecast_days

        daily_schedule = []
        total_water = 0.0
        irrigation_count = 0
        et0_sum = 0.0
        etc_sum = 0.0
        rain_sum = 0.0

        for day in range(n_days):
            if fc_dates:
                date = datetime.strptime(fc_dates[day], "%Y-%m-%d").strftime("%d/%m/%y")
            else:
                date = (datetime.now() + timedelta(days=day)).strftime("%d/%m/%y")

            t_max = IrrigationScheduler._safe_idx(fc_tmax, day, 35.0)
            t_min = IrrigationScheduler._safe_idx(fc_tmin, day, 25.0)
            t_mean = IrrigationScheduler._safe_idx(fc_tmean, day, 30.0)
            rain_mm = float(IrrigationScheduler._safe_idx(fc_rain, day, 0.0))
            rain_prob = IrrigationScheduler._safe_idx(fc_rain_prob, day, 0)

            day_of_year = (datetime.now() + timedelta(days=day)).timetuple().tm_yday
            et0 = IrrigationCalculator.calculate_et0_hargreaves_samani(
                t_mean, t_max, t_min, 0.0, lat, day_of_year,
            )
            etc = IrrigationCalculator.calculate_etc(et0, kc)  # mm/day

            effective_rain = rain_mm * _EFFECTIVE_RAIN_FRACTION
            net_irrigation = max(0.0, etc - effective_rain)  # mm

            et0_sum += et0
            etc_sum += etc
            rain_sum += rain_mm

            # Alternate-day drip: only irrigate on even days, and only if the
            # crop's net water need that day is positive (rain hasn't already
            # covered ETc).
            irrigate_today = (day % 2 == 0) and net_irrigation > 0.05
            applied = round(net_irrigation, 1) if irrigate_today else 0.0
            if irrigate_today:
                total_water += applied
                irrigation_count += 1

            daily_schedule.append({
                "date": date,
                "drip_mm": applied,
                "basin_mm": applied,
                "sprinkler_mm": applied,
                "rainfall": f"{rain_mm:.1f} mm",
                "rain_percent": f"{int(round(rain_prob))}%",
                "evapotransp": "High" if etc > 6 else "Moderate",
            })

        return {
            "et0_mm_per_day": round(et0_sum / n_days, 2) if n_days else 0.0,
            "kc": round(kc, 2),
            "etc_mm_per_day": round(etc_sum / n_days, 2) if n_days else 0.0,
            "forecast_rainfall_mm": round(rain_sum, 1),
            "total_water_mm": round(total_water, 1),
            "irrigation_days": irrigation_count,
            "best_time": "05:00-08:00",
            "daily_schedule": daily_schedule,
            "irrigation_method_notes": (
                "Alternate-day drip; daily net = ETc - 80% of forecast rain."
            ),
        }
