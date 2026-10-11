# A golden hour walk planner that runs on a 1B model

*Draft. Fill the `[FIELD TEST]` bits after the walk, add 2–3 photos, then publish.
Suggested tags: `python`, `showdev`, `ai`, `gis` (confirm they exist on DEV).*

---

## Open outside

[FIELD TEST — the actual walk, in your own words, first, before any code.]

> Describe the light, the printed card in your hand, and one thing the route got
> right or wrong. Example shape: *"Sunset was at 18:09. I left the house at
> 17:14 with one sheet of paper. The card sent me left toward the park instead of
> right along the main road, and the low sun came through the trees exactly where
> it said it would..."*

No architecture in this part. Just the walk.

## The problem

Most "where should I walk" tools want you to keep looking at a screen. You open a
map app, drag around, check the sun, pick a loop, and by the time you leave the
light has moved. I wanted the opposite: a few minutes at the keyboard that end in
a single printed page, and then a phone in your pocket.

So the output is a one-page route card (big type, a little map) plus a GPX file
for Organic Maps or OsmAnd. The screen is the shortest part of the experience.

## The rule that makes it work: the model never routes

A 1B–3B model cannot plan a loop through a real street network. It will invent a
road, miss a dead end, and hand you a route that crosses a river. So the split is:

- **The model does language.** It reads your request ("45 minutes before dark,
  trees and quiet") into structured parameters, and it writes the card.
- **Deterministic code does everything numeric.** `astral` computes sunset and
  the golden-hour window, `osmnx` downloads the walk network and green space,
  `networkx` builds and scores the loop.

The pipeline is a small LangGraph: `intake → sun → weather → map_fetch →
route_builder → critic → card_writer → render`. The `critic` can send the route
back for another attempt, loosening the target if it cannot hit the length.

## Reading the request with a JSON schema

The `intake` node asks the local model (Ollama) for structured output, so even a
small model returns valid JSON:

```python
resp = llm.chat_structured(
    model=state["model_name"],
    system="Extract walk parameters. Return JSON only.",
    user=state["user_input"],
    schema=IntakeParams.model_json_schema(),
    temperature=0.0,
    keep_alive="10m",   # stay warm until the card is written
)
intake = IntakeParams.model_validate_json(resp)
```

If the model is unreachable or returns junk, the node falls back to defaults and
records a warning. The app always produces a card.

## Writing the card from facts only

The `card_writer` prompt is deliberately constrained: the model may only use the
verified facts, and every place name must be wrapped in `[[double brackets]]` so
it can be checked afterwards.

```text
Use ONLY these facts. Do not invent places, landmarks, or plants.
Wrap every place name in [[double brackets]].
Start: ... | Distance: 3.4 km (~45 min) | Sunset: 2026-10-11 18:08
Golden light comes from the 271° . Weather: 29 C, 20% rain
Green spaces on the route: Allah Rakha Park, Bagh-e-Lyari
```

Then a check pulls every `[[name]]` back out and compares it to the OSM list:

```python
unknown = unknown_names(card_text, state["place_names"])
if unknown:
    warnings.append(f"unknown place names: {', '.join(unknown)}")
```

That check is the difference between "the model wrote a nice card" and "the model
wrote a nice card that sends you to a park that does not exist."

## What went wrong

- **The 1B model invented a place.** On one run `llama3.2:1b` wrote a name that
  was not in the OSM data. The bracketed-name check caught it and logged a
  warning instead of shipping it. Not every run — the honest number is in the
  table below.
- **OSMnx drops latitude/longitude when it saves a projected graph.** The GPX
  export came out with empty coordinates until the loader inverse-projected the
  `x`/`y` node attributes back to WGS84.
- **`weasyprint` would not install on Windows.** I print the HTML from Edge
  headless (or a browser) instead, and treat the PDF as best-effort.

[FIELD TEST — add anything the walk itself exposed: a dead end, a retraced
segment, a muddy path, the light arriving earlier than the card said.]

## The model comparison

Same request, same start point, same map — only the model changes. The router has
no LLM, so route quality is identical; the interesting columns are the
hallucination count and the card length.

| Model | Pace read | Words | Hallucinated names | Length error | Peak RAM | Time |
|---|---|---|---|---|---|---|
| `qwen2.5:3b` | normal | 36 | 0 | 0.3% | 259 MB | 106 s |
| `qwen2.5:1.5b` | brisk | 69 | 0 | 4.4% | 260 MB | 16 s |
| `llama3.2:1b` | slow | 56 | 0 | 9.5% | 274 MB | 76 s |
| template (no model) | normal | 55 | 0 | 0.3% | 273 MB | 65 s |

All three fit under 0.5 GB of model memory. The 3B read the pace correctly and
produced the shortest, most on-target card; the smaller models misread the pace,
which moves the target length and the length error. Full columns live in
`eval/results.csv`; the harness is `eval/compare.py`.

## Close with the ratio

[FIELD TEST — the numbers from `scripts/time_box.py`.]

> Minutes at the screen: __. Minutes outside: __. Ratio: __ : 1.

The whole point: the screen should lose.

---

### References

- Ollama structured outputs — https://docs.ollama.com/capabilities/structured-outputs
- "Ollama Structured Outputs in Practice — Getting Type-Safe JSON from Local LLMs
  with Pydantic" — https://dev.to/jangwook_kim_e31e7291ad98/ollama-structured-outputs-in-practice-getting-type-safe-json-from-local-llms-with-pydantic-m38
- "Your LLM Returns JSON That Isn't JSON: A Robust Structured-Output Pipeline for
  Local Models" — https://dev.to/syed_anwar/your-llm-returns-json-that-isnt-json
