"""
NISAR L-band soil-moisture adapter — ASF SME2 product.

NASA-ISRO publish the pre-processed L3 **SME2** (Soil Moisture Estimate)
product on the Alaska Satellite Facility. L-band (~24 cm) penetrates crop
canopy and the top ~5 cm of soil, so it stays useful mid-season where
Sentinel-1 C-band soil moisture degrades. We consume the L2/L3 product
directly — no SAR-to-SM retrieval pipeline on our side.

Pipeline:
  1. `asf_search` query (keyless) for the latest SME2 granule over the AOI
     within a freshness window (~14 days).
  2. Earthdata-authenticated download of the granule HDF5 (~120 MB) to a
     gitignored cache, keeping only the 2 most-recent granules.
  3. Read soil moisture (m³/m³) at the AOI centroid from the first
     candidate algorithm with a good retrieval-quality flag.

Status (2026-05): SME2 is Beta v1 and production has been paused since
2026-01-20, so the freshness gate falls through to the caller's fallback
(Open-Meteo modelled SM) on live requests today. The pipeline is real and
verified against historical granules; it lights up automatically when
NASA-ISRO resume SME2 production.

Credentials: Earthdata Login username/password via env vars
`EARTHDATA_USER` / `EARTHDATA_PASS` (search needs no auth; download does).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── SME2 HDF5 layout (confirmed against a real 2026-01 granule) ─────────────
_GRID_GROUP = "science/LSAR/SME2/grids"
_LAT_DATASET = f"{_GRID_GROUP}/latitude"          # 1-D, per-row
_LON_DATASET = f"{_GRID_GROUP}/longitude"         # 1-D, per-col
# The Beta product ships three candidate retrieval algorithms; we take the
# first one (in this order) whose per-pixel retrievalQualityFlag is 0 (good).
_ALGORITHM_PREFERENCE = ("DSG", "PMI", "TSR")
_FILL_VALUE = -9999.0

_DEFAULT_DAYS_BACK = 14          # freshness window for a "current" reading
_EDGE_MARGIN_DEG = 0.045         # ~5 km — reject AOIs near the granule edge
_CACHE_KEEP = 2                  # most-recent granules to retain on disk

_CACHE_DIR = (
    Path(__file__).resolve().parents[4] / "data" / "cache" / "nisar"
)


def _creds() -> tuple[Optional[str], Optional[str]]:
    return os.environ.get("EARTHDATA_USER"), os.environ.get("EARTHDATA_PASS")


# ── ASF search (no auth) ────────────────────────────────────────────────────
def _find_latest_granule(lat: float, lon: float, days_back: int):
    """Return the newest SME2 granule intersecting (lat, lon) within
    `days_back` days, or None. Search needs no Earthdata auth.
    """
    import asf_search as asf  # noqa: WPS433 — heavy import, kept lazy

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    try:
        results = asf.search(
            platform=asf.PLATFORM.NISAR,
            processingLevel="SME2",
            intersectsWith=f"POINT({lon} {lat})",
            start=start,
            end=end,
            maxResults=50,
        )
    except Exception as e:
        print(f"[WARN] NISAR ASF search failed: {e}")
        return None
    if not results:
        return None
    results = sorted(
        results, key=lambda g: g.properties.get("startTime", ""), reverse=True,
    )
    return results[0]


# ── Authenticated download + cache management ───────────────────────────────
def _download_granule(granule) -> Optional[Path]:
    """Download the granule's main .h5 to the cache (skip if present),
    evict all but the `_CACHE_KEEP` most-recent .h5 files. Returns the
    local path, or None on auth/download failure.
    """
    user, pw = _creds()
    if not user or not pw:
        print("[INFO] EARTHDATA_USER/PASS not set — skipping NISAR download")
        return None

    props = granule.properties
    fname = props.get("fileName") or f"{props.get('sceneName')}.h5"
    target = _CACHE_DIR / fname
    if target.exists() and target.stat().st_size > 1_000_000:
        return target

    import asf_search as asf  # noqa: WPS433
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        session = asf.ASFSession().auth_with_creds(user, pw)
        granule.download(path=str(_CACHE_DIR), session=session)
    except Exception as e:
        print(f"[WARN] NISAR granule download failed: {e}")
        return None

    if not target.exists():
        return None

    _evict_old_granules()
    return target


def _evict_old_granules() -> None:
    """Keep only the `_CACHE_KEEP` most-recently-modified main .h5 files."""
    h5s = sorted(
        [p for p in _CACHE_DIR.glob("*.h5") if "QA_STATS" not in p.name],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for stale in h5s[_CACHE_KEEP:]:
        try:
            stale.unlink()
            # also drop the sidecar files that share the stem
            for sidecar in _CACHE_DIR.glob(stale.stem + "*"):
                if sidecar != stale:
                    sidecar.unlink()
        except Exception:
            pass


# ── HDF5 sampling ───────────────────────────────────────────────────────────
def _sample_sm(h5_path: Path, lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Sample soil moisture (m³/m³) at the nearest grid cell to (lat, lon).

    Tries each candidate algorithm in preference order, returning the first
    with a good retrieval-quality flag (0) and a non-fill value. Rejects
    points within `_EDGE_MARGIN_DEG` of the granule edge.
    """
    import h5py  # noqa: WPS433
    import numpy as np

    try:
        with h5py.File(h5_path, "r") as f:
            grid = f[_GRID_GROUP]
            lats = grid["latitude"][:]
            lons = grid["longitude"][:]

            lat_lo, lat_hi = float(lats.min()), float(lats.max())
            lon_lo, lon_hi = float(lons.min()), float(lons.max())
            if not (lat_lo <= lat <= lat_hi and lon_lo <= lon <= lon_hi):
                return None
            # Edge margin — distortion / partial coverage near the swath edge.
            if (lat - lat_lo < _EDGE_MARGIN_DEG or lat_hi - lat < _EDGE_MARGIN_DEG
                    or lon - lon_lo < _EDGE_MARGIN_DEG or lon_hi - lon < _EDGE_MARGIN_DEG):
                return None

            ri = int(np.abs(lats - lat).argmin())
            ci = int(np.abs(lons - lon).argmin())

            for algo in _ALGORITHM_PREFERENCE:
                base = grid.get(f"algorithmCandidates/{algo}")
                if base is None:
                    continue
                sm = float(base["soilMoisture"][ri, ci])
                qf = int(base["retrievalQualityFlag"][ri, ci])
                if sm == _FILL_VALUE or not np.isfinite(sm) or sm < 0:
                    continue
                if qf != 0:
                    continue
                return {
                    "soil_moisture_m3m3": round(sm, 4),
                    "algorithm": algo,
                    "quality_flag": qf,
                }
    except Exception as e:
        print(f"[WARN] NISAR HDF5 sample failed: {e}")
        return None
    return None


# ── Public client ───────────────────────────────────────────────────────────
class NisarSoilMoistureClient:
    """Latest NISAR SME2 soil moisture at the AOI centroid, or None."""

    @staticmethod
    def fetch_sm_at(lat: float, lon: float,
                    days_back: int = _DEFAULT_DAYS_BACK) -> Optional[Dict[str, Any]]:
        """Return `{soil_moisture_m3m3, pass_date, granule_id, algorithm,
        quality_flag, source}` for the latest fresh-enough SME2 pass over
        (lat, lon), or None (no pass in window / no creds / out of coverage /
        download or read failure). The caller converts m³/m³ to whatever
        scale it needs and decides the fallback.
        """
        granule = _find_latest_granule(lat, lon, days_back)
        if granule is None:
            return None

        props = granule.properties
        pass_iso = props.get("startTime", "")
        pass_date = pass_iso.split("T")[0] if pass_iso else ""
        granule_id = props.get("sceneName", "")

        h5_path = _download_granule(granule)
        if h5_path is None:
            return None

        sampled = _sample_sm(h5_path, lat, lon)
        if sampled is None:
            return None

        sampled.update({
            "pass_date": pass_date,
            "granule_id": granule_id,
            "source": "nisar-sme2",
        })
        return sampled
