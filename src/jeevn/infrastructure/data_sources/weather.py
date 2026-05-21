"""
Weather data adapter — Open-Meteo client.

On failure, returns the fallback series from `infrastructure.pseudo_satellite`
with `_fabricated=True` so the report can flag it.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, Any

from jeevn.infrastructure import pseudo_satellite


class WeatherDataFetcher:
    """Fetch weather data from Open-Meteo API (free, no API key needed)."""

    @staticmethod
    def fetch_weather(lat: float, lon: float, start_date: str = None,
                      end_date: str = None) -> Dict[str, Any]:
        try:
            url = "https://archive-api.open-meteo.com/v1/archive"

            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            # Open-Meteo's archive-api only covers historical dates. The
            # caller can pass crop sowing/end dates that lie in the future
            # (e.g. a sowing date plus a 6-month season); clamping to today
            # avoids a 400 Bad Request and falls back to "up to today".
            today_iso = datetime.now().strftime("%Y-%m-%d")
            if start_date > today_iso:
                start_date = today_iso
            if end_date > today_iso:
                end_date = today_iso
            # Guarantee start <= end after clamping.
            if start_date > end_date:
                start_date = end_date

            # Open-Meteo renamed some daily variables: the legacy names
            # `precipitation` and `radiation_sum` now 400 with
            # "Cannot initialize ForecastVariableDaily from invalid String
            # value ..." — they must be the `_sum` variants. The wind name
            # is still accepted as `windspeed_10m_max`.
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                "daily": ",".join([
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "temperature_2m_mean",
                    "precipitation_sum",
                    "shortwave_radiation_sum",
                    "windspeed_10m_max",
                ]),
                "timezone": "auto",
                "temperature_unit": "celsius",
                "windspeed_unit": "kmh",
                "precipitation_unit": "mm",
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            daily_data = data.get("daily", {})
            return {
                "location": {
                    "latitude": lat,
                    "longitude": lon,
                    "timezone": data.get("timezone", "UTC")
                },
                "daily": {
                    "dates": daily_data.get("time", []),
                    "temp_max": daily_data.get("temperature_2m_max", []),
                    "temp_min": daily_data.get("temperature_2m_min", []),
                    "temp_mean": daily_data.get("temperature_2m_mean", []),
                    "rainfall": daily_data.get("precipitation_sum", []),
                    "solar_radiation": daily_data.get("shortwave_radiation_sum", []),
                    "wind_speed": daily_data.get("windspeed_10m_max", []),
                },
                "_fabricated": False,
            }
        except Exception as e:
            print(f"[WARN] Weather fetch failed: {e}")
            return pseudo_satellite.make_default_weather(lat, lon)
