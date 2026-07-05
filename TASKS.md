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

### 16. Pest/disease forecasting — Layer 1 (weather-driven risk models)
- **Status:** in-progress (grape powdery/downy landed; codling-moth/scab degree-day models still pending)
- **Why:** Today's pest/disease section is a static-lookup *susceptibility
  heuristic*, not a forecast — it scores "conditions resemble what this
  pest likes" from a 5-row table. The goal is to move it toward genuine
  **weather-driven forecasting**: predict *when* risk is high before any
  symptoms, the way operational systems (NEWA, RIMpro, USPest.org) do.
- **What we want to achieve** (not how):
  - [ ] Insect risk driven by **degree-day accumulation** from sowing /
        a biofix, so the model tracks each pest's actual life-cycle timing.
  - [ ] Disease risk driven by **leaf-wetness duration × temperature**
        infection logic (Mills-curve style), not a humidity heuristic.
  - [ ] Output framed as a forward risk window ("egg-hatch / infection
        period expected on date X"), not just a static percentage.
  - [ ] Per-crop/per-pest parameters sourced from published models rather
        than hand-tuned constants.
- **Depends on:** real RH (#15); ideally real LST (#9) for canopy
  temperature; degree-days already computed in the AOI composer.

### 17. Pest/disease — Layer 2 (ground-truth observation inputs)
- **Status:** pending (backlog, epic)
- **Why:** Any forecast model (#16) drifts without ground truth. This layer
  is about **letting real observations into the system** — the biofix and
  population pressure that anchor the models, and the confirmation that a
  predicted risk is actually present.
- **What we want to achieve:**
  - [ ] A way for a user/agronomist to log **pheromone-trap counts** and
        **scouting observations** (pest, count, date, location) against an AOI.
  - [ ] The first sustained trap catch sets the **biofix** that anchors the
        degree-day models in #16.
  - [ ] Observed pressure overrides / calibrates the modelled risk, and the
        report distinguishes "modelled risk" from "confirmed presence".
  - [ ] Economic-threshold-based spray/no-spray guidance where data allows.

### 18. Pest/disease — Layer 3 (remote-sensing symptom detection)
- **Status:** pending (backlog, epic)
- **Why:** Locate *where* a problem is and *how severe*, ideally before the
  eye sees it — complementing the "when" from #16 and the "confirmed" from
  #17. We already pull Sentinel-2; this is about turning imagery into
  spatial stress/symptom signals.
- **What we want to achieve:**
  - [ ] Spatial stress maps from the indices we already compute (red-edge /
        NDRE, thermal once #9 lands) highlighting anomalous patches within
        the AOI.
  - [ ] Where feasible, image-based symptom classification (e.g. a
        photo-upload disease classifier) as an optional input.
  - [ ] Severity quantification (affected-area %) rather than a single
        whole-field score.
  - [ ] Honest attribution — flag that a remote stress signal is
        non-specific until confirmed by #17.

### 19. Pest/disease — Layer 4 (sensor fusion + integrated forecast)
- **Status:** pending (backlog, epic; depends on #16-#18)
- **Why:** The end state — tie the other three layers into one
  continuously-updated, farm-specific, ideally spatial forecast, fed by
  automated inputs rather than one-off API calls.
- **What we want to achieve:**
  - [ ] Ingest in-field sensor streams (leaf wetness, canopy RH/temp) when
        available, feeding the infection models with local microclimate
        instead of a distant station.
  - [ ] Fuse weather + observations (#17) + remote sensing (#18) into a
        single risk forecast, spatial where the data supports it.
  - [ ] Continuously update as new data arrives, with model
        validation/retraining hooks.
  - [ ] Drive targeted (variable-rate) management recommendations.

### 9. Sentinel-3 SLSTR Land Surface Temperature (LST) adapter
- **Status:** pending (backlog)
- **Why:** Sentinel-2 has no thermal band, so we currently have no way to
  see crop canopy temperature — only air temperature from Open-Meteo. LST
  is a high-value input that unlocks two things we cannot do today:
  - **Crop water stress detection** before NDVI changes. A transpiring
    canopy is typically 2–5 °C cooler than air; a water-stressed canopy
    heats up. Canopy-Air Temperature (CAT) is a direct, early stress
    signal.
  - **Actual ET** (not potential). SEBAL / METRIC / SSEBop models invert
    LST + albedo + meteorology into actual evapotranspiration, replacing
    today's ET₀ × Kc estimate with a measured one.
- **Source:** Sentinel-3 SLSTR L2 LST product. 1 km native (500 m for
  some derived products), daily revisit (combined 3A + 3B). Free via
  Copernicus Open Access Hub / EarthSearch STAC / Microsoft Planetary
  Computer. License: CC BY (Copernicus).
- **Approach (sketch — confirm at pickup time):**
  - Adapter `src/jeevn/infrastructure/data_sources/lst.py` using
    `pystac-client` against MPC's STAC endpoint (same pattern as our
    Sentinel-2 ingest).
  - Fetch the most-recent cloud-free LST scene over the AOI within the
    last 7 days; sample at the AOI centroid + a 3×3 neighbourhood for
    a representative value.
  - Compute Canopy-Air Temperature stress index using the LST plus the
    Open-Meteo daily mean air temp.
  - Wire into the irrigation_schedule narrative (real water-stress
    callout) and growth_yield (water-stress branch).
  - Fabricated fallback as usual when no recent scene / clouded out.
- **Acceptance:**
  - [ ] `LSTDataFetcher.fetch_lst(lat, lon)` returns
        `{lst_celsius, scene_date, source, cloud_pct}` or fabricated.
  - [ ] Three-tier wiring (real LST / fabricated / no-data alert when
        sustained cloud).
  - [ ] Narrative branch: stress / no-stress / inconclusive.
  - [ ] Doc updates per sync rule.

### 11. CHIRPS daily 5 km precipitation (complements Open-Meteo)
- **Status:** pending (backlog)
- **Why:** Open-Meteo serves precipitation derived from ERA5 reanalysis
  — a global atmospheric model that smooths localized convective
  events. CHIRPS (Climate Hazards Group InfraRed Precipitation with
  Station data) blends real satellite IR observations with rain-gauge
  station data, **purpose-built for agricultural drought monitoring**
  in low-data regions. For an Indian advisory product, CHIRPS is the
  agronomically right source.
- **Source:** Climate Hazards Center, UC Santa Barbara. Free, no auth.
  HTTPS direct download from `data.chc.ucsb.edu/products/CHIRPS-2.0/`.
  Daily preliminary at ~2 day latency, daily final at ~3 weeks
  latency. COG format. License: public domain.
- **Approach:**
  - Adapter `src/jeevn/infrastructure/data_sources/precip.py` with
    `ChirpsClient.fetch_daily_series(lat, lon, start, end)` — fetches
    the relevant daily COGs via `/vsicurl/` (no full-globe download),
    samples at the AOI centroid, returns per-day rainfall in mm.
  - In `aoi.py` composer: when CHIRPS is reachable, override
    Open-Meteo precipitation with CHIRPS values. Mark source on the
    weather dict. Open-Meteo stays as the fallback.
  - The advisory irrigation_schedule narrative already references
    rainfall — just adapts to the source.
- **Acceptance:**
  - [ ] `fetch_daily_series` returns `[{date, rainfall_mm}, ...]` or
        None on failure.
  - [ ] Composer wiring + per-property source tracking.
  - [ ] Tests: mocked /vsicurl/ reads, network-down fallback to
        Open-Meteo, source labelling.
  - [ ] Doc updates per sync rule.

### 12. HLS (Harmonized Landsat Sentinel) gap-filler (complements Sentinel-2)
- **Status:** pending (backlog)
- **Why:** Our NDVI/NDWI pipeline relies on Sentinel-2; during sustained
  cloud cover (monsoon!) the most-recent cloud-free Sentinel-2 scene
  over a given AOI can be 2+ weeks old. HLS adds Landsat 8 + 9
  acquisitions to the candidate pool, pre-harmonized to the Sentinel-2
  grid + atmospheric correction. Effective revisit goes from ~5 day
  (Sentinel-2 alone) to ~2–3 day (combined L8+L9+S2A+S2B+S2C).
- **Complementarity with Sentinel-2:** HLS is **a gap-filler, not a
  replacement** — Sentinel-2 at 10 m resolution beats HLS's 30 m for
  small Indian parcels. Use HLS only when the freshest Sentinel-2
  cloud-free scene is older than a threshold (e.g., 7 days). Return to
  Sentinel-2 the moment one is available again.
- **Source:** NASA LP DAAC. Collections `HLSL30` (Landsat-derived) and
  `HLSS30` (Sentinel-2-derived, resampled to 30 m for harmony). COG
  format. Free with Earthdata Login (`EARTHDATA_USER`/`EARTHDATA_PASS`).
  License: NASA open data.
- **Approach:**
  - Extend the existing Sentinel-2 ingest path in
    `remote_sensing/ingestion/` to query HLS when no Sentinel-2 scene
    matches the freshness threshold.
  - Same indices (NDVI, NDWI) computed from HLS bands — HLS is already
    harmonized to Sentinel-2 band-equivalents so existing index code
    needs no change.
  - Source-tag the output so the report says e.g.
    "NDVI from HLS Landsat-9 scene 2026-05-23 (no fresh Sentinel-2)".
- **Acceptance:**
  - [ ] HLS search + scene download integrated into the ingest pipeline.
  - [ ] Selection logic: Sentinel-2 first, HLS only when stale.
  - [ ] `field_maps` and indices carry a source label.
  - [ ] Tests: mocked LP DAAC STAC, fallback decision under stale-S2
        conditions.
  - [ ] Doc updates per sync rule.

### 13. Landsat 8/9 TIRS LST (finer than Sentinel-3 SLSTR — depends on #9)
- **Status:** pending (backlog, depends on #9)
- **Why:** Sentinel-3 SLSTR (#9) gives daily 1 km LST. Landsat 8/9 TIRS
  gives 100 m LST every 8 days (combined L8+L9). For a 0.5 acre AOI,
  1 km Sentinel-3 is essentially one pixel — useful as a regional
  signal but coarse. Landsat TIRS resolves the AOI into a meaningful
  10×10 pixel block, which is what we need for actual canopy-air
  temperature analysis.
- **Complementarity with #9:** Sentinel-3 = high revisit, low res;
  Landsat = lower revisit, high res. The LST adapter chooses the
  **finest-resolution recent scene** for each request — Landsat if
  within ~10 days, else Sentinel-3.
- **Source:** USGS Collection-2 Level-2 (`landsat-c2-l2`), MPC STAC.
  Free with Earthdata Login OR via MPC (no auth needed for MPC).
  License: USGS open data.
- **Approach:** extend `infrastructure/data_sources/lst.py` (created
  by #9) with a Landsat TIRS source tier. Selection rule: most-recent
  scene wins; break ties by finest resolution.
- **Acceptance:**
  - [ ] LST adapter has a second tier: Landsat TIRS via MPC STAC.
  - [ ] Selection logic + source label propagation.
  - [ ] Tests: mocked STAC, selection ordering, fallback chain.
  - [ ] Doc updates per sync rule.

### 14. ECOSTRESS LST (finest-resolution thermal — depends on #9 and #13)
- **Status:** pending (backlog, depends on #9 and #13)
- **Why:** ECOSTRESS (on ISS) provides **70 m LST** — finer than
  Landsat TIRS's 100 m, finest free LST anywhere. The instrument is
  literally designed for vegetation water stress monitoring (ECOsystem
  Spaceborne Thermal Radiometer Experiment on Space Station). When a
  recent ECOSTRESS scene exists over the AOI, it's the strongest
  signal we can get for canopy-air temperature.
- **Complementarity with #9 / #13:** Same LST adapter pattern with a
  third tier. ECOSTRESS revisit is irregular (ISS orbit, ~4 day
  average but with multi-day gaps); fall through to Landsat (100 m,
  8-day) and Sentinel-3 (1 km, daily) when no fresh ECOSTRESS scene.
- **Source:** NASA LP DAAC. Product `ECO2LSTE` (Level-2 LST + emissivity).
  Free with Earthdata Login. License: NASA open data.
- **Caveat to verify at pickup time:** ECOSTRESS had instrument issues
  (SLC failure) in 2023; acquisitions resumed but check current
  production status before assuming continuous delivery.
- **Approach:** extend `lst.py` with a third tier. Same selection
  rule as #13: most-recent + finest-resolution wins. Three-tier
  ordering: ECOSTRESS (70 m, sporadic) → Landsat TIRS (100 m, 8-day)
  → Sentinel-3 SLSTR (1 km, daily) → fabricated fallback.
- **Acceptance:**
  - [ ] LST adapter has a third tier: ECOSTRESS via LP DAAC STAC.
  - [ ] Selection logic respects "finest-resolution wins among
        recent-enough scenes" rather than strict source priority.
  - [ ] Tests: mocked STAC, three-way selection ordering, all-stale
        fallback chain.
  - [ ] Doc updates per sync rule.

### 8. Add NDWI with Gao's (1996) formulation alongside the existing index
- **Status:** pending (backlog)
- **Why:** `remote_sensing/analysis/signals.py:15` currently exposes one
  index named `ndwi(green, swir)`. That formula `(green - swir)/(green + swir)`
  is actually Xu (2006) **MNDWI** — designed for open-water-body detection
  in urban scenes. Gao (1996) **NDWI** is a different (and arguably more
  agriculturally relevant) index: `(NIR - SWIR) / (NIR + SWIR)`. It
  measures **vegetation canopy water content / moisture stress** rather
  than surface water, and is the one most agronomic literature means
  when it says "NDWI" in a crop context.
- **Acceptance:**
  - [ ] New function `ndwi_gao(nir, swir)` in `signals.py` with explicit
        Gao 1996 reference in the docstring.
  - [ ] Decide naming for the existing index — either:
        (a) rename the current `ndwi` to `mndwi_xu` and update all callers, OR
        (b) keep `ndwi` as Xu MNDWI for backward compat but rename the
            variable label in narratives/UI to reflect what it is.
        Probably (a) is cleaner; flag in the PR.
  - [ ] Wire `ndwi_gao` into the crop-health / moisture-stress narrative
        wherever vegetation water-content makes more sense than open-water
        detection (likely `growth_yield/projection.py` water-stress branch
        and the irrigation-schedule moisture commentary).
  - [ ] Tests in `tests/remote_sensing/analysis/test_indices.py`:
        known-input reference cases for both formulations + a regression
        test that ensures they produce different values on the same data
        (so a future refactor can't silently collapse them).
  - [ ] **Update the 13 docs** per the doc-sync rule: at minimum
        `src/jeevn/remote_sensing/OVERVIEW.md` (new index) and
        `PROCESSES.md` (how the moisture-stress signal is computed).
        Touch others only if behaviour visible to them changes.

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

### 20. Real-time advisory + dry-spell alerts (weather + ground sensors)
- **Resolved:** 2026-07-05
- Status: done
- One-liner: New real-time advisory layer on top of the accurate report —
  ground soil-moisture sensor fusion + dry-spell detection + confidence-gated
  irrigation/fertilisation alerts. Delivery (SMS/WhatsApp) deferred to Part 2
  behind a `Notifier` seam.
- What landed:
  - `infrastructure/sensors/` — `SoilSensor` ABC + `SensorReading` (Mock/REST/
    MQTT); fused as the **top-priority** soil-moisture source in the AOI
    composer (raw m³/m³ normalised via real SoilGrids texture).
  - `domain/dry_spell/` — recent (`fetch_forecast(past_days=…)`) + forecast
    dry-run detector; **fail-safe** (fabricated/failed forecast → data gap →
    no false dry-spell alert). `weather.fetch_forecast` gained `past_days`.
  - `application/{realtime_advisory,alerts,render,notifier,realtime_monitor}.py`
    — orchestration + `dry_spell`/`irrigate_now`/`hold_fertigation`/
    `high_salinity`/`fertilize` alerts; `python -m jeevn.application.realtime_monitor --once`.
  - **Fertilizer honesty fix:** replaced the hardcoded N/P/K "current levels"
    placeholder with a tiered resolver — soil test → **India Soil Health Card**
    (village→district→state cascade, real 2023-24 data.gov.in data) →
    SoilGrids/pedotransfer → constant. Added SoilGrids `nitrogen` layer,
    district/village reverse-geocoding, and bundled
    `data/static/shc_{district,village}_npk.csv[.gz]` built by
    `scripts/dev_smoke/build_shc_district_npk.py`. Dose alerts are
    confidence-gated (≥ medium only).
  - Fixed a pre-existing crash: `sar.py` now imports `rasterio` inside the try
    so a missing optional dep degrades to a fabricated RVI instead of crashing.
  - 39 new tests; full suite 166 passed / 0 failed in the project `.venv`
    (run tests with `.venv/Scripts/python.exe -m pytest`, NOT bare system
    Python — the venv holds rasterio/asf_search/fastapi/sqlalchemy). Docs in
    `docs/realtime_advisory.md`; ARCHITECTURE/PROCESSES/OVERVIEW docs synced.
- Follow-ups (Part 2 / backlog): SMS/WhatsApp `TwilioNotifier`; alert history +
  dedupe/ack; crop-/stage-calibrated dry-spell thresholds; S/Zn from SHC
  micronutrient data; sensor calibration/QC.

### Grape crop database (MVP-plan Part 2 #3)
- **Resolved:** 2026-06-13
- One-liner: Grape is now a first-class crop, no longer a wheat shadow.
  Added `CROP_DATA["grape"]` to `crop/phenology.py` (t_base 10 °C; 8 stages
  budburst→harvest anchored to forward/fruit pruning, ~155 d; Kc per stage;
  K-weighted N/P/K/S/Zn targets; yield potential 10000 kg/acre), grape rows
  in `growth_yield/projection.py` (`_assess_growth_stage` timing +
  `_determine_harvest_status`), a dedicated `_get_grape_recommendations`
  fertilizer branch (SOP not MOP — chloride-sensitive; foliar Zn; S top-up
  beyond SOP), and fixed the grape mealybug `stage_susceptibility` to real
  grape stages. Verified end-to-end: a grape AOI projects against grape
  stages/yield/harvest, not wheat. New tests: `test_phenology.py` (5),
  `test_fertilizer.py` (3). Docs synced (PROCESSES F.1/F.4/G.1/G.2/I.1,
  domain OVERVIEW). With this, the H.2/H.3 grape disease models fire against
  real grape phenology rather than the wheat fallback.

### 15. Real relative humidity from Open-Meteo (replace the RH proxy)
- **Resolved:** 2026-06-13
- One-liner: `weather.py` now fetches Open-Meteo hourly `temperature_2m`,
  `relative_humidity_2m`, `precipitation` (alongside the existing soil
  moisture) in both `fetch_weather` (archive) and `fetch_forecast`, and
  surfaces `daily.relative_humidity_mean` (24-h mean) + a full `hourly`
  block. `assess_pest_disease_risk` and `growth_yield/projection.py` consume
  the real RH and fall back to the `40 + rainfall×2 + (30 − temp)×2` proxy
  only on fabricated weather, flagging `environmental_conditions.humidity_estimated`;
  UI/PDF label "Humidity" vs "Humidity (est.)" off that flag. Landed together
  with the first slice of #16 (grape Gubler powdery + hedged downy models in
  the new `domain/crop_health/disease_models.py`) and dropped the unjustified
  RVI term from disease scoring. New tests: `test_disease_models.py` (10),
  `test_assessment.py` (5), extended `test_weather.py`. Docs synced
  (PROCESSES D.5/H.1–H.4, domain + infra OVERVIEW).

### 4. NISAR L-band soil moisture integration (SME2)
- **Resolved:** 2026-05-29
- One-liner: New `infrastructure/data_sources/nisar.py` —
  `NisarSoilMoistureClient.fetch_sm_at(lat, lon, days_back=14)` runs the
  full pipeline: keyless `asf_search` for the latest SME2 granule over the
  AOI → Earthdata-authenticated download of the ~120 MB HDF5 to
  `data/cache/nisar/` (gitignored, keeps 2 most-recent) → reads
  `soilMoisture` (m³/m³) at the nearest EASE-grid cell from the first
  candidate algorithm (DSG→PMI→TSR) with `retrievalQualityFlag==0`, with a
  ~5 km edge-margin reject. HDF5 layout confirmed against a real 2026-01-18
  granule (`science/LSAR/SME2/grids/...`, EPSG:6933, fill -9999). Wired as
  the **top tier of a tiered RSM source** in the AOI composer:
  NISAR (m³/m³ → fraction-of-FC via texture) → Open-Meteo
  `soil_moisture_current` → fabricated `0.72`; `advisory_service` overrides
  `ndvi_data["rsm"]` and drops `rsm` from `data_quality.fabricated_fields`
  when real. Creds via `EARTHDATA_USER`/`EARTHDATA_PASS` (+ authorise the
  "ASF Data Access" app); composer only attempts NISAR when creds are set.
  Live-verified end-to-end against the 2026-01-18 granule (0.2257 m³/m³,
  DSG, qflag 0); composer today falls through to Open-Meteo (no pass in
  14-day window — SME2 production paused since 2026-01-20) and `rsm` is no
  longer in fabricated_fields (was `['ndvi','rsm']` → `['ndvi']`). 7 new
  tests (mocked search/download/sample, no-creds + no-pass fallbacks, +2
  against the real cached granule). 137 tests pass. The NISAR tier is
  dormant until NASA-ISRO resume SME2 production, then activates with no
  code change. `asf_search` + `h5py` added to requirements.txt;
  `.env.example` documents the Earthdata setup.
- **Enables:** task #6 (NISAR ↔ Open-Meteo SM calibration) once paired
  observations accumulate.

### Bugfix — irrigation schedule: ET0 units + rain-aware forecast scheduling
- **Resolved:** 2026-05-26
- One-liner: Fixed three intertwined bugs that made the irrigation schedule
  physically impossible (7018 mm/day drip, 28,075 mm total) and ignored rain.
  (1) `et0.py` — `Ra = solar_radiation / 0.408` inverted the MJ→mm factor AND
  substituted surface for extraterrestrial radiation, inflating ET0 ~6× (23→
  ~6 mm/day). Now always computes Ra from `_calculate_ra` (FAO-56 eq. 21,
  MJ/m²/day) × 0.408. (2) `scheduler.py` — dropped the `/1000` on rainfall
  (which silently ignored it) and the `×1000` on irrigation (which inflated
  drip 1000×); everything is now mm end-to-end. (3) Rewrote the scheduler to
  be **rain-aware + forward-looking**: new `WeatherDataFetcher.fetch_forecast`
  (Open-Meteo forecast API — 7-day daily precip + `precipitation_probability_max`
  + temps, distinct from the historical archive) feeds per-day ETc minus
  `0.8 × forecast_rain`; rows show real forecast rainfall + rain% instead of
  hardcoded "0 mm"/"0%". Wired forecast through the AOI composer + a
  `pseudo_satellite.make_default_forecast` fallback (surfaces as `forecast`
  in `data_quality.fabricated_fields`). Live-verified at Ganganagar: ET0 6.69,
  drip 3-4 mm/day, total 13.4 mm over 4 events, real forecast rain/rain% per
  row. 8 new tests in `tests/domain/irrigation/test_scheduler.py` (ET0 sanity,
  unit regression, heavy-rain-zeroes-irrigation, light-rain-reduces,
  per-row rain display, no-forecast fallback). 130 tests pass.

### 10. Sentinel-1 C-band SAR adapter (real RVI)
- **Resolved:** 2026-05-26
- One-liner: New `infrastructure/data_sources/sar.py` — `Sentinel1Client.fetch_latest_rvi(lat, lon)`
  queries Microsoft Planetary Computer's STAC for the `sentinel-1-rtc` collection over the AOI
  in the last 10 days (no auth), picks the newest scene, signs VV + VH COG hrefs with an MPC
  SAS token, reads a 5×5 pixel window (~100 m × 100 m) at the centroid via rasterio `/vsicurl/`
  HTTP range reads, computes `RVI = 4·VH / (VV + VH)` in linear γ⁰ units (no dB conversion —
  RTC is already linear), clips to `[0, 1.5]`. Returns `{rvi, scene_date, scene_id, source}`
  or None on any failure. Wired into `advisory_service._process_ndvi_data` as a new `sar_data`
  kwarg that overrides the previous NDVI×1.08 proxy when a real scene is found.
  `data["rvi_source"]` and `data["rvi_scene_date"]` propagate so narratives can attribute
  the value. RVI source priority is now Sentinel-1 → NDVI proxy → fabricated default.
  9 new tests pass (mocked STAC, mocked raster reads, no-scene/STAC-fail/missing-asset/
  raster-fail paths, three RVI-math reference cases including the speckle-clip). Live-verified
  end-to-end at default Ganganagar AOI: previous fabricated `rvi=0.65` → real
  `rvi=0.509 from scene 2026-05-19`; Kc drops from ~0.71 to 0.30 reflecting actual canopy
  vigour rather than the over-optimistic proxy; `data_quality.fabricated_fields` no longer
  lists `rvi` (only `ndvi`, `rsm` remain). Also tested at Shimla (1.242, dense Himalayan
  forest, plausible) and Mumbai (no recent scene → graceful fallback). NISAR L-band (task #4)
  will live in this same module as a higher-priority canopy-penetrating source when SME2
  graduates from Beta.

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
