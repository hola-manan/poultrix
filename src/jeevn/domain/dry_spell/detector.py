"""
Dry-spell detection.

A dry spell is a run of consecutive days with negligible rainfall. We measure it
across two windows and join them at "today":

  * recent run  — trailing consecutive past days with rain < DRY_DAY_MM
  * forecast run — leading consecutive forward days with rain < DRY_DAY_MM AND
                   rain probability < RAIN_PROB_PCT (a high-probability day is
                   not "dry" even if the modelled amount rounds to ~0)

`dry_days = recent_run + forecast_run`. A spell is flagged when
`dry_days >= min_dry_days`.

FAIL-SAFE: this module never invents data. If the caller passes empty/None
series (e.g. the weather fetch failed or returned a fabricated placeholder), the
result carries `data_gap=True` and `is_dry_spell=False` — a missing forecast must
never be read as "no rain" and page a farmer with a false dry-spell alert. The
caller is responsible for passing `data_gap=True` when the upstream source was
fabricated; this detector also sets it when it has nothing to work with.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence


@dataclass
class DrySpellResult:
    is_dry_spell: bool
    dry_days: int
    recent_dry_run: int
    forecast_dry_run: int
    severity: str  # "none" | "watch" | "alert" | "urgent"
    data_gap: bool = False
    reasons: List[str] = field(default_factory=list)


def _leading_dry_run(rain: Sequence[float], prob: Optional[Sequence[float]],
                     dry_day_mm: float, rain_prob_pct: float) -> int:
    """Count leading days (from index 0 forward) that are dry."""
    run = 0
    for i, r in enumerate(rain):
        amount = r if r is not None else 0.0
        p = None
        if prob is not None and i < len(prob):
            p = prob[i]
        is_dry = amount < dry_day_mm and (p is None or p < rain_prob_pct)
        if is_dry:
            run += 1
        else:
            break
    return run


def _trailing_dry_run(rain: Sequence[float], dry_day_mm: float) -> int:
    """Count trailing consecutive days (most-recent-last) that are dry."""
    run = 0
    for r in reversed(rain):
        amount = r if r is not None else 0.0
        if amount < dry_day_mm:
            run += 1
        else:
            break
    return run


class DrySpellDetector:
    """Detect a dry spell from recent + forecast rainfall series."""

    @staticmethod
    def detect(recent_rain: Optional[Sequence[float]],
               forecast_rain: Optional[Sequence[float]],
               forecast_prob: Optional[Sequence[float]] = None,
               *,
               dry_day_mm: float = 1.0,
               rain_prob_pct: float = 30.0,
               min_dry_days: int = 5,
               soil_moisture_deficit_mm: Optional[float] = None,
               data_gap: bool = False) -> DrySpellResult:
        """Return a `DrySpellResult`.

        Args:
            recent_rain: trailing daily precipitation (mm), oldest→newest.
            forecast_rain: forward daily precipitation (mm), today→future.
            forecast_prob: forward daily rain probability (%), aligned with
                `forecast_rain`.
            dry_day_mm: a day with < this many mm counts as dry.
            rain_prob_pct: forecast day with prob >= this is NOT counted dry.
            min_dry_days: threshold for flagging a dry spell.
            soil_moisture_deficit_mm: optional deficit; when positive it
                escalates an alert to "urgent".
            data_gap: pass True when the upstream weather was fabricated/failed;
                forces a no-alert, gap-flagged result.
        """
        have_recent = bool(recent_rain)
        have_forecast = bool(forecast_rain)
        if data_gap or (not have_recent and not have_forecast):
            return DrySpellResult(
                is_dry_spell=False, dry_days=0, recent_dry_run=0,
                forecast_dry_run=0, severity="none", data_gap=True,
                reasons=["weather data unavailable — dry-spell check skipped"],
            )

        recent_run = _trailing_dry_run(recent_rain or [], dry_day_mm)
        forecast_run = _leading_dry_run(
            forecast_rain or [], forecast_prob, dry_day_mm, rain_prob_pct)
        dry_days = recent_run + forecast_run

        is_spell = dry_days >= min_dry_days
        reasons: List[str] = []
        if is_spell:
            reasons.append(
                f"{dry_days} consecutive dry days "
                f"({recent_run} recent + {forecast_run} forecast)"
            )

        severity = "none"
        if is_spell:
            severity = "alert"
            if soil_moisture_deficit_mm is not None and soil_moisture_deficit_mm > 0:
                severity = "urgent"
                reasons.append(
                    f"soil-water deficit {soil_moisture_deficit_mm:.0f} mm — "
                    "crop stress likely"
                )
        elif dry_days >= max(2, min_dry_days - 2):
            severity = "watch"  # approaching threshold; informational only

        return DrySpellResult(
            is_dry_spell=is_spell,
            dry_days=dry_days,
            recent_dry_run=recent_run,
            forecast_dry_run=forecast_run,
            severity=severity,
            data_gap=False,
            reasons=reasons,
        )
