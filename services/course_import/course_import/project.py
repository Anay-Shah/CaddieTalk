"""Lat/lon to local metric coordinates.

A golf course fits comfortably inside a single UTM zone, so projecting once up front lets
the engine use plain Euclidean distance everywhere instead of great-circle math.
"""

from __future__ import annotations

from pyproj import Transformer


def utm_epsg_for(lon: float, lat: float) -> str:
    """EPSG code of the UTM zone containing this point."""
    zone = int((lon + 180.0) / 6.0) + 1
    zone = min(max(zone, 1), 60)
    return f"EPSG:{32600 + zone}" if lat >= 0 else f"EPSG:{32700 + zone}"


class Projector:
    """Converts between WGS84 lon/lat and a fixed projected CRS."""

    def __init__(self, crs: str) -> None:
        self.crs = crs
        self._fwd = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        self._inv = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    @classmethod
    def for_point(cls, lon: float, lat: float) -> Projector:
        return cls(utm_epsg_for(lon, lat))

    def to_xy(self, lon: float, lat: float) -> tuple[float, float]:
        return self._fwd.transform(lon, lat)

    def to_lonlat(self, x: float, y: float) -> tuple[float, float]:
        return self._inv.transform(x, y)

    def ring_to_xy(self, ring: list[tuple[float, float]]) -> list[list[float]]:
        return [list(self.to_xy(lon, lat)) for lon, lat in ring]

    def ring_to_lonlat(self, ring: list[list[float]]) -> list[list[float]]:
        return [list(self.to_lonlat(x, y)) for x, y in ring]
