# Measuring screen time vs outside time

The point of the project is that planning the walk costs a few minutes at the
screen and buys an hour outside. To keep the number honest, count it the same
way every time.

**Screen time** - start the clock when you open the terminal; stop when the card
is printed or the PDF is saved. It includes typing the request, waiting for the
model, and generating/printing the card.

**Outside time** - start when you close the front door; stop when you are back
through it, including the walk and any stops.

**Not counted:** charging the laptop, the first-time map download, and pulling
models - those are setup, not the routine. Note them separately if they are
large.

```bash
python scripts/time_box.py --screen 4 --outside 46
python scripts/time_box.py --screen 4 --outside 46 --md   # markdown row for the post
```

The two numbers go in `docs/field_test.md`; the ratio goes in the post.
