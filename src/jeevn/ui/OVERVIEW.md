# `src/jeevn/ui/` — Streamlit UI + PDF generator

The user-facing layer. Two delivery formats: an interactive **Streamlit app** and a downloadable **5-page A4 PDF**. Both render the same advisory report; the PDF is built from the exact same data the UI displays.

**Hard rule:** the UI reaches the backend **only over HTTP** through [`api_client.py`](api_client.py). No in-process imports of `application/` or `domain/`. This keeps the frontend and backend genuinely decoupled and prevents the UI from accidentally calling around the API.

## Tech / runtime

- **streamlit** + **streamlit-folium** + **folium** for the map + sidebar.
- **pandas** for the table widgets (used inside the section renderers).
- **Pillow** for client-side colour-scale legends.
- **ReportLab** for PDF assembly (self-installs into the running interpreter on first call if missing).

Started with: `streamlit run src/jeevn/ui/app.py` (requires `pip install -e .` or `PYTHONPATH=src` — Streamlit has no `--app-dir` flag).

## Files

### [`app.py`](app.py) — main Streamlit entrypoint
Two tabs:

**Tab 1 — "Submit AOI"**
- Left column: AOI name, crop type, sowing/start date, end date.
- Right column: Folium map with `Draw` (polygon/rectangle only) + `Geocoder`. Drawn geometry is converted to a `FeatureCollection` and dropped into a GeoJSON textarea so the user can also paste raw GeoJSON. A default polygon centred at `(29.92, 73.97)` (the Indira Gandhi Canal command area, ~10 km east of Sri Ganganagar — confirmed cropland with full SoilGrids coverage) is pre-filled.
- Submit button:
  1. Computes centroid + area via [`geo_utils.py`](geo_utils.py).
  2. `client.submit_aoi(...)` → `POST /aoi` → stores result + NDVI timeseries in `st.session_state`.
  3. `client.generate_advisory(...)` → `POST /advisory/agricultural` (passing the timeseries through) → stores the advisory in `st.session_state`.

**Tab 2 — "View Report"** — mirrors the PDF page-for-page:
1. Header banner (location / area / satellite-visit date / crop) + a red-banner block for `data_quality.alerts` (e.g. "AOI in built-up land") + a yellow-banner block listing `data_quality.fabricated_fields`.
2. [`sections/field_maps.py`](sections/field_maps.py) — real Sentinel-2 NDVI + NDWI rasters AND Sentinel-1 RVI raster, each fetched as PNG bytes from `/aoi/{id}/maps/{kind}.png` (kinds: `ndvi`, `ndwi`, `rvi`). Three-up column layout. Falls back to an explicit "raster unavailable" notice rather than substituting synthetic imagery.
3. [`sections/irrigation_schedule.py`](sections/irrigation_schedule.py) — 7-day schedule table + calculation note + **three metric chips (ET₀ / Kc / LST** — LST is a placeholder until task #9 Sentinel-3 SLSTR lands**)** + terrain-aware narrative + source-aware reference line.
4. [`sections/soil_growth.py`](sections/soil_growth.py) — paired soil/yield metric tiles + details + limiting-factors expander.
5. [`sections/pest_disease_weed.py`](sections/pest_disease_weed.py) — risk-coloured threat table (red/yellow/green) + **environmental chips (Temperature / Humidity / RSM with source attribution)** + pest narrative + weed narrative + source-aware references caption (RSM source: NISAR L-band / Open-Meteo / fabricated).
6. [`sections/fertilizer.py`](sections/fertilizer.py) — N/P/K/S/Zn table with colour-coded status column + recommended-products expander + numbered details.

Then "Generate PDF Report":
- Re-fetches the same raster PNGs the UI shows via `client.fetch_aoi_map(...)`.
- Calls [`pdf/generator.py`](pdf/generator.py) with `(report, ndvi_png, ndwi_png)`.
- Offers a download button with filename `farm_advisory_<YYYYMMDD>.pdf`.

### [`api_client.py`](api_client.py)
`JeevnAPIClient(base_url, timeout=90)`. Methods:
- `health() -> bool` — `GET /health`.
- `submit_aoi(name, geojson, start_date, end_date) -> dict` — `POST /aoi`.
- `generate_advisory(name, latitude, longitude, area_acres, crop_type, sowing_date, ndvi_timeseries, location_name) -> dict` — `POST /advisory/agricultural`.
- `fetch_aoi_map(aoi_id, kind) -> bytes | None` — `GET /aoi/{aoi_id}/maps/{kind}.png` (returns `None` on 404 so the section can render its fallback).

`raise_for_status()` on non-2xx so the UI tab can `try/except` and render an error.

### [`geo_utils.py`](geo_utils.py)
- `extract_centroid(geojson) -> (lat, lon)` — average of polygon ring coordinates; falls back to `pseudo_satellite.DEFAULT_LATITUDE`/`LONGITUDE` on parse failure.
- `estimate_area_acres(geojson) -> float` — shoelace formula on lat/lon degrees, scaled by `12321 × 247.105` (deg² → km² → acres). Clamped to `[0.1, 50000]`; falls back to `pseudo_satellite.DEFAULT_AREA_ACRES`.

### [`visuals.py`](visuals.py)
The only thing produced client-side: a small horizontal colour-scale legend.

- `scale_bar(palette, label_lo, label_hi, w=220, h=22) -> BytesIO | None` — uses the canonical `NDVI_STOPS` / `NDWI_STOPS` / `RVI_STOPS` colour stops imported from [../remote_sensing/visualization.py](../remote_sensing/visualization.py) so the legend colours match the server-rendered raster pixel-for-pixel.

The procedural synthetic field maps that used to live here were removed — when a real raster is unavailable, the field-maps section says so explicitly rather than fabricating one.

### `sections/` — page-1-through-5 renderers
One module per PDF page; each exports a `render(...)` function that takes the relevant slice of the advisory dict plus contextual kwargs (crop_name, location, growth_stage_name, …) and emits Streamlit widgets. All shared narrative thresholds (e.g. terrain → irrigation advice) come from [../application/narratives.py](../application/narratives.py) so the UI and PDF say the same thing.

| File | Mirrors PDF page | Key widgets |
|------|------------------|-------------|
| [`sections/field_maps.py`](sections/field_maps.py) | Page 1 | `st.image` for each raster (or `st.info` fallback), Pillow scale-bar legends. |
| [`sections/irrigation_schedule.py`](sections/irrigation_schedule.py) | Page 2 | pandas DataFrame, calculation-note `st.info` box, ET₀/Kc/LST metric chips, terrain narrative. |
| [`sections/soil_growth.py`](sections/soil_growth.py) | Page 3 | Side-by-side `st.metric` tiles (left=soil, right=yield), texture composition caption, limiting-factors expander. |
| [`sections/pest_disease_weed.py`](sections/pest_disease_weed.py) | Page 4 | Colour-coded threat table (Pandas Styler), Temperature/Humidity/RSM metric chips, pest + weed narratives, source-aware references. |
| [`sections/fertilizer.py`](sections/fertilizer.py) | Page 5 | Nutrient table with colour-coded `Status` column, recommended-products expander. |

### `pdf/generator.py`
**`generate_pdf(report, ndvi_png=None, ndwi_png=None) -> bytes`** — 5-page A4 PDF.

- Self-installs `reportlab` via `pip install --quiet` on first import if missing.
- Custom `_draw_header(canvas, doc, ...)` paints a dark-green banner with title + report date on every page, plus a subhead with location/area/satellite-visit/crop and a "Page N / 5" footer.
- Pages:
  1. **Field Maps** — embeds the NDVI/NDWI PNGs passed in. When `None`, prints "NDVI raster unavailable — no real Sentinel-2 reading." instead of synthesising a fake map. Plus the analysis-scale legends (reuses `visuals.scale_bar`).
  2. **Irrigation Schedule** — top-line summary, 7-day table, calculation-note box, narrative paragraph, terrain addendum, source-aware references.
  3. **Soil Management & Growth / Yield** — paired metric boxes (LIGHT_GREEN background for soil, LIGHT_BLUE for yield) + soil narrative + yield narrative + references.
  4. **Pest, Disease & Weed Management** — risk-coloured threat table (red/yellow/green Risk Level cells) + pest narrative + weed narrative + references.
  5. **Fertilizer Management** — nutrient table with colour-coded status + numbered details paragraph + amber disclaimer box at the bottom.

Colour palette is defined at module top (`DARK_GREEN`, `LIGHT_GREEN`, `RED`, `BLUE`, `AMBER_BG`, …). Table styling helpers (`_base_table_style`, `_note_box`, `_disclaimer_box`) keep the look consistent across pages.

### `__init__.py`, `pdf/__init__.py`, `sections/__init__.py`
Empty package markers.

## Conventions

- **Use API only.** Anything that needs the backend goes through `JeevnAPIClient`. New endpoints get a new method here, not direct module imports.
- **Sections are pure render functions.** They take a dict slice + kwargs and emit widgets. No data fetching, no business logic.
- **No fabrication at the render layer.** When data is missing, render a notice; don't paper over it.
- **UI/PDF parity.** When the UI and the PDF need to phrase the same thing, the phrasing helper goes in [../application/narratives.py](../application/narratives.py) and both import from there.
