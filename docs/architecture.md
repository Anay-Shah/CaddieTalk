# CaddieTalk — Architecture & Build Plan

> Name: **CaddieTalk**. A voice-first AI golf caddie that knows your game.
> This document is the single source of truth for the project. It is written so that
> Claude Code (or any developer) can read it, break it into features, and build it
> milestone by milestone.

---

## 1. What this project is

CaddieTalk is a mobile app that acts like a real caddie standing next to you on the course.

It combines three things:

1. **Your data.** Every shot you hit is logged (club + GPS), and the app learns your real
   distances and miss patterns for each club.
2. **The course.** Hole geometry (tees, fairways, greens, bunkers, water, trees) is pulled
   from OpenStreetMap, plus live wind and elevation.
3. **A strategy engine.** A Monte Carlo simulator throws thousands of virtual shots using
   *your* dispersion and finds the club and aim point with the lowest expected score.

On top of that sits an **AI caddie** (an LLM agent with tools) you can talk to naturally.
You tell it what you're thinking, it combines what you said with the numbers, and it talks
back like a caddie would. You can also snap a photo of your lie and it factors that in.

### Example exchange

> **You:** "I'm thinking 7 iron, I feel like I've been hitting it long today."
>
> **Caddie:** "Plays about 152 with this breeze into you. Your 7 averages 148, and you've
> been about 5 long today, so 7 works. Don't go at the pin though — your right miss brings
> the bunker in. Middle of the green."

Every number in that reply comes from the engine or the player model, never from the LLM
guessing. The LLM's job is to reason, explain, and converse.

---

## 2. Goals and non-goals

### Goals
- Build a genuinely useful on-course tool that the builder will actually use.
- Showcase: data modeling, simulation, geospatial processing, an LLM agent with real
  tools, voice interaction, vision, and a sensible cloud architecture.
- "Good enough and enjoyable" over flawless. Each milestone should produce something
  demoable.

### Non-goals (for now)
- Scaling to thousands of users.
- Hardware sensors (club tags, launch monitors).
- Live video streaming on the course.
- Use in competition rounds (see Rules of Golf note in section 15).

---

## 3. Who this is for

- **Primary user:** the builder — a newer/improving amateur golfer who wants smarter
  course management and to understand their own game.
- **Broader audience (if it grows):** amateur golfers roughly in the 5–30 handicap range
  who lose strokes to poor strategy (aiming at pins, bringing hazards into play, wrong
  club choice) rather than purely to swing mechanics.
- **Portfolio audience:** interviewers. The project should make it easy to talk about
  design decisions and trade-offs.

---

## 4. Platform

- **Mobile app:** React Native with **Expo**, iOS and Android. The phone is what you
  carry on the course and provides GPS, compass, camera, and microphone.
- **Backend:** Python services on AWS (serverless first).
- **Infrastructure:** AWS CDK in **Python**.
- **Optional later:** a small web dashboard (React) for reviewing rounds and stats.

### Why two languages

The app and the backend are separate programs that communicate over HTTPS with JSON, so
each side can use whatever language suits it. React Native is JavaScript, so the app is
TypeScript by necessity. The backend is Python because the strategy engine — the hard part
of this project — depends on libraries JavaScript has no real equivalent for: **NumPy**
(vectorized Monte Carlo over millions of samples, in C), **Shapely/GEOS** (batch
point-in-polygon lie classification), and **pyproj** (lat/lon → UTM projection). Notebooks
for visual verification of holes come free with that choice.

CDK is written in Python rather than TypeScript so that everything server-side shares one
language, one virtualenv, and one toolchain. See `DECISIONS.md` (D-002).

---

## 5. Features

Feature IDs are referenced in the build plan (section 13).

### P0 — MVP (must have)

| ID | Feature | Description |
|----|---------|-------------|
| F-01 | Course import | Import a course from OpenStreetMap (Overpass API) into clean per-hole geometry. |
| F-02 | Hole map | Show the current hole on a satellite map with fairway/green/hazard overlays and live GPS position. |
| F-03 | GPS distances | Distance to front/center/back of green, to pin (user-placed), and to hazards. |
| F-04 | Shot logging | Tap "shot" + pick club at each shot. Landing spot is inferred from the next shot's start. Putts entered as a count per hole. |
| F-05 | Player model | Per-club distance and lateral dispersion, blended with a handicap-based prior when data is thin. |
| F-06 | Strategy engine | Monte Carlo simulation over clubs × aim points → best club, best aim point, expected score, hazard risk. |
| F-07 | Conditions | Wind (speed/direction) and elevation change applied to "plays-like" distance and lateral drift. |
| F-08 | Text caddie | Chat with an LLM caddie that receives full situational context and can call engine tools. |
| F-17 | **Voice caddie (live call)** | Headphones in, talk back and forth naturally with interruptions, like a phone call with a caddie walking beside you. **The primary voice experience.** |
| F-25 | **Caddie avatar** | A minimal 3D-feeling silhouette in a golf cap that listens, speaks, and turns to look at whatever it is talking about. |
| F-09 | Voice caddie (push-to-talk) | Hold a button, speak, hear the reply. The **fallback** when there are no headphones, no signal, or company who would rather you didn't talk to your phone. |
| F-10 | Pre-round game plan | Generate a hole-by-hole plan before the round and cache it on the phone for bad reception. |

### P1 — Should have (next up)

| ID | Feature | Description |
|----|---------|-------------|
| F-11 | Lie photo analysis | Snap a photo of the ball; a vision model assesses the lie (e.g. sitting down in rough → flyer, buried in bunker) and adjusts the recommendation. |
| F-12 | Post-round review | Strokes gained by category (off the tee, approach, around the green, putting) with an AI summary. |
| F-13 | Practice plan | Agent builds a range session targeting the weakest category, and adapts over time. |
| F-14 | "Today's form" | Weight recent shots so the model reflects how you're hitting it *today*. |
| F-15 | Risk mode | Toggle conservative / balanced / aggressive (optimize expected score vs. avoid blow-up holes). |
| F-16 | Heatmap view | Visualize where your simulated shots land for the recommended vs. alternative aim. |

### P2 — Stretch / nice to have (so we remember)

| ID | Feature | Description |
|----|---------|-------------|
| F-18 | Hands-free wake word | "Hey caddie" to start a call without touching the phone. |
| F-19 | Auto shot detection | Detect swings from the phone accelerometer + GPS so logging is automatic. |
| F-20 | Range swing analysis | Film swings at the range; pose estimation compares good vs. bad swings *of your own*. |
| F-21 | Voice shot logging | "7 iron, thin, went right" → structured shot data. |
| F-22 | Watch app | Distances and caddie on Apple Watch / Wear OS. |
| F-23 | Green reading | LiDAR scan of a green (iPhone Pro) + putt physics simulation. |
| F-24 | Caddie personalities | Choose the caddie's vibe (calm veteran, hype man, stats nerd). |

---

## 6. System architecture

```
┌─────────────────────── Mobile app (Expo / React Native) ───────────────────────┐
│  Map + GPS  ·  Shot logging  ·  Chat  ·  Push-to-talk  ·  Camera  ·  Plan cache │
└───────────────┬───────────────────────────────────────────────┬────────────────┘
                │ HTTPS + Cognito JWT                           │ (P2) WebSocket audio
        ┌───────▼────────┐                              ┌───────▼─────────────────┐
        │  API Gateway   │                              │ Realtime voice server   │
        │   (HTTP API)   │                              │ ECS Fargate (P2 only)   │
        └──┬──────────┬──┘                              └───────────┬─────────────┘
           │          │                                             │
  ┌────────▼───┐   ┌──▼────────────────────────────────────────┐    │
  │ Data API   │   │   ONE CONTAINER IMAGE, TWO FUNCTIONS      │◄───┘
  │ Lambda     │   │                                           │
  │ rounds,    │   │  ┌─────────────┐    ┌──────────────────┐  │
  │ shots,     │   │  │ engine fn   │    │ caddie fn        │  │
  │ courses    │   │  │ (high mem)  │    │ context builder  │  │
  └──┬─────────┘   │  │ /engine/*   │    │ + Bedrock loop   │  │
     │             │  └─────────────┘    └──┬────────┬──────┘  │
     │             │         ▲              │        │         │
     │             │         └── in-process ┘        │         │
     │             │     caddie_engine library       │         │
     │             │   (NumPy · Shapely · pyproj)    │         │
     │             └─────────────────┬───────────────┼─────────┘
     │                               │               │
  ┌──▼───────────────────────────────▼──┐   ┌────────▼──┐ ┌─────────┐
  │ DynamoDB          │   S3            │   │ Bedrock   │ │ Polly   │
  │ rounds, shots,    │   course JSON,  │   │ Claude    │ │ (TTS)   │
  │ player model,     │   lie photos,   │   └───────────┘ └─────────┘
  │ turns             │   audio         │
  └───────────────────┴─────────────────┘
External: OpenStreetMap Overpass API · Open-Meteo (wind, elevation)
```

**Why one image, two functions.** The engine is a pure Python library, so the caddie calls
it in-process rather than invoking a second Lambda. That removes a cross-function hop from
the latency budget and one service from the system, while still letting the two functions
be tuned independently (the engine function gets more memory for NumPy; the caddie
function is mostly waiting on Bedrock). See `DECISIONS.md` (D-001).

### Request flow: one caddie voice turn (P0, push-to-talk)

1. User holds the talk button and speaks.
2. App transcribes speech on-device. (No cloud STT in P0 — see section 7.6.)
3. App sends `POST /caddie/turn` with the transcript, the current GPS position, hole,
   selected club, pin location, and (optional) a lie photo reference.
4. Caddie Lambda builds the **context packet** (section 7.5): player model, hole geometry
   summary, conditions, and the engine's precomputed recommendation for this spot.
5. Caddie Lambda calls Claude on Bedrock (Converse API) with tools. If the user asks a
   "what if", the model calls `simulate(...)`, which runs the `caddie_engine` library
   in-process.
6. Final reply text is sent to Polly for speech.
7. App receives `{ reply_text, audio_url, recommendation }` and plays the audio.

**Latency target:** under ~4 seconds end to end. Golf is slow, so this feels natural.

---

## 7. Components in detail

### 7.1 Mobile app

- **Screens:** Sign in · Course search/import · Round setup (tees, risk mode) · Hole view
  (map, distances, recommendation card, shot button, talk button) · Chat · Round summary.
- **Map:** `react-native-maps` with satellite imagery and GeoJSON polygon overlays.
- **Location:** `expo-location` for GPS; compass heading via `expo-sensors` / location
  heading to know which way the player is facing.
- **Camera:** `expo-camera` for lie photos (P1).
- **Audio:** record + playback via Expo audio APIs; on-device speech recognition via a
  library such as `expo-speech-recognition` (verify current package status).
- **Offline:** cache the pre-round plan (F-10), course geometry, and player model locally.
  Queue shot logs when offline and sync later.

### 7.2 Course data pipeline

- Query OpenStreetMap via the **Overpass API** for a course bounding box. Relevant tags:
  - `leisure=golf_course` (course boundary)
  - `golf=hole` (line from tee to green, often with `ref` = hole number and `par`)
  - `golf=tee`, `golf=fairway`, `golf=green`, `golf=bunker`, `golf=rough`
  - `golf=water_hazard`, `golf=lateral_water_hazard`, `natural=water`
  - `natural=wood`, `landuse=forest` (treat as "trees/recovery")
  - `golf=out_of_bounds` / course boundary (often missing — treat as optional)
- Convert lat/lon to a local metric coordinate system (UTM via `pyproj`) so distances are
  simple Euclidean math.
- Assign each polygon to a hole (by proximity to the hole line).
- Output one `course.json` per course (see section 8) and store it in S3.
- If a course is missing or incomplete in OSM, the builder can trace it in the OSM editor
  (OSM data is ODbL-licensed — include attribution in the app).
- Include a plot script (matplotlib or folium) to visually verify each hole.

### 7.3 Player model

- For each shot (except putts): start point, end point (= next shot's start), club.
- **Distance** = straight-line distance start → end.
- **Lateral offset** = perpendicular distance from the target line. v1 assumption: the
  target is the pin (or green center) for approach shots and the hole line / fairway center
  for tee shots. Later: let the user tap their intended target.
- Fit per club: `mean_dist`, `sd_dist`, `mean_lat`, `sd_lat` (normal distributions; allow
  correlation later).
- **Prior blending:** start from typical values for the player's handicap and blend:
  `estimate = (k * prior + n * sample_mean) / (k + n)` with `k ≈ 5–10` pseudo-shots.
  Same idea for standard deviations. (A proper Bayesian model is a later upgrade.)
- **Today's form (P1):** an exponentially weighted version emphasizing the current round.
- Recompute on every shot write (cheap) or at round end.

### 7.4 Strategy engine (the core)

Input: position, hole geometry, pin location, current lie, conditions, player model,
risk mode.

Algorithm:

1. **Candidates.** Clubs whose adjusted distance is plausible for this shot, × a grid of
   aim points (e.g. every ~5 yards across a cone toward the green / down the fairway).
2. **Sample.** For each candidate, draw N shots (N ≈ 2,000–5,000) from the club's
   distribution, vectorized in NumPy.
3. **Adjust.** Apply wind and elevation (configurable heuristics — see below), and a lie
   modifier (e.g. rough reduces distance / widens dispersion; flyer lie adds distance).
4. **Classify landings.** Point-in-polygon against hole features (Shapely vectorized
   `contains_xy`, STRtree for speed): green, fairway, rough, sand, trees, water, OB.
5. **Score.** `expected = 1 + mean(strokes_to_hole_out(lie, distance_to_pin))`
   - Water: +1 penalty, then evaluate from a drop point (approximate: nearest point on the
     hazard edge back along the line of flight, in rough).
   - OB (if mapped): +1 penalty and replay from the original spot (stroke and distance).
6. **Pick.** Lowest expected score. Also report hazard probabilities and the
   alternatives (e.g. "driver: 4.31, 3 wood: 4.24").
7. **Risk mode (P1).** Conservative mode penalizes variance / probability of double bogey+.

**Strokes-to-hole-out baseline.** A lookup table by lie and distance
(tee / fairway / rough / sand / recovery / green), interpolated, stored as CSVs in
`data/baselines/` with a handicap scaling factor.

This does not need to be authoritative to be useful. Start with a reasonable
parameterized curve per lie, note in the CSV header that it is a tunable approximation,
and move on — the engine's *relative* comparisons (this aim point vs. that one) are far
less sensitive to baseline accuracy than the absolute expected-score numbers are.
Refine it later against real logged rounds, or against published strokes-gained research
if a properly licensed source turns up. The one rule that stays: numbers live in the CSV
with a note on where they came from, never hard-coded in the engine.

**Conditions heuristics (starting values, configurable, tune later):**
- Headwind: roughly +1% plays-like distance per mph.
- Tailwind: roughly −0.5% per mph.
- Crosswind: lateral drift proportional to wind component and shot distance.
- Elevation: roughly 1 yard of plays-like distance per yard (≈3 ft) of elevation change.
- Keep all of these in a single config file so they can be tuned.

**Performance.** Vectorize everything; a single recommendation should run in well under a
second in Lambda. The pre-round plan (F-10) evaluates each hole from the tee and a few
typical approach positions.

**Units.** Meters internally, yards in the UI and in caddie speech.

### 7.5 AI caddie agent

**Model:** Claude on Amazon Bedrock via the **Converse API** (supports tool use and images).

**Context packet** (attached to every turn so the caddie never starts from zero):

```json
{
  "hole": { "number": 7, "par": 4, "hazards_summary": "bunker right of green, water long" },
  "position": { "lie": "fairway", "to_pin_yds": 148, "to_front_yds": 139, "to_back_yds": 161 },
  "conditions": { "wind_mph": 8, "wind_relative": "into, slightly left-to-right", "elevation_change_yds": 3 },
  "plays_like_yds": 156,
  "selected_club": "7i",
  "player_model": { "7i": { "mean_yds": 148, "sd_yds": 9, "mean_lat_yds": 4, "today_delta_yds": 5 } },
  "engine_recommendation": {
    "club": "7i", "aim": "center of green", "expected_score": 3.21,
    "hazard_probs": { "bunker_right": 0.08, "water_long": 0.02 },
    "alternatives": [ { "club": "6i", "aim": "pin", "expected_score": 3.33 } ]
  },
  "round_so_far": { "score_to_par": 3, "holes_played": 6 },
  "user_utterance": "I'm thinking 7 iron, I feel like I've been hitting it long today."
}
```

**Tools:**

| Tool | Purpose |
|------|---------|
| `simulate(club, aim, lie_modifier?)` | Run the engine for a specific club/aim and return expected score + hazard probabilities. |
| `recommend(risk_mode?)` | Re-run the full optimization (e.g. after a lie change). |
| `get_club_stats(club)` | Detailed stats for a club, including today's form. |
| `get_hole_info()` | Hazards, carries, layup distances for the current hole. |
| `get_conditions()` | Latest wind and temperature. |
| `assess_lie(image_id)` (P1) | Vision assessment of the lie photo → structured lie modifier. |

**System prompt guidelines:**
- You are a golf caddie: calm, confident, concise. Spoken replies are 1–3 sentences
  unless the player asks for more.
- **Never invent numbers.** Every yardage, percentage, or stat must come from the context
  packet or a tool result. If data is missing, say so.
- Blend the player's feel with the data; acknowledge what they said.
- Give a clear recommendation, but respect the player's decision.
- Always speak in yards.
- Avoid swing-mechanics lectures mid-round; focus on target, club, and commitment.

**Agent loop:** max ~3 tool iterations per turn to keep latency down. Most turns need zero
tool calls because the engine recommendation is already in the context packet.

**Logging:** store each turn (transcript, context, tool calls, reply) in DynamoDB for
debugging and building an evaluation set.

### 7.6 Voice

**The primary experience is a call, not a walkie-talkie.** You put headphones in, you both
just talk, and you can cut the caddie off mid-sentence. This is what makes it feel like
someone walking beside you rather than a device you operate. See `DECISIONS.md` (D-007).

**Live call (F-17, primary):**
- A bidirectional speech-to-speech model holds the conversation (e.g. Amazon Nova Sonic on
  Bedrock — check current versions and tool-use support at build time).
- This needs a connection that stays open for minutes, which Lambda cannot do: Lambda is
  request-and-response only. A small container service holds the session, streams audio
  both ways, and calls the same engine tools as the text caddie.
- **Runs on localhost during development** (`make serve-voice`), so the whole feature can
  be built and played with before deciding anything about hosting. See `DECISIONS.md`
  (D-008).
- The session is bounded: you start a call, talk, and end it. It is not always-listening —
  wind noise, playing partners, and battery make that painful on a course, and a call you
  deliberately start is also the honest answer to the Rules of Golf question in section 16.

**Push-to-talk (F-09, fallback):**
- On-device speech recognition, one request to the caddie, speech back via Amazon Polly.
- Pure request/response, so it works wherever the text caddie works.
- Kept because it degrades gracefully: no headphones, poor signal, or playing partners who
  would rather you didn't hold a conversation with your phone.
- Speech-to-text is **on-device only**; a streaming Amazon Transcribe fallback was cut from
  P0 as a second audio pipeline for a case that may never fire. See `DECISIONS.md` (D-003).

**The avatar (F-25):**
- A minimal silhouette in a golf cap, rim-lit in butter yellow on marine blue. Not a
  photoreal person, and deliberately not a face — it reads as a presence, not an uncanny
  human.
- It listens (head tilts toward you), thinks (glances away), and speaks (motion tracking
  the audio envelope). The detail that matters most: **it turns to look at whatever it is
  talking about** — at the green when it gives you the number, at the bunker when it warns
  you off the pin. That is what sells "standing beside you"; mouth animation is not.
- Rendering approach is open. A rigged 2.5D silhouette gets the same look-around at a
  fraction of the GPU cost of real 3D, and a flat-shaded silhouette has no lighting or
  depth cues to lose by faking it. Battery over four hours is the deciding constraint, not
  fidelity. Start 2.5D; go real-3D only if it feels flat in the hand.

### 7.7 Vision (P1)

- User taps the camera button and photographs the ball / lie.
- Photo uploads to S3 via a presigned URL.
- Caddie calls `assess_lie`, which sends the image to Claude with a structured-output
  prompt returning something like:
  `{ "surface": "rough", "ball_sitting": "down", "flyer_risk": "high", "stance": "ball below feet", "notes": "..." }`
- The lie assessment maps to an engine **lie modifier** (distance and dispersion changes),
  and the recommendation is recomputed.
- Live video coaching is explicitly out of scope on the course (battery, data, reception).

---

## 8. Data model

### DynamoDB tables

| Table | Partition key | Sort key | Key attributes |
|-------|---------------|----------|----------------|
| `Rounds` | `player_id` | `round_id` (ULID) | course_id, tees, date, status, score, risk_mode |
| `Shots` | `round_id` | `seq` | hole, club, start_lat, start_lon, end_lat, end_lon, lie_start, lie_end, penalty, is_putt, putt_count, notes, created_at |
| `PlayerModel` | `player_id` | `club` | mean_dist, sd_dist, mean_lat, sd_lat, n_shots, today_delta, updated_at |
| `Courses` | `course_id` | — | name, centroid_lat, centroid_lon, s3_key, osm_version, holes_count |
| `CaddieTurns` | `round_id` | `turn_ts` | transcript, context_packet, tool_calls, reply_text, latency_ms |

`player_id` = Cognito user `sub`.

### S3 layout

```
courses/{course_id}/course.json      # processed hole geometry
courses/{course_id}/raw_osm.json     # raw Overpass response (for reprocessing)
photos/{player_id}/{round_id}/{id}.jpg
audio/{player_id}/{turn_id}.mp3      # short-lived, lifecycle rule deletes after 1 day
```

### `course.json` shape

```json
{
  "course_id": "string",
  "name": "string",
  "crs": "EPSG:326xx",
  "holes": [
    {
      "number": 1,
      "par": 4,
      "hole_line": [[x, y], ...],
      "tees": [{ "name": "white", "polygon": [[x, y], ...] }],
      "green": [[x, y], ...],
      "fairways": [[[x, y], ...]],
      "bunkers": [[[x, y], ...]],
      "water": [[[x, y], ...]],
      "trees": [[[x, y], ...]]
    }
  ]
}
```

(Store lat/lon alongside or provide a conversion helper so the app can draw overlays.)

---

## 9. Backend API

All endpoints require a Cognito JWT.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/courses/search?lat=&lon=` | Courses near a location (from the `Courses` table). |
| POST | `/courses/import` | Import a course from OSM by name or bounding box. |
| GET | `/courses/{id}` | Processed course geometry. |
| POST | `/rounds` | Start a round (course, tees, risk mode). |
| POST | `/rounds/{id}/shots` | Log a shot. |
| PATCH | `/rounds/{id}/shots/{seq}` | Edit a shot (wrong club, penalty, etc.). |
| POST | `/rounds/{id}/finish` | Close the round; triggers model update and summary. |
| GET | `/rounds/{id}/summary` | Strokes gained breakdown + AI summary (P1). |
| POST | `/rounds/{id}/plan` | Generate the pre-round game plan. |
| GET | `/players/me/model` | Current per-club player model. |
| POST | `/engine/recommend` | Best club/aim for a given situation. |
| POST | `/engine/simulate` | Evaluate a specific club/aim. |
| POST | `/caddie/turn` | One caddie conversation turn (text in → text + audio out). |
| POST | `/uploads/photo` | Get a presigned S3 URL for a lie photo. |

---

## 10. External APIs and services

| API / service | Used for | Notes |
|---------------|----------|-------|
| OpenStreetMap **Overpass API** | Course geometry | Free, rate-limited; cache results in S3. ODbL attribution required. |
| **Open-Meteo** Forecast API | Wind speed, direction, gusts, temperature | Free, no API key. Area-level data, not exact on-course wind. |
| **Open-Meteo** Elevation API | Elevation at shot start / target | Global, coarse resolution; good enough for plays-like adjustments. |
| **Amazon Bedrock** (Converse API) | Caddie LLM, tool use, vision | Request model access in the console first. |
| **Amazon Polly** | Text-to-speech | Neural/generative voices. |
| ~~Amazon Transcribe~~ | — | **Cut from P0.** On-device STT only. |
| **Amazon Cognito** | Auth | Protects the API and Bedrock spend. |
| Device APIs (Expo) | GPS, heading, camera, microphone | `expo-location`, `expo-sensors`, `expo-camera`, audio + speech recognition packages. |
| Map tiles | Satellite basemap | Via `react-native-maps` (Apple Maps / Google Maps providers). |

---

## 11. Models

| Task | Model | Why |
|------|-------|-----|
| Caddie conversation + tool use | Claude Sonnet (latest on Bedrock, e.g. Claude Sonnet 5) | Strong tool use and reasoning with good latency. |
| Lie photo assessment | Same Claude model (vision) | Native image input; structured output. |
| Cheap/fast tasks (voice shot-log parsing, summaries) | Claude Haiku (e.g. Claude Haiku 4.5) | Lower cost and latency. |
| Speech-to-text | On-device recognition | Free and fast; no cloud STT in P0. |
| Text-to-speech | Amazon Polly | Simple, cheap, stays in AWS. |
| **Live voice conversation** | Amazon Nova Sonic (or current equivalent) | Natural back-and-forth with interruptions. The primary voice path (F-17). |
| Strategy | **No ML model** — Monte Carlo simulation + player statistics | Deterministic, explainable, and testable. |

Check exact Bedrock model IDs and regional availability in the Bedrock console at build
time and keep them in config, not in code.

---

## 12. Cloud plan (AWS)

Principle: use a service only where it solves a real problem, and be able to explain why.

| Service | Role | Why this and not something else |
|---------|------|--------------------------------|
| **Lambda** (container image) | Engine fn + caddie fn | Bursty, short compute. Container image because NumPy + Shapely + pyproj exceed the zip size limit. One image, two functions (section 6). |
| **Lambda** (zip) | Data API | Request/response, scales to zero, near-free at personal usage. No heavy deps. |
| **API Gateway** (HTTP API) | Front door | Cognito JWT authorizer; cheaper and simpler than REST API. |
| **DynamoDB** (on-demand) | Rounds, shots, player model, turns | Key-based access patterns; pay per request; $0 at idle. |
| **S3** | Course geometry, photos, audio | Cheap object storage; presigned URLs for direct uploads. |
| **Bedrock** | Caddie LLM + vision | Managed access to Claude; stays inside AWS IAM. |
| **Polly** | Text-to-speech | Managed, cheap, trivial to wire. |
| **Cognito** | Auth | Keeps the API — and therefore Bedrock spend — private. Free at this scale. |
| **CloudWatch** | Logs, metrics, alarms | Track latency, errors, Bedrock token usage. |
| **ECS Fargate** *(decision deferred)* | Live voice server | Long-lived streaming connections don't fit Lambda. Bills while idle (~$25–30/mo with a load balancer), so whether and how to run it is settled at M4 against a working system — possibly only during rounds. |

### Services we are deliberately NOT using

Recorded so the decision isn't relitigated every time one looks tempting:

| Not using | Why |
|-----------|-----|
| **Amazon Location Service** | Worse than Apple/Google map tiles for this use, and it costs money. Maps stay on `react-native-maps`. |
| **Amplify** | Abstracts away exactly the AWS this project exists to learn. |
| **X-Ray** | Timing lines in CloudWatch logs cover the latency budget adequately. |
| **Secrets Manager / SSM Parameter Store** | There are no secrets. Overpass and Open-Meteo are keyless; everything else is IAM. |
| **Step Functions, OpenSearch, RDS/Aurora** | No workflow, search, or relational need. Aurora Serverless also bills at idle. |
| **EventBridge / SQS** | Not yet. Earmarked as the *one* deliberate event-driven exercise at M9 (round finish → model recompute → AI summary), done synchronously first. |
| **Single-table DynamoDB design** | Fashionable, adds real friction, buys nothing at this scale. Separate, clearly-named tables. |

**Infrastructure as code:** AWS CDK in **Python**. No console click-ops for anything that
matters — the one exception is the manual account setup checklist in M0.

**CI/CD:** GitHub Actions — run tests on every push; `cdk deploy` on merge to `main`.

### Cost guardrails ($100 CAD credit budget)

**Baseline: this architecture idles at ~$0.** Lambda, API Gateway, DynamoDB on-demand, and
S3 all bill per request. A week of not touching the project costs cents. That is the main
reason serverless is the right call here, not just a fashion choice.

**Before the first `cdk deploy`:**
- **AWS Budgets** alerts at $10 / $25 / $50, plus a forecast alert. This is step zero of
  M4, not an afterthought.
- Confirm the credits actually cover **Bedrock** — some AWS credit programs exclude
  specific services, and that is much better to discover now than at M6.

**Baked into the CDK so they can't be forgotten:**
- CloudWatch log retention of 14 days on every Lambda (the default is forever).
- DynamoDB explicitly `PAY_PER_REQUEST`.
- S3 lifecycle rule deleting generated audio after 1 day.
- Lambda timeouts of 30s, not the 15-minute default — caps the damage of a runaway loop.
- `reserved_concurrent_executions` of ~5 per function, so a bug cannot fan out to hundreds
  of parallel invocations.
- Lambdas stay **out of any VPC** — a NAT Gateway is ~$35/month and would alone consume
  a third of the budget.

**The three things that actually burn the budget, ranked:**
1. **Leaving something always-on.** NAT Gateway and Fargate + load balancer are the only
   two candidates. Both are avoided or deferred above.
2. **CI running the caddie eval set against real Bedrock on every push.** The single most
   likely accidental burn. Unit tests mock Bedrock; the eval set is run manually and
   deliberately.
3. **A runaway agent loop.** Capped at 3 tool iterations per turn, with `max_tokens`
   limits and the Lambda timeout/concurrency caps above.

**For scale:** a caddie turn is roughly 1,500 input + 150 output tokens, well under a cent.
A full round of heavy conversation is around $0.50. Polly and Cognito are effectively free
at this volume. Realistic spend while actively developing is a few dollars a month.

**Per-turn Bedrock token usage is logged to CloudWatch** so spend can be watched
accumulating rather than discovered on a bill.

---

## 13. Tech stack and repo structure

- **Mobile:** TypeScript, React Native, Expo, react-native-maps
- **Engine & backend:** Python 3.12, NumPy, Pandas, Shapely 2.x, pyproj, pydantic, boto3
- **Infra:** AWS CDK (Python)
- **Testing:** pytest (engine/backend/infra), Jest (mobile)
- **Tooling:** GitHub Actions, ruff + black (Python), ESLint + Prettier (TS)

```
caddietalk/
├── docs/
│   └── architecture.md          # this file
├── DECISIONS.md                 # decision log
├── apps/
│   └── mobile/                  # Expo app
├── services/
│   ├── engine/                  # strategy engine (pure Python library, no AWS imports)
│   │   ├── caddie_engine/
│   │   │   ├── geometry.py      # projection, polygons, lie classification
│   │   │   ├── player_model.py
│   │   │   ├── conditions.py
│   │   │   ├── baseline.py      # strokes-to-hole-out lookup
│   │   │   ├── simulate.py
│   │   │   └── optimize.py
│   │   └── tests/
│   ├── compute/                 # the one container image, two Lambda handlers
│   │   ├── engine_handler.py    # /engine/* — imports caddie_engine
│   │   ├── caddie_handler.py    # context builder, Bedrock loop, Polly
│   │   ├── Dockerfile
│   │   └── tests/
│   ├── api/                     # data API Lambdas (rounds, shots, courses) — zip, light deps
│   └── course_import/           # Overpass fetch + processing
├── data/
│   ├── baselines/               # strokes-gained baseline CSVs (with source notes)
│   └── config/                  # conditions heuristics, model IDs, engine params
├── notebooks/                   # prototyping + visual checks
├── infra/                       # CDK app
└── .github/workflows/
```

Keep the engine a **pure Python library** with no AWS dependencies so it can be tested
locally and reused from notebooks, Lambda, and the P2 voice server.

---

## 14. Build plan (milestones)

Each milestone ends with passing tests and something demoable. Build in order — the AI
layer depends on the engine being trustworthy.

### Revised order (2026-09-25)

**Everything runs on localhost until the app works end to end.** The original plan put the
AWS backend (M4) before the mobile app, which would mean paying for and maintaining
infrastructure while the product is still taking shape. Instead:

```
M0 ✅  M1 ✅  M2 ✅  M3 ✅  →  M5  →  M6  →  M7  →  M4  →  M8+
                                └── all against a local dev server ──┘
```

M5, M6, and M7 talk to a Python dev server on the builder's laptop over wifi. The app
points at one base URL, so switching it to a deployed backend later is a config change,
not a rewrite. **M4 moves after M7**, and begins with a cost and architecture review
against a system that actually exists rather than a guess about one that doesn't. See
`DECISIONS.md` (D-008).

### M0 — Project setup
- Create the monorepo structure above, linting, formatting, and test runners.
- GitHub Actions workflow running Python tests.
- CDK app skeleton in Python (no resources yet).
- `DECISIONS.md` started.
- Document manual steps: AWS account, IAM user with MFA, Budgets alerts, Bedrock model
  access. These are a checklist to run before M4, not now.
- **Done when:** CI is green and `pytest` runs locally.

**No AWS work happens until M4.** M1, M2, and M3 are pure local Python and cost nothing.
Deploying earlier only means paying attention to infrastructure while the simulation is
still the unsolved problem.

### M1 — Course import (F-01)
- Overpass query builder for a course by name or bounding box.
- Parse features into holes; project to UTM; assign polygons to holes.
- Write `course.json`; save raw OSM response.
- Plot script rendering each hole for visual verification.
- **Done when:** a real course imports and every hole plots correctly.

### M2 — Strategy engine prototype (F-06, F-07)
- Baseline table loader with interpolation (with documented sources).
- Vectorized shot sampling, conditions adjustment, lie classification, penalties.
- Aim-grid optimizer returning best club/aim, expected score, hazard probabilities,
  and alternatives.
- Notebook: heatmap of simulated landings and best aim on a real hole.
- Unit tests with synthetic holes, e.g. a straight fairway with a bunker on the right:
  a player who misses right should get an aim point that shifts left.
- **Done when:** recommendations look sensible on real holes and tests pass.

### M3 — Player model (F-05)
- Shot → distance/lateral computation; per-club fit; prior blending by handicap.
- Synthetic shot generator for tests and demos.
- **Done when:** feeding synthetic shots recovers the known distributions.

### M4 — Backend on AWS *(deferred until after M7)*
- **Step zero: a cost and architecture review** against the working local system. The live
  voice service is the open question: it needs a container that bills while idle, so decide
  what actually gets deployed, and whether it runs only during rounds.
- **Then: AWS Budgets alerts at $10 / $25 / $50, and confirm credits cover Bedrock.**
  Nothing else in this milestone starts until that is done.
- CDK: Cognito, API Gateway, DynamoDB tables, S3 bucket, the container image with the
  engine + caddie functions, data API Lambdas, CloudWatch alarms.
- Apply every cost guardrail from section 12 in the CDK itself.
- Implement endpoints in section 9 (except caddie and summary).
- GitHub Actions deploy on merge to `main`. Always `cdk diff` before `cdk deploy`.
- **Done when:** endpoints work end to end from a test script with a real JWT.

### M5 — Mobile app v1 (F-02, F-03, F-04, F-10)
- Auth, course search/import, round setup.
- Hole view: satellite map, overlays, live GPS, distances, user-placed pin.
- Shot logging with club picker; putts per hole; offline queue.
- Recommendation card from `/engine/recommend`.
- Pre-round plan generation and local caching.
- **Done when:** a full round can be played and logged on a real course.

### M6 — Text caddie (F-08)
- Context packet builder.
- Bedrock Converse tool loop with the tools in section 7.5.
- System prompt; turn logging to `CaddieTurns`.
- Chat UI in the app.
- Eval set: ~20 scripted situations checking the caddie uses tools correctly and never
  contradicts engine numbers. **Run manually, never in CI** — automated Bedrock calls on
  every push are the most likely way to burn the credit budget by accident.
- **Done when:** the caddie gives grounded, concise advice across the eval set.

### M7 — Voice caddie (F-17, F-25, F-09)
- Local realtime voice server: holds the session, streams audio both ways, calls the same
  engine tools as the text caddie.
- Call UI: the avatar, live transcript, mute / end / show-hole controls.
- Avatar states — idle, listening, thinking, speaking — plus turning to look at whatever is
  being discussed.
- Push-to-talk kept as the fallback path (F-09).
- Measure and log end-to-end latency; a call only feels like a call under ~1 second.
- **Done when:** you can walk a hole with headphones in, talk to the caddie, interrupt it,
  and have it answer with real numbers from the engine.

### M8 — Lie photo analysis (F-11)
- Presigned upload, `assess_lie` tool, lie modifier mapping, recomputed recommendation.
- **Done when:** photographing a bad lie visibly changes the recommendation and the caddie
  explains why.

### M9 — Post-round review and practice (F-12, F-13, F-14)
- Strokes gained by category from the baseline table.
- AI round summary and practice plan (Haiku).
- Today's form weighting in the player model.
- **Done when:** finishing a round produces a useful summary and practice plan.

### M10+ — Stretch (P2)
- Risk mode and heatmap view (F-15, F-16) if not already done.
- Wake word (F-18).
- Auto shot detection (F-19), voice shot logging (F-21).
- Range swing analysis (F-20), watch app (F-22), green reading (F-23), personalities (F-24).

---

## 15. Testing strategy

- **Engine:** unit tests for projection, lie classification, baseline interpolation,
  penalty handling; property tests (e.g. adding a hazard never *improves* the expected
  score of an aim point that sends shots into it); synthetic-hole scenario tests.
- **Player model:** recover known distributions from synthetic data.
- **API:** integration tests against a deployed dev stack.
- **Caddie:** scripted eval set of situations with expected behaviors (correct tool use,
  no invented numbers, reply length). Run it whenever the prompt or model changes.
- **Field testing:** play real rounds; keep notes on bad recommendations and turn them
  into test cases.

---

## 16. Risks, constraints, and open questions

- **GPS accuracy:** phones are typically accurate to a few meters; fine for strategy, not
  for putting.
- **OSM coverage:** varies by course. Mitigation: trace missing courses in the OSM editor.
- **Cold start on data:** few shots early on. Mitigation: handicap-based priors.
- **Wind data:** Open-Meteo gives area-level wind, not what's happening on the tee. Allow
  the player to override ("it's gusting into us").
- **Reception:** cache the plan; voice needs a connection, so degrade gracefully to the
  cached plan when offline.
- **Battery:** GPS + mic + screen. Keep polling intervals sensible.
- **Rules of Golf:** AI advice during a competition round isn't permitted (distance
  measuring devices generally are). Intended for casual rounds and practice. Consider a
  "tournament mode" that disables the caddie and leaves distances only.
- **Open questions:**
  - How should the player indicate their intended target for better lateral stats?
  - Best source and scaling approach for an amateur strokes-gained baseline?
  - Earbud button support for push-to-talk on iOS vs. Android?

---

## 17. Notes for Claude Code

- Work **one milestone at a time**, in order. Break each milestone into small tasks,
  implement, and make tests pass before moving on.
- Keep the engine a pure library; AWS code wraps it, never the reverse.
- All tunable numbers (heuristics, model IDs, simulation sizes) live in `data/config/`.
- **Ask before creating or modifying AWS resources that cost money.** Always `cdk diff`
  before `cdk deploy`.
- Never commit secrets. Use environment variables and AWS-managed credentials.
- **This document is directional, not a rigid spec.** Where something is ambiguous or has
  no clearly correct answer, pick a defensible default, make the values configurable, log
  it in `DECISIONS.md`, and keep building. Breadth of working, demoable features beats
  narrow correctness — data quality, calibration, and domain precision are deliberate
  later refinement passes, not prerequisites.
