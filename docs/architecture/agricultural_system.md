# Agricultural Advisory System - Implementation Guide

## Overview

The agricultural advisory system calculates real-world agricultural parameters to generate comprehensive farm advisory reports, similar to the Farmonaut Personalized Farm Advisory Report.

## Architecture

### Core Modules

#### 1. **data_fetcher.py**
Fetches real agricultural data from multiple sources:

- **WeatherDataFetcher**: Fetches weather from Open-Meteo API (free, no API key)
  - Daily temperature (min/max/mean)
  - Rainfall and precipitation
  - Solar radiation
  - Wind speed

- **SoilDataFetcher**: Soil properties based on geographic location
  - pH, electrical conductivity (salinity)
  - Organic carbon content
  - Texture (sandy loam, loam, etc.)
  - Water holding capacity
  - Soil moisture from radar data

- **CropPhenologyDatabase**: Crop-specific data
  - Growth stages with expected NDVI ranges
  - Crop coefficients (Kc) for each stage
  - Nutrient requirements
  - Yield potential by crop

- **GeographicDataFetcher**: Location information
  - Reverse geocoding using OpenStreetMap
  - Timezone, state, country information

#### 2. **irrigation.py**
Calculates irrigation water requirements using FAO-56 methodology:

- **ET0 Calculation (Hargreaves-Samani method)**:
  ```
  ET0 = 0.0023 × Ra × √(Tmax - Tmin) × (Tmean + 17.8)
  ```
  Where:
  - Ra = Extraterrestrial radiation
  - T = Temperature values

- **Crop Evapotranspiration (ETc)**:
  ```
  ETc = ET0 × Kc
  ```
  Where Kc is adjusted based on growth stage and vegetation vigor (RVI)

- **Irrigation Scheduling**: Generates daily irrigation recommendations
  - Considers rainfall, soil moisture, and crop water needs
  - Recommends irrigation timing and methods
  - Accounts for different irrigation systems (drip, basin, sprinkler)

#### 3. **soil_management.py**
Analyzes soil conditions and provides recommendations:

- Soil pH assessment (acidic, neutral, alkaline)
- Salinity classification (low, moderate, high)
- Organic carbon status evaluation
  - Compares current levels to crop-specific minimums
  - For apple: 1.0-1.5% minimum, 2.0-3.5% optimal
- Water-holding capacity assessment
- Recommendations for improvement:
  - Organic amendments (compost, manure)
  - Cover cropping
  - Mulching

#### 4. **fertilizer.py**
Calculates nutrient requirements and fertilizer recommendations:

- **Nutrient Requirement Calculation**:
  - Current soil nutrient levels
  - Crop nutrient demands by growth stage
  - Adjustment based on yield targets and vegetation vigor (RVI)

- **Fertilizer Product Recommendations**:
  - Specific products with application rates
  - Conversion of nutrient requirements to fertilizer quantities
  - For apple orchards:
    - Nitrogen: Urea (46% N) via fertigation
    - Phosphorus: DAP and Bone Meal
    - Potassium: SOP and Wood Ash
    - Micronutrients: Zinc Sulphate, Bentonite Sulphur

- **Application Schedule**:
  - Timing recommendations
  - Application method (drip fertigation, soil application, etc.)
  - Frequency of applications

#### 5. **pest_disease_weed.py**
Risk assessment for pests, diseases, and weeds:

- **Risk Scoring (0-100)**:
  - Temperature suitability for each pest/disease
  - Humidity impact (growth-stage dependent)
  - Vegetation density impact (RVI factor)
  - Soil moisture and rainfall influence on weed risk

- **Crop-Specific Database**:
  - For apple: Spider Mites, Powdery Mildew, Codling Moth, Alternaria Leaf Spot
  - Common weeds: Bermuda Grass, Chenopodium album
  - Organic and chemical control solutions

- **Risk Levels**: High (≥70%), Moderate (40-69%), Low (<40%)

- **Management Recommendations**: Integrated pest management strategies

#### 6. **yield_growth.py**
Projects yield and monitors growth:

- **Yield Projection**:
  - Base yield potential from crop database
  - Reduction factors:
    - Nutrient deficiency (RVI-based)
    - Pest/disease pressure
    - Water stress
    - Stage-specific factors

- **Growth Stage Assessment**:
  - Determines if crop is on schedule based on days since sowing
  - Expected growth stage for current date

- **Vegetation Vigor Rating**:
  - Excellent, Good, Moderate, Poor, Very Poor
  - Based on RVI and NDVI values

- **Harvest Status Determination**:
  - Ready for harvest
  - Incomplete
  - Overripe

#### 7. **report_generator.py**
Orchestrates all calculations and generates comprehensive report:

- Fetches all required data
- Performs all calculations in sequence
- Aggregates into structured JSON report
- Generates summary with key findings and recommendations

## Key Calculations Explained

### ET0 Calculation

The Reference Evapotranspiration (ET0) is the foundation for irrigation scheduling:

```
Components:
1. Extraterrestrial Radiation (Ra): Depends on latitude and day of year
2. Temperature Range: (Tmax - Tmin) indicates evaporative demand
3. Mean Temperature: Influences evaporative potential

Formula: ET0 = 0.0023 × Ra × √(Tmax - Tmin) × (Tmean + 17.8)

Result: Daily water requirement in mm for reference surface
```

### Crop Coefficient (Kc) Adjustment

Standard Kc values are adjusted based on actual vegetation vigor:

```
Base Kc (from FAO-56): Stage-dependent (e.g., 0.95 for apple during bloom)
RVI Factor: 0.8 to 1.2 based on vegetation density
Adjusted Kc = Base Kc × RVI Factor

Higher RVI → More vigorous growth → Higher Kc → More water needed
```

### Soil Water Deficit

Determines when to irrigate:

```
Readily Available Water = (Field Capacity - Wilting Point) × Depletion Fraction
Threshold = Wilting Point + Readily Available Water
If Current Moisture < Threshold: Irrigation Needed
```

### Nutrient Gap Calculation

```
Gap = Target Nutrient Level × RVI Factor - Current Level
Quantity of Fertilizer = Gap / Nutrient Content %

Example: Need 10 kg N/acre gap
Urea (46% N) needed = 10 / 0.46 = 21.7 kg/acre
```

### Pest/Disease Risk Scoring

```
Score = (30% × Temperature Suitability) +
        (25% × Humidity Impact) +
        (25% × Vegetation Density Impact) +
        (20% × Growth Stage Susceptibility)

Risk Level:
- High: ≥ 70%
- Moderate: 40-69%
- Low: < 40%
```

## API Endpoints

### Generate Agricultural Advisory

```
POST /advisory/agricultural
Content-Type: application/json

{
  "name": "AOI Name",
  "latitude": 29.9,
  "longitude": 73.9,
  "area_acres": 0.421,
  "crop_type": "apple",
  "sowing_date": "2026-02-01",
  "location_name": "Ganganagar, Rajasthan"
}

Response: Comprehensive agricultural advisory report
```

### Check System Health

```
POST /advisory/health-check

Response:
{
  "status": "ok",
  "agricultural_module": "available",
  "timestamp": "2024-12-20T10:30:00"
}
```

## Data Sources

### Real Data Sources
- **Weather**: Open-Meteo API (historical and forecast)
- **Location**: OpenStreetMap Nominatim (reverse geocoding)
- **Soil**: Regional databases (CSSRI for India)

### Default Data
- Crop phenology database (built-in)
- Pest/disease reference database (built-in)
- FAO crop coefficients (built-in)

## Report Structure

```
{
  "report_date": "DD/MM/YYYY",
  "aoi_info": { location, crop, area, coordinates },
  "components": {
    "field_maps": { crop_health_map, irrigation_health_map },
    "irrigation_schedule": { daily schedule, total water, timing },
    "soil_management": { pH, salinity, organic carbon, recommendations },
    "growth_yield": { yield projection, growth stage, limiting factors },
    "pest_disease_weed": { risk assessment, high-risk threats },
    "fertilizer_management": { nutrient requirements, product recommendations }
  },
  "summary": { key_findings, urgent_actions, recommendations },
  "environmental_context": { weather, soil, growth_stage }
}
```

## Integration with Satellite Data

The system integrates satellite indices:

- **NDVI (Normalized Difference Vegetation Index)**:
  - Calculated from Sentinel-2 B4 (Red) and B8 (NIR) bands
  - Ranges from -1 to +1 (typically 0 to 0.8 for vegetation)

- **RVI (Radar Vegetation Index)**:
  - From Sentinel-1 SAR data
  - More robust in cloudy/rainy conditions
  - Used to adjust crop coefficients and assess vigor

- **RSM (Radar Soil Moisture)**:
  - From Sentinel-1 backscatter
  - Used to trigger irrigation and assess weed risk

## Example Workflow

1. **User provides**: Location, crop type, field area, sowing date
2. **System fetches**:
   - Weather data (last 30 days + forecast)
   - Soil data (from location)
   - Satellite imagery (NDVI, RVI, RSM)
3. **System calculates**:
   - ET0 based on weather
   - Water requirements × area
   - Soil status and recommendations
   - Nutrient gaps
   - Pest/disease/weed risks
   - Yield projections
4. **System generates**: Comprehensive JSON report
5. **UI displays**: Formatted advisory with charts, maps, and recommendations

## Testing

Run the test script to validate calculations:

```bash
cd /path/to/ashi
python test_agricultural_report.py
```

This generates a sample report for Ganganagar Apple farm (same as PDF example).

## Future Enhancements

1. **Real-time Monitoring**:
   - WebSocket updates as new satellite data arrives
   - Continuous monitoring of weather and soil moisture

2. **Machine Learning**:
   - Predict pest/disease outbreaks
   - Optimize irrigation schedules
   - Yield prediction models

3. **Precision Agriculture**:
   - Variable rate applications based on field variability
   - Prescription maps for zone-based management

4. **Integration**:
   - Export to smart irrigation controllers
   - Connect to agri-tech platforms
   - Mobile app for farmer notifications

## References

- FAO-56: Crop Evapotranspiration and Irrigation Scheduling
- Hargreaves-Samani: ET0 Estimation Method
- ICAR Guidelines: Indian crop management practices
- Sentinel Data: ESA satellite imagery
