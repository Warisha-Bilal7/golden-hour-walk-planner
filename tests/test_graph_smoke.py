from __future__ import annotations

from ghwalk import llm
from ghwalk.graph import build_graph
from ghwalk.nodes import map_fetch, route_builder
from ghwalk.state import initial_state


def test_graph_runs_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm, "is_available", lambda: False)
    monkeypatch.setattr(
        map_fetch, "run",
        lambda state: {
            "graph_path": "data/cache/stub.graphml",
            "green_path": "data/cache/stub_green.geojson",
            "place_names": ["Stub Park"],
            "start_node": 0,
        },
    )

    def _stub_route(state):
        params = state["params"]
        candidate = {
            "nodes": [0, 1, 2, 3, 0],
            "length_m": params["target_m"],
            "green_pct": 0.75,
            "overlap_pct": 0.05,
            "score": 0.0,
        }
        return {"candidates": [candidate], "best": candidate}

    monkeypatch.setattr(route_builder, "run", _stub_route)

    app = build_graph()
    result = app.invoke(initial_state("45 minutes, trees", 24.8607, 67.0011, "Asia/Karachi"))
    assert result["best"] is not None
    assert result["critic"]["passed"] is True
    assert result["card_text"]
    assert (tmp_path / "output" / "card.html").exists()
    assert (tmp_path / "output" / "route.gpx").exists()