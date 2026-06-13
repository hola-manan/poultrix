# `src/jeevn/domain/` — Pure agronomic calculations

The science layer. **Zero I/O** — no HTTP, no file reads, no DB, no environment variables. Every function takes plain dicts/floats in and returns plain dicts/floats out. This is what makes the math testable and trivially substitutable.

The orchestrator [../application/advisory_service.py](../application/advisory_service.py) feeds these calculators with data fetched by [../infrastructure/data_sources/](../infrastructure/data_sources/) and merges the outputs into the final advisory report.

## Subpackages

```
domain/
├── crop/                  # Crop phenology lookups
├── irrigation/            # FAO-56 ET0 + scheduling
├── soil/                  # Soil interpretation + recommendations
├── fertilizer/            # Nutrient gap + product schedule
├── pest_disease_weed/     # Risk scoring + IPM recommendations
├── growth_yield/          # Yield projection + NDVI trend monitoring
└── crop_health/           # (currently empty — reserved)
```

Each subpackage's `__init__.py` re-exports the public class for convenient `from jeevn.domain.X import Y` imports.

---

## `crop/` — phenology database

### [`crop/phenology.py`](crop/phenology.py)
`CropPhenologyDatabase` — class-attribute lookup table keyed by crop name.

- **`CROP_DATA`** — has `"apple"`, `"wheat"`, and `"grape"` (the pilot crop; anything else falls back to wheat). The grape calendar is anchored to forward/fruit pruning, not sowing, so `days_since_sowing` is days-since-pruning for grape. For each crop:
  - `t_base` (°C) — base temperature for GDD accumulation.
  - `growth_stages` — ordered dict of `{stage_name: {days, gdd, kc, ndvi_range}}`.
  - `nutrient_requirements_kg_per_acre` — per-nutrient `{low, optimal, high}` targets.
  - `yield_potential_kg_per_acre`.
  - `maturity_days`, `harvest_window_days`.
- **`get_crop_data(crop_name)`** — returns the dict for `crop_name.lower()`, defaults to wheat.
- **`get_current_growth_stage(crop_name, days_since_sowing, accumulated_gdd=0)`** — walks the stages cumulatively; uses GDD when available, days otherwise. Returns `{stage, kc, ndvi_range, days_in_stage[, gdd_in_stage]}`.

---

## `irrigation/` — water requirement + scheduling

### [`irrigation/et0.py`](irrigation/et0.py)
`IrrigationCalculator` — the FAO-56 / Hargreaves-Samani math.

- **`calculate_et0_hargreaves_samani(temp_mean, temp_max, temp_min, solar_radiation, lat, day_of_year, wind_speed)`** → ET0 in mm/day.
  - Always computes `Ra` from `_calculate_ra(lat, day_of_year)` (MJ/m²/day) and converts to mm/day equivalent via `×0.408`. `solar_radiation`/`wind_speed` are accepted for signature compatibility but unused — Hargreaves-Samani is a temperature + extraterrestrial-radiation method, not a measured-radiation one.
  - `ET0 = 0.0023 × Ra_mm × √(Tmax − Tmin) × (Tmean + 17.8)`. Realistic hot semi-arid output ~5-7 mm/day. *(Earlier `Ra = solar_radiation / 0.408` inverted the conversion and inflated ET0 ~6×.)*
- **`_calculate_ra(lat, day_of_year)`** — extraterrestrial radiation in **MJ/m²/day** (FAO-56 eq. 21); standard formula with seasonal correction `b = 2π(day-1)/365`. Convert with ×0.408 before use in Hargreaves.
- **`calculate_kc(crop_name, growth_stage, rvi=0.5)`** — base Kc from FAO-56 lookup × `(0.8 + rvi × 0.4)` RVI adjustment. Crops covered: apple, wheat, default.
- **`calculate_etc(et0, kc)`** = `et0 × kc`.
- **`calculate_soil_water_deficit(current_soil_moisture, field_capacity=0.25, wilting_point=0.12, depletion_fraction=0.5)`** — returns deficit (mm per 300 mm depth) once moisture drops below the readily-available threshold.

### [`irrigation/scheduler.py`](irrigation/scheduler.py)
`IrrigationScheduler.generate_schedule(aoi_data, ndvi_data, area_acres, forecast_days=7)`.

- **Rain-aware + forward-looking.** Reads `aoi_data["forecast"]["daily"]` (the 7-day Open-Meteo *forecast* fetched by the AOI composer — the historical archive can't gate a forward schedule). Per forecast day: compute that day's ET0 (from forecast temps) → ETc (× Kc, Kc from RVI-adjusted FAO-56) → `net = max(0, ETc − 0.8 × forecast_rain_mm)`. The 0.8 is an effective-rainfall fraction (USDA-SCS approximation).
- Alternate-day drip: irrigate on even days only when that day's `net > 0.05 mm` (rain may have already covered ETc). Each row shows the **actual forecast** rainfall (mm) + rain probability (%) — not hardcoded zeros.
- Falls back to default temps / zero rain (degraded, never crashes) when the forecast is absent.
- All quantities are in **mm**; there is no metre conversion. *(An earlier version divided rain by 1000 — silently ignoring it — and multiplied irrigation by 1000, producing drip of thousands of mm/day.)*
- **Returns** `{et0_mm_per_day (avg), kc, etc_mm_per_day (avg), forecast_rainfall_mm (7-day sum), total_water_mm, irrigation_days, best_time: "05:00-08:00", daily_schedule: [{date, drip_mm, basin_mm, sprinkler_mm, rainfall, rain_percent, evapotransp}], irrigation_method_notes}`.

---

## `soil/` — soil interpretation

### [`soil/management.py`](soil/management.py)
`SoilManagementCalculator.analyze_soil(aoi_data)`.

- Reads `aoi_data["soil"]["properties"]` (real values from SoilGrids + bundled salinity raster + Open-Meteo soil moisture, with fabricated fallbacks).
- **Classifications:**
  - Salinity (EC) → `negligible / low / moderate / high` using USDA thresholds (`<0.25 / 0.25–0.75 / 0.75–2.25 / ≥2.25 dS/m`).
  - CEC (cmol(+)/kg) → `low (sandy) / moderate / high (clay)` (USDA-style: `<10 / 10–25 / >25`).
  - Organic carbon → crop-specific minimum + optimal thresholds (apple: 1.0% min / 2.5% opt; others: 0.8 / 2.0). Status string includes the current value.
- **`_generate_findings`** emits human-readable narrative for pH range, salinity, SOC, texture composition (only when sand/silt/clay are real), CEC (only when real), and water-holding capacity.
- **`_get_recommendations`** branches on SOC / pH / salinity status to suggest organic amendments, lime, or gypsum / leaching practices.
- **Returns** `{ph, salinity, organic_carbon_percent, organic_carbon_status, texture, sand/silt/clay_percent, cec, cec_status, water_holding_capacity_mm, infiltration_rate_mm_h, soil_moisture_current, detailed_findings, recommendations: [...]}`.

---

## `fertilizer/` — nutrient gap + product schedule

### [`fertilizer/requirements.py`](fertilizer/requirements.py)
`NutrientRequirementCalculator.calculate_nutrient_requirements(aoi_data, area_acres, rvi, yield_potential_kg_acre=None)`.

- Hard-coded **current soil levels** dict (`N: 13.65, P: 11.0, K: 82.0, S: 7.0, Zn: 0.8`) — placeholder until a real soil-test source is integrated.
- Pulls target levels from `aoi_data["crop"]["nutrient_requirements_kg_per_acre"][nutrient]["optimal"]`.
- `adjusted_target = target_optimal × (0.8 + rvi × 0.4)`.
- `gap = max(0, adjusted_target - current)`.
- Status: `critical` if `current < target × 0.5`, `moderate` if `< target × 0.8`, else `adequate`.
- **Returns** `{N/P/K/S/Zn: {current_kg_per_acre, target_kg_per_acre, gap_kg_per_acre, status}}`.

### [`fertilizer/schedule.py`](fertilizer/schedule.py)
`FertilizerScheduler.generate_fertilizer_schedule(aoi_data, nutrient_requirements, area_acres, application_frequency_days=2)`.

- **`FERTILIZER_GRADES`** class-attribute: nutrient % per product (Urea 46% N, DAP 18% N + 46% P₂O₅, SOP 50% K + 18% S, MOP 60% K, Zinc Sulphate 21% Zn, Bentonite Sulphur 90% S, Vermicompost / Bone Meal / Wood Ash / Enriched FYM with their respective contents).
- Branches by crop:
  - **apple** (`_get_apple_recommendations`) — N→Urea (fertigation), P→split DAP + Bone Meal, K→split SOP + Wood Ash, S→Bentonite Sulphur, Zn→Zinc Sulphate. Always appends Enriched FYM + Vermicompost as soil-applied bulk organics.
  - **wheat** (`_get_wheat_recommendations`) — N→Urea split into base+top-dress, P→DAP at sowing, K→MOP if deficient.
  - **default** — generic by-nutrient placeholder.
- Adds cautions: high-EC soil → reduce concentration; flowering/fruit-set stage → avoid foliar at peak heat.
- **Returns** `{frequency_days, total_nutrient_requirement_kg_acre, recommended_products: [{product, quantity_kg_acre, application_method, timing, notes}], application_details, cautions}`.

---

## `pest_disease_weed/` — environmental risk scoring

### [`pest_disease_weed/assessment.py`](pest_disease_weed/assessment.py)
`PestDiseaseWeedAssessor.assess_pest_disease_risk(aoi_data, ndvi_data)`.

- **`PEST_DATABASE`** keyed by crop. Apple has Spider Mites, Powdery Mildew, Codling Moth, Alternaria Leaf Spot + Bermuda Grass / Chenopodium album. Wheat has Armyworm + Phalaris minor. **Grape** (pilot crop) has Powdery Mildew + Downy Mildew (both `model`-driven — see below) + Grape Mealybug + Bermuda Grass. Heuristic entries hold: `temperature_range`, `humidity_impact`, `stage_susceptibility`, `organic_solution`, `chemical_solution`. Model-driven entries carry a `model` key instead of the scoring fields.
- **Real humidity:** uses the measured `weather.daily.relative_humidity_mean` (Open-Meteo hourly RH, 24-h mean) when present; only falls back to the coarse proxy `min(100, 40 + rainfall×2 + (30 − temp_mean)×2)` on fabricated weather, flagging `environmental_conditions.humidity_estimated`.
- **Model-driven grape diseases** (`_assess_model_disease`, dispatched on the `model` key) call [`crop_health/disease_models.py`](crop_health/disease_models.py): `gubler_powdery_mildew_index` (UC Davis Gubler-Thomas, hourly temperature) and `downy_mildew_wet_period_risk` (hedged RH-as-leaf-wetness wet-period flag). Hourly series come from `_select_hourly` (forecast preferred, archive fallback); model diseases are **omitted** (not fabricated) when no hourly feed is available.
- **`_calculate_pest_disease_risk`** (generic heuristic for non-model pests) — weighted score, **RVI dropped** (was an unjustified 25%): 40% temperature suitability + 35% humidity impact + 25% growth-stage susceptibility.
- **`_calculate_weed_risk`** — moisture trigger (40%), recent rainfall (≤20), low-vigor penalty (40 × (1 − rvi_impact)).
- Risk levels: pest `high≥70`, `moderate≥40`; weeds `high≥60`, `moderate≥35`.
- **Returns** `{environmental_conditions: {…}, pests_diseases: [...], weeds: [...], summary: {high/moderate/low_risk_count}}` — both threat lists are sorted by descending risk %.
- **`get_management_recommendations`** (separate static method, not called by default) produces a flat IPM action list.

---

## `crop_health/` — weather-driven disease models

### [`crop_health/disease_models.py`](crop_health/disease_models.py)
Pure functions (no I/O) for grape disease risk, consumed by `pest_disease_weed/assessment.py`.

- **`gubler_powdery_mildew_index(hourly_times, hourly_temps_c, …)`** — UC Davis Gubler-Thomas powdery-mildew index from hourly temperature only (powdery mildew is temperature-driven, so a regional grid suffices). ≥6 continuous hours in 21–30 °C qualifies a day; 3 consecutive qualifying days initiate at 60; ±20/−10 thereafter; −10 heat penalty ≥35 °C; 0–100, mapped to spray intervals. A *confident* alert.
- **`downy_mildew_wet_period_risk(times, temps, rh, precip, …)`** — *hedged* downy-mildew flag. Downy mildew is leaf-wetness-driven and leaf wetness is microclimate (no Open-Meteo variable), so this is an explicit regional proxy: longest wet period (RH≥90% or rain) in the 13–30 °C band + the "3-10" primary-infection rule. Carries `confidence: "regional-proxy"` and scout/confirm language — never a direct spray instruction.

See PROCESSES.md H.2/H.3 and the go/no-go in the plan history for why these two diseases are treated so differently.

---

## `growth_yield/` — yield projection + NDVI trend

### [`growth_yield/projection.py`](growth_yield/projection.py)
`YieldGrowthCalculator.calculate_yield_projection(aoi_data, ndvi_data, area_acres)`.

- Vegetation vigor rating from RVI (`≥0.75 Excellent → <0.35 Very Poor`), with NDVI-vs-expected-range penalty.
- Growth-stage timing assessment (compares `days_since_sowing` against per-crop stage windows; "On schedule" / "Early by N days" / "Late by N days").
- `_calculate_reduction_factors` returns a dict like `{"Nutrient deficiency": 15.0, "Water stress": 20.0, ...}`:
  - RVI < 0.60 → 15% nutrient hit; < 0.70 → 8%.
  - High humidity in flowering/fruit_set → 10% pest/disease hit.
  - Soil moisture < 0.50 → 20% water stress; < 0.60 → 5%.
  - Flowering with RVI < 0.60 → 5% poor pollination.
  - Apple with RVI < 0.70 → 5% reduced canopy density.
- `adjusted_yield = potential × ∏(1 − reduction_i / 100)`.
- Harvest status: `ready / incomplete / overripe` based on stage + days.
- **Returns** `{crop, area_acres, yield_potential_kg_per_acre, yield_potential_total_kg, vegetation_vigor, vegetation_vigor_score, current_growth_stage, growth_stage_assessment, yield_per_acre_kg, total_yield_kg, potential_loss_percent, harvest_status, limiting_factors: [{factor, impact}]}`.

### [`growth_yield/monitoring.py`](growth_yield/monitoring.py)
`GrowthMonitoring.analyze_growth_trajectory(ndvi_timeseries)`.

- Needs ≥2 points; linear regression on NDVI vs. time index.
- Trend buckets by slope: `>0.02` strong positive, `>0.005` moderate, `>−0.005` stagnant, `>−0.02` moderate decline, else severe decline.
- Recommendation text branches on `decline & current < 0.40 → Critical`, else monitor / continue.
- **Returns** `{status, trend, trend_slope, current_ndvi, ndvi_range, mean_ndvi, data_points, recommendation}`.

---

## Conventions

- **Static methods only.** No instance state.
- **Pure inputs / outputs.** Calculators must not mutate their argument dicts.
- **No silent fallbacks.** If a critical input is missing, raise — fallback selection happens upstream in the data-source adapters.
- **Lookup tables live next to the function that uses them** (e.g. fertilizer grades inside `FertilizerScheduler`, pest database inside `PestDiseaseWeedAssessor`). When a table grows past ~50 lines, factor it out.

## Tests

- [tests/remote_sensing/analysis/test_signals.py](../../../tests/remote_sensing/analysis/test_signals.py) and siblings exercise the remote-sensing math. The domain calculators are currently covered indirectly via the `scripts/test_agricultural_report.py` integration probe; targeted unit tests are a backlog item.
