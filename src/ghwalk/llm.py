from __future__ import annotations

import importlib.util


def _ollama():
    if importlib.util.find_spec("ollama") is None:
        raise RuntimeError("the 'ollama' python package is not installed")
    import ollama

    return ollama


def is_available() -> bool:
    try:
        _ollama().list()
        return True
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        resp = _ollama().list()
    except Exception:
        return []
    models = getattr(resp, "models", None)
    if models is None and isinstance(resp, dict):
        models = resp.get("models", [])
    names = []
    for m in models or []:
        name = getattr(m, "model", None) or getattr(m, "name", None)
        if name is None and isinstance(m, dict):
            name = m.get("model") or m.get("name")
        if name:
            names.append(name)
    return names


def chat_structured(
    model: str,
    system: str,
    user: str,
    schema: dict,
    *,
    temperature: float = 0.0,
    num_ctx: int = 2048,
    keep_alive: str | int = "10m",
) -> str:
    ollama = _ollama()
    resp = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        format=schema,
        options={"num_ctx": num_ctx, "temperature": temperature},
        keep_alive=keep_alive,
    )
    return resp["message"]["content"]


def chat_text(
    model: str,
    system: str,
    user: str,
    *,
    temperature: float = 0.4,
    num_ctx: int = 2048,
    keep_alive: str | int = 0,
) -> str:
    ollama = _ollama()
    resp = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options={"num_ctx": num_ctx, "temperature": temperature},
        keep_alive=keep_alive,
    )
    return resp["message"]["content"]
