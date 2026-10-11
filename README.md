# ghwalk

A local LangGraph pipeline that plans a 30-60 minute walking loop through green
space so the walk ends in golden light. You spend a few minutes at the keyboard,
then take one printed page (and a GPX) outside. The model only reads your request
and writes the card; every distance, sun time, and route is computed by
deterministic code. See `golden-hour-walk-planner.md` for the full plan.

## How it works

```
intake -> sun -> weather -> map_fetch -> route_builder -> critic -> card_writer -> render
 (LLM)   (astral) (Open-Meteo) (osmnx)   (networkx/Dijkstra)  |  (LLM)
                                                             +-> route_builder (retry, loosened)
```

- **The model never routes.** `intake` parses your request into structured
  parameters; `card_writer` writes the card from verified facts. If the model is
  unavailable or returns junk, defaults and a Jinja template keep the app working.
- **The `critic` checks the loop** for length, green coverage, and overlap, and
  can send it back to `route_builder` up to `MAX_ATTEMPTS` (3), loosening the
  target each time.

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
cached 30 min; offline it skips gracefully and the card says "unavailable". Run the dev tools:

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
while sampling RSS and appends a row to `eval/ram_results.csv`.

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

## Model comparison (M4)

`eval/compare.py` runs the **same request** through each pulled model plus the
Jinja template baseline and writes `eval/results.csv` (one row per model). The
router is deterministic, so length/green/overlap only differ when a model parses
the request differently (`pace`); the interesting columns are the hallucination
count and the card length.

```bash
python eval/compare.py                 # models from eval/models.yaml
python eval/compare.py --models "qwen2.5:3b,llama3.2:1b"
python eval/hallucination.py --places-file data/cache/24.860_67.001_green.geojson --card-file card.txt
```

Run 2026-10-11, Karachi, "45 minutes before dark, trees and quiet", CPU-only:

| Model | Pace read | Words | Bracketed | Hallucinations | Length err | Green | Peak RAM | Time |
|---|---|---|---|---|---|---|---|---|
| `qwen2.5:3b` | normal | 36 | 0 | 0 | 0.3% | 6.7% | 259 MB | 106 s |
| `qwen2.5:1.5b` | brisk | 69 | 0 | 0 | 4.4% | 5.5% | 260 MB | 16 s |
| `llama3.2:1b` | slow | 56 | 0 | 0 | 9.5% | 18.2% | 274 MB | 76 s |
| template (baseline) | normal | 55 | 3 | 0 | 0.3% | 6.7% | 273 MB | 65 s |

Takeaways: all three models stayed on the verified place list in this run (the
1B did hallucinate on an earlier run - see the M3 table - so the check matters).
The 3B read the pace as `normal` and produced the shortest, most on-target card;
the 1.5B misread the pace as `brisk` and the 1B as `slow`, which move the target
length and the length error. RAM is flat (~260 MB) across sizes because 1B-3B
are all small 4-bit quants. Full columns: `eval/results.csv`.

## Field test (M5)

The point of the app is the walk, not the app. `docs/field_test.md` is the log I
filled in after taking one printed card out: sun/weather as reported vs. what it
felt like, screen time vs. time outside, and where the card was right or wrong.
Photos go in `docs/photos/`.

## Screen vs. outside (M5)

`scripts/time_box.py` turns a few timestamps into the only metric that matters:

```bash
python scripts/time_box.py --screen 17:10,17:14,18:38 --outside 17:14,18:20,18:38
```

It prints minutes at the screen, minutes outside, and the ratio (and can emit a
Markdown row for the field-test log). `docs/measurement.md` defines what counts as
each. Full write-up: `docs/post.md`.

## Project layout

```
src/ghwalk/     pipeline nodes (intake, sun, weather, map_fetch, route_builder,
                critic, card_writer, render), state, scoring, llm client
templates/      Jinja card fallback (card_text.j2)
scripts/        ram_test.py, dev_plot.py, dev_tune.py, time_box.py
eval/           compare.py, hallucination.py, models.yaml, results.csv, ram_results.csv
tests/          pytest suite
docs/           field_test.md, measurement.md, post.md, submission.md, photos/
output/         generated card/map/gpx (gitignored)
```

## Tests

```bash
python -m pytest -q      # 46 tests
```

## License

MIT — see `LICENSE`.