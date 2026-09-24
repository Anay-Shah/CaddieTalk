"""Orchestration: OpenStreetMap in, `course.json` out."""

from __future__ import annotations

import json
import re
from pathlib import Path

from shapely.geometry import LineString, Polygon

from .assign import HoleGeometry, assign_features
from .models import Course, Hole, TeeBox
from .overpass import fetch_features, find_courses
from .parse import RawFeature, bbox_of, parse_elements
from .project import Projector

DEFAULT_OUTPUT_ROOT = Path("data/courses")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "course"


def resolve_course(name: str, lat: float, lon: float, radius_m: int = 20_000):
    """Find the OSM course best matching `name` near a point."""
    candidates = find_courses(lat, lon, radius_m)
    if not candidates:
        raise LookupError(f"No golf courses found within {radius_m / 1000:.0f} km of {lat},{lon}")

    needle = name.lower()
    exact = [c for c in candidates if needle in c.name.lower()]
    if not exact:
        available = ", ".join(sorted(c.name for c in candidates)[:10])
        raise LookupError(f"No course matching {name!r} nearby. Found: {available}")
    return exact[0]


def _lonlat_polygon(ring: list[tuple[float, float]]) -> Polygon | None:
    if len(ring) < 3:
        return None
    polygon = Polygon(ring)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return polygon if not polygon.is_empty else None


def course_boundary(features: list[RawFeature], name: str):
    """The `leisure=golf_course` polygon matching `name`, in lon/lat.

    Courses frequently sit next to each other — St Andrews has seven sharing a boundary —
    so a bounding-box query returns a blend of several courses' holes. Clipping to the
    named course's own boundary is what keeps hole numbers unique.
    """
    needle = name.lower()
    matches = [
        f for f in features if f.kind == "course" and needle in f.tags.get("name", "").lower()
    ]
    polygons = [p for f in matches for ring in f.rings if (p := _lonlat_polygon(ring))]
    if not polygons:
        return None
    return max(polygons, key=lambda p: p.area)


def _within(rings: list[list[tuple[float, float]]], boundary) -> bool:
    """True when a feature's centre sits inside the course boundary.

    Centroid containment rather than intersection: features on a shared property line
    would otherwise be claimed by both neighbouring courses.
    """
    for ring in rings:
        geometry = (
            _lonlat_polygon(ring)
            if len(ring) >= 3
            else LineString(ring) if len(ring) >= 2 else None
        )
        if geometry is not None and boundary.contains(geometry.centroid):
            return True
    return False


def course_name_matches(tag_value: str, name: str) -> bool:
    """Whether a `course:name` tag refers to this course.

    OSM abbreviates: the Old Course's holes are tagged `course:name=Old`.
    """
    tag = tag_value.strip().lower()
    return bool(tag) and (tag in name.strip().lower() or name.strip().lower() in tag)


def dedupe_holes(hole_features: list[RawFeature], boundary, name: str) -> list[RawFeature]:
    """Keep one way per hole number.

    Neighbouring courses interleave — at St Andrews the Old and New Courses share
    fairways — so a boundary clip alone can still leave two ways claiming the same number.
    Prefer an explicit `course:name` tag, and otherwise keep whichever line lies more
    fully inside this course's boundary.
    """
    by_number: dict[int, list[RawFeature]] = {}
    for feature in hole_features:
        by_number.setdefault(feature.hole_ref, []).append(feature)

    def inside_fraction(feature: RawFeature) -> float:
        if boundary is None:
            return 0.0
        line = LineString(feature.rings[0])
        return line.intersection(boundary).length / line.length if line.length else 0.0

    resolved = []
    for number, group in sorted(by_number.items()):
        if len(group) == 1:
            resolved.append(group[0])
            continue

        named = [f for f in group if course_name_matches(f.tags.get("course:name", ""), name)]
        if len(named) == 1:
            resolved.append(named[0])
            continue

        candidates = named or group
        best = max(candidates, key=inside_fraction)
        if inside_fraction(best) == 0.0 and boundary is not None:
            raise ValueError(
                f"Hole {number} matched {len(group)} ways and none could be attributed to "
                f"{name!r}. Try a tighter --bbox."
            )
        resolved.append(best)

    return resolved


def _to_polygon(ring: list[list[float]]) -> Polygon | None:
    if len(ring) < 3:
        return None
    polygon = Polygon(ring)
    if not polygon.is_valid:
        # Self-intersecting rings are common in OSM; buffer(0) repairs most of them.
        polygon = polygon.buffer(0)
    return polygon if not polygon.is_empty and polygon.geom_type == "Polygon" else None


def build_course(
    features: list[RawFeature],
    name: str,
    course_id: str | None = None,
) -> Course:
    """Project, assign, and assemble features into a `Course`."""
    boundary = course_boundary(features, name)
    if boundary is not None:
        features = [f for f in features if f.kind == "course" or _within(f.rings, boundary)]

    hole_features = [f for f in features if f.is_line and f.hole_ref is not None]
    if not hole_features:
        raise ValueError(
            "No `golf=hole` ways with a hole number found. The course may be missing from "
            "OpenStreetMap, or its holes may be untagged — see docs/architecture.md §16."
        )

    hole_features = dedupe_holes(hole_features, boundary, name)

    bbox = bbox_of(features)
    south, west, north, east = bbox
    projector = Projector.for_point((west + east) / 2, (south + north) / 2)

    holes: list[HoleGeometry] = []
    for feature in sorted(hole_features, key=lambda f: f.hole_ref):
        line = LineString(projector.ring_to_xy(feature.rings[0]))
        holes.append(HoleGeometry(number=feature.hole_ref, par=feature.par, line=line))

    polygons: list[tuple[str, Polygon]] = []
    for feature in features:
        if feature.is_line or feature.kind == "course":
            continue
        for ring in feature.rings:
            polygon = _to_polygon(projector.ring_to_xy(ring))
            if polygon is not None:
                polygons.append((feature.kind, polygon))

    assign_features(holes, polygons)

    def ring_of(polygon: Polygon) -> list[list[float]]:
        return [list(coord) for coord in polygon.exterior.coords]

    return Course(
        course_id=course_id or slugify(name),
        name=name,
        crs=projector.crs,
        bbox_lonlat=list(bbox),
        holes=[
            Hole(
                number=hole.number,
                par=hole.par,
                hole_line=[list(coord) for coord in hole.line.coords],
                tees=[TeeBox(polygon=ring_of(tee)) for tee in hole.tees],
                green=ring_of(hole.green) if hole.green else None,
                fairways=[ring_of(p) for p in hole.fairways],
                bunkers=[ring_of(p) for p in hole.bunkers],
                water=[ring_of(p) for p in hole.water],
                trees=[ring_of(p) for p in hole.trees],
            )
            for hole in holes
        ],
    )


def to_geojson(course: Course) -> dict:
    """WGS84 FeatureCollection for the mobile app and for dropping into geojson.io."""
    projector = Projector(course.crs)
    features = []

    def add(geometry_type: str, coords, hole_number: int, kind: str):
        features.append(
            {
                "type": "Feature",
                "properties": {"hole": hole_number, "kind": kind},
                "geometry": {"type": geometry_type, "coordinates": coords},
            }
        )

    for hole in course.holes:
        add("LineString", projector.ring_to_lonlat(hole.hole_line), hole.number, "hole_line")
        for tee in hole.tees:
            add("Polygon", [projector.ring_to_lonlat(tee.polygon)], hole.number, "tee")
        if hole.green:
            add("Polygon", [projector.ring_to_lonlat(hole.green)], hole.number, "green")
        for kind, rings in (
            ("fairway", hole.fairways),
            ("bunker", hole.bunkers),
            ("water", hole.water),
            ("trees", hole.trees),
        ):
            for ring in rings:
                add("Polygon", [projector.ring_to_lonlat(ring)], hole.number, kind)

    return {"type": "FeatureCollection", "features": features}


def import_course(
    name: str,
    lat: float,
    lon: float,
    radius_m: int = 20_000,
    bbox: tuple[float, float, float, float] | None = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    refresh: bool = False,
) -> tuple[Course, Path]:
    """Fetch, process, and write a course. Returns the course and its output directory."""
    course_id = slugify(name)
    out_dir = output_root / course_id
    raw_path = out_dir / "raw_osm.json"

    if bbox is None:
        match = resolve_course(name, lat, lon, radius_m)
        # A generous box around the course centre; trimmed to actual geometry afterwards.
        pad = 0.02
        bbox = (match.lat - pad, match.lon - pad, match.lat + pad, match.lon + pad)
        name = match.name

    if refresh and raw_path.exists():
        raw_path.unlink()

    data = fetch_features(bbox, cache_path=raw_path)
    features = parse_elements(data)
    course = build_course(features, name=name, course_id=course_id)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "course.json").write_text(course.model_dump_json(indent=2))
    (out_dir / "course.geojson").write_text(json.dumps(to_geojson(course), indent=2))

    return course, out_dir
