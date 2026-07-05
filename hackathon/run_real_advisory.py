import sys
import os

# Add src to python path so we can import jeevn
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from jeevn.infrastructure.data_sources.weather import WeatherDataFetcher
from jeevn.infrastructure.data_sources.soil import SoilDataFetcher, field_capacity_from_texture
from jeevn.infrastructure.data_sources.soil_nutrients import resolve_npk
from jeevn.infrastructure.data_sources.geocoding import GeographicDataFetcher

from fertilization_advisory import generate_fertilizer_advisory, SoilHealthCard, CORN_DATA

def main():
    # Using a coordinate in Karnataka (hub of agriculture) to ensure SoilGrids hits a valid soil pixel
    lat, lon = 15.3, 75.1 
    
    print(f"Fetching real data for lat={lat}, lon={lon} (Farmland)...")
    
    # 1. Fetch all real data from APIs
    weather = WeatherDataFetcher.fetch_weather(lat, lon)
    location = GeographicDataFetcher.get_location_info(lat, lon)
    soil = SoilDataFetcher.fetch_soil_data(lat, lon)
    nutrients = resolve_npk(location, soil.get("properties", {}), None)
    
    # 2. Map to the SoilHealthCard dataclass
    # Handle cases where the SHC resolver might return a fallback structure
    n_kg = nutrients.get("N", {}).get("current_kg_per_acre", 30.0) if nutrients else 30.0
    p_kg = nutrients.get("P", {}).get("current_kg_per_acre", 15.0) if nutrients else 15.0
    k_kg = nutrients.get("K", {}).get("current_kg_per_acre", 150.0) if nutrients else 150.0

    soil_card = SoilHealthCard(
        nitrogen_kg=n_kg,
        phosphorus_kg=p_kg,
        potassium_kg=k_kg,
        ph_level=soil.get("properties", {}).get("ph", 7.0),
        organic_carbon_percent=soil.get("properties", {}).get("organic_carbon_percent", 0.5)
    )
    
    # 3. Extract weather / moisture data
    daily_rain = weather.get("daily", {}).get("precipitation_sum", [0])
    recent_rain = daily_rain[-1] if isinstance(daily_rain, list) and len(daily_rain) > 0 else (daily_rain if isinstance(daily_rain, float) else 0.0)
    
    daily_tmax = weather.get("daily", {}).get("temp_max", [25.0])
    recent_temp = daily_tmax[-1] if isinstance(daily_tmax, list) and len(daily_tmax) > 0 else (daily_tmax if isinstance(daily_tmax, float) else 25.0)
    
    sm_data = weather.get("daily", {}).get("soil_moisture_0_to_7cm_mean", 0.2)
    moisture_m3m3 = sm_data[-1] if isinstance(sm_data, list) and len(sm_data) > 0 else (sm_data if isinstance(sm_data, float) else 0.2)

    
    texture = soil["properties"].get("texture", "loam")
    fc_m3m3 = field_capacity_from_texture(texture)
    
    # Convert volumetric to mm over a 300mm root zone
    root_depth_mm = 300.0
    current_moisture_mm = moisture_m3m3 * root_depth_mm if moisture_m3m3 else 60.0
    field_capacity_mm = fc_m3m3 * root_depth_mm if fc_m3m3 else 75.0

    print("Data successfully fetched. Running the advanced Advisory Model...")
    
    # 4. Simulate a farmer's application context
    # Let's say they applied 50kg urea 3 days ago, and 10kg P.
    advisory = generate_fertilizer_advisory(
        crop=CORN_DATA, 
        soil=soil_card, 
        current_moisture_mm=current_moisture_mm,
        field_capacity_mm=field_capacity_mm,
        recent_rainfall_mm=recent_rain,
        recent_max_temp_c=recent_temp,
        applied_urea_kg=50.0, # Assumed input
        days_since_urea_app=3, # Assumed input
        urea_application_method="surface_broadcast", 
        applied_p_fertilizer_kg=10.0 # Assumed input
    )
    
    print("\n" + "="*50)
    print("        REAL-TIME FERTILIZATION ADVISORY")
    print("="*50)
    print(advisory)
    print("="*50)

if __name__ == "__main__":
    main()
