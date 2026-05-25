# `infra/` — Infrastructure & deployment config

Container orchestration for local development and demo deployments. Production deployment (cloud-native, secrets management, scaling) is not in scope yet.

## Files

### [`docker-compose.example.yml`](docker-compose.example.yml)
Three-service compose file. Brought up via [scripts/dev_up.ps1](../scripts/dev_up.ps1) or directly with `docker compose -f infra/docker-compose.example.yml up --build -d`.

#### `api`
- Built from the repo-root [Dockerfile](../Dockerfile) (Python 3.11-slim + GDAL system packages + pip-installed `requirements.txt`).
- Runs `uvicorn jeevn.api.app:app --host 0.0.0.0 --port 8000`.
- Publishes `8000:8000`.
- `PYTHONPATH=/app/src` set in the image so the `src/` layout is importable without an editable install.
- Mounts `./data` → `/app/data` so generated artifacts (metadata JSON, NDVI rasters, CSV timeseries) persist across container restarts.
- `DATABASE_URL=postgresql://jeevn:jeevn@postgres:5432/ashi` — points at the sibling Postgres service.

#### `postgres`
- Image: `postgis/postgis:15-3.3` — Postgres 15 with the PostGIS extension installed. Currently the schema doesn't use PostGIS types (geometries are stored as JSON), but the image keeps the option open for a future migration.
- Credentials: `jeevn / jeevn / ashi`.
- Published `5432:5432`.
- Volume `postgres_data` for data persistence.

#### `minio`
- Image: `minio/minio:latest`.
- Credentials: `minioadmin / minioadmin`.
- API on `9000`, console UI on `9001`.
- Volume `minio_data`.
- The `MINIO_ENDPOINT` / `MINIO_BUCKET` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` env vars on the API side would target this service once an S3-backed artifact store lands; currently the `Artifact` model carries an `s3_uri` column but the code path writes to local `data/` only.

#### Networking
A bridge network `ashi` is declared so the API can reach `postgres:5432` and (eventually) `minio:9000` by service name. No host-only services; everything intentionally exposed on `localhost`.

## What's not here yet

- **TLS / reverse proxy** — uvicorn is exposed directly; behind a real deployment this would sit behind nginx/Caddy/traefik.
- **CI/CD** — no GitHub Actions / GitLab pipeline definitions are checked in. The [docs/agents/pipeline.json](../docs/agents/pipeline.json) describes a clean-room reimplementation pipeline, not CI.
- **Secrets management** — credentials are hard-coded in the example compose file; a `.env`-fed variant is a 5-line change but not committed.
- **Scaling / replicas** — single instance of each service; the in-memory `AOI_STORE` in the API would not survive scale-out and is a known limitation.

## Operational notes

- `docker compose ... down -v` (what [scripts/dev_down.ps1](../scripts/dev_down.ps1) runs) **deletes** the `postgres_data` and `minio_data` volumes. Drop the `-v` to preserve state between restarts.
- The API container image bakes in `gcc`, `gdal-bin`, and `libgdal-dev` at build time — required by rasterio. Adds ~250 MB to the image but eliminates the optional-rasterio degrade path inside the container.
- First boot reads `Base.metadata.create_all(engine)` on the FastAPI startup event so the Postgres tables are auto-created.
