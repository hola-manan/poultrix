"""
Soil N/P/K profile resolver — replaces the hardcoded "current soil levels"
constant in `domain/fertilizer/requirements.py` with a tiered, provenance-tagged
estimate.

Why a *supply fraction* instead of absolute kg/acre
---------------------------------------------------
jeevn's fertilizer model compares a crop's recommended nutrient dose (the
`nutrient_requirements_kg_per_acre` template in `crop/phenology.py`) against the
soil's current supply, and fertilises the gap. The template targets are on a
per-acre recommended-dose scale, NOT a soil-test available-nutrient scale
(SHC/SoilGrids report available N in the *hundreds of kg/ha*). Forcing those two
scales together produces nonsense gaps.

So each tier here yields, per nutrient, a **soil-supply fraction in [0, 1]**
(0 = soil supplies nothing → fertilise the full recommended dose; 1 = soil is
replete → no fertiliser needed) plus a Low/Medium/High status and its provenance.
This is exactly how a Soil Health Card recommendation works — reduce the dose as
soil-test status rises — and it keeps the units consistent with the existing
model. `requirements.py` then computes `current = supply_fraction × target`.

Tiers (best → worst), resolved per nutrient independently:
  1. injected soil test (host DB) ............ confidence "high"
  2. India Soil Health Card, cascading village → district → state:
       - village .............................. confidence "medium" (needs a
         host-known village; not resolvable from lat/lon alone)
       - district ............................. confidence "medium" (bundled CSV;
         the reliable fallback from a lat/lon)
       - state average ........................ confidence "low"
  3. SoilGrids / pedotransfer estimate ....... confidence "low" (P: "very_low")
  4. none available → signal fabricated ...... confidence "none" (caller keeps
     the legacy constant, unchanged behaviour)
"""

import csv
import gzip
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

# ── Category → soil-supply fraction ─────────────────────────────────────────
# Low soil status ⇒ soil supplies little of the recommended dose ⇒ fertilise
# most of it. High status ⇒ soil already supplies the crop's need.
_STATUS_FRACTION = {"low": 0.4, "medium": 0.7, "high": 1.0}

_NUTRIENTS = ("N", "P", "K")

# Bundled Soil Health Card tables (built by
# scripts/dev_smoke/build_shc_district_npk.py from the data.gov.in Soil Nutrient
# Analysis export). Same committed-artifact pattern as the DEM / salinity India
# rasters. The village table is gzipped (~4 MB) and loaded lazily only when a
# village is known; the district table is the reliable lat/lon fallback.
_STATIC_DIR = Path(__file__).resolve().parents[4] / "data" / "static"
_SHC_CSV_PATH = _STATIC_DIR / "shc_district_npk.csv"
_SHC_VILLAGE_PATH = _STATIC_DIR / "shc_village_npk.csv.gz"


def _norm(s: Optional[str]) -> str:
    """Normalise an admin-unit name for robust matching across sources
    (OSM reverse-geocoding vs SHC): strip accents, lowercase, collapse
    non-alphanumerics to single spaces."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _fraction_from_status(status: Optional[str]) -> Optional[float]:
    if not status:
        return None
    return _STATUS_FRACTION.get(str(status).strip().lower())


def _fraction_from_distribution(low: float, med: float, high: float) -> Optional[float]:
    """Weighted supply fraction from a Low/Med/High sample distribution (%)."""
    total = (low or 0) + (med or 0) + (high or 0)
    if total <= 0:
        return None
    return (low * _STATUS_FRACTION["low"]
            + med * _STATUS_FRACTION["medium"]
            + high * _STATUS_FRACTION["high"]) / total


def _status_from_fraction(frac: float) -> str:
    if frac < 0.55:
        return "low"
    if frac < 0.85:
        return "medium"
    return "high"


# ── Tier 2: India Soil Health Card lookup (village → district → state) ───────
_PREFIX = {"N": "n", "P": "p", "K": "k"}


@lru_cache(maxsize=1)
def _load_shc_table() -> Dict[str, Dict[str, Any]]:
    """Load the bundled SHC district table keyed by norm 'state|district'.

    Columns: state, district, {n,p,k}_{low,med,high}_pct.
    Missing file → empty table (SHC tier simply skipped).
    """
    table: Dict[str, Dict[str, Any]] = {}
    if not _SHC_CSV_PATH.exists():
        return table
    try:
        with open(_SHC_CSV_PATH, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                state = _norm(row.get("state"))
                if not state:
                    continue
                table[f"{state}|{_norm(row.get('district'))}"] = row
    except Exception as e:  # a malformed bundle must not break advisories
        print(f"[WARN] SHC district table load failed: {e}")
    return table


@lru_cache(maxsize=1)
def _load_shc_village_table() -> Dict[str, Dict[str, Any]]:
    """Load the bundled gzipped SHC village table keyed by norm
    'state|district|village'. Loaded lazily (only on the first village lookup)
    because it holds ~270k rows. Missing file → empty (cascade skips this tier).
    """
    table: Dict[str, Dict[str, Any]] = {}
    if not _SHC_VILLAGE_PATH.exists():
        return table
    try:
        with gzip.open(_SHC_VILLAGE_PATH, "rt", newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                state = _norm(row.get("state"))
                village = _norm(row.get("village"))
                if not state or not village:
                    continue
                table[f"{state}|{_norm(row.get('district'))}|{village}"] = row
    except Exception as e:
        print(f"[WARN] SHC village table load failed: {e}")
    return table


def _supply_from_rows(rows, source: str, confidence: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """Build a per-nutrient supply profile from one or more SHC rows (averaged
    across rows for the state-fallback case)."""
    rows = [r for r in rows if r]
    if not rows:
        return None
    out: Dict[str, Dict[str, Any]] = {}
    for nutrient in _NUTRIENTS:
        p = _PREFIX[nutrient]
        fracs = []
        for r in rows:
            try:
                low = float(r.get(f"{p}_low_pct", 0) or 0)
                med = float(r.get(f"{p}_med_pct", 0) or 0)
                high = float(r.get(f"{p}_high_pct", 0) or 0)
            except (TypeError, ValueError):
                continue
            f = _fraction_from_distribution(low, med, high)
            if f is not None:
                fracs.append(f)
        if fracs:
            frac = sum(fracs) / len(fracs)
            out[nutrient] = {
                "supply_fraction": round(frac, 3),
                "status": _status_from_fraction(frac),
                "source": source,
                "confidence": confidence,
            }
    return out or None


def _shc_supply(state: str, district: str,
                village: str = "") -> Optional[Dict[str, Dict[str, Any]]]:
    """Per-nutrient supply profile, cascading village → district → state.

    Village is the finest real data but only usable when the caller knows it
    (it can't be resolved reliably from a lat/lon); district is the dependable
    fallback, then a state-level average.
    """
    state_n = _norm(state)
    if not state_n:
        return None
    district_n = _norm(district)

    # Tier 2a: exact village (finest).
    village_n = _norm(village)
    if village_n:
        vrow = _load_shc_village_table().get(f"{state_n}|{district_n}|{village_n}")
        supply = _supply_from_rows([vrow], "shc-village", "medium")
        if supply:
            return supply

    table = _load_shc_table()
    if not table:
        return None

    # Tier 2b: district.
    supply = _supply_from_rows([table.get(f"{state_n}|{district_n}")],
                               "shc-district", "medium")
    if supply:
        return supply

    # Tier 2c: state-level average across its districts.
    state_rows = [r for k, r in table.items() if k.startswith(f"{state_n}|")]
    return _supply_from_rows(state_rows, "shc-state", "low")


# ── Tier 3: SoilGrids / pedotransfer estimate ───────────────────────────────
# Total-N (g/kg) rough status bands. Total N is not available N, so this is a
# low-confidence proxy — documented as such.
def _n_status_from_total_n(total_n_g_per_kg: Optional[float]) -> Optional[str]:
    if total_n_g_per_kg is None:
        return None
    if total_n_g_per_kg < 0.5:
        return "low"
    if total_n_g_per_kg < 1.0:
        return "medium"
    return "high"


def _k_status_from_cec(cec: Optional[float]) -> Optional[str]:
    # Exchangeable K rises with CEC (cmol(+)/kg). Rough bands.
    if cec is None:
        return None
    if cec < 10:
        return "low"
    if cec < 25:
        return "medium"
    return "high"


def _soilgrids_supply(soil_props: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    n_status = _n_status_from_total_n(soil_props.get("total_nitrogen_g_per_kg"))
    if n_status:
        out["N"] = {
            "supply_fraction": _STATUS_FRACTION[n_status],
            "status": n_status,
            "source": "soilgrids",
            "confidence": "low",
        }

    k_status = _k_status_from_cec(soil_props.get("cec"))
    if k_status:
        out["K"] = {
            "supply_fraction": _STATUS_FRACTION[k_status],
            "status": k_status,
            "source": "soilgrids",
            "confidence": "low",
        }

    # P has no reliable SoilGrids proxy. We deliberately do NOT emit a P
    # estimate here — leaving it to the constant fallback and, crucially,
    # never letting a fabricated P value drive an alert (confidence gate).
    return out


# ── Tier 1: injected soil test ──────────────────────────────────────────────
def _soil_test_supply(soil_test: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Accepts, per nutrient, either a status string ('low'/'medium'/'high')
    or a supply fraction in [0, 1]. Anything else is ignored."""
    out: Dict[str, Dict[str, Any]] = {}
    if not soil_test:
        return out
    for nutrient in _NUTRIENTS:
        raw = soil_test.get(nutrient)
        if raw is None:
            continue
        frac = None
        status = None
        if isinstance(raw, (int, float)) and 0 <= raw <= 1:
            frac = float(raw)
            status = _status_from_fraction(frac)
        elif isinstance(raw, str):
            frac = _fraction_from_status(raw)
            status = raw.strip().lower() if frac is not None else None
        if frac is not None:
            out[nutrient] = {
                "supply_fraction": round(frac, 3),
                "status": status,
                "source": "soil-test",
                "confidence": "high",
            }
    return out


def resolve_npk(location: Dict[str, Any],
                soil_props: Dict[str, Any],
                soil_test: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Resolve a per-nutrient soil-supply profile for N, P, K.

    Returns e.g. `{"N": {"supply_fraction": 0.7, "status": "medium",
    "source": "shc-district", "confidence": "medium"}, ...}`. A nutrient absent
    from every tier is omitted — the caller keeps its legacy constant for that
    nutrient and marks it fabricated.
    """
    tier1 = _soil_test_supply(soil_test)
    tier2 = _shc_supply(
        location.get("state", ""),
        location.get("district", ""),
        location.get("village", ""),
    ) or {}
    tier3 = _soilgrids_supply(soil_props or {})

    # SoilGrids/pedotransfer can be globally disabled (e.g. to force honesty in
    # regions where the proxy is meaningless) via env, without code changes.
    if os.environ.get("DISABLE_SOILGRIDS_NPK") == "1":
        tier3 = {}

    profile: Dict[str, Dict[str, Any]] = {}
    for nutrient in _NUTRIENTS:
        # Highest-confidence tier that has this nutrient wins.
        for tier in (tier1, tier2, tier3):
            if nutrient in tier:
                profile[nutrient] = tier[nutrient]
                break
    return profile
