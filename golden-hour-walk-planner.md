# Golden Hour Walk Planner

> A small LangGraph pipeline that plans a 30-60 minute loop through green space so the walk ends in golden light. A local open-weight model handles the language at both ends; deterministic code (astral, OSMnx, networkx) handles the sun, the map, and the routing. The output is a printable one-page route card plus a GPX file. The screen is the shortest part of the experience.

---

## 1. Design principles

1. **The LLM never routes.** A 1B-3B model cannot plan a loop reliably. It parses the request and writes the card. Everything numeric is deterministic.
2. **Facts in, prose out.** The card writer sees only verified data (OSM place names, distance, sunset time, weather) and must wrap every place name in `[[double brackets]]` so names can be machine-checked against the map.
3. **Runs on small laptops.** 4-bit quantized models, `num_ctx=2048`, one model loaded at a time, a template fallback when no model is available.
4. **Open end to end.** Ollama or llama.cpp, an open-weight model, OSM data, astral, OSMnx, networkx, and a GPX file that opens in Organic Maps or OsmAnd.

## 2. Pipeline

```
intake (LLM) -> sun -> weather -> map_fetch -> route_builder -> critic --pass--> card_writer (LLM) -> render -> END
                                                    ^              |
                                                    +---- fail ----+   (loosen params, max 3 attempts)
                                                                   |
                                                                   +--- no route at all --> END
```

| Node | Uses model? | Job |
|---|---|---|
| intake | yes (structured output) | Free text to `{duration_min, preferences, pace}` |
| sun | no | Sunset, golden hour window, light direction, walk start time |
| weather | no | One Open-Meteo call, cached to disk; skipped if offline |
| map_fetch | no | Walk graph + green polygons within ~1.5 km, cached to disk |
| route_builder | no | Generate and score candidate loops |
| critic | no | Check length, overlap, timing; loosen params and retry |
| card_writer | yes | Short card from verified facts only |
| render | no | HTML card to PDF, plus GPX |

## 3. Repo layout

```
golden-hour-walk/
├── README.md
├── pyproject.toml
├── src/ghwalk/
│   ├── state.py            # WalkState + params (section 4)
│   ├── graph.py            # wiring + conditional edges (section 6)
│   ├── scoring.py          # edge cost + loop scoring (section 5)
│   ├── llm.py              # Ollama calls, template fallback
│   ├── nodes/
│   │   ├── intake.py
│   │   ├── sun.py
│   │   ├── weather.py
│   │   ├── map_fetch.py
│   │   ├── route_builder.py
│   │   ├── critic.py
│   │   ├── card_writer.py
│   │   └── render.py
│   └── templates/card.html.j2
├── data/cache/             # graphml, geojson, weather json (gitignored)
├── eval/
│   ├── hallucination.py    # checks [[names]] against OSM names
│   ├── models.yaml         # models to compare
│   └── results.csv
├── tests/
└── .github/ISSUE_TEMPLATE/
```

Dependencies: `langgraph ollama pydantic osmnx networkx shapely astral matplotlib jinja2 requests psutil` (optional: `weasyprint` for HTML to PDF; if it is painful to install, open the HTML in a browser and print to PDF).

---

## 4. LangGraph state definition

```python
# src/ghwalk/state.py
import operator
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, Field


# ---- Structured output from the intake LLM (also used as the JSON schema for Ollama) ----
class IntakeParams(BaseModel):
    duration_min: int = Field(default=45, ge=15, le=120)
    preferences: list[str] = Field(default_factory=list)   # e.g. ["trees", "quiet"]
    pace: Literal["slow", "normal", "brisk"] = "normal"


# ---- Routing parameters; the critic loosens these between attempts ----
class RouteParams(TypedDict):
    target_m: float        # desired loop length in metres
    tolerance: float       # allowed length error, 0.15 = +/-15%
    max_overlap: float     # max fraction of the loop that retraces itself
    w_green: float         # how strongly to prefer green edges (cost and score)
    n_candidates: int      # loops to generate per attempt
    radius_factor: float   # waypoint radius as a fraction of target_m (~0.26 to start)


class Candidate(TypedDict):
    nodes: list[int]       # OSM node ids, start to start
    length_m: float
    green_pct: float       # 0..1
    overlap_pct: float     # 0..1
    score: float           # lower is better


class CriticResult(TypedDict):
    passed: bool
    reasons: list[str]


# ---- The graph state ----
class WalkState(TypedDict, total=False):
    # inputs
    user_request: str
    start_lat: float
    start_lon: float
    tz: str                      # IANA name, e.g. "Asia/Karachi"
    model_name: str              # e.g. "qwen2.5:3b"

    # intake
    intake: dict                 # IntakeParams.model_dump()
    speed_kmh: float

    # sun
    sunset_iso: str
    golden_start_iso: str
    walk_start_iso: str
    walk_end_iso: str
    light_bearing_deg: float     # compass direction of the setting sun

    # weather
    weather: dict                # {"temp_c":..., "precip_prob":..., "wind_kmh":..., "source": "live|cache|none"}

    # map
    graph_path: str              # projected graphml on disk
    green_path: str              # green polygons (geojson) on disk
    place_names: list[str]       # OSM names allowed in the card
    start_node: int

    # routing
    params: RouteParams
    candidates: list[Candidate]
    best: Candidate | None
    attempt: int
    critic: CriticResult

    # outputs
    card_text: str
    used_fallback: bool          # True if the template was used instead of the LLM
    pdf_path: str
    gpx_path: str

    # appended to by any node (reducer = list concatenation)
    warnings: Annotated[list[str], operator.add]
```

Initial state when invoking the graph:

```python
initial = {
    "user_request": "45 minutes before dark, trees and quiet, not too steep",
    "start_lat": START_LAT,          # your start point
    "start_lon": START_LON,
    "tz": "Asia/Karachi",
    "model_name": "qwen2.5:3b",
    "attempt": 0,
    "warnings": [],
}
```

---

## 5. Edge-scoring and loop-building

Assumes the OSMnx graph has been **projected** (`ox.project_graph`) and the green polygons are in the same CRS, so x/y and buffers are in metres. `project_graph` keeps `lat`/`lon` node attributes, which the GPX export uses.

```python
# src/ghwalk/scoring.py
import math
import random
import networkx as nx
from shapely.geometry import LineString
from shapely.ops import unary_union
from shapely.prepared import prep

# Added to the cost multiplier. Negative = preferred, positive = avoided.
HIGHWAY_ADJ = {
    "footway": -0.25, "path": -0.25, "pedestrian": -0.20, "track": -0.10,
    "cycleway": -0.10, "living_street": 0.00, "residential": 0.10,
    "service": 0.30, "unclassified": 0.30, "tertiary": 0.50,
    "secondary": 1.00, "primary": 2.00, "trunk": 3.00,
}
DEFAULT_ADJ = 0.30
MIN_MULT = 0.30          # keeps every cost positive for Dijkstra
GREEN_BUFFER_M = 20      # an edge sample within 20 m of a park counts as "beside green"
REUSE_PENALTY = 3.0      # multiplier added to edges already used by this loop

W_LEN, W_OVERLAP = 3.0, 2.0     # score weights (green weight comes from params["w_green"])
PACE_KMH = {"slow": 3.5, "normal": 4.5, "brisk": 5.5}


def _highway(d: dict) -> str:
    hw = d.get("highway", "residential")
    return hw[0] if isinstance(hw, list) else hw


# ---------- one-time preprocessing (run after map download, then cache) ----------

def annotate_green(G, green_polys) -> None:
    """Add d['green'] in [0, 1] to every edge: the fraction of sample points near green space."""
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
    """Collapse the MultiDiGraph into an undirected simple graph (shorter parallel edge wins)."""
    H = nx.Graph()
    for u, v, d in G.edges(data=True):
        if H.has_edge(u, v) and H[u][v]["length"] <= d["length"]:
            continue
        H.add_edge(u, v, length=d["length"], green=d.get("green", 0.0), highway=_highway(d))
    for n, nd in G.nodes(data=True):
        H.add_node(n, x=nd["x"], y=nd["y"], lat=nd.get("lat"), lon=nd.get("lon"))
    return H


# ---------- the edge-scoring function ----------

def edge_cost(d: dict, w_green: float, reused: bool = False) -> float:
    """
    Cost of walking one edge. Lower = more attractive.
    cost = length * max(MIN_MULT, 1 + road_penalty - w_green * green + reuse_penalty)

    - footpaths/paths get a discount, main roads a surcharge
    - edges inside or beside green space get up to w_green off the multiplier
    - edges this loop has already used get a surcharge, which discourages out-and-back loops
    """
    mult = 1.0 + HIGHWAY_ADJ.get(d.get("highway", ""), DEFAULT_ADJ)
    mult -= w_green * d.get("green", 0.0)
    if reused:
        mult += REUSE_PENALTY
    return d["length"] * max(MIN_MULT, mult)


# ---------- loop generation ----------

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
        bearing = (math.degrees(math.atan2(dx, dy)) + 360) % 360   # compass bearing
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


# ---------- loop scoring ----------

def route_metrics(H, route) -> tuple[float, float, float]:
    """Returns (length_m, green_pct, overlap_pct)."""
    total = green_len = repeated = 0.0
    seen: set = set()
    for u, v in zip(route, route[1:]):
        d = H[u][v]
        total += d["length"]
        green_len += d["length"] * d["green"]
        e = frozenset((u, v))
        if e in seen:
            repeated += d["length"]
        seen.add(e)
    if total == 0:
        return 0.0, 0.0, 1.0
    return total, green_len / total, repeated / total


def score_loop(length_m, green_pct, overlap_pct, params) -> float:
    """Lower is better."""
    length_err = abs(length_m - params["target_m"]) / params["target_m"]
    return (W_LEN * length_err
            + params["w_green"] * (1.0 - green_pct)
            + W_OVERLAP * overlap_pct)


def generate_candidates(H, start, params, seed: int = 0, keep: int = 5) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for _ in range(params["n_candidates"]):
        route = build_candidate(H, start, params, rng)
        if not route:
            continue
        length, green, overlap = route_metrics(H, route)
        out.append({
            "nodes": route, "length_m": length, "green_pct": green,
            "overlap_pct": overlap, "score": score_loop(length, green, overlap, params),
        })
    out.sort(key=lambda c: c["score"])
    return out[:keep]


# ---------- parameter handling for the critic loop ----------

def initial_params(duration_min: int, pace: str) -> dict:
    target = duration_min / 60 * PACE_KMH[pace] * 1000
    return {
        "target_m": target, "tolerance": 0.15, "max_overlap": 0.20,
        "w_green": 0.8, "n_candidates": 30, "radius_factor": 0.26,
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
```

**Tuning notes**
- If loops come out too jagged, raise `MIN_MULT` or lower `w_green`.
- If routes hug a single park and ignore everything else, lower `W_LEN` slightly.
- Print the top 3 candidates on a matplotlib map during development. It is the fastest way to find bad weights.

---

## 6. Node and edge wiring

```python
# src/ghwalk/graph.py
from typing import Literal
from langgraph.graph import StateGraph, START, END
from .state import WalkState
from .nodes import intake, sun, weather, map_fetch, route_builder, critic, card_writer, render

MAX_ATTEMPTS = 3


def critic_router(state: WalkState) -> Literal["route_builder", "card_writer", "give_up"]:
    if state["critic"]["passed"]:
        return "card_writer"
    if state["attempt"] >= MAX_ATTEMPTS:
        # Ship the best loop we have, with a warning on the card, or stop if there is none.
        return "card_writer" if state.get("best") else "give_up"
    return "route_builder"


def build_graph():
    g = StateGraph(WalkState)
    g.add_node("intake", intake.run)
    g.add_node("sun", sun.run)
    g.add_node("weather", weather.run)
    g.add_node("map_fetch", map_fetch.run)
    g.add_node("route_builder", route_builder.run)
    g.add_node("critic", critic.run)
    g.add_node("card_writer", card_writer.run)
    g.add_node("render", render.run)

    g.add_edge(START, "intake")
    g.add_edge("intake", "sun")
    g.add_edge("sun", "weather")
    g.add_edge("weather", "map_fetch")
    g.add_edge("map_fetch", "route_builder")
    g.add_edge("route_builder", "critic")
    g.add_conditional_edges(
        "critic", critic_router,
        {"route_builder": "route_builder", "card_writer": "card_writer", "give_up": END},
    )
    g.add_edge("card_writer", "render")
    g.add_edge("render", END)
    return g.compile()
```

### Key node snippets

**sun.py** (astral, no network)

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from astral import Observer
from astral.sun import sun as astral_sun, golden_hour, SunDirection, azimuth

def run(state):
    tz = ZoneInfo(state.get("tz", "UTC"))
    obs = Observer(latitude=state["start_lat"], longitude=state["start_lon"])
    today = datetime.now(tz).date()
    s = astral_sun(obs, date=today, tzinfo=tz)
    g_start, _g_end = golden_hour(obs, today, direction=SunDirection.SETTING, tzinfo=tz)
    walk_end = s["sunset"] - timedelta(minutes=10)
    walk_start = walk_end - timedelta(minutes=state["intake"]["duration_min"])
    return {
        "sunset_iso": s["sunset"].isoformat(),
        "golden_start_iso": g_start.isoformat(),
        "walk_start_iso": walk_start.isoformat(),
        "walk_end_iso": walk_end.isoformat(),
        "light_bearing_deg": azimuth(obs, s["sunset"]),
    }
```

**intake.py** (structured output so even a 1B model returns valid JSON)

```python
import ollama
from ..state import IntakeParams
from ..scoring import PACE_KMH, initial_params

SYSTEM = ("Extract walk parameters from the request. Return JSON only. "
          "duration_min is minutes (15-120). pace is slow, normal, or brisk.")

def run(state):
    try:
        resp = ollama.chat(
            model=state["model_name"],
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": state["user_request"]}],
            format=IntakeParams.model_json_schema(),
            options={"num_ctx": 2048, "temperature": 0},
            keep_alive="10m",           # keep loaded for the card writer; it unloads at the end
        )
        intake = IntakeParams.model_validate_json(resp["message"]["content"])
    except Exception as e:
        intake = IntakeParams()         # defaults: 45 min, normal pace
        warn = [f"intake fallback to defaults: {e}"]
    else:
        warn = []
    d = intake.model_dump()
    return {"intake": d, "speed_kmh": PACE_KMH[d["pace"]],
            "params": initial_params(d["duration_min"], d["pace"]), "warnings": warn}
```

**map_fetch.py** (OSMnx, cached)

```python
import os
import osmnx as ox
from ..scoring import annotate_green

TAGS = {"leisure": ["park", "garden", "nature_reserve"],
        "natural": ["wood", "scrub", "grassland"],
        "landuse": ["grass", "forest", "recreation_ground"]}

def run(state):
    key = f"{state['start_lat']:.3f}_{state['start_lon']:.3f}"
    gpath, fpath = f"data/cache/{key}.graphml", f"data/cache/{key}_green.geojson"
    pt = (state["start_lat"], state["start_lon"])
    if not (os.path.exists(gpath) and os.path.exists(fpath)):
        G = ox.graph_from_point(pt, dist=1500, network_type="walk")
        G = ox.project_graph(G)
        feats = ox.features_from_point(pt, tags=TAGS, dist=1500).to_crs(G.graph["crs"])
        feats = feats[feats.geometry.type.isin(["Polygon", "MultiPolygon"])]
        annotate_green(G, feats.geometry)
        ox.save_graphml(G, gpath)
        feats[["name", "geometry"]].to_file(fpath, driver="GeoJSON")
    # reload, then to_simple(G) inside route_builder
    ...
```

**critic.py**

```python
from ..scoring import loosen

def run(state):
    best, p = state["best"], state["params"]
    if best is None:
        return {"critic": {"passed": False, "reasons": ["no candidate loops"]},
                "params": loosen(p, None), "attempt": state["attempt"] + 1}
    reasons = []
    err = abs(best["length_m"] - p["target_m"]) / p["target_m"]
    if err > p["tolerance"]:
        reasons.append(f"length off by {err:.0%}")
    if best["overlap_pct"] > p["max_overlap"]:
        reasons.append(f"overlap {best['overlap_pct']:.0%}")
    est_min = best["length_m"] / 1000 / state["speed_kmh"] * 60
    if est_min > state["intake"]["duration_min"] * 1.15:
        reasons.append(f"takes ~{est_min:.0f} min, over budget")
    if not reasons:
        return {"critic": {"passed": True, "reasons": []}}
    out = {"critic": {"passed": False, "reasons": reasons},
           "params": loosen(p, best), "attempt": state["attempt"] + 1}
    if state["attempt"] + 1 >= 3:
        out["warnings"] = [f"shipped best-effort route: {', '.join(reasons)}"]
    return out
```

**card_writer.py** (verified facts only, names bracketed so they can be checked)

```python
PROMPT = """Write a short walk card (max 120 words) for someone about to step outside.
Use ONLY these facts. Do not invent places, landmarks, or plants.
Wrap every place name in [[double brackets]].

Start: {start} | Distance: {km:.1f} km (~{mins} min) | Sunset: {sunset}
Golden light comes from the {light_dir}. Weather: {weather}
Green spaces on the route: {places}

Write: one welcoming sentence, 2-3 direction cues using the place names, and one line on what to look for in the light."""
```

- Run the model with `options={"num_ctx": 2048, "temperature": 0.4}` and **`keep_alive=0`** so it unloads right after.
- After generation, extract every `[[name]]`; any name not in `state["place_names"]` goes into `warnings` and is logged for the eval.
- **Template fallback:** if Ollama is unreachable or the model errors, fill a fixed Jinja template from the same facts and set `used_fallback=True`. The app always produces a card, and the template is the baseline for the model comparison.

**render.py**
- Draw park polygons and the route with matplotlib (no tile server), save PNG.
- Fill `card.html.j2` with the map, the card text with brackets stripped, the start time, sunset, and a "leave by" line.
- Export PDF (weasyprint, or print from the browser) and a GPX file (`<trk><trkseg><trkpt lat= lon=>` using node `lat`/`lon`).

---

## 7. Local model setup for small-RAM laptops

| Laptop RAM | Suggested model (4-bit) | Approx. memory | Notes |
|---|---|---|---|
| 4 GB | Llama 3.2 1B or Gemma 3 1B | ~1 GB | Close the browser; expect weaker intake parsing |
| 8 GB | Qwen2.5 3B or Llama 3.2 3B | ~2-2.5 GB | Best default |
| 16 GB | A 7B/8B model | ~5 GB | For the comparison section only |

Newer small models may beat these; the size tiers still apply.

```bash
# keep memory flat and predictable
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
ollama pull qwen2.5:3b
```

Rules of thumb:
- `num_ctx=2048`. The prompts are short.
- The two LLM nodes run sequentially. The model unloads after the card is written.
- CPU-only generation of a ~120-word card takes tens of seconds on a 3B model. That is fine, because this is a plan-then-leave tool.
- Everything else (OSMnx, networkx) uses well under 1 GB for a 1.5 km radius.
- Offline after the first map download. Weather is the only other network call, and the app works without it.

---

## 8. Evaluation plan (this becomes the technical half of the post)

Run the **same start point and request** through each model plus the template baseline.

| Metric | How |
|---|---|
| Hallucinated place names | `[[names]]` not in `place_names`, divided by total names |
| Intake parse success | JSON valid and `duration_min` within 5 of the request, over ~10 test phrasings |
| Card generation time | wall clock for the card_writer node |
| Peak RAM | `psutil` sampling of the Ollama process |
| Route quality | length error, green %, overlap % (identical across models, since the router has no LLM) |

Save results to `eval/results.csv` and put one small table in the post. Also spot-check a few cards by hand for unbracketed invented names, since the bracket check only catches bracketed ones.

---

## 9. GitHub project plan

Time estimates assume a focused weekend (~15 hours total). Add your own due dates to each milestone.

| Milestone | Goal | Est. | Done when |
|---|---|---|---|
| M0 Setup | Repo, env, empty graph runs end to end | 1 h | `python -m ghwalk` runs all nodes with stubs |
| M1 Routing core | Map cache + scoring + loop generator | 4 h | Top loop plotted on a map looks walkable |
| M2 Sun, weather, render | Sun times, weather cache, PDF + GPX | 2.5 h | A printable card with map and GPX opens in OsmAnd |
| M3 Local LLM nodes | Intake + card writer + template fallback | 2.5 h | Works on a 1B and a 3B model; fallback tested with Ollama off |
| M4 Critic + eval | Retry loop, hallucination check, comparison table | 2 h | `eval/results.csv` has one row per model |
| M5 Field test + write-up | Walk it, photograph the card, write the post | 3 h | Post drafted, repo README final, submitted |

**Cut line if you fall behind:** keep M0-M3 and M5. Reduce M4 to a plain retry (no loosening logic) and a single-model hallucination count.

### Issues by milestone

**M0 Setup**
- [ ] Create repo, `pyproject.toml`, `.gitignore` (ignore `data/cache/`), MIT license
- [ ] Define `WalkState`, `IntakeParams`, `RouteParams` in `state.py`
- [ ] Stub every node and wire the graph; add a CLI entry point
- [ ] Install Ollama, pull the 3B and 1B models, confirm `ollama.chat` works

**M1 Routing core**
- [ ] `map_fetch`: download walk graph and green polygons, project, cache to disk
- [ ] `annotate_green` and `to_simple`; unit-test on a tiny synthetic graph
- [ ] `edge_cost` with road and green adjustments; unit-test the ordering (footway beside park < primary road)
- [ ] `build_candidate`: waypoint picking and three-leg loop with reuse penalty
- [ ] `route_metrics` and `score_loop`
- [ ] Dev plot: top 3 candidates over the green polygons (matplotlib)
- [ ] Tune weights on 2-3 different start points

**M2 Sun, weather, render**
- [ ] `sun` node with astral; verify sunset against a trusted source
- [ ] `weather` node: Open-Meteo call, cache, graceful offline skip
- [ ] Matplotlib route map (parks + route + start marker)
- [ ] HTML card template (one page, big type, printable)
- [ ] PDF export
- [ ] GPX export; test in Organic Maps or OsmAnd

**M3 Local LLM nodes**
- [ ] `intake` with JSON-schema structured output and default fallback
- [ ] `card_writer` prompt with `[[name]]` convention
- [ ] Bracket extraction and validation against `place_names`
- [ ] Template fallback when Ollama is unavailable
- [ ] `keep_alive` handling: keep through intake, unload after card
- [ ] Test on a 1B model with RAM monitored

**M4 Critic and evaluation**
- [ ] `critic` node and `critic_router` with `MAX_ATTEMPTS`
- [ ] `loosen` parameter adaptation; test with an unreachable target length
- [ ] `eval/hallucination.py` and `eval/models.yaml`
- [ ] Run the comparison across models and the template baseline
- [ ] Add the results table to the README

**M5 Field test and write-up**
- [ ] Print the card, take it outside, walk it (note start time, weather, what went wrong)
- [ ] Take photos: the card in hand, the route, the light
- [ ] Record screen time vs outside time
- [ ] Draft the post (outline below)
- [ ] README: install, run, model table, offline notes
- [ ] Submit

### Create it all with the GitHub CLI

Run from inside the cloned repo (needs `gh auth login` first).

```bash
#!/usr/bin/env bash
set -e

# Labels
gh label create routing   --color 0E8A16 --force
gh label create llm       --color 5319E7 --force
gh label create render    --color FBCA04 --force
gh label create eval      --color D93F0B --force
gh label create writing   --color 1D76DB --force
gh label create setup     --color C5DEF5 --force

# Milestones (add due_on in ISO 8601 if you want deadlines: -f due_on="2026-10-12T23:59:00Z")
for m in "M0 Setup" "M1 Routing core" "M2 Sun, weather, render" \
         "M3 Local LLM nodes" "M4 Critic and eval" "M5 Field test and write-up"; do
  gh api "repos/{owner}/{repo}/milestones" -f title="$m" >/dev/null
done

mk() { gh issue create --title "$1" --milestone "$2" --label "$3" --body "$4"; }

# M0
mk "Create repo skeleton and pyproject"        "M0 Setup" setup   "Layout from the plan; ignore data/cache."
mk "Define WalkState and params"               "M0 Setup" setup   "state.py as in the plan."
mk "Stub all nodes and wire the graph"         "M0 Setup" setup   "Graph runs end to end with stubs."
mk "Install Ollama and pull 1B + 3B models"    "M0 Setup" llm     "Confirm ollama.chat with format=schema works."

# M1
mk "map_fetch with disk cache"                 "M1 Routing core" routing "OSMnx walk graph + green polygons, projected."
mk "annotate_green and to_simple"              "M1 Routing core" routing "Unit tests on a synthetic graph."
mk "edge_cost with road and green adjustments" "M1 Routing core" routing "Test ordering: footway by park < primary road."
mk "build_candidate loop generator"            "M1 Routing core" routing "Three legs, reuse penalty."
mk "route_metrics and score_loop"              "M1 Routing core" routing "Length error, green %, overlap %."
mk "Dev plot of top 3 candidates"              "M1 Routing core" routing "matplotlib over green polygons."
mk "Tune weights on 3 start points"            "M1 Routing core" routing "Record final constants in README."

# M2
mk "sun node (astral)"                         "M2 Sun, weather, render" render "Sunset, golden hour, light bearing."
mk "weather node with cache and offline skip"  "M2 Sun, weather, render" render "Open-Meteo, no key."
mk "Route map image"                           "M2 Sun, weather, render" render "Parks, route, start marker."
mk "HTML card template"                        "M2 Sun, weather, render" render "One page, printable."
mk "PDF export"                                "M2 Sun, weather, render" render "weasyprint or browser print."
mk "GPX export"                                "M2 Sun, weather, render" render "Opens in Organic Maps / OsmAnd."

# M3
mk "intake node with structured output"        "M3 Local LLM nodes" llm "JSON schema via Ollama format; defaults on failure."
mk "card_writer with [[name]] convention"      "M3 Local LLM nodes" llm "Facts-only prompt."
mk "Validate bracketed names against OSM"      "M3 Local LLM nodes" llm "Unknown names go to warnings."
mk "Template fallback"                         "M3 Local LLM nodes" llm "Works with Ollama off."
mk "keep_alive handling and RAM test on 1B"    "M3 Local LLM nodes" llm "Peak RAM recorded."

# M4
mk "critic node and router"                    "M4 Critic and eval" routing "MAX_ATTEMPTS = 3."
mk "loosen() parameter adaptation"             "M4 Critic and eval" routing "Test with an unreachable target."
mk "Hallucination check script"                "M4 Critic and eval" eval    "eval/hallucination.py"
mk "Run model comparison"                      "M4 Critic and eval" eval    "1B, 3B, 7B (if RAM), template baseline."
mk "Results table in README"                   "M4 Critic and eval" eval    "From eval/results.csv"

# M5
mk "Field test walk"                           "M5 Field test and write-up" writing "Print the card, walk it, take notes and photos."
mk "Measure screen vs outside time"            "M5 Field test and write-up" writing "Put the numbers in the post."
mk "Draft the post"                            "M5 Field test and write-up" writing "Use the outline in the plan."
mk "Final README"                              "M5 Field test and write-up" writing "Install, run, model table, offline notes."
mk "Submit"                                    "M5 Field test and write-up" writing "Check the judging criteria one last time."
```

Optional: create a GitHub Project (board view) and add all issues; group by milestone, with columns Todo / Doing / Done.

Suggested branch and commit style: one branch per milestone (`m1-routing`), small commits, and close issues with `Closes #n` in the PR.

---

## 10. Writing the post (weighted most heavily)

**Outline**
1. **Open outside.** The actual walk: the light, the printed card in your hand, one thing the route got right or wrong. No architecture yet.
2. **The problem in one paragraph.** Why you wanted a route card instead of a map app on a screen.
3. **Why open matters here.** Your location and routine never leave the laptop; it works offline after one map download; the model is swappable (show the 1B vs 3B vs 7B cards side by side); it costs nothing to run; the GPX opens in open-source map apps.
4. **How it works, briefly.** One diagram, plus "the LLM never routes, and here is why."
5. **What went wrong.** At least one honest failure: an invented place name, a dead-end alley, a loop that retraced itself. Show how the critic or the `[[name]]` check caught it (or did not).
6. **The numbers.** The model comparison table: hallucination rate, time, RAM.
7. **Close with the ratio.** Minutes at the screen vs minutes outside.

**Style reminders**
- Concrete over abstract: sunset time, distance, the name of the park.
- Keep the technical section short; the walk is the story.
- Include 2-3 photos: the card in hand, the route, the light.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| OSM green-space tagging is sparse near you | Test the start point early (M1); fall back to a parks-and-paths preference or pick a better-mapped start |
| Loops retrace or come out jagged | Reuse penalty, `MIN_MULT`, dev plots, tune on three start points |
| Small model ignores the facts-only rule | `[[name]]` validation plus the template fallback; report the rate honestly |
| weasyprint is hard to install | Print the HTML from a browser |
| Run out of time | Use the cut line in section 9 |
| Weather call fails | Cache plus skip; the card says "weather unavailable" |
