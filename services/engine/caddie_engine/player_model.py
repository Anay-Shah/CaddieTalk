"""How far each club goes, and how much it scatters.

M2 only needs a default bag derived from handicap so the simulator has something to sample
from. M3 replaces `default_bag` with per-club distributions fitted from logged shots,
blended with these values as a prior — the shape of `ClubStats` is what stays fixed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import clubs_config, to_metres


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
