# `src/jeevn/application/` — Orchestration & narrative layer

Sits between the HTTP layer ([../api/](../api/)) and the pure-calculation domain layer ([../domain/](../domain/)). Its job is to **assemble a complete advisory report** by:

1. Calling the data-source adapters in [../infrastructure/data_sources/](../infrastructure/data_sources/) to gather weather, soil, terrain, location, and crop-phenology inputs.
2. Calling each domain calculator (irrigation, soil management, fertilizer, pest, yield) with those inputs.
3. Merging everything into a single nested report dict.
4. Tracking which inputs were fabricated defaults vs. real measurements (the `data_quality` block).

It is the **single source of truth** for the advisory shape that both the API and the UI consume.

## Tech / dependencies

Pure Python. No HTTP, no DB, no Streamlit imports. Depends on:
- [../infrastructure/data_sources/aoi.py](../infrastructure/data_sources/aoi.py) (composer that bundles weather + soil + terrain + geocoding + phenology)
- [../infrastructure/pseudo_satellite.py](../infrastructure/pseudo_satellite.py) (fallback defaults)
- [../domain/](../domain/) (all agronomic math)

## Files

### [`advisory_service.py`](advisory_service.py)
The `AgriculturalReportGenerator` class. Single static `generate_report(...)` method.

- **Inputs:**
  - `lat`, `lon` — AOI centroid (used for all geo-keyed data fetches).
  - `area_acres` — for total-yield + total-water scaling.
  - `crop_name` — keys into `CropPhenologyDatabase`; defaults to `"apple"`.
  - `sowing_date` — `YYYY-MM-DD` string; drives `days_since_sowing` and accumulated GDD.
  - `ndvi_timeseries` — optional list of `{date, ndvi, ndwi?, ndre?}` dicts from the remote-sensing pipeline. Latest entry overrides the fabricated NDVI default.
  - `ndvi_raster_data` — optional dict with `ndvi_mean`, `parcel_confidence`, `crop_health_path`, `irrigation_health_path` — passed through into the report's `field_maps` block.
  - `location_name` — pre-resolved locality string; if empty, the geocoder fills it.
  - **Real-time / accuracy overrides (optional):** `sensor_reading` — a `SensorReading` fused as the top-priority soil-moisture source; `growth_stage_override` — authoritative stage from the host crop DB; `soil_test` — top tier of the NPK resolver; `village` — host-known village unlocking village-level SHC NPK. All default to prior behaviour, so existing callers are unaffected.

- **Steps:**
  1. `fetch_aoi_data(...)` returns a single dict containing `location` / `weather` / `soil` / `terrain` / `crop` / `current_growth_stage` / `accumulated_gdd` plus `_fabricated_sources` and `_alerts`.
  1a. `Sentinel1Client.fetch_latest_rvi(lat, lon)` is called for the AOI centroid; returns `{rvi, scene_date, scene_id, source}` from the latest Sentinel-1 RTC scene, or `None` if MPC STAC is down / no scene within ~10 days.
  2. `_process_ndvi_data(ndvi_timeseries, ndvi_raster_data, sar_data=...)` builds `{ndvi, rvi, rsm}` from the timeseries / raster / Sentinel-1, starting from `pseudo_satellite` defaults and overwriting with real values where available. Returns the list of fields still using defaults. **RVI source priority:** Sentinel-1 backscatter measurement → NDVI×1.08 proxy → `pseudo_satellite.RVI`. When Sentinel-1 returns a real value, `data["rvi_source"]` and `data["rvi_scene_date"]` are populated so downstream consumers can attribute the value.
  3. Calls each domain calculator with `(aoi_data, ndvi_data, area_acres)` and slots the result into `report["components"][...]`.
     - `IrrigationScheduler.generate_schedule` (+ attaches `terrain` so the narrative can shape irrigation advice by slope/aspect).
     - `SoilManagementCalculator.analyze_soil`.
     - `YieldGrowthCalculator.calculate_yield_projection`.
     - `GrowthMonitoring.analyze_growth_trajectory` (only if timeseries has ≥2 points).
     - `PestDiseaseWeedAssessor.assess_pest_disease_risk`.
     - `NutrientRequirementCalculator.calculate_nutrient_requirements` → `FertilizerScheduler.generate_fertilizer_schedule`.
  4. Builds `environmental_context` (raw weather/soil/terrain/growth_stage).
  5. `_generate_summary(...)` distills the components into three lists: `key_findings`, `urgent_actions`, `recommendations`. Branches on SOC status, vegetation vigor, yield loss %, pest count, nutrient deficiencies.
  6. `data_quality` block: dedupes `_fabricated_sources` from the AOI composer + the NDVI fabrication list, attaches per-key human descriptions from `pseudo_satellite.describe(...)`, attaches `_alerts` (e.g. "AOI is in built-up land"), and writes a top-level `warning` string.

- **Output:** the full report dict described in Section 7.3 of [../../../ARCHITECTURE.md](../../../ARCHITECTURE.md).

Also exports the convenience function `generate_agricultural_report_from_aoi(...)` for non-API callers (the [test_agricultural_report.py](../../../scripts/test_agricultural_report.py) script uses it directly).

### Real-time advisory & alert layer

A thin layer on top of the accurate report that adds ground-sensor fusion, dry-spell detection, and alert generation. **Advice + alerts only — message delivery (SMS/WhatsApp) is Part 2** behind the `Notifier` seam.

- [`realtime_advisory.py`](realtime_advisory.py) — `RealtimeAdvisor.evaluate(lat, lon, crop, sowing_date, area_acres, sensor, growth_stage_override, soil_test, location_name, village, notifier)`. Reads the (optional) sensor (dropping stale readings), runs `generate_report` with the sensor fused, fetches low-latency recent+forward rainfall (`fetch_forecast(..., past_days=…)`), computes the soil-water deficit (reusing `IrrigationCalculator.calculate_soil_water_deficit`), detects a dry spell (gap-safe), and returns `{report, dry_spell, alerts, …}`. Config via `AdvisoryConfig.from_env()` (thresholds).
- [`alerts.py`](alerts.py) — `Alert` dataclass + `build_alerts(...)`: `dry_spell`, `irrigate_now` (deficit), `hold_fertigation` (real 48 h forecast rain ≥ threshold), `high_salinity` (real EC), `fertilize` (confidence-gated — only ≥ medium-confidence NPK doses).
- [`render.py`](render.py) — `render_alert`/`render_advisory` → short human-readable strings (Part-2 delivery reuses these verbatim).
- [`notifier.py`](notifier.py) — `Notifier` ABC + `ConsoleNotifier` (prints). Twilio SMS/WhatsApp lands here in Part 2.
- [`realtime_monitor.py`](realtime_monitor.py) — `run_once()` / loop + `python -m jeevn.application.realtime_monitor --once` demo (MockSoilSensor + ConsoleNotifier).

### [`narratives.py`](narratives.py)
Pure narrative-shaping helpers — **no I/O, no Streamlit, no ReportLab**. Both the UI sections and the PDF generator import from here so the prose threshold logic lives in one place.

- `terrain_irrigation_advice(slope_pct, aspect_compass) -> str`
  - **Thresholds:** `<2%` essentially flat (basin or flood OK), `2–5%` mild slope (prefer drip), `>5%` steep (contour-drip + terracing). Picked from FAO Irrigation & Drainage Paper 24 + ICAR field guidelines.
  - Adds an aspect-conditioned insolation note: south-facing (S/SE/SW) → "schedule irrigation earlier in the morning"; north-facing (N/NE/NW) → "ET is moderated".

### [`__init__.py`](__init__.py)
Empty package marker.

## Conventions

- **All static methods.** No state lives on the service classes — call sites pass everything in explicitly.
- **Fabrication tracking is not optional.** Every code path that touches a fallback default must propagate the key upward into `data_quality.fabricated_fields`. The user always sees what's real vs. illustrative.
- **Single source of truth.** When the UI and PDF render the same thing differently, the difference must come from formatting only — the *content* should always come from the report dict produced here.
