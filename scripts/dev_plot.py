from __future__ import annotations

import argparse
from pathlib import Path

from ghwalk.nodes import map_fetch
from ghwalk.scoring import (
    PACE_KMH,
    generate_candidates,
    initial_params,
    plot_candidates,
    to_simple,
)


def main():
    ap = argparse.ArgumentParser(description="Plot the top-N candidate loops over green space.")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--minutes", type=int, default=45)
    ap.add_argument("--pace", choices=list(PACE_KMH), default="normal")
    ap.add_argument("--num", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="output/dev_plot.png")
    args = ap.parse_args()

    st = map_fetch.run({"start_lat": args.lat, "start_lon": args.lon})
    G = map_fetch.load_graph(st["graph_path"])
    H = to_simple(G)
    green = map_fetch.load_green(st["green_path"])
    params = initial_params(args.minutes, args.pace)
    params["n_candidates"] = 40
    candidates = generate_candidates(H, st["start_node"], params, seed=args.seed, keep=args.num)

    print(f"start node {st['start_node']}; named green spots: "
          f"{', '.join(st['place_names'][:4]) or '(none)'}")
    for c in candidates:
        print(f"  {c['length_m']:.0f} m  green {c['green_pct']:.0%}  "
              f"overlap {c['overlap_pct']:.0%}  score {c['score']:.2f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    plot_candidates(H, green, st["start_node"], candidates, str(out),
                    title=f"top {len(candidates)} loops @ ({args.lat}, {args.lon})")
    print("plot ->", out)


if __name__ == "__main__":
    main()