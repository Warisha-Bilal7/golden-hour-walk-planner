from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import SunDirection, azimuth, golden_hour, sun as astral_sun


def run(state):
    tz = ZoneInfo(state.get("tz", "UTC"))
    obs = Observer(latitude=state["start_lat"], longitude=state["start_lon"])
    today = datetime.now(tz).date()
    s = astral_sun(obs, date=today, tzinfo=tz)
    g_start, _g_end = golden_hour(obs, date=today, direction=SunDirection.SETTING, tzinfo=tz)
    walk_end = s["sunset"] - timedelta(minutes=10)
    walk_start = walk_end - timedelta(minutes=state["intake"]["duration_min"])
    return {
        "sunset_iso": s["sunset"].isoformat(),
        "golden_start_iso": g_start.isoformat(),
        "walk_start_iso": walk_start.isoformat(),
        "walk_end_iso": walk_end.isoformat(),
        "light_bearing_deg": float(azimuth(obs, s["sunset"])),
    }