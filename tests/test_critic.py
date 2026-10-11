from __future__ import annotations

from ghwalk.graph import MAX_ATTEMPTS, critic_router
from ghwalk.nodes import critic
from ghwalk.scoring import initial_params


def _state(length_m: float, overlap_pct: float = 0.0, attempt: int = 0, duration_min: int = 45):
    params = initial_params(duration_min, "normal")
    best = {
        "nodes": [0, 1, 0],
        "length_m": length_m,
        "green_pct": 0.6,
        "overlap_pct": overlap_pct,
        "score": 0.1,
    }
    return {
        "best": best,
        "params": params,
        "attempt": attempt,
        "speed_kmh": 4.5,
        "intake": {"duration_min": duration_min},
    }


def test_critic_passes_on_target_route():
    st = _state(length_m=initial_params(45, "normal")["target_m"])
    out = critic.run(st)
    assert out["critic"] == {"passed": True, "reasons": []}
    assert "params" not in out
    assert "attempt" not in out


def test_critic_flags_length_overlap_and_time():
    over = initial_params(45, "normal")["target_m"] * 2.0
    out = critic.run(_state(length_m=over, overlap_pct=0.5))
    reasons = out["critic"]["reasons"]
    assert out["critic"]["passed"] is False
    assert any("length off" in r for r in reasons)
    assert any("overlap" in r for r in reasons)
    assert any("over budget" in r for r in reasons)
    assert out["attempt"] == 1


def test_critic_loosens_params_on_failure():
    st = _state(length_m=initial_params(45, "normal")["target_m"] * 2.0)
    out = critic.run(st)
    assert out["params"]["tolerance"] > st["params"]["tolerance"]
    assert out["params"]["max_overlap"] > st["params"]["max_overlap"]
    assert out["params"]["w_green"] < st["params"]["w_green"]


def test_critic_no_candidates_fails_and_loosens():
    st = _state(length_m=0)
    st["best"] = None
    out = critic.run(st)
    assert out["critic"] == {"passed": False, "reasons": ["no candidate loops"]}
    assert out["attempt"] == 1
    assert out["params"]["tolerance"] > st["params"]["tolerance"]


def test_critic_warns_on_last_attempt():
    over = initial_params(45, "normal")["target_m"] * 2.0
    out = critic.run(_state(length_m=over, attempt=MAX_ATTEMPTS - 1))
    assert out["attempt"] == MAX_ATTEMPTS
    assert any("best-effort" in w for w in out["warnings"])


def _router_state(passed, attempt, best):
    return {"critic": {"passed": passed, "reasons": []}, "attempt": attempt, "best": best}


def test_critic_router_branches():
    best = {"length_m": 3000.0}
    assert critic_router(_router_state(True, 0, best)) == "card_writer"
    assert critic_router(_router_state(False, 1, best)) == "route_builder"
    assert critic_router(_router_state(False, MAX_ATTEMPTS, best)) == "card_writer"
    assert critic_router(_router_state(False, MAX_ATTEMPTS, None)) == "give_up"