from __future__ import annotations

import pytest

from app.edit_commands import EditCommandError, parse_edit_command


def test_parse_move_furniture_normalizes_position_and_keeps_command_immutable() -> None:
    command = parse_edit_command(
        {
            "version": 1,
            "action": "move_furniture",
            "target_id": "f1",
            "position": {"x": 2, "y": 3.5},
            "reply_fr": "Déplacé.",
        }
    )

    assert command.action == "move_furniture"
    assert command.target_id == "f1"
    assert command.position == (2.0, 3.5)
    assert command.reply_fr == "Déplacé."
    with pytest.raises(AttributeError):
        command.action = "remove_furniture"  # type: ignore[misc]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"action": "not-an-action"},
        {"version": 2, "action": "remove_room", "target_id": "r1"},
        {"action": "remove_room"},
        {"action": "remove_room", "target_id": None},
        {"action": "remove_room", "target_id": "r1", "clarify": None},
        {"action": "remove_room", "target_id": "r1", "clarify": 0},
        {"action": "move_room", "target_id": "r1", "position": {"x": 1}},
        {"action": "move_room", "target_id": "r1", "position": {"x": True, "y": 1}},
        {"action": "remove_room", "target_id": "r1", "unexpected": True},
        {
            "action": "add_opening",
            "target_id": "w1",
            "opening_type": "arch",
            "offset_m": 0,
            "width_m": 1,
        },
        {
            "action": "add_opening",
            "target_id": "w1",
            "opening_type": "door",
            "offset_m": 0,
            "width_m": 0,
        },
        {
            "action": "add_furniture",
            "target_room_id": "r1",
            "position": {"x": 1, "y": 1},
        },
        {"action": "replace_program", "program": [{"type": "bedroom", "count": True}]},
        {"action": "replace_program", "program": [{"type": "bedroom"}]},
        {
            "action": "replace_program",
            "program": [{"type": "bedroom", "count": 64}, {"type": "wc", "count": 1}],
        },
        {"action": "replace_program", "program": [{"type": "bedroom", "area_m2": 0}]},
        {"action": "move_opening", "target_id": "o1", "offset_m": -0.1},
        {
            "action": "add_opening",
            "target_id": "w1",
            "opening_type": "door",
            "offset_m": -0.1,
            "width_m": 0.9,
        },
    ],
)
def test_rejects_invalid_or_ambiguous_payloads(payload: object) -> None:
    with pytest.raises(EditCommandError):
        parse_edit_command(payload)


@pytest.mark.parametrize(
    ("payload", "expected_field"),
    [
        (
            {"action": "remove_room", "target_id": "  "},
            "target_id",
        ),
        (
            {"action": "remove_room", "target_id": "r" * 129},
            "target_id",
        ),
        (
            {"action": "move_opening", "target_id": "o1", "offset_m": float("inf")},
            "offset_m",
        ),
        (
            {"action": "move_opening", "target_id": "o1", "offset_m": 10**1000},
            "offset_m",
        ),
        (
            {
                "action": "add_opening",
                "target_id": "w1",
                "offset_m": 0,
                "width_m": 0.9,
            },
            "fields",
        ),
        (
            {
                "action": "add_opening",
                "target_id": "w1",
                "opening_type": "arch",
                "offset_m": 0,
                "width_m": 0.9,
            },
            "opening_type",
        ),
        (
            {
                "action": "add_opening",
                "target_id": "w1",
                "opening_type": None,
                "offset_m": 0,
                "width_m": 0.9,
            },
            "opening_type",
        ),
        (
            {
                "action": "add_furniture",
                "target_room_id": "r1",
                "position": {"x": 1, "y": 1},
                "catalog_id": None,
            },
            "catalog_id",
        ),
        (
            {
                "action": "add_furniture",
                "target_room_id": "r1",
                "position": {"x": 1, "y": 1},
            },
            "fields",
        ),
        (
            {
                "action": "add_furniture",
                "target_room_id": "r1",
                "position": {"x": 1, "y": 1},
                "catalog_id": " ",
            },
            "catalog_id",
        ),
        (
            {
                "action": "add_furniture",
                "target_room_id": None,
                "position": {"x": 1, "y": 1},
                "catalog_id": "bed.double",
            },
            "target_room_id",
        ),
        ({"action": "remove_room", "target_id": "r1", "reply_fr": 1}, "reply_fr"),
        ({"action": "replace_program", "program": []}, "program"),
        ({"action": "replace_program", "program": [None]}, "program"),
        (
            {
                "action": "replace_program",
                "program": [{"type": "bedroom", "count": 1, "unexpected": True}],
            },
            "program",
        ),
        (
            {
                "action": "replace_program",
                "program": [{"id": " ", "type": "bedroom", "count": 1}],
            },
            "program.id",
        ),
    ],
    ids=[
        "blank_target_id",
        "overlong_target_id",
        "infinite_offset",
        "overflowing_offset",
        "missing_opening_type",
        "unsupported_opening_type",
        "null_opening_type",
        "null_catalog_id",
        "blank_catalog_id",
        "missing_catalog_id",
        "null_target_room_id",
        "non_string_reply",
        "empty_room_program",
        "non_object_room_request",
        "unknown_room_request_field",
        "blank_room_request_id",
    ],
)
def test_invalid_command_boundaries_report_domain_field(
    payload: object, expected_field: str
) -> None:
    with pytest.raises(EditCommandError) as error:
        parse_edit_command(payload)

    assert error.value.code == "invalid_payload"
    assert error.value.field == expected_field


def test_parse_edit_command_trims_optional_ids_and_reply() -> None:
    command = parse_edit_command(
        {
            "action": "replace_program",
            "program": [{"id": " bedroom-1 ", "type": "bedroom", "count": 1}],
            "reply_fr": "  Pièce supprimée.  ",
        }
    )

    assert command.program[0].room_id == "bedroom-1"
    assert command.reply_fr == "Pièce supprimée."


def test_parse_replace_program_normalizes_to_immutable_room_requests() -> None:
    command = parse_edit_command(
        {
            "action": "replace_program",
            "program": [
                {"type": "bedroom", "count": 1, "area_m2": 12.5},
                {"type": "bathroom", "count": 2},
            ],
        }
    )

    assert [(room.room_type, room.count, room.area_m2) for room in command.program] == [
        ("bedroom", 1, 12.5),
        ("bathroom", 2, None),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "move_furniture", "target_id": "f1", "position": {"x": 1, "y": 2}},
        {
            "action": "add_furniture",
            "target_room_id": "r1",
            "position": {"x": 1, "y": 2},
            "catalog_id": "bed.double",
            "rotation_deg": 90,
        },
        {
            "action": "add_furniture",
            "target_room_id": "r1",
            "position": {"x": 1, "y": 2},
            "catalog_id": "bed.double",
        },
        {"action": "remove_furniture", "target_id": "f1"},
        {"action": "move_opening", "target_id": "o1", "offset_m": 1},
        {
            "action": "add_opening",
            "target_id": "w1",
            "opening_type": "door",
            "offset_m": 1,
            "width_m": 0.9,
        },
        {"action": "remove_opening", "target_id": "o1"},
        {"action": "move_room", "target_id": "r1", "position": {"x": 1, "y": 2}},
        {"action": "remove_room", "target_id": "r1"},
        {"action": "replace_program", "program": [{"type": "veranda", "count": 1}]},
    ],
)
def test_accepts_each_supported_object_action(payload: dict[str, object]) -> None:
    command = parse_edit_command(payload)
    assert command.action == payload["action"]
    if command.action == "add_furniture" and "rotation_deg" not in payload:
        assert command.rotation_deg == 0.0
