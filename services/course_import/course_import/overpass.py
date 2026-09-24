"""Overpass API client.

OpenStreetMap data is ODbL-licensed; the app must carry attribution. Overpass is a free,
rate-limited, shared service, so raw responses are cached to disk and re-imports read from
the cache rather than hammering it.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests

ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

USER_AGENT = "CaddieTalk/0.1 (personal project; OSM data used under ODbL)"


class OverpassError(RuntimeError):
    pass


@dataclass
class CourseCandidate:
    osm_type: str
    osm_id: int
    name: str
    lat: float
    lon: float


def _post(query: str, timeout: int = 180) -> dict:
    """Run a query, falling back to the mirror if the primary endpoint is busy."""
    last_error: Exception | None = None
    for endpoint in ENDPOINTS:
        for attempt in range(3):
            try:
                response = requests.post(
                    endpoint,
                    data={"data": query},
                    headers={"User-Agent": USER_AGENT},
                    timeout=timeout,
                )
                if response.status_code in (429, 504):
                    time.sleep(2 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(2 * (attempt + 1))
    raise OverpassError(f"All Overpass endpoints failed: {last_error}")


def find_courses(lat: float, lon: float, radius_m: int = 20_000) -> list[CourseCandidate]:
    """Golf courses near a point.

    Searching by name globally is expensive for Overpass, so we search a radius and filter
    by name locally instead.
    """
    query = f"""
[out:json][timeout:60];
(
  way["leisure"="golf_course"](around:{radius_m},{lat},{lon});
  relation["leisure"="golf_course"](around:{radius_m},{lat},{lon});
);
out tags center;
"""
    data = _post(query, timeout=90)
    candidates = []
    for element in data.get("elements", []):
        center = element.get("center") or {}
        candidates.append(
            CourseCandidate(
                osm_type=element["type"],
                osm_id=element["id"],
                name=element.get("tags", {}).get("name", "(unnamed)"),
                lat=center.get("lat", lat),
                lon=center.get("lon", lon),
            )
        )
    return candidates


def fetch_features(bbox: tuple[float, float, float, float], cache_path: Path | None = None) -> dict:
    """Every golf-relevant feature inside a bounding box of (south, west, north, east)."""
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text())

    south, west, north, east = bbox
    box = f"{south},{west},{north},{east}"
    query = f"""
[out:json][timeout:180];
(
  way["golf"]({box});
  relation["golf"]({box});
  way["leisure"="golf_course"]({box});
  relation["leisure"="golf_course"]({box});
  way["natural"="water"]({box});
  relation["natural"="water"]({box});
  way["natural"="wood"]({box});
  relation["natural"="wood"]({box});
  way["landuse"="forest"]({box});
);
out geom;
"""
    data = _post(query)
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data))
    return data
