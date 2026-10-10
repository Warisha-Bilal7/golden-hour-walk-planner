from pathlib import Path

import networkx as nx
from shapely.geometry import Polygon

from ghwalk.nodes import render as render_node
from ghwalk.nodes.map_fetch import save_green


def _fake_graph() -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    for i, (x, y, lat, lon) in enumerate([
        (0.0, 0.0, 24.860, 67.000),
        (500.0, 0.0, 24.866, 67.002),
        (500.0, 400.0, 24.866, 67.004),
        (0.0, 400.0, 24.860, 67.003),
    ]):
        G.add_node(i, x=x, y=y, lat=lat, lon=lon)
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 0)]:
        G.add_edge(u, v, length=500.0, green=0.5, highway="footway")
    return G


def _state(tmp_path) -> dict:
    cache = tmp_path / "data" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    gpath = cache / "stub.graphml"
    gpath.write_text("stub", encoding="utf-8")
    fpath = cache / "stub_green.geojson"
    save_green(fpath, [Polygon([(-50, -50), (550, -50), (550, 450), (-50, 450)])], ["Test Park"])
    return {
        "start_lat": 24.860, "start_lon": 67.000, "tz": "Asia/Karachi",
        "graph_path": str(gpath), "green_path": str(fpath),
        "start_node": 0, "intake": {"duration_min": 45},
        "sunset_iso": "2026-10-10T21:30:00+05:00",
        "walk_start_iso": "2026-10-10T20:35:00+05:00",
        "weather": {"temp_c": 29.0, "precip_prob": 20, "wind_kmh": 9.0, "source": "live"},
        "best": {"nodes": [0, 1, 2, 3, 0], "length_m": 2000.0,
                 "green_pct": 0.5, "overlap_pct": 0.0, "score": 1.0},
        "card_text": "Head for [[Test Park]] and keep the light low.",
        "used_fallback": True,
    }


def test_render_writes_card_map_gpx_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(render_node, "load_graph", lambda _p: _fake_graph())

    def _fake_pdf(html_path, pdf_path):
        Path(pdf_path).write_bytes(b"%PDF-fake")
        return True

    monkeypatch.setattr(render_node, "_write_pdf", _fake_pdf)
    out = render_node.run(_state(tmp_path))

    assert (tmp_path / "output" / "card.html").exists()
    html = (tmp_path / "output" / "card.html").read_text(encoding="utf-8")
    assert "Head for Test Park and keep the light low." in html
    assert "data:image/png;base64," in html

    assert (tmp_path / "output" / "route_map.png").exists()
    assert out["route_map_path"]

    gpx = (tmp_path / "output" / "route.gpx").read_text(encoding="utf-8")
    assert gpx.count("<trkpt") == 5
    assert 'lat="24.866"' in gpx and 'lon="67.002"' in gpx

    assert out["pdf_path"]
    assert (tmp_path / "output" / "card.pdf").exists()


def test_render_gpx_falls_back_to_start_point(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(render_node, "load_graph", lambda _p: None)
    monkeypatch.setattr(render_node, "_write_pdf", lambda h, p: False)
    state = _state(tmp_path)
    state["card_text"] = "simple"
    out = render_node.run(state)
    gpx = (tmp_path / "output" / "route.gpx").read_text(encoding="utf-8")
    assert gpx.count("<trkpt") == 1
    assert out["route_map_path"] == ""
    assert any("PDF export skipped" in w for w in out["warnings"])