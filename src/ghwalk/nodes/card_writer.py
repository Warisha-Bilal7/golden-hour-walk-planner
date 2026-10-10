from __future__ import annotations

from .. import llm

SYSTEM = ("You write short, friendly walking cards from verified facts only. "
          "Do not invent places, landmarks, or plants. Under 120 words.")

PROMPT = """Write a short walk card (max 120 words) for someone about to step outside.
Use ONLY these facts. Do not invent places, landmarks, or plants.
Wrap every place name in [[double brackets]].

Start: {start} | Distance: {km:.1f} km (~{mins} min) | Sunset: {sunset}
Golden light comes from the {light_dir}. Weather: {weather}
Green spaces on the route: {places}

Write: one welcoming sentence, 2-3 direction cues using the place names, and one line on what to look for in the light."""


def _facts(state) -> dict:
    best = state.get("best") or {}
    weather = state.get("weather", {})
    if weather.get("temp_c") is not None:
        weather_str = (f"{weather['temp_c']} C, {weather.get('precip_prob', '?')}% rain, "
                       f"{weather.get('wind_kmh', '?')} km/h wind")
    else:
        weather_str = "weather unavailable"
    return {
        "start": state.get("user_request", ""),
        "km": best.get("length_m", 0.0) / 1000,
        "mins": state.get("intake", {}).get("duration_min", 0),
        "sunset": state.get("sunset_iso", "")[:16].replace("T", " "),
        "light_dir": state.get("light_bearing_deg", "west"),
        "weather": weather_str,
        "places": ", ".join(state.get("place_names", [])) or "the nearest green space",
    }


def _llm_card(state) -> str | None:
    """Returns model text, or None when Ollama is unreachable or the call fails."""
    if not llm.is_available():
        return None
    try:
        return llm.chat_text(
            model=state["model_name"],
            system=SYSTEM,
            user=PROMPT.format(**_facts(state)),
            temperature=0.4,
            keep_alive=0,
        )
    except Exception:
        return None


def _template_card(state) -> str:
    facts = _facts(state)
    names = ", ".join(f"[[{p}]]" for p in state.get("place_names", [])[:3]) or "the nearest green space"
    return (
        "Lace up and step outside while the light is still low. "
        f"Head out toward {names}, keep the loop gentle, and turn back in time to "
        f"catch the glow. "
        f"Distance {facts['km']:.1f} km (~{facts['mins']} min). "
        f"Sunset around {facts['sunset']}. "
        "Watch the low light catch the leaves and the tops of the trees."
    )


def run(state):
    warnings: list[str] = []
    text = _llm_card(state)
    if text is None:
        text = _template_card(state)
        used_fallback = True
        warnings.append("card_writer: Ollama unavailable, used template fallback")
    else:
        used_fallback = False
    return {"card_text": text, "used_fallback": used_fallback, "warnings": warnings}