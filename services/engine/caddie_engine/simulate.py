"""Monte Carlo shot simulation.

The core idea: rather than asking "how far does a 7 iron go", sample thousands of plausible
7 irons from the player's own distribution, land them on the real hole, and count what
happens. Everything here is vectorized — one NumPy operation over the whole sample rather
than a Python loop — because the optimizer runs this for every club against every aim
point.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .baseline import strokes_to_hole_out
from .conditions import (
    CALM,
    Conditions,
    crosswind_drift_m,
    elevation_penalty_m,
    plays_like_factor,
)
from .config import engine_config
from .geometry import HoleModel
from .player_model import ClubStats


@dataclass(frozen=True)
class ShotOutcome:
    """What happened to a batch of simulated shots."""

    landing_xy: np.ndarray
    """(N, 2) array of landing points."""
    lies: np.ndarray
    """(N,) array of lie names, including 'water'."""
    distance_to_pin_m: np.ndarray
    strokes: np.ndarray
    """(N,) total expected strokes to hole out from here, including this shot."""

    @property
    def expected_score(self) -> float:
        return float(self.strokes.mean())

    def probability_of(self, lie: str) -> float:
        return float((self.lies == lie).mean())

    def lie_probabilities(self) -> dict[str, float]:
        values, counts = np.unique(self.lies, return_counts=True)
        return {str(v): float(c / len(self.lies)) for v, c in zip(values, counts, strict=True)}


def bearing_deg(start: tuple[float, float], target: tuple[float, float]) -> float:
    """Compass-style bearing from start to target, in degrees, 0 = +y (north)."""
    return math.degrees(math.atan2(target[0] - start[0], target[1] - start[1]))


def lie_modifiers(lie: str) -> tuple[float, float]:
    """(distance multiplier, dispersion multiplier) for playing from this lie."""
    modifiers = engine_config()["lie_modifiers"]
    entry = modifiers.get(lie, modifiers["fairway"])
    return entry["distance_mult"], entry["lateral_mult"]


def sample_landings(
    start_xy: tuple[float, float],
    aim_xy: tuple[float, float],
    club: ClubStats,
    conditions: Conditions = CALM,
    lie: str = "fairway",
    samples: int | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Draw `samples` plausible landing points for this club aimed at this point.

    Returns an (N, 2) array. The aim point sets direction only — how far the ball actually
    travels comes from the club's distribution, not from the distance to the aim point.
    That is deliberate: aiming at a target 150 m away with a club that averages 135 m
    should produce shots that come up short, which is exactly the mistake the engine
    exists to catch.
    """
    rng = rng or np.random.default_rng()
    samples = samples or engine_config()["simulation"]["samples_per_candidate"]

    bearing = bearing_deg(start_xy, aim_xy)
    distance_mult, dispersion_mult = lie_modifiers(lie)

    # Wind and elevation change how far the shot must carry, which is equivalent to
    # scaling how far the club actually goes.
    plays_like = plays_like_factor(conditions, bearing)
    effective_mean = club.mean_m * distance_mult / plays_like
    effective_mean -= elevation_penalty_m(conditions)
    effective_sd = club.sd_m * distance_mult

    distances = rng.normal(effective_mean, max(effective_sd, 1e-6), samples)
    lateral = rng.normal(
        club.lateral_bias_m,
        max(club.lateral_sd_m * dispersion_mult, 1e-6),
        samples,
    )
    lateral = lateral + crosswind_drift_m(conditions, bearing, float(effective_mean))

    # Rotate from (along, across) into map coordinates.
    heading = math.radians(bearing)
    sin_h, cos_h = math.sin(heading), math.cos(heading)
    x = start_xy[0] + distances * sin_h + lateral * cos_h
    y = start_xy[1] + distances * cos_h - lateral * sin_h

    return np.column_stack([x, y])


def score_landings(
    hole: HoleModel,
    landing_xy: np.ndarray,
    handicap: float = 15.0,
    strokes_taken: float = 1.0,
) -> ShotOutcome:
    """Turn landing points into expected total strokes.

    Each ball costs the stroke just played, plus what it will take to hole out from where
    it finished. Water adds a penalty stroke and is then played from rough near the hazard,
    which approximates a drop.
    """
    x, y = landing_xy[:, 0], landing_xy[:, 1]
    lies = hole.classify(x, y)
    distances = hole.distance_to_pin(x, y)

    penalties = engine_config()["penalties"]
    remaining = np.zeros(len(lies))

    for lie in np.unique(lies):
        mask = lies == lie
        if lie == "water":
            # Approximation: take the penalty, then play from rough at roughly the same
            # distance. A precise drop point would walk back along the line of flight to
            # the hazard margin; that refinement is not worth the complexity yet.
            remaining[mask] = penalties["water_strokes"] + strokes_to_hole_out(
                "rough", distances[mask], handicap
            )
        else:
            remaining[mask] = strokes_to_hole_out(str(lie), distances[mask], handicap)

    return ShotOutcome(
        landing_xy=landing_xy,
        lies=lies,
        distance_to_pin_m=distances,
        strokes=strokes_taken + remaining,
    )


def simulate_shot(
    hole: HoleModel,
    start_xy: tuple[float, float],
    aim_xy: tuple[float, float],
    club: ClubStats,
    conditions: Conditions = CALM,
    lie: str = "fairway",
    handicap: float = 15.0,
    samples: int | None = None,
    rng: np.random.Generator | None = None,
) -> ShotOutcome:
    """Sample and score one club/aim combination."""
    landings = sample_landings(start_xy, aim_xy, club, conditions, lie, samples, rng)
    return score_landings(hole, landings, handicap)
