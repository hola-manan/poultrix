# TASKS

Single shared task list for this project. Read this first when starting work.
Both human contributors and AI agents (Claude, Cursor, Aider, etc.) edit this
file. It is the persistent counterpart to whatever ephemeral in-session
todo-tracking an agent uses.

---

## Pattern

- Each task is a `### N. Short title` block followed by a small structured
  body. Number N is just an identifier — order does not imply priority;
  the section it sits in does.
- `Status:` is one of `pending`, `in-progress`, `blocked`, `done`.
- New work goes into `## Backlog` first; promote to `## Up Next` only when
  prioritised by the human.
- The agent or human picking up a task sets `Status: in-progress`, adds an
  `Owner:` line (`<agent-or-human>-<YYYY-MM-DD>`), and moves the block to
  `## In Progress`.
- When marking done: add `Resolved: <short-sha> — <YYYY-MM-DD>`, move the
  block under `## Done`, and trim `## Done` to the most recent ~10 items.
- **Update this file in the same commit as the code change** so the task
  state and the code state move together.
- Don't pick a task whose `Status: in-progress` is held by someone else
  without coordinating with the human first.

---

## In Progress

*(currently being worked on — set Owner and move blocks here when starting)*

(none)

---

## Up Next

*(prioritised — top item is the next one to pick up)*

### 1. Replace hardcoded soil properties with ISRIC SoilGrids
- **Status:** pending
- **Why:** All 8 soil values (pH, OC, texture, bulk density, WHC, infiltration,
  EC, soil_moisture) are currently hardcoded regional-template values in
  `src/jeevn/infrastructure/pseudo_satellite.py`. SoilGrids gives global
  250 m real data via a free anonymous REST API at
  `rest.isric.org/soilgrids/v2.0/properties/query`. Replaces ~5 of the 8.
- **Acceptance:**
  - [ ] New `SoilGridsClient` class (or equivalent) in
        `src/jeevn/infrastructure/data_sources/soil.py`, replacing the
        current stub that always returns `make_default_soil`.
  - [ ] Returns pH, SOC, sand/silt/clay (and a derived USDA texture class),
        bulk density, CEC at 0–30 cm depth.
  - [ ] Falls back to `pseudo_satellite.make_default_soil` with
        `_fabricated=True` on network failure.
  - [ ] WHC + infiltration are derived from texture class via a lookup
        table — not hardcoded numbers.
  - [ ] Per-property fabricated tracking: replace whole-or-nothing
        `_fabricated: True` with `_fabricated_fields: {ph: false, ec: true,
        ...}` so the data-quality banner can be granular.
  - [ ] Unit-conversion tests: `phh2o` (×10) → pH, `soc` (dg/kg) → %,
        `bdod` (cg/cm³) → g/cm³.
- **Files:**
  - `src/jeevn/infrastructure/data_sources/soil.py`
  - `src/jeevn/domain/soil/management.py` (read per-property flags)
  - `src/jeevn/infrastructure/pseudo_satellite.py` (`FABRICATED_FIELD_DESCRIPTIONS`)
  - `src/jeevn/application/advisory_service.py` (propagate granular flags)

### 2. Add Open-Meteo soil moisture to weather fetch
- **Status:** pending
- **Why:** The one dynamic soil property is 100% hardcoded today. Open-Meteo's
  `soil_moisture_0_to_7cm` is hourly, free, anonymous — one extra param to
  the call we already make.
- **Acceptance:**
  - [ ] Add `soil_moisture_0_to_7cm` to the `hourly=` param in `weather.py`.
  - [ ] Average the last 24 hours and propagate as
        `soil["properties"]["soil_moisture_current"]`.
  - [ ] `_fabricated=False` on success; `True` only on Open-Meteo failure.
- **Files:**
  - `src/jeevn/infrastructure/data_sources/weather.py`
  - `src/jeevn/infrastructure/data_sources/aoi.py`

### 3. Fix the 3 pre-existing failing tests
- **Status:** pending
- **Why:** `test_yield_proxy`, `test_weeds_guidance`, `test_nutrient_stress_score`
  have been failing since before the restructure (test-vs-impl signature
  drift, not real bugs).
- **Acceptance:** All 39 tests pass under `pytest tests/`.
- **Files:** see `docs/known_issues.md` for the exact mismatches.

---

## Blocked

*(waiting on someone or something — note the blocker)*

(none)

---

## Backlog

*(known future work, not yet prioritised — move to `## Up Next` when ready)*

### 4. NISAR L-band soil moisture integration
- **Status:** pending (backlog)
- **Why:** Sentinel-1 C-band soil-moisture retrievals are degraded under
  crop canopy; NISAR's L-band sees through it. NRSC has already published
  100 m NISAR SM maps covering the Indo-Gangetic plain (the demo region).
  Designed precisely for cropland.
- **Acceptance:**
  - [ ] New adapter using the `asf_search` Python library
        (`pip install asf_search`).
  - [ ] Earthdata Login configured via env vars (`EARTHDATA_USER`,
        `EARTHDATA_PASS`); document in `.env.example`.
  - [ ] When the latest NISAR pass over the AOI is within ~14 days, use it;
        otherwise fall back to Open-Meteo SM (task #2).
  - [ ] Report explicitly states the source: "Sentinel-2 capture / NISAR
        pass YYYY-MM-DD / Open-Meteo modelled".
- **Defers:** SAR-as-truth Open-Meteo calibration → task #6.

### 5. Bundle ISRIC global salinity raster for real EC
- **Status:** pending (backlog)
- **Why:** No free REST source exists for salinity. The ISRIC global salinity
  GeoTIFF (~50–200 MB at 1 km) can be bundled and sampled with rasterio.
  Closest path to "real EC" without paid APIs.
- **Acceptance:**
  - [ ] Download and commit the raster under `data/static/` (set up Git LFS
        if file size >100 MB — coordinate with human before committing
        large binary).
  - [ ] Sampling function in `soil.py` that returns EC at the AOI centroid.
  - [ ] Removes `salinity` from `data_quality.fabricated_fields` when sample
        is in raster coverage.

### 6. NISAR ↔ Open-Meteo SM calibration (research-grade)
- **Status:** pending (backlog, depends on #4)
- **Why:** Once paired NISAR + Open-Meteo SM observations accumulate per AOI,
  fit a per-AOI bias correction (linear or quantile-mapping). Lets us serve
  near-NISAR-quality SM even on days without a satellite pass.
- **Acceptance:**
  - [ ] Per-AOI calibration coefficients persisted (DB schema change).
  - [ ] Fit triggered once ≥5 paired observations exist for an AOI.
  - [ ] Leave-one-out cross-validation report saved with the calibration.
  - [ ] Advisory output annotates whether the SM value is raw Open-Meteo,
        calibrated Open-Meteo, or direct NISAR.

### 7. DEM-derived slope + aspect for the AOI
- **Status:** pending (backlog)
- **Why:** Slope affects drainage + irrigation choices; aspect affects
  insolation. Free via OpenTopography REST against Copernicus DEM 30 m.
- **Acceptance:**
  - [ ] New adapter `data_sources/terrain.py`.
  - [ ] Returns mean slope (%) and mean aspect (compass degrees) over the
        AOI polygon.
  - [ ] Wired into the irrigation_schedule narrative in `soil_growth.py`
        and `pdf/generator.py`.

---

## Done

*(most recent ~10 — older entries can be trimmed)*

### Move dev-smoke scripts out of project root
- **Resolved:** 441578e — 2026-05-14
- One-liner: `test_boundary.py` + `test_network_api.py` → `scripts/dev_smoke/`.

### Initial commit — Jeevn MVP published to public repo `hola-manan/poultrix`
- **Resolved:** 11c7606 — 2026-05-14
- One-liner: 11-step restructure into the `src/jeevn/` layered layout
  (`domain/application/infrastructure/remote_sensing/ingestion/api/ui/`);
  real Sentinel-2 NDVI/NDWI rasters from B04/B08 + B03/B11 with
  cross-resolution reprojection, cropped to the AOI polygon and served via
  `/aoi/{id}/maps/{kind}.png`; STAC search window decoupled from user's
  crop sowing dates; `data_quality.fabricated_fields` propagation; field
  maps endpoint replaces synthetic client-side noise.

---

## Notes for AI agents

- **Read this file first.** It tells you what's prioritised and what
  acceptance looks like.
- **Read `docs/known_issues.md`** for previously-investigated test failures
  and design notes that shouldn't be re-litigated.
- **Read `README.md` and `QUICKSTART.md`** for launch commands and tooling.
- Run `git log --oneline -10` before starting any task — recent commits are
  the best context for what just changed.
- Update this file *in the same commit* as the code change. Don't leave
  it stale.
- When picking a task, set `Status: in-progress`, add `Owner:` (`<your name
  or model>-<YYYY-MM-DD>`), and move the block to `## In Progress`.
- When closing a task, the commit message should briefly say which task
  number it resolves (`Resolves task #1` or similar).
- Don't `git add .` blindly — review what's staged before committing.
- Public repo: never commit `.env`, API keys, third-party branded PDFs,
  or large binaries without explicit human approval.
