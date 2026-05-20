"""
Irrigation scheduling workflow.
Uses IrrigationCalculator (et0.py) for the underlying math.
"""

from typing import Dict, Any
from datetime import datetime, timedelta

from .et0 import IrrigationCalculator


class IrrigationScheduler:
    """Generate irrigation schedule based on water requirements"""

    @staticmethod
    def generate_schedule(aoi_data: Dict[str, Any], ndvi_data: Dict[str, Any],
                          area_acres: float, forecast_days: int = 7) -> Dict[str, Any]:
        weather = aoi_data.get("weather", {})
        soil = aoi_data.get("soil", {})
        growth_stage = aoi_data.get("current_growth_stage", {})
        crop_name = aoi_data.get("crop_name", "apple")

        daily_weather = weather.get("daily", {})
        temp_mean = daily_weather.get("temp_mean", [30])[-1]
        temp_max = daily_weather.get("temp_max", [35])[-1]
        temp_min = daily_weather.get("temp_min", [25])[-1]
        solar_radiation = daily_weather.get("solar_radiation", [25])[-1]
        rainfall = daily_weather.get("rainfall", [0])[-1]
        wind_speed = daily_weather.get("wind_speed", [8])[-1] / 3.6

        rvi = ndvi_data["rvi"]

        day_of_year = datetime.now().timetuple().tm_yday
        et0 = IrrigationCalculator.calculate_et0_hargreaves_samani(
            temp_mean, temp_max, temp_min, solar_radiation,
            aoi_data["location"]["latitude"], day_of_year, wind_speed
        )

        growth_stage_name = growth_stage.get("stage", "initial")
        kc = IrrigationCalculator.calculate_kc(crop_name, growth_stage_name, rvi)
        etc = IrrigationCalculator.calculate_etc(et0, kc)

        irrigation_requirement = max(0, etc - (rainfall / 1000.0))

        schedule = {
            "et0_mm_per_day": round(et0, 2),
            "kc": round(kc, 2),
            "etc_mm_per_day": round(etc, 2),
            "rainfall_mm": round(rainfall, 1),
            "net_irrigation_mm": round(irrigation_requirement * 1000, 2),
            "total_water_mm": 0,
            "irrigation_days": 0,
            "best_time": "05:00-08:00",
            "daily_schedule": []
        }

        total_water = 0
        irrigation_count = 0

        for day in range(forecast_days):
            date = (datetime.now() + timedelta(days=day)).strftime("%d/%m/%y")

            if day % 2 == 0 and irrigation_requirement > 0:
                irrigation_mm = irrigation_requirement * 1000
                total_water += irrigation_mm
                irrigation_count += 1

                schedule["daily_schedule"].append({
                    "date": date,
                    "drip_mm": round(irrigation_mm, 1),
                    "basin_mm": round(irrigation_mm, 1),
                    "sprinkler_mm": round(irrigation_mm, 1),
                    "rainfall": "0 mm",
                    "rain_percent": "0%",
                    "evapotransp": "High" if etc > 6 else "Moderate"
                })
            else:
                schedule["daily_schedule"].append({
                    "date": date,
                    "drip_mm": 0.0,
                    "basin_mm": 0.0,
                    "sprinkler_mm": 0.0,
                    "rainfall": "0 mm",
                    "rain_percent": "5%",
                    "evapotransp": "High" if etc > 6 else "Moderate"
                })

        schedule["total_water_mm"] = round(total_water, 1)
        schedule["irrigation_days"] = irrigation_count
        schedule["irrigation_method_notes"] = "Alternate-day drip irrigation recommended for water-holding soils"

        return schedule
