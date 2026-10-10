"""Independent geometric diagnostics; never imports the placement engine."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

LENGTH_EPS = 1e-6
AREA_EPS = 1e-6


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean coordinate")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite coordinate")
    return number


def _point(value: dict[str, Any]) -> tuple[float, float]:
    return _number(value["x"]), _number(value["y"])


def evaluate(document: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate final geometry, explicit parcel constraints and annotated program.

    Findings are diagnostics, not a building-code certificate. Furniture,
    accessibility and visual fidelity are deliberately marked unmeasured.
    """
    errors: list[str] = []
    if not isinstance(document, dict):
        return {"geometry_valid": False, "errors": ["invalid_document"], "program_match": None}
    document = dict(document)
    rooms: list[tuple[str, str, Polygon]] = []
    walls: dict[str, LineString] = {}
    exterior: list[LineString] = []
    for collection in ("rooms", "walls", "openings", "furniture"):
        items = document.get(collection, [])
        if not isinstance(items, list):
            errors.append(f"{collection}:invalid_collection")
            items = []
        if any(not isinstance(item, dict) for item in items):
            errors.append(f"{collection}:invalid_item")
        document[collection] = [item for item in items if isinstance(item, dict)]
        ids = [item.get("id") for item in document[collection]]
        if any(not isinstance(value, str) or not value for value in ids):
            errors.append(f"{collection}:invalid_ids")
        elif len(set(ids)) != len(ids):
            errors.append(f"{collection}:invalid_ids")
    try:
        bounds = document["floor"]["bounds"]
        width, depth = _number(bounds["width"]), _number(bounds["depth"])
        if width <= 0 or depth <= 0:
            raise ValueError("non-positive bounds")
        envelope = box(0, 0, width, depth)
    except (KeyError, TypeError, ValueError):
        envelope = None
        errors.append("invalid_bounds")
    constraints = case.get("constraints", {})
    try:
        setback = _number(constraints.get("setback_m", 0))
        usable_w = _number(constraints["parcel_width_m"]) - 2 * setback
        usable_d = _number(constraints["parcel_depth_m"]) - 2 * setback
        if setback < 0 or usable_w <= 0 or usable_d <= 0:
            errors.append("impossible_parcel")
        elif envelope is not None and (width > usable_w + LENGTH_EPS or depth > usable_d + LENGTH_EPS):
            errors.append("bounds_outside_parcel")
    except (KeyError, TypeError, ValueError):
        errors.append("invalid_parcel")
    for room in document.get("rooms", []):
        identifier = str(room.get("id"))
        try:
            polygon = Polygon([_point(point) for point in room["polygon"]])
            if not polygon.is_valid or polygon.area <= AREA_EPS:
                raise ValueError("invalid polygon")
            rooms.append((identifier, str(room.get("type")), polygon))
            if envelope is not None and polygon.difference(envelope).area > AREA_EPS:
                errors.append(f"room:{identifier}:outside_bounds")
        except (KeyError, TypeError, ValueError):
            errors.append(f"room:{identifier}:invalid_polygon")
    if not rooms:
        errors.append("no_valid_rooms")
    for (a_id, _, a), (b_id, _, b) in combinations(rooms, 2):
        if a.intersection(b).area > AREA_EPS:
            errors.append(f"rooms:{a_id}:{b_id}:overlap")
    for wall in document.get("walls", []):
        identifier = str(wall.get("id"))
        try:
            segment = LineString([_point(wall["a"]), _point(wall["b"])])
            if segment.length <= LENGTH_EPS:
                raise ValueError("degenerate wall")
            walls[identifier] = segment
            if envelope is not None and not envelope.buffer(LENGTH_EPS).covers(segment):
                errors.append(f"wall:{identifier}:outside_bounds")
            # Current schema marks exterior walls through their boundary position.
            if envelope is not None and envelope.boundary.buffer(LENGTH_EPS).covers(segment):
                exterior.append(segment)
        except (KeyError, TypeError, ValueError):
            errors.append(f"wall:{identifier}:invalid_segment")
    closed = bool(
        envelope is not None
        and exterior
        and envelope.boundary.difference(unary_union(exterior).buffer(LENGTH_EPS)).length <= LENGTH_EPS
    )
    if not closed:
        errors.append("perimeter_not_covered")
    intervals: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for opening in document.get("openings", []):
        identifier = str(opening.get("id"))
        try:
            wall_id = opening["wall_id"]
            length = walls[wall_id].length
            start = _number(opening.get("offset_m", 0))
            end = start + _number(opening["width_m"])
            if start < 0 or end <= start or end > length + LENGTH_EPS:
                raise ValueError("opening outside wall")
            intervals[wall_id].append((start, end, identifier))
        except (KeyError, TypeError, ValueError):
            errors.append(f"opening:{identifier}:invalid_interval_or_wall")
    for values in intervals.values():
        for a, b in combinations(values, 2):
            if min(a[1], b[1]) - max(a[0], b[0]) > LENGTH_EPS:
                errors.append(f"openings:{a[2]}:{b[2]}:overlap")
    counts = Counter(str(room.get("type")) for room in document.get("rooms", []))
    if counts["hallway"]:
        counts["hallway"] = 1
    expected = case.get("expected_rooms")
    program_match = dict(counts) == expected if expected is not None else None
    area_errors = []
    for kind, targets in case.get("target_area_m2", {}).items():
        actual = sorted(polygon.area for _, typ, polygon in rooms if typ == kind)
        if len(actual) == len(targets):
            area_errors.extend(abs(a - b) / b for a, b in zip(actual, sorted(targets), strict=True))
    return {
        "geometry_valid": not errors,
        "errors": sorted(errors),
        "closed_perimeter": closed,
        "room_counts": dict(counts),
        "program_match": program_match,
        "explicit_target_relative_error": sum(area_errors) / len(area_errors) if area_errors else None,
        "explicit_target_count_measured": len(area_errors),
        "unmeasured": ["accessibility", "furniture_clearance", "editor_fidelity", "gemini_fidelity"],
    }
