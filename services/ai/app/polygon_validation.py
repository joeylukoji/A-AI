"""Simple polygon and pairwise interior-area checks without rendering dependencies."""

from __future__ import annotations

import math

from app.opening_intervals import EPSILON_M
from app.plan_contracts import PlanDocumentError

Point2D = tuple[float, float]
Polygon2D = list[Point2D]
AREA_EPSILON_M2 = 1e-6


def _cross(a: Point2D, b: Point2D, c: Point2D) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _near(a: Point2D, b: Point2D) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= EPSILON_M


def _on_segment(point: Point2D, a: Point2D, b: Point2D) -> bool:
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    return (
        abs(_cross(a, b, point)) <= EPSILON_M * length
        and min(a[0], b[0]) - EPSILON_M <= point[0] <= max(a[0], b[0]) + EPSILON_M
        and min(a[1], b[1]) - EPSILON_M <= point[1] <= max(a[1], b[1]) + EPSILON_M
    )


def _segments_touch(a: Point2D, b: Point2D, c: Point2D, d: Point2D) -> bool:
    abc, abd, cda, cdb = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    opposite_ab = (abc > 0 and abd < 0) or (abc < 0 and abd > 0)
    opposite_cd = (cda > 0 and cdb < 0) or (cda < 0 and cdb > 0)
    return (
        (opposite_ab and opposite_cd)
        or _on_segment(c, a, b)
        or _on_segment(d, a, b)
        or _on_segment(a, c, d)
        or _on_segment(b, c, d)
    )


def simple_polygon(points: Polygon2D, path: str) -> Polygon2D:
    """Normalize an optional closing vertex; reject self-touch and backtracking."""
    polygon = points[:-1] if len(points) > 3 and _near(points[0], points[-1]) else points
    count = len(polygon)
    if count < 3:
        raise PlanDocumentError("invalid_room_polygon", path)
    for index, point in enumerate(polygon):
        next_point = polygon[(index + 1) % count]
        if _near(point, next_point):
            raise PlanDocumentError("invalid_room_polygon", path)
        for other in polygon[index + 1 :]:
            if _near(point, other):
                raise PlanDocumentError("invalid_room_polygon", path)
        before = polygon[(index - 1) % count]
        incoming = (point[0] - before[0], point[1] - before[1])
        outgoing = (next_point[0] - point[0], next_point[1] - point[1])
        adjacent_length = max(math.hypot(*incoming), math.hypot(*outgoing))
        if abs(_cross(before, point, next_point)) <= EPSILON_M * adjacent_length:
            if incoming[0] * outgoing[0] + incoming[1] * outgoing[1] < 0:
                raise PlanDocumentError("invalid_room_polygon", path)
    for first in range(count):
        a, b = polygon[first], polygon[(first + 1) % count]
        for second in range(first + 1, count):
            if second == first + 1 or (first == 0 and second == count - 1):
                continue
            c, d = polygon[second], polygon[(second + 1) % count]
            if _segments_touch(a, b, c, d):
                raise PlanDocumentError("invalid_room_polygon", path)
    return polygon


def _edges(polygon: Polygon2D):
    return zip(polygon, polygon[1:] + polygon[:1], strict=True)


def _crossing_ordinates(first: Polygon2D, second: Polygon2D) -> list[float]:
    values = [point[1] for point in first + second]
    for a, b in _edges(first):
        rx, ry = b[0] - a[0], b[1] - a[1]
        for c, d in _edges(second):
            sx, sy = d[0] - c[0], d[1] - c[1]
            denominator = rx * sy - ry * sx
            if abs(denominator) <= 1e-12:
                continue
            dx, dy = c[0] - a[0], c[1] - a[1]
            t = (dx * sy - dy * sx) / denominator
            u = (dx * ry - dy * rx) / denominator
            if 0 <= t <= 1 and 0 <= u <= 1:
                values.append(a[1] + t * ry)
    return sorted(set(values))


def _intervals_at_y(polygon: Polygon2D, y: float) -> list[tuple[float, float]]:
    crossings: list[float] = []
    for a, b in _edges(polygon):
        if (a[1] <= y < b[1]) or (b[1] <= y < a[1]):
            crossings.append(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
    crossings.sort()
    return list(zip(crossings[::2], crossings[1::2], strict=True))


def intersection_area(first: Polygon2D, second: Polygon2D) -> float:
    """Integrate horizontal interval overlap between all topology breakpoints."""
    ys = _crossing_ordinates(first, second)
    area = 0.0
    for low, high in zip(ys[:-1], ys[1:], strict=True):
        if high <= low:
            continue
        y = low + (high - low) / 2
        a_intervals, b_intervals = _intervals_at_y(first, y), _intervals_at_y(second, y)
        row_width = sum(
            max(0.0, min(a_end, b_end) - max(a_start, b_start))
            for a_start, a_end in a_intervals
            for b_start, b_end in b_intervals
        )
        area += row_width * (high - low)
    return area


def validate_room_overlaps(polygons: list[Polygon2D]) -> None:
    """Reject positive interior overlap; shared edges and points are allowed."""
    for first_index, first in enumerate(polygons):
        for second_index in range(first_index + 1, len(polygons)):
            second = polygons[second_index]
            if intersection_area(first, second) > AREA_EPSILON_M2:
                raise PlanDocumentError("overlapping_rooms", f"rooms[{first_index}],rooms[{second_index}]")
