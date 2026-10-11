from __future__ import annotations

import pytest

from scripts import time_box


def test_summarize_ratio_and_share():
    s = time_box.summarize(4, 46)
    assert s["ratio"] == pytest.approx(11.5)
    assert s["screen_pct"] == pytest.approx(8.0, abs=0.1)


def test_summarize_rejects_zero_screen():
    with pytest.raises(ValueError):
        time_box.summarize(0, 46)


def test_markdown_row_contains_numbers():
    row = time_box.markdown_row(time_box.summarize(3, 45))
    assert "At the screen" in row
    assert "45.0" in row
    assert "15.0 : 1" in row


def test_cli_prints_ratio(capsys):
    code = time_box.main(["--screen", "4", "--outside", "46"])
    out = capsys.readouterr().out
    assert code == 0
    assert "11.5 : 1" in out
