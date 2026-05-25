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

---

## Done

*(most recent ~10 — older entries can be trimmed)*

### 7. DEM-derived slope + aspect for the AOI
- **Resolved:** 2026-05-23
- One-liner: New `infrastructure/data_sources/terrain.py` with a two-tier
  source: PRIMARY = Open-Elevation REST API (keyless, SRTM-backed) — sends
  a 3×3 elevation grid request (~30 m spacing) around the AOI centroid and
  computes slope + aspect locally via the Horn 1981 kernel. FALLBACK =
  bundled `data/static/dem_india.tif` (13.78 MB int16 clipped from NOAA
  ETOPO 2022 30 arc-sec global via `scripts/dev_smoke/build_dem_clip.py`
  using rasterio `/vsicurl/` HTTP range reads so we never download the
  whole 1.58 GB source). LAST RESORT = pseudo-satellite default
  (Indo-Gangetic plain typical values) — surfaced as `terrain` in
  `data_quality.fabricated_fields`. `TerrainDataFetcher.fetch_terrain`
  returns `{slope_percent, aspect_degrees, aspect_compass, elevation_m,
  source}` where `source ∈ {open-elevation, bundled-dem, fabricated}`.
  Wired into the AOI composer + advisory_service so the irrigation_schedule
  component carries terrain through to both the Streamlit section
  (`ui/sections/irrigation_schedule.py`) and the PDF generator
  (`ui/pdf/generator.py`). Branching narrative lives in
  `application/narratives.py` (single source of truth for both renderers):
  <2% slope → basin OK; 2–5% → prefer drip; >5% → drip + contour/terracing.
  References note adapts to the source ("Slope/aspect from Open-Elevation
  (SRTM ~30 m) via Horn 1981 kernel" vs "from bundled ETOPO 2022 30 arc-sec
  India clip (Open-Elevation unreachable)"). 26 new tests pass (Horn math
  reference cases, aspect→compass conversion, OpenElevation client happy
  path + failures, LocalDEMSampler bbox + missing-file, two-tier
  composition). Live-verified at: Ganganagar (flat, 180 m, source
  open-elevation), Shimla (41.7% slope, 1959 m), Mumbai (flat, 3 m) —
  and the fallback path independently sampled (Shimla 11% W facing,
  2089 m from bundled DEM when Open-Elevation simulated-down). License:
  NOAA ETOPO is U.S. government public domain.

### 5. Bundle ISRIC global salinity raster for real EC
- **Resolved:** 2026-05-21
- One-liner: `scripts/dev_smoke/build_salinity_clip.py` fetches the 15
  ISRIC GSSmap 2016 tiles (~363 MB total, CC BY 4.0), mosaics + clips them
  to an India bbox (lat 5-38, lon 67-99) at native ~250 m resolution, and
  writes `data/static/salinity_india.tif` (13.2 MB, EPSG:4326, int32, 5-class
  FAO scheme). `SalinityRasterSampler` in `infrastructure/data_sources/soil.py`
  reads the bundled raster lazily via rasterio, returns
  `{ec, salinity_class, salinity_label}` for points inside the bbox, None
  outside. `SoilDataFetcher` now overlays real EC + class + label onto the
  soil properties when sampling succeeds; `_fabricated_fields["ec"]` flips
  to False. `_NO_REAL_SOURCE` is now empty (was `{"ec"}` — every soil
  property has at least a conditional real source). Live-verified at the
  default Ganganagar AOI: previously fabricated `ec=0.4` → real raster
  reading `ec=3.0 dS/m, class 1 "slightly saline"`, and
  `data_quality.fabricated_fields` no longer lists any `soil.*` entries
  (only the still-fabricated NDVI/RVI/RSM indices remain). `.gitignore`
  exempts `data/static/` so the clip ships with the repo (no LFS needed).
  6 new tests pass (3 raster-sampling + 2 public-adapter overlay + 1
  out-of-coverage); 4 pre-existing tests updated to mock the new
  independent salinity source. Tile cache in `data/cache/isric_salinity_2016/`
  can be deleted post-build to reclaim ~360 MB.

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
