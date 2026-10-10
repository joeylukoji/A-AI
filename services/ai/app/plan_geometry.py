"""Primitives géométriques partagées, indépendantes du moteur de placement."""

from __future__ import annotations

import math
from typing import Any


def room_bounds(room: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """Return the bounding box of a room with at least three polygon vertices."""
    polygon = room.get("polygon") or []
    if len(polygon) < 3:
        return None
    xs = [float(point["x"]) for point in polygon]
    ys = [float(point["y"]) for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def opening_segment(
    wall: dict[str, Any], opening: dict[str, Any]
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Project an opening's offset from wall.a, preserving wall orientation.

    An invalid or out-of-wall opening is not relocated or silently shortened.
    The caller can omit it from drawing; domain validation must report it.
    """
    try:
        ax, ay = float(wall["a"]["x"]), float(wall["a"]["y"])
        bx, by = float(wall["b"]["x"]), float(wall["b"]["y"])
        offset = float(opening.get("offset_m", 0))
        width = float(opening["width_m"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (ax, ay, bx, by, offset, width)):
        return None
    length = math.hypot(bx - ax, by - ay)
    if length <= 0 or width <= 0 or offset < 0 or offset + width > length + 1e-6:
        return None
    ux, uy = (bx - ax) / length, (by - ay) / length
    return (ax + ux * offset, ay + uy * offset), (
        ax + ux * (offset + width),
        ay + uy * (offset + width),
    )
