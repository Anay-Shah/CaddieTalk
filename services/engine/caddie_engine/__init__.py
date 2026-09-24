"""CaddieTalk strategy engine.

A pure Python library: Monte Carlo shot simulation, lie classification, and aim-point
optimization. This package must never import boto3 or any other AWS dependency, so that it
stays runnable from notebooks and tests as well as from Lambda.

Typical use:

    from caddie_engine import HoleModel, default_bag, recommend

    result = recommend(hole, start_xy=(x, y), handicap=14)
    print(result.summary())
"""

from .baseline import strokes_to_hole_out
from .conditions import Conditions, plays_like_distance_m
from .geometry import HoleModel, hole_model_from_course
from .optimize import Candidate, Recommendation, recommend
from .player_model import ClubStats, default_bag
from .simulate import ShotOutcome, sample_landings, simulate_shot

__version__ = "0.2.0"

__all__ = [
    "Candidate",
    "ClubStats",
    "Conditions",
    "HoleModel",
    "Recommendation",
    "ShotOutcome",
    "default_bag",
    "hole_model_from_course",
    "plays_like_distance_m",
    "recommend",
    "sample_landings",
    "simulate_shot",
    "strokes_to_hole_out",
]
