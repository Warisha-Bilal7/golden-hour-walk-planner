from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ghwalk.nodes import map_fetch
from ghwalk.scoring import generate_candidates, initial_params, to_simple


def _tune(point, w_greens, keep):
    lat, lon = point
    st = map_fetch.run({"start_lat": lat, "start_lon": lon})
    G = map_fetch.load_graph(st["graph_path"])
    H = to_simple(G)
    base = initial_params(45, "normal")
    base["n_candidates"] = 60
    rows = []
    for w in w_greens:
        params = dict(base)
        params["w_green"] = w
        cands = generate_candidates(H, st["start_node"], params, seed=0, keep=keep)
        if not cands:
            continue
        c = cands[0]
        rows.append({
            "lat": round(lat, 4), "lon": round(lon, 4), "w_green": w,
            "length_m": round(c["length_m"]),
            "len_err": round(abs(c["length_m"] - params["target_m"]) / params["target_m"], 3),
            "green_pct": round(c["green_pct"], 3),
            "overlap_pct": round(c["overlap_pct"], 3),
            "score": round(c["score"], 3),
        })
    return rows


def main():
    ap = argparse.ArgumentParser(
        description="Compare route quality across w_green values on several start points.")
    ap.add_argument("--points", required=True, help="start points as lat,lon;lat,lon")
    ap.add_argument("--w-greens", default="0.4,0.8,1.2")
    ap.add_argument("--keep", type=int, default=1)
    ap.add_argument("--csv", default="output/tune_results.csv")
    args = ap.parse_args()

    w_greens = [float(x) for x in args.w_greens.split(",")]
    points = [tuple(float(v) for v in p.split(",")) for p in args.points.split(";")]

    out_path = Path(args.csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["lat", "lon", "w_green", "length_m", "len_err", "green_pct", "overlap_pct", "score"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for point in points:
            print(f"== start {point[0]:.4f}, {point[1]:.4f} ==", flush=True)
            for attempt in range(3):
                try:
                    rows = _tune(point, w_greens, args.keep)
                    break
                except Exception as exc:  # network flakes: retry, then skip
                    print(f"  ! attempt {attempt + 1} failed: {exc}", flush=True)
                    rows = None
            if rows is None:
                continue
            for row in rows:
                print(f"  w_green={row['w_green']}  len {row['length_m']}m "
                      f"(err {row['len_err']})  green {row['green_pct']}  "
                      f"overlap {row['overlap_pct']}  score {row['score']}", flush=True)
                writer.writerow(row)
    print("table ->", out_path)


if __name__ == "__main__":
    main()