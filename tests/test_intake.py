from ghwalk import llm
from ghwalk.nodes import intake
from ghwalk.scoring import PACE_KMH
from ghwalk.state import IntakeParams

STATE = {"user_request": "45 minutes before dark, trees and quiet",
         "model_name": "qwen2.5:3b"}


def test_intake_defaults_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: False)
    out = intake.run(dict(STATE))
    assert out["intake"] == IntakeParams().model_dump()
    assert out["speed_kmh"] == PACE_KMH["normal"]
    assert out["params"]["target_m"] == 45 / 60 * PACE_KMH["normal"] * 1000
    assert any("unavailable" in w for w in out["warnings"])


def test_intake_parses_structured_output(monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: True)

    def _fake_chat(model, system, user, schema, **kwargs):
        assert "duration_min" in system and "pace" in system and "brisk" in system
        assert schema == IntakeParams.model_json_schema()
        assert kwargs.get("keep_alive") == "10m"
        return '{"duration_min": 30, "preferences": ["trees", "quiet"], "pace": "brisk"}'

    monkeypatch.setattr(llm, "chat_structured", _fake_chat)
    out = intake.run(dict(STATE))
    assert out["intake"]["duration_min"] == 30
    assert out["intake"]["pace"] == "brisk"
    assert out["speed_kmh"] == PACE_KMH["brisk"]
    assert out["params"]["target_m"] == 30 / 60 * PACE_KMH["brisk"] * 1000
    assert out["warnings"] == []


def test_intake_defaults_on_garbage_json(monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(llm, "chat_structured",
                        lambda *a, **k: "not json at all")
    out = intake.run(dict(STATE))
    assert out["intake"] == IntakeParams().model_dump()
    assert any("intake fallback" in w for w in out["warnings"])