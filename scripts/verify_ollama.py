from __future__ import annotations

import sys

from ghwalk import llm
from ghwalk.state import IntakeParams


def main() -> int:
    if not llm.is_available():
        print("Ollama server not reachable.")
        print("Install from https://ollama.com, then run `ollama serve`.")
        return 1

    models = llm.list_models()
    print("pulled models:", models or "(none)")
    has_small = any("1b" in m.lower() or "1.5b" in m.lower() for m in models)
    has_mid = any("3b" in m.lower() for m in models)
    print(f"1B-class model present: {has_small} | 3B-class model present: {has_mid}")

    target = next((m for m in models if "3b" in m.lower()), models[0] if models else None)
    if not target:
        print("No model to test. Run: ollama pull qwen2.5:3b  and  ollama pull qwen2.5:1.5b")
        return 1

    print(f"testing structured output against {target!r} ...")
    raw = llm.chat_structured(
        model=target,
        system="Extract walk parameters. Return JSON only.",
        user="45 minutes before dark, trees and quiet",
        schema=IntakeParams.model_json_schema(),
        temperature=0.0,
        keep_alive=0,
    )
    print("raw:", raw)
    print("parsed:", IntakeParams.model_validate_json(raw).model_dump())
    return 0


if __name__ == "__main__":
    sys.exit(main())
