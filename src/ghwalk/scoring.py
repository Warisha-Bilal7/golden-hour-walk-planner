PACE_KMH = {"slow": 3.5, "normal": 4.5, "brisk": 5.5}

W_LEN, W_OVERLAP = 3.0, 2.0


def initial_params(duration_min: int, pace: str) -> dict:
    target = duration_min / 60 * PACE_KMH[pace] * 1000
    return {
        "target_m": target,
        "tolerance": 0.15,
        "max_overlap": 0.20,
        "w_green": 0.8,
        "n_candidates": 30,
        "radius_factor": 0.26,
    }


def loosen(params: dict, best: dict | None) -> dict:
    p = dict(params)
    if best and best["length_m"] > 0:
        ratio = best["length_m"] / p["target_m"]
        p["radius_factor"] = min(0.45, max(0.12, p["radius_factor"] * (1 / ratio) ** 0.8))
    p["tolerance"] += 0.05
    p["max_overlap"] += 0.10
    p["w_green"] = max(0.2, p["w_green"] - 0.2)
    p["n_candidates"] = min(120, p["n_candidates"] * 2)
    return p


def score_loop(length_m: float, green_pct: float, overlap_pct: float, params: dict) -> float:
    length_err = abs(length_m - params["target_m"]) / params["target_m"]
    return (
        W_LEN * length_err
        + params["w_green"] * (1.0 - green_pct)
        + W_OVERLAP * overlap_pct
    )
