"""
HTTP client to the Jeevn API.
This is the ONLY path UI code uses to obtain data — no in-process imports
of domain or application modules. Keeps frontend and backend decoupled.
"""

from typing import Optional, Dict, Any

import requests


class JeevnAPIClient:
    """Thin wrapper around the FastAPI HTTP endpoints."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 90):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        """Returns True if the API responds healthy."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def submit_aoi(self, name: str, geojson: dict,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> Dict[str, Any]:
        """POST /aoi — ingestion + raster preprocessing.

        Returns the AOI ingest result (raises requests.HTTPError on non-2xx).
        """
        payload = {
            "name": name,
            "geojson": geojson,
            "start_date": start_date,
            "end_date": end_date,
        }
        response = requests.post(f"{self.base_url}/aoi", json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def generate_advisory(self, name: str, latitude: float, longitude: float,
                          area_acres: float, crop_type: str,
                          sowing_date: Optional[str] = None,
                          ndvi_timeseries: Optional[list] = None,
                          location_name: str = "") -> Dict[str, Any]:
        """POST /advisory/agricultural — full advisory report.

        Returns the advisory payload (raises requests.HTTPError on non-2xx).
        """
        payload = {
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "area_acres": area_acres,
            "crop_type": crop_type,
            "sowing_date": sowing_date,
            "ndvi_timeseries": ndvi_timeseries,
            "location_name": location_name,
        }
        response = requests.post(
            f"{self.base_url}/advisory/agricultural",
            json=payload, timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def fetch_aoi_map(self, aoi_id: str, kind: str) -> Optional[bytes]:
        """GET /aoi/{aoi_id}/maps/{kind}.png — fetch the real colorized
        NDVI or NDWI raster as PNG bytes. Returns None if the server has no
        real raster for this AOI (HTTP 404) or the request fails.
        """
        try:
            response = requests.get(
                f"{self.base_url}/aoi/{aoi_id}/maps/{kind}.png",
                timeout=self.timeout,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.content
        except Exception:
            return None
