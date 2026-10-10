"""Strict interval checks, independent of placement heuristics and rendering."""

from __future__ import annotations

import math
from typing import Any

EPSILON_M = 1e-6


class OpeningGeometryError(RuntimeError):
    """The engine produced openings that cannot be used safely downstream."""

    def __init__(self, code: str, opening_id: str) -> None:
        self.code = code
        self.opening_id = opening_id
        super().__init__(f"{code}: {opening_id}")


def _number(value: Any, label: str) -> float:
    if type(value) not in (int, float):
        raise OpeningGeometryError("invalid_number", label)
    try:
        number = float(value)
    except OverflowError as exc:
        raise OpeningGeometryError("invalid_number", label) from exc
    if not math.isfinite(number):
        raise OpeningGeometryError("invalid_number", label)
    return number


def wall_lengths(walls: list[dict[str, Any]]) -> dict[str, float]:
    """Read unique, finite, non-degenerate orthogonal wall segments."""
    lengths: dict[str, float] = {}
    for wall in walls:
        wall_id = wall.get("id")
        if not isinstance(wall_id, str) or not wall_id or wall_id in lengths:
            raise OpeningGeometryError("invalid_wall_id", str(wall_id))
        coordinates = []
        for end in ("a", "b"):
            point = wall.get(end)
            if not isinstance(point, dict):
                raise OpeningGeometryError("invalid_wall_point", wall_id)
            coordinates.append(tuple(_number(point.get(axis), wall_id) for axis in ("x", "y")))
        a, b = coordinates
        dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
        length = math.hypot(dx, dy)
        if not math.isfinite(length) or length <= EPSILON_M or min(dx, dy) > EPSILON_M:
            raise OpeningGeometryError("invalid_wall_segment", wall_id)
        lengths[wall_id] = length
    return lengths


def opening_interval(opening: dict[str, Any], lengths: dict[str, float]) -> tuple[float, float]:
    """Read a positive interval; bounds are checked separately for placement."""
    opening_id = str(opening.get("id"))
    wall_id = opening.get("wall_id")
    if not isinstance(wall_id, str) or wall_id not in lengths:
        raise OpeningGeometryError("unknown_wall", opening_id)
    opening_type = opening.get("type")
    if opening_type not in ("door", "window"):
        raise OpeningGeometryError("invalid_opening_type", opening_id)
    _validate_door_semantics(opening, opening_type, opening_id)
    start = _number(opening.get("offset_m"), opening_id)
    width = _number(opening.get("width_m"), opening_id)
    if width <= 0:
        raise OpeningGeometryError("invalid_opening_width", opening_id)
    if not math.isfinite(start + width):
        raise OpeningGeometryError("invalid_number", opening_id)
    return start, start + width


def _validate_door_semantics(opening: dict[str, Any], opening_type: str, opening_id: str) -> None:
    """Validate the optional, inseparable hinge/swing pair on hinged doors."""
    has_hinge = "hinge" in opening
    has_swing = "swing" in opening
    if opening_type != "door" or has_hinge != has_swing:
        if has_hinge or has_swing:
            raise OpeningGeometryError("invalid_door_semantics", opening_id)
        return
    if not has_hinge:
        return
    if opening["hinge"] not in ("start", "end") or opening["swing"] not in (
        "positive",
        "negative",
    ):
        raise OpeningGeometryError("invalid_door_semantic_value", opening_id)


def overlaps(first: tuple[float, float], second: tuple[float, float]) -> bool:
    """Allow boundary contact, but not an interior intersection over tolerance."""
    return min(first[1], second[1]) - max(first[0], second[0]) > EPSILON_M


def validate_openings(walls: list[dict[str, Any]], openings: list[dict[str, Any]]) -> None:
    """Reject invalid references, numbers, bounds, IDs and overlapping openings."""
    lengths = wall_lengths(walls)
    seen: set[str] = set()
    occupied: dict[str, list[tuple[float, float]]] = {}
    for opening in openings:
        opening_id = opening.get("id")
        if not isinstance(opening_id, str) or not opening_id or opening_id in seen:
            raise OpeningGeometryError("invalid_opening_id", str(opening_id))
        seen.add(opening_id)
        interval = opening_interval(opening, lengths)
        wall_id = opening["wall_id"]
        if interval[0] < -EPSILON_M or interval[1] > lengths[wall_id] + EPSILON_M:
            raise OpeningGeometryError("opening_out_of_bounds", opening_id)
        previous = occupied.setdefault(wall_id, [])
        if any(overlaps(interval, other) for other in previous):
            raise OpeningGeometryError("overlapping_openings", opening_id)
        previous.append(interval)


def nearest_free_offset(
    desired: float, width: float, span: tuple[float, float], occupied: list[tuple[float, float]]
) -> float | None:
    """Project onto free intervals; equal-distance ties prefer the lower offset."""
    cursor, end = span
    candidates: list[float] = []
    for start, stop in sorted(occupied) + [(end, end)]:
        if stop < cursor or start > end:
            continue
        gap_end = min(start, end)
        if gap_end - cursor + EPSILON_M >= width:
            candidates.append(max(cursor, min(desired, gap_end - width)))
        cursor = max(cursor, stop)
    return min(candidates, key=lambda offset: (abs(offset - desired), offset)) if candidates else None
