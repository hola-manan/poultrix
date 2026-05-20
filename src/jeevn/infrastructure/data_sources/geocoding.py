"""
Reverse geocoding adapter — Nominatim client.

Nominatim's usage policy requires a custom User-Agent identifying the
application; without one the public endpoint returns 403 Forbidden. We also
ask for `addressdetails=1` to guarantee the parsed address block, and try
several locality keys (`city` → `town` → `village` → `hamlet` → `suburb`)
since rural polygons rarely have a `city`.

On failure, returns the fallback location info from
`infrastructure.pseudo_satellite` with `_fabricated=True`.
"""

import requests
from typing import Dict, Any

from jeevn.infrastructure import pseudo_satellite


# Identifies this app to the public Nominatim instance. Required by
# https://operations.osmfoundation.org/policies/nominatim/.
USER_AGENT = "Jeevn-MVP/0.1.0 (agricultural advisory; https://github.com/jeevn-mvp)"

# Nominatim sometimes nests the locality under different keys depending on
# how OpenStreetMap classifies the feature. Try them in priority order.
_LOCALITY_KEYS = ("city", "town", "village", "hamlet", "suburb", "county")


class GeographicDataFetcher:
    """Fetch location-specific data for agricultural calculations."""

    @staticmethod
    def get_location_info(lat: float, lon: float) -> Dict[str, Any]:
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                "lat": lat,
                "lon": lon,
                "format": "json",
                "addressdetails": 1,
                "zoom": 10,
            }
            headers = {"User-Agent": USER_AGENT, "Accept-Language": "en"}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            address = data.get("address", {}) or {}
            locality = next(
                (address[k] for k in _LOCALITY_KEYS if address.get(k)),
                data.get("name") or address.get("state_district") or "Unknown",
            )

            return {
                "latitude": lat,
                "longitude": lon,
                "name": locality,
                "city": address.get("city", "") or address.get("town", ""),
                "state": address.get("state", ""),
                "country": address.get("country", ""),
                "display_name": data.get("display_name", ""),
                "timezone": pseudo_satellite.DEFAULT_TIMEZONE,
                "_fabricated": False,
            }
        except Exception as e:
            print(f"[WARN] Location fetch failed: {e}")
            return pseudo_satellite.make_default_location(lat, lon)
