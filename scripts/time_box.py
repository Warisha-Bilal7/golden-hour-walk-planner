"""Screen time vs outside time for the field test.

The pitch of this project is that the screen is the shortest part of the
experience. This helper turns the two numbers into the ratio the post closes
with.

    python scripts/time_box.py --screen 4 --outside 46
    python scripts/time_box.py --screen 4 --outside 46 --md
"""
from __future__ import annotations

import argparse


def summarize(screen_min: float, outside_min: float) -> dict:
    if screen_min <= 0:
        raise ValueError("screen_min must be positive")
    return {
        "screen_min": round(screen_min, 1),
        "outside_min": round(outside_min, 1),
        "ratio": round(outside_min / screen_min, 1),
        "screen_pct": round(screen_min / (screen_min + outside_min) * 100, 1),
    }


def markdown_row(s: dict) -> str:
    return (
        f"| At the screen | {s['screen_min']:.1f} |\n"
        f"| Outside | {s['outside_min']:.1f} |\n"
        f"| Ratio (outside : screen) | {s['ratio']:.1f} : 1 |"
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Minutes at the screen vs minutes outside.")
    ap.add_argument("--screen", type=float, required=True, help="minutes at the screen")
    ap.add_argument("--outside", type=float, required=True, help="minutes outside")
    ap.add_argument("--md", action="store_true", help="print a markdown table instead")
    args = ap.parse_args(argv)

    s = summarize(args.screen, args.outside)
    if args.md:
        print(markdown_row(s))
    else:
        print(f"screen  : {s['screen_min']:.1f} min ({s['screen_pct']:.0f}% of the time)")
        print(f"outside : {s['outside_min']:.1f} min")
        print(f"ratio   : {s['ratio']:.1f} : 1 (outside : screen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
