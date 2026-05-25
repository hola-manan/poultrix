# `src/jeevn/api/` — FastAPI HTTP layer

The thin HTTP surface of the application. Holds the FastAPI instance, route handlers, and Pydantic request/response schemas. No agronomic math, no remote-sensing logic — those calls live in [application/](../application/), [domain/](../domain/), [ingestion/](../ingestion/), and [remote_sensing/](../remote_sensing/).

## Tech / runtime

- **FastAPI** for the HTTP framework, **Pydantic v2** for schemas (`ConfigDict`).
- Mounted as ASGI on port `8000` by default. Started with `uvicorn jeevn.api.app:app --reload --port 8000 --app-dir src`.
- Hosts a sub-app at `/metrics` (Prometheus) when `prometheus_client` is importable.
- Initialises DB tables on the FastAPI `startup` event when `sqlalchemy` is importable.

## Files

### [`app.py`](app.py)
The FastAPI application entrypoint.

- Constructs `app = FastAPI(title="Jeevn - MVP API", version="1.0.0")`.
- Mounts the two routers (`aoi_router`, `advisory_router`).
- Mounts `/metrics` ASGI sub-app when monitoring is available.
- Re-exports `AOI_STORE` + `AOI_STORE_LOCK` from `routes.aoi` so the tests can clear in-memory state via `from jeevn.api.app import ...`.
- Wraps DB and metrics imports in try/except — the app starts cleanly even when those optional integrations are missing.

### [`routes/aoi.py`](routes/aoi.py)
AOI ingestion + report endpoints. Owns the **primary in-memory store**.

- `AOI_STORE: Dict[str, Dict]` + `AOI_STORE_LOCK = threading.Lock()` — process-local cache, authoritative for read.
- `GET /health` → `{"status": "ok"}`.
- `POST /aoi`:
  - **In:** `AOIRequest` — `name`, `geojson` (FeatureCollection), optional `start_date`, `end_date`.
  - **Steps:** mints UUID → writes to `AOI_STORE` and (best-effort) to the `aois` DB table → calls `ingestion.sentinel.ingest(...)` → if metadata produced, calls `remote_sensing.aggregate_ndvi(...)` + `remote_sensing.compute_raster(...)` + `remote_sensing.analyze_signals(...)`. All optional integrations degrade gracefully (catch + log + continue).
  - **Out:** `AOIResponse` — `aoi_id`, `metadata_path`, `ndvi_csv`, `ndvi_timeseries`, `ndvi_raster`, `ndwi_raster`, `parcel_confidence`, `raster_quality`, `anomalies`.
  - Increments `aoi_created_counter` / `aoi_error_counter` Prometheus counters when monitoring is available.
- `GET /aoi/{aoi_id}/report` → `ReportResponse` (read from `AOI_STORE`; 404 if absent).
- `GET /aoi/{aoi_id}/maps/{kind}.png` where `kind ∈ {ndvi, ndwi}`:
  - Loads the GeoTIFF raster path from `AOI_STORE[aoi_id]["report"][f"{kind}_raster"]`.
  - Calls `remote_sensing.visualization.load_raster_data` then `colorize_raster` to produce a PNG with transparency outside the AOI polygon.
  - 404 if no real raster was produced for this AOI (caller renders an "unavailable" notice rather than substituting synthetic imagery).

### [`routes/advisory.py`](routes/advisory.py)
Thin HTTP wrapper over `application.advisory_service`.

- `POST /advisory/agricultural`:
  - **In:** `AgriculturalAdvisoryRequest` — `name`, `latitude`, `longitude`, optional `area_acres` (default 0.421), `crop_type` ("apple"), `sowing_date`, `ndvi_timeseries`, `location_name`.
  - **Steps:** calls `AgriculturalReportGenerator.generate_report(...)` which fans out to weather/soil/terrain/geocoding fetchers, runs all domain calculators, and assembles the full report dict.
  - **Out:** `AgriculturalAdvisoryResponse` — `advisory_id` (fresh UUID, not persisted), `status` (`"completed"` / `"failed"`), `report` (full advisory tree — see Section 7.3 in [../../../ARCHITECTURE.md](../../../ARCHITECTURE.md)), `error`.
- `GET /advisory/agricultural/{advisory_id}` — stub; advisory persistence is not implemented yet.
- `POST /advisory/health-check` — reports whether the advisory module import succeeded.

### [`schemas/aoi.py`](schemas/aoi.py)
Pydantic models for the AOI endpoints. `AOIRequest` carries an example payload through `model_config = ConfigDict(json_schema_extra=...)` so the auto-generated OpenAPI/Swagger UI at `/docs` shows a copy-paste-ready sample.

### [`schemas/advisory.py`](schemas/advisory.py)
Pydantic models for the advisory endpoints. Defaults bake in `area_acres=0.421` and `crop_type="apple"` to match the [`farmonaut_technologies_private_limited_jeevnaireport.pdf`](../../../farmonaut_technologies_private_limited_jeevnaireport.pdf) reference report.

### `routes/__init__.py`, `schemas/__init__.py`, `__init__.py`
Empty package markers.

## Calling conventions

- All endpoints return JSON except `/aoi/{aoi_id}/maps/{kind}.png` (image/png) and `/metrics` (Prometheus text).
- Errors raise `fastapi.HTTPException` with appropriate status codes (`400` bad kind, `404` not found, `500` unexpected, `503` advisory module unavailable).
- Concurrency: `AOI_STORE` mutations are always inside `with AOI_STORE_LOCK:`. The `/aoi` POST holds the lock only for the dictionary write — the long-running ingest + raster work happens outside the lock so concurrent submissions don't block each other.

## Tests covering this layer

- [tests/api/test_api.py](../../../tests/api/test_api.py) — `TestClient`-driven tests for `/health`, `/aoi`, and thread-safety of `AOI_STORE`.
