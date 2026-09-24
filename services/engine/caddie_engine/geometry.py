"""Classifying where a ball ended up.

The simulator produces thousands of landing points per candidate shot, so this has to
answer "what is each ball sitting on?" in bulk. Shapely's `contains_xy` tests a whole
array of points against one polygon in a single C call, which is what makes that cheap.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

# Checked in this order; first match wins. Water outranks everything because a ball in a
# hazard is a penalty regardless of what else overlaps there. Sand outranks green so that
# a greenside bunker overlapping the green polygon is still sand. Green outranks fairway
# for the same reason.
LIE_PRECEDENCE = ("water", "sand", "green", "fairway", "recovery")

DEFAULT_LIE = "rough"


@dataclass
class HoleModel:
    """A hole's geometry, prepared once and reused across thousands of simulations."""

    number: int
    par: int | None
    tee_xy: tuple[float, float]
    pin_xy: tuple[float, float]
    green: Polygon | MultiPolygon | None = None
    fairway: Polygon | MultiPolygon | None = None
    sand: Polygon | MultiPolygon | None = None
    water: Polygon | MultiPolygon | None = None
    recovery: Polygon | MultiPolygon | None = None
    _surfaces: dict = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._surfaces = {
            "water": self.water,
            "sand": self.sand,
            "green": self.green,
            "fairway": self.fairway,
            "recovery": self.recovery,
        }

    def classify(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Lie for each point, as an array of strings.

        Anything not inside a mapped feature is rough. That is the right default: OSM maps
        the notable surfaces, and the unmapped remainder of a golf course is rough.
        """
        lies = np.full(len(x), DEFAULT_LIE, dtype="<U8")
        unassigned = np.ones(len(x), dtype=bool)

        for name in LIE_PRECEDENCE:
            surface = self._surfaces.get(name)
            if surface is None or surface.is_empty or not unassigned.any():
                continue
            inside = shapely.contains_xy(surface, x, y) & unassigned
            lies[inside] = name
            unassigned &= ~inside

        return lies

    def distance_to_pin(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return np.hypot(x - self.pin_xy[0], y - self.pin_xy[1])


def _merge(rings: list[list[list[float]]]) -> Polygon | MultiPolygon | None:
    """Combine rings into one geometry so each surface is a single containment test."""
    polygons = []
    for ring in rings:
        if len(ring) < 3:
            continue
        polygon = Polygon(ring)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if not polygon.is_empty:
            polygons.append(polygon)

    if not polygons:
        return None
    merged = unary_union(polygons)
    return merged if not merged.is_empty else None


def hole_model_from_dict(data: dict, pin_xy: tuple[float, float] | None = None) -> HoleModel:
    """Build a `HoleModel` straight from a `course.json` hole entry.

    Kept dict-based on purpose: the engine must not import `course_import`, so that it
    stays a standalone library usable from Lambda, notebooks, and tests alike.
    """
    green = _merge([data["green"]] if data.get("green") else [])

    if pin_xy is None:
        if green is None:
            raise ValueError(f"Hole {data.get('number')} has no green, so the pin is unknown")
        pin_xy = (green.centroid.x, green.centroid.y)

    hole_line = data.get("hole_line") or []
    return HoleModel(
        number=data.get("number", 0),
        par=data.get("par"),
        tee_xy=tuple(hole_line[0]) if hole_line else pin_xy,
        pin_xy=pin_xy,
        green=green,
        fairway=_merge(data.get("fairways", [])),
        sand=_merge(data.get("bunkers", [])),
        water=_merge(data.get("water", [])),
        recovery=_merge(data.get("trees", [])),
    )


def hole_model_from_course(
    hole,
    pin_xy: tuple[float, float] | None = None,
    tee_name: str | None = None,
) -> HoleModel:
    """Build a `HoleModel` from an imported `course_import.models.Hole`.

    The pin defaults to the centre of the green, since a real pin position is something
    the player taps on the map during a round.
    """
    green = _merge([hole.green] if hole.green else [])

    if pin_xy is None:
        if green is None:
            raise ValueError(f"Hole {hole.number} has no green, so the pin cannot be inferred")
        pin_xy = (green.centroid.x, green.centroid.y)

    tee_xy = tuple(hole.hole_line[0]) if hole.hole_line else pin_xy
    if tee_name:
        match = next((t for t in hole.tees if t.name == tee_name), None)
        if match:
            centroid = Polygon(match.polygon).centroid
            tee_xy = (centroid.x, centroid.y)

    return HoleModel(
        number=hole.number,
        par=hole.par,
        tee_xy=tee_xy,
        pin_xy=pin_xy,
        green=green,
        fairway=_merge(hole.fairways),
        sand=_merge(hole.bunkers),
        water=_merge(hole.water),
        recovery=_merge(hole.trees),
    )
