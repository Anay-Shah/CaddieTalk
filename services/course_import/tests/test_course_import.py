"""Tests for the OSM course import pipeline.

Everything here runs against a synthetic Overpass response. No network calls.
"""

from __future__ import annotations

import math

import pytest
from course_import.build import build_course, slugify, to_geojson
from course_import.parse import classify, parse_elements
from course_import.project import Projector, utm_epsg_for

LAT0, LON0 = 43.0, -79.0


def m_to_lonlat(x: float, y: float) -> dict:
    """Metre offsets from (LAT0, LON0) as an Overpass geometry point."""
    return {
        "lat": LAT0 + y / 111_320.0,
        "lon": LON0 + x / (111_320.0 * math.cos(math.radians(LAT0))),
    }


def line(points: list[tuple[float, float]]) -> list[dict]:
    return [m_to_lonlat(x, y) for x, y in points]


def square(cx: float, cy: float, size: float = 15.0) -> list[dict]:
    h = size / 2
    corners = [
        (cx - h, cy - h),
        (cx + h, cy - h),
        (cx + h, cy + h),
        (cx - h, cy + h),
        (cx - h, cy - h),
    ]
    return line(corners)


def way(way_id: int, tags: dict, geometry: list[dict]) -> dict:
    return {"type": "way", "id": way_id, "tags": tags, "geometry": geometry}


@pytest.fixture
def osm_response() -> dict:
    """A two-hole course laid out so the tee/green assignment heuristic is exercised.

    Hole 1 runs south to north; hole 2 runs north to south alongside it. That puts hole 1's
    green next to hole 2's tee, which is exactly the situation that breaks naive
    nearest-line assignment.
    """
    return {
        "elements": [
            way(1, {"golf": "hole", "ref": "1", "par": "4"}, line([(0, 0), (0, 300)])),
            way(2, {"golf": "hole", "ref": "2", "par": "5"}, line([(80, 300), (80, 0)])),
            way(10, {"golf": "green"}, square(0, 300)),
            way(11, {"golf": "green"}, square(80, 0)),
            way(12, {"golf": "tee"}, square(0, 0)),
            way(13, {"golf": "tee"}, square(80, 300)),
            way(20, {"golf": "bunker"}, square(20, 250, size=10)),
            way(21, {"natural": "water"}, square(100, 100, size=30)),
            way(30, {"natural": "wood"}, square(600, 600, size=40)),
            way(40, {"golf": "cartpath"}, line([(5, 0), (5, 300)])),
        ]
    }


@pytest.fixture
def course(osm_response):
    return build_course(parse_elements(osm_response), name="Test Links")


# --- projection ---------------------------------------------------------------------


def test_utm_zone_northern_hemisphere():
    assert utm_epsg_for(-79.0, 43.0) == "EPSG:32617"


def test_utm_zone_southern_hemisphere():
    assert utm_epsg_for(151.2, -33.9) == "EPSG:32756"


def test_projection_round_trips():
    projector = Projector.for_point(LON0, LAT0)
    x, y = projector.to_xy(LON0, LAT0)
    lon, lat = projector.to_lonlat(x, y)
    assert lon == pytest.approx(LON0, abs=1e-9)
    assert lat == pytest.approx(LAT0, abs=1e-9)


def test_projected_distance_matches_metres():
    """300 m of latitude offset should measure ~300 m after projection."""
    projector = Projector.for_point(LON0, LAT0)
    start = projector.to_xy(**{"lon": LON0, "lat": LAT0})
    north = m_to_lonlat(0, 300)
    end = projector.to_xy(north["lon"], north["lat"])
    distance = math.dist(start, end)
    assert distance == pytest.approx(300, rel=0.01)


# --- parsing ------------------------------------------------------------------------


def test_classify_maps_known_tags():
    assert classify({"golf": "bunker"}) == "bunker"
    assert classify({"natural": "water"}) == "water"
    assert classify({"landuse": "forest"}) == "trees"


def test_classify_ignores_noise():
    assert classify({"golf": "cartpath"}) is None
    assert classify({"highway": "residential"}) is None


def test_parse_drops_ignored_features(osm_response):
    features = parse_elements(osm_response)
    assert all(f.kind != "cartpath" for f in features)
    assert sum(1 for f in features if f.kind == "hole") == 2


def test_hole_ref_falls_back_to_name():
    response = {"elements": [way(1, {"golf": "hole", "name": "Hole 7"}, line([(0, 0), (0, 10)]))]}
    assert parse_elements(response)[0].hole_ref == 7


# --- assembly -----------------------------------------------------------------------


def test_builds_expected_holes(course):
    assert [hole.number for hole in course.holes] == [1, 2]
    assert course.hole(1).par == 4
    assert course.hole(2).par == 5


def test_hole_length_is_correct(course):
    assert course.hole(1).length_m == pytest.approx(300, rel=0.02)


def test_green_assigned_to_hole_whose_line_ends_there(course):
    """The regression this guards: hole 1's green sits beside hole 2's tee."""
    assert course.hole(1).green is not None
    assert course.hole(2).green is not None

    green_1 = course.hole(1).green
    line_1_end = course.hole(1).hole_line[-1]
    centroid_x = sum(x for x, _ in green_1) / len(green_1)
    centroid_y = sum(y for _, y in green_1) / len(green_1)
    assert math.dist((centroid_x, centroid_y), line_1_end) < 20


def test_tee_assigned_to_hole_start(course):
    assert len(course.hole(1).tees) == 1
    assert len(course.hole(2).tees) == 1


def test_bunker_assigned_to_nearest_hole(course):
    assert len(course.hole(1).bunkers) == 1
    assert len(course.hole(2).bunkers) == 0


def test_water_assigned_to_nearest_hole(course):
    assert len(course.hole(2).water) == 1
    assert len(course.hole(1).water) == 0


def test_distant_features_are_dropped(course):
    """The wood is 600 m away and belongs to no hole."""
    assert all(not hole.trees for hole in course.holes)


def test_crs_is_recorded(course):
    assert course.crs == "EPSG:32617"


def test_raises_when_no_holes_tagged():
    response = {"elements": [way(10, {"golf": "green"}, square(0, 0))]}
    with pytest.raises(ValueError, match="golf=hole"):
        build_course(parse_elements(response), name="Empty")


# --- output -------------------------------------------------------------------------


def test_geojson_covers_every_hole(course):
    geojson = to_geojson(course)
    assert geojson["type"] == "FeatureCollection"
    hole_lines = [f for f in geojson["features"] if f["properties"]["kind"] == "hole_line"]
    assert len(hole_lines) == 2


def test_geojson_coordinates_are_lonlat(course):
    geojson = to_geojson(course)
    lon, lat = geojson["features"][0]["geometry"]["coordinates"][0]
    assert lon == pytest.approx(LON0, abs=0.05)
    assert lat == pytest.approx(LAT0, abs=0.05)


def test_course_json_round_trips(course):
    from course_import.models import Course

    assert Course.model_validate_json(course.model_dump_json()).hole(1).par == 4


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Glen Abbey", "glen-abbey"), ("St. George's G&CC", "st-george-s-g-cc")],
)
def test_slugify(name, expected):
    assert slugify(name) == expected


# --- shared and ambiguous features --------------------------------------------------
#
# These guard behaviours found by importing the Old Course at St Andrews, where seven
# courses share a property, holes interleave, and greens and fairways are shared.


def rect(x0: float, y0: float, x1: float, y1: float) -> list[dict]:
    return line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def test_double_green_serves_both_holes():
    """Links courses share greens; a green must be claimable by more than one hole."""
    response = {
        "elements": [
            way(1, {"golf": "hole", "ref": "1", "par": "4"}, line([(0, 0), (0, 300)])),
            way(2, {"golf": "hole", "ref": "2", "par": "4"}, line([(40, 0), (40, 300)])),
            way(10, {"golf": "green"}, rect(-10, 300, 50, 340)),
        ]
    }
    course = build_course(parse_elements(response), name="Double Green Links")
    assert course.hole(1).green is not None
    assert course.hole(2).green is not None
    assert course.hole(1).green == course.hole(2).green


def test_shared_fairway_attaches_to_every_hole_crossing_it():
    response = {
        "elements": [
            way(1, {"golf": "hole", "ref": "1", "par": "4"}, line([(0, 0), (0, 300)])),
            way(2, {"golf": "hole", "ref": "2", "par": "4"}, line([(40, 0), (40, 300)])),
            way(10, {"golf": "fairway"}, rect(-20, 50, 60, 250)),
        ]
    }
    course = build_course(parse_elements(response), name="Shared Fairway Links")
    assert len(course.hole(1).fairways) == 1
    assert len(course.hole(2).fairways) == 1


def test_boundary_clips_out_a_neighbouring_course():
    """A bbox query catches adjacent courses; the named boundary is what excludes them."""
    response = {
        "elements": [
            way(99, {"leisure": "golf_course", "name": "Test Links"}, rect(-100, -100, 200, 400)),
            way(1, {"golf": "hole", "ref": "1", "par": "4"}, line([(0, 0), (0, 300)])),
            way(2, {"golf": "hole", "ref": "1", "par": "3"}, line([(900, 0), (900, 300)])),
        ]
    }
    course = build_course(parse_elements(response), name="Test Links")
    assert [hole.number for hole in course.holes] == [1]
    assert course.hole(1).par == 4


def test_duplicate_hole_resolved_by_course_name_tag():
    """Interleaved courses need `course:name` to break the tie."""
    response = {
        "elements": [
            way(
                1,
                {"golf": "hole", "ref": "1", "par": "4", "course:name": "Test"},
                line([(0, 0), (0, 300)]),
            ),
            way(2, {"golf": "hole", "ref": "1", "par": "3"}, line([(10, 0), (10, 300)])),
        ]
    }
    course = build_course(parse_elements(response), name="Test Links")
    assert [hole.number for hole in course.holes] == [1]
    assert course.hole(1).par == 4


def test_course_name_matching_is_abbreviation_tolerant():
    from course_import.build import course_name_matches

    assert course_name_matches("Old", "Old Course")
    assert course_name_matches("Old Course", "Old")
    assert not course_name_matches("New", "Old Course")
    assert not course_name_matches("", "Old Course")
