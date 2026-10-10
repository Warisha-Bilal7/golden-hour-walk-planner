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
# Get current repository owner and name automatically
REPO=$(gh repo view --json owner,name --jq '.owner.login + "/" + .name')

# Milestones (add due_on in ISO 8601 if you want deadlines: -f due_on="2026-10-12T23:59:00Z")
for m in "M0 Setup" "M1 Routing core" "M2 Sun, weather, render" \
         "M3 Local LLM nodes" "M4 Critic and eval" "M5 Field test and write-up"; do
  gh api "repos/$REPO/milestones" -f title="$m" >/dev/null
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
