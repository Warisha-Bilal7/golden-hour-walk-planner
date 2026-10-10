from __future__ import annotations

import math

import networkx as nx
import osmnx as ox
from pyproj import Transformer
from shapely.geometry import Polygon

from ghwalk import llm
from ghwalk.graph import build_graph
from ghwalk.nodes.map_fetch import save_green
from ghwalk.scoring import annotate_green
from ghwalk.state import initial_state

LAT, LON = 24.860, 67.001
CRS = "EPSG:32642"
N_RING = 40
RING_RADIUS = 900.0


def _make_cached_map(cache_dir) -> str:
    trans = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    cx, cy = trans.transform(LON, LAT)
    G = nx.MultiDiGraph()
    G.graph["crs"] = CRS
    G.add_node(0, x=cx, y=cy, lat=LAT, lon=LON)
    for i in range(N_RING):
        ang = 2 * math.pi * i / N_RING
        G.add_node(i + 1, x=cx + RING_RADIUS * math.cos(ang),
                   y=cy + RING_RADIUS * math.sin(ang), lat=LAT, lon=LON)
    for i in range(1, N_RING + 1):
        j = i + 1 if i < N_RING else 1
        x1, y1 = G.nodes[i]["x"], G.nodes[i]["y"]
        x2, y2 = G.nodes[j]["x"], G.nodes[j]["y"]
        G.add_edge(i, j, length=math.hypot(x2 - x1, y2 - y1), highway="footway")
        G.add_edge(0, i, length=math.hypot(G.nodes[i]["x"] - cx, G.nodes[i]["y"] - cy),
                   highway="path")
    park = Polygon([(cx - 250, cy - 250), (cx + 250, cy - 250),
                    (cx + 250, cy + 250), (cx - 250, cy + 250)])
    annotate_green(G, [park])
    key = f"{LAT:.3f}_{LON:.3f}"
    gpath = cache_dir / f"{key}.graphml"
    fpath = cache_dir / f"{key}_green.geojson"
    ox.save_graphml(G, gpath)
    save_green(fpath, [park], ["Test Park"])
    return key


def test_pipeline_runs_against_cached_map(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm, "is_available", lambda: False)
    _make_cached_map(tmp_path / "data" / "cache")

    app = build_graph()
    result = app.invoke(initial_state("45 minutes, quiet", LAT, LON, "Asia/Karachi"))
    assert result["best"] is not None
    assert result["candidates"]
    assert result["attempt"] <= 3
    err = abs(result["best"]["length_m"] - result["params"]["target_m"]) / result["params"]["target_m"]
    assert err <= result["params"]["tolerance"] + 0.30
    assert result["best"]["overlap_pct"] <= result["params"]["max_overlap"] + 0.15
    assert result["card_text"]
    assert result["start_node"] == 0