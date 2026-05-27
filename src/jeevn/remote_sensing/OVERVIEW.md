# `src/jeevn/remote_sensing/` — NDVI/NDWI pipeline + analysis

Everything that turns Sentinel-2 metadata + COG bands into vegetation/water indices, anomaly detections, and colorized PNG outputs.

Entry point: [`pipeline.py`](pipeline.py). The API route in [../api/routes/aoi.py](../api/routes/aoi.py) calls `aggregate_ndvi(metadata_path)`, `compute_raster(metadata_path)`, and `analyze_signals(timeseries, raster_path)` in sequence.

## Tech / runtime

- **numpy** for array math (always required).
- **rasterio** for COG streaming (lazy import — degrades gracefully when missing).
- **scipy.ndimage** for `generic_filter` in texture metrics (lazy import; pure-Python fallback exists).
- **Pillow** for PNG rendering in [`visualization.py`](visualization.py).

## Subpackage map

```
remote_sensing/
├── pipeline.py           # Orchestrator — the three public entry points
├── visualization.py      # NumPy raster → colorized PNG (server-side)
├── masking/cloud.py      # SCL + QA60 cloud masking
├── ndvi/
│   ├── compute.py        # Canonical NDVI formula + masked raster helper
│   └── aggregate.py      # Per-date NDVI/NDWI/NDRE timeseries from STAC items
└── analysis/
    ├── confidence.py     # Real NDVI/NDWI raster generation + parcel confidence
    ├── signals.py        # Vegetation indices, stress scores, anomalies
    ├── detections.py     # Disease/fertilizer/weed/yield detections
    ├── texture.py        # Local std + Shannon entropy
    └── sar.py            # SAR helpers (dB↔linear, moisture index)
```

---

## `pipeline.py` — public orchestrator

Three wrappers + one composite:

- **`aggregate_ndvi(metadata_path)`** → wrapper over `ndvi.aggregate.aggregate_ndvi`. Returns `{ndvi_csv, record_count, ndvi_timeseries}`.
- **`compute_raster(metadata_path)`** → wrapper over `analysis.confidence.compute_raster`. Returns `{ndvi_raster, ndwi_raster, parcel_confidence, raster_quality}`.
- **`analyze_signals(ndvi_timeseries, ndvi_raster_path)`** → runs the full anomaly battery and returns a flat dict the API includes in its response. Pulls in:
  - `signals.ndvi_anomaly` / `persistent_stress_detection` / `z_score_anomaly`
  - `detections.disease_patch_detection` / `yield_proxy` / `fertilizer_issue_detection` / `weeds_guidance`
  - `signals.water_stress_score` / `nutrient_stress_score` / `irrigation_stress_flag`
  - `texture.local_std` + `local_entropy` (operating on the real raster if `.tif`/`.npy` provided, else a small synthetic ~20×20 mock)
  - `sar.sar_moisture_index` over a synthetic 3×10×10 stack (placeholder until real SAR ingest lands)
- **`run_preproc(metadata_path)`** → composite that runs aggregate + raster and accumulates an `outputs` + `errors` list. Not currently invoked by the API but kept as a convenience for scripts.

---

## `ndvi/` — per-date timeseries

### [`ndvi/compute.py`](ndvi/compute.py)
- **`ndvi_index(red, nir)`** = `(nir - red) / (nir + red + 1e-6)`. **Single source of truth** for the NDVI formula — never inlined elsewhere.
- **`compute_ndvi(red_array, nir_array, output_path=None)`** — works on arrays; optionally writes a GeoTIFF (degrades to returning the array if rasterio is missing).
- **`compute_ndvi_with_mask(red_path, nir_path, scl_path, qa60_path, output_dir)`** — masked variant that uses [`masking/cloud.py`](masking/cloud.py) for SCL or QA60 cloud removal.

### [`ndvi/aggregate.py`](ndvi/aggregate.py)
**`aggregate_ndvi(metadata_path, output_dir="data")`** — the per-AOI per-date NDVI/NDWI/NDRE timeseries.

- Reads the ingest metadata JSON, sorts items by `properties.datetime`.
- For each STAC item, streams the AOI window of each needed band via `rasterio.open(url) + rasterio.mask.mask` (no full-tile download):
  - **NDVI** from B04 (red) + B08 (NIR)
  - **NDWI** from B03 (green) + B11 (SWIR) — note: uses the same `ndvi_index` shape; the actual NDWI sign is `(green - swir)`.
  - **NDRE** from B05 (red-edge) + B08 (NIR)
- When rasterio is missing or a URL fails, falls back to a synthetic `0.5 + 0.3 × (1 - cloud_pct/100)` formula derived from the STAC `eo:cloud_cover` property.
- Writes a CSV to `data/indices_timeseries_<UTC-timestamp>.csv` with columns `date, ndvi, ndwi, ndre`.
- **Returns** `{ndvi_csv: path, record_count, ndvi_timeseries: [{date, ndvi, ndwi, ndre}]}`.

If the metadata has `tiles` (stub-ingest output) instead of `stac_items`, falls back to a fully synthetic timeseries based on cloud percentage.

---

## `masking/cloud.py`

Sentinel-2 cloud-removal helpers.

- **`scl_cloud_mask(scl_array, cloud_classes=None)`** — returns a boolean mask. Default cloud classes: `{3 shadow, 8 cloud-med, 9 cloud-high, 10 cirrus}` (per Sen2Cor SCL semantics).
- **`qa60_mask(qa60_array)`** — bitmask over Sentinel-2 QA60 (bit 10 = cloud, bit 11 = cirrus).
- **`apply_mask(data_array, mask, fill_value=np.nan)`** — drop masked pixels to `nan`.

---

## `analysis/` — raster computation + signals

### [`analysis/confidence.py`](analysis/confidence.py)
**`compute_raster(metadata_path, output_dir="data")`** — produces the actual GeoTIFF rasters served by the `/aoi/{id}/maps/{kind}.png` endpoint.

- Picks the **latest** STAC item by datetime.
- For NDVI (B04 + B08) and NDWI (B03 + B11) independently:
  - `_compute_index_raster(red_url, nir_url, geometry)`:
    - Opens the COG via rasterio (lazy import).
    - Reprojects the AOI geometry into the COG's CRS via `rasterio.warp.transform_geom`.
    - Crops both bands with `rasterio.mask.mask(...all_touched=True)`.
    - Resamples NIR onto the red grid via bilinear `reproject` when shapes differ (B08 and B04 are both 10 m natively but the masked windows can land on different grids when the AOI is small).
    - Builds an NDVI array with `nan` outside the valid-pixel mask.
  - For NDWI, passes `(green, swir)` and negates the result (because `ndvi_index` would otherwise compute `(swir − green)`).
  - Writes the float32 GeoTIFF to `data/<aoi_id>_ndvi.tif` / `_ndwi.tif` with `nodata=nan`.
- **`compute_parcel_confidence(ndvi_raster)`** scores the parcel: `0.4 × mean_ndvi_normed + 0.3 × uniformity (1 − std) + 0.3 × valid_pixel_pct`.
- **Returns** `{ndvi_raster, ndwi_raster, parcel_confidence, raster_quality: {ndvi_raster_available, ndwi_raster_available, capture_date}}`.
- Either raster is independently `None` when its source bands or rasterio are missing — the report's data-quality layer surfaces this.

### [`analysis/signals.py`](analysis/signals.py)
Vegetation indices (`ndvi`, `ndwi`, `evi`, `savi`, `ndre`, `gci`, `msi`) + anomaly + stress detectors.

- **`z_score_anomaly(values, threshold=2.0)`** — z-score with **modified-z (MAD-based) fallback** when std is zero or no anomalies are detected. Returns a boolean array.
- **`ndvi_anomaly(ndvi_timeseries, threshold=0.3)`** — flags `low_ndvi` (mean < 0.3) or `rapid_decline` (any step drop > threshold).
- **`irrigation_stress_flag(ndvi, lst=None)`** — true if NDVI < 0.4 or LST > 35.
- **`persistent_stress_detection(ndvi_timeseries, window_size=3)`** — moving average < 0.4 over > 50% of windows.
- **`water_stress_score(ndvi, ndwi)`** = `0.6 × (1 − ndvi) + 0.4 × (1 − ndwi)`.
- **`nutrient_stress_score(ndvi, red_edge_ndvi)`** — clamped `(re/ndvi − 0.2) / 0.6` band.
- **`parcel_confidence_score(mean_ndvi, ndvi_std, valid_pixel_pct)`** — same weighted formula as `compute_parcel_confidence` but takes scalars.

### [`analysis/detections.py`](analysis/detections.py)
Higher-level detections that combine signals.

- **`disease_patch_detection(ndvi_timeseries, window_size=2, decline_threshold=0.2)`** — boolean detection + risk score from max rolling decline.
- **`fertilizer_issue_detection(early, mid, late)`** — early-season growth deficit → `fert_score`.
- **`weeds_guidance(ndvi, texture_entropy)`** — pressure score from entropy + dense-canopy suppression; returns a narrative string.
- **`yield_proxy(cumulative_ndvi, max_ndvi, record_count)`** — `2.0 + cumulative × 0.5 + peak × 3.0` clamped to 0.5–12 t/ha + confidence.

### [`analysis/texture.py`](analysis/texture.py)
- **`local_std(data, kernel_size=3)`** — scipy `generic_filter(np.std, …)` with a pure-Python sliding-window fallback.
- **`local_entropy(data, kernel_size=3)`** — Shannon entropy on 10-bin histogram `[0,1]`. Used by `weeds_guidance`.

### [`analysis/sar.py`](analysis/sar.py)
- `sar_db_to_linear` / `sar_linear_to_db` conversions.
- `sar_vh_vv_difference` — polarization difference.
- `sar_moisture_index(sar_stack)` — temporal-median normalised by max; expects 3-D `(time, h, w)`.
- `sar_stack_loading(file_paths, normalize=True)` — read + z-score-normalise multiple SAR rasters.

Note: SAR ingest is **not implemented** — the pipeline currently passes a random synthetic stack into `sar_moisture_index` so the field is populated. NISAR L-band integration is on the TASKS.md backlog.

---

## `visualization.py` — server-side colorization

`colorize_raster(raster, palette, output_size=(440, 320), smooth=True, geometry=, transform=, crs=)`.

- Float NDVI/NDWI/RVI array → RGBA PNG bytes.
- **NaN-aware:** pixels outside the AOI polygon arrive as NaN and are rendered fully transparent (alpha=0) so the rendered image shows the parcel shape, not a rectangle.
- Colour ramps `NDVI_STOPS` (red → orange → yellow → green → dark green), `NDWI_STOPS` (dark red → pink → white → light blue → dark blue), and `RVI_STOPS` (dark brown → tan → pale yellow → green → deep green; for the Sentinel-1 radar map) defined at module top — re-used by `ui.visuals.scale_bar` for the legend so colours match pixel-for-pixel.
- Upsampled via `PILImage.NEAREST` to keep blocks crisp, then `ImageFilter.GaussianBlur(radius=1.5)` to soften the pixelation (real rasters at parcel scale are tiny — a few × a few pixels at 10 m Sentinel-2 resolution).
- When `geometry + transform + crs` are passed, draws the AOI polygon outline in white over the colour map via `PIL.ImageDraw.polygon(outline=(255,255,255,255), width=3)`.
- `load_raster_data(path)` reads either `.tif` (rasterio + nodata→nan) or `.npy` (numpy). Returns `(array, transform, crs)` or `None`.

---

## Tests

- [tests/remote_sensing/test_aggregate_ndvi.py](../../../tests/remote_sensing/test_aggregate_ndvi.py) — full timeseries roundtrip.
- [tests/remote_sensing/analysis/](../../../tests/remote_sensing/analysis/) — `test_indices.py`, `test_signals.py`, `test_detections.py`, `test_texture.py`, `test_sar.py`.

## Known limitations

- SAR is synthetic — see TASKS.md item #4 (NISAR integration).
- The single 35-day STAC search window in `ingestion/sentinel.py` will return zero items for AOIs over very cloudy regions or during winter — the file structure supports progressive widening but it's currently disabled.
