# `tests/` — Pytest suite

Mirrors the `src/jeevn/` package tree so the test for `src/jeevn/X/Y.py` lives at `tests/X/test_Y.py`. Discovery + path setup are handled by the repo-root [`conftest.py`](../conftest.py) which prepends `src/` to `sys.path`.

## Tech

- **pytest** as the runner. Config in [`pyproject.toml`](../pyproject.toml) (`[tool.pytest.ini_options]`): `testpaths = ["tests"]`, `python_files = ["test_*.py"]`, `addopts = "-v --tb=short"`.
- **fastapi.testclient.TestClient** for HTTP-level integration tests of the API.
- No external network in CI — tests that would otherwise call live APIs (SoilGrids, Nominatim, Open-Meteo, Planetary Computer) monkeypatch the adapters or skip.

Run with:

```powershell
pytest -q              # quiet, all tests
pytest -v              # verbose
pytest tests/api/      # just the API layer
pytest -k stub         # name filter
```

## Layout

```
tests/
├── api/
│   └── test_api.py                       # /health, POST /aoi, AOI_STORE thread-safety
├── infrastructure/
│   ├── data_sources/
│   │   ├── test_aoi.py                   # composer: fabrication tracking, alerts hoisting
│   │   ├── test_soil.py                  # SoilGrids fetch + texture classifier + WHC/infiltration tables
│   │   ├── test_terrain.py               # Horn 1981 kernel + 3-tier fallback chain
│   │   └── test_weather.py               # Open-Meteo URL params + soil-moisture aggregation
│   └── db/
│       └── test_models.py                # AOI / IngestJob / Artifact round-trip via SessionLocal
├── ingestion/
│   └── test_ingest_stub.py               # runner.stub_ingest metadata structure
├── remote_sensing/
│   ├── test_aggregate_ndvi.py            # full timeseries assembly from metadata JSON
│   └── analysis/
│       ├── test_detections.py            # disease_patch / fertilizer_issue / weeds_guidance / yield_proxy
│       ├── test_indices.py               # ndvi / ndwi / evi / savi / ndre / gci / msi vector formulas
│       ├── test_sar.py                   # dB↔linear, polarization difference, moisture index
│       ├── test_signals.py               # z-score / persistent_stress / water+nutrient_stress_score
│       └── test_texture.py               # local_std + local_entropy (scipy + fallback paths)
└── __init__.py
```

## Test coverage notes

- **API layer** ([tests/api/test_api.py](api/test_api.py)) — uses `TestClient(app)`. Includes a `test_aoi_store_thread_safety` test that spawns multiple threads writing to `AOI_STORE` to verify the lock holds.
- **Infrastructure / data sources** — adapters are tested with `monkeypatch.setattr` over `requests.get` / `requests.post` so the actual network endpoints aren't hit. Coverage includes the fabricated-field flag propagation, alert emission for built-up land, and the Horn 1981 slope+aspect math against hand-computed expected values.
- **Domain layer** — currently exercised mostly through the [scripts/test_agricultural_report.py](../scripts/test_agricultural_report.py) integration probe rather than per-calculator unit tests. Adding focused tests for the irrigation / fertilizer / pest math is on the backlog.
- **Remote sensing** — `tests/remote_sensing/test_aggregate_ndvi.py` writes a tiny metadata JSON to disk and checks the timeseries shape; the analysis tests are pure-numpy unit tests against the formulas in [src/jeevn/remote_sensing/analysis/](../src/jeevn/remote_sensing/analysis/).

## Adding a new test

1. Mirror the source file's path: `src/jeevn/foo/bar.py` → `tests/foo/test_bar.py`.
2. Don't add a `sys.path` shim — the root `conftest.py` already handles `src/` resolution.
3. Mock external HTTP via `monkeypatch.setattr` over the `requests` callable, not the adapter itself, so the full code path under test runs.
4. Tests that need a temp directory should use `tmp_path` rather than writing into the `data/` folder (which is the runtime output area).
