# `src/jeevn/infrastructure/` — External adapters

Everything that talks to the outside world: HTTP APIs, the SQL database, Prometheus, MLflow, bundled raster files on disk. Each adapter exposes a small typed interface that the application/domain layers can call without knowing what's behind it.

The cardinal rule: **fail soft, surface the substitution.** If a real source is unreachable, fall back to a deterministic default and flag the field name so the report's `data_quality` block can warn the user.

## Subpackages

```
infrastructure/
├── data_sources/          # External REST APIs + bundled raster/CSV sources
├── sensors/               # Ground soil-moisture sensor adapters (Mock/REST/MQTT)
├── db/                    # SQLAlchemy engine, session, models
├── monitoring/            # Prometheus + MLflow
└── pseudo_satellite.py    # Single source of truth for fallback defaults
```

---

## `pseudo_satellite.py` — fallback defaults

[`pseudo_satellite.py`](pseudo_satellite.py) holds **every** fabricated value the system uses when real data isn't available. Importing from anywhere else (`domain/` constants, hard-coded fallbacks in adapters) is forbidden — if a default is needed, it goes here.

- **Constants:** `NDVI`, `RVI`, `RSM`, `SOIL_MOISTURE`, `DEFAULT_AREA_ACRES`, `DEFAULT_CROP_NAME = "apple"`, `DEFAULT_LATITUDE = 29.92`, `DEFAULT_LONGITUDE = 73.97` (~10 km east of Sri Ganganagar, picked because it has full SoilGrids coverage and is real cropland), `DEFAULT_DAYS_SINCE_SOWING = 60`, `DEFAULT_TIMEZONE = "Asia/Kolkata"`.
- **Templates:** `DEFAULT_SOIL_PROPERTIES`, `GANGANAGAR_SOIL_PROPERTIES`, `DEFAULT_WEATHER_DAILY` (7-day semi-arid May baseline), `DEFAULT_LOCATION`, `DEFAULT_TERRAIN` (flat plain).
- **Builders:** `make_default_weather(lat, lon)`, `make_default_forecast(lat, lon, days=7)`, `make_default_soil(lat, lon, location_name)`, `make_default_location(lat, lon)`, `make_default_terrain()` — each returns the dict in the same shape its real adapter does, with a `_fabricated` (or `_fabricated_fields`) flag set.
- **`FABRICATED_FIELD_DESCRIPTIONS`** — human-readable explanations keyed by field name; used by `describe(field)` to build the bulleted "what was fabricated and why" list in the UI.

---

## `data_sources/` — external data adapters

### [`data_sources/aoi.py`](data_sources/aoi.py) — composer
**Not** a real source itself. `fetch_aoi_data(lat, lon, location_name, start_date, end_date, crop_name, sowing_date, sensor_soil_moisture, sensor_is_fraction, soil_test, growth_stage_override, village)` calls every sub-adapter, normalises the outputs, and hoists fabricated-field flags into a single top-level `_fabricated_sources` list.

Real-time / accuracy overrides (all optional, default to prior behaviour):
- **`sensor_soil_moisture`** (+`sensor_is_fraction`) — a fresh in-field reading. Raw m³/m³ is normalised via the AOI's real SoilGrids texture and used as the **top-priority** soil-moisture source (above NISAR/Open-Meteo), setting `soil.properties.soil_moisture_source = "ground-sensor"`.
- **`soil_test`** — host-DB soil test; top tier of the NPK resolver.
- **`growth_stage_override`** — authoritative stage from the host crop DB (else phenology+GDD).
- **`village`** — host-known village name; unlocks village-level SHC NPK (injected into `location["village"]`).

Special behaviour:
- Combines Open-Meteo's hourly `soil_moisture_0_to_7cm` (m³/m³) with SoilGrids texture to produce a `fraction-of-field-capacity` value that downstream agronomic comparisons expect. Without this normalisation, raw m³/m³ values would trip the `<0.5` water-stress threshold in [growth_yield/projection.py](../domain/growth_yield/projection.py) on well-watered soil.
- Walks the weather daily `temp_mean` series with `t_base` from the crop's phenology entry to accumulate Growing-Degree-Days, feeds GDD into `CropPhenologyDatabase.get_current_growth_stage` for a more accurate stage than the days-based heuristic.
- Surfaces a structured `_aoi_in_built_up_land` **alert** (not just a flag) when SoilGrids reports all-null at the centroid — the UI displays a red banner with a "redraw the polygon over actual cropland" instruction.

- Resolves a tiered **`radar_soil_moisture`** (RSM): **ground sensor** (tier 0, when supplied) → NISAR SME2 (m³/m³ → fraction via texture field capacity, only attempted when Earthdata creds are set) → Open-Meteo `soil_moisture_current` → fabricated `pseudo_satellite.RSM`. Surfaced so `advisory_service` can override the `rsm` default and drop it from the fabricated list when real.
- Attaches a per-nutrient **`soil_nutrients`** profile (N/P/K supply fraction + status + source + confidence) via `soil_nutrients.resolve_npk`.

**Returns** a dict with `location`, `weather`, `forecast`, `soil`, `terrain`, `radar_soil_moisture`, `soil_nutrients`, `crop`, `current_growth_stage`, `sowing_date`, `days_since_sowing`, `accumulated_gdd`, `crop_name`, `_fabricated_sources`, `_alerts`.

### [`data_sources/weather.py`](data_sources/weather.py) — Open-Meteo
- **Endpoint:** `https://archive-api.open-meteo.com/v1/archive` (no API key).
- **Daily variables fetched:** `temperature_2m_{max,min,mean}`, `precipitation_sum`, `shortwave_radiation_sum`, `windspeed_10m_max` (note: `_sum` variants are required since the rename — legacy names 400).
- **Hourly:** `temperature_2m`, `relative_humidity_2m`, `precipitation`, `soil_moisture_0_to_7cm`. The soil-moisture 24-h mean is exposed as `daily.soil_moisture_0_to_7cm_mean` and the RH 24-h mean as `daily.relative_humidity_mean` (real RH that replaces the old fabricated humidity proxy). The full hourly temp/RH/precip arrays are surfaced under `hourly` for the grape disease models (Gubler powdery / downy wet-period).
- **Date clamping:** start/end are clamped to "today" if the caller passed a future date (sowing date plus 6-month season), avoiding 400 Bad Request.
- **Output shape:** `{location: {lat, lon, timezone}, daily: {dates, temp_max, temp_min, temp_mean, rainfall, solar_radiation, wind_speed, soil_moisture_0_to_7cm_mean, relative_humidity_mean}, hourly: {time, temperature_2m, relative_humidity_2m, precipitation}, _fabricated: False}`. On fallback the `hourly` arrays are empty and `relative_humidity_mean` is None (no synthesised hourly weather).
- On any failure → `pseudo_satellite.make_default_weather(lat, lon)`.
- **`WeatherDataFetcher.fetch_forecast(lat, lon, days=7, past_days=0)`** — forward forecast from the **forecast** API (`api.open-meteo.com/v1/forecast`, distinct from the historical archive). Daily `temp_{max,min,mean}`, `precipitation_sum` (mm), `precipitation_probability_max` (%), radiation, wind, plus a forward `hourly` block (`temperature_2m`, `relative_humidity_2m`, `precipitation`) that drives the actionable this-week grape disease alerts. Used by the irrigation scheduler to subtract per-day forecast rain from per-day ETc — the archive is backward-looking and can't gate a forward schedule. When `past_days>0` the daily arrays also include that many recent low-latency days (with `today_index` marking the split) — the real-time dry-spell detector uses this instead of the ~5-day-lagged archive. On failure → `pseudo_satellite.make_default_forecast(lat, lon, days)` (zero-rain semi-arid baseline, `_fabricated=True` → surfaces as `forecast` in the report's fabricated list; the alert layer treats this as a data gap and suppresses dry-spell alerts rather than trusting the zero-rain).

### [`data_sources/soil.py`](data_sources/soil.py) — ISRIC SoilGrids + bundled salinity raster
- **`SoilGridsClient.fetch(lat, lon)`** — `GET https://rest.isric.org/soilgrids/v2.0/properties/query` for `phh2o, soc, bdod, sand, silt, clay, cec, nitrogen` at depths `0-5/5-15/15-30 cm` (`nitrogen` → `total_nitrogen_g_per_kg`, a total-N estimate used as a low-confidence available-N proxy in the NPK resolver). Depth-weighted mean (5/10/15 cm), then applies SoilGrids' `d_factor` to convert mapped → target units, then SOC g/kg → mass %. Returns a dict with `_no_data_in_land_mask: True` when the centroid lies in SoilGrids' built-up / water / rock exclusion zone (HTTP 200 + all-null).
- **`classify_usda_texture(sand, silt, clay) -> str`** — 12-class USDA approximation; `whc_from_texture` and `infiltration_from_texture` lookup tables convert texture → water-holding capacity (mm/30cm) and infiltration (mm/h); `field_capacity_from_texture` returns m³/m³ field capacity used for the SM normalisation in [aoi.py](data_sources/aoi.py).
- **`SalinityRasterSampler.sample(lat, lon)`** — opens [data/static/salinity_india.tif](../../../data/static/salinity_india.tif) (built by [scripts/dev_smoke/build_salinity_clip.py](../../../scripts/dev_smoke/build_salinity_clip.py)) lazily, samples the FAO/USDA 5-class salinity code, maps to a representative EC midpoint in dS/m (`0 → 1.0`, `1 → 3.0`, `2 → 6.0`, `3 → 12.0`, `4 → 18.0`).
- **`SoilDataFetcher.fetch_soil_data`** — starts from the regional `pseudo_satellite` template (everything fabricated), overlays real SoilGrids values where available, overlays real salinity from the bundled raster where in-bbox. Returns `{location, properties: {...}, _fabricated_fields: {prop: bool}, _aoi_in_built_up_land: bool}`. Per-property fabrication tracking, not a single dict-wide flag.

### [`data_sources/terrain.py`](data_sources/terrain.py) — Open-Elevation + bundled DEM
Three-tier resolution for slope + aspect:
1. **Primary — Open-Elevation API** (`POST https://api.open-elevation.com/api/v1/lookup`). Queries a 3×3 grid at 30 m spacing around the centroid, computes slope/aspect via the **Horn (1981) 3×3 kernel** (matches GDAL/ArcGIS).
2. **Fallback — bundled ETOPO 2022** ([data/static/dem_india.tif](../../../data/static/dem_india.tif), built by [scripts/dev_smoke/build_dem_clip.py](../../../scripts/dev_smoke/build_dem_clip.py)). 30 arc-sec resolution → 3×3 grid at 1 km spacing. Coarse but real.
3. **Last resort — `pseudo_satellite.make_default_terrain()`** (flat plain).

**Returns** `{slope_percent, aspect_degrees, aspect_compass: one of {N, NE, E, SE, S, SW, W, NW, flat}, elevation_m, source: "open-elevation"|"bundled-dem"|"fabricated", _fabricated}`. The narrative layer uses `source` to attribute the data correctly in references.

### [`data_sources/geocoding.py`](data_sources/geocoding.py) — Nominatim
- `GET https://nominatim.openstreetmap.org/reverse` with a custom `User-Agent` (Nominatim's usage policy requires one; without it the endpoint returns 403).
- Tries locality keys in priority order: `city → town → village → hamlet → suburb → county` (rural polygons rarely have `city`).
- **Returns** `{latitude, longitude, name, city, district, village, state, country, display_name, timezone, _fabricated: False}`. `district` (`state_district`/`county`) keys the SHC district NPK lookup; `village` (`village`/`hamlet`) can *refine* it to the village tier when present.
- On any failure → `pseudo_satellite.make_default_location(lat, lon)`.

### [`data_sources/nisar.py`](data_sources/nisar.py) — NISAR SME2 L-band soil moisture
- **`NisarSoilMoistureClient.fetch_sm_at(lat, lon, days_back=14)`** — three-stage pipeline: (1) keyless `asf_search` query for the latest SME2 granule over the AOI within `days_back`; (2) Earthdata-authenticated download of the granule HDF5 (~120 MB) to `data/cache/nisar/` (gitignored, keeps the 2 most-recent); (3) read `soilMoisture` (m³/m³) at the nearest grid cell from the first candidate algorithm (DSG → PMI → TSR) whose `retrievalQualityFlag` is 0. Rejects points within ~5 km of the granule edge.
- **HDF5 layout** (confirmed against a real 2026-01 granule): `science/LSAR/SME2/grids/` with 1-D `latitude`/`longitude` and `algorithmCandidates/{DSG,PMI,TSR}/{soilMoisture, retrievalQualityFlag}`. EPSG:6933 EASE-Grid 2.0; fill `-9999`; units m³/m³.
- **Credentials:** `EARTHDATA_USER`/`EARTHDATA_PASS` env vars (search is keyless; download needs auth + the "ASF Data Access" app authorised on the Earthdata profile). No creds → returns None.
- **Returns** `{soil_moisture_m3m3, algorithm, quality_flag, pass_date, granule_id, source: "nisar-sme2"}` or None.
- **Status:** SME2 is Beta v1, production paused since 2026-01-20, so live requests find no fresh pass and the composer falls through to Open-Meteo. The pipeline is real + tested against historical granules and lights up when production resumes.

### [`data_sources/sar.py`](data_sources/sar.py) — Sentinel-1 RTC backscatter (real RVI)
- **`Sentinel1Client.fetch_latest_rvi(lat, lon, days_back=10)`** — queries Microsoft Planetary Computer's STAC catalogue for the `sentinel-1-rtc` collection at the AOI point in the last `days_back` days. Picks the newest scene, signs the VV + VH asset hrefs with an MPC SAS token, reads a 5×5 pixel window at the centroid via rasterio `/vsicurl/` (HTTP range reads, no full-scene download), computes the mean linear-power backscatter for each band.
- **`fetch_rvi_raster(geojson, aoi_id, days_back=10, output_dir="data")`** — same STAC pick, but reads the **full polygon-clipped raster** for both bands (rasterio.mask with `crop=True`), computes per-pixel RVI, masks pixels outside the polygon to NaN, and writes a compressed GeoTIFF to `<output_dir>/rvi_<aoi_id>.tif`. Returns `{rvi_raster, scene_date, scene_id, source}` or `None`. Called by [api/routes/aoi.py](../api/routes/aoi.py) during AOI submission alongside the Sentinel-2 NDVI/NDWI raster pipeline; the resulting path lands in `raster_quality.rvi_raster_available` and is served via `/aoi/{id}/maps/rvi.png`.
- **RVI formula:** `4 · VH / (VV + VH)` in linear power units. Sentinel-1 RTC values are already in γ⁰ linear so no dB→linear conversion is needed. Clipped to `[0, 1.5]` to defang speckle outliers.
- **Returns** `{rvi, scene_date, scene_id, source: "sentinel-1-rtc"}` (centroid sampler) or the raster path equivalent (raster builder) or `None` on any failure (STAC down, no scene in window, raster read failure, VV/VH missing).
- Used by [application/advisory_service.py](../application/advisory_service.py) as the **top-priority** source for the `rvi` *value*; falls back to NDVI×1.08 proxy, then `pseudo_satellite.RVI`. The *raster* is independently produced and served as a field map.
- NISAR L-band (task #4 in TASKS.md) will eventually live in this same module as an even-higher priority canopy-penetrating source — until then Sentinel-1 C-band is our only real SAR.

### [`data_sources/soil_nutrients.py`](data_sources/soil_nutrients.py) — tiered N/P/K resolver
Replaces the legacy hardcoded "current soil levels" constant in [domain/fertilizer/requirements.py](../domain/fertilizer/requirements.py) with a per-nutrient **soil-supply fraction** (0..1 of the crop's recommended dose) + status + `source` + `confidence`, resolved independently per nutrient through the highest-confidence tier that has it:
1. **injected soil test** (`soil_test`) — `high`.
2. **India Soil Health Card**, cascading **village → district → state**: village from the bundled gzipped table (only when a village is known — not resolvable from a lat/lon alone), district from the bundled CSV (the reliable lat/lon fallback), then a state average. `medium`/`medium`/`low`.
3. **SoilGrids/pedotransfer** — N from `total_nitrogen_g_per_kg`, K from CEC; P has no reliable proxy (omitted). `low`.
4. **none** → nutrient omitted (caller keeps the flagged legacy constant).

Names are accent/case/punctuation-normalised for robust OSM↔SHC matching. Tables are bundled at [data/static/shc_district_npk.csv](../../../data/static/shc_district_npk.csv) + [shc_village_npk.csv.gz](../../../data/static/shc_village_npk.csv.gz) (village loaded lazily), built by [scripts/dev_smoke/build_shc_district_npk.py](../../../scripts/dev_smoke/build_shc_district_npk.py). `DISABLE_SOILGRIDS_NPK=1` drops the low-confidence proxy tier.

---

## `sensors/` — ground soil-moisture adapters

Pluggable in-field soil-moisture sources fused as the **top-priority** moisture input. All implement `SoilSensor.read() -> SensorReading | None` and are **non-throwing** (device/transport error → `None` → pipeline falls back to modelled/satellite moisture).

- [`sensors/base.py`](sensors/base.py) — `SoilSensor` ABC + `SensorReading` (raw m³/m³ or fraction-of-FC via `is_fraction`, optional temps, `is_fresh(max_age_min)`).
- [`sensors/mock.py`](sensors/mock.py) — `MockSoilSensor` (dev/tests; supports jitter + simulated failure).
- [`sensors/rest.py`](sensors/rest.py) — `RestSensor` polls a JSON HTTP endpoint (dotted-path field mapping).
- [`sensors/mqtt.py`](sensors/mqtt.py) — `MqttSensor` caches the last value on a broker topic (optional `paho-mqtt`).

---

## `db/` — SQLAlchemy

### [`db/connection.py`](db/connection.py)
- `DATABASE_URL` env var → defaults to `sqlite:///./data/dev.db`.
- For SQLite, passes `connect_args={"check_same_thread": False}` so the same connection is usable across the FastAPI threadpool.
- Exports `engine`, `SessionLocal`, `Base`, `init_db()` (creates all tables), and a `get_db()` dependency generator for FastAPI.

### [`db/models.py`](db/models.py)
Three tables (all UUID PKs, all timestamps `datetime.utcnow`):

| Table          | Columns                                                                                         |
|----------------|-------------------------------------------------------------------------------------------------|
| `aois`         | `id`, `name`, `geojson_data` JSON, `start_date`, `end_date`, `created_at`, `updated_at`         |
| `ingest_jobs`  | `id`, `aoi_id`, `status` (`pending` default), `metadata_path`, `created_at`, `completed_at`     |
| `artifacts`    | `id`, `aoi_id`, `artifact_type`, `local_path`, `s3_uri`, `sha256_hash`, `created_at`            |

The DB is a **secondary mirror** — the API writes to it but reads from the in-memory `AOI_STORE` in [api/routes/aoi.py](../api/routes/aoi.py). Without a DB, the system still functions for the lifetime of a single API process.

---

## `monitoring/` — observability

### [`monitoring/metrics.py`](monitoring/metrics.py)
Prometheus counters + histogram registered into a **private `CollectorRegistry`** (not the global one). This isolates Jeevn metrics from any other prometheus_client user in the same process and makes the module safe to re-import under Streamlit's in-process hot reload.

Exposes:
- `aoi_created_counter` (`ashi_aoi_created_total{status}`)
- `aoi_error_counter` (`ashi_aoi_errors_total`)
- `request_duration_histogram` (`ashi_request_duration_seconds{endpoint}`)
- `metrics_app` — an ASGI sub-app the FastAPI root mounts at `/metrics`.

### [`monitoring/mlflow.py`](monitoring/mlflow.py)
Opt-in MLflow helpers. `setup_mlflow()` honours `MLFLOW_TRACKING_URI`. `log_dummy_run(params, metrics, artifacts)` logs a single run, gracefully no-ops when `mlflow` isn't installed. Not wired into the request path yet — placeholder for future experiment tracking.

---

## Conventions

- **Adapters never raise on remote failure.** They log a `[WARN] ...` line and fall back to `pseudo_satellite`.
- **Every fallback path sets a flag.** Either `_fabricated: True` (whole-dict) or a `_fabricated_fields: {prop: bool}` map (per-property).
- **No domain logic.** Adapters return raw, lightly-normalised data; classification, recommendation, and scoring happen in [../domain/](../domain/).
- **Lazy heavy imports.** rasterio (with its GDAL dependency) is imported inside method bodies, not at module top, so the rest of the codebase loads even when rasterio is missing.

## Tests

- [tests/infrastructure/data_sources/](../../../tests/infrastructure/data_sources/) — `test_aoi.py`, `test_aoi_sensor_fusion.py`, `test_soil.py`, `test_soil_nutrients.py`, `test_terrain.py`, `test_weather.py`, `test_sentinel1_sar.py`, `test_nisar.py`.
- [tests/infrastructure/sensors/test_soil_sensors.py](../../../tests/infrastructure/sensors/test_soil_sensors.py) — sensor contract + freshness.
- [tests/infrastructure/db/test_models.py](../../../tests/infrastructure/db/test_models.py) — round-trip checks for AOI / IngestJob / Artifact.
