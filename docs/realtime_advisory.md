# Real-time advisory & dry-spell alerts

Live irrigation/fertilisation guidance that fuses **localized weather forecasts** with
**ground soil-moisture sensor data** and the accurate `jeevn` agronomic pipeline, then emits
**structured + human-readable alerts**. Part 1 generates the advice and alerts; **delivery
(SMS/WhatsApp) is Part 2**, behind the `Notifier` seam already in place.

## Quick start

```bash
# One cycle (uses a MockSoilSensor + ConsoleNotifier; prints alerts + digest)
PYTHONPATH=src python -m jeevn.application.realtime_monitor --once \
    --lat 31.1048 --lon 77.1734 --crop apple --location "Shimla"

# Loop every hour (simple sleep loop; use cron/APScheduler in production)
PYTHONPATH=src python -m jeevn.application.realtime_monitor --loop --interval-min 60 ...
```

Programmatic use:

```python
from jeevn.application.realtime_advisory import RealtimeAdvisor
from jeevn.application.notifier import ConsoleNotifier
from jeevn.infrastructure.sensors import RestSensor   # or MqttSensor / MockSoilSensor

advisor = RealtimeAdvisor()                 # thresholds from env (AdvisoryConfig)
advisory = advisor.evaluate(
    lat=31.1048, lon=77.1734, crop="apple", sowing_date="2026-03-01",
    area_acres=2.0, location_name="Shimla",
    sensor=RestSensor(url="https://gateway.local/plots/42/latest",
                      moisture_path="data.soil_moisture"),
    growth_stage_override=None,             # or pass the stage from your crop DB
    soil_test={"N": "medium", "P": "low", "K": "high"},  # or 0..1 supply fractions
    notifier=ConsoleNotifier(),             # Part-2: swap for a Twilio notifier
)

advisory["alerts"]      # list[Alert]  (severity, kind, title, message, data)
advisory["dry_spell"]   # DrySpellResult
advisory["report"]      # the full accurate jeevn report
```

## What's genuine vs. estimated (honesty matters for an alerter)

| Signal | Basis | Alertable? |
|---|---|---|
| Dry spell | Real recent (`past_days`) + forward Open-Meteo rainfall | ✅ |
| Irrigate-now | Soil-water deficit from **fused ground-sensor** (or modelled) moisture via FAO-56 | ✅ |
| Hold fertigation | Real forecast rain ≥ `LEACH_RAIN_MM` in 48 h (leaching risk) | ✅ |
| High salinity | Real ISRIC EC (India raster coverage) | ✅ |
| N/P/K dose | Tiered resolver (soil test → SHC district → SoilGrids/pedotransfer → constant) | ⚠️ only at ≥ medium confidence; low-confidence stays guidance-only |

**Fail-safe:** if the weather fetch fails or returns a fabricated placeholder, the dry-spell
check is *skipped* (a data gap), never read as "no rain" — so a network blip cannot page a
farmer with a false dry-spell.

## Ground sensor incorporation

No hardware is required to run. Soil moisture is resolved in priority order:

1. **Fresh ground-sensor reading** (`SENSOR_MAX_AGE_MIN`) — highest priority.
2. NISAR L-band → Open-Meteo modelled soil moisture.
3. None → deficit trigger skipped; advisory falls back to the ET0−rain balance.

Adapters (all implement `SoilSensor.read() -> SensorReading | None`, non-throwing):

- `MockSoilSensor` — dev/tests.
- `RestSensor(url, moisture_path=…, is_fraction=…)` — poll a JSON HTTP endpoint. Simplest
  path for a real probe/gateway.
- `MqttSensor(host, topic, moisture_key=…)` — subscribe to a broker topic (`.start()` then
  `.read()`). Requires the optional `paho-mqtt` package.

Raw volumetric readings (`m³/m³`) are normalised to fraction-of-field-capacity using the
AOI's real SoilGrids texture, so they land on the same scale the deficit/pest thresholds use.
Pass `is_fraction=True` if your device already reports 0..1 of field capacity.

## Soil N/P/K profile (India Soil Health Card + SoilGrids)

`infrastructure/data_sources/soil_nutrients.py` replaces the old hardcoded soil-nutrient
constant with a per-nutrient **supply-fraction** resolver:

1. **Injected soil test** (`soil_test=` / `AdvisoryContext`) — confidence `high`.
2. **India Soil Health Card district** — bundled `data/static/shc_district_npk.csv`, keyed by
   state+district from reverse geocoding (state-average fallback). Confidence `medium`.
3. **SoilGrids/pedotransfer** — real N from the SoilGrids `nitrogen` layer; K from CEC/clay;
   P has no reliable proxy (omitted). Confidence `low`.
4. **Constant fallback** — the legacy placeholder, flagged `fabricated`.

### Building the SHC table (one-time)

Runtime is fully offline once the CSV exists (same as the bundled DEM/salinity rasters). To
generate it from data.gov.in:

```bash
DATA_GOV_IN_API_KEY=<your key> SHC_RESOURCE_ID=<district-macro-nutrient resource uuid> \
    python scripts/dev_smoke/build_shc_district_npk.py
```

If the CSV is absent (e.g. not yet built), the resolver simply skips the SHC tier and falls
back to SoilGrids/pedotransfer — no crash, clearly lower confidence. We never ship fabricated
district data.

## Configuration (env)

| Var | Default | Meaning |
|---|---|---|
| `PAST_DAYS` | 10 | recent-rain window for the current dry run |
| `FORECAST_DAYS` | 7 | forward forecast horizon |
| `DRY_DAY_MM` | 1.0 | a day under this many mm counts as dry |
| `RAIN_PROB_PCT` | 30 | forecast day with prob ≥ this is not counted dry |
| `DRY_SPELL_DAYS` | 5 | consecutive dry days to flag a spell |
| `LEACH_RAIN_MM` | 15 | ≥ this rain in 48 h → hold fertigation |
| `SENSOR_MAX_AGE_MIN` | 180 | readings older than this are ignored |
| `DISABLE_SOILGRIDS_NPK` | — | set `1` to drop the low-confidence NPK proxy tier |

## Part 2 (not in this change)

- SMS/WhatsApp delivery via a `TwilioNotifier` behind the existing `Notifier` interface.
- Alert-history persistence / cross-run dedupe; production scheduler; multi-farm fan-out.
