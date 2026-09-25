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
    hazards = [
        HazardRisk(lie=lie_name, probability=probability)
        for lie_name, probability in sorted(result.best.hazard_probabilities.items())
        if probability > 0
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
