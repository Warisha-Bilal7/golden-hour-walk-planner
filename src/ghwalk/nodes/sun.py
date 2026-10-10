from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def run(state):
    tz = ZoneInfo(state.get("tz", "UTC"))
    now = datetime.now(tz).replace(second=0, microsecond=0)
    duration = state["intake"]["duration_min"]
    walk_end = now
    walk_start = walk_end - timedelta(minutes=duration)
    sunset = walk_end + timedelta(minutes=10)
    golden_start = sunset - timedelta(minutes=30)
    return {
        "sunset_iso": sunset.isoformat(),
        "golden_start_iso": golden_start.isoformat(),
        "walk_start_iso": walk_start.isoformat(),
        "walk_end_iso": walk_end.isoformat(),
        "light_bearing_deg": 270.0,
        "warnings": ["sun: stub times (astral not wired yet)"],
    }
