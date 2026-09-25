"""How far each club goes, and how much it scatters.

Two halves. `default_bag` produces generic numbers from a handicap, used before a player
has logged anything. `fit_bag` replaces them with distributions measured from real shots,
blended against those generic numbers so that early rounds shift the estimate gradually
instead of swinging it wildly.

The decomposition here is the exact inverse of `simulate.sample_landings`: that function
turns (distance along the target line, sideways offset) into a landing point, and
`shot_metrics` turns a landing point back into those two numbers. Keeping them mirrored is
what makes "fit from real shots, then simulate" coherent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import clubs_config, engine_config, to_metres


@dataclass(frozen=True)
class ClubStats:
    """One club's distribution. All distances in metres."""

    name: str
    mean_m: float
    sd_m: float
    lateral_bias_m: float = 0.0
    """Systematic miss. Positive is right of target."""
    lateral_sd_m: float = 0.0
    n_shots: int = 0
    """How many real shots this was fitted from. 0 means it is pure prior."""

    @property
    def is_fitted(self) -> bool:
        return self.n_shots > 0


def handicap_distance_factor(handicap: float, reference_handicap: float) -> float:
    """Scale the reference bag's distances for a different handicap.

    Better players hit it further, but the effect is mild compared with the difference in
    dispersion, so this stays deliberately small: ~1% per stroke of handicap.
    """
    return 1.0 - 0.01 * (handicap - reference_handicap)


def handicap_dispersion_factor(handicap: float, reference_handicap: float) -> float:
    """Scale the reference bag's spread for a different handicap.

    This is where skill actually shows up. A 5-handicap's 7 iron is not much shorter than
    a 20-handicap's, but it is far more predictable, and predictability is what the
    strategy engine optimizes around.
    """
    return max(0.35, 1.0 + 0.025 * (handicap - reference_handicap))


def default_bag(handicap: float = 15.0) -> dict[str, ClubStats]:
    """A plausible set of clubs for a player of this handicap, before any real data."""
    config = clubs_config()
    reference = config["reference_handicap"]
    defaults = config["defaults"]

    distance_factor = handicap_distance_factor(handicap, reference)
    dispersion_factor = handicap_dispersion_factor(handicap, reference)

    bag = {}
    for entry in config["clubs"]:
        mean_m = to_metres(entry["mean_yds"]) * distance_factor
        sd_pct = entry.get("sd_pct", defaults["sd_pct"])
        lateral_sd_pct = entry.get("lateral_sd_pct", defaults["lateral_sd_pct"])
        bias_pct = entry.get("bias_pct", defaults["bias_pct"])

        bag[entry["name"]] = ClubStats(
            name=entry["name"],
            mean_m=mean_m,
            sd_m=mean_m * sd_pct * dispersion_factor,
            lateral_bias_m=mean_m * bias_pct,
            lateral_sd_m=mean_m * lateral_sd_pct * dispersion_factor,
        )
    return bag


# --- fitting from real shots ---------------------------------------------------------


@dataclass(frozen=True)
class Shot:
    """One logged shot.

    `end_xy` comes from where the *next* shot started, which is how the app infers it
    without asking the player to mark the ball twice.

    `target_xy` is where the player was aiming. Without it the sideways miss is
    meaningless — a ball 20 m right of the pin is a good shot if you were aiming 20 m
    right. Early rounds will often lack it, so it is optional and those shots then
    contribute distance only.
    """

    club: str
    start_xy: tuple[float, float]
    end_xy: tuple[float, float]
    target_xy: tuple[float, float] | None = None
    penalty: bool = False
    """Excluded from fitting: a penalty drop is not a swing."""


@dataclass(frozen=True)
class ShotMetrics:
    club: str
    distance_m: float
    """Distance travelled along the target line."""
    lateral_m: float | None
    """Sideways miss, positive to the right. None when the target was not recorded."""


def shot_metrics(shot: Shot) -> ShotMetrics:
    """Split a shot into distance along the target line and sideways miss.

    With no target recorded, distance falls back to straight-line start-to-end, which
    slightly overstates it for a crooked shot but is the best available answer.
    """
    dx = shot.end_xy[0] - shot.start_xy[0]
    dy = shot.end_xy[1] - shot.start_xy[1]

    if shot.target_xy is None:
        return ShotMetrics(shot.club, math.hypot(dx, dy), None)

    tx = shot.target_xy[0] - shot.start_xy[0]
    ty = shot.target_xy[1] - shot.start_xy[1]
    target_distance = math.hypot(tx, ty)
    if target_distance == 0:
        return ShotMetrics(shot.club, math.hypot(dx, dy), None)

    # Unit vector toward the target, and the unit vector 90 degrees to its right.
    ux, uy = tx / target_distance, ty / target_distance
    along = dx * ux + dy * uy
    lateral = dx * uy - dy * ux

    return ShotMetrics(shot.club, along, lateral)


def _blend(prior: float, sample: float | None, prior_weight: float, sample_weight: float) -> float:
    """Weighted average of a prior and a measurement.

    `estimate = (k * prior + n * sample) / (k + n)` — the blend the architecture
    specifies. With no shots it returns the prior; with many it converges on the data.
    """
    if sample is None or sample_weight <= 0:
        return prior
    return (prior_weight * prior + sample_weight * sample) / (prior_weight + sample_weight)


def drop_mishits(distances: list[float], fraction: float | None = None) -> list[float]:
    """Remove duffs and tops, which are a different event from a normal swing."""
    if len(distances) < 3:
        return distances
    if fraction is None:
        fraction = engine_config()["player_model"]["mishit_fraction"]
    threshold = float(np.median(distances)) * fraction
    return [d for d in distances if d >= threshold]


def fit_club(
    prior: ClubStats,
    metrics: list[ShotMetrics],
    prior_pseudo_shots: float | None = None,
) -> ClubStats:
    """Blend this club's logged shots against its prior."""
    config = engine_config()["player_model"]
    if prior_pseudo_shots is None:
        prior_pseudo_shots = config["prior_pseudo_shots"]
    min_for_spread = config["min_shots_for_spread"]

    distances = drop_mishits([m.distance_m for m in metrics])
    laterals = [m.lateral_m for m in metrics if m.lateral_m is not None]

    n_distance = len(distances)
    n_lateral = len(laterals)

    # A standard deviation needs more evidence than a mean does, so it gets its own,
    # stricter gate rather than riding on the mean's sample size.
    spread_weight = n_distance if n_distance >= min_for_spread else 0
    lateral_spread_weight = n_lateral if n_lateral >= min_for_spread else 0

    return ClubStats(
        name=prior.name,
        mean_m=_blend(prior.mean_m, _mean(distances), prior_pseudo_shots, n_distance),
        sd_m=_blend(prior.sd_m, _sd(distances), prior_pseudo_shots, spread_weight),
        lateral_bias_m=_blend(prior.lateral_bias_m, _mean(laterals), prior_pseudo_shots, n_lateral),
        lateral_sd_m=_blend(
            prior.lateral_sd_m, _sd(laterals), prior_pseudo_shots, lateral_spread_weight
        ),
        n_shots=n_distance,
    )


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _sd(values: list[float]) -> float | None:
    return float(np.std(values, ddof=1)) if len(values) >= 2 else None


def fit_bag(
    shots: list[Shot],
    handicap: float = 15.0,
    prior_bag: dict[str, ClubStats] | None = None,
    prior_pseudo_shots: float | None = None,
) -> dict[str, ClubStats]:
    """Fit every club in the bag from logged shots.

    Clubs with no logged shots keep their prior, so the bag is always complete and the
    engine never has to handle a missing club.
    """
    bag = dict(prior_bag if prior_bag is not None else default_bag(handicap))

    by_club: dict[str, list[ShotMetrics]] = {}
    for shot in shots:
        if shot.penalty:
            continue
        by_club.setdefault(shot.club, []).append(shot_metrics(shot))

    for club_name, metrics in by_club.items():
        prior = bag.get(club_name)
        if prior is None:
            # A club not in the reference bag — seed its prior from the shots themselves
            # so a player with an unusual set still gets modelled.
            distances = drop_mishits([m.distance_m for m in metrics])
            seed_mean = _mean(distances) or 0.0
            prior = ClubStats(
                name=club_name,
                mean_m=seed_mean,
                sd_m=seed_mean * 0.05,
                lateral_sd_m=seed_mean * 0.07,
            )
        bag[club_name] = fit_club(prior, metrics, prior_pseudo_shots)

    return bag
