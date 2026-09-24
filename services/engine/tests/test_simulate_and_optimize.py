"""Tests for shot sampling and aim optimization.

The headline tests here are `test_fairway_bunker_right_pushes_the_tee_shot_left` and
`test_conditions_change_the_club_the_way_a_caddie_would` — the behaviours the whole project
exists to produce. Both come out of counting simulated outcomes; neither is a rule anyone
wrote down.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from caddie_engine.conditions import Conditions
from caddie_engine.optimize import aim_points, plausible_clubs, recommend
from caddie_engine.player_model import ClubStats, default_bag
from caddie_engine.simulate import sample_landings, score_landings, simulate_shot
from caddie_engine.synthetic import rect, straight_hole

SAMPLES = 4000

# --- sampling -----------------------------------------------------------------------


def test_sampled_distances_match_the_club(hole, straight_shooter, rng):
    landings = sample_landings((0, 0), (0, 150), straight_shooter, samples=20000, rng=rng)
    travelled = np.hypot(landings[:, 0], landings[:, 1])
    assert travelled.mean() == pytest.approx(straight_shooter.mean_m, rel=0.02)


def test_sampled_spread_matches_the_club(straight_shooter, rng):
    landings = sample_landings((0, 0), (0, 150), straight_shooter, samples=20000, rng=rng)
    assert landings[:, 1].std() == pytest.approx(straight_shooter.sd_m, rel=0.1)


def test_a_player_who_pushes_it_lands_right_of_target(pushes_it_right, rng):
    landings = sample_landings((0, 0), (0, 150), pushes_it_right, samples=20000, rng=rng)
    assert landings[:, 0].mean() == pytest.approx(pushes_it_right.lateral_bias_m, abs=1.0)


def test_aim_direction_is_respected(straight_shooter, rng):
    """Aiming east should send the ball east."""
    landings = sample_landings((0, 0), (150, 0), straight_shooter, samples=5000, rng=rng)
    assert landings[:, 0].mean() > 100
    assert abs(landings[:, 1].mean()) < 20


def test_aim_point_sets_direction_not_distance(straight_shooter, rng):
    """A 150 m club aimed at a target 250 m away still only goes 150 m.

    This is the mistake the engine exists to catch, so it must not be silently corrected.
    """
    landings = sample_landings((0, 0), (0, 250), straight_shooter, samples=5000, rng=rng)
    assert np.hypot(landings[:, 0], landings[:, 1]).mean() == pytest.approx(150, rel=0.03)


def test_rough_costs_distance_and_accuracy(straight_shooter, rng):
    from_fairway = sample_landings(
        (0, 0), (0, 150), straight_shooter, lie="fairway", samples=20000, rng=rng
    )
    from_rough = sample_landings(
        (0, 0), (0, 150), straight_shooter, lie="rough", samples=20000, rng=rng
    )
    assert from_rough[:, 1].mean() < from_fairway[:, 1].mean()
    assert from_rough[:, 0].std() > from_fairway[:, 0].std()


def test_headwind_shortens_the_shot(straight_shooter, rng):
    calm = sample_landings((0, 0), (0, 150), straight_shooter, samples=20000, rng=rng)
    into = sample_landings(
        (0, 0),
        (0, 150),
        straight_shooter,
        conditions=Conditions(wind_mph=15, wind_bearing_deg=180),
        samples=20000,
        rng=rng,
    )
    assert into[:, 1].mean() < calm[:, 1].mean()


# --- scoring ------------------------------------------------------------------------


def test_water_is_scored_as_a_penalty():
    hole = straight_hole(water=rect(-25, 140, 25, 160))
    dry = score_landings(hole, np.array([[40.0, 150.0]]))
    wet = score_landings(hole, np.array([[0.0, 150.0]]))
    assert wet.lies[0] == "water"
    assert wet.strokes[0] > dry.strokes[0]


def test_landing_closer_to_the_pin_scores_better(hole):
    near = score_landings(hole, np.array([[0.0, 280.0]]))
    far = score_landings(hole, np.array([[0.0, 150.0]]))
    assert near.strokes[0] < far.strokes[0]


def test_every_shot_counts_the_stroke_just_played(hole):
    outcome = score_landings(hole, np.array([[0.0, 299.0]]))
    assert outcome.strokes[0] > 1.0


def test_lie_probabilities_sum_to_one(hole, straight_shooter, rng):
    outcome = simulate_shot(hole, (0, 150), (0, 300), straight_shooter, samples=SAMPLES, rng=rng)
    assert sum(outcome.lie_probabilities().values()) == pytest.approx(1.0)


# --- aim grid -----------------------------------------------------------------------


def test_aim_points_are_centred_on_the_target():
    points = aim_points((0, 0), (0, 150), aim_distance_m=150)
    offsets = [offset for _, offset in points]
    assert min(offsets) < 0 < max(offsets)
    assert any(abs(o) < 1e-6 for o in offsets)


def test_aim_points_sit_at_the_requested_distance():
    for point, _ in aim_points((0, 0), (0, 150), aim_distance_m=150):
        assert math.dist((0, 0), point) == pytest.approx(150, rel=1e-6)


def test_plausible_clubs_excludes_the_absurd():
    bag = default_bag(15)
    chosen = {club.name for club in plausible_clubs(bag, distance_to_target_m=140)}
    assert "Dr" not in chosen
    assert "LW" not in chosen


def test_plausible_clubs_always_returns_something():
    """Even a 400 m shot must get an answer rather than an empty list."""
    assert plausible_clubs(default_bag(15), distance_to_target_m=400)


# --- the strategy behaviour that matters ---------------------------------------------


def test_fairway_bunker_right_pushes_the_tee_shot_left(
    driving_hole_clean, driving_hole_bunker_right, driver
):
    """The headline behaviour: trouble right, so aim further left.

    Nobody wrote a rule saying "avoid bunkers" — it falls out of counting outcomes. Both
    runs share a club, seed, and aim grid, so the bunker is the only difference.
    """
    bag = {"Dr": driver}
    clean = recommend(driving_hole_clean, (0, 0), bag=bag, lie="tee", samples=SAMPLES, seed=7)
    guarded = recommend(
        driving_hole_bunker_right, (0, 0), bag=bag, lie="tee", samples=SAMPLES, seed=7
    )

    assert guarded.best.aim_offset_m < clean.best.aim_offset_m


def test_even_a_straight_hitter_avoids_a_fairway_bunker(
    driving_hole_clean, driving_hole_bunker_right, straight_shooter
):
    """Aiming away from trouble is about dispersion, not just about a systematic miss."""
    straight_driver = ClubStats("Dr", mean_m=192.0, sd_m=10.0, lateral_sd_m=17.0)
    bag = {"Dr": straight_driver}
    clean = recommend(driving_hole_clean, (0, 0), bag=bag, lie="tee", samples=SAMPLES, seed=7)
    guarded = recommend(
        driving_hole_bunker_right, (0, 0), bag=bag, lie="tee", samples=SAMPLES, seed=7
    )

    assert clean.best.aim_offset_m == pytest.approx(0, abs=5)
    assert guarded.best.aim_offset_m < clean.best.aim_offset_m


def test_aiming_toward_a_bunker_costs_more_than_aiming_away(hole_with_greenside_bunker, hole):
    """The underlying mechanism, tested directly rather than through the optimizer.

    A greenside bunker does not always move the recommended aim — at 20 m from the pin,
    sand costs only a little more than rough, so being closer to the hole can be worth the
    risk. What must always hold is that the bunker's cost is concentrated on its own side.
    """
    club = ClubStats("7i", mean_m=150.0, sd_m=7.0, lateral_sd_m=12.0)

    def penalty(aim_offset: float) -> float:
        aim = (aim_offset, 300.0)
        clean = simulate_shot(
            hole, (0, 150), aim, club, samples=20000, rng=np.random.default_rng(3)
        )
        sandy = simulate_shot(
            hole_with_greenside_bunker,
            (0, 150),
            aim,
            club,
            samples=20000,
            rng=np.random.default_rng(3),
        )
        return sandy.expected_score - clean.expected_score

    assert penalty(15.0) > penalty(-15.0)


def test_a_player_who_misses_right_is_told_to_aim_left(hole, pushes_it_right):
    bag = {"7i": pushes_it_right}
    result = recommend(hole, (0, 150), bag=bag, samples=SAMPLES, seed=7)
    assert result.best.aim_offset_m < 0


def test_a_straight_hitter_is_told_to_aim_at_the_pin(hole, straight_shooter):
    bag = {"7i": straight_shooter}
    result = recommend(hole, (0, 150), bag=bag, samples=SAMPLES, seed=7)
    assert result.best.aim_offset_m == pytest.approx(0, abs=6.0)


def test_adding_a_hazard_never_improves_the_score(hole, straight_shooter):
    """A property that must hold regardless of tuning: trouble cannot help you."""
    bag = {"7i": straight_shooter}
    clean = recommend(hole, (0, 150), bag=bag, samples=SAMPLES, seed=11)

    hazardous = straight_hole(water=rect(-40, 280, 40, 320))
    risky = recommend(hazardous, (0, 150), bag=bag, samples=SAMPLES, seed=11)

    assert risky.best.expected_score >= clean.best.expected_score


def test_water_in_front_of_the_green_raises_the_risk_reported(hole, straight_shooter):
    bag = {"7i": straight_shooter}
    carry = straight_hole(water=rect(-40, 270, 40, 292))
    result = recommend(carry, (0, 150), bag=bag, samples=SAMPLES, seed=3)
    assert result.best.outcome.probability_of("water") > 0


def _chosen_club_length(hole, conditions, bag):
    result = recommend(hole, (0, 150), bag=bag, conditions=conditions, samples=6000, seed=42)
    return bag[result.best.club].mean_m


def test_conditions_change_the_club_the_way_a_caddie_would(hole):
    """Into the wind and uphill take more club; downwind takes less.

    This is the single clearest sanity check on the whole engine: the numbers have to
    reproduce advice any golfer would recognise as obviously correct.
    """
    bag = default_bag(15)
    calm = _chosen_club_length(hole, Conditions(), bag)
    into = _chosen_club_length(hole, Conditions(wind_mph=15, wind_bearing_deg=180), bag)
    downwind = _chosen_club_length(hole, Conditions(wind_mph=15, wind_bearing_deg=0), bag)
    uphill = _chosen_club_length(hole, Conditions(elevation_change_m=9.0), bag)

    assert into > calm
    assert downwind < calm
    assert uphill > calm


def test_recommendation_reports_alternative_clubs(hole):
    result = recommend(hole, (0, 150), handicap=15, samples=1200, seed=5)
    assert result.alternatives
    assert result.best.club not in {a.club for a in result.alternatives}


def test_alternatives_never_beat_the_recommendation(hole):
    result = recommend(hole, (0, 150), handicap=15, samples=1200, seed=5)
    for alternative in result.alternatives:
        assert alternative.expected_score >= result.best.expected_score


def test_summary_is_human_readable(hole):
    result = recommend(hole, (0, 150), handicap=15, samples=1200, seed=5)
    assert "expected" in result.summary()


def test_better_players_score_better(hole):
    """Same hole, same position; lower handicap should expect fewer strokes."""
    good = recommend(hole, (0, 150), handicap=5, samples=1500, seed=9)
    weak = recommend(hole, (0, 150), handicap=25, samples=1500, seed=9)
    assert good.expected_score < weak.expected_score


def test_describe_aim_names_a_side():
    from caddie_engine.optimize import Candidate

    left = Candidate("7i", (0, 0), aim_offset_m=-9.0, expected_score=3.0, outcome=None)
    right = Candidate("7i", (0, 0), aim_offset_m=9.0, expected_score=3.0, outcome=None)
    assert "left" in left.describe_aim()
    assert "right" in right.describe_aim()


def test_engine_has_no_aws_dependencies():
    """An architectural rule worth enforcing: the engine stays a pure library.

    Parsing imports rather than grepping the source, so that merely *mentioning* AWS in a
    comment doesn't trip it.
    """
    import ast
    import pathlib

    import caddie_engine

    banned = {"boto3", "botocore", "aws_lambda_powertools"}
    root = pathlib.Path(caddie_engine.__file__).parent

    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                continue
            assert not (names & banned), f"{path.name} imports {names & banned}"


def test_a_short_club_is_not_chosen_for_a_long_shot(hole):
    """Sanity: from 200 m out the engine should reach for something long."""
    result = recommend(hole, (0, 100), handicap=15, samples=1200, seed=5)
    chosen = default_bag(15)[result.best.club]
    assert chosen.mean_m > 120


def test_deterministic_with_a_seed(hole, straight_shooter):
    bag = {"7i": straight_shooter}
    first = recommend(hole, (0, 150), bag=bag, samples=1500, seed=42)
    second = recommend(hole, (0, 150), bag=bag, samples=1500, seed=42)
    assert first.best.expected_score == second.best.expected_score
    assert first.best.aim_offset_m == second.best.aim_offset_m


def test_club_stats_knows_whether_it_is_fitted():
    assert not ClubStats("7i", 150, 7).is_fitted
    assert ClubStats("7i", 150, 7, n_shots=20).is_fitted
