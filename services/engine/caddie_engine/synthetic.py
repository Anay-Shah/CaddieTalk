"""Synthetic holes with known geometry.

Real imported courses are irregular, which makes them good for eyeballing results and bad
for assertions — you can never say exactly what the right answer should be. These builders
produce deliberately plain holes so that behaviour can be reasoned about precisely.

Used by the test suite and by the demo script.
"""

from __future__ import annotations

import numpy as np
from shapely.geometry import Point, Polygon

from .geometry import HoleModel
from .player_model import ClubStats, Shot
from .simulate import sample_landings


def rect(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def straight_hole(**overrides) -> HoleModel:
    """A 300 m par 4: straight fairway, circular green at the end, tee at the origin.

    Suited to testing approach shots. Any field can be overridden to place a hazard, e.g.
    `straight_hole(sand=rect(15, 280, 38, 320))` for a bunker right of the green.
    """
    defaults = dict(
        number=1,
        par=4,
        tee_xy=(0.0, 0.0),
        pin_xy=(0.0, 300.0),
        fairway=rect(-25, 0, 25, 285),
        green=Point(0, 300).buffer(15),
    )
    defaults.update(overrides)
    return HoleModel(**defaults)


def logged_shots(
    club: ClubStats,
    count: int,
    start_xy: tuple[float, float] = (0.0, 0.0),
    target_xy: tuple[float, float] | None = None,
    rng: np.random.Generator | None = None,
) -> list[Shot]:
    """Generate shots that a player with these club stats would plausibly have hit.

    Built on the same sampler the engine uses to simulate, so fitting these back should
    return roughly the stats they came from. That round trip is the main check that the
    player model and the simulator agree on what a shot is.
    """
    rng = rng or np.random.default_rng(0)
    target_xy = target_xy or (start_xy[0], start_xy[1] + club.mean_m)

    landings = sample_landings(start_xy, target_xy, club, samples=count, rng=rng)
    return [
        Shot(
            club=club.name,
            start_xy=start_xy,
            end_xy=(float(x), float(y)),
            target_xy=target_xy,
        )
        for x, y in landings
    ]


def driving_hole(**overrides) -> HoleModel:
    """A 380 m par 4 for testing tee shots.

    The fairway starts 60 m out, so a tee shot can miss it. This is the hole shape where
    hazards genuinely change strategy: a fairway bunker leaves a long second shot from
    sand, which is far more costly than a greenside bunker leaving a 20 m splash-out.
    """
    defaults = dict(
        number=1,
        par=4,
        tee_xy=(0.0, 0.0),
        pin_xy=(0.0, 380.0),
        fairway=rect(-25, 60, 25, 340),
        green=Point(0, 380).buffer(15),
    )
    defaults.update(overrides)
    return HoleModel(**defaults)
