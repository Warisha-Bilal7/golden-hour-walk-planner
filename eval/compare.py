"""Run the same request through each local model (plus the template baseline)
and write one row per model to eval/results.csv.

    python eval/compare.py
    python eval/compare.py --models "qwen2.5:3b,llama3.2:1b"
    python -m eval.compare

Models come from eval/models.yaml; models that are not pulled are skipped.
Everything is deterministic except the language at the two ends, so length /
green / overlap should be identical across models that parse the request the
same way - the interesting columns are hallucinations and card length.
"""
from __future__ import annotations

import argparse
import csv
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psutil  # noqa: E402
import yaml  # noqa: E402

from eval.hallucination import check_card  # noqa: E402
from ghwalk import llm  # noqa: E402
from ghwalk.graph import build_graph  # noqa: E402
from ghwalk.state import initial_state  # noqa: E402

FIELDS = [
    "timestamp", "model", "used_fallback", "attempts", "card_words",
    "bracketed_names", "hallucinations", "length_m", "target_m", "length_err_pct",
    "green_pct", "overlap_pct", "peak_ollama_mb", "peak_python_mb", "elapsed_s",
]


def _ollama_rss_mb() -> float:
    total = 0.0
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if "ollama" in name:
            try:
                total += proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    return total / (1024 * 1024)


def measure(model, request, lat, lon, tz, baseline=False, interval=0.25) -> dict:
    """Run the pipeline once and return one results row."""
    original = llm.is_available
    if baseline:
        llm.is_available = lambda: False
    peaks = {"ollama": 0.0, "self": 0.0}
    stop = threading.Event()
    me = psutil.Process()

    def sample():
        while not stop.is_set():
            peaks["ollama"] = max(peaks["ollama"], _ollama_rss_mb())
            peaks["self"] = max(peaks["self"], me.memory_info().rss / (1024 * 1024))
            time.sleep(interval)

    try:
        app = build_graph()
        state = initial_state(request, lat, lon, tz, model)
        thread = threading.Thread(target=sample, daemon=True)
        start = time.time()
        thread.start()
        result = app.invoke(state)
        elapsed = time.time() - start
        stop.set()
        thread.join(timeout=2)
    finally:
        llm.is_available = original

    best = result.get("best") or {}
    card = result.get("card_text", "")
    check = check_card(card, result.get("place_names", []))
    target = result.get("params", {}).get("target_m", 0.0)
    length = best.get("length_m", 0.0)
    err = abs(length - target) / target * 100 if target else 0.0
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": "template" if baseline else model,
        "used_fallback": True if baseline else bool(result.get("used_fallback")),
        "attempts": result.get("attempt"),
        "card_words": len(card.split()),
        "bracketed_names": len(check["bracketed"]),
        "hallucinations": check["hallucinations"],
        "length_m": round(length, 1),
        "target_m": round(target, 1),
        "length_err_pct": round(err, 1),
        "green_pct": round(best.get("green_pct", 0.0) * 100, 1),
        "overlap_pct": round(best.get("overlap_pct", 0.0) * 100, 1),
        "peak_ollama_mb": round(peaks["ollama"], 1),
        "peak_python_mb": round(peaks["self"], 1),
        "elapsed_s": round(elapsed, 1),
    }


def run(models, request, lat, lon, tz, interval=0.25) -> list[dict]:
    rows = [measure(m, request, lat, lon, tz, interval=interval) for m in models]
    rows.append(measure("template", request, lat, lon, tz, baseline=True, interval=interval))
    return rows


def write_csv(rows, path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def load_models(path) -> list[str]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return list(data.get("models", []))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compare local models; write eval/results.csv.")
    ap.add_argument("--models-file", default="eval/models.yaml")
    ap.add_argument("--csv", default="eval/results.csv")
    ap.add_argument("--request", default="45 minutes before dark, trees and quiet")
    ap.add_argument("--lat", type=float, default=24.8607)
    ap.add_argument("--lon", type=float, default=67.0011)
    ap.add_argument("--tz", default="Asia/Karachi")
    ap.add_argument("--interval", type=float, default=0.25)
    ap.add_argument("--models", help="comma-separated override of models.yaml")
    args = ap.parse_args(argv)

    models = ([m.strip() for m in args.models.split(",") if m.strip()]
              if args.models else load_models(args.models_file))
    available = set(llm.list_models()) if llm.is_available() else set()
    chosen = [m for m in models if not available or m in available]
    for m in models:
        if m not in chosen:
            print(f"skip {m}: not pulled")
    if not chosen:
        print("no models pulled; running the template baseline only")
    print(f"comparing: {', '.join(chosen) or '(none)'} + template baseline")

    rows = []
    for m in chosen:
        row = measure(m, args.request, args.lat, args.lon, args.tz, interval=args.interval)
        rows.append(row)
        print(f"  {m:16s} words={row['card_words']:3d} halluc={row['hallucinations']} "
              f"ram={row['peak_ollama_mb']}MB {row['elapsed_s']}s")
    rows.append(measure("template", args.request, args.lat, args.lon, args.tz,
                        baseline=True, interval=args.interval))
    write_csv(rows, args.csv)
    print(f"wrote {len(rows)} rows -> {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
