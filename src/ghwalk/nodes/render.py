from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

OUT_DIR = Path("output")


def _gpx(state) -> str:
    lat = state.get("start_lat")
    lon = state.get("start_lon")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="ghwalk" xmlns="http://www.topografix.com/GPX/1/1">\n'
        "  <trk><name>golden hour loop</name><trkseg>\n"
        f'    <trkpt lat="{lat}" lon="{lon}"></trkpt>\n'
        "  </trkseg></trk>\n"
        "</gpx>\n"
    )


def run(state):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    card_text = re.sub(r"\[\[(.+?)\]\]", r"\1", state.get("card_text", ""))
    env = Environment(
        loader=PackageLoader("ghwalk", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("card.html.j2")
    html = template.render(
        card_text=card_text,
        km=(state.get("best") or {}).get("length_m", 0.0) / 1000,
        sunset=state.get("sunset_iso", "")[:16].replace("T", " "),
        walk_start=state.get("walk_start_iso", "")[:16].replace("T", " "),
        weather=state.get("weather", {}),
        used_fallback=state.get("used_fallback", False),
    )
    html_path = OUT_DIR / "card.html"
    html_path.write_text(html, encoding="utf-8")
    gpx_path = OUT_DIR / "route.gpx"
    gpx_path.write_text(_gpx(state), encoding="utf-8")
    return {
        "pdf_path": "",
        "gpx_path": str(gpx_path),
        "warnings": ["render: stub, HTML + GPX written, no PDF"],
    }
