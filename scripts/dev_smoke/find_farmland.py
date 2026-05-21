"""Probe SoilGrids around Sri Ganganagar to find confirmed-farmland AOIs.

Sri Ganganagar town centre (~29.92, 73.88) sits in a built-up zone that
SoilGrids flags as no-data. The Indira Gandhi Canal command area extends
south and east of town with cropland; this script sweeps a wider grid to
pin down clearly-working farmland coordinates the user can test against.
"""
import math
import requests


def fetch_at(lat: float, lon: float):
    r = requests.get(
        "https://rest.isric.org/soilgrids/v2.0/properties/query",
        params=[
            ("lon", lon), ("lat", lat), ("value", "mean"),
            ("property", "phh2o"), ("property", "soc"),
            ("property", "sand"), ("property", "silt"), ("property", "clay"),
            ("depth", "0-5cm"),
        ],
        headers={"User-Agent": "Jeevn-MVP/0.1.0"},
        timeout=15,
    )
    layers = (r.json().get("properties") or {}).get("layers") or []
    out = {}
    for layer in layers:
        depths = layer.get("depths", [])
        if depths:
            out[layer["name"]] = (depths[0].get("values") or {}).get("mean")
    return out


def main():
    print(f"{'direction':<6} {'dist':>5}  {'lat':>9} {'lon':>10}  pH    OC     sand/silt/clay")
    print("-" * 80)

    center = (29.92, 73.88)
    candidates = []
    # Eight cardinal/diagonal directions, three distances each (10/15/20 km).
    for direction, dlat, dlon in [
        ("N",  +1, 0), ("NE", +1, +1), ("E",  0, +1), ("SE", -1, +1),
        ("S",  -1, 0), ("SW", -1, -1), ("W",  0, -1), ("NW", +1, -1),
    ]:
        for dist_km in (10, 15, 20):
            deg = dist_km / 111.0
            norm = math.sqrt(abs(dlat) + abs(dlon)) or 1.0
            lat = round(center[0] + dlat * deg / norm, 4)
            lon = round(center[1] + dlon * deg / norm, 4)
            candidates.append((direction, dist_km, lat, lon))

    found = []
    for direction, dist, lat, lon in candidates:
        result = fetch_at(lat, lon)
        if not result or all(v is None for v in result.values()):
            continue

        ph = result.get("phh2o")
        soc = result.get("soc")
        sand = result.get("sand")
        silt = result.get("silt")
        clay = result.get("clay")

        ph_s = f"{ph / 10:.1f}" if ph is not None else "-"
        soc_s = f"{soc / 100:.2f}%" if soc is not None else "-"
        comp = "-"
        if sand is not None and silt is not None and clay is not None:
            comp = f"{sand / 10:.0f}/{silt / 10:.0f}/{clay / 10:.0f}"

        print(f"  {direction:<4} {dist:>3}km  {lat:>9.4f}  {lon:>10.4f}  {ph_s:>4}  {soc_s:>6}  {comp}")
        found.append((direction, dist, lat, lon))

    print()
    print(f"Total farmland candidates found: {len(found)}")


if __name__ == "__main__":
    main()
