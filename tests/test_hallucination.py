from __future__ import annotations

import json

from eval.hallucination import check_card, main


def test_check_card_flags_unknown_name():
    res = check_card("Head to [[Allah Rakha Park]], then [[Enchanted Forest]].", ["Allah Rakha Park"])
    assert res["unknown"] == ["Enchanted Forest"]
    assert res["hallucinations"] == 1
    assert res["ok"] is False


def test_check_card_clean():
    res = check_card("Only [[Bagh-e-Lyari]] today.", ["Bagh-e-Lyari"])
    assert res["unknown"] == []
    assert res["ok"] is True


def test_cli_returns_nonzero_on_hallucination(capsys):
    code = main(["--places", "Park A,Park B", "--card", "Walk to [[Park A]] and [[Ghost Park]]"])
    out = capsys.readouterr().out
    assert code == 2
    assert "Ghost Park" in out
    assert "hallucinations  : 1" in out


def test_cli_ok(capsys):
    code = main(["--places", "Park A,Park B", "--card", "Walk to [[Park A]]"])
    assert code == 0


def test_cli_reads_places_from_geojson(tmp_path, capsys):
    gj = tmp_path / "green.geojson"
    gj.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [
            {"properties": {"name": "Park A"}},
            {"properties": {"name": "Park B"}},
        ],
    }), encoding="utf-8")
    code = main(["--places-file", str(gj), "--card", "Go to [[Park A]].", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["place_names"] == 2
    assert out["ok"] is True