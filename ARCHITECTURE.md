# Jeevn (ashi) — Architecture Overview

A high-level technical map of what lives in this repository, how the pieces fit together, and where to find what. For a folder-by-folder deeper dive, see the `OVERVIEW.md` inside each top-level folder.

---

## 1. What this project is

**Jeevn** is an agricultural remote-sensing MVP that takes a polygon of farmland on a map (an "AOI" — Area of Interest) plus a crop type and produces a multi-page **Personalized Farm Advisory Report**. The report covers:

- **Field maps** — real Sentinel-2 NDVI / NDWI rasters cropped to the AOI polygon
- **Irrigation schedule** — daily water requirement (FAO-56 / Hargreaves-Samani ET0)
- **Soil management** — pH, salinity, organic carbon, texture, recommendations
- **Growth & yield projection** — vegetation vigor, limiting factors, projected yield
- **Pest, disease & weed risk** — temperature / humidity / vegetation-density scoring
- **Fertilizer schedule** — N/P/K/S/Zn gaps + specific product/dose recommendations

The report is rendered both as an interactive **Streamlit UI** and as a downloadable **5-page PDF**.

The package is published as a Python distribution named `jeevn` under [src/jeevn/](src/jeevn/) (src-layout). The repository folder is called `ashi`; the import name is `jeevn`.

---

## 2. Tech stack

| Layer                | Tech                                                                    |
|----------------------|-------------------------------------------------------------------------|
| Backend API          | **FastAPI** + Uvicorn ([src/jeevn/api/](src/jeevn/api/))                |
| UI                   | **Streamlit** + folium + streamlit-folium ([src/jeevn/ui/](src/jeevn/ui/)) |
| PDF                  | **ReportLab** + Pillow ([src/jeevn/ui/pdf/](src/jeevn/ui/pdf/))         |
| ORM / DB             | **SQLAlchemy** (SQLite default, Postgres via Docker)                    |
| Object storage       | **MinIO** (S3-compatible) via docker-compose                            |
| Raster I/O           | **rasterio** + numpy + scipy (optional — degrades gracefully)           |
| Observability        | **prometheus-client** + **MLflow**                                      |
| Tests                | **pytest** with `conftest.py` adding `src/` to `sys.path`               |
| Containerisation     | **Dockerfile** + `infra/docker-compose.example.yml`                     |
| Python               | 3.10+ (3.11 in Docker, 3.12 venvs locally)                              |

Full dependency list: [requirements.txt](requirements.txt) and [pyproject.toml](pyproject.toml).

---

## 3. Top-level layout

```
ashi/
├── src/jeevn/             # Importable Python package (the application)
│   ├── api/               # FastAPI app, routes, request/response schemas
│   ├── application/       # Orchestration (report assembly, narratives)
│   ├── domain/            # Pure agronomic calculations (no I/O)
│   ├── infrastructure/    # External adapters: data sources, DB, monitoring
│   ├── ingestion/         # Sentinel-2 STAC ingest (Planetary Computer)
│   ├── remote_sensing/    # NDVI/NDWI raster pipeline + analysis
│   └── ui/                # Streamlit app, API client, PDF generator
├── tests/                 # pytest suite (mirrors src/jeevn/ tree)
├── scripts/               # Dev helpers, smoke tests, raster prep scripts
├── docs/                  # Architecture docs + clean-room agent contracts
├── infra/                 # Docker Compose for postgres + minio + api
├── data/                  # Runtime outputs + bundled static rasters
├── Dockerfile             # Container build for the API
├── pyproject.toml         # Package metadata + dependencies
├── requirements.txt       # Pip-installable mirror of dependencies
├── conftest.py            # Adds `src/` to sys.path for pytest
├── Makefile               # Convenience targets
├── README.md              # Setup + run instructions
├── QUICKSTART.md          # Step-by-step local-dev walkthrough
└── TASKS.md               # Shared task list (read this before working)
```

---

## 4. End-to-end data flow

```
┌──────────────────┐     POST /aoi          ┌──────────────────────┐
│  Streamlit UI    │ ─────────────────────▶ │  FastAPI app         │
│  (jeevn.ui.app)  │                        │  (jeevn.api.app)     │
└──────────────────┘                        └──────────┬───────────┘
                                                       │
                              ┌────────────────────────┼──────────────────────┐
                              ▼                        ▼                      ▼
                   ┌────────────────┐      ┌────────────────────┐   ┌──────────────────┐
                   │  ingestion/    │      │  remote_sensing/   │   │  infrastructure/ │
                   │  sentinel.py   │      │  pipeline.py       │   │  db/             │
                   │                │      │                    │   │                  │
                   │ → STAC search  │      │ aggregate_ndvi()   │   │ AOI / IngestJob/ │
                   │   (Planetary   │      │ compute_raster()   │   │ Artifact tables  │
                   │   Computer)    │      │ analyze_signals()  │   │ (SQLite/Postgres)│
                   │ → Saves        │      │ → CSV timeseries   │   └──────────────────┘
                   │   metadata     │      │ → GeoTIFF NDVI/NDWI│
                   │   JSON         │      └────────────────────┘
                   └────────────────┘
                                                       │
                              ┌────────────────────────┘
                              ▼
                                  POST /advisory/agricultural
                   ┌──────────────────────────────────────────────┐
                   │  application/advisory_service.py             │
                   │  AgriculturalReportGenerator.generate_report │
                   └──────────────┬───────────────────────────────┘
                                  │
            ┌─────────────────────┼──────────────────────────────┐
            ▼                     ▼                              ▼
  ┌──────────────────┐  ┌────────────────────┐   ┌────────────────────────────┐
  │ infrastructure/  │  │   domain/          │   │ infrastructure/            │
  │ data_sources/    │  │                    │   │ pseudo_satellite.py        │
  │                  │  │ irrigation/        │   │                            │
  │ ▸ weather  (Open-│  │   et0 + scheduler  │   │ Fallback defaults whenever │
  │   Meteo)         │  │ soil/management    │   │ a real source is missing.  │
  │ ▸ soil     (ISRIC│  │ fertilizer/        │   │ Each fabricated field is   │
  │   SoilGrids +    │  │   requirements +   │   │ surfaced in the report's   │
  │   bundled        │  │   schedule         │   │ `data_quality` block.      │
  │   salinity tiff) │  │ growth_yield/      │   └────────────────────────────┘
  │ ▸ terrain  (Open-│  │   projection +     │
  │   Elevation +    │  │   monitoring       │
  │   bundled DEM)   │  │ pest_disease_weed/ │
  │ ▸ geocoding      │  │   assessment       │
  │   (Nominatim)    │  │ crop/phenology     │
  └──────────────────┘  └────────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────────┐
                │  Full advisory JSON returned to UI      │
                │  → Streamlit sections (jeevn.ui.sections│
                │  → "Generate PDF" button                │
                │     → jeevn.ui.pdf.generator (5 pages)  │
                └─────────────────────────────────────────┘
```

Key design points:

- **In-memory primary store** — AOIs are kept in a process-local `AOI_STORE: Dict` guarded by a `threading.Lock`. The SQLAlchemy DB is a secondary mirror that is opportunistically written to but never read from in the request path.
- **Graceful degradation** — every external integration (DB, ingest, raster preproc, monitoring) is wrapped in a try/except + availability flag. The API will still return 200s if rasterio, the DB, MinIO, or even Planetary Computer is unreachable.
- **Fabrication tracking** — when any data source falls back to a default, the field name is added to `report["data_quality"]["fabricated_fields"]` and surfaced to the user via a yellow banner + bulleted list. See [src/jeevn/infrastructure/pseudo_satellite.py](src/jeevn/infrastructure/pseudo_satellite.py).
- **Decoupled UI** — the Streamlit app reaches the backend only via HTTP through [src/jeevn/ui/api_client.py](src/jeevn/ui/api_client.py). No in-process imports of `application/` or `domain/` from the UI.

---

## 5. External data sources

| Source                         | Used for                                 | Where it lives                                                              | Fallback                            |
|--------------------------------|------------------------------------------|-----------------------------------------------------------------------------|-------------------------------------|
| **Microsoft Planetary Computer STAC** | Sentinel-2 L2A item search + COG hrefs   | [ingestion/sentinel.py](src/jeevn/ingestion/sentinel.py)                    | `runner.stub_ingest`               |
| **Sentinel-2 COGs (B03/04/05/08/11)** | NDVI/NDWI/NDRE raster computation        | [remote_sensing/analysis/confidence.py](src/jeevn/remote_sensing/analysis/confidence.py) | Raster reported as `None`           |
| **Open-Meteo Archive API**     | Daily temp / rain / radiation / wind + hourly soil moisture | [data_sources/weather.py](src/jeevn/infrastructure/data_sources/weather.py) | `pseudo_satellite.make_default_weather` |
| **Open-Meteo Forecast API**    | Forward forecast + low-latency recent rain (`past_days`) for scheduling + dry-spell | [data_sources/weather.py](src/jeevn/infrastructure/data_sources/weather.py) | `pseudo_satellite.make_default_forecast` (→ data gap, alerts suppressed) |
| **ISRIC SoilGrids v2.0 REST**  | pH, SOC, sand/silt/clay, CEC, bulk density, total N (0–30 cm) | [data_sources/soil.py](src/jeevn/infrastructure/data_sources/soil.py)       | `pseudo_satellite.make_default_soil` |
| **India Soil Health Card (data.gov.in)** | Soil N/P/K status by village/district (bundled CSVs) | [data_sources/soil_nutrients.py](src/jeevn/infrastructure/data_sources/soil_nutrients.py) | SoilGrids/pedotransfer → flagged constant |
| **Ground soil-moisture sensor** | Real in-field moisture, fused as top-priority source | [infrastructure/sensors/](src/jeevn/infrastructure/sensors/) (Mock/REST/MQTT) | NISAR → Open-Meteo modelled moisture |
| **ISRIC GSSmap 2016**          | Soil salinity / EC (India-clipped raster) | [data_sources/soil.py](src/jeevn/infrastructure/data_sources/soil.py) (bundled tif) | Fabricated EC                       |
| **Open-Elevation API**         | Slope + aspect (Horn 1981 from 3×3 SRTM grid) | [data_sources/terrain.py](src/jeevn/infrastructure/data_sources/terrain.py) | Bundled ETOPO 2022 → fabricated flat plain |
| **ETOPO 2022 30 arc-sec**      | Fallback DEM when Open-Elevation down    | [data_sources/terrain.py](src/jeevn/infrastructure/data_sources/terrain.py) (bundled tif) | Fabricated flat plain               |
| **Nominatim (OpenStreetMap)**  | Reverse geocoding (locality / state)     | [data_sources/geocoding.py](src/jeevn/infrastructure/data_sources/geocoding.py) | `pseudo_satellite.make_default_location` |
| **FAO-56 Universal Crop DB**   | Crop phenology (Kc, root depth)          | `data/static/fao56_crop_db.json`                                            | Fallback to wheat                         |

Bundled rasters + the SHC N/P/K CSVs live under `data/static/` and are produced by one-shot prep scripts in [scripts/dev_smoke/](scripts/dev_smoke/) (`build_dem_clip.py`, `build_salinity_clip.py`, `build_shc_district_npk.py`, `build_fao56_db.py`).

**Real-time advisory layer** ([application/realtime_advisory.py](src/jeevn/application/realtime_advisory.py)) sits on top of the report pipeline: it fuses a ground soil-moisture sensor, detects dry spells from low-latency + forecast rainfall, and emits confidence-gated irrigation/fertilisation **alerts** via a `Notifier` (Part 1: `ConsoleNotifier`; SMS/WhatsApp is Part 2). Run: `python -m jeevn.application.realtime_monitor --once`.

---

## 6. HTTP API surface

Defined in [src/jeevn/api/](src/jeevn/api/). Default port: `8000`.

| Method | Path                                     | Description                                                                  | Schemas |
|--------|------------------------------------------|------------------------------------------------------------------------------|---------|
| GET    | `/health`                                | Liveness probe                                                               | `HealthResponse` |
| POST   | `/aoi`                                   | Submit AOI (GeoJSON + dates). Triggers ingest + raster preproc. Returns NDVI timeseries + raster paths + parcel confidence. | `AOIRequest` → `AOIResponse` |
| GET    | `/aoi/{aoi_id}/report`                   | Re-fetch the report for a previously submitted AOI                           | → `ReportResponse` |
| GET    | `/aoi/{aoi_id}/maps/{kind}.png`          | Returns colorized NDVI/NDWI PNG (`kind` ∈ {`ndvi`, `ndwi`}). 404 if no real raster exists. | image/png |
| POST   | `/advisory/agricultural`                 | Generate the full agricultural advisory report                               | `AgriculturalAdvisoryRequest` → `AgriculturalAdvisoryResponse` |
| GET    | `/advisory/agricultural/{advisory_id}`   | Stub retrieval — not persisted yet                                           | — |
| POST   | `/advisory/health-check`                 | Reports whether the advisory module imported successfully                    | — |
| GET    | `/metrics`                               | Prometheus metrics (mounted if `prometheus_client` available)                | text/plain |

---

## 7. Data model

### 7.1 Database tables ([infrastructure/db/models.py](src/jeevn/infrastructure/db/models.py))

| Table          | Columns                                                                                       |
|----------------|-----------------------------------------------------------------------------------------------|
| `aois`         | `id` UUID PK, `name`, `geojson_data` JSON, `start_date`, `end_date`, `created_at`, `updated_at` |
| `ingest_jobs`  | `id` UUID PK, `aoi_id` UUID, `status`, `metadata_path`, `created_at`, `completed_at`          |
| `artifacts`    | `id` UUID PK, `aoi_id` UUID, `artifact_type`, `local_path`, `s3_uri`, `sha256_hash`, `created_at` |

Engine string: `DATABASE_URL` env var → defaults to `sqlite:///./data/dev.db`. Postgres+PostGIS image used in docker-compose.

### 7.2 In-memory store

`AOI_STORE: Dict[str, Dict[str, Any]]` in [api/routes/aoi.py](src/jeevn/api/routes/aoi.py) — guarded by `AOI_STORE_LOCK`. This is the authoritative read path for an AOI's report within a single process lifetime.

### 7.3 Advisory report shape (returned by `POST /advisory/agricultural`)

```json
{
  "report_date": "DD/MM/YYYY",
  "aoi_info": { "area_acres", "location", "crop", "state", "latitude", "longitude", "satellite_visit" },
  "components": {
    "field_maps":            { "crop_health_map", "irrigation_health_map", "ndvi_raster" },
    "irrigation_schedule":   { "et0_mm_per_day", "kc", "etc_mm_per_day", "total_water_mm", "irrigation_days", "best_time", "daily_schedule": [...], "terrain": {...} },
    "soil_management":       { "ph", "salinity", "organic_carbon_percent", "organic_carbon_status", "texture", "sand_percent", "silt_percent", "clay_percent", "cec", "cec_status", "water_holding_capacity_mm", "infiltration_rate_mm_h", "soil_moisture_current", "detailed_findings", "recommendations": [...] },
    "growth_yield":          { "yield_potential_kg_per_acre", "vegetation_vigor", "current_growth_stage", "yield_per_acre_kg", "total_yield_kg", "potential_loss_percent", "harvest_status", "limiting_factors": [...] },
    "growth_trajectory":     { "trend", "trend_slope", "current_ndvi", "ndvi_range", "mean_ndvi", "recommendation" },
    "pest_disease_weed":     { "environmental_conditions": {...}, "pests_diseases": [...], "weeds": [...], "summary": { high/moderate/low_risk_count } },
    "fertilizer_management": { "nutrient_requirements": { N/P/K/S/Zn: {current_kg_per_acre,target,gap,status} }, "fertilizer_schedule": { recommended_products: [...] } }
  },
  "environmental_context": { "weather", "soil", "terrain", "growth_stage" },
  "summary":      { "key_findings": [...], "urgent_actions": [...], "recommendations": [...] },
  "data_quality": { "fabricated_fields": [...], "details": {...}, "alerts": [...], "warning": "..." }
}
```

---

## 8. Agronomic math (the science layer)

Pure-Python implementations under [src/jeevn/domain/](src/jeevn/domain/). No I/O, no DB, no HTTP — only inputs in, calculations out.

| Subdomain                            | What it computes                                                                                | Algorithms / sources                                                                                  |
|--------------------------------------|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| [crop/phenology.py](src/jeevn/domain/crop/phenology.py) | Per-crop growth stages, Kc, NDVI ranges, nutrient targets, yield potential                       | Universal FAO-56 database + detailed manual profiles for Apple/Wheat                  |
| [irrigation/et0.py](src/jeevn/domain/irrigation/et0.py) | ET0 (reference evapotranspiration), Kc adjustment by RVI, ETc, soil water deficit               | **Hargreaves-Samani** (FAO-56); Ra from latitude + day-of-year                                        |
| [irrigation/scheduler.py](src/jeevn/domain/irrigation/scheduler.py) | 7-day irrigation schedule (alternate-day drip)                                                  | ETc – rainfall = net irrigation                                                                       |
| [soil/management.py](src/jeevn/domain/soil/management.py) | pH, salinity tier, SOC, CEC, Field Capacity (FC), PWP, AWC, recommendations              | USDA salinity scheme, ICAR thresholds, **Saxton & Rawls (2006) Pedotransfer Functions** for texture-to-volumetric-water conversion |
| [fertilizer/requirements.py](src/jeevn/domain/fertilizer/requirements.py) | N/P/K/S/Zn gap from current vs target (RVI-adjusted)                                            | Target = crop_data × (0.8 + RVI×0.4)                                                                  |
| [fertilizer/schedule.py](src/jeevn/domain/fertilizer/schedule.py) | Translate gaps → specific products (Urea, DAP, SOP, Bone Meal, etc.)                            | Conversion via fertilizer-grade nutrient %                                                            |
| [pest_disease_weed/assessment.py](src/jeevn/domain/pest_disease_weed/assessment.py) | Per-pest risk score 0–100 from temp/humidity/RVI/growth-stage                                   | Weighted: 30% temp + 25% humidity + 25% vegetation density + 20% stage susceptibility                 |
| [growth_yield/projection.py](src/jeevn/domain/growth_yield/projection.py) | Adjusted yield = potential × ∏(1 – reduction_i); harvest readiness                              | Reduction factors keyed on RVI/soil moisture/humidity/stage                                           |
| [growth_yield/monitoring.py](src/jeevn/domain/growth_yield/monitoring.py) | NDVI time-series trend classification                                                            | Linear-regression slope → strong growth / moderate / stagnant / decline                               |

---

## 9. Remote-sensing pipeline

[src/jeevn/remote_sensing/](src/jeevn/remote_sensing/) orchestrated by [pipeline.py](src/jeevn/remote_sensing/pipeline.py):

1. **`aggregate_ndvi(metadata_path)`** — opens the ingest metadata JSON, walks every STAC item, streams the per-band COG with `rasterio.mask` cropped to the AOI geometry, computes mean NDVI/NDWI/NDRE per date, writes a CSV (`data/indices_timeseries_*.csv`) and returns the timeseries.
2. **`compute_raster(metadata_path)`** — takes the latest STAC item, computes a full **NDVI raster** from B04+B08 and a full **NDWI raster** from B03+B11, writes both as GeoTIFFs alongside the metadata JSON. Returns parcel-confidence stats (mean/std/valid-pixel%/composite score).
3. **`analyze_signals(timeseries, raster_path)`** — runs anomaly + texture + SAR-like detections from [analysis/signals.py](src/jeevn/remote_sensing/analysis/signals.py), [detections.py](src/jeevn/remote_sensing/analysis/detections.py), [texture.py](src/jeevn/remote_sensing/analysis/texture.py), [sar.py](src/jeevn/remote_sensing/analysis/sar.py).
4. **`visualization.colorize_raster(raster, palette)`** — turns the float NDVI/NDWI array into a transparent-background PNG that the `/aoi/{id}/maps/{kind}.png` endpoint serves.

Cloud masking helpers (SCL + QA60) live in [masking/cloud.py](src/jeevn/remote_sensing/masking/cloud.py). The canonical NDVI formula is centralized in [ndvi/compute.py](src/jeevn/remote_sensing/ndvi/compute.py) (`ndvi_index(red, nir)`).

---

## 10. UI layout (Streamlit + PDF)

[src/jeevn/ui/app.py](src/jeevn/ui/app.py) provides two tabs:

- **Submit AOI** — folium map with draw + geocoder, plus a raw GeoJSON textarea fallback. On submit:
  1. `POST /aoi` → ingest + raster preproc, capture `aoi_id` + NDVI timeseries.
  2. `POST /advisory/agricultural` → full advisory report (passing the timeseries through).
- **View Report** — 5 sections that mirror the 5 pages of the PDF:
  1. [sections/field_maps.py](src/jeevn/ui/sections/field_maps.py) — fetches real raster PNGs from `/aoi/{id}/maps/{kind}.png`, shows colour-scale legend.
  2. [sections/irrigation_schedule.py](src/jeevn/ui/sections/irrigation_schedule.py) — 7-day table + terrain-aware narrative.
  3. [sections/soil_growth.py](src/jeevn/ui/sections/soil_growth.py) — paired soil + yield metric tiles.
  4. [sections/pest_disease_weed.py](src/jeevn/ui/sections/pest_disease_weed.py) — risk-coloured threat table.
  5. [sections/fertilizer.py](src/jeevn/ui/sections/fertilizer.py) — N/P/K/S/Zn gap table + product schedule.

Then "Generate PDF Report" → [ui/pdf/generator.py](src/jeevn/ui/pdf/generator.py) renders a 5-page A4 PDF via ReportLab, embedding the same NDVI/NDWI PNGs the UI shows.

Shared narrative helpers (terrain → irrigation advice etc.) live in [application/narratives.py](src/jeevn/application/narratives.py) so the UI text and PDF text are byte-identical.

---

## 11. Observability + monitoring

- **Prometheus** ([infrastructure/monitoring/metrics.py](src/jeevn/infrastructure/monitoring/metrics.py)) — `ashi_aoi_created_total`, `ashi_aoi_errors_total`, `ashi_request_duration_seconds` exposed at `/metrics`. Uses a private `CollectorRegistry` so re-imports under Streamlit hot reload don't collide.
- **MLflow** ([infrastructure/monitoring/mlflow.py](src/jeevn/infrastructure/monitoring/mlflow.py)) — opt-in via `MLFLOW_TRACKING_URI`. `log_dummy_run` available for experiment tracking when integrated.

---

## 12. Local dev quick reference

```powershell
# Editable install
pip install -e .

# API
uvicorn jeevn.api.app:app --reload --port 8000 --app-dir src

# UI (separate terminal — needs `pip install -e .` or PYTHONPATH=src)
streamlit run src/jeevn/ui/app.py

# Tests
pytest -v

# Docker Compose (postgres + minio + api)
docker compose -f infra/docker-compose.example.yml up --build -d
```

Full walkthrough: [QUICKSTART.md](QUICKSTART.md). Setup notes: [README.md](README.md).

---

## 13. Where to look for…

| You want to…                                               | Open                                                                                                  |
|------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| Add a new HTTP endpoint                                     | [src/jeevn/api/routes/](src/jeevn/api/routes/) + [src/jeevn/api/schemas/](src/jeevn/api/schemas/)     |
| Change how the advisory report is assembled                 | [src/jeevn/application/advisory_service.py](src/jeevn/application/advisory_service.py)                |
| Tweak agronomic math (ET0, fertilizer gap, pest risk score) | [src/jeevn/domain/](src/jeevn/domain/)                                                                |
| Add or swap an external data source                         | [src/jeevn/infrastructure/data_sources/](src/jeevn/infrastructure/data_sources/)                      |
| Touch NDVI / NDWI computation or cloud masking              | [src/jeevn/remote_sensing/](src/jeevn/remote_sensing/)                                                |
| Add a Streamlit section to the report                       | [src/jeevn/ui/sections/](src/jeevn/ui/sections/) + plug in [src/jeevn/ui/app.py](src/jeevn/ui/app.py) |
| Change the PDF layout                                       | [src/jeevn/ui/pdf/generator.py](src/jeevn/ui/pdf/generator.py)                                        |
| Migrate / add DB tables                                     | [src/jeevn/infrastructure/db/models.py](src/jeevn/infrastructure/db/models.py)                        |
| Add fallback defaults                                       | [src/jeevn/infrastructure/pseudo_satellite.py](src/jeevn/infrastructure/pseudo_satellite.py)          |

Each top-level folder has its own `OVERVIEW.md` with file-by-file detail.
