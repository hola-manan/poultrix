"""
Real-time advisory monitor — thin runner around `RealtimeAdvisor`.

Run one cycle:
    python -m jeevn.application.realtime_monitor --once --lat 31.1 --lon 77.1 \
        --crop apple --location "Shimla"

Loop every N minutes (simple sleep loop; use cron/APScheduler in production):
    python -m jeevn.application.realtime_monitor --loop --interval-min 60 ...

By default it uses a MockSoilSensor (no hardware) and the ConsoleNotifier
(prints alerts). Swap in `RestSensor`/`MqttSensor` and a Part-2 notifier to go
live.
"""

import argparse
import time
from typing import Optional

from jeevn.infrastructure.sensors.mock import MockSoilSensor
from jeevn.infrastructure.sensors.base import SoilSensor
from jeevn.application.realtime_advisory import RealtimeAdvisor, AdvisoryConfig
from jeevn.application.notifier import ConsoleNotifier
from jeevn.application.render import render_advisory


def run_once(lat: float, lon: float, crop: str = "apple",
             sowing_date: Optional[str] = None, area_acres: float = 1.0,
             location_name: str = "", sensor: Optional[SoilSensor] = None,
             min_severity: str = "info",
             config: Optional[AdvisoryConfig] = None) -> dict:
    """Run a single advisory cycle and print the digest. Returns the advisory."""
    advisor = RealtimeAdvisor(config=config)
    notifier = ConsoleNotifier(min_severity=min_severity)
    advisory = advisor.evaluate(
        lat=lat, lon=lon, crop=crop, sowing_date=sowing_date,
        area_acres=area_acres, location_name=location_name,
        sensor=sensor, notifier=notifier,
    )
    print()
    print(render_advisory(advisory))
    return advisory


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Real-time irrigation/fertilisation advisory")
    p.add_argument("--lat", type=float, default=31.1048, help="AOI latitude")
    p.add_argument("--lon", type=float, default=77.1734, help="AOI longitude")
    p.add_argument("--crop", default="apple")
    p.add_argument("--sowing-date", default=None, help="YYYY-MM-DD")
    p.add_argument("--area", type=float, default=1.0, help="area in acres")
    p.add_argument("--location", default="", help="location label")
    p.add_argument("--mock-moisture", type=float, default=0.12,
                   help="MockSoilSensor volumetric m3/m3 reading (default dry)")
    p.add_argument("--no-sensor", action="store_true",
                   help="run without any ground sensor")
    p.add_argument("--min-severity", default="info",
                   choices=["info", "watch", "alert", "urgent"])
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run a single cycle (default)")
    mode.add_argument("--loop", action="store_true", help="run repeatedly")
    p.add_argument("--interval-min", type=int, default=60)
    return p


def main(argv=None) -> None:
    args = _build_arg_parser().parse_args(argv)
    sensor = None if args.no_sensor else MockSoilSensor(soil_moisture=args.mock_moisture)

    def _cycle():
        run_once(args.lat, args.lon, crop=args.crop, sowing_date=args.sowing_date,
                 area_acres=args.area, location_name=args.location, sensor=sensor,
                 min_severity=args.min_severity)

    if args.loop:
        print(f"[monitor] looping every {args.interval_min} min (Ctrl-C to stop)")
        while True:
            try:
                _cycle()
            except Exception as e:  # a bad cycle must not kill the loop
                print(f"[monitor] cycle error: {e}")
            time.sleep(max(60, args.interval_min * 60))
    else:
        _cycle()


if __name__ == "__main__":
    main()
