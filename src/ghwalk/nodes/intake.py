from __future__ import annotations

from ..scoring import PACE_KMH, initial_params
from ..state import IntakeParams

SYSTEM = (
    "Extract walk parameters from the request. Return JSON only. "
    "duration_min is minutes (15-120). pace is slow, normal, or brisk."
)


def run(state):
    warnings: list[str] = []
    intake = IntakeParams()
    try:
        from .. import llm
    except Exception as e:  # noqa: BLE001
        llm = None
        warnings.append(f"intake: llm module unavailable ({e})")

    if llm is not None and llm.is_available():
        try:
            content = llm.chat_structured(
                model=state["model_name"],
                system=SYSTEM,
                user=state["user_request"],
                schema=IntakeParams.model_json_schema(),
                temperature=0.0,
                keep_alive="10m",
            )
            intake = IntakeParams.model_validate_json(content)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"intake fallback to defaults: {e}")
    elif llm is not None:
        warnings.append("intake: Ollama unavailable, using defaults")

    d = intake.model_dump()
    return {
        "intake": d,
        "speed_kmh": PACE_KMH[d["pace"]],
        "params": initial_params(d["duration_min"], d["pace"]),
        "warnings": warnings,
    }
