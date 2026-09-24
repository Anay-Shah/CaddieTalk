"""Shared fixtures for engine tests.

The synthetic hole builders themselves live in `caddie_engine.synthetic` so that the demo
script can use them too.
"""

from __future__ import annotations

import numpy as np
import pytest
from caddie_engine.geometry import HoleModel
from caddie_engine.player_model import ClubStats
from caddie_engine.synthetic import driving_hole, rect, straight_hole

FAIRWAY_BUNKER_RIGHT = rect(12, 165, 45, 215)
"""Right of the fairway, in the driving-zone of a ~190 m tee shot."""


@pytest.fixture
def hole() -> HoleModel:
    return straight_hole()


@pytest.fixture
def hole_with_greenside_bunker() -> HoleModel:
    """Approach hole with a bunker just off the right edge of the green."""
    return straight_hole(sand=rect(15, 280, 38, 320))


@pytest.fixture
def driving_hole_clean() -> HoleModel:
    return driving_hole()


@pytest.fixture
def driving_hole_bunker_right() -> HoleModel:
    return driving_hole(sand=FAIRWAY_BUNKER_RIGHT)


@pytest.fixture
def driver() -> ClubStats:
    """A ~190 m driver for a player who leaks it right."""
    return ClubStats(name="Dr", mean_m=192.0, sd_m=10.0, lateral_bias_m=14.0, lateral_sd_m=17.0)


@pytest.fixture
def straight_shooter() -> ClubStats:
    """A club that goes 150 m with no systematic miss."""
    return ClubStats(name="7i", mean_m=150.0, sd_m=7.0, lateral_bias_m=0.0, lateral_sd_m=10.0)


@pytest.fixture
def pushes_it_right() -> ClubStats:
    """The same club for a player who reliably misses right."""
    return ClubStats(name="7i", mean_m=150.0, sd_m=7.0, lateral_bias_m=12.0, lateral_sd_m=10.0)


@pytest.fixture
def rng() -> np.random.Generator:
    """Seeded so simulation-based assertions are reproducible."""
    return np.random.default_rng(20260924)
