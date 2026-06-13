"""
Weather-driven grapevine disease risk models.

Two diseases, two very different data requirements — see PROCESSES.md H.1
and the go/no-go that motivated this module:

* **Powdery mildew** (*Erysiphe necator*) is essentially temperature-driven
  (rain suppresses it). The UC Davis **Gubler-Thomas Risk Index** is a
  published hourly-temperature-only model, so a 9-11 km regional grid
  resolves it well at block scale. This is a *confident* alert.

* **Downy mildew** (*Plasmopara viticola*) is leaf-wetness-driven. Leaf
  wetness is microclimate (canopy, dew, irrigation, local convective rain)
  and Open-Meteo has no leaf-wetness variable, so the best a regional feed
  can do is a *hedged* "wet-period favorable — scout/confirm" flag built
  from an RH-derived wetness proxy. Never phrased as "spray now".

Both functions are pure (no I/O); they take aligned hourly series and return
plain dicts, mirroring the stateless style of
``remote_sensing/analysis/signals.py``.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple
from collections import OrderedDict


# ── Gubler-Thomas powdery mildew index ──────────────────────────────────────

# 70-85 °F conidial-reproduction optimum and the 95 °F heat threshold, in °C.
_GT_LOW_C = 21.0
_GT_HIGH_C = 30.0
_GT_HEAT_C = 35.0
_GT_QUALIFYING_HOURS = 6          # continuous hours in band to "qualify" a day
_GT_INIT_STREAK = 3               # consecutive qualifying days to initiate
_GT_INIT_INDEX = 60
_GT_STEP_UP = 20
_GT_STEP_DOWN = 10
_GT_HEAT_PENALTY = 10


def _group_by_day(times: Sequence[str],
                  values: Sequence[Optional[float]]) -> "OrderedDict[str, List[float]]":
    """Group an hourly series into {date_str: [hourly values]} preserving order.

    `times` are ISO-ish stamps like '2026-05-14T13:00'; the date is the part
    before 'T'. Null values are dropped (Open-Meteo can return sparse hours).
    """
    days: "OrderedDict[str, List[float]]" = OrderedDict()
    for t, v in zip(times, values):
        if v is None:
            continue
        day = str(t).split("T")[0]
        days.setdefault(day, []).append(float(v))
    return days


def _max_run_in_band(temps: Sequence[float], lo: float, hi: float) -> int:
    """Longest run of consecutive entries with lo <= temp <= hi."""
    best = run = 0
    for t in temps:
        if lo <= t <= hi:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def gubler_powdery_mildew_index(
    hourly_times: Sequence[str],
    hourly_temps_c: Sequence[Optional[float]],
    prev_index: float = 0.0,
    initiated: bool = False,
) -> Dict[str, Any]:
    """UC Davis Gubler-Thomas powdery-mildew risk index from hourly temps.

    Rules (per calendar day in the supplied window):
      * a day *qualifies* if it has >= 6 continuous hours in 21-30 °C;
      * before initiation, 3 consecutive qualifying days set the index to 60;
      * after initiation, each qualifying day +20, each non-qualifying -10;
      * any day reaching >= 35 °C takes an additional -10 heat penalty;
      * the index is clamped to 0-100.

    `prev_index` / `initiated` let the caller carry state across runs; the
    default (0 / False) computes the index fresh over the window.

    Returns ``{index, risk_level, spray_interval_days, qualifying_days,
    days_evaluated, rationale}``.
    """
    days = _group_by_day(hourly_times, hourly_temps_c)

    index = float(prev_index)
    streak = 0
    qualifying = 0
    for _day, temps in days.items():
        qualifies = _max_run_in_band(temps, _GT_LOW_C, _GT_HIGH_C) >= _GT_QUALIFYING_HOURS
        hot = any(t >= _GT_HEAT_C for t in temps)

        if not initiated:
            streak = streak + 1 if qualifies else 0
            if streak >= _GT_INIT_STREAK:
                index = max(index, _GT_INIT_INDEX)
                initiated = True
        else:
            index += _GT_STEP_UP if qualifies else -_GT_STEP_DOWN

        if hot:
            index -= _GT_HEAT_PENALTY

        index = max(0.0, min(100.0, index))
        if qualifies:
            qualifying += 1

    if index >= 60:
        level, interval = "high", 14
    elif index >= 30:
        level, interval = "moderate", 17
    else:
        level, interval = "low", 21

    rationale = (
        f"Gubler-Thomas index {index:.0f}/100 over {len(days)} day(s); "
        f"{qualifying} day(s) had >=6 continuous hours in 21-30 deg C "
        f"(conidial-reproduction optimum). "
        + {
            "high": "Sustained favorable temperatures - tighten spray interval.",
            "moderate": "Intermittently favorable - hold a protective interval.",
            "low": "Temperatures unfavorable for reproduction - low pressure.",
        }[level]
    )

    return {
        "index": round(index, 0),
        "risk_level": level,
        "spray_interval_days": interval,
        "qualifying_days": qualifying,
        "days_evaluated": len(days),
        "rationale": rationale,
    }


# ── Downy mildew wet-period risk (hedged regional proxy) ─────────────────────

_DM_RH_WET = 90.0                 # RH (%) at/above which we treat leaf as wet
_DM_PRECIP_WET = 0.2              # mm/h precipitation that also counts as wet
_DM_TEMP_MIN = 13.0               # infection band lower bound (deg C)
_DM_TEMP_MAX = 30.0
_DM_TEMP_OPT_LO = 15.0            # optimum 15-22 deg C
_DM_TEMP_OPT_HI = 22.0
_DM_MIN_WET_HOURS = 4             # minimum favorable wet-period length
_DM_HIGH_WET_HOURS = 8           # a long optimal wet period -> high
_DM_PRIMARY_RAIN_MM = 10.0        # "3-10 rule": >=10 mm rain ...
_DM_PRIMARY_TEMP_C = 10.0         # ... at >=10 deg C ...
_DM_PRIMARY_SHOOT_CM = 10.0       # ... with shoots >=10 cm


def _longest_favorable_wet_run(
    temps: Sequence[float], rhs: Sequence[float], precs: Sequence[float],
) -> Tuple[int, bool]:
    """Longest consecutive run of 'wet' hours (RH>=90 or rain) whose temps sit
    in the 13-30 deg C infection band. Returns (run_hours, touched_optimum)
    where touched_optimum is True if any hour of the best run was 15-22 deg C.
    """
    best = run = 0
    best_opt = cur_opt = False
    for t, rh, pr in zip(temps, rhs, precs):
        wet = (rh is not None and rh >= _DM_RH_WET) or (pr is not None and pr > _DM_PRECIP_WET)
        in_band = t is not None and _DM_TEMP_MIN <= t <= _DM_TEMP_MAX
        if wet and in_band:
            run += 1
            if _DM_TEMP_OPT_LO <= t <= _DM_TEMP_OPT_HI:
                cur_opt = True
            if run > best:
                best, best_opt = run, cur_opt
        else:
            run = 0
            cur_opt = False
    return best, best_opt


def _primary_infection_rule(
    times: Sequence[str], temps: Sequence[float], precs: Sequence[float],
    shoot_length_cm: Optional[float],
) -> bool:
    """Simplified '3-10 rule' primary-infection check: a rolling 24-h window
    with >=10 mm rain while temperature stays >=10 deg C, and (if known)
    shoots >=10 cm. Shoot length defaults to met when unknown (can't disprove).
    """
    if shoot_length_cm is not None and shoot_length_cm < _DM_PRIMARY_SHOOT_CM:
        return False
    by_day = _group_by_day(times, precs)
    temp_by_day = _group_by_day(times, temps)
    for day, day_prec in by_day.items():
        if sum(day_prec) >= _DM_PRIMARY_RAIN_MM:
            day_temps = temp_by_day.get(day, [])
            if day_temps and min(day_temps) >= _DM_PRIMARY_TEMP_C:
                return True
    return False


def downy_mildew_wet_period_risk(
    hourly_times: Sequence[str],
    hourly_temps_c: Sequence[Optional[float]],
    hourly_rh_pct: Sequence[Optional[float]],
    hourly_precip_mm: Sequence[Optional[float]],
    shoot_length_cm: Optional[float] = None,
) -> Dict[str, Any]:
    """Hedged downy-mildew 'wet-period favorable' flag from regional hourly
    weather. RH is used as a *proxy* for leaf wetness — this is explicitly a
    regional, non-specific signal (confidence='regional-proxy'). Output is
    framed for scouting/confirmation, never as a direct spray instruction.

    Returns ``{favorable, risk_level, wet_hours, primary_infection,
    confidence, rationale}``.
    """
    temps = [t for t in hourly_temps_c]
    rhs = [r for r in hourly_rh_pct]
    precs = [p for p in hourly_precip_mm]

    wet_hours, touched_opt = _longest_favorable_wet_run(temps, rhs, precs)
    primary = _primary_infection_rule(hourly_times, temps, precs, shoot_length_cm)

    favorable = primary or wet_hours >= _DM_MIN_WET_HOURS
    if primary or (wet_hours >= _DM_HIGH_WET_HOURS and touched_opt):
        level = "high"
    elif favorable:
        level = "moderate"
    else:
        level = "low"

    reasons = []
    if primary:
        reasons.append("a >=10 mm rain day at >=10 deg C met the primary-infection rule")
    if wet_hours >= _DM_MIN_WET_HOURS:
        reasons.append(
            f"a {wet_hours}-hour wet period (RH>=90% / rain) fell in the "
            f"13-30 deg C infection band"
            + (" including the 15-22 deg C optimum" if touched_opt else "")
        )
    if not reasons:
        reasons.append("no sustained wet period in the infection band")

    rationale = (
        "Downy-mildew conditions " + ("FAVORABLE" if favorable else "not favorable")
        + ": " + "; ".join(reasons)
        + ". Regional estimate from modelled RH (no in-canopy leaf-wetness "
        "sensor) - scout the block to confirm before acting."
    )

    return {
        "favorable": favorable,
        "risk_level": level,
        "wet_hours": wet_hours,
        "primary_infection": primary,
        "confidence": "regional-proxy",
        "rationale": rationale,
    }
