from __future__ import annotations

from ..scoring import loosen


def run(state):
    best, params = state["best"], state["params"]
    if best is None:
        return {
            "critic": {"passed": False, "reasons": ["no candidate loops"]},
            "params": loosen(params, None),
            "attempt": state["attempt"] + 1,
        }
    reasons = []
    err = abs(best["length_m"] - params["target_m"]) / params["target_m"]
    if err > params["tolerance"]:
        reasons.append(f"length off by {err:.0%}")
    if best["overlap_pct"] > params["max_overlap"]:
        reasons.append(f"overlap {best['overlap_pct']:.0%}")
    est_min = best["length_m"] / 1000 / state["speed_kmh"] * 60
    if est_min > state["intake"]["duration_min"] * 1.15:
        reasons.append(f"takes ~{est_min:.0f} min, over budget")
    if not reasons:
        return {"critic": {"passed": True, "reasons": []}}
    out = {
        "critic": {"passed": False, "reasons": reasons},
        "params": loosen(params, best),
        "attempt": state["attempt"] + 1,
    }
    if state["attempt"] + 1 >= 3:
        out["warnings"] = [f"shipped best-effort route: {', '.join(reasons)}"]
    return out
