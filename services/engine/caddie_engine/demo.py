"""Visual check of a recommendation on a real hole.

M2 is only trustworthy if the recommendations look sensible to someone who plays golf, and
a heatmap of where the simulated shots actually land is the fastest way to judge that. A
number like "expected score 4.21" is impossible to sanity-check by eye; a picture of 3,000
golf balls scattered across a fairway is not.
"""

from __future__ import annotations

from pathlib import Path

from .config import to_yards
from .geometry import HoleModel
from .optimize import Recommendation

SURFACE_STYLE = {
    "recovery": ("#cfe0c4", "#9bb38f", 1),
    "fairway": ("#a8d5a2", "#6da368", 2),
    "water": ("#9ec9e8", "#4a89b5", 3),
    "green": ("#5fbf60", "#2f7a32", 4),
    "sand": ("#f2e2b6", "#c9b078", 5),
}


def _draw_surface(ax, geometry, style) -> None:
    from matplotlib.patches import Polygon as MplPolygon

    if geometry is None or geometry.is_empty:
        return
    face, edge, z = style
    parts = geometry.geoms if geometry.geom_type == "MultiPolygon" else [geometry]
    for part in parts:
        ax.add_patch(
            MplPolygon(
                list(part.exterior.coords),
                closed=True,
                facecolor=face,
                edgecolor=edge,
                linewidth=0.8,
                zorder=z,
            )
        )


def plot_recommendation(
    hole: HoleModel,
    recommendation: Recommendation,
    start_xy: tuple[float, float],
    output_path: Path,
    title: str | None = None,
) -> Path:
    """Render the hole, where the recommended shot lands, and the aim point."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, ax = plt.subplots(figsize=(8, 9))

    for name, style in SURFACE_STYLE.items():
        _draw_surface(ax, getattr(hole, name, None), style)

    landings = recommendation.best.outcome.landing_xy
    ax.hexbin(
        landings[:, 0],
        landings[:, 1],
        gridsize=45,
        cmap="inferno_r",
        mincnt=1,
        alpha=0.75,
        zorder=6,
    )

    ax.plot(*start_xy, "o", color="#1b1b1b", markersize=8, zorder=9, label="ball")
    ax.plot(*hole.pin_xy, "*", color="#c0392b", markersize=16, zorder=9, label="pin")
    ax.plot(
        *recommendation.best.aim_xy,
        "x",
        color="#1f6fb2",
        markersize=13,
        markeredgewidth=3,
        zorder=9,
        label="aim",
    )
    ax.plot(
        [start_xy[0], recommendation.best.aim_xy[0]],
        [start_xy[1], recommendation.best.aim_xy[1]],
        "--",
        color="#1f6fb2",
        linewidth=1.2,
        zorder=8,
    )

    ax.set_aspect("equal")
    ax.axis("off")
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)

    if title is None:
        distance = to_yards(
            ((hole.pin_xy[0] - start_xy[0]) ** 2 + (hole.pin_xy[1] - start_xy[1]) ** 2) ** 0.5
        )
        title = f"Hole {hole.number} · {distance:.0f} yds to pin"
    ax.set_title(f"{title}\n{recommendation.summary()}", fontsize=10, loc="left")

    figure.tight_layout()
    figure.savefig(output_path, dpi=120)
    plt.close(figure)
    return output_path
