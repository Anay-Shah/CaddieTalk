"""Command line entry point: `python -m course_import <command>`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import DEFAULT_OUTPUT_ROOT, import_course
from .models import Course
from .overpass import find_courses
from .plot import plot_course, summarize


def _parse_latlon(value: str) -> tuple[float, float]:
    lat, lon = (float(part) for part in value.split(","))
    return lat, lon


def cmd_search(args: argparse.Namespace) -> int:
    lat, lon = _parse_latlon(args.near)
    candidates = find_courses(lat, lon, int(args.radius * 1000))
    if not candidates:
        print(f"No golf courses found within {args.radius} km.")
        return 1
    for candidate in sorted(candidates, key=lambda c: c.name):
        print(f"  {candidate.name}  ({candidate.lat:.5f}, {candidate.lon:.5f})")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    lat, lon = _parse_latlon(args.near) if args.near else (0.0, 0.0)
    bbox = tuple(float(p) for p in args.bbox.split(",")) if args.bbox else None

    course, out_dir = import_course(
        name=args.name,
        lat=lat,
        lon=lon,
        radius_m=int(args.radius * 1000),
        bbox=bbox,
        output_root=Path(args.output),
        refresh=args.refresh,
    )

    print(summarize(course))
    print(f"\nWrote {out_dir}/course.json and course.geojson")

    if not args.no_plot:
        image = plot_course(course, out_dir / "holes.png")
        print(f"Wrote {image} — check every hole looks right before moving on.")
    return 0


def cmd_plot(args: argparse.Namespace) -> int:
    course = Course.model_validate_json(Path(args.course_json).read_text())
    print(summarize(course))
    image = plot_course(course, Path(args.course_json).parent / "holes.png")
    print(f"\nWrote {image}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="course_import", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="List golf courses near a point")
    search.add_argument("--near", required=True, metavar="LAT,LON")
    search.add_argument("--radius", type=float, default=20.0, help="km (default: 20)")
    search.set_defaults(func=cmd_search)

    imp = sub.add_parser("import", help="Import a course into course.json")
    imp.add_argument("--name", required=True)
    imp.add_argument("--near", metavar="LAT,LON", help="Required unless --bbox is given")
    imp.add_argument("--radius", type=float, default=20.0, help="km (default: 20)")
    imp.add_argument("--bbox", metavar="S,W,N,E", help="Skip the name search")
    imp.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    imp.add_argument("--refresh", action="store_true", help="Ignore the cached OSM response")
    imp.add_argument("--no-plot", action="store_true")
    imp.set_defaults(func=cmd_import)

    plot = sub.add_parser("plot", help="Re-render holes from an existing course.json")
    plot.add_argument("course_json")
    plot.set_defaults(func=cmd_plot)

    args = parser.parse_args(argv)
    if args.command == "import" and not args.near and not args.bbox:
        parser.error("import requires --near LAT,LON or --bbox S,W,N,E")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
