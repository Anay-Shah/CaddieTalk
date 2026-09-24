# CaddieTalk

A voice-first AI golf caddie that knows your game.

It combines three things: **your data** (every shot logged with club and GPS, so the app
learns your real distances and miss patterns), **the course** (hole geometry from
OpenStreetMap, plus live wind and elevation), and **a strategy engine** (a Monte Carlo
simulator that throws thousands of virtual shots using your dispersion and finds the club
and aim point with the lowest expected score).

On top sits an AI caddie you can talk to. Every number in its reply comes from the engine
or your player model — never from the model guessing.

> **You:** "I'm thinking 7 iron, I feel like I've been hitting it long today."
>
> **Caddie:** "Plays about 152 with this breeze into you. Your 7 averages 148, and you've
> been about 5 long today, so 7 works. Don't go at the pin though — your right miss brings
> the bunker in. Middle of the green."

## Where to start

| Document | What it's for |
|----------|---------------|
| [`PROGRESS.md`](PROGRESS.md) | What's built so far, in plain language |
| [`docs/architecture.md`](docs/architecture.md) | The full plan — features, milestones, system design |
| [`DECISIONS.md`](DECISIONS.md) | Why things are the way they are |

## Setup

```bash
make install        # creates .venv and installs everything
make test           # run the test suite
make lint           # ruff + black
```

Requires Python 3.11+. Nothing here touches AWS yet — milestones M1 through M3 run
entirely on your machine and cost nothing.

## Importing a course

```bash
# What's nearby?
.venv/bin/python -m course_import search --near 56.348,-2.803 --radius 5

# Import one
.venv/bin/python -m course_import import --name "Old Course" --near 56.348,-2.803

# Re-render the verification plot from an existing import
.venv/bin/python -m course_import plot data/courses/old-course/course.json
```

This writes to `data/courses/<course-id>/`:

- `course.json` — per-hole geometry in projected metres, for the engine
- `course.geojson` — the same geometry in lat/lon, for the mobile app (and viewable at
  [geojson.io](https://geojson.io))
- `holes.png` — one panel per hole, for checking the import by eye
- `raw_osm.json` — the cached OpenStreetMap response, so re-imports don't re-query

Always look at `holes.png` before trusting an import. OpenStreetMap coverage varies a lot
by course, and bad geometry is obvious in a picture long before it produces a wrong number.

## Layout

```
services/engine/          strategy engine — pure Python, no AWS imports
services/course_import/   OpenStreetMap → per-hole geometry
infra/                    AWS CDK app (Python)
data/config/              tunable engine parameters
data/baselines/           strokes-gained lookup tables
docs/                     architecture
```

## Attribution

Course geometry comes from [OpenStreetMap](https://www.openstreetmap.org/copyright),
licensed under the Open Database License (ODbL). The mobile app must display this
attribution.
