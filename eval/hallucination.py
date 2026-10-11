"""Hallucination check for the walk card.

A card may only name green spaces that exist in the OSM data for the route.
The card writer wraps every place name in [[double brackets]]; any bracketed
name that is not in the verified list is a hallucination.

Usage:
    python eval/hallucination.py --places "Park A,Park B" --card "Walk to [[Park A]]"
    python eval/hallucination.py --places-file data/cache/24.860_67.001_green.geojson --card-file output/card.txt
    echo "..." | python eval/hallucination.py --places-file ...
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ghwalk.nodes.card_writer import extract_names, unknown_names


def check_card(card_text: str, place_names) -> dict:
    """Return the bracketed names and any that are not in the verified list."""
    bracketed = extract_names(card_text)
    unknown = unknown_names(card_text, place_names)
    return {
        "place_names": len(set(place_names or [])),
        "bracketed": bracketed,
        "unknown": unknown,
        "hallucinations": len(unknown),
        "ok": not unknown,
    }


def _load_places(args) -> list[str]:
    if args.places:
        return [p.strip() for p in args.places.split(",") if p.strip()]
    if args.places_file:
        data = json.loads(Path(args.places_file).read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            return sorted(
                {f["properties"].get("name") for f in data["features"]
                 if f.get("properties", {}).get("name")}
            )
        return list(data)
    return []


def _load_card(args) -> str:
    if args.card_file:
        return Path(args.card_file).read_text(encoding="utf-8")
    if args.card:
        return args.card
    return sys.stdin.read()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check a walk card for invented place names.")
    ap.add_argument("--card", help="card text")
    ap.add_argument("--card-file", help="path to a file containing the card text")
    ap.add_argument("--places", help="comma-separated verified place names")
    ap.add_argument("--places-file",
                    help="JSON list of names, or a green GeoJSON FeatureCollection")
    ap.add_argument("--json", action="store_true", help="print a JSON object")
    args = ap.parse_args(argv)

    res = check_card(_load_card(args), _load_places(args))
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"bracketed names : {', '.join(res['bracketed']) or '(none)'}")
        print(f"unknown names   : {', '.join(res['unknown']) or '(none)'}")
        print(f"hallucinations  : {res['hallucinations']}")
        print(f"ok              : {res['ok']}")
    return 0 if res["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
