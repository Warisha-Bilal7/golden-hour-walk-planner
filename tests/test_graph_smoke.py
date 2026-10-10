from __future__ import annotations

from ghwalk.graph import build_graph
from ghwalk.state import initial_state


def test_graph_runs_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = build_graph()
    result = app.invoke(initial_state("45 minutes, trees", 24.8607, 67.0011, "Asia/Karachi"))
    assert result["best"] is not None
    assert result["critic"]["passed"] is True
    assert result["attempt"] >= 1
    assert result["card_text"]
    assert (tmp_path / "output" / "card.html").exists()
    assert (tmp_path / "output" / "route.gpx").exists()
