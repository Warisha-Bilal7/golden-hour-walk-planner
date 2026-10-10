from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from .map_fetch import CACHE_DIR

TTL_SECONDS = 30 * 60
TIMEOUT_SECONDS = 12


def _cache_file(lat: float, lon: float) -> Path:
    return CACHE_DIR / f"weather_{lat:.3f}_{lon:.3f}.json"


def _hour_index(data: dict, target_hour: str) -> int:
    times = data.get("hourly", {}).get("time", [])
    if target_hour in times:
        return times.index(target_hour)
    for i, t in enumerate(times):
        if t.startswith(target_hour):
            return i
    return 0


def _fetch(lat: float, lon: float, tz: str, target_hour: str) -> dict:
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation_probability,wind_speed_10m",
            "timezone": tz,
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    i = _hour_index(data, target_hour)
    hourly = data["hourly"]
    return {
        "time": hourly["time"][i],
        "temp_c": hourly["temperature_2m"][i],
        "precip_prob": hourly["precipitation_probability"][i],
        "wind_kmh": hourly["wind_speed_10m"][i],
    }


def _pluck(entry: dict, source: str) -> dict:
    return {
        "temp_c": entry.get("temp_c"),
        "precip_prob": entry.get("precip_prob"),
        "wind_kmh": entry.get("wind_kmh"),
        "source": source,
    }


def _fresh(fetched_iso: str) -> bool:
    try:
        fetched = datetime.fromisoformat(fetched_iso)
        age = (datetime.now(timezone.utc) - fetched).total_seconds()
        return age < TTL_SECONDS
    except (TypeError, ValueError):
        return False


def run(state):
    lat, lon = state["start_lat"], state["start_lon"]
    target_hour = state.get("walk_end_iso", "")[:13]  # "YYYY-MM-DDTHH"
    tz = state.get("tz", "UTC")
    cache = _cache_file(lat, lon)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    saved = None
    entry = None
    if cache.exists():
        try:
            saved = json.loads(cache.read_text(encoding="utf-8"))
            entry = saved.get("entry")
        except (json.JSONDecodeError, OSError):
            entry = None

    if entry is not None and _fresh(saved["fetched_at"]):
        return {"weather": _pluck(entry, "cache")}

    try:
        entry = _fetch(lat, lon, tz, target_hour)
    except Exception as exc:
        if entry is not None:
            return {
                "weather": _pluck(entry, "cache"),
                "warnings": [f"weather: Open-Meteo unreachable, used stale cache ({exc})"],
            }
        return {
            "weather": _pluck({}, "none"),
            "warnings": [f"weather: unavailable (offline?), skipped ({exc})"],
        }

    cache.write_text(
        json.dumps({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "entry": entry,
        }),
        encoding="utf-8",
    )
    return {"weather": _pluck(entry, "live")}