# ghwalk

A local LangGraph pipeline that plans a 30-60 minute walking loop through green
space so the walk ends in golden light. See `golden-hour-walk-planner.md` for
the full plan.

## Install

Requires Python 3.12+ (the heavy geospatial deps need recent wheels).

```bash
python -m venv .venv
pip install -e .
```

Run the planner:

```bash
python -m ghwalk --request "45 minutes before dark, trees and quiet" \
  --lat 24.86 --lon 67.01 --tz Asia/Karachi
```

The first run downloads the OSM walk graph and green polygons for the start
point and caches them in `data/cache/` (gitignored). Outputs land in
`output/`:

| File | What |
|---|---|
| `card.html` / `card.pdf` | one-page route card (print the PDF) |
| `route_map.png` | the route over the green polygons |
| `route.gpx` | track that opens in Organic Maps or OsmAnd |

Sun times come from `astral` (no network). Weather is one Open-Meteo call,
cached 30 min; offline it skips gracefully the card says "unavailable". Run the dev tools:

```bash
python scripts/dev_plot.py --lat 24.86 --lon 67.01   # top-3 loops over green space
python scripts/dev_tune.py --points "24.8607,67.0011;24.8700,67.0100;24.8550,66.9900"
```

## Routing constants (M1)

Final constants in `src/ghwalk/scoring.py`:

| Constant | Value | Meaning |
|---|---|---|
| `MIN_MULT` | 0.30 | floor on the cost multiplier (keeps costs positive for Dijkstra) |
| `GREEN_BUFFER_M` | 20 | edge sample counts as "beside green" within 20 m of a park |
| `REUSE_PENALTY` | 3.0 | multiplier added to edges a loop has already used |
| `W_LEN, W_OVERLAP` | 3.0, 2.0 | score weights for length error and overlap |
| `w_green` start | 1.2 | how strongly to prefer green edges (critic loosens toward 0.2) |
| `radius_factor` start | 0.26 | waypoint radius as a fraction of target length |
| `GREEN/DEFAULT adj` | -0.25 / +0.30 | footway/path discount; road surcharge |

`initial_params()` derives `target_m` from `pace` (3.5 / 4.5 / 5.5 km/h) and
`duration_min`. Tuning table lives in `output/tune_results.csv`.

## Local models (M3)

Two nodes use the local model; both degrade gracefully.

| Node | Call | Keep-alive | On failure |
|---|---|---|---|
| `intake` | `chat_structured` with `IntakeParams.model_json_schema()` | `"10m"` (stay warm for the card) | `IntakeParams()` defaults + warning |
| `card_writer` | `chat_text`, temperature 0.4, facts-only prompt | `0` (unload right after) | Jinja template `templates/card_text.j2` + `used_fallback=True` |

The model loads once (intake), stays resident for the route math, writes the
card, then unloads. `scripts/ram_test.py` runs the whole pipeline for one model
while sampling RSS and appends a row to `eval/results.csv`.

```bash
python scripts/ram_test.py --model llama3.2:1b
python scripts/ram_test.py --model qwen2.5:3b
```

Measured on this machine (CPU-only, Karachi start, warmed map cache):

| Model | Card words | Unknown-name warns | Peak model RAM | Wall time |
|---|---|---|---|---|
| `llama3.2:1b` | 78 | 1 | 403 MB | 68 s |
| `qwen2.5:3b` | 32 | 0 | 395 MB | 18 s |

Both finish under 0.5 GB of model memory, so a 4 GB laptop is enough. The 1B
model invented one place name (caught and warned, not shown as a real place);
the 3B stayed on the verified list.

## Tests

```bash
python -m pytest -q
```