"""Run the engine against an imported course: `python -m caddie_engine ...`"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from .conditions import Conditions
from .config import to_metres, to_yards
from .demo import plot_recommendation
from .geometry import hole_model_from_dict
from .optimize import recommend


def _load_hole(course_json: Path, number: int):
    course = json.loads(course_json.read_text())
    entry = next((h for h in course["holes"] if h["number"] == number), None)
    if entry is None:
        available = sorted(h["number"] for h in course["holes"])
        raise SystemExit(f"Hole {number} not found. This course has holes {available}.")
    return course, hole_model_from_dict(entry)


def _start_position(hole, yards_out: float | None):
    """Where the player is standing: the tee by default, or a point out on the hole line."""
    if yards_out is None:
        return hole.tee_xy, "tee"

    metres = to_metres(yards_out)
    dx = hole.pin_xy[0] - hole.tee_xy[0]
    dy = hole.pin_xy[1] - hole.tee_xy[1]
    total = math.hypot(dx, dy)
    if metres >= total:
        return hole.tee_xy, "tee"

    fraction = (total - metres) / total
    return (hole.tee_xy[0] + dx * fraction, hole.tee_xy[1] + dy * fraction), "fairway"


def cmd_recommend(args: argparse.Namespace) -> int:
    course_json = Path(args.course_json)
    course, hole = _load_hole(course_json, args.hole)
    start_xy, lie = _start_position(hole, args.from_yards)

    conditions = Conditions(
        wind_mph=args.wind_mph,
        wind_bearing_deg=args.wind_bearing,
        elevation_change_m=to_metres(args.elevation_yards),
    )

    result = recommend(
        hole,
        start_xy=start_xy,
        conditions=conditions,
        lie=lie,
        handicap=args.handicap,
        samples=args.samples,
        seed=args.seed,
    )

    distance = math.dist(start_xy, hole.pin_xy)
    print(f"{course['name']} — hole {hole.number} (par {hole.par})")
    print(f"  {to_yards(distance):.0f} yds to pin, from {lie}, handicap {args.handicap:g}")
    if not conditions.is_calm:
        print(f"  wind {conditions.wind_mph:g} mph toward {conditions.wind_bearing_deg:g}°")
    print()
    print(result.summary())

    if not args.no_plot:
        output = course_json.parent / f"hole-{hole.number}-recommendation.png"
        plot_recommendation(hole, result, start_xy, output)
        print(f"\nWrote {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="caddie_engine", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("recommend", help="Best club and aim for a position on a hole")
    rec.add_argument("course_json", help="Path to an imported course.json")
    rec.add_argument("--hole", type=int, required=True)
    rec.add_argument(
        "--from-yards",
        type=float,
        default=None,
        dest="from_yards",
        help="Distance to the pin. Defaults to playing from the tee.",
    )
    rec.add_argument("--handicap", type=float, default=15.0)
    rec.add_argument("--wind-mph", type=float, default=0.0)
    rec.add_argument(
        "--wind-bearing",
        type=float,
        default=0.0,
        help="Compass bearing the wind blows TOWARD, in degrees.",
    )
    rec.add_argument("--elevation-yards", type=float, default=0.0)
    rec.add_argument("--samples", type=int, default=None)
    rec.add_argument("--seed", type=int, default=None)
    rec.add_argument("--no-plot", action="store_true")
    rec.set_defaults(func=cmd_recommend)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
