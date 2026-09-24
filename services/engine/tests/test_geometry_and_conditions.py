from __future__ import annotations

import numpy as np
import pytest
from caddie_engine.conditions import (
    Conditions,
    crosswind_drift_m,
    plays_like_distance_m,
    wind_components,
)
from caddie_engine.geometry import HoleModel
from caddie_engine.synthetic import rect, straight_hole

# --- lie classification -------------------------------------------------------------


def test_points_on_the_fairway_are_fairway(hole):
    lies = hole.classify(np.array([0.0, 10.0]), np.array([100.0, 200.0]))
    assert list(lies) == ["fairway", "fairway"]


def test_points_on_the_green_are_green(hole):
    assert hole.classify(np.array([0.0]), np.array([300.0]))[0] == "green"


def test_unmapped_ground_is_rough(hole):
    """Anything outside a mapped feature is rough — that is the correct default."""
    assert hole.classify(np.array([80.0]), np.array([150.0]))[0] == "rough"


def test_water_outranks_every_other_surface():
    """A ball in a hazard is a penalty no matter what else is mapped underneath it."""
    hole = straight_hole(water=rect(-25, 0, 25, 285))
    assert hole.classify(np.array([0.0]), np.array([100.0]))[0] == "water"


def test_greenside_bunker_outranks_the_green():
    """Bunker polygons often overlap the green's edge; sand has to win there."""
    hole = straight_hole(sand=rect(-5, 295, 5, 305))
    assert hole.classify(np.array([0.0]), np.array([300.0]))[0] == "sand"


def test_green_outranks_fairway_on_overlap():
    hole = straight_hole(fairway=rect(-25, 0, 25, 320))
    assert hole.classify(np.array([0.0]), np.array([300.0]))[0] == "green"


def test_classification_handles_large_arrays(hole):
    x = np.random.default_rng(0).uniform(-50, 50, 5000)
    y = np.random.default_rng(1).uniform(0, 320, 5000)
    assert len(hole.classify(x, y)) == 5000


def test_distance_to_pin(hole):
    distance = hole.distance_to_pin(np.array([0.0]), np.array([200.0]))
    assert distance[0] == pytest.approx(100.0)


def test_hole_with_no_features_is_all_rough():
    bare = HoleModel(number=1, par=3, tee_xy=(0, 0), pin_xy=(0, 150))
    assert set(bare.classify(np.array([0.0, 5.0]), np.array([10.0, 150.0]))) == {"rough"}


# --- wind and elevation -------------------------------------------------------------


def test_headwind_makes_the_shot_play_longer():
    """Wind blowing toward the player (bearing 180) when hitting north (bearing 0)."""
    into = Conditions(wind_mph=10, wind_bearing_deg=180)
    assert plays_like_distance_m(150, into, shot_bearing_deg=0) > 150


def test_tailwind_makes_the_shot_play_shorter():
    behind = Conditions(wind_mph=10, wind_bearing_deg=0)
    assert plays_like_distance_m(150, behind, shot_bearing_deg=0) < 150


def test_tailwind_helps_less_than_headwind_hurts():
    """A real asymmetry golfers rely on, and one the config encodes deliberately."""
    into = plays_like_distance_m(150, Conditions(wind_mph=10, wind_bearing_deg=180), 0)
    behind = plays_like_distance_m(150, Conditions(wind_mph=10, wind_bearing_deg=0), 0)
    assert (into - 150) > (150 - behind)


def test_uphill_plays_longer():
    uphill = Conditions(elevation_change_m=10)
    assert plays_like_distance_m(150, uphill, shot_bearing_deg=0) > 150


def test_downhill_plays_shorter():
    downhill = Conditions(elevation_change_m=-10)
    assert plays_like_distance_m(150, downhill, shot_bearing_deg=0) < 150


def test_calm_conditions_change_nothing():
    assert plays_like_distance_m(150, Conditions(), shot_bearing_deg=0) == pytest.approx(150)


def test_crosswind_from_the_left_pushes_the_ball_right():
    """Wind blowing toward bearing 90 (eastward) while hitting north."""
    from_left = Conditions(wind_mph=10, wind_bearing_deg=90)
    assert crosswind_drift_m(from_left, shot_bearing_deg=0, distance_m=150) > 0


def test_crosswind_from_the_right_pushes_the_ball_left():
    from_right = Conditions(wind_mph=10, wind_bearing_deg=270)
    assert crosswind_drift_m(from_right, shot_bearing_deg=0, distance_m=150) < 0


def test_pure_crosswind_has_no_headwind_component():
    head, cross = wind_components(Conditions(wind_mph=10, wind_bearing_deg=90), 0)
    assert head == pytest.approx(0, abs=1e-9)
    assert abs(cross) == pytest.approx(10)


def test_longer_shots_drift_further_in_the_same_wind():
    wind = Conditions(wind_mph=10, wind_bearing_deg=90)
    assert crosswind_drift_m(wind, 0, 200) > crosswind_drift_m(wind, 0, 100)
