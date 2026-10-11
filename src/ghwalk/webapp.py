from __future__ import annotations

import re
from pathlib import Path

from .graph import build_graph
from .llm import list_models
from .state import initial_state

DEFAULT_LAT = 24.8607
DEFAULT_LON = 67.0011
DEFAULT_TZ = "Asia/Karachi"
DEFAULT_MODEL = "qwen2.5:3b"
OUT_DIR = Path("output")


def available_models() -> list[str]:
    models = list_models()
    if DEFAULT_MODEL not in models:
        models = [DEFAULT_MODEL, *models]
    return models


def _strip_markers(text: str) -> str:
    return re.sub(r"\[\[(.+?)\]\]", r"\1", text or "")


def _existing(path) -> str | None:
    if path and Path(path).exists():
        return str(path)
    return None


def run_walk(request, lat, lon, tz, model):
    request = (request or "").strip()
    if not request:
        return "Please enter a request.", "", None, None, None
    try:
        app = build_graph()
        state = initial_state(request, float(lat), float(lon), tz, model)
        result = app.invoke(state)
    except Exception as exc:
        return f"**Error:** `{exc}`", "", None, None, None

    best = result.get("best") or {}
    lines = [
        "### Golden hour walk",
        f"- **request:** {state['user_request']}",
        f"- **sunset:** {result.get('sunset_iso')}",
        f"- **walk window:** {result.get('walk_start_iso')} -> {result.get('walk_end_iso')}",
        f"- **distance:** {best.get('length_m', 0) / 1000:.2f} km",
        f"- **green / overlap:** {best.get('green_pct', 0):.0%} / {best.get('overlap_pct', 0):.0%}",
        f"- **attempts:** {result.get('attempt')}",
        f"- **fallback card:** {result.get('used_fallback')}",
    ]
    warnings = result.get("warnings", [])
    if warnings:
        lines += ["", "**Warnings**", *[f"- {w}" for w in warnings]]
    summary = "\n".join(lines)

    card = re.sub(r"\[\[(.+?)\]\]", r"\1", result.get("card_text", ""))
    return (
        summary,
        card,
        _existing(result.get("route_map_path")),
        _existing(result.get("pdf_path")),
        _existing(result.get("gpx_path")),
    )


def build_ui():
    import gradio as gr

    with gr.Blocks(title="Golden hour walk planner") as demo:
        gr.Markdown(
            "# Golden hour walk planner\n"
            "Plan a loop that ends in golden light, then take the printed card outside. "
            "The model reads your request and writes the card; all routing is deterministic."
        )
        with gr.Row():
            with gr.Column(scale=1):
                request = gr.Textbox(
                    value="45 minutes before dark, trees and quiet",
                    label="Request",
                    lines=2,
                )
                lat = gr.Number(value=DEFAULT_LAT, label="Latitude")
                lon = gr.Number(value=DEFAULT_LON, label="Longitude")
                tz = gr.Textbox(value=DEFAULT_TZ, label="Timezone")
                model = gr.Dropdown(
                    choices=available_models(),
                    value=DEFAULT_MODEL,
                    label="Model",
                    allow_custom_value=True,
                )
                btn = gr.Button("Plan walk", variant="primary")
            with gr.Column(scale=2):
                summary = gr.Markdown()
                card = gr.Markdown(label="Route card")
                map_img = gr.Image(label="Route map", type="filepath")
                with gr.Row():
                    pdf_out = gr.File(label="Route card (PDF)")
                    gpx_path = gr.File(label="Route (GPX)")

        btn.click(
            run_walk,
            inputs=[request, lat, lon, tz, model],
            outputs=[summary, card, map_img, pdf_out, gpx_path],
        )
    return demo


def main() -> int:
    build_ui().launch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
