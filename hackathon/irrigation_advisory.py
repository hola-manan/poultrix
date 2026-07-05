from dataclasses import dataclass
from typing import List

@dataclass
class WeatherForecast:
    day_offset: int  # 0 for today, 1 for tomorrow, etc.
    temperature_max: float
    temperature_min: float
    humidity: float
    wind_speed: float
    solar_radiation: float
    rainfall: float

@dataclass
class SoilData:
    field_capacity: float      # Max water soil can hold (mm)
    wilting_point: float       # Point where plant dies (mm)
    stress_threshold: float    # Management Allowed Depletion (MAD) threshold (mm)

def calculate_reference_et(weather: WeatherForecast) -> float:
    """
    Mock FAO-56 Penman-Monteith calculation.
    In a real system, you would implement the full mathematical formula here
    using temp, humidity, wind, and solar radiation.
    """
    # Dummy placeholder calculation
    return 3.0 + (weather.temperature_max * 0.1)

def calculate_crop_usage(weather: WeatherForecast, crop_kc: float) -> float:
    """Calculates specific crop evapotranspiration (ETc)"""
    et0 = calculate_reference_et(weather)
    return et0 * crop_kc

def sum_rain(forecast: List[WeatherForecast], window: int) -> float:
    """Sums forecasted rain over the next N days."""
    return sum(day.rainfall for day in forecast[:window])

def generate_advisory(
    current_moisture: float, 
    forecast_7_days: List[WeatherForecast], 
    soil: SoilData,
    farmer_interval: int,
    crop_kc: float
) -> str:
    """
    Generates a smart irrigation advisory considering fixed schedules and upcoming rain.
    """
    simulated_moisture = current_moisture
    will_stress_before_next_cycle = False
    
    # 1. Project moisture over the farmer's mandatory waiting period (interval)
    for i in range(farmer_interval):
        # Prevent index errors if interval is longer than our forecast
        if i >= len(forecast_7_days):
            break 
            
        weather_today = forecast_7_days[i]
        
        # Add rain, subtract plant usage
        simulated_moisture += weather_today.rainfall
        simulated_moisture -= calculate_crop_usage(weather_today, crop_kc)
        
        # Cap at field capacity (excess is lost to runoff/deep percolation)
        if simulated_moisture > soil.field_capacity:
            simulated_moisture = soil.field_capacity
            
        # Check if we hit the danger zone
        if simulated_moisture < soil.stress_threshold:
             will_stress_before_next_cycle = True
             break
             
    # 2. If they are safe until their next cycle, do nothing.
    if not will_stress_before_next_cycle:
        return "STATUS GREEN: No irrigation needed. Moisture is sufficient for your current cycle."
        
    # 3. If they WILL stress, check for rain BEFORE telling them to irrigate
    # We look ahead a few days to see if free water is coming
    lookahead_window = 3 
    upcoming_rain_total = sum_rain(forecast_7_days, window=lookahead_window) 
    
    # Calculate how much water is needed to fill the soil back to 100% capacity
    deficit_to_fill = soil.field_capacity - current_moisture
    
    if upcoming_rain_total >= deficit_to_fill:
        return f"STATUS YELLOW: Soil getting dry, but {upcoming_rain_total:.1f}mm rain expected soon. HOLD irrigation to capture free rain."
        
    elif upcoming_rain_total > 0:
        # Partial rain coming. Just irrigate the difference so we don't overflow when it rains!
        needed_water = deficit_to_fill - upcoming_rain_total
        return f"STATUS ORANGE: Irrigate {needed_water:.1f}mm today. (Relying on {upcoming_rain_total:.1f}mm of upcoming rain to cover the rest)."
        
    else:
        # No rain coming. Fill the bucket completely so it lasts until their next allowed watering day.
        return f"STATUS RED: Irrigate {deficit_to_fill:.1f}mm today to survive until your next cycle."
