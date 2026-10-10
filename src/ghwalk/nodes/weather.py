from __future__ import annotations


def run(state):
    return {
        "weather": {
            "temp_c": None,
            "precip_prob": None,
            "wind_kmh": None,
            "source": "none",
        },
        "warnings": ["weather: stub, no network call"],
    }
