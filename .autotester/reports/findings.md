# Auto-Tester report — `jeevn`

**24 distinct issue(s)** across 7 runs (7 input cases, mode=`both`).

🔴 6 critical  🟠 9 high  🟡 8 medium  ⚪ 1 low

> Code-scan produced 4 hypotheses.

> Generated checks suite (6 invariants, 3 metamorphic).


## 🔴 CRITICAL

### Incorrect Date Range in Fabricated Weather Data
*check:* `llm.spot_check`  ·  *category:* correctness

**Observed:** The 'make_default_weather' function returned fabricated weather data for dates in 2026 (e.g., '2026-05-31'), which is significantly in the future and does not align with the input 'sowing_date' of '2023-11-10' or any reasonable current period for an agricultural report.

**Evidence:**
```json
{
  "step_name": "jeevn.infrastructure.pseudo_satellite.make_default_weather",
  "input_sowing_date": "2023-11-10",
  "output_weather_dates": [
    "2026-05-31",
    "2026-06-01",
    "2026-06-02",
    "2026-06-03",
    "2026-06-04",
    "2026-06-05",
    "2026-06-06"
  ]
}
```

**Reproduce with case(s):** case_76208838

### Fabricated Data Not Fully Declared
*check:* `llm.final_judge`  ·  *category:* fabrication

**Observed:** The `growth_yield.vegetation_vigor` and `growth_yield.vegetation_vigor_score` fields appear to be fabricated or derived from fabricated data, but are not listed in `data_quality.fabricated_fields`.

**Evidence:**
```json
{
  "growth_yield.vegetation_vigor": "Very Poor",
  "growth_yield.vegetation_vigor_score": 13.5,
  "data_quality.fabricated_fields": [
    "ndvi",
    "rsm",
    "soil.bulk_density",
    "soil.cec",
    "soil.clay_percent",
    "soil.infiltration_rate",
    "soil.organic_carbon_percent",
    "soil.ph",
    "soil.sand_percent",
    "soil.silt_percent",
    "soil.soil_moisture_current",
    "soil.texture",
    "soil.water_holding_capacity",
    "weather"
  ]
}
```

**Reproduce with case(s):** case_76208838

### Inconsistent Growth Stage Assessment
*check:* `llm.final_judge`  ·  *category:* internal_consistency

**Observed:** The `growth_yield.current_growth_stage` is 'tillering', but the `growth_yield.growth_stage_assessment` states 'Late by 879 days (accelerated development)'. This is a contradiction. A crop sown on 2023-11-10 cannot be 'late by 879 days' and simultaneously be in an 'accelerated development' state, especially when the report date is 2026-06-06.

**Evidence:**
```json
{
  "input_sowing_date": "2023-11-10",
  "report_date": "06/06/2026",
  "growth_yield.current_growth_stage": "tillering",
  "growth_yield.growth_stage_assessment": "Late by 879 days (accelerated development)"
}
```

**Reproduce with case(s):** case_76208838

### NDVI Analysis Not Using Input Data
*check:* `llm.final_judge`  ·  *category:* input_propagation

**Observed:** The `growth_trajectory` section reports `current_ndvi: 0`, `ndvi_range: 0.00 to 0.00`, and `mean_ndvi: 0.0`, despite valid `ndvi_timeseries` being provided in the input. This indicates the input NDVI data was not used for this section.

**Evidence:**
```json
{
  "input_ndvi_timeseries": [
    {
      "date": "2023-11-25",
      "mean_ndvi": 0.21
    },
    {
      "date": "2023-12-20",
      "mean_ndvi": 0.45
    },
    {
      "date": "2024-01-14",
      "mean_ndvi": 0.82
    },
    {
      "date": "2024-02-05",
      "mean_ndvi": 0.79
    }
  ],
  "growth_trajectory.current_ndvi": 0,
  "growth_trajectory.ndvi_range": "0.00 to 0.00",
  "growth_trajectory.mean_ndvi": 0.0
}
```

**Reproduce with case(s):** case_76208838

### Fabricated weather data not explicitly declared in output
*check:* `llm.spot_check`  ·  *category:* fabrication

**Observed:** The `jeevn.infrastructure.pseudo_satellite.make_default_weather` step returned fabricated data, indicated by `_fabricated: true`, but the output structure does not include a `_fabricated_fields` key to explicitly list which fields were fabricated, as required by the intent's 'Data Provenance and Fabrication Disclosure' rule.

**Evidence:**
```json
{
  "step_name": "jeevn.infrastructure.pseudo_satellite.make_default_weather",
  "result": {
    "location": {
      "latitude": 22.5726,
      "longitude": 88.3639,
      "timezone": "Asia/Kolkata"
    },
    "daily": {
      "dates": [
        "2026-05-31",
        "2026-06-01",
        "2026-06-02",
        "2026-06-03",
        "2026-06-04",
        "2026-06-05",
        "2026-06-06"
      ],
      "temp_max": [
        35,
        36,
        37,
        36,
        35,
        34,
        33
      ],
      "temp_min": [
        25,
        26,
        27,
        26,
        25,
        24,
        23
      ],
      "temp_mean": [
        30,
        31,
        32,
        31,
        30,
        29,
        28
      ],
      "rainfall": [
        0,
        0,
        0,
        0,
        0,
        5,
        0
      ],
      "solar_radiation": [
        25,
        26,
        27,
        26,
        25,
        22,
        24
      ],
      "wind_speed": [
        8,
        8,
        9,
        8,
        7,
        6,
        7
      ]
    },
    "_fabricated": true
  }
}
```

**Reproduce with case(s):** case_f315aff5

### Incorrect Sowing Date Propagation and Growth Stage Calculation
*check:* `llm.final_judge`  ·  *category:* correctness

**Observed:** The `sowing_date` (2024-06-20) is not correctly used to calculate 'days since sowing' for growth stage determination. The report states 'current_growth_stage': 'tillering' and 'growth_stage_assessment': 'Late by 656 days (accelerated development)'. This is a contradiction and indicates a miscalculation. From 2024-06-20 to 2026-06-06 (report_date), there are approximately 716 days, not 656. Furthermore, 'tillering' is an early growth stage, and being 'Late by 656 days' for tillering is nonsensical. The 'days_in_stage' in 'environmental_context.growth_stage' is also 716, which matches the total days since sowing, but this should not be the 'days_in_stage' for tillering.

**Evidence:**
```json
{
  "input_sowing_date": "2024-06-20",
  "report_date": "06/06/2026",
  "growth_yield.current_growth_stage": "tillering",
  "growth_yield.growth_stage_assessment": "Late by 656 days (accelerated development)",
  "environmental_context.growth_stage.days_in_stage": 716
}
```

**Reproduce with case(s):** case_f315aff5


## 🟠 HIGH

### Changing the sowing date should result in a different current growth stage. ×3
*check:* `sowing_date_impact`  ·  *category:* correctness

**Intent:** Changing the sowing date should result in a different current growth stage.

**Observed:** Changing the sowing date had no effect on the calculated current_growth_stage.

**Evidence:**
```json
{
  "base_sowing_date": "2023-11-10",
  "variant_sowing_date": "2024-02-15",
  "observed_stage": "tillering",
  "variant_case_id": "case_cae40ccb"
}
```

**Reproduce with case(s):** case_76208838, case_f315aff5, case_b2c6b015

### [code-review] Satellite visit date is hardcoded to the report generation date  _(confidence 50%)_
*check:* `code_scan.hardcoded_satellite_visit_date`  ·  *category:* code-suspicion

**Intent:** The `satellite_visit` field in the `aoi_info` dictionary is populated using `datetime.now().strftime("%d %b %Y")`. This is incorrect; the visit date should correspond to the acquisition date of the satellite imagery used (e.g., from `sar_data['scene_date']` or the date of the latest `ndvi_timeseries` entry), not the date the report was generated.

**Observed:** The report will always show the current date as the 'satellite visit date', regardless of when the actual satellite data was captured. This provides false information about data freshness and provenance.

**Evidence:**
```json
{
  "location": "jeevn.application.advisory_service:AgriculturalReportGenerator.generate_report:81",
  "probe_hint": "Run the report on two different days using the exact same input data, including a fixed `sar_data` dictionary with a `scene_date` from last month. The `satellite_visit` field in the output will change to the current date each time, instead of remaining static and matching the `scene_date`."
}
```

### [code-review] Inconsistent NDVI sources used for point-in-time vs. trajectory analysis  _(confidence 50%)_
*check:* `code_scan.inconsistent_ndvi_source`  ·  *category:* code-suspicion

**Intent:** When both `ndvi_timeseries` and `ndvi_raster_data` are provided, `_process_ndvi_data` first sets `data['ndvi']` from the timeseries, but then overwrites it with the value from the raster data. However, the `growth_trajectory` analysis in the main function is still performed on the original `ndvi_timeseries`. This can lead to a report where the current NDVI value (used for irrigation, yield, etc.) is inconsistent with the trend line.

**Observed:** The report's `growth_trajectory` might show a declining trend ending at NDVI=0.7, while the `growth_yield` projection and other current-state calculations are based on a current NDVI of 0.5 (from the raster), creating a confusing and contradictory narrative for the user.

**Evidence:**
```json
{
  "location": "jeevn.application.advisory_service:AgriculturalReportGenerator._process_ndvi_data:201",
  "probe_hint": "Call `generate_report` with an `ndvi_timeseries` where the last point is `{'ndvi': 0.7}` and an `ndvi_raster_data` dictionary where `{'ndvi_mean': 0.5}`. The resulting report will have a trajectory ending at 0.7 but other calculations will be based on 0.5."
}
```

### Soil properties in 'soil_management' must be consistent with 'environmental_context'.
*check:* `internal_consistency_soil`  ·  *category:* correctness

**Intent:** Soil properties in 'soil_management' must be consistent with 'environmental_context'.

**Observed:** Soil properties are inconsistent between soil_management and environmental_context.

**Evidence:**
```json
{
  "mismatches": [
    {
      "field": "ph",
      "soil_management": 8.2,
      "environmental_context": 8.18
    }
  ]
}
```

**Reproduce with case(s):** case_846400aa

### Inconsistent Harvest Status and Growth Stage
*check:* `llm.final_judge`  ·  *category:* internal_consistency

**Observed:** The report states `growth_yield.harvest_status` as 'ready' while `growth_yield.current_growth_stage` is 'tillering'. These two states are mutually exclusive for a crop like Wheat. A crop in the tillering stage is far from being ready for harvest.

**Evidence:**
```json
{
  "growth_yield.harvest_status": "ready",
  "growth_yield.current_growth_stage": "tillering"
}
```

**Reproduce with case(s):** case_76208838

### Inconsistent Growth Stage Duration
*check:* `llm.final_judge`  ·  *category:* internal_consistency

**Observed:** The `environmental_context.growth_stage.days_in_stage` is reported as 939 days. This is an extremely long duration for a single growth stage (tillering) and is inconsistent with the typical lifecycle of Wheat.

**Evidence:**
```json
{
  "environmental_context.growth_stage.stage": "tillering",
  "environmental_context.growth_stage.days_in_stage": 939
}
```

**Reproduce with case(s):** case_76208838

### Fabricated weather data dates are in the future
*check:* `llm.spot_check`  ·  *category:* correctness

**Observed:** The `jeevn.infrastructure.pseudo_satellite.make_default_weather` step returned fabricated weather data with dates starting from '2026-05-31'. The input `sowing_date` is '2024-06-20', implying the report is for the current or recent past season. Future weather data is not relevant for current agronomic calculations.

**Evidence:**
```json
{
  "step_name": "jeevn.infrastructure.pseudo_satellite.make_default_weather",
  "input_sowing_date": "2024-06-20",
  "fabricated_weather_dates": [
    "2026-05-31",
    "2026-06-01",
    "2026-06-02",
    "2026-06-03",
    "2026-06-04",
    "2026-06-05",
    "2026-06-06"
  ]
}
```

**Reproduce with case(s):** case_f315aff5

### Inconsistent Salinity Status Reporting
*check:* `llm.final_judge`  ·  *category:* internal_consistency

**Observed:** The `soil_management.salinity` is reported as 'moderate', but `environmental_context.soil.properties.salinity_label` is 'non-saline'. These two values contradict each other.

**Evidence:**
```json
{
  "soil_management.salinity": "moderate",
  "environmental_context.soil.properties.salinity_label": "non-saline"
}
```

**Reproduce with case(s):** case_f315aff5

### NDVI Data Not Used for Growth Trajectory Analysis
*check:* `llm.final_judge`  ·  *category:* correctness

**Observed:** The `ndvi_timeseries` input data is provided, but the `growth_trajectory` section reports 'current_ndvi': 0, 'ndvi_range': '0.00 to 0.00', and 'mean_ndvi': 0.0, with 'data_points': 2. This indicates that the provided NDVI data (0.18 and 0.33) was not used for the analysis, despite the intent to generate the `growth_yield.monitoring` section using this data.

**Evidence:**
```json
{
  "input_ndvi_timeseries": [
    {
      "date": "2024-07-05",
      "mean_ndvi": 0.18
    },
    {
      "date": "2024-07-20",
      "mean_ndvi": 0.33
    }
  ],
  "growth_trajectory.current_ndvi": 0,
  "growth_trajectory.ndvi_range": "0.00 to 0.00",
  "growth_trajectory.mean_ndvi": 0.0,
  "growth_trajectory.data_points": 2
}
```

**Reproduce with case(s):** case_f315aff5


## 🟡 MEDIUM

### Total yield must equal yield per acre multiplied by the area. ×6
*check:* `yield_calculation`  ·  *category:* accuracy

**Intent:** Total yield must equal yield per acre multiplied by the area.

**Observed:** Total yield calculation is incorrect.

**Evidence:**
```json
{
  "errors": [
    {
      "type": "actual_yield",
      "yield_per_acre": 3102.0,
      "area": 25.0,
      "expected_total": 77550.0,
      "observed_total": 77562.5
    }
  ]
}
```

**Reproduce with case(s):** case_76208838, case_f315aff5, case_b2c6b015, case_097243b0, case_3743adcf

### [code-review] RVI derived from NDVI is not flagged as a proxy  _(confidence 50%)_
*check:* `code_scan.rvi_proxy_not_flagged`  ·  *category:* code-suspicion

**Intent:** When a real NDVI value is available but no real SAR data is, the code calculates a proxy RVI (`ts_ndvi * 1.08`) and then removes 'rvi' from the `fabricated` set. This is misleading. While derived from real data, this RVI is an estimate, not a direct radar measurement. According to the stated intent, such non-direct values should be disclosed.

**Observed:** The final report will show an RVI value, but the `data_quality.fabricated_fields` list will not contain 'rvi'. This misleads the user into thinking they have a real radar measurement when they only have an optical-derived proxy, potentially giving them false confidence in the value.

**Evidence:**
```json
{
  "location": "jeevn.application.advisory_service:AgriculturalReportGenerator._process_ndvi_data:192",
  "probe_hint": "Call `generate_report` with a valid `ndvi_timeseries` (containing a real NDVI value) but with `sar_data=None`. The resulting report's `data_quality.fabricated_fields` will be missing 'rvi', and the `details` will not explain its proxy origin."
}
```

### [code-review] Convenience wrapper function drops the `ndvi_raster_data` input  _(confidence 50%)_
*check:* `code_scan.dropped_raster_data_input`  ·  *category:* code-suspicion

**Intent:** The wrapper function `generate_agricultural_report_from_aoi` does not have `ndvi_raster_data` in its signature and therefore does not pass it to the underlying `AgriculturalReportGenerator.generate_report` method. This makes it impossible for any code using this convenience entrypoint to provide raster data.

**Observed:** The `field_maps` component of the report will always be empty/null when using the `generate_agricultural_report_from_aoi` function, even if raster data is available and intended to be used. The point-in-time NDVI value will also never be sourced from a raster when using this entrypoint.

**Evidence:**
```json
{
  "location": "jeevn.application.advisory_service:generate_agricultural_report_from_aoi",
  "probe_hint": "Attempt to generate a report with field maps using the `generate_agricultural_report_from_aoi` function. It's impossible because the function signature doesn't accept `ndvi_raster_data`. If the signature were modified to accept it, the data would still be dropped as it's not passed to the internal call."
}
```

### Inconsistent Salinity Assessment
*check:* `llm.final_judge`  ·  *category:* internal_consistency

**Observed:** The `soil_management.salinity` is reported as 'high', but the `environmental_context.soil.properties.salinity_label` is 'slightly saline'. These two assessments contradict each other.

**Evidence:**
```json
{
  "soil_management.salinity": "high",
  "environmental_context.soil.properties.salinity_label": "slightly saline"
}
```

**Reproduce with case(s):** case_76208838

### Inconsistent Soil Organic Carbon Status  _(confidence 80%)_
*check:* `llm.final_judge`  ·  *category:* internal_consistency

**Observed:** The `soil_management.organic_carbon_status` states 'critically low (current: 0.15%, min required: 0.8%)', but the `fertilizer_management.nutrient_requirements` does not list Carbon as a nutrient with a gap, nor does it explicitly link the low organic carbon to nutrient deficiencies in its 'limiting_factors'. While organic carbon is not a direct nutrient, its critical level should influence nutrient availability and be reflected more directly in fertilizer recommendations or limiting factors.

**Evidence:**
```json
{
  "soil_management.organic_carbon_percent": 0.15,
  "soil_management.organic_carbon_status": "critically low (current: 0.15%, min required: 0.8%)",
  "fertilizer_management.nutrient_requirements": {
    "N": {
      "current_kg_per_acre": 13.65,
      "target_kg_per_acre": "36.4-47.3",
      "gap_kg_per_acre": 33.7,
      "status": "critical"
    },
    "P": {
      "current_kg_per_acre": 11.0,
      "target_kg_per_acre": "18.2-23.7",
      "gap_kg_per_acre": 12.67,
      "status": "critical"
    },
    "K": {
      "current_kg_per_acre": 82.0,
      "target_kg_per_acre": "18.2-23.7",
      "gap_kg_per_acre": 0,
      "status": "adequate"
    },
    "S": {
      "current_kg_per_acre": 7.0,
      "target_kg_per_acre": "9.7-14.7",
      "gap_kg_per_acre": 7.74,
      "status": "critical"
    },
    "Zn": {
      "current_kg_per_acre": 0.8,
      "target_kg_per_acre": "4.4-9.4",
      "gap_kg_per_acre": 8.57,
      "status": "critical"
    }
  },
  "growth_yield.limiting_factors": [
    {
      "factor": "Nutrient deficiency",
      "impact": "15.0% yield reduction"
    }
  ]
}
```

**Reproduce with case(s):** case_76208838

### Inconsistent Fertilizer Recommendation for DAP  _(confidence 90%)_
*check:* `llm.final_judge`  ·  *category:* internal_consistency

**Observed:** The `fertilizer_management.nutrient_requirements.P.gap_kg_per_acre` is 12.67 kg/acre. DAP (Diammonium Phosphate) typically contains 46% P2O5, which is about 20% P. To supply 12.67 kg of P, approximately 63.35 kg of DAP would be needed (12.67 / 0.20). The recommended quantity of DAP is 63.35 kg/acre, which matches the P gap. However, DAP also contains 18% Nitrogen. This means 63.35 kg of DAP would supply approximately 11.4 kg of N (63.35 * 0.18). This N contribution from DAP is not accounted for in the Urea recommendations, which are based on 50% of the N requirement each, potentially leading to over-application of N.

**Evidence:**
```json
{
  "fertilizer_management.nutrient_requirements.P.gap_kg_per_acre": 12.67,
  "fertilizer_management.nutrient_requirements.N.gap_kg_per_acre": 33.7,
  "fertilizer_management.fertilizer_schedule.recommended_products": [
    {
      "product": "Urea (46% N) - Base application",
      "quantity_kg_acre": 36.63,
      "notes": "50% of N requirement"
    },
    {
      "product": "Urea (46% N) - Top dressing",
      "quantity_kg_acre": 36.63,
      "notes": "50% of N requirement; critical for grain fill"
    },
    {
      "product": "DAP - Diammonium Phosphate",
      "quantity_kg_acre": 63.35,
      "notes": "Ensures available P at seedling stage"
    }
  ]
}
```

**Reproduce with case(s):** case_76208838

### Fabrication Disclosure Inconsistency for Weather Data  _(confidence 90%)_
*check:* `llm.final_judge`  ·  *category:* fabrication

**Observed:** The `data_quality.fabricated_fields` lists 'weather' as fabricated, with the detail 'Weather data (Open-Meteo unreachable; using semi-arid May defaults)'. However, the `environmental_context.weather.daily` section contains specific daily weather data (temperatures, rainfall, solar radiation, wind speed) for dates from 2026-05-31 to 2026-06-06, which contradicts the idea of using 'semi-arid May defaults'. If it's fabricated, it should either be explicitly stated as such in the data itself or the data should reflect the 'defaults' more clearly.

**Evidence:**
```json
{
  "data_quality.fabricated_fields": [
    "weather"
  ],
  "data_quality.details.weather": "Weather data (Open-Meteo unreachable; using semi-arid May defaults)",
  "environmental_context.weather.daily": {
    "dates": [
      "2026-05-31",
      "2026-06-01",
      "2026-06-02",
      "2026-06-03",
      "2026-06-04",
      "2026-06-05",
      "2026-06-06"
    ],
    "temp_max": [
      35,
      36,
      37,
      36,
      35,
      34,
      33
    ],
    "temp_min": [
      25,
      26,
      27,
      26,
      25,
      24,
      23
    ],
    "temp_mean": [
      30,
      31,
      32,
      31,
      30,
      29,
      28
    ],
    "rainfall": [
      0,
      0,
      0,
      0,
      0,
      5,
      0
    ],
    "solar_radiation": [
      25,
      26,
      27,
      26,
      25,
      22,
      24
    ],
    "wind_speed": [
      8,
      8,
      9,
      8,
      7,
      6,
      7
    ]
  }
}
```

**Reproduce with case(s):** case_f315aff5

### Inconsistent KC Value for Growth Stage  _(confidence 80%)_
*check:* `llm.final_judge`  ·  *category:* internal_consistency

**Observed:** The `irrigation_schedule.kc` is 0.51, while `environmental_context.growth_stage.kc` is 0.5. While these are close, they should ideally be consistent if they refer to the same crop coefficient for the current growth stage.

**Evidence:**
```json
{
  "irrigation_schedule.kc": 0.51,
  "environmental_context.growth_stage.kc": 0.5
}
```

**Reproduce with case(s):** case_f315aff5


## ⚪ LOW

### Inconsistent Location Name in AOI Info  _(confidence 70%)_
*check:* `llm.final_judge`  ·  *category:* correctness

**Observed:** The input `location_name` is 'Kolkata, West Bengal, India', but `aoi_info.location` is 'Baranagar'. While Baranagar is a locality within Kolkata, the report should ideally reflect the input location name or provide a clear reason for the change.

**Evidence:**
```json
{
  "input_location_name": "Kolkata, West Bengal, India",
  "aoi_info.location": "Baranagar"
}
```

**Reproduce with case(s):** case_f315aff5
