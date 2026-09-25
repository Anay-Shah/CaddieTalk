# Progress

A plain-language log of what actually exists so far. Newest entries at the top.
For *why* decisions were made, see `DECISIONS.md`. For the full plan, see
`docs/architecture.md`.

**Current milestone:** M4 — Backend on AWS (not started; first milestone that spends money)
**Overall:** M0–M3 complete. The whole brain of the app works locally.

---

## Milestone status

| Milestone | What it delivers | Status |
|-----------|------------------|--------|
| M0 | Repo structure, tooling, CI, decision log | ✅ Done |
| M1 | Import a real course from OpenStreetMap into clean per-hole geometry | ✅ Done |
| M2 | Strategy engine — Monte Carlo simulation and aim optimization | ✅ Done |
| M3 | Player model — per-club distance and dispersion | ✅ Done |
| M4 | Backend on AWS (first milestone that spends money) | ⬜ Next |
| M5 | Mobile app v1 — map, GPS, distances, shot logging | ⬜ Not started |
| M6 | Text caddie — Bedrock agent with tools | ⬜ Not started |
| M7 | Voice caddie — push-to-talk | ⬜ Not started |
| M8 | Lie photo analysis | ⬜ Not started |
| M9 | Post-round review and practice plans | ⬜ Not started |

**Money spent on AWS so far: $0.** Nothing is deployed. M1–M3 run entirely on your laptop.

---

## 2026-09-24 — M3 complete: the player model

**The engine now learns your actual game instead of assuming a generic one.** With M2 the
advice was competent but impersonal — it assumed you hit a 7 iron 135 yards because that's
what a typical mid-handicapper does. Now it measures.

### What it does

Every logged shot gives two numbers once you know where the player was aiming:

- **How far it went** — measured *along* the line to the target, not straight-line to
  where it finished. A shot 140 m down the line that finishes 30 m right travelled 140 m,
  not 143 m.
- **How far off line** — the sideways miss, positive for right.

Collect those per club and you get the four numbers the simulator needs: average distance,
how much that varies, systematic miss, and how much *that* varies.

### The payoff, concretely

Same 150-yard approach on BraeBen's 11th, for a player who hits it 20 m shorter than the
default assumes and leaks it right:

```
generic bag : 6i   straight at it      expected 3.29
measured bag: 4i   10 yds left         expected 3.40
```

Two more clubs, and aim left to allow for the push. That is the difference between an app
that knows golf and an app that knows *your* golf.

### Three judgement calls

1. **Early shots barely move the needle.** One long drive shouldn't convince the app you
   hit a 7 iron 200 yards. Real shots are blended against the generic starting numbers,
   with the generic ones carrying the weight of about 8 shots. After a couple of rounds
   your real numbers dominate.
2. **Duffs are thrown away.** One topped shot that goes 25 yards would otherwise drag a
   club's average down permanently. Shots under ~55% of a club's typical distance are
   treated as mishits and excluded — a duff is a different event, not the tail of the same
   distribution.
3. **Spread needs more evidence than average.** Two shots tell you something about how far
   a club goes and nothing trustworthy about how much it scatters, so the spread stays at
   the default until there are at least four shots.

All three are configurable in `data/config/engine.yaml`.

### Testing

25 new tests, 121 total, all passing. The acceptance check is a round trip: generate
shots from a known distribution, fit them back, and confirm you recover roughly what you
started with. It uses the *same* sampler the engine simulates with, so the test also
proves the player model and the simulator agree on what a shot actually is.

**Still $0 spent on AWS.** M4 is the first milestone that costs anything.

---

## 2026-09-24 — M2 complete: the strategy engine

**The engine now gives real club and aim recommendations on real holes.** This is the
heart of the project — everything before it was setup.

Try it:

```bash
.venv/bin/python -m caddie_engine recommend data/courses/braeben/course.json --hole 3 --handicap 15
```

which prints something like:

```
Braeben Golf Course — hole 3 (par 4)
  311 yds to pin, from tee, handicap 15

Dr, aim 20 yds right (expected 4.38)
  alt: 3w 25 yds right (4.41)
```

and writes a heatmap showing where 3,000 simulated tee shots actually land.

### How it works, briefly

1. **Sample.** Draw thousands of plausible shots from your club's distribution — how far
   it goes on average, and how much that varies.
2. **Adjust.** Wind and elevation change how far the shot has to travel; rough costs
   distance and accuracy.
3. **Classify.** Work out what each simulated ball landed on: green, fairway, bunker,
   water, trees, rough.
4. **Score.** Look up "how many more shots from here" for each landing spot, add penalty
   strokes for water, and average.
5. **Repeat** for every sensible club against a fan of aim points, and pick the lowest
   average.

The strategy is not programmed in anywhere. "Aim away from the bunker" emerges from
counting outcomes.

### Does it actually give sensible advice?

Three checks, all of which it passes:

- **On a dogleg** (BraeBen hole 3), it aims down the fairway rather than straight at the
  pin — which is what any golfer would do.
- **In wind**, from 150 yards it plays 6 iron in calm, **4 iron into a 15mph wind**,
  7 iron downwind, and 5 iron when the green is 10 yards uphill. That is exactly how a
  caddie clubs a player.
- **By skill**, a 5-handicap gets a better expected score than a 25-handicap from the same
  spot.

### Two real bugs the tests caught

1. **The engine was blind to greenside bunkers.** My strokes table only went down to about
   20 metres for rough and sand, so anything nearer clamped to the same value — meaning a
   bunker beside the green cost exactly as much as rough. Fixed by extending the table
   down to 5 metres.
2. **Crosswind blew the ball the wrong way.** A sign error meant the ball drifted *into*
   the wind rather than with it. Caught by a test asserting that wind from the left pushes
   the ball right.

There was also a third finding that turned out not to be a bug. A test expecting a
greenside bunker to shift the aim kept failing — but investigating showed the engine was
right and the test was wrong. At 20 metres from the pin, sand costs only slightly more
than rough, so being closer to the hole is worth the risk. Re-reading the plan, the
scenario it describes is a **fairway** bunker on a tee shot, where the penalty is much
larger. With that scenario the engine shifts the aim decisively, even for a straight
hitter.

96 tests passing, none touching the network.

### Known approximations (deliberate, see DECISIONS.md)

- The strokes-to-hole-out table is hand-built, not fitted from data. Good enough for
  comparing aim points; not to be quoted as fact.
- Club distances come from a generic mid-handicap bag. **M3 replaces this with your real
  numbers**, which is what makes the advice personal rather than generic.
- Water is scored as "penalty stroke, then play from rough nearby" rather than computing
  an exact drop point.

---

## 2026-09-24 — M1 complete: course import from OpenStreetMap

**You can now type a course name and get clean, per-hole geometry out the other end.**
Verified end to end by importing the Old Course at St Andrews: all 18 holes, correct pars
(par 72), every green found, and a plot where each hole is visually recognizable — the
Swilcan Burn shows up on 1 and 18, the Road Hole bunker on 17.

Try it:

```bash
.venv/bin/python -m course_import search --near 56.348,-2.803 --radius 5
.venv/bin/python -m course_import import --name "Old Course" --near 56.348,-2.803
```

It writes `course.json` (metres, for the engine), `course.geojson` (lat/lon, for the
phone app — you can drag it onto geojson.io to view), `holes.png` (one panel per hole for
checking by eye), and a cached copy of the raw map data.

### Three real problems the St Andrews test caught

Testing against a real course rather than synthetic data surfaced bugs that would have
quietly produced wrong recommendations later:

1. **Neighbouring courses bled in.** Seven courses share the property at St Andrews, so
   searching a bounding box returned a blend of all of them — hole numbers appeared up to
   five times each. Fixed by clipping everything to the named course's own boundary.
2. **Interleaved holes still collided.** Even after clipping, the Old and New Courses
   overlap enough that two different ways both claimed hole 3. Fixed by preferring
   OpenStreetMap's `course:name` tag, then falling back to whichever hole line sits more
   fully inside the boundary.
3. **Seven holes had no green.** The Old Course has *double greens* — pairs of holes share
   one enormous green. The original code let only one hole claim each green. Same bug
   applied to its shared fairways. Both are now shareable, which is correct for links
   courses generally, not just this one.

All three are covered by regression tests so they can't come back.

### Test suite

29 tests, all passing, none of which touch the network — the pipeline is exercised against
a synthetic course laid out to reproduce the tricky cases above.

---

## 2026-09-24 — M0 complete: project setup

The skeleton everything else hangs off. No application logic yet by design.

- **Monorepo layout** matching `docs/architecture.md` — `services/` for backend Python,
  `infra/` for AWS definitions, `data/` for tunable config, `apps/` for the mobile app later.
- **Tooling** — `pyproject.toml` with ruff (linting), black (formatting), pytest (tests).
  A `Makefile` wraps the common commands so you don't have to remember them:
  `make install`, `make test`, `make lint`, `make fmt`.
- **CI** — GitHub Actions runs linting and tests on every push. It deliberately never calls
  Bedrock or any paid AWS service.
- **CDK skeleton** in Python — an empty stack that synthesizes, plus `guardrails.py` which
  holds every cost-protection value in one place (log retention, timeouts, concurrency
  caps) so no resource can quietly skip them.
- **`DECISIONS.md`** — six decisions recorded, covering the architecture changes made
  before building started.

---

## 2026-09-24 — Architecture review

Reviewed `docs/architecture.md` before writing code and made four changes, all recorded in
`DECISIONS.md`:

1. **Merged the engine and caddie into one container image** (D-001). The original design
   had one Lambda calling another Lambda, which wastes time and money on every request.
   Now the caddie just calls the engine directly as a library.
2. **CDK in Python instead of TypeScript** (D-002). Drops the project from three
   toolchains to two.
3. **Cut Amazon Transcribe from the first version** (D-003). On-device speech recognition
   is free and good enough; the cloud fallback was complexity for a problem we may not have.
4. **Wrote down which AWS services we're deliberately *not* using** (D-004), so the
   question doesn't get relitigated every time one looks tempting.

Plus cost guardrails (D-005) and a decision not to let the strokes-gained baseline block
progress (D-006).
