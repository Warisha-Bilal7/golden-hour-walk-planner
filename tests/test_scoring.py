from __future__ import annotations

import math
import random

import networkx as nx
import pytest
from shapely.geometry import Polygon

from ghwalk.scoring import (
    PACE_KMH,
    annotate_green,
    build_candidate,
    edge_cost,
    generate_candidates,
    initial_params,
    loosen,
    route_metrics,
    score_loop,
    to_simple,
)


def _multidigraph():
    G = nx.MultiDiGraph()
    for i in range(5):
        G.add_node(i, x=i * 100.0, y=0.0, lat=24.8, lon=67.0 + i / 1000)
    G.add_edge(0, 1, length=100.0, highway="footway")
    G.add_edge(1, 2, length=100.0, highway="primary")
    G.add_edge(2, 3, length=100.0, highway="path")
    G.add_edge(3, 4, length=100.0, highway="residential")
    G.add_edge(2, 3, length=50.0, highway="path")
    return G


def _ring_graph(n=40, radius=900.0):
    cx, cy = 1000000.0, 2000000.0
    H = nx.Graph()
    H.add_node(0, x=cx, y=cy)
    for i in range(n):
        ang = 2 * math.pi * i / n
        H.add_node(i + 1, x=cx + radius * math.cos(ang), y=cy + radius * math.sin(ang))
    for i in range(1, n + 1):
        j = i + 1 if i < n else 1
        x1, y1 = H.nodes[i]["x"], H.nodes[i]["y"]
        x2, y2 = H.nodes[j]["x"], H.nodes[j]["y"]
        H.add_edge(i, j, length=math.hypot(x2 - x1, y2 - y1), green=0.0, highway="footway")
        H.add_edge(
            0, i,
            length=math.hypot(H.nodes[i]["x"] - cx, H.nodes[i]["y"] - cy),
            green=0.0, highway="path",
        )
    return H, 0


def _params():
    return {
        "target_m": 3500.0,
        "tolerance": 0.15,
        "max_overlap": 0.20,
        "w_green": 0.8,
        "n_candidates": 40,
        "radius_factor": 0.26,
    }


def test_annotate_green_marks_edges_near_park():
    G = _multidigraph()
    park = Polygon([(-20, -10), (120, -10), (120, 10), (-20, 10)])
    annotate_green(G, [park])
    assert G.edges[0, 1, 0]["green"] == pytest.approx(1.0)
    assert G.edges[1, 2, 0]["green"] < 1.0
    assert G.edges[3, 4, 0]["green"] == pytest.approx(0.0)


def test_to_simple_keeps_shortest_parallel_edge():
    H = to_simple(_multidigraph())
    assert H[2][3]["length"] == pytest.approx(50.0)
    assert H[0][1]["highway"] == "footway"
    assert H.nodes[0]["x"] == 0.0


def test_edge_cost_prefers_green_footway_over_primary():
    near = {"length": 100.0, "highway": "footway", "green": 1.0}
    road = {"length": 100.0, "highway": "primary", "green": 0.0}
    assert edge_cost(near, w_green=0.8) < edge_cost(road, w_green=0.8)


def test_edge_cost_reuse_penalty_and_floor():
    d = {"length": 100.0, "highway": "residential", "green": 0.0}
    assert edge_cost(d, 0.8, reused=True) > edge_cost(d, 0.8, reused=False)
    cheap = {"length": 100.0, "highway": "footway", "green": 1.0}
    assert edge_cost(cheap, 1.5) >= 100.0 * 0.3


def test_score_loop_rewards_length_and_green():
    p = _params()
    on_target = score_loop(3400, 0.8, 0.0, p)
    assert on_target < score_loop(2800, 0.8, 0.0, p)
    assert on_target < score_loop(4200, 0.8, 0.0, p)
    assert score_loop(3400, 0.9, 0.0, p) < score_loop(3400, 0.3, 0.0, p)
    assert score_loop(3400, 0.9, 0.0, p) < score_loop(3400, 0.9, 0.2, p)


def test_route_metrics_ring_has_no_overlap():
    H, start = _ring_graph(n=40)
    n = 40
    route = [start] + list(range(1, n + 1)) + [start]
    length, green, overlap = route_metrics(H, route)
    expected = sum(H[u][v]["length"] for u, v in zip(route, route[1:]))
    assert length == pytest.approx(expected)
    assert overlap == pytest.approx(0.0)
    assert green == pytest.approx(0.0)


def test_build_candidate_makes_loop():
    H, start = _ring_graph()
    p = _params()
    route = build_candidate(H, start, p, random.Random(7))
    assert route is not None
    assert route[0] == route[-1] == start
    assert len(route) > 2


def test_generate_candidates_returns_sorted_loops():
    H, start = _ring_graph()
    p = _params()
    cands = generate_candidates(H, start, p, seed=3, keep=3)
    assert len(cands) == 3
    scores = [c["score"] for c in cands]
    assert scores == sorted(scores)
    for c in cands:
        assert c["nodes"][0] == start == c["nodes"][-1]
        assert c["length_m"] > 0
        assert 0.0 <= c["green_pct"] <= 1.0
        assert 0.0 <= c["overlap_pct"] <= 1.0


def test_initial_params_and_loosen():
    p = initial_params(45, "normal")
    assert p["target_m"] == pytest.approx(45 / 60 * PACE_KMH["normal"] * 1000)
    best = {"length_m": p["target_m"] * 2.0}
    lp = loosen(p, best)
    assert lp["tolerance"] > p["tolerance"]
    assert lp["max_overlap"] > p["max_overlap"]
    assert lp["w_green"] < p["w_green"]
    assert lp["n_candidates"] > p["n_candidates"]