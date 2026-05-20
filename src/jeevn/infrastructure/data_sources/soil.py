"""
Soil data adapter — region-based lookups.

This is currently a stub that always returns fabricated values; once a real
soil DB integration exists, `_fabricated=False` paths will hit a network call.
"""

from typing import Dict, Any

from jeevn.infrastructure import pseudo_satellite


class SoilDataFetcher:
    """Fetch soil data based on geographic location."""

    @staticmethod
    def fetch_soil_data(lat: float, lon: float,
                        location_name: str = "") -> Dict[str, Any]:
        # No real soil database integration yet — always return the regional
        # template marked as fabricated.
        return pseudo_satellite.make_default_soil(lat, lon, location_name)
