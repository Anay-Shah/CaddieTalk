"""The CaddieTalk API.

Runs locally during development (`make serve`) so the mobile app has something to talk to
long before any AWS exists. M4 wraps this same app for Lambda rather than rewriting it, so
nothing here is throwaway.

Reads courses straight off disk for now; M4 swaps that for S3 and DynamoDB behind the same
endpoints.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from caddie_engine.conditions import Conditions
from caddie_engine.config import find_data_dir, to_metres, to_yards
from caddie_engine.geometry import hole_model_from_dict
from caddie_engine.optimize import recommend
from caddie_engine.player_model import ClubStats, default_bag
from course_import.project import Projector
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="CaddieTalk API", version="0.1.0")

# The Expo dev client runs on a different origin on the local network.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def courses_dir() -> Path:
    return find_data_dir() / "courses"


@lru_cache(maxsize=8)
def load_course(course_id: str) -> dict:
    path = courses_dir() / course_id / "course.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Course {course_id!r} has not been imported")
    return json.loads(path.read_text())


@lru_cache(maxsize=8)
def load_geojson(course_id: str) -> dict:
    path = courses_dir() / course_id / "course.geojson"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Course {course_id!r} has no geojson")
    return json.loads(path.read_text())


@lru_cache(maxsize=8)
def projector_for(course_id: str) -> Projector:
    """Converts GPS lat/lon into the course's projected metres.

    The phone reports lat/lon; the engine works in metres. Doing the conversion here rather
    than in the app keeps a single source of truth for the projection — pyproj, the same
    library that produced the geometry in the first place.
    """
    return Projector(load_course(course_id)["crs"])


def to_course_xy(course_id: str, lat: float, lon: float) -> tuple[float, float]:
    return projector_for(course_id).to_xy(lon, lat)


class CourseSummary(BaseModel):
    course_id: str
    name: str
    holes: int


class RecommendRequest(BaseModel):
    course_id: str
    hole: int
    start: tuple[float, float] | None = Field(
        default=None,
        description="Projected [x, y] position. Defaults to the tee.",
    )
    start_latlon: tuple[float, float] | None = Field(
        default=None,
        description="Where the player actually is, as [lat, lon] from the phone's GPS. "
        "Takes precedence over `start` and `from_yards`.",
    )
    from_yards: float | None = Field(
        default=None,
        description="Alternative to `start`: stand this far from the pin down the hole line.",
    )
    lie: str = "fairway"
    handicap: float = 15.0
    wind_mph: float = 0.0
    wind_bearing_deg: float = 0.0
    elevation_yards: float = 0.0
    samples: int | None = None
    seed: int | None = None


class HazardRisk(BaseModel):
    lie: str
    probability: float


class CandidateOut(BaseModel):
    club: str
    aim_offset_yards: float
    aim_description: str
    expected_score: float


class RecommendResponse(BaseModel):
    hole: int
    par: int | None
    to_pin_yards: float
    plays_like_yards: float
    lie: str
    best: CandidateOut
    alternatives: list[CandidateOut]
    hazards: list[HazardRisk]
    aim_xy: tuple[float, float]
    pin_xy: tuple[float, float]
    start_xy: tuple[float, float]
    landing_sample: list[tuple[float, float]]
    """A thinned sample of simulated landings, for drawing the dispersion cone."""


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/courses", response_model=list[CourseSummary])
def list_courses() -> list[CourseSummary]:
    root = courses_dir()
    if not root.is_dir():
        return []

    summaries = []
    for path in sorted(root.glob("*/course.json")):
        data = json.loads(path.read_text())
        summaries.append(
            CourseSummary(
                course_id=data["course_id"],
                name=data["name"],
                holes=len(data["holes"]),
            )
        )
    return summaries


@app.get("/courses/{course_id}")
def get_course(course_id: str) -> dict:
    return load_course(course_id)


@app.get("/courses/{course_id}/geojson")
def get_course_geojson(course_id: str) -> dict:
    """WGS84 geometry for drawing overlays on the map."""
    return load_geojson(course_id)


def _start_position(hole, request: RecommendRequest) -> tuple[tuple[float, float], str]:
    if request.start_latlon is not None:
        lat, lon = request.start_latlon
        return to_course_xy(request.course_id, lat, lon), request.lie
    if request.start is not None:
        return tuple(request.start), request.lie
    if request.from_yards is None:
        return hole.tee_xy, "tee"

    metres = to_metres(request.from_yards)
    dx = hole.pin_xy[0] - hole.tee_xy[0]
    dy = hole.pin_xy[1] - hole.tee_xy[1]
    total = math.hypot(dx, dy)
    if metres >= total:
        return hole.tee_xy, "tee"

    fraction = (total - metres) / total
    return (hole.tee_xy[0] + dx * fraction, hole.tee_xy[1] + dy * fraction), request.lie


def _bag(handicap: float) -> dict[str, ClubStats]:
    """The player's clubs.

    Still the generic bag: M4 fetches the fitted per-club stats from DynamoDB instead, at
    which point the advice becomes personal.
    """
    return default_bag(handicap)


class LocateResponse(BaseModel):
    hole: int
    par: int | None
    """Distances to the green, the way a yardage book gives them."""
    to_front_yards: float
    to_middle_yards: float
    to_back_yards: float
    on_course: bool
    """False when the player is far from every hole — a stale fix, or not at the course."""


# Beyond this from every hole, assume the fix is wrong rather than that the player is
# standing in a car park 2 km away holding a 7 iron.
ON_COURSE_LIMIT_M = 400.0


@app.get("/courses/{course_id}/locate", response_model=LocateResponse)
def locate(course_id: str, lat: float, lon: float) -> LocateResponse:
    """Which hole the player is on, and their distances to the green.

    Inferred from position rather than asked for, because a player walking down a fairway
    should not have to tell the app where they are.
    """
    course = load_course(course_id)
    x, y = to_course_xy(course_id, lat, lon)

    best: tuple[float, dict] | None = None
    for entry in course["holes"]:
        line = entry.get("hole_line") or []
        if not line:
            continue
        # Distance to the hole's centre-line, approximated by its vertices. Hole lines have
        # few points, so this is both cheap and accurate enough to pick the right hole.
        distance = min(math.dist((x, y), (px, py)) for px, py in line)
        if best is None or distance < best[0]:
            best = (distance, entry)

    if best is None:
        raise HTTPException(status_code=404, detail="Course has no hole lines")

    distance_to_hole, entry = best
    hole = hole_model_from_dict(entry)

    green = entry.get("green") or []
    if green:
        distances = [math.dist((x, y), (gx, gy)) for gx, gy in green]
        front, back = min(distances), max(distances)
    else:
        front = back = math.dist((x, y), hole.pin_xy)

    return LocateResponse(
        hole=hole.number,
        par=hole.par,
        to_front_yards=to_yards(front),
        to_middle_yards=to_yards(math.dist((x, y), hole.pin_xy)),
        to_back_yards=to_yards(back),
        on_course=distance_to_hole <= ON_COURSE_LIMIT_M,
    )


@app.post("/engine/recommend", response_model=RecommendResponse)
def engine_recommend(request: RecommendRequest) -> RecommendResponse:
    course = load_course(request.course_id)
    entry = next((h for h in course["holes"] if h["number"] == request.hole), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Hole {request.hole} not found")

    hole = hole_model_from_dict(entry)
    start_xy, lie = _start_position(hole, request)

    conditions = Conditions(
        wind_mph=request.wind_mph,
        wind_bearing_deg=request.wind_bearing_deg,
        elevation_change_m=to_metres(request.elevation_yards),
    )

    result = recommend(
        hole,
        start_xy=start_xy,
        bag=_bag(request.handicap),
        conditions=conditions,
        lie=lie,
        handicap=request.handicap,
        samples=request.samples,
        seed=request.seed,
    )

    def as_candidate(candidate) -> CandidateOut:
        return CandidateOut(
            club=candidate.club,
            aim_offset_yards=to_yards(candidate.aim_offset_m),
            aim_description=candidate.describe_aim(),
            expected_score=candidate.expected_score,
        )

    to_pin_m = math.dist(start_xy, hole.pin_xy)
    # Below 1% is noise: it rounds to "0%" on screen and tells the player nothing they
    # would act on. Reporting it would only crowd out the risks that matter.
    hazards = [
        HazardRisk(lie=lie_name, probability=probability)
        for lie_name, probability in sorted(result.best.hazard_probabilities.items())
        if probability >= 0.01
    ]

    # The app draws a cone, not a scatter plot, so a few hundred points is plenty and keeps
    # the payload small enough for a weak on-course connection.
    landings = result.best.outcome.landing_xy[::10][:400]

    from caddie_engine.conditions import plays_like_distance_m
    from caddie_engine.simulate import bearing_deg

    plays_like = plays_like_distance_m(to_pin_m, conditions, bearing_deg(start_xy, hole.pin_xy))

    return RecommendResponse(
        hole=hole.number,
        par=hole.par,
        to_pin_yards=to_yards(to_pin_m),
        plays_like_yards=to_yards(plays_like),
        lie=lie,
        best=as_candidate(result.best),
        alternatives=[as_candidate(c) for c in result.alternatives[:3]],
        hazards=hazards,
        aim_xy=result.best.aim_xy,
        pin_xy=hole.pin_xy,
        start_xy=start_xy,
        landing_sample=[(float(x), float(y)) for x, y in landings],
    )
