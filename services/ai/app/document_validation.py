"""Shared 2D structure/interval profile; not a complete polygon validity test.

See packages/plan-schema/validation-profile.md. Unknown metadata is preserved.
This module never imports the independent research/benchmark evaluator.
"""

from __future__ import annotations

import math
from typing import Any

from app.opening_intervals import (
    EPSILON_M,
    OpeningGeometryError,
    validate_openings,
    wall_lengths,
)
from app.perimeter_validation import validate_perimeter
from app.plan_contracts import GeneratedDocumentError, PlanDocumentError
from app.polygon_validation import simple_polygon, validate_room_overlaps

AREA_EPSILON_M2 = 1e-6
MAX_ROOMS = 64
MAX_VERTICES_PER_ROOM = 64
MAX_TOTAL_VERTICES = 256


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PlanDocumentError("invalid_structure", path)
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise PlanDocumentError("invalid_structure", path)
    return value


def _number(value: Any, path: str) -> float:
    if type(value) not in (int, float):
        raise PlanDocumentError("invalid_number", path)
    try:
        number = float(value)
    except OverflowError as exc:
        raise PlanDocumentError("invalid_number", path) from exc
    if not math.isfinite(number):
        raise PlanDocumentError("invalid_number", path)
    return number


def _point(value: Any, bounds: tuple[float, float], path: str) -> tuple[float, float]:
    point = _object(value, path)
    x, y = (_number(point.get(axis), f"{path}.{axis}") for axis in ("x", "y"))
    if x < -EPSILON_M or y < -EPSILON_M or x > bounds[0] + EPSILON_M or y > bounds[1] + EPSILON_M:
        raise PlanDocumentError("point_out_of_bounds", path)
    return x, y


def _validate_rooms(rooms: list[Any], bounds: tuple[float, float]) -> list[list[tuple[float, float]]]:
    if len(rooms) > MAX_ROOMS:
        raise PlanDocumentError("geometry_complexity_limit", "rooms")
    seen: set[str] = set()
    polygons: list[list[tuple[float, float]]] = []
    total_vertices = 0
    for index, value in enumerate(rooms):
        path = f"rooms[{index}]"
        room = _object(value, path)
        identifier = room.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise PlanDocumentError("invalid_room_id", path)
        seen.add(identifier)
        polygon = _array(room.get("polygon"), f"{path}.polygon")
        total_vertices += len(polygon)
        if len(polygon) > MAX_VERTICES_PER_ROOM or total_vertices > MAX_TOTAL_VERTICES:
            raise PlanDocumentError("geometry_complexity_limit", f"{path}.polygon")
        if len(polygon) < 3:
            raise PlanDocumentError("invalid_room_polygon", path)
        points = [_point(point, bounds, f"{path}.polygon[{i}]") for i, point in enumerate(polygon)]
        points = simple_polygon(points, path)
        origin_x, origin_y = points[0]
        # Translate before multiplication to reduce cancellation at large coordinates.
        twice_area = 0.0
        for a, b in zip(points[1:-1], points[2:], strict=True):
            twice_area += (a[0] - origin_x) * (b[1] - origin_y) - (a[1] - origin_y) * (b[0] - origin_x)
        if not math.isfinite(twice_area) or abs(twice_area) / 2 <= AREA_EPSILON_M2:
            raise PlanDocumentError("invalid_room_polygon", path)
        polygons.append(points)
    return polygons


def validate_document(value: Any) -> None:
    """Validate without mutation; raise PlanDocumentError with a stable code.

    Acceptance does not imply constructive or regulatory feasibility.
    """
    document = _object(value, "document")
    if document.get("version") != "1.0" or document.get("units") != "m":
        raise PlanDocumentError("invalid_header", "version/units")
    floor = _object(document.get("floor"), "floor")
    raw_bounds = _object(floor.get("bounds"), "floor.bounds")
    bounds = tuple(_number(raw_bounds.get(axis), f"floor.bounds.{axis}") for axis in ("width", "depth"))
    if min(bounds) <= 0:
        raise PlanDocumentError("invalid_bounds", "floor.bounds")
    walls = _array(document.get("walls"), "walls")
    rooms = _array(document.get("rooms"), "rooms")
    openings = _array(document.get("openings", []), "openings")
    if len(walls) < 4:
        raise PlanDocumentError("insufficient_walls", "walls")
    for index, wall in enumerate(walls):
        _object(wall, f"walls[{index}]")
    try:
        wall_lengths(walls)
        for index, wall in enumerate(walls):
            for end in ("a", "b"):
                _point(wall[end], bounds, f"walls[{index}].{end}")
        validate_perimeter(walls, bounds)
        polygons = _validate_rooms(rooms, bounds)
        validate_room_overlaps(polygons)
        for index, opening in enumerate(openings):
            _object(opening, f"openings[{index}]")
        validate_openings(walls, openings)
    except OpeningGeometryError as exc:
        raise PlanDocumentError(exc.code, exc.opening_id) from exc


def validate_generated_document(document: Any) -> None:
    """Mark contract failures at generation boundaries as internal failures."""
    try:
        validate_document(document)
    except PlanDocumentError as exc:
        raise GeneratedDocumentError(exc) from exc
