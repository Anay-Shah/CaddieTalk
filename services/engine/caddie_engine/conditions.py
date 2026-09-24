"""Wind and elevation adjustments.

These are crude heuristics, and deliberately so — they live in `data/config/engine.yaml`
precisely because the right values are something you tune by playing, not something to
derive from first principles. A headwind roughly costs you 1% of distance per mph; that
is a rule of thumb caddies actually use, not physics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import engine_config


@dataclass(frozen=True)
class Conditions:
    """Wind is reported the way forecasts report it: the direction it blows TOWARD."""

    wind_mph: float = 0.0
    wind_bearing_deg: float = 0.0
    elevation_change_m: float = 0.0
    """Positive when the target is above the ball."""

    @property
    def is_calm(self) -> bool:
        return self.wind_mph == 0.0 and self.elevation_change_m == 0.0


CALM = Conditions()
"""No wind, flat ground. A shared singleton so it can be used as a default argument."""


def wind_components(conditions: Conditions, shot_bearing_deg: float) -> tuple[float, float]:
    """Split wind into (headwind, crosswind) in mph relative to the shot.

    Headwind is positive when blowing back at the player; crosswind is positive when
    pushing the ball right.
    """
    relative = math.radians(conditions.wind_bearing_deg - shot_bearing_deg)
    # Headwind is negated because a wind blowing toward the shot's own bearing is a
    # tailwind. Crosswind is not: a wind blowing toward the shot's right pushes the ball
    # right, so the sign carries through directly.
    headwind = -conditions.wind_mph * math.cos(relative)
    crosswind = conditions.wind_mph * math.sin(relative)
    return headwind, crosswind


def plays_like_factor(conditions: Conditions, shot_bearing_deg: float) -> float:
    """Multiplier on a club's distance for the shot to cover the same ground.

    A factor above 1.0 means the shot plays longer than the number on the sprinkler head.
    """
    config = engine_config()["conditions"]
    headwind, _ = wind_components(conditions, shot_bearing_deg)

    if headwind >= 0:
        wind_pct = headwind * config["headwind_pct_per_mph"]
    else:
        wind_pct = -headwind * config["tailwind_pct_per_mph"]

    return 1.0 + wind_pct / 100.0


def elevation_penalty_m(conditions: Conditions) -> float:
    """Extra distance the shot must cover because the target is uphill (or less, downhill)."""
    config = engine_config()["conditions"]
    return conditions.elevation_change_m * config["elevation_yds_per_yd"]


def crosswind_drift_m(conditions: Conditions, shot_bearing_deg: float, distance_m: float) -> float:
    """Sideways push from crosswind, positive to the right. Scales with shot length."""
    config = engine_config()["conditions"]
    _, crosswind = wind_components(conditions, shot_bearing_deg)
    return crosswind * config["crosswind_drift_per_mph"] * distance_m


def plays_like_distance_m(
    actual_distance_m: float,
    conditions: Conditions,
    shot_bearing_deg: float,
) -> float:
    """What a given distance 'plays like' — the number the caddie should quote."""
    return actual_distance_m * plays_like_factor(conditions, shot_bearing_deg) + (
        elevation_penalty_m(conditions)
    )
