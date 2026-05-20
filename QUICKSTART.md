# Quick Start Guide - Jeevn MVP

## Prerequisites

- Python 3.11+
- Docker Desktop (for Docker Compose setup)
- Git

## Option 1: Local Development Setup (Recommended for Testing)

### Step 1: Create Virtual Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate
```
    
### Step 2: Install Dependencies

```powershell
pip install -r requirements.txt
```

### Step 3: Create `.env` File

```powershell
# Copy the example config
Copy-Item .env.example .env
```

For local testing, the defaults are fine. You can optionally set:
```
DATABASE_URL=sqlite:///./data/dev.db
SENTINEL_USER=  # Leave empty for stub ingest
SENTINEL_PASS=  # Leave empty for stub ingest
DOWNLOAD_PRODUCTS=0
```

### Step 4: Initialize Database

```powershell
# Database will auto-init on first API call, or manually:
python -c "import sys; sys.path.insert(0, 'src'); from jeevn.infrastructure.db import connection as db; db.init_db(); print('✅ Database initialized')"
```

### Step 5: Make the `jeevn` package importable

Pick one of these (the first is recommended — set once and forget):

```powershell
# Option A (recommended): editable install — adds jeevn to your venv permanently
pip install -e .
```

```powershell
# Option B: set PYTHONPATH each session (do this in BOTH terminals before launching)
$env:PYTHONPATH = "$(Get-Location)\src"
```

### Step 6: Run the API

```powershell
# Terminal 1 - API Server
uvicorn jeevn.api.app:app --reload --port 8000 --app-dir src
```

`--app-dir src` adds `src/` to uvicorn's import path, so this works even
without the editable install or `PYTHONPATH` from Step 5.

You should see:
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 7: Run the Streamlit UI (Optional)

```powershell
# Terminal 2 - Streamlit UI (requires Step 5 — Streamlit has no --app-dir flag)
streamlit run src/jeevn/ui/app.py
```

If you skipped Step 5 you'll get `ModuleNotFoundError: No module named 'jeevn'`
because Streamlit only puts the script's parent directory on `sys.path`, not
the project's `src/`. Run `pip install -e .` (Option A) or set
`$env:PYTHONPATH = "$(Get-Location)\src"` in this terminal first.

The UI will open at `http://localhost:8501`

---

## Option 2: Docker Compose Setup (Full Stack)

### Step 1: Start Services

```powershell
# Using the helper script (Windows)
.\scripts\dev_up.ps1
```

Or manually:
```powershell
docker compose -f infra/docker-compose.example.yml up --build -d
```

This starts:
- **API**: http://localhost:8000
- **Postgres**: localhost:5432 (jeevn/jeevn)
- **MinIO**: http://localhost:9001 (minioadmin/minioadmin)

### Step 2: Stop Services

```powershell
.\scripts\dev_down.ps1
```

---

## Testing the System

### Option 1: Run All Unit Tests

```powershell
# From repo root (venv activated)
pytest -v

# Run only new tests
pytest tests/test_api.py tests/test_models.py -v
```

### Option 2: Quick Manual API Test

```powershell
# Terminal with API running
# Check health
curl http://localhost:8000/health

# Create an AOI
$payload = @{
    name = "Test AOI"
    geojson = @{
        type = "FeatureCollection"
        features = @(@{
            type = "Feature"
            geometry = @{
                type = "Polygon"
                coordinates = @(@(
                    @(0.0, 0.0),
                    @(1.0, 0.0),
                    @(1.0, 1.0),
                    @(0.0, 1.0),
                    @(0.0, 0.0)
                ))
            }
        })
    }
    start_date = "2024-01-01"
    end_date = "2024-12-31"
} | ConvertTo-Json -Depth 10

Invoke-WebRequest -Uri http://localhost:8000/aoi `
    -Method POST `
    -Headers @{"Content-Type"="application/json"} `
    -Body $payload | Select-Object -ExpandProperty Content | ConvertFrom-Json
```

### Option 3: Use Streamlit UI

1. Start API: `uvicorn jeevn.api.app:app --reload --port 8000 --app-dir src`
2. Start UI: `streamlit run src/jeevn/ui/app.py`
3. Click "Check API Health" in the sidebar
4. Fill in AOI details and submit

---

## What's in Place ✅

- ✅ Fixed UUID type mismatch (api/app.py)
- ✅ Fixed circular imports (ingest/, preproc/)
- ✅ Thread-safe AOI store with locks
- ✅ `.env.example` for configuration
- ✅ `tests/test_models.py` - Database model tests
- ✅ `tests/test_api.py` - API endpoint and thread-safety tests
- ✅ Database models (AOI, IngestJob, Artifact)
- ✅ FastAPI backend with graceful fallbacks
- ✅ Streamlit UI
- ✅ Docker Compose setup (postgres + minio)

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'jeevn'"
- Make sure you're in the repo root directory
- The `src/` layout requires `--app-dir src` for uvicorn, or `pip install -e .`
- For pytest, the project's root `conftest.py` adds `src/` to sys.path

### "Database locked" error
- SQLite has concurrency limits. For production, use PostgreSQL
- For local testing, this is normal with multiple workers

### "Connection refused" to localhost:5432
- Postgres is only available via Docker Compose
- For local testing, use SQLite (default)

### "GDAL/rasterio" import errors
- These are optional dependencies used by preprocessing
- The API gracefully skips preprocessing if unavailable
- For full functionality: `pip install gdal rasterio`

---

## Next Steps

1. **Run tests first**: `pytest -v` (catches any import/setup issues)
2. **Test API locally**: `uvicorn api.app:app --reload` + quick curl test
3. **Run full stack**: Docker Compose for a complete setup
4. **Explore**: Use Streamlit UI to submit AOIs and see results

Questions? Check [README.md](README.md) for more details.
