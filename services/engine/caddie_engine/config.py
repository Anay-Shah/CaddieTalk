"""Locating and loading the tunable data files.

Every number the engine can be argued with about lives in `data/`, never in code, so that
tuning is an edit to a config file rather than a code change and a redeploy.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path

import yaml


def find_data_dir() -> Path:
    """The repo's `data/` directory.

    Checked in order: the `CADDIETALK_DATA` environment variable (which is how the Lambda
    container points at its bundled copy), then upwards from this file.
    """
    override = os.environ.get("CADDIETALK_DATA")
    if override:
        return Path(override)

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data"
        if (candidate / "config").is_dir():
            return candidate

    raise FileNotFoundError(
        "Could not locate the data/ directory. Set CADDIETALK_DATA to point at it."
    )


@functools.cache
def load_yaml(name: str) -> dict:
    """Load `data/config/<name>.yaml`. Cached — these files don't change at runtime."""
    path = find_data_dir() / "config" / f"{name}.yaml"
    return yaml.safe_load(path.read_text())


def engine_config() -> dict:
    return load_yaml("engine")


def clubs_config() -> dict:
    return load_yaml("clubs")


YARDS_PER_METRE = 1.0936133
METRES_PER_YARD = 0.9144


def to_yards(metres: float) -> float:
    return metres * YARDS_PER_METRE


def to_metres(yards: float) -> float:
    return yards * METRES_PER_YARD
