"""
Sentinel-2 ingestion via Microsoft Planetary Computer STAC.

The imagery search window is decoupled from the user's crop sowing/end dates:
the latter are about the crop schedule and the former is about the satellite
archive, so we cannot use one for the other. We always start by searching the
most recent ~90 days for Sentinel-2 L2A passes over the AOI, and progressively
expand the window (180 → 365 → 730 days) if nothing is found. This makes the
ingest robust regardless of what the user puts in the sowing-date field, and
ensures the report uses the *latest* available imagery.

Falls back to the stub runner if STAC is unreachable or the network call fails.
"""

import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from . import runner


_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
_SAS_TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a"
_CLOUD_COVER_LIMIT = 50
_SEARCH_WINDOWS_DAYS = (35,)


def _search_stac(geometry: dict, days_back: int) -> Tuple[list, str, str]:
    """Run one STAC search over the last `days_back` days. Returns the feature
    list plus the actual start/end strings used.
    """
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days_back)
    start = start_dt.strftime("%Y-%m-%d")
    end = end_dt.strftime("%Y-%m-%d")

    payload = {
        "collections": ["sentinel-2-l2a"],
        "intersects": geometry,
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": _CLOUD_COVER_LIMIT}},
        "limit": 100,
    }
    response = requests.post(_STAC_URL, json=payload, timeout=30)
    response.raise_for_status()
    features = response.json().get("features", [])
    return features, start, end


def _sign_assets(features: list) -> None:
    """Append a Planetary Computer SAS token to every asset href, in place.
    Silently no-ops if the token endpoint is unreachable; unsigned hrefs are
    still usable for small AOIs although with stricter rate limits.
    """
    try:
        sas_token = requests.get(_SAS_TOKEN_URL, timeout=10).json().get("token", "")
    except Exception as e:
        print(f"[INFO] PC SAS token unavailable, using unsigned hrefs: {e}")
        return
    if not sas_token:
        return
    for feat in features:
        for asset in feat.get("assets", {}).values():
            href = asset.get("href", "")
            if href and "?" not in href:
                asset["href"] = f"{href}?{sas_token}"


def ingest(
    aoi_geojson: dict,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    aoi_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch Sentinel-2 L2A items over the AOI from Planetary Computer.

    `start_date` / `end_date` are recorded in the metadata for the caller's
    bookkeeping (they describe the crop, not the imagery), but they are NOT
    used as the STAC search window — see module docstring.
    """
    try:
        geometry = aoi_geojson.get("features", [{}])[0].get("geometry")
        if not geometry:
            raise ValueError("No geometry found")

        # Progressively widen the imagery search window until we hit something.
        features: list = []
        searched_start, searched_end = "", ""
        for days in _SEARCH_WINDOWS_DAYS:
            print(f"[INFO] Querying Planetary Computer STAC for the last {days} days...")
            features, searched_start, searched_end = _search_stac(geometry, days)
            if features:
                print(f"[INFO] Found {len(features)} satellite passes "
                      f"({searched_start} -> {searched_end}).")
                break
        else:
            print(f"[INFO] No Sentinel-2 passes found within the last "
                  f"{_SEARCH_WINDOWS_DAYS[-1]} days; falling back to stub.")
            return runner.stub_ingest(aoi_geojson, start_date, end_date, aoi_id)

        _sign_assets(features)

        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)

        metadata = {
            "aoi": aoi_geojson,
            "start_date": start_date,
            "end_date": end_date,
            "imagery_search_window": {
                "start": searched_start,
                "end": searched_end,
            },
            "fetched_at": datetime.utcnow().isoformat(),
            "stac_items": features,
        }

        metadata_filename = f"ingest_metadata_{aoi_id or 'stac'}.json"
        metadata_path = data_dir / metadata_filename
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return {
            "metadata_path": str(metadata_path),
            "success": True,
            "products_found": len(features),
            "imagery_search_window": {"start": searched_start, "end": searched_end},
        }

    except Exception as e:
        print(f"[WARN] PC STAC query failed: {e}")
        return runner.stub_ingest(aoi_geojson, start_date, end_date, aoi_id)
