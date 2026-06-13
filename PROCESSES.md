# PROCESSES — Ideal vs. What This MVP Does

A process-first companion to [ARCHITECTURE.md](ARCHITECTURE.md) and the per-folder `OVERVIEW.md` files. The other docs go *code → behaviour*. This one goes the other way: pick a measurement or calculation, and read top-down through:

1. **What it is** — one-line definition.
2. **Scientific ideal** — the gold-standard method, instrumentation, units, expected accuracy. Stated *immaterial* of whether it's tractable from a satellite — this is the "what would a research lab actually do" line.
3. **What this MVP does** — the approximation, with the actual formula or method.
4. **Gap / when it breaks** — what the approximation loses and where it's likely to be wrong.
5. **Code path** — where the data source, the transformation, and the outstream live.

Grouped thematically: remote sensing → soil → terrain → weather → irrigation → phenology → fertilizer → pest/disease/weed → yield → anomaly detections.

---

## A. Remote Sensing — Vegetation & Water Indices

### A.1 NDVI (Normalized Difference Vegetation Index)

**What it is:** A 0-1 (formally -1..+1) proxy for green-leaf biomass and photosynthetic activity.

**Scientific ideal:** A field spectroradiometer (ASD FieldSpec, Apogee MS-100 etc.) takes hemispherical reflectance in narrow red (660-680 nm) and NIR (770-900 nm) bands at the canopy with a known irradiance reference, corrected for solar zenith and atmospheric path. Output is calibrated to a Spectralon reference plate. Typical accuracy: ±0.01 NDVI. Even better: leaf-level LAI (Licor LAI-2200C) + chlorophyll content (SPAD-502).

**What this MVP does:** `NDVI = (B08 - B04) / (B08 + B04 + 1e-6)` from Sentinel-2 L2A surface reflectance (B04 = 665 nm Red, B08 = 842 nm NIR), both at 10 m native. Pixels outside the AOI polygon set to NaN.

**Gap / when it breaks:** Sentinel-2 atmospheric correction (Sen2Cor) carries ~0.02-0.05 reflectance uncertainty, magnified into NDVI; saturates above LAI ≈ 3-4; sensitive to soil background at low cover; cloudy/cirrus pixels degrade silently if SCL masking misses them.

**Code path:**
- Data source: STAC item with `B04` + `B08` asset hrefs from [src/jeevn/ingestion/sentinel.py](src/jeevn/ingestion/sentinel.py) (Microsoft Planetary Computer).
- Transformation: canonical formula in [src/jeevn/remote_sensing/ndvi/compute.py](src/jeevn/remote_sensing/ndvi/compute.py) (`ndvi_index`); per-date AOI mean in [src/jeevn/remote_sensing/ndvi/aggregate.py](src/jeevn/remote_sensing/ndvi/aggregate.py); full raster in [src/jeevn/remote_sensing/analysis/confidence.py](src/jeevn/remote_sensing/analysis/confidence.py) (`_compute_index_raster`).
- Outstream: `ndvi_timeseries` + `ndvi_raster` in the `/aoi` response; PNG via `/aoi/{id}/maps/ndvi.png` (colorized in [src/jeevn/remote_sensing/visualization.py](src/jeevn/remote_sensing/visualization.py)); `aoi_info.ndvi_mean` flows into the advisory report's vegetation-vigor branch.

---

### A.2 NDWI (Normalized Difference Water Index)

**What it is:** Canopy water content / irrigation health proxy.

**Scientific ideal:** Two acceptable formulations exist — Gao (1996) NDWI = (NIR - SWIR)/(NIR + SWIR) for canopy water; McFeeters (1996) NDWI = (Green - NIR)/(Green + NIR) for open-water mapping. For irrigation health, Gao's NIR-SWIR formulation is the textbook choice. Best ground truth: gravimetric leaf water content (oven-dry mass loss).

**What this MVP does:** `NDWI = (B03 - B11) / (B03 + B11)` — i.e. (Green - SWIR)/(Green + SWIR). Two code paths reach the same value by different routes: the per-date aggregator calls `ndvi_index(swir, green)` with the arguments **swapped**, so `(green - swir)/(green + swir)` falls out directly; the raster path in `confidence.py` calls `_compute_index_raster(green, swir)` in the normal order and then **negates** the result to flip the sign. B03 is 10 m, B11 is 20 m — bilinearly resampled onto the B03 grid.

**Gap / when it breaks:** This is the McFeeters family, not Gao's. Tends to behave more like a "wet ground vs dry ground" index than a true canopy-water index — it works for the "irrigation health map" framing because wet soil + irrigated canopy both push it the same way, but it isn't quite what FAO/USDA literature calls NDWI for crop water stress.

**Code path:**
- Data source: STAC `B03` + `B11` from [src/jeevn/ingestion/sentinel.py](src/jeevn/ingestion/sentinel.py).
- Transformation: raster path in [src/jeevn/remote_sensing/analysis/confidence.py](src/jeevn/remote_sensing/analysis/confidence.py) (~line 184, the green/swir branch + negate); per-date in [src/jeevn/remote_sensing/ndvi/aggregate.py](src/jeevn/remote_sensing/ndvi/aggregate.py) (~line 92, the argument-swapped `ndvi_index(swir, green)` call).
- Outstream: `ndwi_raster` in `/aoi` response; PNG via `/aoi/{id}/maps/ndwi.png`; "Irrigation Health Map" on PDF page 1 + Streamlit field-maps section.

---

### A.3 NDRE (Normalized Difference Red Edge)

**What it is:** Chlorophyll / nitrogen status proxy, more sensitive than NDVI in dense canopies.

**Scientific ideal:** NDRE = (NIR - Red-Edge) / (NIR + Red-Edge) with the red-edge band centred near 705-740 nm. Validation against leaf-N from Kjeldahl digestion or near-IR leaf reflectometers. Best ground truth: SPAD-502 chlorophyll meter + foliar N% from a wet-chem lab.

**What this MVP does:** `NDRE = ndvi_index(B05, B08)` with Sentinel-2 B05 (705 nm) and B08 (842 nm). Computed only in the per-date timeseries — no full raster.

**Gap / when it breaks:** Used only as a single AOI-mean per date; no spatial map. Currently feeds `signals.nutrient_stress_score` and not much else. B05 is 20 m native — coarser than NDVI/NDWI.

**Code path:**
- Data source: STAC `B05` + `B08` from [src/jeevn/ingestion/sentinel.py](src/jeevn/ingestion/sentinel.py).
- Transformation: [src/jeevn/remote_sensing/ndvi/aggregate.py](src/jeevn/remote_sensing/ndvi/aggregate.py) (re_url branch, line ~94).
- Outstream: `ndre` column in `data/indices_timeseries_*.csv` + `ndvi_timeseries[i].ndre`; consumed by [src/jeevn/remote_sensing/analysis/signals.py](src/jeevn/remote_sensing/analysis/signals.py) `nutrient_stress_score`.

---

### A.4 RVI (Radar Vegetation Index)

**What it is:** Cloud-penetrating biomass proxy from C-band SAR.

**Scientific ideal:** Sentinel-1 dual-polarisation RVI = (4 × σ°VH) / (σ°VV + σ°VH). Backscatter terrain-flattened (RTC), incidence-angle normalised, multilooked to reduce speckle, and validated against destructive biomass sampling (kg dry matter / m²). For L-band (NISAR), the formulation differs but the same logic applies.

**What this MVP does:** **Real Sentinel-1 RTC.** [src/jeevn/infrastructure/data_sources/sar.py](src/jeevn/infrastructure/data_sources/sar.py) (`Sentinel1Client.fetch_latest_rvi`) queries Microsoft Planetary Computer's STAC catalogue for the `sentinel-1-rtc` collection over the AOI in the last 10 days, picks the newest scene, signs the VV + VH COG hrefs with an MPC SAS token, reads a 5×5 pixel window (~100 m × 100 m) at the centroid via rasterio `/vsicurl/`, computes the mean linear-power backscatter for each band, and applies the standard formula `4 · VH / (VV + VH)` (RTC values are already in γ⁰ linear so no dB→linear step). Clipped to `[0, 1.5]` to defang speckle outliers. RVI source priority is now Sentinel-1 → NDVI×1.08 proxy → `pseudo_satellite.RVI = 0.65`.

**Gap / when it breaks:** The 5×5 sample is small — for larger AOIs we average a 100 m × 100 m patch rather than the whole polygon. Speckle and edge effects can still push RVI to the clipped 1.5 ceiling for very-bright scenes. When MPC STAC is down or no scene exists within 10 days (rare — Sentinel-1A has 12-day repeat, plus Sentinel-1C for ~6-day combined), falls through to the NDVI×1.08 proxy that doesn't reflect the radar-specific scattering physics.

**Code path:**
- Data source: [src/jeevn/infrastructure/data_sources/sar.py](src/jeevn/infrastructure/data_sources/sar.py) — MPC STAC `sentinel-1-rtc` collection.
- Transformation: same file, `_sample_mean()` reads the COG window, RVI formula applied in `Sentinel1Client.fetch_latest_rvi`.
- Composition: [src/jeevn/application/advisory_service.py](src/jeevn/application/advisory_service.py) (`generate_report` calls the adapter; `_process_ndvi_data` accepts a `sar_data=` kwarg and overrides any NDVI-derived RVI with the real Sentinel-1 value).
- Outstream: `ndvi_data["rvi"]` feeds [src/jeevn/domain/irrigation/scheduler.py](src/jeevn/domain/irrigation/scheduler.py) (Kc adjustment), [src/jeevn/domain/fertilizer/requirements.py](src/jeevn/domain/fertilizer/requirements.py) (target adjustment), [src/jeevn/domain/pest_disease_weed/assessment.py](src/jeevn/domain/pest_disease_weed/assessment.py) (per-pest risk factor), [src/jeevn/domain/growth_yield/projection.py](src/jeevn/domain/growth_yield/projection.py) (vigor rating). `ndvi_data["rvi_source"]` and `ndvi_data["rvi_scene_date"]` are populated when the real source won — narratives can attribute the value.

**Listed backlog item:** TASKS.md #4 — NISAR L-band ingest via `asf_search` (deferred; SME2 currently Beta with sparse delivery). When NISAR graduates, it slots into `sar.py` as a higher-priority canopy-penetrating tier alongside Sentinel-1.

---

### A.5 RSM (Radar Soil Moisture)

**What it is:** Surface soil moisture (0-5 cm) from SAR backscatter.

**Scientific ideal:** Inversion model (e.g. Oh 2004, Dubois, IEM) applied to terrain-flattened σ°VV + incidence angle, ideally L-band (deeper sensing depth). NISAR's standard SM product is at 100 m; SMAP at 9 km. Validated against in-situ TDR / FDR probes (Campbell CS650, Decagon 5TE). Output in m³/m³ volumetric water content.

**What this MVP does:** **Tiered, real-where-possible** (the old `0.72` constant is retired). The AOI composer resolves RSM in priority order, all on the same fraction-of-field-capacity scale the pest/weed thresholds expect:
1. **NISAR SME2 (L-band)** — when Earthdata creds are present AND a pass falls within ~14 days AND the AOI is ≥5 km from the granule edge. The granule's `soilMoisture` (m³/m³, from the first candidate algorithm — DSG/PMI/TSR — with retrievalQualityFlag 0) is divided by the texture field capacity to a fraction. *Currently dormant:* SME2 production paused 2026-01-20, so the freshness gate falls through today. Verified end-to-end against a real 2026-01-18 granule (0.2257 m³/m³, DSG).
2. **Open-Meteo modelled SM** — the real fallback (same value as `soil.soil_moisture_current`, B.9). This is what serves live requests today.
3. **`pseudo_satellite.RSM = 0.72`** — last resort, flagged `rsm` in `data_quality.fabricated_fields`.

**Gap / when it breaks:** NISAR tier is dormant until SME2 resumes; until then RSM = Open-Meteo modelled SM (decent, but modelled not measured). Open-Meteo m³/m³ is normalised by a texture-derived field capacity, so the fraction can clamp to 1.0 after rain.

**Code path:**
- Data source: NISAR via [src/jeevn/infrastructure/data_sources/nisar.py](src/jeevn/infrastructure/data_sources/nisar.py) (`NisarSoilMoistureClient.fetch_sm_at`); Open-Meteo SM via the weather adapter; constant from `pseudo_satellite`.
- Transformation: tiered resolution + m³/m³→fraction in [src/jeevn/infrastructure/data_sources/aoi.py](src/jeevn/infrastructure/data_sources/aoi.py) (`radar_soil_moisture`); override applied in [src/jeevn/application/advisory_service.py](src/jeevn/application/advisory_service.py).
- Outstream: `ndvi_data["rsm"]` (+ `rsm_source`, `rsm_pass_date`); surfaces as `environmental_conditions.rsm` and feeds [src/jeevn/domain/pest_disease_weed/assessment.py](src/jeevn/domain/pest_disease_weed/assessment.py) (`_calculate_weed_risk`).

---

### A.6 Cloud masking

**What it is:** Identifying and excluding cloud / cloud-shadow / cirrus pixels before computing indices.

**Scientific ideal:** **Fmask 4.x** (Zhu & Woodcock 2012) or **s2cloudless** (Sentinel Hub's ML model). Both give per-pixel probability + binary masks; Fmask additionally separates shadows. Validation: Hollstein et al. confusion-matrix benchmarks against hand-labelled scenes.

**What this MVP does:** Sentinel-2 SCL (Scene Classification Layer) band, treating class IDs `{3 shadow, 8 cloud-med, 9 cloud-high, 10 cirrus}` as masked. Alternative path via QA60 bitmask (bits 10/11).

**Gap / when it breaks:** SCL is good (Sen2Cor) but conservative on cirrus; can miss thin sub-pixel clouds and over-mask snow / bright soil as cloud. The masking helpers exist but are **not currently called** from the active raster path in [src/jeevn/remote_sensing/analysis/confidence.py](src/jeevn/remote_sensing/analysis/confidence.py) — it just filters out pixels where red or NIR ≤ 0. The aggregator also doesn't apply SCL masking when streaming from STAC.

**Code path:**
- Data source: SCL or QA60 bands from STAC assets (would be fetched same as B04/B08).
- Transformation: [src/jeevn/remote_sensing/masking/cloud.py](src/jeevn/remote_sensing/masking/cloud.py) (`scl_cloud_mask`, `qa60_mask`, `apply_mask`).
- Outstream: only routed through `compute_ndvi_with_mask` in [src/jeevn/remote_sensing/ndvi/compute.py](src/jeevn/remote_sensing/ndvi/compute.py) — not used by the main API flow. Effectively dormant.

---

### A.7 Parcel confidence score

**What it is:** A 0-1 quality score combining how green, how uniform, and how complete the AOI raster is.

**Scientific ideal:** Stratified ground-truth sampling — geo-located biomass cuts or canopy-cover photographs, regressed against the index, with the confidence being a function of regression R² and per-pixel residual variance. Typically presented with formal uncertainty bounds.

**What this MVP does:** `confidence = 0.4 × ndvi_score + 0.3 × uniformity + 0.3 × validity` where `ndvi_score = clip((mean+1)/2, 0, 1)`, `uniformity = 1 - clip(std, 0, 1)`, `validity = valid_pct / 100`.

**Gap / when it breaks:** Heuristic, not calibrated to any real biomass. Penalises both heterogeneous fields (where heterogeneity might be genuine) and high std (which can flag interesting structure). Returns ~0.5-0.8 for almost any reasonable field.

**Code path:**
- Data source: the NDVI raster array from `compute_raster`.
- Transformation: [src/jeevn/remote_sensing/analysis/confidence.py](src/jeevn/remote_sensing/analysis/confidence.py) (`compute_parcel_confidence`) — and the scalar version [src/jeevn/remote_sensing/analysis/signals.py](src/jeevn/remote_sensing/analysis/signals.py) (`parcel_confidence_score`).
- Outstream: `parcel_confidence` field in `/aoi` response; flows into `aoi_result` in the UI but isn't surfaced prominently to the user.

---

### A.8 Other spectral indices (defined, not wired in)

**What it is:** A small library of additional vegetation/water/chlorophyll indices that exist as helper functions but are not part of the active `/aoi` pipeline.

**Scientific ideal:** Each is a recognised index in its own right — EVI (Huete 2002, atmosphere- and soil-resistant greenness), SAVI (Huete 1988, soil-adjusted greenness), GCI (Gitelson, green-chlorophyll), MSI (Hunt & Rock, moisture stress). In a mature system they would be computed from masked surface reflectance and validated like NDVI/NDRE.

**What this MVP does:** Defines them as pure functions but **never calls them** from the API flow:
```
evi  = 2.5 × (NIR − Red) / (NIR + 6·Red − 7.5·Blue + 1)
savi = ((NIR − Red) / (NIR + Red + L)) × (1 + L)     # L = 0.5
gci  = (NIR / Green) − 1
msi  = SWIR / NIR
```
The file also carries standalone `ndvi`, `ndwi`, `ndre` helpers that duplicate the formulas actually used elsewhere (`ndvi_index` in `compute.py`, the swapped/negated NDWI in A.2, the `ndre` branch in `aggregate.py`).

**Gap / when it breaks:** Dead code from the operator's point of view — none of these reach a response field or the report. Listed here so a future contributor knows they exist (and that wiring one in means adding a band fetch + raster path, not just calling the function).

**Code path:**
- Transformation: [src/jeevn/remote_sensing/analysis/signals.py](src/jeevn/remote_sensing/analysis/signals.py) (`evi`, `savi`, `gci`, `msi`, plus duplicate `ndvi`/`ndwi`/`ndre`, lines 10-42).
- Outstream: none.

---

## B. Soil

### B.1 Soil pH

**What it is:** Acidity / alkalinity of the soil solution.

**Scientific ideal:** Lab determination on a 1:2.5 soil-to-water suspension with a calibrated glass electrode (per ISO 10390). Accuracy ±0.05 pH. For field rapid-test: portable pH meter on a saturated paste.

**What this MVP does:** ISRIC SoilGrids v2.0 `phh2o` property, depth-weighted across 0-5 / 5-15 / 15-30 cm, divided by SoilGrids' `d_factor=10` to convert mapped int → real pH. Fallback when SoilGrids is unreachable: `pseudo_satellite.DEFAULT_SOIL_PROPERTIES["ph"] = 7.0`.

**Gap / when it breaks:** SoilGrids is a 250 m global model; per-pixel uncertainty is ±0.5 pH in many regions. Won't reflect localised liming/acidification history of the specific parcel. Returns nothing for built-up/water/rock pixels (the AOI-in-city alert).

**Code path:**
- Data source: ISRIC SoilGrids REST API in [src/jeevn/infrastructure/data_sources/soil.py](src/jeevn/infrastructure/data_sources/soil.py) (`SoilGridsClient.fetch`).
- Transformation: depth-weighted mean (`_depth_weighted_mean`) + d-factor (`_convert_to_target_units`).
- Outstream: `aoi_data["soil"]["properties"]["ph"]` → [src/jeevn/domain/soil/management.py](src/jeevn/domain/soil/management.py) (classification + recommendations) → `components.soil_management.ph` in the report.

---

### B.2 Soil EC / Salinity

**What it is:** Electrical conductivity of the saturated paste extract; classifies soil salinity.

**Scientific ideal:** USDA saturated-paste extract (ECe) per Handbook 60 — saturate soil, vacuum-extract pore water, measure with a conductivity probe at 25 °C. Output in dS/m. Field rapid: 1:1 or 1:5 soil-to-water EC (different thresholds). Validates against root-zone osmotic potential.

**What this MVP does:** Two-tier:
1. **Real:** ISRIC GSSmap 2016 salinity raster (5-class FAO/USDA scheme), India-clipped, sampled at AOI centroid. Class → EC midpoint mapping: `{0: 1.0, 1: 3.0, 2: 6.0, 3: 12.0, 4: 18.0}` dS/m.
2. **Fallback:** `pseudo_satellite.DEFAULT_SOIL_PROPERTIES["ec"] = 0.4`.

**Gap / when it breaks:** The bundled raster is a single 2016 snapshot at ~1 km, India-only. Class-to-EC mapping loses precision within a class (a class-2 field is "somewhere between 4 and 8 dS/m"). AOIs outside India fall through to 0.4 and the report flags `soil.ec` as fabricated.

**Code path:**
- Data source: bundled raster [data/static/salinity_india.tif](data/static/salinity_india.tif), built by [scripts/dev_smoke/build_salinity_clip.py](scripts/dev_smoke/build_salinity_clip.py).
- Transformation: [src/jeevn/infrastructure/data_sources/soil.py](src/jeevn/infrastructure/data_sources/soil.py) (`SalinityRasterSampler.sample`).
- Outstream: `aoi_data["soil"]["properties"]["ec"]` + `salinity_class` + `salinity_label`; classified by `_classify_salinity` in [src/jeevn/domain/soil/management.py](src/jeevn/domain/soil/management.py) on EC thresholds `negligible <0.25 / low 0.25-0.75 / moderate 0.75-2.25 / high ≥2.25` dS/m; surfaces as `components.soil_management.salinity`. (Note the raster class→midpoint mapping above starts at 1.0 dS/m, so a class-0 field already classifies as `moderate`.)

---

### B.3 Soil Organic Carbon (SOC)

**What it is:** Mass percent of organic carbon in the bulk soil — a proxy for soil health, structure, CEC, water-holding.

**Scientific ideal:** Walkley-Black wet oxidation (chromic acid + back-titration) or dry combustion (LECO C analyser, ISO 10694). Dry combustion is the modern gold standard — accuracy ±0.05% C, traceable to NIST reference soils. Field rapid: NIR spectroscopy on dried soil + multivariate calibration.

**What this MVP does:** SoilGrids v2.0 `soc` property in g/kg → convert to mass % via `÷10`, depth-weighted to 0-30 cm. Fallback: 0.15%.

**Gap / when it breaks:** SoilGrids is modelled, not measured. Per-parcel real SOC can differ by ±0.5% absolute. Crop-specific status thresholds (apple: 1.0% min / 2.5% optimal, others: 0.8 / 2.0) come from ICAR rules of thumb, not calibration.

**Code path:**
- Data source: ISRIC SoilGrids in [src/jeevn/infrastructure/data_sources/soil.py](src/jeevn/infrastructure/data_sources/soil.py).
- Transformation: `_normalise_soc_to_percent` then classification in [src/jeevn/domain/soil/management.py](src/jeevn/domain/soil/management.py) (`_classify_organic_carbon`).
- Outstream: `organic_carbon_percent` + `organic_carbon_status` strings; drives the "incorporate FYM / compost / cover-crop" recommendation block.

---

### B.4 Soil texture (sand / silt / clay)

**What it is:** Mass fractions of the three particle-size classes — the basis for the USDA texture triangle.

**Scientific ideal:** Hydrometer (Bouyoucos) or pipette sedimentation method on chemically-dispersed soil per ISO 11277; modern: laser-diffraction particle-size analyser (Malvern Mastersizer). Accuracy ±2% per fraction. Then USDA-NRCS triangle for the class.

**What this MVP does:** SoilGrids v2.0 `sand`/`silt`/`clay` (mass %, depth-weighted to 0-30 cm) → fed into `classify_usda_texture(sand, silt, clay)` which approximates the 12-class USDA triangle with conditional branches. Fallback texture: `"loam"` from `pseudo_satellite`.

**Gap / when it breaks:** Triangle approximation can mis-classify boundary cases (e.g. sand=44 vs 45 swings between "sandy clay" and a different class). SoilGrids itself carries ±5% uncertainty per fraction. The downstream WHC/infiltration/field-capacity lookups (B.5-B.7) are coarser than this uncertainty, so it tends to wash out.

**Code path:**
- Data source: SoilGrids in [src/jeevn/infrastructure/data_sources/soil.py](src/jeevn/infrastructure/data_sources/soil.py).
- Transformation: `classify_usda_texture` (same file).
- Outstream: `properties.texture` + `sand_percent`/`silt_percent`/`clay_percent`; surfaces in the soil-management metric tile + texture caption.

---

### B.5 Water-Holding Capacity (WHC)

**What it is:** Plant-available water held between field capacity (-0.033 MPa) and wilting point (-1.5 MPa), expressed as mm of water per fixed soil depth.

**Scientific ideal:** Pressure-plate apparatus on undisturbed cores per USDA-NRCS NSSC Lab Method 3F1. Saturate the core, drain at -33 kPa for field capacity, then at -1500 kPa for wilting point. Subtract, multiply by depth × bulk density. Accuracy ±2 mm per 30 cm depth.

**What this MVP does:** Texture-class lookup table `_TEXTURE_WHC_MM_PER_30CM` in mm per 30 cm: `{sand: 6, loamy sand: 11, sandy loam: 17, loam: 23, silt loam: 29, … clay: 24}`. Drawn from USDA-NRCS field tables.

**Gap / when it breaks:** A coarse 12-bucket lookup vs the actual continuous response surface. Doesn't account for bulk density variation, structure, organic matter. Soils with high OM (>3%) hold considerably more water than the lookup suggests.

**Code path:**
- Data source: derived from texture in [src/jeevn/infrastructure/data_sources/soil.py](src/jeevn/infrastructure/data_sources/soil.py) (`whc_from_texture`).
- Transformation: same.
- Outstream: `properties.water_holding_capacity`; used by [src/jeevn/domain/soil/management.py](src/jeevn/domain/soil/management.py) for the "frequent irrigation needed / longer intervals OK" narrative.

---

### B.6 Infiltration rate

**What it is:** Steady-state rate at which water enters the soil surface, in mm/hour.

**Scientific ideal:** **Double-ring infiltrometer** (per ASTM D3385) — pond water in two concentric rings, measure the rate after equilibration. Or **disc tension infiltrometer** for unsaturated rates. Validated against soil-moisture sensors at several depths during the test.

**What this MVP does:** Texture-class lookup table `_TEXTURE_INFILTRATION_MM_PER_H`: `{sand: 35, sandy loam: 15, loam: 10, … clay: 1}`.

**Gap / when it breaks:** Same as WHC — coarse, ignores structure / compaction / OM. Real infiltration on a tilled-then-rained-on loam can be 3× lower than the lookup says due to surface sealing.

**Code path:**
- Data source: same as WHC, derived from texture.
- Transformation: `infiltration_from_texture` in [src/jeevn/infrastructure/data_sources/soil.py](src/jeevn/infrastructure/data_sources/soil.py).
- Outstream: `properties.infiltration_rate`; available to downstream calculators but not heavily used.

---

### B.7 Volumetric Field Capacity

**What it is:** Soil water content at -0.033 MPa matric potential, in m³/m³.

**Scientific ideal:** Pressure plate (see B.5), or in-situ TDR profile monitored 24-48 h after a fully-wetting event with no further input.

**What this MVP does:** Texture-class lookup `_TEXTURE_FIELD_CAPACITY_M3M3`: `{sand: 0.10, loam: 0.25, clay: 0.42}` (Saxton & Rawls approximate averages).

**Why this matters:** Used **specifically** to convert Open-Meteo's raw m³/m³ surface soil moisture into a `fraction-of-field-capacity` value. Without this conversion, raw 0.2-0.3 m³/m³ readings would trip the `<0.5` water-stress threshold in the yield-projection logic on a perfectly well-watered field.

**Code path:**
- Data source: texture (see B.4).
- Transformation: `field_capacity_from_texture` in [src/jeevn/infrastructure/data_sources/soil.py](src/jeevn/infrastructure/data_sources/soil.py).
- Outstream: consumed only inside the AOI composer [src/jeevn/infrastructure/data_sources/aoi.py](src/jeevn/infrastructure/data_sources/aoi.py) (around line 78-90) for the m³/m³ → fraction normalisation.

---

### B.8 Cation Exchange Capacity (CEC)

**What it is:** The soil's nutrient-holding capacity, in cmol(+)/kg.

**Scientific ideal:** Ammonium-acetate displacement at pH 7 (USDA-NRCS NSSC Method 4B1a) — saturate exchange sites with NH₄⁺, wash, displace with K⁺ or Na⁺, quantify by Kjeldahl. Accuracy ±1 cmol(+)/kg.

**What this MVP does:** SoilGrids v2.0 `cec` property, depth-weighted 0-30 cm. Classified into `low (<10) / moderate (10-25) / high (>25)` by [src/jeevn/domain/soil/management.py](src/jeevn/domain/soil/management.py) (`_classify_cec`).

**Gap / when it breaks:** SoilGrids CEC carries ±3-5 cmol(+)/kg uncertainty. Returns `None` (and the UI hides the row) when SoilGrids has no value for the centroid.

**Code path:**
- Data source: SoilGrids.
- Transformation: classification in [src/jeevn/domain/soil/management.py](src/jeevn/domain/soil/management.py).
- Outstream: `properties.cec` + `cec_status`; soil-management metric tile.

---

### B.9 Surface soil moisture (current)

**What it is:** Volumetric water content in the 0-7 cm layer.

**Scientific ideal:** In-situ TDR/FDR probes (Campbell CS650, Decagon 5TE) sampled at 5-min intervals at multiple depths. Or, from satellites: NISAR L-band SM at 100 m (works through canopy), SMAP at 9 km. Both validated against probe arrays.

**What this MVP does:** Open-Meteo's modelled `soil_moisture_0_to_7cm` hourly variable (m³/m³), averaged over the most recent 24 hours, then normalised by the texture-derived field capacity (B.7) to produce a 0-1 fraction-of-FC value that the agronomic thresholds expect.

**Gap / when it breaks:** Open-Meteo's SM is a reanalysis-derived model, not a sensor — accuracy varies by region. The texture normalisation hides real wet/dry signal when texture is fabricated. Fallback when Open-Meteo fails: `pseudo_satellite.SOIL_MOISTURE = 0.65`.

**Code path:**
- Data source: Open-Meteo archive API in [src/jeevn/infrastructure/data_sources/weather.py](src/jeevn/infrastructure/data_sources/weather.py) (hourly variable).
- Transformation: 24-hour mean in `_mean_of_last_n`, then normalisation in [src/jeevn/infrastructure/data_sources/aoi.py](src/jeevn/infrastructure/data_sources/aoi.py) (line 78-90).
- Outstream: `properties.soil_moisture_current` (fraction) + `soil_moisture_m3m3` (raw); drives water-stress branches in [src/jeevn/domain/growth_yield/projection.py](src/jeevn/domain/growth_yield/projection.py) and surfaces in the soil-management section.

---

### B.10 Bulk density

**What it is:** Oven-dry mass of soil per unit bulk volume, g/cm³ — needed to convert gravimetric/volumetric water contents into mm of water over a depth, and a structure/compaction indicator.

**Scientific ideal:** Undisturbed core method (USDA-NRCS NSSC Method 3B) — drive a known-volume ring, oven-dry at 105 °C, divide dry mass by ring volume. Or clod/excavation methods for stony soils. Accuracy ±0.02 g/cm³.

**What this MVP does:** SoilGrids v2.0 `bdod` property, depth-weighted to 0-30 cm (the SoilGrids int is divided by its `d_factor` like the other properties). Stored as `bulk_density` (rounded to 3 dp).

**Gap / when it breaks:** Fetched and stored, but currently only *informational* — the soil-water-deficit ideal (E.5) references bulk density in its formula, yet the active deficit scaffold and the field-capacity normalisation (B.7) use texture-class lookups rather than this value, so `bulk_density` doesn't feed any live calculation today. SoilGrids carries ±0.1 g/cm³ uncertainty.

**Code path:**
- Data source: ISRIC SoilGrids in [src/jeevn/infrastructure/data_sources/soil.py](src/jeevn/infrastructure/data_sources/soil.py) (`bdod` branch, ~line 257).
- Transformation: depth-weighted mean + d-factor, same as the other SoilGrids properties.
- Outstream: `properties.bulk_density`; available to downstream calculators but not consumed by the active flow. Fallback in `pseudo_satellite.DEFAULT_SOIL_PROPERTIES`.

---

## C. Terrain

### C.1 Elevation

**What it is:** Height above mean sea level (or above a chosen geoid).

**Scientific ideal:** **RTK GPS** survey (centimetre vertical accuracy) or airborne LiDAR (Riegl, Optech — decimetre absolute, centimetre relative). Photogrammetric DEMs from UAV imagery are intermediate.

**What this MVP does:** Three-tier:
1. **Open-Elevation API** (anonymous, SRTM-backed, ~30 m horizontal, ±5-10 m vertical) — centroid of a 3×3 grid.
2. **Bundled ETOPO 2022 30 arc-sec** (~1 km, ±10-30 m vertical) — India-clipped GeoTIFF in [data/static/dem_india.tif](data/static/dem_india.tif).
3. Fabricated 200 m default.

**Gap / when it breaks:** SRTM has voids in steep terrain; ETOPO is much coarser. Neither captures cm-scale field grading or terraces that actually matter for irrigation.

**Code path:**
- Data source: [src/jeevn/infrastructure/data_sources/terrain.py](src/jeevn/infrastructure/data_sources/terrain.py) — `OpenElevationClient.fetch_3x3_grid` (HTTP) or `LocalDEMSampler.fetch_3x3_grid` (rasterio).
- Transformation: just takes the centroid pixel (index 4 in the row-major 3×3).
- Outstream: `terrain.elevation_m`; surfaced as "elevation X m" in the irrigation narrative.

---

### C.2 Slope (rise/run %)

**What it is:** Steepness of the terrain surface, expressed as a percentage.

**Scientific ideal:** Direct measurement with an Abney level / clinometer on transects, or from a high-resolution DEM (≤ 5 m, LiDAR-derived) using Horn's method or Zevenbergen-Thorne. Accuracy ±0.5% on flat-to-moderate slopes.

**What this MVP does:** **Horn (1981) 3×3 kernel** — the standard GDAL/ArcGIS slope algorithm — applied to a 3×3 elevation grid. Open-Elevation samples at 30 m spacing (~1 SRTM pixel); ETOPO fallback at 1000 m. Formula:
```
dz/dx = ((c + 2f + i) − (a + 2d + g)) / (8 × cellsize)
dz/dy = ((g + 2h + i) − (a + 2b + c)) / (8 × cellsize)
slope_pct = 100 × √(dz/dx² + dz/dy²)
```

**Gap / when it breaks:** At ETOPO's 1 km cellsize the slope is averaged over a 3 km window — useless for detecting field-scale grading. SRTM resolution is fine for orchard-scale decisions.

**Code path:**
- Data source: see C.1.
- Transformation: [src/jeevn/infrastructure/data_sources/terrain.py](src/jeevn/infrastructure/data_sources/terrain.py) (`compute_slope_aspect`).
- Outstream: `terrain.slope_percent`; drives the irrigation method recommendation in [src/jeevn/application/narratives.py](src/jeevn/application/narratives.py) (`terrain_irrigation_advice`): <2% flat / 2-5% mild / >5% steep + terracing.

---

### C.3 Aspect (compass direction of steepest descent)

**What it is:** Direction the slope faces, 0-360° clockwise from north.

**Scientific ideal:** Same as slope — Horn 1981 on a high-resolution DEM. Used for insolation modelling (south-facing in NH gets ~20% more solar load).

**What this MVP does:** Horn 1981's aspect output, then bucketed into 8-point compass {N, NE, E, SE, S, SW, W, NW} with a "flat" bucket when slope < 0.5%.

**Code path:**
- Same as C.2; `aspect_degrees_to_compass` does the 8-point bucketing.
- Outstream: `terrain.aspect_compass`; appended to the irrigation narrative (south-facing → "schedule irrigation earlier in the morning").

---

## D. Weather

### D.1 Daily air temperature

**What it is:** Min / max / mean dry-bulb temperature at 2 m above ground.

**Scientific ideal:** **On-site Automatic Weather Station** (AWS) with a ventilated thermistor in a Stevenson screen at 2 m, logged at 1-minute intervals. WMO accuracy spec: ±0.2 °C. Calibrated against an ice-bath reference and a precision RTD.

**What this MVP does:** Open-Meteo archive API daily aggregates (`temperature_2m_{max,min,mean}`). Open-Meteo's archive blends ERA5 reanalysis with high-resolution downscaling (typically 9 km in India). Accuracy: ±1-2 °C against an in-situ AWS in most regions.

**Code path:**
- Data source: Open-Meteo in [src/jeevn/infrastructure/data_sources/weather.py](src/jeevn/infrastructure/data_sources/weather.py).
- Transformation: passthrough; arrays stored in `weather["daily"]["temp_{max,min,mean}"]`.
- Outstream: drives [src/jeevn/domain/irrigation/et0.py](src/jeevn/domain/irrigation/et0.py) (ET0 calculation) and [src/jeevn/domain/pest_disease_weed/assessment.py](src/jeevn/domain/pest_disease_weed/assessment.py) (pest temperature suitability).

---

### D.2 Precipitation

**What it is:** Daily total rainfall, mm.

**Scientific ideal:** Tipping-bucket or weighing-pluviometer rain gauge (Texas Electronics, OTT Pluvio) at the site, with windshield correction (gauges undercatch in wind). Accuracy: ±2% above 10 mm/day. Radar-corrected gauge networks (NEXRAD-style) are the regional-scale gold standard.

**What this MVP does:** Open-Meteo `precipitation_sum`. Model-based, so ±20-40% vs gauge in convective events. Two streams: the **archive** API (`fetch_weather`, historical, for context) and the **forecast** API (`fetch_forecast`, forward 7-day, with `precipitation_probability_max`) — the irrigation schedule uses the forecast stream so it can subtract *future* rain from *future* ETc.

**Code path:**
- Data source: `fetch_weather` (archive) for `weather.daily.rainfall`; `fetch_forecast` (forecast) for `forecast.daily.rainfall` + `rain_probability`.
- Outstream: forecast rainfall is subtracted (× 0.8 effective fraction) from each forecast day's ETc in E.4, and shown per-row in the schedule.

---

### D.3 Solar radiation

**What it is:** Shortwave radiation flux incident on a horizontal surface (MJ/m²/day).

**Scientific ideal:** **Pyranometer** (Kipp & Zonen CMP, Hukseflux) at the site, ventilated, with daily integration. WMO accuracy spec: ±5% daily. Calibrated against a reference cavity radiometer.

**What this MVP does:** Open-Meteo `shortwave_radiation_sum`. Used in ET0 calculation; if absent, ET0 falls back to a latitude+day-of-year computation of extraterrestrial radiation (Ra), which loses cloud/aerosol attenuation.

**Code path:**
- Data source: Open-Meteo.
- Transformation: optionally fed into Ra calculation in [src/jeevn/domain/irrigation/et0.py](src/jeevn/domain/irrigation/et0.py) (`_calculate_ra` is the fallback).
- Outstream: ET0 → ETc → irrigation schedule.

---

### D.4 Wind speed

**What it is:** Mean horizontal wind speed at 10 m above ground.

**Scientific ideal:** **Cup anemometer** or sonic anemometer at standard 10 m height, AWS-grade.

**What this MVP does:** Open-Meteo `windspeed_10m_max` (note: it's the daily *max*, not the mean — this is a small mismatch with the FAO-56 Penman-Monteith wind input which wants daily mean at 2 m).

**Gap / when it breaks:** Hargreaves-Samani (the ET0 method actually used — see E.1) **doesn't read wind** at all, so this mismatch doesn't affect the active code path. The wind variable is fetched but not consumed.

**Code path:**
- Data source: Open-Meteo.
- Outstream: stored in `weather["daily"]["wind_speed"]`; passed to `IrrigationScheduler` but unused in Hargreaves-Samani.

---

### D.5 Relative humidity

**What it is:** Near-surface relative humidity, % — a driver of pest/disease pressure and (indirectly) of pollination/disease yield penalties.

**Scientific ideal:** Direct measurement with a capacitive RH sensor (Vaisala HMP-series) in the same Stevenson screen as the thermometer, or derived from a measured dewpoint. WMO accuracy spec: ±3% RH.

**What this MVP does:** **Real, where available.** The weather adapter now fetches Open-Meteo hourly `relative_humidity_2m` and surfaces a last-24-hour mean as `daily.relative_humidity_mean` (m³/m³ is the soil-moisture analogue; RH is %). The pest/disease model and the yield-reduction model both consume that measured value. Only when the feed has no RH (fabricated-weather fallback) do they revert to the legacy proxy `humidity = min(100, 40 + rainfall×2 + (30 − temp_mean)×2)`, and the output is flagged `humidity_estimated: true`.

**Gap / when it breaks:** Open-Meteo RH is modelled (ERA5/ICON, ~9–25 km in India), not an on-site sensor, and is a 2 m air value — it does not capture in-canopy microclimate (the limitation the grape downy-mildew model is explicitly hedged against; see H.3). The proxy fallback remains crude (no physical basis) but now fires only when the whole weather section is already flagged fabricated.

**Code path:**
- Data source: Open-Meteo hourly `relative_humidity_2m` in [src/jeevn/infrastructure/data_sources/weather.py](src/jeevn/infrastructure/data_sources/weather.py) (archive + forecast); 24-h mean via `_mean_of_last_n`.
- Transformation: real-vs-proxy selection in [src/jeevn/domain/pest_disease_weed/assessment.py](src/jeevn/domain/pest_disease_weed/assessment.py) (`assess_pest_disease_risk`) and [src/jeevn/domain/growth_yield/projection.py](src/jeevn/domain/growth_yield/projection.py) (`_calculate_reduction_factors`).
- Outstream: feeds H.1/H.2/H.3 and I.1; surfaces as `environmental_conditions.humidity_estimate` + `humidity_estimated` (the UI/PDF label "Humidity" vs "Humidity (est.)" off the flag).

---

## E. Irrigation Math

### E.1 ET0 — Reference Evapotranspiration

**What it is:** Water-loss rate of a hypothetical short green crop with unlimited water — the baseline for any crop's water demand. Units: mm/day.

**Scientific ideal:** **FAO-56 Penman-Monteith** (Allen et al. 1998):
```
ET0 = [0.408 Δ (Rn − G) + γ (900/(T+273)) u₂ (es − ea)] / [Δ + γ(1 + 0.34 u₂)]
```
Requires: net radiation (Rn), soil heat flux (G, often ≈ 0 daily), wind at 2 m (u₂), saturation vapour pressure (es) and actual vapour pressure (ea, from RH or dewpoint), psychrometric constant (γ), slope of saturation curve (Δ). Validated against weighing lysimeters — the absolute gold standard for ET measurement.

**What this MVP does:** **Hargreaves-Samani** (1985), a temperature-only simplification:
```
ET0 = 0.0023 × Ra_mm × √(Tmax − Tmin) × (Tmean + 17.8)
```
Where `Ra_mm = _calculate_ra(lat, day_of_year) × 0.408` — extraterrestrial radiation computed from latitude + day-of-year (FAO-56 eq. 21 gives Ra in MJ/m²/day; ×0.408 converts to mm/day equivalent). It does **not** use measured surface radiation — that's the whole point of HS. Realistic hot semi-arid output ~5-7 mm/day.

**Gap / when it breaks:** Hargreaves-Samani is FAO-56's recommended fallback when full meteorology is missing. Typical bias: under-predicts ET0 by 5-15% in humid conditions, over-predicts in arid windy conditions. We have wind data but don't use it. Daily mean error: ±0.5 mm/day vs PM. Acceptable for scheduling, not for water-rights accounting. *(Historical bug, fixed 2026-05: the code briefly set `Ra = solar_radiation / 0.408` — inverting the MJ→mm factor AND substituting surface for extraterrestrial radiation — which inflated ET0 to ~23 mm/day.)*

**Code path:**
- Data source: per-forecast-day temperature from `aoi_data["forecast"]` (E.4), plus latitude from `aoi_data["location"]`.
- Transformation: [src/jeevn/domain/irrigation/et0.py](src/jeevn/domain/irrigation/et0.py) (`calculate_et0_hargreaves_samani`, `_calculate_ra`).
- Outstream: per-day ET0 → ETc → daily schedule; the 7-day average surfaces as `et0_mm_per_day` in the irrigation section header.

---

### E.2 Kc — Crop coefficient

**What it is:** Multiplier on ET0 to get crop-specific water demand, varies by growth stage.

**Scientific ideal:** **Stage-specific Kc curves measured by lysimeter on the cultivar of interest** in the local climate. FAO-56 publishes generic Kc curves; ICAR-CITH publishes apple-specific values for India. Best practice updates Kc daily from canopy cover or NDVI ("Kc from NDVI" via Bausch / Hunsaker linear relations).

**What this MVP does:** Hard-coded per-stage lookup × RVI adjustment:
```
base_kc = lookup(crop, growth_stage)          # FAO-56 table
adjusted_kc = base_kc × (0.8 + RVI × 0.4)
```
With RVI itself being NDVI × 1.08 (see A.4), this *is* the "Kc-from-NDVI" idea — but the constants `0.8 + RVI×0.4` aren't derived from a regression on this crop in this region.

**Code path:**
- Data source: lookup table + RVI from advisory service.
- Transformation: [src/jeevn/domain/irrigation/et0.py](src/jeevn/domain/irrigation/et0.py) (`calculate_kc`).
- Outstream: surfaces as the `kc` field in the irrigation schedule + PDF narrative.

---

### E.3 ETc — Crop evapotranspiration

**What it is:** Actual crop water demand under the current conditions, mm/day.

**Scientific ideal:** Direct measurement by lysimeter or eddy-covariance flux tower. Or modelled via dual-Kc FAO-56 (separate Kcb for transpiration and Ke for soil evaporation) for higher fidelity than single-Kc.

**What this MVP does:** `ETc = ET0 × Kc` (single-Kc FAO-56).

**Code path:**
- Transformation: [src/jeevn/domain/irrigation/et0.py](src/jeevn/domain/irrigation/et0.py) (`calculate_etc`).
- Outstream: `etc_mm_per_day` in the irrigation schedule.

---

### E.4 Irrigation schedule

**What it is:** A 7-day plan of when and how much to apply.

**Scientific ideal:** Real-time soil-moisture-triggered irrigation: continuous TDR probes at root depth, irrigate when SM drops below a refill threshold (typically field capacity − 50% of plant-available water). Drip systems with pressure-compensating emitters + flow-rate meters. Variable rate via prescription maps from NDVI/EM38 soil-EC surveys.

**What this MVP does:** **Rain-aware alternate-day drip.** For each of the next 7 forecast days: compute that day's ETc (E.1 × E.2) and subtract that day's *effective* forecast rain (`0.8 × forecast_rain_mm`, an USDA-SCS-style effective-rainfall fraction). `net = max(0, ETc − effective_rain)`. Irrigate on even days only when `net > 0.05 mm` — so a rainy day that already covers ETc gets no irrigation. Each row shows the real forecast rainfall (mm) + rain probability (%). Always recommends drip + 05:00-08:00 best time. Doesn't read soil moisture into the schedule (reported separately, doesn't gate events).

**Gap / when it breaks:** No SM trigger means irrigations can be scheduled even when the soil is already at field capacity from a prior event. The "alternate days" pattern is a heuristic — real schedules vary by emitter flow rate, plot size, and the previous irrigation's depth. The 0.8 effective-rain fraction is a flat approximation (real effective rainfall depends on intensity, soil intake, and antecedent moisture). *(Historical bug, fixed 2026-05: rain was divided by 1000 before subtraction — silently ignored — and net irrigation multiplied by 1000, producing ~7000 mm/day drip.)*

**Code path:**
- Data source: per-day ETc (E.1/E.2) + per-day forecast rain (D.2) from `aoi_data["forecast"]`.
- Transformation: [src/jeevn/domain/irrigation/scheduler.py](src/jeevn/domain/irrigation/scheduler.py) (`generate_schedule`).
- Outstream: `components.irrigation_schedule.daily_schedule[]` — 7 rows of drip/basin/sprinkler mm + real rainfall + rain% + an `evapotransp` demand label (`"High"` when that day's ETc > 6 mm, else `"Moderate"`); plus header-level total_water_mm + irrigation_days + forecast_rainfall_mm. PDF page 2 + Streamlit irrigation section.

---

### E.5 Soil water deficit

**What it is:** How much water (mm) needs to be added to bring the root zone back to field capacity.

**Scientific ideal:** From a continuously-monitored multi-depth SM profile:
```
deficit = Σ (FC_i − SM_i) × depth_i × bulk_density_i
```
summed over root depth. Or by soil-water-balance models like FAO-56 ETc with daily updating.

**What this MVP does:**
```
threshold = wilting_point + (FC − WP) × depletion_fraction
deficit_mm = max(0, (threshold − current_SM)) × 300
```
With hard-coded defaults `FC=0.25`, `WP=0.12`, `depletion_fraction=0.5`, depth=300 mm.

**Gap / when it breaks:** The function exists but **isn't called** by `IrrigationScheduler.generate_schedule` — it's there as scaffolding. The schedule uses ETc − rainfall instead of an SM-deficit trigger.

**Code path:**
- Transformation: [src/jeevn/domain/irrigation/et0.py](src/jeevn/domain/irrigation/et0.py) (`calculate_soil_water_deficit`).
- Outstream: dormant.

---

## F. Crop phenology & growth

### F.1 Current growth stage

**What it is:** Where the crop is in its life cycle — dormancy, bud-burst, flowering, fruit-set, etc.

**Scientific ideal:** **Visual scoring against the BBCH-scale** (Biologische Bundesanstalt, Bundessortenamt und CHemische Industrie) — standardised 00-99 codes per crop, scouted in the field at twice-weekly cadence. Or phenology cameras (PhenoCam network) for automated detection from canopy greenness time-series.

**What this MVP does:** Days-since-sowing + GDD walk through a hard-coded per-crop stage table (apple, wheat, and grape are populated; everything else falls back to wheat).
```
accumulated_gdd = Σ max(0, daily_temp_mean − t_base)
walk stages in order, accumulate days+gdd; the first stage whose cumulative ≥ accumulated_gdd is "current"
```

**Gap / when it breaks:** Date-driven, not observation-driven. Will say "flowering" on the canonical date even if the orchard is actually 10 days late. Three-crop database (apple/wheat/grape) — anything else is treated as wheat. The grape calendar is anchored to forward (fruit) pruning, not sowing, so `days_since_sowing` must be days-since-pruning for grape.

**Code path:**
- Data source: sowing date (user input or default), temp_mean series from Open-Meteo, crop_name.
- Transformation: GDD accumulation in [src/jeevn/infrastructure/data_sources/aoi.py](src/jeevn/infrastructure/data_sources/aoi.py) (line 122-129); stage walk in [src/jeevn/domain/crop/phenology.py](src/jeevn/domain/crop/phenology.py) (`CropPhenologyDatabase.get_current_growth_stage`).
- Outstream: `current_growth_stage.{stage, kc, ndvi_range, days_in_stage, gdd_in_stage}` → feeds every downstream calculator.

---

### F.2 Growing Degree Days (GDD)

**What it is:** Cumulative thermal time above a crop-specific base temperature.

**Scientific ideal:** Hourly temperature with a sine-curve correction for the diurnal cycle, capped at an upper threshold (`max_temp`) where development slows. Modified GDD method (Baskerville-Emin).

**What this MVP does:** Simple daily-mean method: `GDD_d = max(0, T_mean − t_base)`, summed over the available daily series. No upper cap.

**Code path:**
- Data source: temp_mean from weather adapter.
- Transformation: [src/jeevn/infrastructure/data_sources/aoi.py](src/jeevn/infrastructure/data_sources/aoi.py) (line 125-129).
- Outstream: `accumulated_gdd` in the report; drives the phenology walk in F.1.

---

### F.3 NDVI time-series trend

**What it is:** Whether the canopy is growing, stable, or declining.

**Scientific ideal:** **BFAST** (Break detection For Additive Season and Trend) or **CCDC** (Continuous Change Detection and Classification) — harmonic decomposition that separates seasonal, trend, and disturbance components. Statistically rigorous, used in operational forest-change products.

**What this MVP does:** Linear regression slope over the timeseries (`Σ(x−x̄)(y−ȳ) / Σ(x−x̄)²`), bucketed: `>0.02 strong / >0.005 moderate / >−0.005 stagnant / >−0.02 moderate decline / else severe decline`.

**Gap / when it breaks:** Mixes seasonal variation with trend — a fading harvest signal looks like "decline". Needs at least 2 points; doesn't handle gaps.

**Code path:**
- Data source: `ndvi_timeseries` from the remote-sensing pipeline.
- Transformation: [src/jeevn/domain/growth_yield/monitoring.py](src/jeevn/domain/growth_yield/monitoring.py) (`analyze_growth_trajectory`).
- Outstream: `components.growth_trajectory.{trend, trend_slope, current_ndvi, ndvi_range, mean_ndvi, data_points, recommendation}` (the descriptive `current_ndvi`/`mean_ndvi`/`ndvi_range` are simple summary stats over the same series).

---

### F.4 Growth-stage timing assessment

**What it is:** A verdict on whether the crop is *on schedule*, *ahead*, or *behind* for its current phenological stage — "On schedule" / "Early by N days (delayed development)" / "Late by N days (accelerated development)".

**Scientific ideal:** Compare observed BBCH stage dates (F.1) against a GDD- or date-anchored expectation derived from the local long-term climatology for the cultivar, ideally with a confidence interval on the expected window.

**What this MVP does:** Compares `days_since_sowing` against a hard-coded per-stage day-range table (apple, wheat, grape; everything else falls back to wheat). If inside the window → "On schedule"; before it → "Early by …"; after it → "Late by …". Note the label wording is slightly counter-intuitive: being *before* the expected window is called "Early … (delayed development)" and *after* is "Late … (accelerated development)".

**Gap / when it breaks:** The day-ranges are fixed calendars, not GDD-driven, so the assessment double-counts the same date-vs-observation weakness as F.1. Two-crop table. The label semantics are easy to misread.

**Code path:**
- Data source: `days_since_sowing` + the current `stage` from F.1.
- Transformation: [src/jeevn/domain/growth_yield/projection.py](src/jeevn/domain/growth_yield/projection.py) (`_assess_growth_stage`, line ~101, with the `stage_timing` table).
- Outstream: `components.growth_yield.growth_stage_assessment`.

---

## G. Fertilizer

### G.1 Nutrient gap (N / P / K / S / Zn)

**What it is:** Per-nutrient difference between current soil level and what the crop needs.

**Scientific ideal:** Combined approach:
1. **Soil test** — pre-season Mehlich-3 or Olsen-P extraction; KCl-N; CaCl₂-K. Calibrated against crop response trials.
2. **Plant tissue test** — mid-season leaf analysis (ICP-OES on dried leaves) for in-season adjustment.
3. **Crop removal calculation** — yield × nutrient concentration in harvest.
4. **Balance equation:** gap = (yield_target × removal_factor + losses) − (soil_supply + atmospheric_deposition + mineralisation).

**What this MVP does:**
```
current_levels = HARD_CODED {"N": 13.65, "P": 11.0, "K": 82.0, "S": 7.0, "Zn": 0.8}     # placeholder
target = crop_data.nutrient_requirements[nut]["optimal"]   # from phenology table
adjusted_target = target × (0.8 + RVI × 0.4)
gap = max(0, adjusted_target − current)
status = critical | moderate | adequate based on current/target ratio
```

**Gap / when it breaks:** **Current soil levels are hard-coded, not measured.** Every parcel gets the same `N=13.65`. The system effectively recommends fertiliser based on the crop target alone, with RVI as the only parcel-specific input. This is a placeholder until a soil-test ingest lands. Also note the **nutrient set is crop-dependent**: the apple and grape phenology tables define all five (N/P/K/S/Zn), but the wheat table defines only N/P/K — so S and Zn gaps are simply never computed for wheat (and for any crop that falls back to wheat).

**Code path:**
- Data source: hard-coded dict in [src/jeevn/domain/fertilizer/requirements.py](src/jeevn/domain/fertilizer/requirements.py) (line 27-33). Target from crop phenology in [src/jeevn/domain/crop/phenology.py](src/jeevn/domain/crop/phenology.py).
- Transformation: same file, `calculate_nutrient_requirements`.
- Outstream: `components.fertilizer_management.nutrient_requirements.{N,P,K,S,Zn}` — current / target / gap / status. Fertilizer table on PDF page 5 + Streamlit fertilizer section.

---

### G.2 Fertilizer product schedule

**What it is:** Specific products (Urea, DAP, SOP, …) + per-acre quantities + application method.

**Scientific ideal:** **4R Nutrient Stewardship** (Right source, Right rate, Right time, Right place) per IPNI: split-application of N matched to crop uptake curves; banded or fertigated P near roots; soil-test-derived rates; tissue-test mid-season adjustments. Plus 4R refinements for variable-rate based on yield-zone maps.

**What this MVP does:** Four distinct per-crop branches (apple, wheat, grape, generic), each converting a per-nutrient gap to product mass by nutrient %. **The branches do not share a formula — they make different chemistry assumptions:**

*Apple* (`_get_apple_recommendations`) — fertigation-oriented, splits P and K across a soluble + an organic source, and is the only branch that handles S and Zn:
```
urea_kg      = N_gap / 0.46                 # Urea 46% N
dap_kg       = (P_gap × 0.7) / 0.46         # 70% of P from DAP (treated as 46%)…
bone_meal_kg = (P_gap × 0.3) / 0.03         # …30% from Bone Meal (3% P)
sop_kg       = (K_gap × 0.7) / 0.50         # 70% of K from SOP (50% K2O)…
wood_ash_kg  = (K_gap × 0.3) / 0.05         # …30% from Wood Ash (5% K)
bentonite_kg = S_gap  / 0.90                # Bentonite Sulphur 90% S
zn_sulph_kg  = Zn_gap / 0.21                # Zinc Sulphate 21% Zn
+ fixed Enriched FYM (55 kg) and Vermicompost (N_gap / 0.015)
```

*Wheat* (`_get_wheat_recommendations`) — broadcast/top-dress, no organic split, no S/Zn, and a **different DAP and K basis** than apple:
```
urea_base = urea_top = (N_gap × 0.5) / 0.46  # split 50% pre-sow / 50% at tillering
dap_kg    = P_gap / 0.20                      # DAP treated as 20% P here (vs 46% for apple)
mop_kg    = K_gap / 0.60                      # MOP (Muriate of Potash), not SOP
```

*Grape* (`_get_grape_recommendations`) — fully fertigated, handles all five nutrients like apple but K-weighted to berry-development/veraison; **uses SOP not MOP** (grapes are chloride-sensitive) and delivers Zn **foliar** (grapes are prone to little-leaf Zn deficiency). Tops up S only beyond what SOP's 18% S already supplies.

*Generic* (`_get_generic_recommendations`) — fallback for any other crop: one "Generic source" line per nutrient at `quantity = gap` (no product chemistry at all).

**Gap / when it breaks:** The same P gap yields different DAP masses for apple vs wheat because the two branches assume different DAP grades (46% vs 20%) — an internal inconsistency, not a calibrated agronomic choice. Wheat's missing S/Zn ties back to G.1's crop-dependent nutrient set.

**Code path:**
- Data source: gap from G.1; branch selected by crop name (anything not apple/wheat/grape → generic).
- Transformation: [src/jeevn/domain/fertilizer/schedule.py](src/jeevn/domain/fertilizer/schedule.py) (`_get_apple_recommendations`, `_get_wheat_recommendations`, `_get_grape_recommendations`, `_get_generic_recommendations`).
- Outstream: `recommended_products[]` → fertilizer table + recommended-products expander on PDF page 5.

---

## H. Pest, disease, weed

### H.1 Pest / disease risk score

**What it is:** A 0-100% score for each known threat to the crop.

**Scientific ideal:** **Degree-day pest-forecasting models** (e.g. Welch et al. for codling moth) — accumulate insect-specific GDD from biofix dates; combined with **trap counts** (pheromone traps logged 2-3× weekly) and **field scouting** (whole-plant inspection on a stratified sample). Disease forecasters layer in leaf wetness duration (e.g. Mills curves for apple scab).

**What this MVP does:** This is the **generic susceptibility heuristic** used for apple/wheat (and any crop without a dedicated model). Grape powdery/downy mildew are no longer scored here — they have published weather-driven models in H.2/H.3. The heuristic is a weighted 0-100 score per pest:
```
score = 40% × temp_suitability(temp_mean, temp_range_for_pest)
      + 35% × humidity_impact(humidity, pest.humidity_preference)
      + 25% × stage_susceptibility[current_stage]
```
Risk levels: `high ≥ 70, moderate ≥ 40, low < 40`.

**Two changes from the original heuristic:** (1) **RVI was dropped** — canopy vigour previously contributed 25% of disease risk, which is agronomically unjustified; the remaining temp/humidity/stage weights were rescaled (40/35/25). (2) **Humidity is now the real measured RH** (D.5) when the feed provides it; the `40 + rainfall×2…` proxy is only the fabricated-weather fallback (flagged `humidity_estimated`).

**Gap / when it breaks:** Still a static susceptibility heuristic — no degree-day biofix, no trap counts, no leaf-wetness, no forward forecast window. Pest database has 4 apple, 1 wheat, and 3 grape entries (one of which, the mealybug, uses this heuristic; the two mildews use H.2/H.3).

**Code path:**
- Data source: weather (D.1/D.2/D.5), growth_stage. (RVI no longer read here.)
- Transformation: [src/jeevn/domain/pest_disease_weed/assessment.py](src/jeevn/domain/pest_disease_weed/assessment.py) (`_calculate_pest_disease_risk` + the `PEST_DATABASE` dict).
- Outstream: `components.pest_disease_weed.pests_diseases[].{name, risk_percent, risk_level, organic_solution, chemical_solution}` — PDF page 4 + Streamlit pest section.

---

### H.2 Powdery mildew — Gubler-Thomas index (grape)

**What it is:** A confident, weather-driven spray-window risk for grape powdery mildew (*Erysiphe necator*).

**Scientific ideal:** The **UC Davis Gubler-Thomas Risk Index** (a peer-reviewed model) — powdery mildew is temperature-driven (rain suppresses it), so a published hourly-temperature model needs no leaf-wetness or microclimate sensor. This is the disease where a regional 9–11 km grid is genuinely adequate at block scale (see the go/no-go in the plan history).

**What this MVP does:** Faithful Gubler-Thomas, computed from Open-Meteo **hourly temperature**: a day *qualifies* if it has ≥6 continuous hours in 21–30 °C; 3 consecutive qualifying days initiate the index at 60; thereafter +20 per qualifying day, −10 per non-qualifying day, additional −10 on any day reaching ≥35 °C; index clamped 0–100. Maps to `high ≥ 60 (14-day spray), moderate ≥ 30 (17-day), low (21-day)`. Prefers the forward forecast hourly series (actionable this-week window), falls back to recent archive.

**Gap / when it breaks:** Open-Meteo temperature is modelled, not on-site; the index assumes the published thresholds without local calibration; omitted entirely (not fabricated) when no hourly feed is available.

**Code path:**
- Data source: Open-Meteo hourly `temperature_2m` (forecast preferred) via [src/jeevn/infrastructure/data_sources/weather.py](src/jeevn/infrastructure/data_sources/weather.py).
- Transformation: [src/jeevn/domain/crop_health/disease_models.py](src/jeevn/domain/crop_health/disease_models.py) (`gubler_powdery_mildew_index`); dispatched from `assessment.py` (`_assess_model_disease`) for `PEST_DATABASE["grape"]` entries flagged `model: "gubler_powdery"`.
- Outstream: `pests_diseases[]` entry with `{model, risk_percent (=index), risk_level, spray_interval_days, rationale}`.

---

### H.3 Downy mildew — wet-period flag (grape, hedged)

**What it is:** A deliberately **hedged** "conditions favorable — scout/confirm" flag for grape downy mildew (*Plasmopara viticola*), never a direct spray instruction.

**Scientific ideal:** Downy mildew is **leaf-wetness-driven** (sporulation/infection need free water or ≥95% RH at 13–30 °C). Leaf wetness is a *microclimate* variable; the gold-standard input is an in-canopy leaf-wetness sensor feeding a mechanistic model (Goidanich/EPI/DMCast). Open-Meteo has no leaf-wetness variable and Indian RH/rain are only ~9–25 km — so a regional feed can only *approximate* this (the explicit limitation from the go/no-go).

**What this MVP does:** From Open-Meteo hourly temp/RH/precip: detect the longest consecutive **wet period** (RH ≥ 90% or precip > 0.2 mm/h) with temperature in the 13–30 °C infection band; flag favorable if that run ≥ 4 h, or if a day meets the **3-10 primary-infection rule** (≥10 mm rain at ≥10 °C, shoots ≥10 cm when known). Risk `high` for a long optimal wet period or a primary-rule day, else `moderate`/`low`. Every output carries `confidence: "regional-proxy"` and scout/confirm language.

**Gap / when it breaks:** RH is a *proxy* for leaf wetness, not a measurement — this is precisely where on-farm IoT sensors (the incumbents' moat) beat satellite + regional weather. The flag can cry-wolf (regional rain that missed the block) or miss local dew events. Treated as advisory-only; omitted when no hourly feed.

**Code path:**
- Data source: Open-Meteo hourly `temperature_2m` / `relative_humidity_2m` / `precipitation` (forecast preferred).
- Transformation: [src/jeevn/domain/crop_health/disease_models.py](src/jeevn/domain/crop_health/disease_models.py) (`downy_mildew_wet_period_risk`); dispatched for `PEST_DATABASE["grape"]` entries flagged `model: "downy_wet_period"`.
- Outstream: `pests_diseases[]` entry with `{model, risk_percent, risk_level, favorable, confidence, rationale}`.

---

### H.4 Weed risk score

**What it is:** Likelihood of weed pressure during the current period.

**Scientific ideal:** **Emergence models** (e.g. WeedCast, AlertInf) per weed species — degree-day-driven emergence prediction conditioned on soil moisture + tillage history + seedbank surveys. Plus aerial / UAV imagery for in-field weed-patch mapping.

**What this MVP does:**
```
score = 40 × ((rsm − moisture_trigger) / (1 − moisture_trigger))   # if rsm > trigger
      + min(20, rainfall/20 × 20)
      + 40 × (1 − rvi_impact(rvi))                                  # per-weed lambda
```
Risk: `high ≥ 60, moderate ≥ 35`. RSM is constant 0.72 (see A.5), so the first term is effectively constant.

**Code path:**
- Transformation: [src/jeevn/domain/pest_disease_weed/assessment.py](src/jeevn/domain/pest_disease_weed/assessment.py) (`_calculate_weed_risk`).
- Outstream: `components.pest_disease_weed.weeds[]`.

---

## I. Yield projection

### I.1 Projected yield per acre

**What it is:** Expected harvest, kg/acre, given current conditions.

**Scientific ideal:** **Process-based crop simulation models** — DSSAT, APSIM, WOFOST — that integrate weather, soil, cultivar parameters, management, and pest pressure across the season. Calibrated against multi-year multi-site field trials. Output includes uncertainty bands. Or empirically: **machine-learning yield-NDVI regression** trained on regional harvest data with covariates (temp, GDD, rainfall).

**What this MVP does:**
```
adjusted_yield = yield_potential × ∏(1 − reduction_i/100)
```
where `yield_potential` comes from `phenology.CROP_DATA[crop]["yield_potential_kg_per_acre"]` (apple: 2500, wheat: 3650, grape: 10000), and `reduction_i` is a fixed-percentage hit from each limiting factor detected:
- RVI<0.60 → 15% nutrient deficiency; <0.70 → 8%
- High humidity in flowering/fruit_set → 10% pest/disease
- Soil moisture < 0.50 → 20% water stress; <0.60 → 5%
- Flowering + RVI<0.60 → 5% poor pollination
- Apple + RVI<0.70 → 5% reduced canopy

From `adjusted_yield` the projection also derives three headline numbers: `yield_potential_total_kg = yield_potential × area`, `total_yield_kg = adjusted_yield × area`, and `potential_loss_percent = (yield_potential − adjusted_yield) / yield_potential × 100`. Separately, `harvest_status` (`_determine_harvest_status`) maps the current stage + `days_since_sowing` against a per-crop maturity window (apple 275-305 d, wheat 125-135 d, grape 145-160 d, else 100-150 d) to `ready / incomplete / overripe`.

**Gap / when it breaks:** Multiplicative penalties on a fixed potential — no representation of the *timing* of stress (a 5-day water stress at flowering vs at maturity matters very differently). Yield potential is a single number per crop, not cultivar/zone-specific. `harvest_status` is purely calendar-driven (same date-vs-observation weakness as F.1/F.4), so it can read "ready" on a crop that is actually behind.

**Code path:**
- Data source: NDVI/RVI from advisory, soil moisture from soil composer, weather from Open-Meteo, crop from phenology.
- Transformation: [src/jeevn/domain/growth_yield/projection.py](src/jeevn/domain/growth_yield/projection.py) (`calculate_yield_projection`, `_calculate_reduction_factors`).
- Outstream: `components.growth_yield.{yield_per_acre_kg, total_yield_kg, potential_loss_percent, limiting_factors[], harvest_status, vegetation_vigor}` — PDF page 3 metric tiles.

---

### I.2 Vegetation vigor rating

**What it is:** Qualitative grade — Excellent / Good / Moderate / Poor / Very Poor.

**Scientific ideal:** Calibrated against field-measured LAI or canopy cover. Or simply NDVI normalised against the crop-stage expected range from the phenology table.

**What this MVP does:**
```
rating = "Excellent" if rvi ≥ 0.75 else "Good" if ≥0.65 else "Moderate" if ≥0.50 else "Poor" if ≥0.35 else "Very Poor"
score = 95 / 80 / 60 / 35 / 15 — then × 0.85 if NDVI below stage range, × 0.9 if above
```

**Code path:**
- Transformation: [src/jeevn/domain/growth_yield/projection.py](src/jeevn/domain/growth_yield/projection.py) (`_assess_vegetation_vigor`).
- Outstream: `vegetation_vigor` + `vegetation_vigor_score`.

---

### I.3 Yield proxy (NDVI-based)

**What it is:** A standalone yield estimate from the NDVI timeseries alone, in t/ha.

**Scientific ideal:** Multi-year multi-site regression of cumulative-NDVI (or NDVI-integral over the growing season) against measured harvest, separated by cultivar and management. R² typically 0.5-0.8 for cereals.

**What this MVP does:**
```
base_yield = 2.0 + cumulative_ndvi × 0.5 + peak_ndvi × 3.0
estimated_yield_t_ha = clip(base_yield, 0.5, 12.0)
```
Hand-tuned coefficients, no calibration.

**Code path:**
- Transformation: [src/jeevn/remote_sensing/analysis/detections.py](src/jeevn/remote_sensing/analysis/detections.py) (`yield_proxy`).
- Outstream: `anomalies.yield_proxy` in the `/aoi` response — informational only; the headline yield in the advisory is I.1.

---

## J. Stress & anomaly detections

### J.1 Water stress

**What it is:** Whether the canopy is showing water-stress symptoms.

**Scientific ideal:** **Crop Water Stress Index** (CWSI, Idso 1981): `(Tc − Ta) − (Tc − Ta)_lower_baseline / ((Tc − Ta)_upper − (Tc − Ta)_lower)` from thermal-IR canopy temperature. Or stomatal conductance via porometer. Best satellite proxy: thermal bands (Landsat ST_B10, ECOSTRESS).

**What this MVP does:**
```
water_stress = 0.6 × (1 − max(0, NDVI)) + 0.4 × (1 − max(0, NDWI))
```
plus a flag `irrigation_stress_flag(ndvi < 0.4 or lst > 35)`. There is no LST source; the lst check never fires.

**Code path:**
- Transformation: [src/jeevn/remote_sensing/analysis/signals.py](src/jeevn/remote_sensing/analysis/signals.py) (`water_stress_score`, `irrigation_stress_flag`).
- Outstream: `anomalies.water_stress` + `anomalies.irrigation_stress` in the `/aoi` response.

---

### J.2 Nutrient stress

**What it is:** Whether the canopy shows nitrogen-deficiency symptoms.

**Scientific ideal:** **Leaf SPAD-502** chlorophyll readings, calibrated against in-house leaf-N tissue tests. Or hyperspectral indices (REIP, MCARI). Best satellite proxy: NDRE-based indices.

**What this MVP does:**
```
ratio = NDRE / NDVI
stress = clip(1 - (ratio - 0.2)/0.6, 0.05, 0.95)
```

**Code path:**
- Transformation: [src/jeevn/remote_sensing/analysis/signals.py](src/jeevn/remote_sensing/analysis/signals.py) (`nutrient_stress_score`).
- Outstream: `anomalies.nutrient_stress`.

---

### J.3 NDVI anomaly

**What it is:** Time-series points that depart from the seasonal norm.

**Scientific ideal:** **BFAST** / **CCDC** harmonic decomposition (see F.3). Flags formal change-points with p-values.

**What this MVP does:** Two-tier:
1. If `mean(NDVI) < 0.3` → low_ndvi anomaly.
2. Else if any step-down > 0.3 → rapid_decline anomaly.
3. Separately, z-score with **modified-z MAD fallback** for per-point anomaly flags.

**Code path:**
- Transformation: [src/jeevn/remote_sensing/analysis/signals.py](src/jeevn/remote_sensing/analysis/signals.py) (`ndvi_anomaly`, `z_score_anomaly`, `persistent_stress_detection`).
- Outstream: `anomalies.{ndvi_anomaly, persistent_stress, z_score_anomalies}`.

---

### J.4 Disease patch detection

**What it is:** Spatial / temporal pattern that suggests disease.

**Scientific ideal:** Hyperspectral imaging from UAVs (Photochemical Reflectance Index, Anthocyanin Reflectance Index) — disease-specific spectral signatures, validated against pathology lab cultures.

**What this MVP does:** Walks the timeseries and compares each point with the one **two steps later** (`ndvi[i]` vs `ndvi[i+2]`, not a rolling/averaged window) — a decline greater than 0.2 anywhere flags disease. Returns `disease_detected: bool` + a `risk_score = clip(max_decline / 0.3, 0, 1)` with a `0.02-0.08` jitter floor.

**Gap / when it breaks:** A pure NDVI-decline signal — can't distinguish disease from drought, frost, or harvest. The `np.random.uniform(0.02, 0.08)` jitter floor makes the output non-deterministic, which is a quirk worth flagging.

**Code path:**
- Transformation: [src/jeevn/remote_sensing/analysis/detections.py](src/jeevn/remote_sensing/analysis/detections.py) (`disease_patch_detection`).
- Outstream: `anomalies.disease_patch`.

---

### J.5 Canopy texture metrics

**What it is:** Spatial heterogeneity of the canopy — uniform vs patchy.

**Scientific ideal:** **GLCM** (Gray-Level Co-occurrence Matrix) features per Haralick — contrast, dissimilarity, homogeneity, entropy, energy, correlation, ASM. Standard in remote-sensing texture analysis.

**What this MVP does:** Two metrics:
- `local_std(data, k=3)` — scipy `generic_filter(std, …)`, with a pure-Python sliding-window fallback.
- `local_entropy(data, k=3)` — Shannon entropy on a 10-bin histogram over [0, 1].

**Gap / when it breaks:** Not GLCM. Std and 1D-histogram-entropy are coarser than the Haralick suite and don't capture orientation / co-occurrence at all.

**Code path:**
- Transformation: [src/jeevn/remote_sensing/analysis/texture.py](src/jeevn/remote_sensing/analysis/texture.py).
- Outstream: `anomalies.texture.{mean_std, mean_entropy}`; entropy feeds `weeds_guidance` (J.6).

---

### J.6 Weed pressure (texture-based)

**What it is:** Hint at heterogeneous canopy structure suggesting weed patches.

**Scientific ideal:** UAV multispectral imagery + segmentation networks (Mask R-CNN trained on labelled weed patches). Or in-row vs between-row reflectance contrast.

**What this MVP does:** `pressure_score = clip((entropy − 1.0) / 3.0, 0.05, 0.95)` with a low-pressure halving when NDVI > 0.75 and entropy is low (dense uniform canopy → weeds suppressed).

**Code path:**
- Transformation: [src/jeevn/remote_sensing/analysis/detections.py](src/jeevn/remote_sensing/analysis/detections.py) (`weeds_guidance`).
- Outstream: `anomalies.weeds_guidance.{weed_pressure_score, guidance}`.

---

### J.7 Fertilizer issue (early-season growth deficit)

**What it is:** Whether the crop is growing sluggishly in early season, suggesting a base nutrient issue.

**Scientific ideal:** Early-season tissue testing + soil-test response — but really, this is what fertiliser-rate trials are for.

**What this MVP does:**
```
early_growth = max(0, mid_ndvi - early_ndvi)
growth_deficit = max(0, 0.3 - early_growth)
fert_score = clip(growth_deficit / 0.3 × (1 - late_ndvi × 0.2), 0.05, 0.95)
```
Flagged if `fert_score > 0.7`.

**Code path:**
- Transformation: [src/jeevn/remote_sensing/analysis/detections.py](src/jeevn/remote_sensing/analysis/detections.py) (`fertilizer_issue_detection`).
- Outstream: `anomalies.fertilizer_issue`.

---

### J.8 SAR moisture index

**What it is:** Backscatter-derived surface soil-moisture proxy.

**Scientific ideal:** Physical SAR inversion (Oh 2004, IEM, Dubois) on multitemporal terrain-flattened σ° stacks, validated against in-situ TDR / FDR probes.

**What this MVP does:** **No real SAR.** `np.random.uniform(0.1, 0.5, (3, 10, 10))` synthetic stack → `sar_moisture_index = median(stack, axis=0) / max(median)`. Placeholder until NISAR L-band ingest lands (TASKS.md #4).

**Code path:**
- Data source: synthetic random (placeholder).
- Transformation: [src/jeevn/remote_sensing/analysis/sar.py](src/jeevn/remote_sensing/analysis/sar.py) (`sar_moisture_index`); wired in [src/jeevn/remote_sensing/pipeline.py](src/jeevn/remote_sensing/pipeline.py) (`analyze_signals`, line 99-101).
- Outstream: `anomalies.sar_moisture_index`.

---

## K. Geography & area

### K.1 AOI centroid

**What it is:** Representative (lat, lon) for the AOI — the point all geo-keyed data fetches use.

**Scientific ideal:** Geodesic centroid of the polygon on the WGS-84 ellipsoid (shapely's `unary_union(...).centroid` after projection to an equal-area CRS).

**What this MVP does:** Simple mean of polygon-ring coordinates in lat/lon degrees: `(sum(lats)/N, sum(lons)/N)`. Fast, fine for small parcels, off for elongated or large polygons.

**Code path:**
- Transformation: [src/jeevn/ui/geo_utils.py](src/jeevn/ui/geo_utils.py) (`extract_centroid`).
- Outstream: passed to the advisory request as `latitude` / `longitude`.

---

### K.2 AOI area

**What it is:** Polygon area in acres.

**Scientific ideal:** Project to an equal-area projection appropriate to the latitude (UTM zone, Cylindrical Equal Area, or Albers for mid-latitudes), compute area, convert to acres. Or use the geodesic algorithm in PROJ's `geod_polygonarea` for direct ellipsoidal area.

**What this MVP does:** **Planar shoelace formula on lat/lon degrees directly**, then `area_deg2 × 12321 × 247.105` (deg² → km² → acres). Clamped to [0.1, 50000]. The constant 12321 ≈ 111² is a single-latitude approximation that breaks down for polygons at high latitudes or large extents.

**Gap / when it breaks:** Fine for small (< 1 km) parcels in mid-latitudes; over-estimates by ~20% at 60°N, under-estimates near the equator. Don't trust for water-rights-grade accounting.

**Code path:**
- Transformation: [src/jeevn/ui/geo_utils.py](src/jeevn/ui/geo_utils.py) (`estimate_area_acres`).
- Outstream: `area_acres` in the advisory request, surfaces in `aoi_info.area_acres` and the header banner.

---

### K.3 Reverse geocoding (location name)

**What it is:** Mapping (lat, lon) → human-readable place name (village, state, country).

**Scientific ideal:** **National cadastral / parcel records** — in India, the BHOOMI / Dharani / NLRMP land-records databases per state. Or, for general place-name purposes, **commercial geocoders** (Mapbox, Google) with formal SLAs.

**What this MVP does:** **Nominatim** (OpenStreetMap's free reverse-geocoding service). Required custom User-Agent. Locality tried in priority order: `city → town → village → hamlet → suburb → county`.

**Gap / when it breaks:** Nominatim has 1 req/sec rate limit on the public endpoint. Rural Indian polygons frequently lack a `city` and only have `state_district` — covered by the fallback chain. No cadastral parcel info.

**Code path:**
- Data source: [src/jeevn/infrastructure/data_sources/geocoding.py](src/jeevn/infrastructure/data_sources/geocoding.py) (`GeographicDataFetcher.get_location_info`).
- Transformation: locality key fallback.
- Outstream: `aoi_data.location.{name, city, state, country, display_name}` → report header banner.

---

## L. Data-quality / fabrication tracking

**What it is:** Recording which inputs to the report were real vs default, and warning the user accordingly.

**Scientific ideal:** Formal uncertainty propagation — every measurement carries an σ; downstream calculations propagate via partial derivatives or Monte Carlo; outputs carry ±bands. The user sees both the value and its uncertainty.

**What this MVP does:** Per-field boolean: each adapter sets `_fabricated: True` (or per-property `_fabricated_fields: {k: bool}`) when it falls back to a default. The AOI composer in [src/jeevn/infrastructure/data_sources/aoi.py](src/jeevn/infrastructure/data_sources/aoi.py) hoists them into a single top-level `_fabricated_sources` list. The advisory service merges with NDVI fabrication flags, attaches human descriptions from `pseudo_satellite.describe(field)`, and emits `data_quality.fabricated_fields` + `details` + `alerts` + `warning` in the report.

Plus a special-case structured alert (`_aoi_in_built_up_land`) when SoilGrids returns all-null at the centroid — the UI shows a red banner with "redraw the polygon over actual cropland".

**Code path:**
- Data sources: every adapter in [src/jeevn/infrastructure/data_sources/](src/jeevn/infrastructure/data_sources/) sets a fabrication flag on failure.
- Transformation: hoisting in [src/jeevn/infrastructure/data_sources/aoi.py](src/jeevn/infrastructure/data_sources/aoi.py); merging + describing in [src/jeevn/application/advisory_service.py](src/jeevn/application/advisory_service.py); descriptions in [src/jeevn/infrastructure/pseudo_satellite.py](src/jeevn/infrastructure/pseudo_satellite.py) (`FABRICATED_FIELD_DESCRIPTIONS` + `describe`).
- Outstream: `data_quality.{fabricated_fields[], details, alerts[], warning}` in the advisory report; rendered as a yellow banner + bulleted list (and red banner for alerts) in [src/jeevn/ui/app.py](src/jeevn/ui/app.py) (`tab_report` block, line 207-228). PDF disclaimer box on page 5.

---

## How to use this doc

- **Adding a process:** copy the template, fill `Ideal / Actual / Gap / Code path` in that order. Be honest about the gap; future-you will thank you.
- **Replacing a placeholder with a real source:** find the placeholder here (e.g. RVI, RSM, SAR moisture), find the `pseudo_satellite` constant or the fabricated-flag site, and grep for callers — those are the spots that need updating in lockstep with the real ingest.
- **Tracing a number in the PDF back to its source:** open the relevant section in [src/jeevn/ui/pdf/generator.py](src/jeevn/ui/pdf/generator.py), find the field it reads from the `report` dict, then jump to this doc to see whether that field is real, derived, or fabricated.

For structural how-the-code-fits-together questions, see [ARCHITECTURE.md](ARCHITECTURE.md) and the per-folder `OVERVIEW.md` files.
