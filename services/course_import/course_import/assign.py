"""Assign each polygon to the hole it belongs to.

OpenStreetMap tags a bunker as a bunker, but rarely says which hole it is on. We infer it
from proximity to the hole centre-lines, which are tagged with their number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

# Beyond this, a feature is treated as belonging to the course rather than to any hole.
# Mostly this drops large woods and lakes that span the whole property.
MAX_ASSIGN_DISTANCE_M = 120.0


@dataclass
class HoleGeometry:
    number: int
    par: int | None
    line: LineString
    tees: list[Polygon] = field(default_factory=list)
    green: Polygon | None = None
    fairways: list[Polygon] = field(default_factory=list)
    bunkers: list[Polygon] = field(default_factory=list)
    water: list[Polygon] = field(default_factory=list)
    trees: list[Polygon] = field(default_factory=list)


def _nearest_hole(holes: list[HoleGeometry], geom: Polygon, tree: STRtree) -> HoleGeometry | None:
    """The hole whose centre-line is closest to this polygon."""
    if not holes:
        return None
    index = tree.nearest(geom)
    hole = holes[int(index)]
    return hole if hole.line.distance(geom) <= MAX_ASSIGN_DISTANCE_M else None


def _nearest_by_endpoint(holes: list[HoleGeometry], geom: Polygon, end: str) -> HoleGeometry | None:
    """The hole whose line starts (tees) or ends (greens) closest to this polygon.

    Greens and tees sit at the ends of a hole, and adjacent holes often run alongside each
    other, so distance-to-the-whole-line picks the wrong hole surprisingly often. Comparing
    against the correct endpoint is much more reliable.
    """
    if not holes:
        return None
    centre = geom.centroid

    def endpoint_distance(hole: HoleGeometry) -> float:
        coords = list(hole.line.coords)
        x, y = coords[0] if end == "start" else coords[-1]
        return ((centre.x - x) ** 2 + (centre.y - y) ** 2) ** 0.5

    best = min(holes, key=endpoint_distance)
    return best if endpoint_distance(best) <= MAX_ASSIGN_DISTANCE_M else None


def _assign_greens(holes: list[HoleGeometry], greens: list[Polygon]) -> None:
    """Give every hole its nearest green, allowing a green to serve several holes.

    Shared greens are a real feature of links courses — the Old Course at St Andrews has
    seven double greens. Iterating over holes rather than over green polygons is what lets
    one polygon be claimed more than once.
    """
    if not greens:
        return
    for hole in holes:
        end = Point(list(hole.line.coords)[-1])
        nearest = min(greens, key=end.distance)
        if end.distance(nearest) <= MAX_ASSIGN_DISTANCE_M:
            hole.green = nearest


def _assign_fairways(holes: list[HoleGeometry], fairways: list[Polygon]) -> None:
    """Attach a fairway to every hole running through it.

    Older links courses often map one large shared fairway spanning several holes, so a
    single-owner rule would leave most holes with none.
    """
    for polygon in fairways:
        crossing = [hole for hole in holes if hole.line.intersects(polygon)]
        if crossing:
            for hole in crossing:
                hole.fairways.append(polygon)
        else:
            nearest = min(holes, key=lambda h: h.line.distance(polygon))
            if nearest.line.distance(polygon) <= MAX_ASSIGN_DISTANCE_M:
                nearest.fairways.append(polygon)


def assign_features(
    holes: list[HoleGeometry],
    polygons: list[tuple[str, Polygon]],
) -> list[HoleGeometry]:
    """Attach each (kind, polygon) pair to its hole. Mutates and returns `holes`."""
    if not holes:
        return holes

    tree = STRtree([hole.line for hole in holes])
    by_kind: dict[str, list[Polygon]] = {}
    for kind, polygon in polygons:
        if not polygon.is_empty:
            by_kind.setdefault(kind, []).append(polygon)

    _assign_greens(holes, by_kind.get("green", []))
    _assign_fairways(holes, by_kind.get("fairway", []))

    for polygon in by_kind.get("tee", []):
        hole = _nearest_by_endpoint(holes, polygon, end="start")
        if hole:
            hole.tees.append(polygon)

    # Bunkers, water, and trees are localized, so single ownership is the right rule.
    for kind, attribute in (("bunker", "bunkers"), ("water", "water"), ("trees", "trees")):
        for polygon in by_kind.get(kind, []):
            hole = _nearest_hole(holes, polygon, tree)
            if hole is not None:
                getattr(hole, attribute).append(polygon)

    return holes
