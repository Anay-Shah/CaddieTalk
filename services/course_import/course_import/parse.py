"""Turn a raw Overpass response into classified geometry.

Overpass `out geom` inlines coordinates on each way and on relation members, so no separate
node lookup is needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# OSM tag combinations mapped onto the feature kinds the engine cares about.
TAG_KINDS: list[tuple[str, str, str]] = [
    ("golf", "hole", "hole"),
    ("golf", "tee", "tee"),
    ("golf", "green", "green"),
    ("golf", "fairway", "fairway"),
    ("golf", "bunker", "bunker"),
    ("golf", "water_hazard", "water"),
    ("golf", "lateral_water_hazard", "water"),
    ("golf", "rough", "rough"),
    ("golf", "driving_range", "ignore"),
    ("golf", "path", "ignore"),
    ("golf", "cartpath", "ignore"),
    ("natural", "water", "water"),
    ("natural", "wood", "trees"),
    ("landuse", "forest", "trees"),
    ("leisure", "golf_course", "course"),
]

POLYGON_KINDS = {"tee", "green", "fairway", "bunker", "water", "trees", "rough", "course"}


@dataclass
class RawFeature:
    kind: str
    tags: dict[str, str]
    rings: list[list[tuple[float, float]]] = field(default_factory=list)
    """Lon/lat rings. A `hole` feature carries exactly one open line."""

    @property
    def is_line(self) -> bool:
        return self.kind == "hole"

    @property
    def hole_ref(self) -> int | None:
        """Hole number from `ref`, falling back to digits in `name`."""
        for key in ("ref", "name"):
            value = self.tags.get(key)
            if not value:
                continue
            match = re.search(r"\d+", value)
            if match:
                return int(match.group())
        return None

    @property
    def par(self) -> int | None:
        value = self.tags.get("par")
        return int(value) if value and value.isdigit() else None


def classify(tags: dict[str, str]) -> str | None:
    for key, value, kind in TAG_KINDS:
        if tags.get(key) == value:
            return None if kind == "ignore" else kind
    return None


def _geometry_to_ring(geometry: list[dict]) -> list[tuple[float, float]]:
    return [(point["lon"], point["lat"]) for point in geometry if "lon" in point and "lat" in point]


def parse_elements(data: dict) -> list[RawFeature]:
    features: list[RawFeature] = []

    for element in data.get("elements", []):
        tags = element.get("tags", {}) or {}
        kind = classify(tags)
        if kind is None:
            continue

        if element["type"] == "way":
            ring = _geometry_to_ring(element.get("geometry", []))
            if len(ring) < 2:
                continue
            features.append(RawFeature(kind=kind, tags=tags, rings=[ring]))

        elif element["type"] == "relation":
            # Multipolygons: take the outer members and treat each as its own ring. Inner
            # rings (holes in a polygon) are rare enough on a golf course to skip.
            rings = [
                ring
                for member in element.get("members", [])
                if member.get("role") in ("outer", "")
                and len(ring := _geometry_to_ring(member.get("geometry", []))) >= 3
            ]
            if rings:
                features.append(RawFeature(kind=kind, tags=tags, rings=rings))

    return features


def bbox_of(features: list[RawFeature]) -> tuple[float, float, float, float]:
    """(south, west, north, east) covering every feature."""
    lons = [lon for feature in features for ring in feature.rings for lon, _ in ring]
    lats = [lat for feature in features for ring in feature.rings for _, lat in ring]
    if not lons:
        raise ValueError("No geometry to compute a bounding box from")
    return (min(lats), min(lons), max(lats), max(lons))
