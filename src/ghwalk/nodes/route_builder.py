from __future__ import annotations

from ..scoring import generate_candidates, to_simple
from .map_fetch import load_graph


def run(state):
    G = load_graph(state["graph_path"])
    H = to_simple(G)
    start = state["start_node"]
    params = state["params"]
    candidates = generate_candidates(H, start, params, seed=state.get("attempt", 0), keep=3)
    best = candidates[0] if candidates else None
    return {"candidates": candidates, "best": best}