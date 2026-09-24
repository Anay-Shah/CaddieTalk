"""Tests for the strokes-to-hole-out lookup.

These check the table's *shape* rather than specific values, because the values are a
tunable approximation (DECISIONS.md D-006). The shape is what the engine's logic depends
on: closer is better, bad lies cost more, and worse players take more shots.
"""

from __future__ import annotations

import numpy as np
import pytest
from caddie_engine.baseline import LIES, handicap_scale, strokes_to_hole_out


@pytest.mark.parametrize("lie", ["fairway", "rough", "sand", "recovery", "green"])
def test_strokes_increase_with_distance(lie):
    distances = np.linspace(5, 180, 40)
    strokes = strokes_to_hole_out(lie, distances)
    assert np.all(np.diff(strokes) >= 0), f"{lie} baseline is not monotonic"


@pytest.mark.parametrize("distance", [50.0, 100.0, 150.0])
def test_bad_lies_cost_more_than_fairway(distance):
    fairway = strokes_to_hole_out("fairway", distance)
    assert strokes_to_hole_out("rough", distance) > fairway
    assert strokes_to_hole_out("sand", distance) > fairway
    assert strokes_to_hole_out("recovery", distance) > strokes_to_hole_out("sand", distance)


def test_higher_handicap_takes_more_strokes():
    scratch = strokes_to_hole_out("fairway", 137.0, handicap=0)
    amateur = strokes_to_hole_out("fairway", 137.0, handicap=20)
    assert amateur > scratch


def test_handicap_scale_is_neutral_for_scratch():
    assert handicap_scale(0) == pytest.approx(1.0)


def test_accepts_arrays():
    result = strokes_to_hole_out("fairway", np.array([50.0, 100.0, 150.0]))
    assert result.shape == (3,)


def test_interpolates_between_table_rows():
    low = strokes_to_hole_out("fairway", 91.4)
    high = strokes_to_hole_out("fairway", 109.7)
    middle = strokes_to_hole_out("fairway", 100.0)
    assert low < middle < high


def test_clamps_beyond_table_range():
    """A 400 m shot is simply the hardest case in the table, not an error."""
    longest = strokes_to_hole_out("fairway", 237.7)
    assert strokes_to_hole_out("fairway", 400.0) == pytest.approx(longest)


def test_holing_out_from_the_lip_costs_about_one_putt():
    assert 0.9 < strokes_to_hole_out("green", 0.3) < 1.2


def test_unknown_lie_is_an_error():
    with pytest.raises(KeyError, match="water"):
        strokes_to_hole_out("water", 50.0)


def test_every_declared_lie_has_data():
    for lie in LIES:
        assert strokes_to_hole_out(lie, 50.0) > 0
