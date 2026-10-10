from __future__ import annotations

import math
import random

import networkx as nx

PACE_KMH = {"slow": 3.5, "normal": 4.5, "brisk": 5.5}

HIGHWAY_ADJ = {
    "footway": -0.25, "path": -0.25, "pedestrian": -0.20, "track": -0.10,
    "cycleway": -0.10, "living_street": 0.00, "residential": 0.10,
    "service": 0.30, "unclassified": 0.30, "tertiary": 0.50,
    "secondary": 1.00, "primary": 2.00, "trunk": 3.00,
}
DEFAULT_ADJ = 0.30
MIN_MULT = 0.30
GREEN_BUFFER_M = 20
REUSE_PENALTY = 3.0

W_LEN, W_OVERLAP = 3.0, 2.0


def _highway(d: dict) -> str:
    hw = d.get("highway", "residential")
    return hw[0] if isinstance(hw, list) else hw


def annotate_green(G, green_polys) -> None:
    """Add d['green'] in [0, 1] to every edge: the fraction of samples near green space."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from shapely.prepared import prep

    green = prep(unary_union(list(green_polys)))
    for u, v, _k, d in G.edges(keys=True, data=True):
        geom = d.get("geometry") or LineString([
            (G.nodes[u]["x"], G.nodes[u]["y"]),
            (G.nodes[v]["x"], G.nodes[v]["y"]),
        ])
        pts = [geom.interpolate(f, normalized=True) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
        hits = sum(green.intersects(p.buffer(GREEN_BUFFER_M)) for p in pts)
        d["green"] = hits / len(pts)


def to_simple(G) -> nx.Graph:
    """Collapse a MultiDiGraph into an undirected simple graph (shorter parallel edge wins)."""
    H = nx.Graph()
    for u, v, d in G.edges(data=True):
        if H.has_edge(u, v) and H[u][v]["length"] <= d["length"]:
            continue
        H.add_edge(u, v, length=d["length"], green=d.get("green", 0.0), highway=_highway(d))
    for n, nd in G.nodes(data=True):
        H.add_node(n, x=nd["x"], y=nd["y"], lat=nd.get("lat"), lon=nd.get("lon"))
    return H


def edge_cost(d: dict, w_green: float, reused: bool = False) -> float:
    """Cost of walking one edge; lower = more attractive."""
    mult = 1.0 + HIGHWAY_ADJ.get(_highway(d), DEFAULT_ADJ)
    mult -= w_green * d.get("green", 0.0)
    if reused:
        mult += REUSE_PENALTY
    return d["length"] * max(MIN_MULT, mult)


def _leg(H, a, b, used: set, w_green: float) -> list[int]:
    def weight(u, v, d):
        return edge_cost(d, w_green, reused=frozenset((u, v)) in used)

    return nx.shortest_path(H, a, b, weight=weight)


def _pick_waypoint(H, start, bearing_deg, radius_m, rng, tol_deg=25):
    sx, sy = H.nodes[start]["x"], H.nodes[start]["y"]
    pool = []
    for n, nd in H.nodes(data=True):
        dx, dy = nd["x"] - sx, nd["y"] - sy
        r = math.hypot(dx, dy)
        if not (0.7 * radius_m <= r <= 1.3 * radius_m):
            continue
        bearing = (math.degrees(math.atan2(dx, dy)) + 360) % 360
        if abs((bearing - bearing_deg + 180) % 360 - 180) <= tol_deg:
            pool.append(n)
    return rng.choice(pool) if pool else None


def build_candidate(H, start, params, rng) -> list[int] | None:
    """start -> waypoint A -> waypoint B -> start, with waypoints ~120 degrees apart."""
    radius = params["target_m"] * params["radius_factor"]
    b0 = rng.uniform(0, 360)
    wa = _pick_waypoint(H, start, b0, radius, rng)
    wb = _pick_waypoint(H, start, b0 + rng.uniform(100, 140), radius, rng)
    if wa is None or wb is None:
        return None
    used: set = set()
    route = [start]
    try:
        for a, b in [(start, wa), (wa, wb), (wb, start)]:
            path = _leg(H, a, b, used, params["w_green"])
            used.update(frozenset(e) for e in zip(path, path[1:]))
            route += path[1:]
    except nx.NetworkXNoPath:
        return None
    return route


def route_metrics(H, route) -> tuple[float, float, float]:
    """Returns (length_m, green_pct, overlap_pct)."""
    total = green_len = repeated = 0.0
    seen: set = set()
    for u, v in zip(route, route[1:]):
        d = H[u][v]
        total += d["length"]
        green_len += d["length"] * d.get("green", 0.0)
        e = frozenset((u, v))
        if e in seen:
            repeated += d["length"]
        seen.add(e)
    if total == 0:
        return 0.0, 0.0, 1.0
    return total, green_len / total, repeated / total


def score_loop(length_m: float, green_pct: float, overlap_pct: float, params: dict) -> float:
    """Lower is better."""
    length_err = abs(length_m - params["target_m"]) / params["target_m"]
    return (
        W_LEN * length_err
        + params["w_green"] * (1.0 - green_pct)
        + W_OVERLAP * overlap_pct
    )


def generate_candidates(H, start, params, seed: int = 0, keep: int = 5) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for _ in range(params["n_candidates"]):
        route = build_candidate(H, start, params, rng)
        if not route:
            continue
        length, green, overlap = route_metrics(H, route)
        out.append({
            "nodes": route,
            "length_m": length,
            "green_pct": green,
            "overlap_pct": overlap,
            "score": score_loop(length, green, overlap, params),
        })
    out.sort(key=lambda c: c["score"])
    return out[:keep]


def plot_candidates(H, green_polys, start, candidates, out_png, title="candidate loops"):
    """Dev plot: green polygons + route graph + the candidate loops."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def _exteriors(geom):
        if geom is None:
            return []
        if geom.geom_type == "Polygon":
            return [geom.exterior]
        if geom.geom_type == "MultiPolygon":
            return [p.exterior for p in geom.geoms]
        return []

    fig, ax = plt.subplots(figsize=(10, 10))
    for poly in green_polys:
        for ext in _exteriors(poly):
            xs, ys = ext.xy
            ax.fill(xs, ys, color="green", alpha=0.15, linewidth=0)
    xs = [nd["x"] for n, nd in H.nodes(data=True)]
    ys = [nd["y"] for n, nd in H.nodes(data=True)]
    ax.plot(xs, ys, "k.", ms=1.5)
    colors = plt.cm.Set1(range(len(candidates)))
    for cand, c in zip(candidates, colors):
        px = [H.nodes[n]["x"] for n in cand["nodes"]]
        py = [H.nodes[n]["y"] for n in cand["nodes"]]
        ax.plot(px, py, color=c, lw=2.5,
                label=f"{cand['length_m']:.0f} m g{cand['green_pct']:.0%} o{cand['overlap_pct']:.0%}")
    ax.plot(H.nodes[start]["x"], H.nodes[start]["y"], "r*", ms=22)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=9)
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)


def initial_params(duration_min: int, pace: str) -> dict:
    target = duration_min / 60 * PACE_KMH[pace] * 1000
    return {
        "target_m": target,
        "tolerance": 0.15,
        "max_overlap": 0.20,
        "w_green": 1.2,
        "n_candidates": 30,
        "radius_factor": 0.26,
    }


def loosen(params: dict, best: dict | None) -> dict:
    """Adapt the waypoint radius toward the target length and relax the constraints."""
    p = dict(params)
    if best and best["length_m"] > 0:
        ratio = best["length_m"] / p["target_m"]
        p["radius_factor"] = min(0.45, max(0.12, p["radius_factor"] * (1 / ratio) ** 0.8))
    p["tolerance"] += 0.05
    p["max_overlap"] += 0.10
    p["w_green"] = max(0.2, p["w_green"] - 0.2)
    p["n_candidates"] = min(120, p["n_candidates"] * 2)
    return p