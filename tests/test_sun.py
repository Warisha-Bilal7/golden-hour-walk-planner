from datetime import datetime, timedelta, timezone

from ghwalk.nodes import sun as sun_node

KARACHI = {"start_lat": 24.8607, "start_lon": 67.0011, "tz": "Asia/Karachi",
           "intake": {"duration_min": 45}}


class _FixedNow:
    def __init__(self, when):
        self.when = when

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 10, 12, 0, tzinfo=tz or timezone.utc)


def test_sun_karachi_before_dark(monkeypatch):
    monkeypatch.setattr(sun_node, "datetime", _FixedNow)
    out = sun_node.run(dict(KARACHI))
    sunset = datetime.fromisoformat(out["sunset_iso"])
    walk_end = datetime.fromisoformat(out["walk_end_iso"])
    walk_start = datetime.fromisoformat(out["walk_start_iso"])
    golden = datetime.fromisoformat(out["golden_start_iso"])
    assert golden < sunset
    assert walk_end == sunset - timedelta(minutes=10)
    assert walk_start == walk_end - timedelta(minutes=45)
    assert 240 <= out["light_bearing_deg"] <= 300


def test_sun_sunset_equator_equinox_trusted(monkeypatch):
    monkeypatch.setattr(sun_node, "datetime", _FixedNow)
    state = {"start_lat": 0.0, "start_lon": 0.0, "tz": "UTC",
             "intake": {"duration_min": 30}}
    sunset = datetime.fromisoformat(sun_node.run(state)["sunset_iso"])
    minutes = sunset.hour * 60 + sunset.minute
    assert 17 * 60 + 45 <= minutes <= 18 * 60 + 15