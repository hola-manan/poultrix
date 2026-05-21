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
- When marking done: add `Resolved: <YYYY-MM-DD>` and move the block under
  `## Done`. The commit message should contain `Resolves task #N` so the
  resolving commit is findable via `git log --grep "Resolves task #N"`.
  Trim `## Done` to the most recent ~10 items.
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

(none — backlog items below; promote one here when prioritised)

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

### 3. Fix the 3 pre-existing failing tests
- **Resolved:** 2026-05-21
- One-liner: Updated `test_yield_proxy`, `test_weeds_guidance`,
  `test_nutrient_stress_score` to match each function's current
  contract. Suite is now fully green (82 passing, 0 failing) — first
  time since the restructure. Functions left untouched since the rest
  of the codebase already relies on their current return shapes; only
  the stale test expectations needed correcting.
  `docs/known_issues.md` rewritten to a generic skeleton with these
  three moved to a Resolved section.

### 2. Add Open-Meteo soil moisture to weather fetch
- **Resolved:** 2026-05-21
- One-liner: `weather.py` now also requests hourly `soil_moisture_0_to_7cm`
  and surfaces a last-24-hours mean (m³/m³). The AOI composer converts
  it to a fraction-of-field-capacity using a USDA-NRCS field-capacity
  lookup keyed on the real SoilGrids texture, then writes both the
  fraction and the raw m³/m³ into `soil.properties`. Per-property
  fabricated flag for `soil_moisture_current` flips to False when
  Open-Meteo returned a value. Live-verified at the default farmland
  AOI: 0.307 m³/m³ raw → 1.0 fraction (saturated, recent rain). With
  this in, the only persistently-fabricated soil property is
  `soil.ec` (deferred — no free salinity REST source).

### 1. Replace hardcoded soil properties with ISRIC SoilGrids
- **Resolved:** 2026-05-14
- One-liner: SoilGrids v2.0 REST adapter in `data_sources/soil.py` now
  fetches real pH, SOC, sand/silt/clay, bulk density, CEC at 0–30 cm
  (depth-weighted) for the AOI centroid. Texture classified from real
  sand/silt/clay via USDA triangle; WHC + infiltration looked up from
  texture. Per-property `_fabricated_fields` tracking replaces the old
  whole-dict `_fabricated` flag — `data_quality.fabricated_fields` now
  shows e.g. `soil.ec`, `soil.soil_moisture_current` only for the
  properties that are still synthetic. Falls back to the regional
  template (everything fabricated) on network failure. 28 new tests pass.
  Live-verified against Ganganagar farmland: hardcoded OC was 0.14 %;
  SoilGrids returns ~0.56 % depth-weighted (4× correction). Also bundled:
  - Built-up-land detection: when SoilGrids returns HTTP 200 with all-null
    means (AOI centroid is in their urban land mask), the report now
    surfaces a top-level red alert via `data_quality.alerts` instead of
    silently falling back. The alert tells the user the polygon needs to
    be redrawn over actual cropland (per the no-spiral-substitution rule).
  - Weather fix: Open-Meteo archive-api end_date/start_date now clamped
    to today before the request, removing the 400 Bad Request that fired
    when the user's crop dates extended into the future.
  - Dev utility: `scripts/dev_smoke/find_farmland.py` for probing
    SoilGrids coverage around a region.

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
