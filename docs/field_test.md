# Field test — golden hour walk

Fill this in as you go. Keep it short and concrete: times, place names, what the
route got right and wrong. This log feeds the "open outside" and "what went
wrong" sections of the post.

## Run

- Date: ____
- Start point (lat, lon): ____
- Request typed into `ghwalk`: ____
- Model: ____ (e.g. `qwen2.5:3b`)
- Sunset on the card: ____ | I left home at: ____

Generate the card for this run and print it:

```bash
python -m ghwalk --request "45 minutes before dark, trees and quiet" \
  --lat ____ --lon ____ --tz ____ --model qwen2.5:3b
# open output/card.html in a browser and print to PDF (or use output/card.pdf)
```

## Before leaving (screen time)

- Minutes spent at the screen (type request -> print card): ____
- What I re-ran or changed: ____

## The walk (outside time)

- Out the door: ____ | Back: ____ -> **outside = ____ min**
- Weather on the card: ____ | Actual weather: ____
- Route on the card: ____ km, green ____%, overlap ____%
- Followed the card? yes / partly / no. Where I deviated: ____
- What the route got right: ____
- What went wrong (dead end, retraced itself, muddy, dark before sunset,
  invented place name, ...): ____
- If a name was invented, did the `[[name]]` check flag it? (see the run output
  or `python eval/hallucination.py --places-file ... --card-file ...`): ____

## The light

- Card said the low sun would be from the ____; it actually came from the ____
- Photo notes: the card in hand / the route / the light

## Photos

Add these under `docs/photos/` (they are not required to build the project):

- [ ] `docs/photos/card-in-hand.jpg`
- [ ] `docs/photos/route.jpg`
- [ ] `docs/photos/light.jpg`

## Numbers for the post

| | Minutes |
|---|---|
| At the screen | ____ |
| Outside | ____ |
| Ratio (outside : screen) | ____ |

One sentence on whether it was worth it: ____
