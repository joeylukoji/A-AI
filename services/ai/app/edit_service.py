"""Application service for editing a plan through explicit internal commands."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from copy import deepcopy
import math
from typing import Any

from app.edit_commands import EditCommand, EditCommandError, parse_edit_command
from app.furnish import CATALOG
from app.plan_contracts import PlanDocumentError
from app.polygon_validation import intersection_area


def edit_plan(
    instruction: str,
    *,
    brief: str = "",
    constraints: dict[str, Any] | None = None,
    spec: dict[str, Any] | None = None,
    plan_document: dict[str, Any] | None = None,
    image_png_b64: str = "",
    job_id: str | None = None,
    interpret: Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any]],
    rebuild: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    render_document: Callable[[dict[str, Any]], str],
    notify_step: Callable[[str | None, str], None],
    validate_document: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    """Run one edit request and keep the vector document as the source of truth.

    The interpreter and integrations are injected so this service does not depend on
    FastAPI, persistence, or a specific image provider.
    """
    instruction = (instruction or "").strip()
    constraints = dict(constraints or {})
    spec = dict(spec or {})
    if brief and not spec.get("brief"):
        spec["brief"] = brief
    document = deepcopy(plan_document or {})
    interpreted = interpret(instruction, spec, document)
    reply_fr = interpreted["reply_fr"]
    clarification = bool(interpreted.get("clarify"))
    adapted: dict[str, Any] = {}
    applied = False
    steps = ["edit"]

    notify_step(job_id, "edit")
    if clarification:
        preview = (
            render_document(document) if document else (image_png_b64 or "").strip()
        )
        method = "edit-clarify"
        if document:
            steps.append("render")
    elif interpreted.get("rooms"):
        command = _parse_command(
            {
                "version": 1,
                "action": "replace_program",
                "program": interpreted["rooms"],
                "reply_fr": reply_fr,
            }
        )
        spec["rooms"] = _program_as_spec(command)
        adapted = rebuild(spec, _rebuild_constraints(constraints, document))
        document = _rebuilt_document(adapted)
        _reconcile_rebuilt_room_ids(adapted, plan_document or {})
        document = _rebuilt_document(adapted)
        reply_fr = _with_rebuild_warning(reply_fr, plan_document or {}, document)
        validate_document(document)
        applied = True
        steps.extend(["rebuild", "validate", "render"])
        preview = render_document(document)
        method = "procedural+edit"
    elif interpreted.get("command"):
        command = _parse_command(interpreted["command"])
        if command.action in {"replace_program", "remove_room"}:
            if command.action == "remove_room":
                replacement = _replacement_after_room_removal(command, document, spec)
                replacement_command = _parse_command(
                    {"version": 1, "action": "replace_program", "program": replacement}
                )
                spec["rooms"] = _program_as_spec(replacement_command)
            else:
                spec["rooms"] = _program_as_spec(command)
            adapted = rebuild(spec, _rebuild_constraints(constraints, document))
            document = _rebuilt_document(adapted)
            _reconcile_rebuilt_room_ids(
                adapted,
                plan_document or {},
                excluded_room_id=command.target_id
                if command.action == "remove_room"
                else None,
            )
            document = _rebuilt_document(adapted)
            reply_fr = _with_rebuild_warning(reply_fr, plan_document or {}, document)
            steps.extend(["rebuild", "validate", "render"])
        else:
            document = apply_edit_command(document, command)
            adapted = {"plan_document": document}
            steps.extend(["apply", "validate", "render"])
        validate_document(document)
        applied = True
        preview = render_document(document)
        method = "procedural+edit"
    else:
        reply_fr = (
            "Pour modifier le plan, précisez la pièce, le meuble ou l'ouverture à cibler et "
            "la modification souhaitée."
        )
        clarification = True
        preview = (
            render_document(document) if document else (image_png_b64 or "").strip()
        )
        method = "edit-clarify"
        if document:
            steps.append("render")

    if not adapted and document:
        adapted = {
            "plan_document": document,
            "compliance": {},
            "dimensions": [],
            "parcel": {},
            "rules": {},
        }
    return {
        "building_spec": spec,
        "plan_document": document,
        "compliance": adapted.get("compliance") or {},
        "dimensions": adapted.get("dimensions") or [],
        "parcel": adapted.get("parcel") or {},
        "rules": adapted.get("rules") or {},
        "preview_key": "",
        "image_png_b64": preview,
        "reply_fr": reply_fr,
        "edit_en": interpreted["edit_en"],
        "method": method,
        "clarify": clarification,
        "edit_status": "applied" if applied else "clarification_required",
        "steps": steps,
    }


def _parse_command(value: Any) -> EditCommand:
    try:
        return parse_edit_command(value)
    except EditCommandError as exc:
        raise PlanDocumentError(exc.code, exc.field) from exc


def _with_rebuild_warning(
    reply: str, previous: dict[str, Any], current: dict[str, Any]
) -> str:
    lowered = reply.casefold()
    message = reply.rstrip()
    if not any(word in lowered for word in ("repav", "redessin", "reconstru")):
        message = f"{message} Le plan est repavé.".strip()
    lost = _lost_element_ids(previous, current)
    if lost:
        details = "; ".join(f"{kind}: {', '.join(ids)}" for kind, ids in lost.items())
        message = f"{message} Éléments non conservés: {details}."
    previous_layout = previous.get("layout")
    if previous_layout is not None and previous_layout != current.get("layout"):
        message = f"{message} Le choix d'implantation a été ajusté pour respecter le nouveau programme."
    return message


def _rebuild_constraints(
    constraints: dict[str, Any], document: dict[str, Any]
) -> dict[str, Any]:
    rebuilt = dict(constraints)
    rebuilt.pop("_aai_source_layout", None)
    layout = document.get("layout")
    if isinstance(layout, dict):
        rebuilt["_aai_source_layout"] = deepcopy(layout)
    return rebuilt


def _lost_element_ids(
    previous: dict[str, Any], current: dict[str, Any]
) -> dict[str, list[str]]:
    lost: dict[str, list[str]] = {}
    for collection in ("rooms", "walls", "openings", "furniture"):
        current_ids = {
            item.get("id")
            for item in current.get(collection, [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        missing_ids = [
            item["id"]
            for item in previous.get(collection, [])
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item["id"] not in current_ids
        ]
        if missing_ids:
            lost[collection] = missing_ids
    return lost


def _rebuilt_document(adapted: dict[str, Any]) -> dict[str, Any]:
    document = adapted.get("plan_document") if isinstance(adapted, dict) else None
    if not isinstance(document, dict) or not document:
        raise PlanDocumentError("invalid_result", "plan_document")
    return document


def _program_as_spec(
    command: EditCommand,
) -> list[dict[str, Any]]:
    """Keep generator IDs independent from editor identity metadata."""
    return [
        {
            "type": room.room_type,
            "count": room.count,
            **({"area_m2": room.area_m2} if room.area_m2 is not None else {}),
        }
        for room in command.program
    ]


def _reconcile_rebuilt_room_ids(
    adapted: dict[str, Any],
    previous: dict[str, Any],
    *,
    excluded_room_id: str | None = None,
) -> None:
    """Restore IDs only for unambiguous same-type geometric correspondences."""
    document = _rebuilt_document(adapted)
    source_rooms: list[dict[str, Any]] = []
    previous_rooms = [
        room
        for room in previous.get("rooms", [])
        if isinstance(room, dict) and isinstance(room.get("id"), str)
    ]
    source_id_counts = Counter(room["id"] for room in previous_rooms)
    for room in previous_rooms:
        if source_id_counts[room["id"]] == 1 and room.get("id") != excluded_room_id:
            source_rooms.append(room)
    occupied = {
        str(item.get("id"))
        for collection in ("walls", "openings", "furniture")
        for item in document.get(collection, [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    reserved = {
        str(item.get("id"))
        for collection in ("rooms", "walls", "openings", "furniture")
        for item in previous.get(collection, [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    } | occupied
    rebuilt_rooms = [
        room for room in document.get("rooms", []) if isinstance(room, dict)
    ]
    generated_ids = [room.get("id") for room in rebuilt_rooms]
    if any(not isinstance(room_id, str) for room_id in generated_ids) or len(
        set(generated_ids)
    ) != len(generated_ids):
        raise PlanDocumentError("invalid_result", "rooms.id")

    matched_ids = _unambiguous_room_matches(source_rooms, rebuilt_rooms)
    mapping: dict[str, str] = {}
    next_id = 1
    for room in rebuilt_rooms:
        generated_id = room.get("id")
        room_id = matched_ids.get(id(room))
        if room_id in occupied:
            room_id = None
        if room_id is None:
            while f"edit_r{next_id}" in reserved:
                next_id += 1
            room_id = f"edit_r{next_id}"
            next_id += 1
        mapping[generated_id] = room_id
        room["id"] = room_id

    for furniture in document.get("furniture", []):
        if isinstance(furniture, dict) and furniture.get("room_id") in mapping:
            furniture["room_id"] = mapping[furniture["room_id"]]
    for item in document.get("program", []):
        if isinstance(item, dict) and item.get("id") in mapping:
            item["id"] = mapping[item["id"]]
    for item in adapted.get("dimensions", []):
        if isinstance(item, dict) and item.get("id") in mapping:
            item["id"] = mapping[item["id"]]


def _unambiguous_room_matches(
    source_rooms: list[dict[str, Any]], rebuilt_rooms: list[dict[str, Any]]
) -> dict[int, str]:
    """Match rooms by mutual, clearly dominant polygon IoU, never list order."""
    scores: dict[tuple[int, int], float] = {}
    for source_index, source in enumerate(source_rooms):
        source_polygon = _safe_room_coordinates(source)
        if source_polygon is None:
            continue
        source_area = _coordinates_area(source_polygon)
        for rebuilt_index, rebuilt in enumerate(rebuilt_rooms):
            if source.get("type") != rebuilt.get("type"):
                continue
            rebuilt_polygon = _safe_room_coordinates(rebuilt)
            if rebuilt_polygon is None:
                continue
            rebuilt_area = _coordinates_area(rebuilt_polygon)
            union = (
                source_area
                + rebuilt_area
                - intersection_area(source_polygon, rebuilt_polygon)
            )
            if union > 1e-9:
                scores[(source_index, rebuilt_index)] = (
                    intersection_area(source_polygon, rebuilt_polygon) / union
                )

    def dominant(values: list[tuple[int, float]]) -> int | None:
        ranked = sorted(values, key=lambda item: item[1], reverse=True)
        if not ranked or ranked[0][1] < 0.25:
            return None
        if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < 0.1:
            return None
        return ranked[0][0]

    source_best = {
        source_index: dominant(
            [
                (rebuilt_index, score)
                for (candidate_source, rebuilt_index), score in scores.items()
                if candidate_source == source_index
            ]
        )
        for source_index in range(len(source_rooms))
    }
    rebuilt_best = {
        rebuilt_index: dominant(
            [
                (source_index, score)
                for (source_index, candidate_rebuilt), score in scores.items()
                if candidate_rebuilt == rebuilt_index
            ]
        )
        for rebuilt_index in range(len(rebuilt_rooms))
    }
    return {
        id(rebuilt_rooms[rebuilt_index]): source_rooms[source_index]["id"]
        for rebuilt_index, source_index in rebuilt_best.items()
        if source_index is not None and source_best.get(source_index) == rebuilt_index
    }


def _safe_room_coordinates(room: dict[str, Any]) -> list[tuple[float, float]] | None:
    try:
        polygon = _polygon_coordinates(room.get("polygon") or [])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if len(polygon) < 3 or not all(
        math.isfinite(value) for point in polygon for value in point
    ):
        return None
    return polygon if _coordinates_area(polygon) > 1e-9 else None


def _replacement_after_room_removal(
    command: EditCommand, document: dict[str, Any], spec: dict[str, Any]
) -> list[dict[str, Any]]:
    rooms = document.get("rooms")
    if not isinstance(rooms, list):
        raise PlanDocumentError("invalid_result", "rooms")
    target = next(
        (
            room
            for room in rooms
            if isinstance(room, dict) and room.get("id") == command.target_id
        ),
        None,
    )
    if target is None:
        raise PlanDocumentError("target_not_found", str(command.target_id))
    remaining = [room for room in rooms if room is not target]
    if len(remaining) < 2:
        raise PlanDocumentError("constraint_violation", "rooms")
    counts: dict[str, int] = {}
    for room in remaining:
        room_type = room.get("type")
        if isinstance(room_type, str):
            counts[room_type] = counts.get(room_type, 0) + 1
    old_requests = {
        item.get("type"): item
        for item in (spec.get("rooms") or [])
        if isinstance(item, dict)
    }
    replacement = []
    for room_type, count in counts.items():
        old = old_requests.get(room_type, {})
        replacement.append(
            {
                "type": room_type,
                "count": count,
                "area_m2": old.get("area_m2") or _mean_room_area(room_type, remaining),
            }
        )
    return replacement


def _mean_room_area(room_type: str, rooms: list[dict[str, Any]]) -> float:
    matching = [room for room in rooms if room.get("type") == room_type]
    areas = [abs(_polygon_area(room.get("polygon") or [])) for room in matching]
    return sum(areas) / len(areas)


def _polygon_area(polygon: list[dict[str, Any]]) -> float:
    if len(polygon) < 3:
        return 0.0
    twice_area = sum(
        point["x"] * polygon[(index + 1) % len(polygon)]["y"]
        - polygon[(index + 1) % len(polygon)]["x"] * point["y"]
        for index, point in enumerate(polygon)
    )
    return twice_area / 2


def apply_edit_command(
    document: dict[str, Any], command: EditCommand
) -> dict[str, Any]:
    """Apply a local command to a copy of a PlanDocument."""
    result = deepcopy(document)
    if command.action in {"add_furniture", "move_furniture", "remove_furniture"}:
        furniture = result.setdefault("furniture", [])
        target = next(
            (item for item in furniture if item.get("id") == command.target_id), None
        )
        if command.action == "add_furniture":
            item_spec = CATALOG.get(command.catalog_id or "")
            if item_spec is None:
                raise PlanDocumentError("invalid_payload", "catalog_id")
            room = _room_by_id(result, command.target_room_id)
            _ensure_furniture_placement(
                result,
                room,
                command.position,
                command.catalog_id or "",
                item_spec,
                command.rotation_deg or 0.0,
            )
            furniture.append(
                {
                    "id": _next_id("edit_f", result),
                    "catalog_id": command.catalog_id,
                    "room_id": command.target_room_id,
                    "position": {"x": command.position[0], "y": command.position[1]},
                    "rotation_deg": command.rotation_deg or 0.0,
                    "size_m": {key: item_spec[key] for key in ("w", "d", "h")},
                }
            )
        elif target is None:
            raise PlanDocumentError("target_not_found", str(command.target_id))
        elif command.action == "remove_furniture":
            furniture.remove(target)
        else:
            room = _room_by_id(result, target.get("room_id"))
            catalog_id = str(target.get("catalog_id") or "")
            item_spec = CATALOG.get(catalog_id)
            _ensure_furniture_placement(
                result,
                room,
                command.position,
                catalog_id,
                target.get("size_m") or item_spec or {},
                float(target.get("rotation_deg") or 0.0),
                exclude_id=command.target_id,
            )
            target["position"] = {"x": command.position[0], "y": command.position[1]}
    elif command.action in {"add_opening", "move_opening", "remove_opening"}:
        openings = result.setdefault("openings", [])
        target = next(
            (item for item in openings if item.get("id") == command.target_id), None
        )
        if command.action == "add_opening":
            if not any(
                wall.get("id") == command.target_id for wall in result.get("walls", [])
            ):
                raise PlanDocumentError("target_not_found", str(command.target_id))
            openings.append(
                {
                    "id": _next_id("edit_o", result),
                    "wall_id": command.target_id,
                    "type": command.opening_type,
                    "offset_m": command.offset_m,
                    "width_m": command.width_m,
                }
            )
        elif target is None:
            raise PlanDocumentError("target_not_found", str(command.target_id))
        elif command.action == "remove_opening":
            openings.remove(target)
        else:
            target["offset_m"] = command.offset_m
    elif command.action == "move_room":
        _move_room(result, command)
    else:
        raise PlanDocumentError("unknown_action", command.action)
    return result


def _room_by_id(document: dict[str, Any], room_id: str | None) -> dict[str, Any]:
    room = next(
        (item for item in document.get("rooms", []) if item.get("id") == room_id), None
    )
    if room is None:
        raise PlanDocumentError("target_not_found", str(room_id))
    return room


def _point_in_polygon(
    point: tuple[float, float] | None, polygon: list[dict[str, Any]]
) -> bool:
    if point is None or len(polygon) < 3:
        return False
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        ax, ay = float(previous["x"]), float(previous["y"])
        bx, by = float(current["x"]), float(current["y"])
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
        previous = current
    return inside


def _ensure_furniture_placement(
    document: dict[str, Any],
    room: dict[str, Any],
    position: tuple[float, float] | None,
    catalog_id: str,
    size_m: dict[str, Any],
    rotation_deg: Any,
    *,
    exclude_id: str | None = None,
) -> None:
    if position is None:
        raise PlanDocumentError("invalid_payload", "position")
    footprint = _rectangle_footprint(position, size_m, rotation_deg)
    room_polygon = _polygon_coordinates(room.get("polygon") or [])
    footprint_area = _coordinates_area(footprint)
    if intersection_area(room_polygon, footprint) < footprint_area - 1e-6:
        raise PlanDocumentError("constraint_violation", "furniture.position")

    for existing in document.get("furniture", []):
        if not isinstance(existing, dict) or existing.get("id") == exclude_id:
            continue
        existing_catalog_id = str(existing.get("catalog_id") or "")
        if catalog_id.startswith("rug") or existing_catalog_id.startswith("rug"):
            continue
        existing_position = existing.get("position")
        if not isinstance(existing_position, dict):
            raise PlanDocumentError("invalid_result", "furniture.position")
        catalog_item = CATALOG.get(existing_catalog_id) or {}
        existing_size = existing.get("size_m") or catalog_item
        existing_footprint = _rectangle_footprint(
            (existing_position.get("x"), existing_position.get("y")),
            existing_size,
            float(existing.get("rotation_deg") or 0.0),
        )
        if intersection_area(footprint, existing_footprint) > 1e-6:
            raise PlanDocumentError("constraint_violation", "furniture.position")


def _rectangle_footprint(
    position: tuple[Any, Any], size_m: dict[str, Any], rotation_deg: Any
) -> list[tuple[float, float]]:
    try:
        x, y = float(position[0]), float(position[1])
        width, depth = float(size_m["w"]), float(size_m["d"])
        rotation = math.radians(float(rotation_deg))
    except (TypeError, ValueError, KeyError, IndexError, OverflowError) as exc:
        raise PlanDocumentError("invalid_result", "furniture.geometry") from exc
    if not all(math.isfinite(value) for value in (x, y, width, depth, rotation)):
        raise PlanDocumentError("invalid_result", "furniture.geometry")
    if width <= 0 or depth <= 0:
        raise PlanDocumentError("invalid_result", "furniture.size_m")
    cosine, sine = math.cos(rotation), math.sin(rotation)
    return [
        (
            x + local_x * cosine - local_y * sine,
            y + local_x * sine + local_y * cosine,
        )
        for local_x, local_y in (
            (-width / 2, -depth / 2),
            (width / 2, -depth / 2),
            (width / 2, depth / 2),
            (-width / 2, depth / 2),
        )
    ]


def _polygon_coordinates(polygon: list[dict[str, Any]]) -> list[tuple[float, float]]:
    return [(float(point["x"]), float(point["y"])) for point in polygon]


def _coordinates_area(polygon: list[tuple[float, float]]) -> float:
    return (
        abs(
            sum(
                x1 * y2 - x2 * y1
                for (x1, y1), (x2, y2) in zip(
                    polygon, polygon[1:] + polygon[:1], strict=True
                )
            )
        )
        / 2
    )


def _next_id(prefix: str, document: dict[str, Any]) -> str:
    existing = {
        str(item.get("id"))
        for collection in ("rooms", "walls", "openings", "furniture")
        for item in document.get(collection, [])
        if isinstance(item, dict)
    }
    index = 1
    while f"{prefix}{index}" in existing:
        index += 1
    return f"{prefix}{index}"


def _move_room(document: dict[str, Any], command: EditCommand) -> None:
    room = _room_by_id(document, command.target_id)
    dx, dy = command.position
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        raise PlanDocumentError("constraint_violation", "position")
    polygon = room.get("polygon") or []
    old_edges = _polygon_edges(polygon)
    adjacent_edges = [
        edge
        for other in document.get("rooms", [])
        if other is not room
        for edge in _polygon_edges(other.get("polygon") or [])
    ]
    for wall in document.get("walls", []):
        wall_edge = (wall.get("a"), wall.get("b"))
        if not any(_same_edge(wall_edge, edge) for edge in old_edges):
            continue
        if str(wall.get("id", "")).startswith("w_outer") or any(
            _same_edge(wall_edge, edge) for edge in adjacent_edges
        ):
            continue
        for endpoint in ("a", "b"):
            wall[endpoint]["x"] += dx
            wall[endpoint]["y"] += dy
    room["polygon"] = [
        {"x": point["x"] + dx, "y": point["y"] + dy} for point in polygon
    ]
    for edge in _polygon_edges(room["polygon"]):
        if any(
            _same_edge(edge, (wall.get("a"), wall.get("b")))
            for wall in document.get("walls", [])
        ):
            continue
        document.setdefault("walls", []).append(
            {
                "id": _next_id("edit_w", document),
                "a": deepcopy(edge[0]),
                "b": deepcopy(edge[1]),
                "thickness_m": 0.15,
            }
        )
    moved_furniture = []
    for item in document.get("furniture", []):
        if item.get("room_id") == room["id"]:
            item["position"]["x"] += dx
            item["position"]["y"] += dy
            moved_furniture.append(item)
    for item in moved_furniture:
        catalog_id = str(item.get("catalog_id") or "")
        _ensure_furniture_placement(
            document,
            room,
            (item["position"]["x"], item["position"]["y"]),
            catalog_id,
            item.get("size_m") or CATALOG.get(catalog_id) or {},
            item.get("rotation_deg") or 0.0,
            exclude_id=item.get("id"),
        )


def _polygon_edges(
    polygon: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [
        (polygon[index], polygon[(index + 1) % len(polygon)])
        for index in range(len(polygon))
    ]


def _same_edge(
    first: tuple[dict[str, Any], dict[str, Any]],
    second: tuple[dict[str, Any], dict[str, Any]],
) -> bool:
    def same_point(a: dict[str, Any], b: dict[str, Any]) -> bool:
        return abs(a["x"] - b["x"]) < 1e-6 and abs(a["y"] - b["y"]) < 1e-6

    return (same_point(first[0], second[0]) and same_point(first[1], second[1])) or (
        same_point(first[0], second[1]) and same_point(first[1], second[0])
    )
