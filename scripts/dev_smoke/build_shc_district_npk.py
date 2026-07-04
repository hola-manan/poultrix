"""
Build the bundled India Soil Health Card (SHC) district N/P/K table.

Fetches district-wise macronutrient status (% of samples Low / Medium / High
for N, P, K) from the Government of India open-data portal (data.gov.in) and
writes `data/static/shc_district_npk.csv`, which
`infrastructure/data_sources/soil_nutrients.py` reads at runtime. Same
committed-artifact pattern as the bundled DEM / salinity India rasters —
runtime stays fully offline (no API key, no network) once this CSV exists.

Usage:
    DATA_GOV_IN_API_KEY=xxxx SHC_RESOURCE_ID=<resource-uuid> \
        python scripts/dev_smoke/build_shc_district_npk.py

Notes:
  * data.gov.in requires a free API key (https://data.gov.in → "Sign In" →
    "My Account" → API key). Pass it as DATA_GOV_IN_API_KEY.
  * SHC publishes several macronutrient resources; set SHC_RESOURCE_ID to the
    district-wise macro-nutrient dataset you want to bundle. Field names differ
    between resources, so the column mapping below is best-effort and prints the
    keys it saw to help you adjust.
  * On any failure this script exits non-zero WITHOUT writing a partial/fake
    file — the resolver then simply skips the SHC tier. We never fabricate
    district data.
"""

import csv
import os
import sys
from pathlib import Path

import requests

_OUT = Path(__file__).resolve().parents[2] / "data" / "static" / "shc_district_npk.csv"
_API = "https://api.data.gov.in/resource/{rid}"

# Best-effort field-name candidates for each logical column (lowercased match).
_FIELD_CANDIDATES = {
    "state": ["state", "state_name", "statename"],
    "district": ["district", "district_name", "districtname"],
    "n_low_pct": ["nitrogen_low", "n_low", "low_n", "n_low_pct"],
    "n_med_pct": ["nitrogen_medium", "n_medium", "medium_n", "n_med_pct"],
    "n_high_pct": ["nitrogen_high", "n_high", "high_n", "n_high_pct"],
    "p_low_pct": ["phosphorous_low", "phosphorus_low", "p_low", "low_p"],
    "p_med_pct": ["phosphorous_medium", "phosphorus_medium", "p_medium", "medium_p"],
    "p_high_pct": ["phosphorous_high", "phosphorus_high", "p_high", "high_p"],
    "k_low_pct": ["potassium_low", "k_low", "low_k"],
    "k_med_pct": ["potassium_medium", "k_medium", "medium_k"],
    "k_high_pct": ["potassium_high", "k_high", "high_k"],
}
_COLUMNS = list(_FIELD_CANDIDATES.keys())


def _pick(record: dict, candidates: list):
    lower = {k.lower(): v for k, v in record.items()}
    for c in candidates:
        if c in lower and lower[c] not in (None, ""):
            return lower[c]
    return ""


def fetch_records(resource_id: str, api_key: str) -> list:
    records, offset, limit = [], 0, 1000
    while True:
        resp = requests.get(
            _API.format(rid=resource_id),
            params={"api-key": api_key, "format": "json",
                    "offset": offset, "limit": limit},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json().get("records", []) or []
        if not batch:
            break
        records.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return records


def main() -> int:
    api_key = os.environ.get("DATA_GOV_IN_API_KEY")
    resource_id = os.environ.get("SHC_RESOURCE_ID")
    if not api_key or not resource_id:
        print("ERROR: set DATA_GOV_IN_API_KEY and SHC_RESOURCE_ID env vars.",
              file=sys.stderr)
        print("See the module docstring for how to obtain them.", file=sys.stderr)
        return 2

    try:
        records = fetch_records(resource_id, api_key)
    except Exception as e:
        print(f"ERROR: fetch failed: {e}", file=sys.stderr)
        return 1
    if not records:
        print("ERROR: no records returned; check SHC_RESOURCE_ID.", file=sys.stderr)
        return 1

    print(f"Fetched {len(records)} records. Sample keys: "
          f"{sorted(records[0].keys())}")

    rows = []
    for rec in records:
        row = {col: _pick(rec, cands) for col, cands in _FIELD_CANDIDATES.items()}
        if row["state"] and (row["n_low_pct"] or row["p_low_pct"] or row["k_low_pct"]):
            rows.append(row)
    if not rows:
        print("ERROR: could not map any rows — adjust _FIELD_CANDIDATES to the "
              "printed keys above.", file=sys.stderr)
        return 1

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(_OUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} district rows → {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
