"""
Soil data adapter — ISRIC SoilGrids v2.0 client.

Fetches real soil properties at the AOI centroid from the free, anonymous
SoilGrids REST API and aggregates the 0–5/5–15/15–30 cm depth layers into a
single 0–30 cm depth-weighted mean. Derives USDA texture class from the
real sand/silt/clay percentages, and looks up an approximate water-holding
capacity and infiltration rate from the resulting texture class.

When SoilGrids is unreachable or returns partial data, the caller falls back
to `pseudo_satellite.make_default_soil` and the response is marked fabricated
on a per-property basis via `_fabricated_fields`.

This replaces the prior stub that always returned the regional template.
"""

from typing import Any, Dict, List, Optional

import requests

from jeevn.infrastructure import pseudo_satellite


# ── SoilGrids v2.0 endpoint config ─────────────────────────────────────────
_SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
_PROPERTIES = ("phh2o", "soc", "bdod", "sand", "silt", "clay", "cec")
_DEPTHS = ("0-5cm", "5-15cm", "15-30cm")
_DEPTH_WEIGHTS_CM: Dict[str, int] = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
_REQUEST_TIMEOUT_S = 20
_USER_AGENT = "Jeevn-MVP/0.1.0 (agricultural advisory)"


# ── USDA texture-triangle classifier ───────────────────────────────────────
# Approximate USDA classification. Boundary cases at the edges of the
# triangle may differ slightly from the official chart; downstream use (the
# coarse WHC + infiltration lookup) is insensitive to those small shifts.
def classify_usda_texture(sand: float, silt: float, clay: float) -> str:
    """Return one of the 12 USDA soil-texture classes from sand/silt/clay
    percentages. Inputs should sum to ~100; minor rounding is tolerated.
    """
    s, si, c = sand, silt, clay

    if c >= 40:
        if s >= 45:
            return "sandy clay"
        if si >= 40:
            return "silty clay"
        return "clay"

    if c >= 27:
        if s > 45:
            return "sandy clay loam"
        if si >= 40:
            return "silty clay loam"
        return "clay loam"

    # Sandy clay loam window: clay 20–35, sand 45–80, silt < 28.
    if c >= 20 and s > 45 and si < 28:
        return "sandy clay loam"

    if si >= 80 and c < 12:
        return "silt"

    if si >= 50:
        return "silt loam"

    if c < 7 and s >= 85:
        return "sand"

    if c < 15 and s >= 70:
        return "loamy sand"

    if s > 52 and c < 20:
        return "sandy loam"

    return "loam"


# ── Texture-class → field-capacity & infiltration lookup ───────────────────
# Approximate plant-available water (mm per 30 cm depth) and steady-state
# infiltration rate (mm/hour) by USDA texture class. Drawn from USDA-NRCS
# field tables; intentionally coarse — when more precise field-capacity data
# is available (e.g. SoilGrids' future wv0033/wv1500 layers), this lookup
# should be replaced by direct values.
_TEXTURE_WHC_MM_PER_30CM: Dict[str, int] = {
    "sand":              6,
    "loamy sand":        11,
    "sandy loam":        17,
    "loam":              23,
    "silt loam":         29,
    "silt":              28,
    "sandy clay loam":   22,
    "clay loam":         25,
    "silty clay loam":   27,
    "sandy clay":        22,
    "silty clay":        26,
    "clay":              24,
}

_TEXTURE_INFILTRATION_MM_PER_H: Dict[str, int] = {
    "sand":              35,
    "loamy sand":        25,
    "sandy loam":        15,
    "loam":              10,
    "silt loam":         7,
    "silt":              5,
    "sandy clay loam":   8,
    "clay loam":         5,
    "silty clay loam":   3,
    "sandy clay":        3,
    "silty clay":        2,
    "clay":              1,
}


def whc_from_texture(texture: str) -> int:
    return _TEXTURE_WHC_MM_PER_30CM.get(texture, _TEXTURE_WHC_MM_PER_30CM["loam"])


def infiltration_from_texture(texture: str) -> int:
    return _TEXTURE_INFILTRATION_MM_PER_H.get(texture, _TEXTURE_INFILTRATION_MM_PER_H["loam"])


# ── Aggregation + unit conversion ──────────────────────────────────────────
def _depth_weighted_mean(depth_values: List[Dict[str, Any]]) -> Optional[float]:
    """Weight 0–5, 5–15, 15–30 cm mean values by their cm-thickness."""
    weighted_sum = 0.0
    total_weight = 0
    for d in depth_values:
        label = d.get("label")
        mean = (d.get("values") or {}).get("mean")
        if mean is None or label is None:
            continue
        w = _DEPTH_WEIGHTS_CM.get(label, 0)
        if w == 0:
            continue
        weighted_sum += float(mean) * w
        total_weight += w
    if total_weight == 0:
        return None
    return weighted_sum / total_weight


def _convert_to_target_units(layer: Dict[str, Any], raw_mean: float) -> float:
    """Apply SoilGrids' `d_factor` to convert mapped units to target units.

    Example: `phh2o` has d_factor=10 (mapped pH*10), so raw 77 → 7.7 pH.
    SoilGrids embeds the conversion factor in each layer; we honour it.
    """
    d_factor = (layer.get("unit_measure") or {}).get("d_factor", 1)
    if not d_factor:
        return raw_mean
    return raw_mean / d_factor


def _normalise_soc_to_percent(soc_g_per_kg: float) -> float:
    """SoilGrids returns SOC in g/kg after d_factor; convert to mass %.
    1 g/kg = 0.1 %.
    """
    return soc_g_per_kg / 10.0


# ── SoilGrids client ───────────────────────────────────────────────────────
class SoilGridsClient:
    """Anonymous client for the ISRIC SoilGrids v2.0 REST API."""

    @staticmethod
    def fetch(lat: float, lon: float) -> Optional[Dict[str, float]]:
        """Return a dict of real 0–30 cm soil properties for (lat, lon),
        or None on any network/parse failure.

        Keys (all in target units, depth-weighted across 0–30 cm):
            ph                      — pH in water
            organic_carbon_percent  — % mass
            bulk_density            — g/cm³
            sand_percent            — % mass
            silt_percent            — % mass
            clay_percent            — % mass
            cec                     — cmol(+)/kg
        Any individual key may be missing if SoilGrids returned no value at
        any depth for that property.
        """
        params: List = [("lon", lon), ("lat", lat), ("value", "mean")]
        params += [("property", p) for p in _PROPERTIES]
        params += [("depth", d) for d in _DEPTHS]

        try:
            response = requests.get(
                _SOILGRIDS_URL,
                params=params,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                timeout=_REQUEST_TIMEOUT_S,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"[WARN] SoilGrids fetch failed: {e}")
            return None

        layers = (data.get("properties") or {}).get("layers") or []
        if not layers:
            return None

        result: Dict[str, Any] = {}
        for layer in layers:
            name = layer.get("name")
            depths = layer.get("depths") or []
            raw_mean = _depth_weighted_mean(depths)
            if raw_mean is None:
                continue
            value = _convert_to_target_units(layer, raw_mean)

            # Map SoilGrids names to our internal property names.
            if name == "phh2o":
                result["ph"] = round(value, 2)
            elif name == "soc":
                # `soc` arrives in g/kg after d_factor; convert to %.
                result["organic_carbon_percent"] = round(_normalise_soc_to_percent(value), 3)
            elif name == "bdod":
                result["bulk_density"] = round(value, 3)
            elif name == "sand":
                result["sand_percent"] = round(value, 2)
            elif name == "silt":
                result["silt_percent"] = round(value, 2)
            elif name == "clay":
                result["clay_percent"] = round(value, 2)
            elif name == "cec":
                result["cec"] = round(value, 2)

        # Distinguish "network/parse error" from "service responded but the
        # query point sits in their land-mask exclusion zone" (i.e. urban /
        # water / rock). The empty-result case is informative — it tells the
        # user their AOI is on non-soil land and the polygon should be
        # redrawn over actual cropland. We surface this distinctly rather
        # than silently substituting distant data.
        if not result:
            print(
                f"[WARN] SoilGrids returned no values for ({lat}, {lon}) - "
                "all properties null. AOI centroid is likely in SoilGrids' "
                "land-mask exclusion (built-up / water / rock)."
            )
            return {"_no_data_in_land_mask": True}

        return result


# ── Public adapter: SoilDataFetcher ────────────────────────────────────────
# Properties for which there is no real source available right now. These
# are always fabricated until a later task lands real data for them.
_NO_REAL_SOURCE = {"ec", "soil_moisture_current"}


class SoilDataFetcher:
    """Fetch soil data for an AOI, combining SoilGrids real values with
    fabricated regional fallbacks where no real source exists.

    Returns a dict in the same shape consumed by `domain/soil/management.py`,
    plus a `_fabricated_fields` map indicating which properties came from
    a real source vs the regional template.
    """

    @staticmethod
    def fetch_soil_data(lat: float, lon: float,
                        location_name: str = "") -> Dict[str, Any]:
        # Start from the regional template (everything fabricated).
        base = pseudo_satellite.make_default_soil(lat, lon, location_name)
        properties: Dict[str, Any] = base["properties"]
        fabricated: Dict[str, bool] = {k: True for k in properties.keys()}
        in_built_up_land = False

        # Overlay SoilGrids real values where available.
        real_values = SoilGridsClient.fetch(lat, lon)
        if real_values:
            # Distinguish "no data because this AOI is in built-up land"
            # (HTTP 200 + all-null) from "got real data". The former does
            # NOT overlay anything — every property stays fabricated, but
            # the caller learns *why* via the in_built_up_land flag.
            if real_values.get("_no_data_in_land_mask"):
                in_built_up_land = True
            else:
                for key, value in real_values.items():
                    properties[key] = value
                    fabricated[key] = False

                # Derive USDA texture class from real sand/silt/clay if we
                # have all three. Texture is "not fabricated" because its
                # input chain is real measurements.
                sand = real_values.get("sand_percent")
                silt = real_values.get("silt_percent")
                clay = real_values.get("clay_percent")
                if sand is not None and silt is not None and clay is not None:
                    texture = classify_usda_texture(sand, silt, clay)
                    properties["texture"] = texture
                    fabricated["texture"] = False

                    # Derive WHC + infiltration from texture. These are
                    # lookup-table outputs of real inputs, not measured, but
                    # closer to "real" than the regional template was.
                    properties["water_holding_capacity"] = whc_from_texture(texture)
                    properties["infiltration_rate"] = infiltration_from_texture(texture)
                    fabricated["water_holding_capacity"] = False
                    fabricated["infiltration_rate"] = False

        # Always-fabricated properties (no real source available yet).
        for key in _NO_REAL_SOURCE:
            fabricated[key] = True

        # Drop the legacy whole-dict flag if pseudo_satellite still sets it.
        base.pop("_fabricated", None)
        base["properties"] = properties
        base["_fabricated_fields"] = fabricated
        base["_aoi_in_built_up_land"] = in_built_up_land
        return base
