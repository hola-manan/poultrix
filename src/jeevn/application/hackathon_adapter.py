"""
Adapter for the hackathon irrigation advisory module.
Transforms the Jeevn AOI data and report dictionaries into the exact dataclasses 
expected by irrigation_advisory.py.
"""
import sys
from typing import List, Dict, Any

# Attempt to import the external hackathon module
try:
    sys.path.append(r"C:\Users\manan\OneDrive2\Desktop\ashi\hackathon")
    from irrigation_advisory import WeatherForecast, SoilData, generate_advisory
except ImportError:
    # Fallback definitions if the path is unavailable
    from dataclasses import dataclass

    @dataclass
    class WeatherForecast:
        day_offset: int
        temperature_max: float
        temperature_min: float
        humidity: float
        wind_speed: float
        solar_radiation: float
        rainfall: float

    @dataclass
    class SoilData:
        field_capacity: float
        wilting_point: float
        stress_threshold: float

    def generate_advisory(*args, **kwargs):
        return "Hackathon module not found."


def generate_hackathon_advisory(aoi_data: Dict[str, Any], soil_analysis: Dict[str, Any], farmer_interval: int = 4) -> str:
    """
    Extracts weather, crop, and soil data from the Jeevn pipeline, converts units 
    (e.g., volumetric water to mm), and runs the hackathon smart advisory.
    """
    # 1. Extract Crop Data
    crop_data = aoi_data.get("crop", {})
    crop_kc = crop_data.get("Kc_mid", 1.0)
    root_depth_m = crop_data.get("root_depth_m", 0.6)

    # 2. Extract and Convert Soil Data (Volumetric m³/m³ to mm)
    # 1 m³/m³ = 1000 mm of water per meter of soil depth
    # So multiply by root_depth_m * 1000 to get total mm in the root zone
    fc_vol = soil_analysis.get("field_capacity_vol", 0.27)
    pwp_vol = soil_analysis.get("permanent_wilting_point_vol", 0.13)
    
    fc_mm = fc_vol * root_depth_m * 1000
    pwp_mm = pwp_vol * root_depth_m * 1000
    mad_mm = pwp_mm + (fc_mm - pwp_mm) * 0.5  # 50% Management Allowed Depletion

    soil = SoilData(
        field_capacity=fc_mm,
        wilting_point=pwp_mm,
        stress_threshold=mad_mm
    )

    # 3. Current Moisture (fraction of FC * FC mm)
    # Our system normalizes current_moisture as a fraction of Field Capacity (0 to 1).
    current_sm_fraction = soil_analysis.get("soil_moisture_current", 0.5)
    current_moisture_mm = current_sm_fraction * fc_mm

    # 4. Extract Weather Forecast
    # aoi_data structure usually places forecast inside weather dict
    weather = aoi_data.get("weather", {})
    # If the forecast is nested under 'forecast':
    forecast_data = weather.get("forecast", weather) 
    
    daily = forecast_data.get("daily", {})
    today_idx = forecast_data.get("today_index", 0)
    
    forecast_7_days: List[WeatherForecast] = []
    
    dates = daily.get("dates", [])
    temp_max = daily.get("temp_max", [])
    temp_min = daily.get("temp_min", [])
    humidity = daily.get("humidity", [])
    wind = daily.get("wind_speed", [])
    solar = daily.get("solar_radiation", [])
    rain = daily.get("rainfall", [])

    # Construct exactly 7 days of forecast starting from today
    for i in range(today_idx, min(len(dates), today_idx + 7)):
        forecast_7_days.append(WeatherForecast(
            day_offset=i - today_idx,
            temperature_max=temp_max[i] if temp_max and len(temp_max) > i else 30.0,
            temperature_min=temp_min[i] if temp_min and len(temp_min) > i else 20.0,
            humidity=humidity[i] if humidity and len(humidity) > i and humidity[i] is not None else 60.0,
            wind_speed=wind[i] if wind and len(wind) > i else 10.0,
            solar_radiation=solar[i] if solar and len(solar) > i else 15.0,
            rainfall=rain[i] if rain and len(rain) > i else 0.0,
        ))
        
    # Ensure we always have 7 days even if forecast fell short
    while len(forecast_7_days) < 7:
        offset = len(forecast_7_days)
        forecast_7_days.append(WeatherForecast(
            day_offset=offset, temperature_max=30.0, temperature_min=20.0,
            humidity=60.0, wind_speed=10.0, solar_radiation=15.0, rainfall=0.0
        ))

    # 5. Run the external advisory function
    return generate_advisory(
        current_moisture=current_moisture_mm,
        forecast_7_days=forecast_7_days,
        soil=soil,
        farmer_interval=farmer_interval,
        crop_kc=crop_kc
    )
