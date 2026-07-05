# `scripts/` — Dev helpers, smoke tests, raster prep

One-shot utilities. Not part of the import-time runtime; they're invoked directly from the shell when needed.

## Top-level scripts

### [`dev_up.ps1`](dev_up.ps1) / [`dev_down.ps1`](dev_down.ps1)
PowerShell wrappers around `docker compose -f infra/docker-compose.example.yml up --build -d` / `down -v`. Print the published URLs (API on `:8000`, Postgres on `:5432`, MinIO console on `:9001`).

### [`e2e_smoke.py`](e2e_smoke.py)
End-to-end probe against a running API.

- Reads `API_URL` env (default `http://localhost:8000`).
- Hits `/health`, `POST /aoi` with a 1°×1° sample polygon, `GET /aoi/{id}/report`, then verifies the metadata JSON exists on disk and is valid.
- Returns exit code 0 / 1. Useful as a CI gate after `dev_up.ps1`.

### [`test_agricultural_report.py`](test_agricultural_report.py)
Full advisory pipeline probe **without** going through the API. Calls `application.advisory_service.generate_agricultural_report_from_aoi` directly with the same `(29.9, 73.9)` Ganganagar coordinates the reference PDF uses, simulates a 30-day NDVI growth curve, and prints the resulting irrigation/soil/yield/pest/fertilizer numbers. Saves the full JSON to `/tmp/agricultural_report_test.json` (NB: hard-coded Unix path — won't work on Windows as-is).

## `dev_smoke/` — narrow-focus tools

### [`dev_smoke/build_dem_clip.py`](dev_smoke/build_dem_clip.py)
**One-shot raster prep.** Builds [data/static/dem_india.tif](../data/static/dem_india.tif) — the fallback DEM used by [src/jeevn/infrastructure/data_sources/terrain.py](../src/jeevn/infrastructure/data_sources/terrain.py).

- Source: NOAA ETOPO 2022 30 arc-sec global surface-elevation GeoTIFF (`https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/30s/30s_surface_elev_gtif/ETOPO_2022_v1_30s_N90W180_surface.tif`).
- Uses **GDAL `/vsicurl/`** + HTTP-range reads so only the India window bytes (~10–50 MB) are pulled rather than the full 1.58 GB.
- Quantises float32 metres → int16 metres (Everest is 8849 m, deepest trench ~−11000 m — both fit), DEFLATE-compressed, tiled.
- India bounding box: `(67, 5, 99, 38)` degrees.
- Requires: `rasterio` with GDAL ≥ 3.

### [`dev_smoke/build_salinity_clip.py`](dev_smoke/build_salinity_clip.py)
**One-shot raster prep.** Builds [data/static/salinity_india.tif](../data/static/salinity_india.tif) — the bundled ISRIC GSSmap 2016 raster used for real EC / salinity-class data.

- Source: ISRIC public salinity tiles (`https://files.isric.org/public/global_soil_salinity/salmap2016/`). License: CC BY 4.0.
- Downloads 15 tiles (3 rows × 5 cols) into `data/cache/isric_salinity_2016/` with resume support (range request to a `.part` file, 2/4/8/16-second backoff on transient failures).
- Mosaics with `rasterio.merge.merge(bounds=INDIA_BBOX)` so only the India window is loaded.
- DEFLATE-compressed output (`predictor=2` for integer DEMs / class rasters).

### [`dev_smoke/build_shc_district_npk.py`](dev_smoke/build_shc_district_npk.py)
**One-shot data prep.** Builds [data/static/shc_district_npk.csv](../data/static/shc_district_npk.csv) + [shc_village_npk.csv.gz](../data/static/shc_village_npk.csv.gz) — the India Soil Health Card N/P/K lookup tables used by [soil_nutrients.py](../src/jeevn/infrastructure/data_sources/soil_nutrients.py).

- Input: the data.gov.in **"Soil Nutrient Analysis"** bulk CSV export (long-format, village-level, ~10.8M rows). Pass its path as arg1 or set `SHC_LOCAL_CSV`.
- Streams once (no full load), aggregates macro N/P/K High/Medium/Low sample counts per village, rolls up to district (sample-count-weighted), writes both tables (village gzipped). Pure stdlib — no rasterio/GDAL.
- Exits non-zero without writing on failure (never ships fabricated district data).

### [`dev_smoke/find_farmland.py`](dev_smoke/find_farmland.py)
Probe SoilGrids at 24 candidate points around `(29.92, 73.88)` (Sri Ganganagar town centre, which sits in built-up land that SoilGrids flags as no-data). Sweeps 8 cardinal+diagonal directions × 3 distances (10/15/20 km), prints which points return real pH/SOC/sand/silt/clay. Used to pin down the default test coordinates the UI ships with.

### [`dev_smoke/test_network_api.py`](dev_smoke/test_network_api.py)
Manual sanity check for the **real** ingest path (Planetary Computer STAC + COG streaming):

- Hard-coded ~28 m × ~70 m polygon near `(73.865, 29.925)`.
- Calls `jeevn.ingestion.sentinel.ingest(...)` then `jeevn.remote_sensing.analysis.confidence.compute_raster(...)`.
- Prints products-found count, metadata path, NDVI/NDWI raster paths, and `raster_quality` dict.

### [`dev_smoke/test_boundary.py`](dev_smoke/test_boundary.py)
Standalone probe for the AOI-outline drawing in [src/jeevn/remote_sensing/visualization.py](../src/jeevn/remote_sensing/visualization.py). Generates a synthetic 10×10 NaN-bordered array, upscales it, draws a white boundary via PIL's erosion/subtract trick, and saves to `data/test_boundary.png` for visual inspection.

## Conventions

- Scripts in [`dev_smoke/`](dev_smoke/) are **manual tools**, not part of automated test runs. They can be slow (multi-MB downloads) and depend on optional dependencies (rasterio, GDAL).
- Output of the raster-prep scripts lives under [data/static/](../data/static/) and is checked into git so a fresh clone has the fallback data immediately.
- The cached source tiles under `data/cache/` can be deleted after a successful clip to reclaim disk; the gitignore exception only covers `data/static/`.
