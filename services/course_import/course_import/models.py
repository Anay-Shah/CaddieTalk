"""Shapes for the processed course geometry written to `course.json`.

Coordinates in these models are **projected metres** (UTM), not lat/lon, so the engine can
treat distance as plain Euclidean math. A parallel `course.geojson` is written in WGS84 for
the mobile app and for visual checks.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

Ring = list[list[float]]
"""A closed ring of [x, y] projected coordinates."""

Line = list[list[float]]
"""An open line of [x, y] projected coordinates."""


class TeeBox(BaseModel):
    name: str | None = None
    polygon: Ring


class Hole(BaseModel):
    number: int
    par: int | None = None
    hole_line: Line = Field(default_factory=list)
    tees: list[TeeBox] = Field(default_factory=list)
    green: Ring | None = None
    fairways: list[Ring] = Field(default_factory=list)
    bunkers: list[Ring] = Field(default_factory=list)
    water: list[Ring] = Field(default_factory=list)
    trees: list[Ring] = Field(default_factory=list)

    @property
    def length_m(self) -> float:
        if len(self.hole_line) < 2:
            return 0.0
        total = 0.0
        for (x1, y1), (x2, y2) in zip(self.hole_line, self.hole_line[1:], strict=False):
            total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        return total


class Course(BaseModel):
    course_id: str
    name: str
    crs: str
    """EPSG code of the projected coordinate system, e.g. "EPSG:32617"."""

    bbox_lonlat: list[float]
    """[south, west, north, east] in WGS84, as used for the Overpass query."""

    holes: list[Hole] = Field(default_factory=list)

    def hole(self, number: int) -> Hole | None:
        return next((h for h in self.holes if h.number == number), None)
