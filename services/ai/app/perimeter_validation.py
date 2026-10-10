"""Coverage of the rectangular envelope by already validated wall segments."""

from __future__ import annotations

from typing import Any

from app.opening_intervals import EPSILON_M
from app.plan_contracts import PlanDocumentError


def _covers_side(intervals: list[tuple[float, float]], length: float) -> bool:
    covered = 0.0
    for start, end in sorted(intervals):
        if start > covered + EPSILON_M:
            return False
        covered = max(covered, end)
    return covered >= length - EPSILON_M


def validate_perimeter(walls: list[dict[str, Any]], bounds: tuple[float, float]) -> None:
    """Require four covered sides, independent of wall IDs and endpoint order.

    Call after structural, numeric and bounds validation. Windows and doors do
    not remove intervals from their supporting wall's envelope representation.
    """
    width, depth = bounds
    sides: list[list[tuple[float, float]]] = [[], [], [], []]
    for wall in walls:
        ax, ay = float(wall["a"]["x"]), float(wall["a"]["y"])
        bx, by = float(wall["b"]["x"]), float(wall["b"]["y"])
        horizontal = (min(ax, bx), max(ax, bx))
        vertical = (min(ay, by), max(ay, by))
        if abs(ay) <= EPSILON_M and abs(by) <= EPSILON_M:
            sides[0].append(horizontal)
        if abs(ax - width) <= EPSILON_M and abs(bx - width) <= EPSILON_M:
            sides[1].append(vertical)
        if abs(ay - depth) <= EPSILON_M and abs(by - depth) <= EPSILON_M:
            sides[2].append(horizontal)
        if abs(ax) <= EPSILON_M and abs(bx) <= EPSILON_M:
            sides[3].append(vertical)
    for side, (intervals, length) in enumerate(zip(sides, (width, depth, width, depth), strict=True)):
        if not _covers_side(intervals, length):
            raise PlanDocumentError("incomplete_perimeter", f"walls.side[{side}]")
