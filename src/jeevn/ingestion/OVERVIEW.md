# `src/jeevn/ingestion/` — Satellite imagery ingest

Locates Sentinel-2 imagery for an AOI and writes a metadata JSON file that the [../remote_sensing/](../remote_sensing/) pipeline consumes downstream. Strictly an **ingest** layer — does not compute indices, does not download band data (the COG URLs in the metadata are streamed band-by-band later by `aggregate_ndvi` and `compute_raster`).

## Tech / runtime

- Pure Python + `requests`. No GDAL/rasterio dependency at this layer.
- Hits **Microsoft Planetary Computer STAC** (free, no auth — SAS token fetched anonymously).
- Falls back to an in-process stub when STAC is unreachable or returns zero items.

## Files

### [`sentinel.py`](sentinel.py)
The main ingest path: Sentinel-2 L2A via Planetary Computer.

- **`ingest(aoi_geojson, start_date, end_date, aoi_id)` — public entry point.**
  - **In:** AOI as a GeoJSON FeatureCollection; the user's `start_date`/`end_date` are recorded but **not** used as the imagery search window (those dates are about the crop; imagery dates are about the satellite archive).
  - **Steps:**
    1. Search the most recent 35 days via `POST https://planetarycomputer.microsoft.com/api/stac/v1/search` filtering `eo:cloud_cover < 50`. Currently `_SEARCH_WINDOWS_DAYS = (35,)` — a single window; the file structure supports progressively widening (180 / 365 / 730 day fallbacks).
    2. If found, calls `_sign_assets(features)` which fetches a SAS token from `https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a` and appends it to every asset href (so the COG GETs that happen later are signed). No-ops silently if the token endpoint is unreachable; unsigned hrefs still work with stricter rate limits.
    3. Writes the full STAC item list + AOI + dates to `data/ingest_metadata_{aoi_id}.json`.
  - **Out:** `{metadata_path, success: True, products_found, imagery_search_window: {start, end}}`.
  - **On any failure:** calls `runner.stub_ingest(...)` and returns its result instead. The caller can't tell the difference structurally.

### [`runner.py`](runner.py)
The fallback stub. `stub_ingest(aoi_geojson, start_date, end_date, aoi_id)` writes a deterministic demo metadata JSON with two hard-coded "tiles" entries (Sentinel-2 tile id `31TCG`, plausible-looking dates and cloud percentages). Used when:
- Planetary Computer is unreachable.
- STAC returns zero items in the search window.
- The caller deliberately wants offline behaviour for testing.

The downstream pipeline detects the absence of `stac_items` and uses the `tiles` list instead, producing synthetic NDVI values (no real raster).

### [`__init__.py`](__init__.py)
Empty package marker.

## Metadata file contract

The file is the **handoff format** to the remote-sensing pipeline. Two flavours:

### Real-ingest output (`sentinel.ingest`)
```json
{
  "aoi": {<original FeatureCollection>},
  "start_date": "YYYY-MM-DD",
  "end_date":   "YYYY-MM-DD",
  "imagery_search_window": { "start": "...", "end": "..." },
  "fetched_at": "ISO-8601",
  "stac_items": [
    {
      "properties": {
        "datetime": "ISO-8601",
        "eo:cloud_cover": <float>
      },
      "assets": {
        "B03": {"href": "https://...?sas-token"},
        "B04": {"href": "..."},
        "B05": {"href": "..."},
        "B08": {"href": "..."},
        "B11": {"href": "..."}
        /* and the rest of the L2A bands */
      }
    }
  ]
}
```

### Stub output (`runner.stub_ingest`)
```json
{
  "aoi": {<FeatureCollection>},
  "start_date": "...",
  "end_date":   "...",
  "fetched_at": "ISO-8601",
  "tiles": [
    {"tile_id": "31TCG", "date": "2024-03-15", "cloud_percentage": 12.5},
    {"tile_id": "31TCG", "date": "2024-04-14", "cloud_percentage":  5.2}
  ]
}
```

The remote-sensing aggregator branches on `stac_items` (preferred) vs `tiles` (fallback).

## Tests

- [tests/ingestion/test_ingest_stub.py](../../../tests/ingestion/test_ingest_stub.py) — exercises `stub_ingest`'s metadata structure (`success`, `metadata_path`, `aoi`, `start_date`, `end_date`, `fetched_at`, `tiles`).
- Real-ingest path is exercised manually via [scripts/dev_smoke/test_network_api.py](../../../scripts/dev_smoke/test_network_api.py).
