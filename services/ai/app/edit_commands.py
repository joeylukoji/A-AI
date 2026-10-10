"""Typed, deterministic internal commands for 2D PlanDocument edits."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

EDIT_COMMAND_VERSION = 1
ROOM_TYPES = frozenset(
    {
        "living",
        "kitchen",
        "dining",
        "bedroom",
        "bathroom",
        "wc",
        "hallway",
        "garage",
        "office",
        "storage",
        "laundry",
        "veranda",
    }
)
OPENING_TYPES = frozenset({"door", "window"})
EDIT_ACTIONS = frozenset(
    {
        "move_furniture",
        "add_furniture",
        "remove_furniture",
        "move_opening",
        "add_opening",
        "remove_opening",
        "move_room",
        "remove_room",
        "replace_program",
    }
)

ACTION_FIELDS: dict[str, frozenset[str]] = {
    "move_furniture": frozenset({"target_id", "position"}),
    "add_furniture": frozenset(
        {"target_room_id", "position", "catalog_id", "rotation_deg"}
    ),
    "remove_furniture": frozenset({"target_id"}),
    "move_opening": frozenset({"target_id", "offset_m"}),
    "add_opening": frozenset({"target_id", "opening_type", "offset_m", "width_m"}),
    "remove_opening": frozenset({"target_id"}),
    "move_room": frozenset({"target_id", "position"}),
    "remove_room": frozenset({"target_id"}),
    "replace_program": frozenset({"program"}),
}
REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "move_furniture": frozenset({"target_id", "position"}),
    "add_furniture": frozenset({"target_room_id", "position", "catalog_id"}),
    "remove_furniture": frozenset({"target_id"}),
    "move_opening": frozenset({"target_id", "offset_m"}),
    "add_opening": frozenset({"target_id", "opening_type", "offset_m", "width_m"}),
    "remove_opening": frozenset({"target_id"}),
    "move_room": frozenset({"target_id", "position"}),
    "remove_room": frozenset({"target_id"}),
    "replace_program": frozenset({"program"}),
}

_COMMON_FIELDS = frozenset({"version", "action", "reply_fr"})


class EditCommandError(ValueError):
    """Raised when an edit command does not satisfy the v1 contract."""

    def __init__(self, code: str, field: str = "command") -> None:
        self.code = code
        self.field = field
        super().__init__(f"{code}: {field}")


@dataclass(frozen=True, slots=True)
class RoomRequest:
    """Requested room type, multiplicity and optional target area."""

    room_type: str
    count: int
    area_m2: float | None = None
    room_id: str | None = None


@dataclass(frozen=True, slots=True)
class EditCommand:
    """Normalized command payload; positions are world metres in PlanDocument coordinates."""

    action: str
    target_id: str | None = None
    target_room_id: str | None = None
    position: tuple[float, float] | None = None
    offset_m: float | None = None
    width_m: float | None = None
    rotation_deg: float | None = None
    catalog_id: str | None = None
    opening_type: str | None = None
    program: tuple[RoomRequest, ...] = ()
    reply_fr: str = ""


def parse_edit_command(value: Any) -> EditCommand:
    """Validate and normalize an untrusted interpreter response.

    Args:
        value: JSON object returned by the edit interpreter.

    Returns:
        An immutable command with action-specific fields normalized.

    Raises:
        EditCommandError: If the action or payload is invalid.
    """
    if not isinstance(value, dict):
        raise EditCommandError("invalid_payload")
    action = value.get("action")
    if not isinstance(action, str) or action not in EDIT_ACTIONS:
        raise EditCommandError("unknown_action", "action")
    version = value.get("version", EDIT_COMMAND_VERSION)
    if type(version) is not int or version != EDIT_COMMAND_VERSION:
        raise EditCommandError("invalid_payload", "version")
    allowed_fields = _COMMON_FIELDS | ACTION_FIELDS[action]
    if value.keys() - allowed_fields:
        raise EditCommandError("invalid_payload", "fields")
    if REQUIRED_FIELDS[action] - value.keys():
        raise EditCommandError("invalid_payload", "fields")
    target_id = _optional_id(value.get("target_id"), "target_id")
    target_room_id = _optional_id(value.get("target_room_id"), "target_room_id")
    if "target_id" in REQUIRED_FIELDS[action] and target_id is None:
        raise EditCommandError("invalid_payload", "target_id")
    if "target_room_id" in REQUIRED_FIELDS[action] and target_room_id is None:
        raise EditCommandError("invalid_payload", "target_room_id")
    position = (
        _position(value.get("position"))
        if "position" in ACTION_FIELDS[action]
        else None
    )
    offset = (
        _finite_number(value.get("offset_m"), "offset_m")
        if "offset_m" in ACTION_FIELDS[action]
        else None
    )
    width = (
        _finite_number(value.get("width_m"), "width_m")
        if "width_m" in ACTION_FIELDS[action]
        else None
    )
    rotation = (
        _finite_number(value.get("rotation_deg"), "rotation_deg")
        if "rotation_deg" in value
        else (0.0 if action == "add_furniture" else None)
    )
    catalog_id = _optional_id(value.get("catalog_id"), "catalog_id")
    opening_type = value.get("opening_type")
    if opening_type is not None and (
        not isinstance(opening_type, str) or opening_type not in OPENING_TYPES
    ):
        raise EditCommandError("invalid_payload", "opening_type")
    if action == "add_opening" and (width is None or width <= 0):
        raise EditCommandError("invalid_payload", "width_m")
    if action in {"move_opening", "add_opening"} and offset is not None and offset < 0:
        raise EditCommandError("invalid_payload", "offset_m")
    if action == "add_furniture" and not catalog_id:
        raise EditCommandError("invalid_payload", "catalog_id")
    if action == "add_opening" and not opening_type:
        raise EditCommandError("invalid_payload", "opening_type")
    program = _program(value.get("program")) if action == "replace_program" else ()
    reply = value.get("reply_fr", "")
    if not isinstance(reply, str):
        raise EditCommandError("invalid_payload", "reply_fr")

    return EditCommand(
        action=action,
        target_id=target_id,
        target_room_id=target_room_id,
        position=position,
        offset_m=offset,
        width_m=width,
        rotation_deg=rotation,
        catalog_id=catalog_id,
        opening_type=opening_type,
        program=program,
        reply_fr=reply.strip(),
    )


def _optional_id(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise EditCommandError("invalid_payload", field)
    return value.strip()


def _finite_number(value: Any, field: str) -> float:
    if type(value) not in (int, float):
        raise EditCommandError("invalid_payload", field)
    try:
        result = float(value)
    except OverflowError as exc:
        raise EditCommandError("invalid_payload", field) from exc
    if not math.isfinite(result):
        raise EditCommandError("invalid_payload", field)
    return result


def _position(value: Any) -> tuple[float, float]:
    if not isinstance(value, dict) or value.keys() != {"x", "y"}:
        raise EditCommandError("invalid_payload", "position")
    return (
        _finite_number(value["x"], "position.x"),
        _finite_number(value["y"], "position.y"),
    )


def _program(value: Any) -> tuple[RoomRequest, ...]:
    if not isinstance(value, list) or not value or len(value) > 64:
        raise EditCommandError("invalid_payload", "program")
    normalized: list[RoomRequest] = []
    for item in value:
        if not isinstance(item, dict) or item.keys() - {
            "id",
            "type",
            "count",
            "area_m2",
        }:
            raise EditCommandError("invalid_payload", "program")
        if {"type", "count"} - item.keys():
            raise EditCommandError("invalid_payload", "program")
        room_type, count = item.get("type"), item.get("count")
        room_id = _optional_id(item.get("id"), "program.id")
        area = (
            _finite_number(item["area_m2"], "program.area_m2")
            if "area_m2" in item
            else None
        )
        if (
            not isinstance(room_type, str)
            or room_type not in ROOM_TYPES
            or type(count) is not int
            or not 1 <= count <= 64
            or (area is not None and not 0 < area <= 500)
        ):
            raise EditCommandError("invalid_payload", "program")
        normalized.append(
            RoomRequest(room_type=room_type, count=count, area_m2=area, room_id=room_id)
        )
    if sum(request.count for request in normalized) > 64:
        raise EditCommandError("invalid_payload", "program")
    return tuple(normalized)
