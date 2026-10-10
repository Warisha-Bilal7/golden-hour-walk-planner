from ghwalk import llm
from ghwalk.nodes import card_writer

STATE = {
    "user_request": "45 minutes before dark, trees and quiet",
    "model_name": "qwen2.5:3b",
    "place_names": ["Allah Rakha Park", "Bagh-e-Lyari"],
    "intake": {"duration_min": 45},
    "best": {"length_m": 3400.0},
    "sunset_iso": "2026-10-10T18:09:51+05:00",
    "light_bearing_deg": 271.0,
    "weather": {"temp_c": 29.0, "precip_prob": 20, "wind_kmh": 9.0, "source": "live"},
}


def test_card_writer_falls_back_to_template(monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: False)
    out = card_writer.run(dict(STATE))
    assert out["used_fallback"] is True
    assert "[[Allah Rakha Park]]" in out["card_text"]
    assert any("template fallback" in w for w in out["warnings"])


def test_card_writer_uses_model_and_unloads(monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: True)
    calls = {}

    def _fake_chat(model, system, user, **kwargs):
        calls["model"] = model
        calls["keep_alive"] = kwargs.get("keep_alive")
        calls["user"] = user
        assert "Allah Rakha Park" in user and "3.4 km" in user
        assert "18:09" in user
        return "Lace up! Head for [[Allah Rakha Park]], turn at the fountain, and watch for the glow."

    monkeypatch.setattr(llm, "chat_text", _fake_chat)
    out = card_writer.run(dict(STATE))
    assert out["used_fallback"] is False
    assert out["card_text"].startswith("Lace up!")
    assert calls["keep_alive"] == 0
    assert calls["model"] == STATE["model_name"]


def test_card_writer_template_on_model_error(monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: True)

    def _boom(*a, **k):
        raise RuntimeError("ollama exploded")

    monkeypatch.setattr(llm, "chat_text", _boom)
    out = card_writer.run(dict(STATE))
    assert out["used_fallback"] is True