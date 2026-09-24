"""Import golf course geometry from OpenStreetMap into per-hole `course.json`.

OSM data is licensed ODbL; the mobile app must display attribution.
"""

from .build import build_course, import_course, to_geojson
from .models import Course, Hole, TeeBox

__all__ = ["Course", "Hole", "TeeBox", "build_course", "import_course", "to_geojson"]
