"""Tests for fitting a player's clubs from logged shots.

The milestone's acceptance criterion is the round trip: generate shots from a known
distribution, fit them back, and recover roughly what you started with. If that holds, the
player model and the simulator agree on what a shot is.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from caddie_engine.player_model import (
    ClubStats,
    Shot,
    default_bag,
    drop_mishits,
    fit_bag,
    fit_club,
    shot_metrics,
)
from caddie_engine.synthetic import logged_shots

# --- decomposing a single shot ------------------------------------------------------


def test_a_straight_shot_has_no_sideways_miss():
    shot = Shot("7i", start_xy=(0, 0), end_xy=(0, 140), target_xy=(0, 150))
    metrics = shot_metrics(shot)
    assert metrics.distance_m == pytest.approx(140)
    assert metrics.lateral_m == pytest.approx(0)


def test_a_push_is_measured_as_a_miss_to_the_right():
    shot = Shot("7i", start_xy=(0, 0), end_xy=(12, 140), target_xy=(0, 150))
    assert shot_metrics(shot).lateral_m == pytest.approx(12)


def test_a_pull_is_measured_as_a_miss_to_the_left():
    shot = Shot("7i", start_xy=(0, 0), end_xy=(-12, 140), target_xy=(0, 150))
    assert shot_metrics(shot).lateral_m == pytest.approx(-12)


def test_distance_is_measured_along_the_target_line():
    """A shot 140 m down the line and 30 m right travelled 140 m, not 143 m."""
    shot = Shot("7i", start_xy=(0, 0), end_xy=(30, 140), target_xy=(0, 150))
    assert shot_metrics(shot).distance_m == pytest.approx(140)


def test_the_sideways_convention_holds_in_any_direction():
    """Aiming east, a miss to the south is a miss to the right."""
    shot = Shot("7i", start_xy=(0, 0), end_xy=(140, -12), target_xy=(150, 0))
    assert shot_metrics(shot).lateral_m == pytest.approx(12)


def test_without_a_target_only_distance_is_known():
    shot = Shot("7i", start_xy=(0, 0), end_xy=(30, 140))
    metrics = shot_metrics(shot)
    assert metrics.lateral_m is None
    assert metrics.distance_m == pytest.approx(math.hypot(30, 140))


def test_a_target_on_top_of_the_ball_is_handled():
    shot = Shot("7i", start_xy=(0, 0), end_xy=(0, 140), target_xy=(0, 0))
    assert shot_metrics(shot).lateral_m is None


# --- the milestone criterion --------------------------------------------------------


@pytest.fixture
def known_club() -> ClubStats:
    return ClubStats("7i", mean_m=140.0, sd_m=8.0, lateral_bias_m=6.0, lateral_sd_m=11.0)


def test_fitting_recovers_the_distribution_it_came_from(known_club):
    """The acceptance test for M3.

    Enough shots that the prior is swamped, so what comes back is the data.
    """
    shots = logged_shots(known_club, count=600, rng=np.random.default_rng(1))
    fitted = fit_bag(shots, prior_bag={"7i": known_club})["7i"]

    assert fitted.mean_m == pytest.approx(known_club.mean_m, rel=0.03)
    assert fitted.sd_m == pytest.approx(known_club.sd_m, rel=0.15)
    assert fitted.lateral_bias_m == pytest.approx(known_club.lateral_bias_m, abs=1.5)
    assert fitted.lateral_sd_m == pytest.approx(known_club.lateral_sd_m, rel=0.15)


def test_fitting_recovers_a_club_that_differs_from_its_prior(known_club):
    """The point of the whole exercise: real data must be able to override the default."""
    reality = ClubStats("7i", mean_m=118.0, sd_m=9.0, lateral_bias_m=-9.0, lateral_sd_m=14.0)
    shots = logged_shots(reality, count=600, rng=np.random.default_rng(2))

    fitted = fit_bag(shots, prior_bag={"7i": known_club})["7i"]
    assert fitted.mean_m == pytest.approx(reality.mean_m, rel=0.05)
    assert fitted.lateral_bias_m < 0


def test_shot_count_is_recorded(known_club):
    shots = logged_shots(known_club, count=25, rng=np.random.default_rng(3))
    assert fit_bag(shots, prior_bag={"7i": known_club})["7i"].n_shots == 25


# --- blending against the prior -----------------------------------------------------


def test_no_shots_leaves_the_prior_untouched(known_club):
    fitted = fit_club(known_club, metrics=[])
    assert fitted.mean_m == pytest.approx(known_club.mean_m)
    assert fitted.sd_m == pytest.approx(known_club.sd_m)
    assert not fitted.is_fitted


def test_a_single_shot_barely_moves_the_estimate(known_club):
    """Cold start: one long drive should not convince the app you hit it 200 m."""
    long_one = ClubStats("7i", mean_m=200.0, sd_m=1.0, lateral_sd_m=1.0)
    shots = logged_shots(long_one, count=1, rng=np.random.default_rng(4))

    fitted = fit_club(known_club, [shot_metrics(s) for s in shots])
    assert abs(fitted.mean_m - known_club.mean_m) < 10


def test_more_shots_move_the_estimate_further(known_club):
    reality = ClubStats("7i", mean_m=170.0, sd_m=5.0, lateral_sd_m=5.0)

    def fitted_mean(count: int) -> float:
        shots = logged_shots(reality, count=count, rng=np.random.default_rng(5))
        return fit_club(known_club, [shot_metrics(s) for s in shots]).mean_m

    assert fitted_mean(2) < fitted_mean(10) < fitted_mean(60)


def test_spread_is_ignored_until_there_is_enough_evidence(known_club):
    """Two shots cannot tell you anything trustworthy about dispersion."""
    tight = ClubStats("7i", mean_m=140.0, sd_m=0.5, lateral_sd_m=0.5)
    shots = logged_shots(tight, count=2, rng=np.random.default_rng(6))

    fitted = fit_club(known_club, [shot_metrics(s) for s in shots])
    assert fitted.sd_m == pytest.approx(known_club.sd_m)


def test_a_bigger_prior_weight_resists_the_data_more(known_club):
    reality = ClubStats("7i", mean_m=170.0, sd_m=5.0, lateral_sd_m=5.0)
    metrics = [shot_metrics(s) for s in logged_shots(reality, 10, rng=np.random.default_rng(7))]

    trusting = fit_club(known_club, metrics, prior_pseudo_shots=2)
    stubborn = fit_club(known_club, metrics, prior_pseudo_shots=40)
    assert trusting.mean_m > stubborn.mean_m


# --- mishits ------------------------------------------------------------------------


def test_a_duff_does_not_drag_the_average_down():
    """One topped shot should not rewrite what a club does."""
    assert 20.0 not in drop_mishits([140.0, 138.0, 142.0, 139.0, 20.0])


def test_normal_variation_is_kept():
    distances = [140.0, 128.0, 151.0, 136.0, 145.0]
    assert drop_mishits(distances) == distances


def test_too_few_shots_to_judge_a_mishit():
    """With two shots there is no median worth trusting, so keep both."""
    assert drop_mishits([140.0, 40.0]) == [140.0, 40.0]


def test_mishits_are_excluded_from_the_fit(known_club):
    clean = logged_shots(known_club, count=40, rng=np.random.default_rng(8))
    duffed = [Shot("7i", (0, 0), (0, 25), (0, 140)) for _ in range(4)]

    with_duffs = fit_club(known_club, [shot_metrics(s) for s in clean + duffed])
    without = fit_club(known_club, [shot_metrics(s) for s in clean])
    assert with_duffs.mean_m == pytest.approx(without.mean_m, rel=0.02)


# --- the whole bag ------------------------------------------------------------------


def test_clubs_with_no_data_keep_their_prior():
    bag = default_bag(15)
    shots = logged_shots(bag["7i"], count=20, rng=np.random.default_rng(9))
    fitted = fit_bag(shots, handicap=15)

    assert fitted["7i"].is_fitted
    assert not fitted["Dr"].is_fitted
    assert fitted["Dr"].mean_m == pytest.approx(bag["Dr"].mean_m)


def test_the_bag_stays_complete():
    """The engine must never have to handle a missing club."""
    fitted = fit_bag([], handicap=15)
    assert set(fitted) == set(default_bag(15))


def test_penalty_shots_are_excluded(known_club):
    shots = logged_shots(known_club, count=20, rng=np.random.default_rng(10))
    drops = [Shot("7i", (0, 0), (0, 5), (0, 140), penalty=True) for _ in range(10)]
    assert fit_bag(shots + drops, prior_bag={"7i": known_club})["7i"].n_shots == 20


def test_an_unrecognised_club_is_still_modelled():
    """A player with a 2-hybrid the reference bag has never heard of still gets numbers."""
    hybrid = ClubStats("2h", mean_m=175.0, sd_m=9.0, lateral_sd_m=13.0)
    shots = logged_shots(hybrid, count=60, rng=np.random.default_rng(11))

    fitted = fit_bag(shots, handicap=15)["2h"]
    assert fitted.mean_m == pytest.approx(175.0, rel=0.08)


def test_shots_without_a_target_still_teach_distance(known_club):
    shots = [
        Shot("7i", s.start_xy, s.end_xy)
        for s in logged_shots(known_club, 100, rng=np.random.default_rng(12))
    ]
    fitted = fit_bag(shots, prior_bag={"7i": known_club})["7i"]

    assert fitted.n_shots == 100
    # No target means no usable sideways data, so the bias must stay at the prior.
    assert fitted.lateral_bias_m == pytest.approx(known_club.lateral_bias_m)


def test_a_fitted_bag_changes_the_recommendation():
    """The payoff: measured clubs should produce different advice from generic ones."""
    from caddie_engine.optimize import recommend
    from caddie_engine.synthetic import straight_hole

    hole = straight_hole()
    generic = default_bag(15)

    # This player hits everything 25 m shorter than the reference bag assumes.
    shots = []
    for club in generic.values():
        shorter = ClubStats(club.name, club.mean_m - 25, club.sd_m, 0.0, club.lateral_sd_m)
        shots += logged_shots(shorter, count=40, rng=np.random.default_rng(13))

    fitted = fit_bag(shots, handicap=15)
    before = recommend(hole, (0, 150), bag=generic, samples=4000, seed=1)
    after = recommend(hole, (0, 150), bag=fitted, samples=4000, seed=1)

    assert fitted[after.best.club].mean_m > 0
    assert before.best.club != after.best.club
