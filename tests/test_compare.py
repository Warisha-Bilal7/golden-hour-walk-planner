from __future__ import annotations

from ghwalk import llm
from eval import compare

CANNED = {
    "best": {"length_m": 3400.0, "green_pct": 0.4, "overlap_pct": 0.1},
    "params": {"target_m": 3375.0},
    "attempt": 1,
    "card_text": "Go to [[Fake Park]] and [[Ghost Park]].",
    "place_names": ["Fake Park"],
    "used_fallback": False,
}


class _App:
    def __init__(self, result):
        self._result = result

    def invoke(self, state):
        return self._result


def test_measure_builds_row(monkeypatch):
    monkeypatch.setattr(compare, "build_graph", lambda: _App(CANNED))
    monkeypatch.setattr(compare, "_ollama_rss_mb", lambda: 123.4)
    row = compare.measure("qwen2.5:3b", "req", 24.86, 67.0, "Asia/Karachi", interval=0.01)
    assert row["model"] == "qwen2.5:3b"
    assert row["used_fallback"] is False
    assert row["card_words"] == 7
    assert row["bracketed_names"] == 2
    assert row["hallucinations"] == 1
    assert row["length_err_pct"] == round(abs(3400 - 3375) / 3375 * 100, 1)
    assert row["peak_ollama_mb"] == 123.4


def test_measure_baseline_forces_fallback_and_restores(monkeypatch):
    monkeypatch.setattr(compare, "build_graph", lambda: _App(CANNED))
    monkeypatch.setattr(compare, "_ollama_rss_mb", lambda: 0.0)
    before = llm.is_available
    row = compare.measure("x", "req", 24.86, 67.0, "Asia/Karachi", baseline=True, interval=0.01)
    assert row["model"] == "template"
    assert row["used_fallback"] is True
    assert llm.is_available is before


def test_run_appends_template_baseline(monkeypatch):
    monkeypatch.setattr(compare, "measure", lambda *a, **k: {f: 0 for f in compare.FIELDS})
    rows = compare.run(["m1", "m2"], "req", 0.0, 0.0, "UTC", interval=0.01)
    assert len(rows) == 3


def test_load_models(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text("models:\n  - a\n  - b\nbaseline: template\n", encoding="utf-8")
    assert compare.load_models(p) == ["a", "b"]


def test_write_csv_header_and_rows(tmp_path):
    p = tmp_path / "out.csv"
    compare.write_csv([{f: 0 for f in compare.FIELDS}], p)
    text = p.read_text(encoding="utf-8").splitlines()
    assert text[0] == ",".join(compare.FIELDS)
    assert len(text) == 2