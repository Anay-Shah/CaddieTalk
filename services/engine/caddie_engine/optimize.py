"""Searching clubs and aim points for the lowest expected score.

This is where strategy comes from. The simulator can tell you what happens if you hit a
7 iron at the pin; the optimizer tries every sensible club against a fan of aim points and
reports which combination scores best. Aiming away from the pin falls out of the numbers
rather than being a rule anyone wrote down.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .conditions import CALM, Conditions
from .config import engine_config, to_yards
from .geometry import HoleModel
from .player_model import ClubStats, default_bag
from .simulate import ShotOutcome, bearing_deg, simulate_shot

HAZARD_LIES = ("water", "sand", "recovery")


@dataclass
class Candidate:
    """One club aimed at one point, and how it turned out."""

    club: str
    aim_xy: tuple[float, float]
    aim_offset_m: float
    """Sideways offset of the aim point from the straight line to the target.
    Negative is left."""
    expected_score: float
    outcome: ShotOutcome = field(repr=False)

    @property
    def hazard_probabilities(self) -> dict[str, float]:
        probabilities = self.outcome.lie_probabilities()
        return {lie: probabilities.get(lie, 0.0) for lie in HAZARD_LIES}

    def describe_aim(self) -> str:
        offset_yds = to_yards(abs(self.aim_offset_m))
        if offset_yds < 3:
            return "straight at it"
        return f"{offset_yds:.0f} yds {'right' if self.aim_offset_m > 0 else 'left'}"


@dataclass
class Recommendation:
    best: Candidate
    alternatives: list[Candidate]
    target_xy: tuple[float, float]

    @property
    def club(self) -> str:
        return self.best.club

    @property
    def expected_score(self) -> float:
        return self.best.expected_score

    def summary(self) -> str:
        lines = [
            f"{self.best.club}, aim {self.best.describe_aim()} "
            f"(expected {self.best.expected_score:.2f})"
        ]
        risky = {k: v for k, v in self.best.hazard_probabilities.items() if v >= 0.02}
        if risky:
            joined = ", ".join(f"{k} {v:.0%}" for k, v in sorted(risky.items()))
            lines.append(f"  risk: {joined}")
        for alternative in self.alternatives[:3]:
            lines.append(
                f"  alt: {alternative.club} {alternative.describe_aim()} "
                f"({alternative.expected_score:.2f})"
            )
        return "\n".join(lines)


def aim_points(
    start_xy: tuple[float, float],
    target_xy: tuple[float, float],
    aim_distance_m: float,
) -> list[tuple[tuple[float, float], float]]:
    """A fan of aim points across a cone centred on the target.

    Returns (point, sideways offset) pairs. The offsets are what make the recommendation
    explainable — "aim 8 yards left" is actionable in a way that a raw coordinate is not.
    """
    config = engine_config()["simulation"]
    spacing = config["aim_grid_spacing_m"]
    half_width = math.radians(config["aim_cone_half_width_deg"])

    bearing = math.radians(bearing_deg(start_xy, target_xy))
    aim_distance_m = max(aim_distance_m, 1.0)

    # Convert the spacing (a distance on the ground) into an angular step at this range.
    angle_step = math.atan2(spacing, aim_distance_m)
    steps = int(half_width / angle_step) if angle_step > 0 else 0

    points = []
    for index in range(-steps, steps + 1):
        angle = bearing + index * angle_step
        point = (
            start_xy[0] + aim_distance_m * math.sin(angle),
            start_xy[1] + aim_distance_m * math.cos(angle),
        )
        points.append((point, aim_distance_m * math.sin(index * angle_step)))
    return points


def plausible_clubs(
    bag: dict[str, ClubStats],
    distance_to_target_m: float,
    lie: str = "fairway",
) -> list[ClubStats]:
    """Clubs worth considering for a shot of this length.

    Anything that cannot reach half the distance is a layup nobody would choose, and
    anything more than ~25% past the target only makes sense as a deliberate lay-up to a
    number, which is handled by the aim search rather than by club choice.
    """
    lower, upper = 0.5 * distance_to_target_m, 1.35 * distance_to_target_m
    candidates = [club for club in bag.values() if lower <= club.mean_m <= upper]
    if candidates:
        return candidates
    # Out of range in both directions — fall back to the closest club by distance so the
    # engine always returns something rather than refusing to answer.
    return [min(bag.values(), key=lambda c: abs(c.mean_m - distance_to_target_m))]


def recommend(
    hole: HoleModel,
    start_xy: tuple[float, float],
    bag: dict[str, ClubStats] | None = None,
    conditions: Conditions = CALM,
    lie: str = "fairway",
    handicap: float = 15.0,
    target_xy: tuple[float, float] | None = None,
    samples: int | None = None,
    seed: int | None = None,
) -> Recommendation:
    """Best club and aim point from this position, by expected score."""
    bag = bag if bag is not None else default_bag(handicap)
    target_xy = target_xy or hole.pin_xy
    rng = np.random.default_rng(seed)

    distance_to_target = math.dist(start_xy, target_xy)
    candidates: list[Candidate] = []

    for club in plausible_clubs(bag, distance_to_target, lie):
        # Aim at the club's own range: aiming a wedge at a target 200 m away describes a
        # direction, not a destination, and the offset would be meaningless.
        aim_distance = (
            min(club.mean_m, distance_to_target) if distance_to_target > 0 else club.mean_m
        )

        for point, offset in aim_points(start_xy, target_xy, aim_distance):
            outcome = simulate_shot(
                hole=hole,
                start_xy=start_xy,
                aim_xy=point,
                club=club,
                conditions=conditions,
                lie=lie,
                handicap=handicap,
                samples=samples,
                rng=rng,
            )
            candidates.append(
                Candidate(
                    club=club.name,
                    aim_xy=point,
                    aim_offset_m=offset,
                    expected_score=outcome.expected_score,
                    outcome=outcome,
                )
            )

    candidates.sort(key=lambda c: c.expected_score)
    best = candidates[0]

    # Alternatives are only interesting if they are a different club; ten variations on
    # the winning club's aim is noise, not a choice.
    alternatives = []
    seen = {best.club}
    for candidate in candidates:
        if candidate.club not in seen:
            alternatives.append(candidate)
            seen.add(candidate.club)

    return Recommendation(best=best, alternatives=alternatives, target_xy=target_xy)
