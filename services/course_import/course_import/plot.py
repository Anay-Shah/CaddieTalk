"""Render imported holes so they can be checked by eye.

M1 is only done when every hole plots correctly, so this is a deliverable rather than a
debugging convenience. Bad OSM data usually looks obviously wrong long before it produces a
wrong number.
"""

from __future__ import annotations

import math
from pathlib import Path

from .models import Course, Hole

STYLES = {
    "fairways": {"facecolor": "#a8d5a2", "edgecolor": "#6da368", "zorder": 2},
    "green": {"facecolor": "#5fbf60", "edgecolor": "#2f7a32", "zorder": 4},
    "bunkers": {"facecolor": "#f2e2b6", "edgecolor": "#c9b078", "zorder": 5},
    "water": {"facecolor": "#9ec9e8", "edgecolor": "#4a89b5", "zorder": 3},
    "trees": {"facecolor": "#cfe0c4", "edgecolor": "#9bb38f", "zorder": 1},
    "tees": {"facecolor": "#d9d2c5", "edgecolor": "#8f8779", "zorder": 5},
}


def _draw_hole(ax, hole: Hole) -> None:
    from matplotlib.patches import Polygon as MplPolygon

    for attribute, style in STYLES.items():
        value = getattr(hole, attribute)
        rings = [value] if attribute == "green" else value
        for ring in rings or []:
            if attribute == "tees":
                ring = ring.polygon
            if ring:
                ax.add_patch(MplPolygon(ring, closed=True, linewidth=0.8, **style))

    if hole.hole_line:
        xs = [x for x, _ in hole.hole_line]
        ys = [y for _, y in hole.hole_line]
        ax.plot(xs, ys, color="#c0392b", linewidth=1.2, linestyle="--", zorder=6)
        ax.plot(xs[0], ys[0], "o", color="#c0392b", markersize=4, zorder=7)

    par = f"par {hole.par}" if hole.par else "par ?"
    yards = hole.length_m * 1.09361
    ax.set_title(f"Hole {hole.number} · {par} · {yards:.0f} yds", fontsize=9)
    ax.set_aspect("equal")
    ax.axis("off")

    # Frame the hole itself. Shared fairways can span the whole property — the Old Course
    # maps one polygon covering most of it — so autoscaling would show the same blob for
    # every hole and hide the detail this plot exists to check.
    points = list(hole.hole_line) + (hole.green or []) + [p for t in hole.tees for p in t.polygon]
    if points:
        margin = 45.0
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        ax.set_xlim(min(xs) - margin, max(xs) + margin)
        ax.set_ylim(min(ys) - margin, max(ys) + margin)


def plot_course(course: Course, output_path: Path | None = None) -> Path:
    """One panel per hole, written to a PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    holes = sorted(course.holes, key=lambda h: h.number)
    if not holes:
        raise ValueError("Course has no holes to plot")

    columns = min(3, len(holes))
    rows = math.ceil(len(holes) / columns)
    figure, axes = plt.subplots(rows, columns, figsize=(5 * columns, 4.2 * rows))
    flat_axes = axes.flatten() if len(holes) > 1 else [axes]

    for ax, hole in zip(flat_axes, holes, strict=False):
        _draw_hole(ax, hole)
    for ax in flat_axes[len(holes) :]:
        ax.axis("off")

    figure.suptitle(f"{course.name} — {len(holes)} holes imported", fontsize=14)
    figure.tight_layout(rect=(0, 0, 1, 0.98))

    output_path = output_path or Path(f"{course.course_id}-holes.png")
    figure.savefig(output_path, dpi=110)
    plt.close(figure)
    return output_path


def summarize(course: Course) -> str:
    """A quick text report of what did and didn't come through, for spotting gaps fast."""
    lines = [f"{course.name} ({course.course_id}) — {course.crs}", ""]
    lines.append(f"{'hole':>5} {'par':>4} {'yards':>6}  green  fairway  bunkers  water  trees")

    for hole in sorted(course.holes, key=lambda h: h.number):
        lines.append(
            f"{hole.number:>5} {hole.par or '?':>4} {hole.length_m * 1.09361:>6.0f}"
            f"  {'yes' if hole.green else ' NO':>5}"
            f"  {len(hole.fairways):>7}"
            f"  {len(hole.bunkers):>7}"
            f"  {len(hole.water):>5}"
            f"  {len(hole.trees):>5}"
        )

    missing_green = [h.number for h in course.holes if not h.green]
    missing_par = [h.number for h in course.holes if h.par is None]
    if missing_green:
        lines += ["", f"WARNING: no green found for holes {missing_green}"]
    if missing_par:
        lines += [f"WARNING: no par tagged for holes {missing_par}"]

    return "\n".join(lines)
