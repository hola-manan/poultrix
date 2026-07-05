"""
Weather data adapter — Open-Meteo client.

Pulls daily climate variables (temp, precipitation, radiation, wind) from
the archive-api, plus hourly surface soil moisture (`soil_moisture_0_to_7cm`).
The last-24-hour mean of that hourly series is surfaced as
`daily.soil_moisture_0_to_7cm_mean` (in m³/m³) — the AOI composer combines
it with the real SoilGrids texture to produce a fraction-of-field-capacity
soil-moisture value the downstream agronomic models expect.

On failure, returns the fallback series from `infrastructure.pseudo_satellite`
with `_fabricated=True` so the report can flag it.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from jeevn.infrastructure import pseudo_satellite


def _mean_of_last_n(values: List[Optional[float]], n: int) -> Optional[float]:
    """Mean of the last `n` non-null values, or None if there aren't any."""
    if not values:
        return None
    tail = [v for v in values[-n:] if v is not None]
    if not tail:
        return None
    return sum(tail) / len(tail)


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
                # Hourly variables. `soil_moisture_0_to_7cm` (m³/m³) is the
                # surface layer matching SMAP/NISAR — the composer aggregates
                # it to a 24-h mean. `temperature_2m` / `relative_humidity_2m`
                # / `precipitation` drive the grape disease models
                # (Gubler-Thomas powdery mildew, downy-mildew wet-period) which
                # need hourly resolution, not daily aggregates.
                "hourly": ",".join([
                    "temperature_2m",
                    "relative_humidity_2m",
                    "precipitation",
                    "soil_moisture_0_to_7cm",
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
            hourly_data = data.get("hourly", {})

            sm_hourly = hourly_data.get("soil_moisture_0_to_7cm", []) or []
            sm_last_24h_mean = _mean_of_last_n(sm_hourly, n=24)

            rh_hourly = hourly_data.get("relative_humidity_2m", []) or []
            # 24-h mean → `daily.relative_humidity_mean` (grape disease models,
            # growth_yield/pest RH). Also per-day means → `daily.humidity`
            # (consumed by application/hackathon_adapter.py).
            rh_last_24h_mean = _mean_of_last_n(rh_hourly, n=24)
            daily_rh = []
            if rh_hourly:
                for i in range(0, len(rh_hourly), 24):
                    day_rh = [r for r in rh_hourly[i:i+24] if r is not None]
                    daily_rh.append(sum(day_rh) / len(day_rh) if day_rh else None)

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
                    "humidity": daily_rh,
                    # Mean of the most-recent 24 hourly readings (m³/m³).
                    # `None` if Open-Meteo returned no soil-moisture values.
                    "soil_moisture_0_to_7cm_mean": sm_last_24h_mean,
                    # Real measured RH replaces the old fabricated humidity
                    # proxy in the pest/disease model. `None` if unavailable.
                    "relative_humidity_mean": rh_last_24h_mean,
                },
                # Hourly series consumed by the grape disease models. Kept as
                # parallel arrays (Open-Meteo's native shape) aligned on `time`.
                "hourly": {
                    "time": hourly_data.get("time", []),
                    "temperature_2m": hourly_data.get("temperature_2m", []),
                    "relative_humidity_2m": rh_hourly,
                    "precipitation": hourly_data.get("precipitation", []),
                },
                "_fabricated": False,
            }
        except Exception as e:
            print(f"[WARN] Weather fetch failed: {e}")
            return pseudo_satellite.make_default_weather(lat, lon)

    @staticmethod
    def fetch_forecast(lat: float, lon: float, days: int = 7,
                       past_days: int = 0) -> Dict[str, Any]:
        """Fetch a `days`-day forward forecast (plus an optional `past_days` of
        recent history) from Open-Meteo's forecast API — distinct from the
        historical archive used by `fetch_weather`.

        Two consumers rely on this:
          * rain-aware irrigation scheduling — the archive API only covers past
            dates, so a forward schedule cannot subtract future rain without it;
          * near-real-time dry-spell detection — the ERA5 *archive* lags several
            days, so recent "consecutive dry days" must come from the forecast
            endpoint's low-latency `past_days` window, NOT from `fetch_weather`.

        When `past_days > 0`, the daily arrays include those recent days first,
        then the forward days; the `dates`/`today_index` fields let callers split
        the series at today.

        Returns:
            {
              "daily": {dates[], temp_max[], temp_min[], temp_mean[],
                        rainfall[] (mm), rain_probability[] (% 0-100),
                        solar_radiation[], wind_speed[]},
              "today_index": int,   # index of today's date in the daily arrays
              "past_days": int,
              "_fabricated": False,
            }
        On failure → `pseudo_satellite.make_default_forecast(lat, lon, days)`
        (a fabricated, zero-rain placeholder flagged `_fabricated=True` — callers
        doing dry-spell/alerting MUST treat that flag as a data gap and suppress
        alerts rather than trust the zero-rain series).
        """
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "daily": ",".join([
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "temperature_2m_mean",
                    "precipitation_sum",
                    "precipitation_probability_max",
                    "shortwave_radiation_sum",
                    "windspeed_10m_max",
                ]),
                # Forward hourly series — drives the actionable "this week's
                # spray window" disease alert (the forecast, not the archive,
                # is what a weekly advisory loop acts on).
                "hourly": ",".join([
                    "temperature_2m",
                    "relative_humidity_2m",
                    "precipitation",
                ]),
                "forecast_days": days,
                "timezone": "auto",
                "temperature_unit": "celsius",
                "windspeed_unit": "kmh",
                "precipitation_unit": "mm",
            }
            if past_days > 0:
                # Open-Meteo caps past_days at 92; clamp to be safe.
                params["past_days"] = min(int(past_days), 92)

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            daily_data = payload.get("daily", {})
            hourly_data = payload.get("hourly", {})

            # Per-day RH means → daily.humidity (application/hackathon_adapter.py).
            rh_hourly = hourly_data.get("relative_humidity_2m", []) or []
            daily_rh = []
            if rh_hourly:
                for i in range(0, len(rh_hourly), 24):
                    day_rh = [r for r in rh_hourly[i:i+24] if r is not None]
                    daily_rh.append(sum(day_rh) / len(day_rh) if day_rh else None)

            dates = daily_data.get("time", [])
            today_iso = datetime.now().strftime("%Y-%m-%d")
            today_index = dates.index(today_iso) if today_iso in dates else past_days

            return {
                "daily": {
                    "dates": dates,
                    "temp_max": daily_data.get("temperature_2m_max", []),
                    "temp_min": daily_data.get("temperature_2m_min", []),
                    "temp_mean": daily_data.get("temperature_2m_mean", []),
                    "rainfall": daily_data.get("precipitation_sum", []),
                    "rain_probability": daily_data.get("precipitation_probability_max", []),
                    "solar_radiation": daily_data.get("shortwave_radiation_sum", []),
                    "wind_speed": daily_data.get("windspeed_10m_max", []),
                    "humidity": daily_rh,
                },
                "today_index": today_index,
                "past_days": past_days,
                "hourly": {
                    "time": hourly_data.get("time", []),
                    "temperature_2m": hourly_data.get("temperature_2m", []),
                    "relative_humidity_2m": hourly_data.get("relative_humidity_2m", []),
                    "precipitation": hourly_data.get("precipitation", []),
                },
                "_fabricated": False,
            }
        except Exception as e:
            print(f"[WARN] Weather forecast fetch failed: {e}")
            fallback = pseudo_satellite.make_default_forecast(lat, lon, days)
            fallback.setdefault("today_index", 0)
            fallback.setdefault("past_days", 0)
            return fallback
