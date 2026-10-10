from __future__ import annotations

import argparse

from .graph import build_graph
from .state import initial_state

DEFAULT_LAT = 24.8607
DEFAULT_LON = 67.0011
DEFAULT_TZ = "Asia/Karachi"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ghwalk", description="Golden hour walk planner")
    parser.add_argument("--request", default="45 minutes before dark, trees and quiet")
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT)
    parser.add_argument("--lon", type=float, default=DEFAULT_LON)
    parser.add_argument("--tz", default=DEFAULT_TZ)
    parser.add_argument("--model", default="qwen2.5:3b")
    args = parser.parse_args(argv)

    app = build_graph()
    state = initial_state(args.request, args.lat, args.lon, args.tz, args.model)
    result = app.invoke(state)

    best = result.get("best") or {}
    print("=== golden hour walk ===")
    print(f"request      : {state['user_request']}")
    print(f"sunset       : {result.get('sunset_iso')}")
    print(f"walk window  : {result.get('walk_start_iso')} -> {result.get('walk_end_iso')}")
    print(f"distance     : {best.get('length_m', 0) / 1000:.2f} km")
    print(f"green / ovlp : {best.get('green_pct', 0):.0%} / {best.get('overlap_pct', 0):.0%}")
    print(f"attempts     : {result.get('attempt')}")
    print(f"fallback     : {result.get('used_fallback')}")
    print(f"card         : {result.get('card_text', '')}")
    print(f"html / gpx   : output/card.html | {result.get('gpx_path')}")
    for w in result.get("warnings", []):
        print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
