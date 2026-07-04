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
  2. India Soil Health Card district ......... confidence "medium"  (bundled CSV)
  3. SoilGrids / pedotransfer estimate ....... confidence "low" (P: "very_low")
  4. none available → signal fabricated ...... confidence "none" (caller keeps
     the legacy constant, unchanged behaviour)
"""

import csv
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

# ── Category → soil-supply fraction ─────────────────────────────────────────
# Low soil status ⇒ soil supplies little of the recommended dose ⇒ fertilise
# most of it. High status ⇒ soil already supplies the crop's need.
_STATUS_FRACTION = {"low": 0.4, "medium": 0.7, "high": 1.0}

_NUTRIENTS = ("N", "P", "K")

# Bundled Soil Health Card district table (built by
# scripts/dev_smoke/build_shc_district_npk.py from data.gov.in). Same
# committed-artifact pattern as the DEM / salinity India rasters.
_SHC_CSV_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "static" / "shc_district_npk.csv"
)


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


# ── Tier 2: India Soil Health Card district lookup ──────────────────────────
@lru_cache(maxsize=1)
def _load_shc_table() -> Dict[str, Dict[str, Any]]:
    """Load the bundled SHC district table keyed by 'state|district' (lower).

    Expected CSV columns:
      state, district,
      n_low_pct, n_med_pct, n_high_pct,
      p_low_pct, p_med_pct, p_high_pct,
      k_low_pct, k_med_pct, k_high_pct
    Missing file → empty table (SHC tier is simply skipped).
    """
    table: Dict[str, Dict[str, Any]] = {}
    if not _SHC_CSV_PATH.exists():
        return table
    try:
        with open(_SHC_CSV_PATH, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                state = (row.get("state") or "").strip().lower()
                district = (row.get("district") or "").strip().lower()
                if not state:
                    continue
                key = f"{state}|{district}"
                table[key] = row
    except Exception as e:  # a malformed bundle must not break advisories
        print(f"[WARN] SHC district table load failed: {e}")
    return table


def _shc_supply(state: str, district: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """Per-nutrient supply fraction + status from the SHC district table.

    Falls back to a state-level average when the exact district is absent.
    """
    table = _load_shc_table()
    if not table:
        return None
    state_l = (state or "").strip().lower()
    district_l = (district or "").strip().lower()

    row = table.get(f"{state_l}|{district_l}")
    rows = [row] if row else [
        r for k, r in table.items() if k.startswith(f"{state_l}|")
    ]
    rows = [r for r in rows if r]
    if not rows:
        return None

    prefix = {"N": "n", "P": "p", "K": "k"}
    out: Dict[str, Dict[str, Any]] = {}
    for nutrient in _NUTRIENTS:
        p = prefix[nutrient]
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
                "source": "shc-district" if row else "shc-state",
                "confidence": "medium" if row else "low",
            }
    return out or None


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
    tier2 = _shc_supply(location.get("state", ""), location.get("district", "")) or {}
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
