"""Expected strokes to hole out, by lie and distance.

This is the engine's scoring function. Every simulated shot ends somewhere, and this
converts "you are 32 m from the pin in a bunker" into "that costs about 2.8 more strokes".
Without it there is no way to compare one aim point against another.

The table itself is an approximation — see the header of the CSV and DECISIONS.md (D-006).
"""

from __future__ import annotations

import csv
import functools

import numpy as np

from .config import engine_config, find_data_dir

LIES = ("green", "tee", "fairway", "rough", "sand", "recovery")

# Water and out-of-bounds are not lies you play from; they are penalties resolved by the
# simulator before it asks this module for a score.
PENALTY_OUTCOMES = ("water", "ob")


@functools.lru_cache(maxsize=1)
def _table() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Per-lie arrays of (distances, strokes), sorted by distance."""
    path = find_data_dir() / "baselines" / "strokes_to_hole_out.csv"
    rows: dict[str, list[tuple[float, float]]] = {}

    with path.open() as handle:
        reader = csv.DictReader(line for line in handle if not line.startswith("#"))
        for row in reader:
            rows.setdefault(row["lie"], []).append(
                (float(row["distance_m"]), float(row["strokes"]))
            )

    table = {}
    for lie, pairs in rows.items():
        pairs.sort()
        table[lie] = (
            np.array([d for d, _ in pairs]),
            np.array([s for _, s in pairs]),
        )
    return table


def handicap_scale(handicap: float) -> float:
    """How much worse than the reference player this golfer is, as a multiplier."""
    per_stroke = engine_config()["baseline"]["per_handicap_stroke"]
    return 1.0 + per_stroke * handicap


def strokes_to_hole_out(
    lie: str,
    distance_m: np.ndarray | float,
    handicap: float = 0.0,
) -> np.ndarray:
    """Expected strokes from this lie at this distance.

    Vectorized: `distance_m` may be a single value or an array of thousands, because the
    simulator scores every sampled landing point at once.
    """
    if lie not in _table():
        raise KeyError(f"No baseline data for lie {lie!r}. Known lies: {sorted(_table())}")

    distances, strokes = _table()[lie]
    # np.interp clamps to the end values outside the table's range, which is the behaviour
    # we want: a 300 m shot is simply the hardest case we have data for.
    interpolated = np.interp(np.asarray(distance_m, dtype=float), distances, strokes)
    return interpolated * handicap_scale(handicap)
