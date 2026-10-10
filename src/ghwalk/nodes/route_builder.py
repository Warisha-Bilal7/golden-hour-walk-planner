from __future__ import annotations

from ..scoring import score_loop


def run(state):
    params = state["params"]
    attempt = state.get("attempt", 0)
    target = params["target_m"]
    if attempt == 0:
        length, green, overlap = target * 1.4, 0.50, 0.30
    else:
        length, green, overlap = target, 0.75, 0.05
    candidate = {
        "nodes": [0, 1, 2, 3, 0],
        "length_m": round(length, 1),
        "green_pct": green,
        "overlap_pct": overlap,
        "score": score_loop(length, green, overlap, params),
    }
    return {
        "candidates": [candidate],
        "best": candidate,
        "warnings": ["route_builder: stub candidate"],
    }
