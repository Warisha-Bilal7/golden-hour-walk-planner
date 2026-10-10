from __future__ import annotations

import re

PROMPT = """Write a short walk card (max 120 words) for someone about to step outside.
Use ONLY these facts. Do not invent places, landmarks, or plants.
Wrap every place name in [[double brackets]].

Start: {start} | Distance: {km:.1f} km (~{mins} min) | Sunset: {sunset}
Golden light comes from the {light_dir}. Weather: {weather}
Green spaces on the route: {places}

Write: one welcoming sentence, 2-3 direction cues using the place names, and one line on what to look for in the light."""


def _template_card(state) -> str:
    places = state.get("place_names", [])[:3]
    names = ", ".join(f"[[{p}]]" for p in places) or "the nearest green space"
    best = state.get("best") or {}
    km = best.get("length_m", 0.0) / 1000
    mins = state.get("intake", {}).get("duration_min", 0)
    sunset = state.get("sunset_iso", "")[:16].replace("T", " ")
    return (
        "Lace up and step outside while the light is still low. "
        f"Head out toward {names}, keep the loop gentle, and turn back in time to "
        f"catch the glow. "
        f"Distance {km:.1f} km (~{mins} min). Sunset around {sunset}. "
        "Watch the low light catch the leaves and the tops of the trees."
    )


def run(state):
    text = _template_card(state)
    warnings = ["card_writer: stub, used template fallback"]
    valid = set(state.get("place_names", []))
    for name in re.findall(r"\[\[(.+?)\]\]", text):
        if name not in valid:
            warnings.append(f"card_writer: unknown place name '{name}'")
    return {"card_text": text, "used_fallback": True, "warnings": warnings}
