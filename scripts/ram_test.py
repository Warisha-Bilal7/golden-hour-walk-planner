from __future__ import annotations

import argparse
import csv
import threading
import time
from datetime import datetime
from pathlib import Path

import psutil

from ghwalk.graph import build_graph
from ghwalk.state import initial_state


def _ollama_rss_mb() -> float:
    total = 0
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if "ollama" in name:
            try:
                total += proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    return total / (1024 * 1024)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the pipeline for one model and record peak RAM.")
    ap.add_argument("--model", default="llama3.2:1b")
    ap.add_argument("--request", default="45 minutes before dark, trees and quiet")
    ap.add_argument("--lat", type=float, default=24.8607)
    ap.add_argument("--lon", type=float, default=67.0011)
    ap.add_argument("--tz", default="Asia/Karachi")
    ap.add_argument("--csv", default="eval/ram_results.csv")
    ap.add_argument("--interval", type=float, default=0.25)
    args = ap.parse_args(argv)

    app = build_graph()
    state = initial_state(args.request, args.lat, args.lon, args.tz, args.model)

    peaks = {"ollama": 0.0, "self": 0.0}
    stop = threading.Event()
    me = psutil.Process()

    def sample():
        while not stop.is_set():
            peaks["ollama"] = max(peaks["ollama"], _ollama_rss_mb())
            peaks["self"] = max(peaks["self"], me.memory_info().rss / (1024 * 1024))
            time.sleep(args.interval)

    thread = threading.Thread(target=sample, daemon=True)
    start = time.time()
    thread.start()
    result = app.invoke(state)
    elapsed = time.time() - start
    stop.set()
    thread.join(timeout=2)

    card = result.get("card_text", "")
    unknown = sum(1 for w in result.get("warnings", []) if "unknown place names" in w)
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "used_fallback": result.get("used_fallback", False),
        "card_words": len(card.split()),
        "unknown_name_warnings": unknown,
        "peak_ollama_mb": round(peaks["ollama"], 1),
        "peak_python_mb": round(peaks["self"], 1),
        "elapsed_s": round(elapsed, 1),
    }

    print(f"model            : {row['model']}")
    print(f"used_fallback    : {row['used_fallback']}")
    print(f"card words       : {row['card_words']}")
    print(f"unknown-name warns: {row['unknown_name_warnings']}")
    print(f"peak ollama RAM  : {row['peak_ollama_mb']} MB")
    print(f"peak python RAM  : {row['peak_python_mb']} MB")
    print(f"elapsed          : {row['elapsed_s']} s")

    out = Path(args.csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    exists = out.exists()
    with open(out, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)
    print(f"row appended -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())