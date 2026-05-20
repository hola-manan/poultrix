"""
Lightweight GeoJSON helpers used by the Streamlit submit form.
"""

from jeevn.infrastructure import pseudo_satellite


def extract_centroid(geojson: dict):
    """Return (lat, lon) centroid from GeoJSON FeatureCollection polygon."""
    try:
        coords = geojson['features'][0]['geometry']['coordinates'][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    except Exception:
        return pseudo_satellite.DEFAULT_LATITUDE, pseudo_satellite.DEFAULT_LONGITUDE


def estimate_area_acres(geojson: dict) -> float:
    """Polygon area in acres via shoelace formula on lat/lon degrees."""
    try:
        coords = geojson['features'][0]['geometry']['coordinates'][0]
        n = len(coords)
        area_deg2 = 0.0
        for i in range(n - 1):
            area_deg2 += coords[i][0] * coords[i + 1][1]
            area_deg2 -= coords[i + 1][0] * coords[i][1]
        area_deg2 = abs(area_deg2) / 2
        area_acres = area_deg2 * 12321 * 247.105   # deg² → km² → acres
        return round(max(0.1, min(area_acres, 50000)), 3)
    except Exception:
        return pseudo_satellite.DEFAULT_AREA_ACRES
