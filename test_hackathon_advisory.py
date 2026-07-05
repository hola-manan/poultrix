from src.jeevn.infrastructure.data_sources.aoi import fetch_aoi_data
from src.jeevn.domain.soil.management import SoilManagementCalculator
from src.jeevn.application.hackathon_adapter import generate_hackathon_advisory
from src.jeevn.infrastructure import pseudo_satellite

def main():
    print("--------------------------------------------------")
    print("1. Fetching REAL AOI data from APIs (Weather, Soil, Phenology)...")
    # Coordinates for a farm somewhere in India (fallback default)
    # This fires Open-Meteo, SoilGrids, etc. using the default valid AOI
    lat = pseudo_satellite.DEFAULT_LATITUDE
    lon = pseudo_satellite.DEFAULT_LONGITUDE
    aoi_data = fetch_aoi_data(lat=lat, lon=lon, crop_name="maize")
    print("✅ Data fetched.")

    print("\n2. Computing real soil capacity via Saxton-Rawls PTF...")
    soil_analysis = SoilManagementCalculator.analyze_soil(aoi_data)
    print("✅ Soil analysis complete.")
    
    print("\n3. Feeding data to hackathon/irrigation_advisory.py...")
    print("--------------------------------------------------\n")

    # Run the user's logic
    advisory_result = generate_hackathon_advisory(aoi_data, soil_analysis, farmer_interval=4)
    
    print(advisory_result)

if __name__ == "__main__":
    main()
