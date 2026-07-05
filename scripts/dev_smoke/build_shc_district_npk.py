"""
Build the bundled India Soil Health Card (SHC) N/P/K lookup tables from the
data.gov.in "Soil Nutrient Analysis" bulk export.

The bulk export is a long-format, village-level CSV (one row per
state/district/block/village x nutrient x level, with `value` = sample count):

    id,year,state_name,state_code,district_name,district_code,block_name,
    block_code,village_name,village_code,nutrient_type,nutrient_name,
    nutrient_level,value

We aggregate the macro nutrients (Nitrogen / Phosphorus / Potassium) at
High/Medium/Low into two committed lookup tables that
`infrastructure/data_sources/soil_nutrients.py` reads at runtime (fully offline
thereafter):

  * data/static/shc_village_npk.csv.gz  — per (state, district, village),
    gzipped (~5 MB) to keep the repo lean.
  * data/static/shc_district_npk.csv    — per (state, district) roll-up
    (sample-count weighted), tiny.

The resolver cascades village -> district -> state, so the fine village data is
used when the farmer's village is known, and district is the reliable fallback
from a lat/lon.

Usage:
    python scripts/dev_smoke/build_shc_district_npk.py <path-to-bulk-csv>
    # or set SHC_LOCAL_CSV=<path>

Village names repeat across blocks within a district; we aggregate those
together (block is not addressable from reverse geocoding anyway). On any
failure the script exits non-zero without writing partial files — we never
ship fabricated district data.
"""

import csv
import gzip
import os
import sys
from collections import defaultdict
from pathlib import Path

_STATIC = Path(__file__).resolve().parents[2] / "data" / "static"
_DISTRICT_OUT = _STATIC / "shc_district_npk.csv"
_VILLAGE_OUT = _STATIC / "shc_village_npk.csv.gz"

# Macro nutrient name -> column prefix; macro level -> slot suffix.
_NUTRIENT_PREFIX = {"Nitrogen": "n", "Phosphorus": "p", "Potassium": "k"}
_LEVELS = {"low": "low", "medium": "med", "high": "high"}

# Fixed 9-slot vector per key: [n_low,n_med,n_high, p_low,p_med,p_high, k_low,k_med,k_high]
_SLOT = {f"{p}_{lvl}": i for i, (p, lvl) in enumerate(
    (p, lvl) for p in ("n", "p", "k") for lvl in ("low", "med", "high"))}

_COLUMNS_DISTRICT = ["state", "district",
                     "n_low_pct", "n_med_pct", "n_high_pct",
                     "p_low_pct", "p_med_pct", "p_high_pct",
                     "k_low_pct", "k_med_pct", "k_high_pct"]
_COLUMNS_VILLAGE = ["state", "district", "village"] + _COLUMNS_DISTRICT[2:]

# CSV column indices in the bulk export.
_C_STATE, _C_DIST, _C_VILLAGE, _C_NAME, _C_LEVEL, _C_VALUE = 2, 4, 8, 11, 12, 13


def _new_vec():
    return [0.0] * 9


def _pcts(vec, base):
    """(low%, med%, high%) for nutrient prefix `base` ('n'/'p'/'k')."""
    lo = vec[_SLOT[f"{base}_low"]]
    me = vec[_SLOT[f"{base}_med"]]
    hi = vec[_SLOT[f"{base}_high"]]
    tot = lo + me + hi
    if tot <= 0:
        return ("", "", "")
    return (round(100 * lo / tot, 1), round(100 * me / tot, 1), round(100 * hi / tot, 1))


def _row_for(vec, keys):
    row = dict(zip(("state", "district", "village"), keys))
    for base in ("n", "p", "k"):
        lo, me, hi = _pcts(vec, base)
        row[f"{base}_low_pct"] = lo
        row[f"{base}_med_pct"] = me
        row[f"{base}_high_pct"] = hi
    return row


def aggregate(csv_path: str):
    village = defaultdict(_new_vec)   # (state, district, village) -> vec
    n_rows = 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader)  # header
        for r in reader:
            n_rows += 1
            prefix = _NUTRIENT_PREFIX.get(r[_C_NAME])
            if prefix is None:
                continue
            level = _LEVELS.get(r[_C_LEVEL].strip().lower())
            if level is None:
                continue
            try:
                val = float(r[_C_VALUE])
            except (ValueError, IndexError):
                continue
            if val <= 0:
                continue
            vec = village[(r[_C_STATE].strip(), r[_C_DIST].strip(), r[_C_VILLAGE].strip())]
            vec[_SLOT[f"{prefix}_{level}"]] += val

    # District roll-up = sample-count-weighted sum of its villages.
    district = defaultdict(_new_vec)
    for (state, dist, _village), vec in village.items():
        d = district[(state, dist)]
        for i, v in enumerate(vec):
            d[i] += v

    return village, district, n_rows


def main() -> int:
    csv_path = (sys.argv[1] if len(sys.argv) > 1 else None) or os.environ.get("SHC_LOCAL_CSV")
    if not csv_path:
        print("ERROR: pass the bulk CSV path as arg1 or set SHC_LOCAL_CSV.", file=sys.stderr)
        return 2
    if not Path(csv_path).exists():
        print(f"ERROR: file not found: {csv_path}", file=sys.stderr)
        return 2

    print(f"Aggregating {csv_path} ...")
    village, district, n_rows = aggregate(csv_path)
    print(f"Scanned {n_rows:,} rows -> {len(village):,} villages, {len(district):,} districts.")
    if not district:
        print("ERROR: no N/P/K macro rows found - wrong file?", file=sys.stderr)
        return 1

    _STATIC.mkdir(parents=True, exist_ok=True)

    with open(_DISTRICT_OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_COLUMNS_DISTRICT)
        w.writeheader()
        for (state, dist), vec in sorted(district.items()):
            row = _row_for(vec, (state, dist, ""))
            row.pop("village")
            w.writerow(row)
    print(f"Wrote {len(district):,} district rows -> {_DISTRICT_OUT}")

    with gzip.open(_VILLAGE_OUT, "wt", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_COLUMNS_VILLAGE)
        w.writeheader()
        for (state, dist, vil), vec in sorted(village.items()):
            w.writerow(_row_for(vec, (state, dist, vil)))
    size_mb = _VILLAGE_OUT.stat().st_size / 1e6
    print(f"Wrote {len(village):,} village rows -> {_VILLAGE_OUT} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
