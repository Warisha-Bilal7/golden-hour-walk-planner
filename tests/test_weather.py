import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import requests

from ghwalk.nodes import weather as weather_node

STATE = {
    "start_lat": 24.8607,
    "start_lon": 67.0011,
    "tz": "Asia/Karachi",
    "walk_end_iso": "2026-10-10T21:30:00+05:00",
}

_HOURLY = {
    "time": ["2026-10-10T20:00", "2026-10-10T21:00", "2026-10-10T22:00"],
    "temperature_2m": [30.0, 29.0, 28.0],
    "precipitation_probability": [10, 20, 30],
    "wind_speed_10m": [8.0, 9.0, 10.0],
}


class _Resp:
    def __init__(self, data=None, exc=None):
        self._data = data
        self._exc = exc

    def raise_for_status(self):
        if self._exc:
            raise self._exc
        return None

    def json(self):
        return self._data


def _fake_get(_url=None, **kwargs):
    return _Resp({"hourly": _HOURLY})


def test_weather_live_then_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(weather_node, "requests", SimpleNamespace(get=_fake_get))
    out = weather_node.run(dict(STATE))
    assert out["weather"]["source"] == "live"
    assert out["weather"]["temp_c"] == 29.0
    assert out["weather"]["precip_prob"] == 20
    assert out["weather"]["wind_kmh"] == 9.0

    out = weather_node.run(dict(STATE))
    assert out["weather"]["source"] == "cache"


def test_weather_offline_skips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _boom(_url=None, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(weather_node, "requests", SimpleNamespace(get=_boom))
    out = weather_node.run(dict(STATE))
    assert out["weather"]["source"] == "none"
    assert out["weather"]["temp_c"] is None
    assert any("unavailable" in w for w in out["warnings"])


def test_weather_stale_cache_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    cache = weather_node._cache_file(STATE["start_lat"], STATE["start_lon"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({
        "fetched_at": old.isoformat(),
        "entry": {"temp_c": 25.0, "precip_prob": 5, "wind_kmh": 11.0},
    }))

    def _boom(_url=None, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(weather_node, "requests", SimpleNamespace(get=_boom))
    out = weather_node.run(dict(STATE))
    assert out["weather"]["source"] == "cache"
    assert out["weather"]["temp_c"] == 25.0
    assert any("stale" in w for w in out["warnings"])