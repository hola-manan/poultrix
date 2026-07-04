"""Tests for the soil-sensor contract + mock."""

from datetime import datetime, timedelta, timezone

from jeevn.infrastructure.sensors import MockSoilSensor, SensorReading


def test_mock_sensor_reads_value():
    s = MockSoilSensor(soil_moisture=0.22)
    r = s.read()
    assert r is not None
    assert r.soil_moisture == 0.22
    assert r.is_fraction is False


def test_mock_sensor_failure_returns_none():
    assert MockSoilSensor(fail=True).read() is None


def test_reading_freshness():
    fresh = SensorReading(soil_moisture=0.2,
                          timestamp=datetime.now(timezone.utc))
    assert fresh.is_fresh(180)

    stale = SensorReading(
        soil_moisture=0.2,
        timestamp=datetime.now(timezone.utc) - timedelta(hours=5))
    assert not stale.is_fresh(180)


def test_naive_timestamp_treated_as_utc():
    r = SensorReading(soil_moisture=0.2, timestamp=datetime.utcnow())
    assert r.is_fresh(180)


def test_none_value_is_never_fresh():
    assert not SensorReading(soil_moisture=None).is_fresh(180)
