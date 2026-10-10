from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from app.edit_service import _reconcile_rebuilt_room_ids, apply_edit_command, edit_plan
from app.plan_contracts import PlanDocumentError


def _document() -> dict[str, Any]:
    return {
        "version": "1.0",
        "units": "m",
        "floor": {"bounds": {"width": 6, "depth": 5}},
        "walls": [
            {
                "id": "w_outer_1",
                "a": {"x": 0, "y": 0},
                "b": {"x": 6, "y": 0},
                "thickness_m": 0.15,
            },
            {
                "id": "w_outer_2",
                "a": {"x": 6, "y": 0},
                "b": {"x": 6, "y": 5},
                "thickness_m": 0.15,
            },
            {
                "id": "w_outer_3",
                "a": {"x": 6, "y": 5},
                "b": {"x": 0, "y": 5},
                "thickness_m": 0.15,
            },
            {
                "id": "w_outer_4",
                "a": {"x": 0, "y": 5},
                "b": {"x": 0, "y": 0},
                "thickness_m": 0.15,
            },
        ],
        "rooms": [
            {
                "id": "r1",
                "type": "living",
                "polygon": [
                    {"x": 1, "y": 1},
                    {"x": 5, "y": 1},
                    {"x": 5, "y": 4},
                    {"x": 1, "y": 4},
                ],
            }
        ],
        "openings": [],
    }


def test_program_replacement_validates_document_and_renders_the_exact_result() -> None:
    source = _document()
    original = deepcopy(source)
    target = _document()
    observed: dict[str, Any] = {}

    def rebuild(spec: dict[str, Any], constraints: dict[str, Any]) -> dict[str, Any]:
        observed["spec"] = deepcopy(spec)
        observed["constraints"] = deepcopy(constraints)
        return {"plan_document": target, "compliance": {"score": 1}}

    def render(document: dict[str, Any]) -> str:
        observed["rendered_document"] = document
        return "local-preview-from-document"

    result = edit_plan(
        "ajouter une véranda",
        constraints={
            "parcel_width_m": 10,
            "_aai_source_layout": {"parti": "forged", "seed": 5},
        },
        spec={"brief": "maison"},
        plan_document=source,
        image_png_b64="old-preview",
        interpret=lambda *_: {
            "edit_en": "Add a veranda",
            "reply_fr": "Je reconstruis le programme.",
            "rooms": [{"type": "living", "count": 1}, {"type": "veranda", "count": 1}],
        },
        rebuild=rebuild,
        render_document=render,
        notify_step=lambda job_id, step: observed.setdefault("step", (job_id, step)),
        validate_document=lambda document: observed.setdefault("validated", document),
    )

    assert source == original
    assert observed["spec"]["rooms"] == [
        {"type": "living", "count": 1},
        {"type": "veranda", "count": 1},
    ]
    assert "_aai_source_layout" not in observed["constraints"]
    assert observed["validated"] is target
    assert observed["rendered_document"] is target
    assert observed["step"] == (None, "edit")
    assert result["plan_document"] is target
    assert result["image_png_b64"] == "local-preview-from-document"
    assert result["method"] == "procedural+edit"
    assert result["edit_status"] == "applied"
    assert result["compliance"] == {"score": 1}


def test_rebuild_reuses_same_type_ids_and_ignores_model_ids() -> None:
    source = _document()
    source["rooms"] = [
        {
            "id": "bedroom-a",
            "type": "bedroom",
            "polygon": [
                {"x": 0, "y": 0},
                {"x": 2, "y": 0},
                {"x": 2, "y": 2},
                {"x": 0, "y": 2},
            ],
        },
        {
            "id": "bedroom-b",
            "type": "bedroom",
            "polygon": [
                {"x": 2, "y": 0},
                {"x": 4, "y": 0},
                {"x": 4, "y": 2},
                {"x": 2, "y": 2},
            ],
        },
        {
            "id": "living",
            "type": "living",
            "polygon": deepcopy(_document()["rooms"][0]["polygon"]),
        },
    ]
    source["layout"] = {"parti": "zoned", "seed": 9, "arr": "L2|R1|B2"}
    source["walls"].append({"id": "edit_r1"})
    observed: dict[str, Any] = {}
    target = _document()
    original_polygon = deepcopy(target["rooms"][0]["polygon"])

    result = edit_plan(
        "réorganise les pièces",
        constraints={"parcel_width_m": 12},
        plan_document=source,
        interpret=lambda *_: {
            "edit_en": "rebuild rooms",
            "reply_fr": "Je reconstruis le plan.",
            "command": {
                "action": "replace_program",
                "program": [
                    {"id": "invented-1", "type": "bedroom", "count": 2, "area_m2": 12},
                    {"id": "invented-2", "type": "office", "count": 2, "area_m2": 8},
                ],
            },
        },
        rebuild=lambda spec, constraints: observed.update(
            {"rooms": deepcopy(spec["rooms"]), "constraints": deepcopy(constraints)}
        )
        or {"plan_document": target},
        render_document=lambda _: "preview",
        notify_step=lambda *_: None,
        validate_document=lambda _: None,
    )

    assert observed["rooms"] == [
        {"type": "bedroom", "count": 2, "area_m2": 12.0},
        {"type": "office", "count": 2, "area_m2": 8.0},
    ]
    assert observed["constraints"]["_aai_source_layout"] == source["layout"]
    assert target["rooms"][0]["id"] == "living"
    assert target["rooms"][0]["polygon"] == original_polygon
    assert "layout" in result["reply_fr"] or "implantation" in result["reply_fr"]


def test_new_rebuilt_rooms_get_collision_free_ids_and_update_references() -> None:
    source = _document()
    source["walls"].append({"id": "edit_r1"})
    target = _document()
    target["rooms"].append(
        {
            "id": "generated-r2",
            "type": "veranda",
            "polygon": [
                {"x": 1, "y": 1},
                {"x": 3, "y": 1},
                {"x": 3, "y": 3},
                {"x": 1, "y": 3},
            ],
        }
    )
    target["furniture"] = [
        {"id": "f1", "catalog_id": "table.dining", "room_id": "generated-r2"}
    ]
    adapted = {
        "plan_document": target,
        "dimensions": [{"id": "r1"}, {"id": "generated-r2"}],
    }

    _reconcile_rebuilt_room_ids(adapted, source)

    assert [room["id"] for room in target["rooms"]] == ["r1", "edit_r2"]
    assert target["furniture"][0]["room_id"] == "edit_r2"
    assert [row["id"] for row in adapted["dimensions"]] == ["r1", "edit_r2"]


def test_rebuilt_room_ids_follow_geometry_when_same_type_rooms_are_reordered() -> None:
    source = _document()
    source["rooms"] = [
        {
            "id": "left-bedroom",
            "type": "bedroom",
            "polygon": [
                {"x": 0, "y": 0},
                {"x": 2, "y": 0},
                {"x": 2, "y": 2},
                {"x": 0, "y": 2},
            ],
        },
        {
            "id": "right-bedroom",
            "type": "bedroom",
            "polygon": [
                {"x": 4, "y": 0},
                {"x": 6, "y": 0},
                {"x": 6, "y": 2},
                {"x": 4, "y": 2},
            ],
        },
    ]
    rebuilt = {
        "rooms": [
            {
                "id": "generated-right",
                "type": "bedroom",
                "polygon": [
                    {"x": 4, "y": 0},
                    {"x": 6, "y": 0},
                    {"x": 6, "y": 2},
                    {"x": 4, "y": 2},
                ],
            },
            {
                "id": "generated-left",
                "type": "bedroom",
                "polygon": [
                    {"x": 0, "y": 0},
                    {"x": 2, "y": 0},
                    {"x": 2, "y": 2},
                    {"x": 0, "y": 2},
                ],
            },
        ],
        "furniture": [
            {"id": "chair", "catalog_id": "chair.dining", "room_id": "generated-left"}
        ],
    }

    _reconcile_rebuilt_room_ids({"plan_document": rebuilt}, source)

    assert [room["id"] for room in rebuilt["rooms"]] == [
        "right-bedroom",
        "left-bedroom",
    ]
    assert rebuilt["furniture"][0]["room_id"] == "left-bedroom"


def test_rebuilt_duplicate_room_ids_are_rejected_before_reference_mapping() -> None:
    rebuilt = _document()
    rebuilt["rooms"].append(deepcopy(rebuilt["rooms"][0]))

    with pytest.raises(PlanDocumentError, match="rooms.id"):
        _reconcile_rebuilt_room_ids({"plan_document": rebuilt}, _document())


def test_duplicate_source_room_ids_are_never_reused() -> None:
    polygon = [
        {"x": 0, "y": 0},
        {"x": 2, "y": 0},
        {"x": 2, "y": 2},
        {"x": 0, "y": 2},
    ]
    source = {
        "rooms": [
            {"id": "duplicate", "type": "bedroom", "polygon": polygon},
            {"id": "duplicate", "type": "bedroom", "polygon": polygon},
        ]
    }
    rebuilt = {
        "rooms": [
            {"id": "new-a", "type": "bedroom", "polygon": polygon},
            {"id": "new-b", "type": "bedroom", "polygon": polygon},
        ]
    }

    _reconcile_rebuilt_room_ids({"plan_document": rebuilt}, source)

    assert len({room["id"] for room in rebuilt["rooms"]}) == 2
    assert all(room["id"] != "duplicate" for room in rebuilt["rooms"])


@pytest.mark.parametrize(
    ("source_polygons", "rebuilt_polygon"),
    [
        (
            [
                [
                    {"x": 0, "y": 0},
                    {"x": 2, "y": 0},
                    {"x": 2, "y": 2},
                    {"x": 0, "y": 2},
                ],
                [
                    {"x": 0, "y": 0},
                    {"x": 2, "y": 0},
                    {"x": 2, "y": 2},
                    {"x": 0, "y": 2},
                ],
            ],
            [
                {"x": 0, "y": 0},
                {"x": 2, "y": 0},
                {"x": 2, "y": 2},
                {"x": 0, "y": 2},
            ],
        ),
        (
            [
                [
                    {"x": 0, "y": 0},
                    {"x": 2, "y": 0},
                    {"x": 2, "y": 2},
                    {"x": 0, "y": 2},
                ]
            ],
            [
                {"x": 10, "y": 10},
                {"x": 12, "y": 10},
                {"x": 12, "y": 12},
                {"x": 10, "y": 12},
            ],
        ),
    ],
    ids=("ambiguous", "low-overlap"),
)
def test_ambiguous_or_low_overlap_room_gets_a_fresh_id(
    source_polygons: list[list[dict[str, int]]],
    rebuilt_polygon: list[dict[str, int]],
) -> None:
    source = {
        "rooms": [
            {"id": f"old-{index}", "type": "bedroom", "polygon": polygon}
            for index, polygon in enumerate(source_polygons)
        ]
    }
    rebuilt = {
        "rooms": [{"id": "generated", "type": "bedroom", "polygon": rebuilt_polygon}]
    }

    _reconcile_rebuilt_room_ids({"plan_document": rebuilt}, source)

    assert rebuilt["rooms"][0]["id"] == "edit_r1"


def test_remove_room_command_rebuilds_the_remaining_room_program() -> None:
    source = _document()
    source["rooms"] = [
        {
            "id": "r1",
            "type": "living",
            "polygon": [
                {"x": 1, "y": 1},
                {"x": 3, "y": 1},
                {"x": 3, "y": 4},
                {"x": 1, "y": 4},
            ],
        },
        {
            "id": "r2",
            "type": "bedroom",
            "polygon": [
                {"x": 3, "y": 1},
                {"x": 4, "y": 1},
                {"x": 4, "y": 4},
                {"x": 3, "y": 4},
            ],
        },
        {
            "id": "r3",
            "type": "kitchen",
            "polygon": [
                {"x": 4, "y": 1},
                {"x": 5, "y": 1},
                {"x": 5, "y": 4},
                {"x": 4, "y": 4},
            ],
        },
    ]
    original = deepcopy(source)
    target = _document()
    target["rooms"][0]["id"] = "living-new"
    observed: dict[str, Any] = {}

    def rebuild(spec: dict[str, Any], _: dict[str, Any]) -> dict[str, Any]:
        observed["rooms"] = deepcopy(spec["rooms"])
        return {"plan_document": target}

    result = edit_plan(
        "supprime le séjour",
        spec={
            "rooms": [
                {"type": "living", "count": 1},
                {"type": "bedroom", "count": 1},
                {"type": "kitchen", "count": 1},
            ]
        },
        plan_document=source,
        interpret=lambda *_: {
            "edit_en": "remove living room",
            "reply_fr": "Le séjour est retiré.",
            "command": {"action": "remove_room", "target_id": "r1"},
        },
        rebuild=rebuild,
        render_document=lambda _: "preview",
        notify_step=lambda *_: None,
        validate_document=lambda _: None,
    )

    assert source == original
    assert observed["rooms"] == [
        {"type": "bedroom", "count": 1, "area_m2": 3.0},
        {"type": "kitchen", "count": 1, "area_m2": 3.0},
    ]
    assert "rooms: r1" in result["reply_fr"]
    assert result["edit_status"] == "applied"


def test_remove_first_of_same_type_preserves_the_remaining_room_identity() -> None:
    source = _document()
    source["rooms"] = [
        {
            "id": "bedroom-a",
            "type": "bedroom",
            "polygon": [
                {"x": 0, "y": 0},
                {"x": 2, "y": 0},
                {"x": 2, "y": 2},
                {"x": 0, "y": 2},
            ],
        },
        {
            "id": "bedroom-b",
            "type": "bedroom",
            "polygon": [
                {"x": 2, "y": 0},
                {"x": 4, "y": 0},
                {"x": 4, "y": 2},
                {"x": 2, "y": 2},
            ],
        },
        {
            "id": "living-1",
            "type": "living",
            "polygon": [
                {"x": 0, "y": 2},
                {"x": 4, "y": 2},
                {"x": 4, "y": 4},
                {"x": 0, "y": 4},
            ],
        },
    ]
    observed: dict[str, Any] = {}
    rebuilt = _document()
    rebuilt["rooms"] = [
        {
            "id": "generated-bedroom",
            "type": "bedroom",
            "polygon": [
                {"x": 2, "y": 0},
                {"x": 4, "y": 0},
                {"x": 4, "y": 2},
                {"x": 2, "y": 2},
            ],
        },
        {
            "id": "generated-living",
            "type": "living",
            "polygon": [
                {"x": 0, "y": 2},
                {"x": 4, "y": 2},
                {"x": 4, "y": 4},
                {"x": 0, "y": 4},
            ],
        },
    ]

    result = edit_plan(
        "supprime la première chambre",
        spec={"rooms": [{"type": "bedroom", "count": 2}]},
        plan_document=source,
        interpret=lambda *_: {
            "edit_en": "remove bedroom",
            "reply_fr": "Je retire la chambre ciblée.",
            "command": {"action": "remove_room", "target_id": "bedroom-a"},
        },
        rebuild=lambda spec, _: observed.update({"rooms": deepcopy(spec["rooms"])})
        or {"plan_document": rebuilt},
        render_document=lambda _: "preview",
        notify_step=lambda *_: None,
        validate_document=lambda _: None,
    )

    assert observed["rooms"] == [
        {"type": "bedroom", "count": 1, "area_m2": 4.0},
        {"type": "living", "count": 1, "area_m2": 8.0},
    ]
    assert [room["id"] for room in result["plan_document"]["rooms"]] == [
        "bedroom-b",
        "living-1",
    ]


@pytest.mark.parametrize(
    ("target_id", "room_count", "expected_code"),
    [
        ("missing", 1, "target_not_found"),
        ("r1", 2, "constraint_violation"),
    ],
)
def test_remove_room_rejects_missing_or_last_remaining_room_without_rebuilding(
    target_id: str, room_count: int, expected_code: str
) -> None:
    source = _document()
    source["rooms"] = source["rooms"][:room_count]
    if room_count > 1:
        source["rooms"].append(
            {
                **source["rooms"][0],
                "id": "r2",
                "type": "bedroom",
            }
        )
    original = deepcopy(source)

    with pytest.raises(PlanDocumentError) as raised:
        edit_plan(
            "supprime cette pièce",
            plan_document=source,
            interpret=lambda *_: {
                "edit_en": "remove room",
                "reply_fr": "La pièce est retirée.",
                "command": {"action": "remove_room", "target_id": target_id},
            },
            rebuild=lambda *_: pytest.fail("invalid room removal must not rebuild"),
            render_document=lambda _: pytest.fail(
                "invalid room removal must not render"
            ),
            notify_step=lambda *_: None,
            validate_document=lambda _: None,
        )

    assert raised.value.code == expected_code
    assert source == original


def test_remove_room_aggregates_types_preserves_requested_area_and_derives_missing_area() -> (
    None
):
    source = _document()
    source["floor"]["bounds"] = {"width": 8, "depth": 6}
    source["walls"] = [
        {
            "id": "w_outer_1",
            "a": {"x": 0, "y": 0},
            "b": {"x": 8, "y": 0},
            "thickness_m": 0.15,
        },
        {
            "id": "w_outer_2",
            "a": {"x": 8, "y": 0},
            "b": {"x": 8, "y": 6},
            "thickness_m": 0.15,
        },
        {
            "id": "w_outer_3",
            "a": {"x": 8, "y": 6},
            "b": {"x": 0, "y": 6},
            "thickness_m": 0.15,
        },
        {
            "id": "w_outer_4",
            "a": {"x": 0, "y": 6},
            "b": {"x": 0, "y": 0},
            "thickness_m": 0.15,
        },
    ]
    source["rooms"] = [
        {
            "id": "living",
            "type": "living",
            "polygon": [
                {"x": 0, "y": 0},
                {"x": 2, "y": 0},
                {"x": 2, "y": 2},
                {"x": 0, "y": 2},
            ],
        },
        {
            "id": "bedroom-1",
            "type": "bedroom",
            "polygon": [
                {"x": 2, "y": 0},
                {"x": 4, "y": 0},
                {"x": 4, "y": 3},
                {"x": 2, "y": 3},
            ],
        },
        {
            "id": "bedroom-2",
            "type": "bedroom",
            "polygon": [
                {"x": 4, "y": 0},
                {"x": 8, "y": 0},
                {"x": 8, "y": 3},
                {"x": 4, "y": 3},
            ],
        },
        {
            "id": "office-1",
            "type": "office",
            "polygon": [
                {"x": 0, "y": 2},
                {"x": 2, "y": 2},
                {"x": 2, "y": 4},
                {"x": 0, "y": 4},
            ],
        },
        {
            "id": "office-2",
            "type": "office",
            "polygon": [
                {"x": 0, "y": 4},
                {"x": 3, "y": 4},
                {"x": 3, "y": 6},
                {"x": 0, "y": 6},
            ],
        },
    ]
    original = deepcopy(source)
    observed: dict[str, Any] = {}

    def rebuild(spec: dict[str, Any], _: dict[str, Any]) -> dict[str, Any]:
        observed["rooms"] = deepcopy(spec["rooms"])
        return {"plan_document": _document()}

    result = edit_plan(
        "supprime le séjour",
        spec={"rooms": [{"type": "bedroom", "count": 1, "area_m2": 10.5}]},
        plan_document=source,
        interpret=lambda *_: {
            "edit_en": "remove living room",
            "reply_fr": "Le séjour est retiré.",
            "command": {"action": "remove_room", "target_id": "living"},
        },
        rebuild=rebuild,
        render_document=lambda _: "preview",
        notify_step=lambda *_: None,
        validate_document=lambda _: None,
    )

    assert source == original
    assert observed["rooms"] == [
        {"type": "bedroom", "count": 2, "area_m2": 10.5},
        {"type": "office", "count": 2, "area_m2": 5.0},
    ]
    assert result["edit_status"] == "applied"


def test_rebuild_reply_lists_ids_of_elements_not_preserved() -> None:
    source = _document()
    source["furniture"] = [{"id": "sofa-1", "room_id": "r1"}]
    target = _document()
    target["rooms"][0]["id"] = "room-new"
    target["walls"][0]["id"] = "wall-new"
    target["openings"] = []

    result = edit_plan(
        "remplace le programme",
        plan_document=source,
        interpret=lambda *_: {
            "edit_en": "replace the room program",
            "reply_fr": "Je reconstruis le programme.",
            "rooms": [{"type": "living", "count": 1}],
        },
        rebuild=lambda *_: {"plan_document": target},
        render_document=lambda _: "preview",
        notify_step=lambda *_: None,
        validate_document=lambda _: None,
    )

    assert "rooms: r1" not in result["reply_fr"]
    assert result["plan_document"]["rooms"][0]["id"] == "r1"
    assert "walls: w_outer_1" in result["reply_fr"]
    assert "furniture: sofa-1" in result["reply_fr"]


def test_clarification_preserves_source_document_and_preview_without_rebuild() -> None:
    source = _document()
    original = deepcopy(source)
    result = edit_plan(
        "déplace cette pièce",
        plan_document=source,
        image_png_b64="existing-preview",
        interpret=lambda *_: {"edit_en": "", "reply_fr": "Laquelle ?", "clarify": True},
        rebuild=lambda *_: pytest.fail("clarification must not rebuild"),
        render_document=lambda _: "rendered-current-plan",
        notify_step=lambda *_: None,
        validate_document=lambda *_: pytest.fail(
            "clarification must not validate a changed document"
        ),
    )

    assert source == original
    assert result["plan_document"] == original
    assert result["image_png_b64"] == "rendered-current-plan"
    assert result["clarify"] is True
    assert result["edit_status"] == "clarification_required"


def test_invalid_interpreted_program_is_rejected_before_rebuild() -> None:
    with pytest.raises(PlanDocumentError) as raised:
        edit_plan(
            "ajouter une pièce",
            interpret=lambda *_: {
                "edit_en": "",
                "reply_fr": "",
                "rooms": [{"type": "unknown-room", "count": 1}],
            },
            rebuild=lambda *_: pytest.fail("invalid program must not rebuild"),
            render_document=lambda *_: "",
            notify_step=lambda *_: None,
            validate_document=lambda *_: None,
        )

    assert raised.value.code == "invalid_payload"


def test_missing_interpreted_command_requests_clarification_without_image_edit() -> (
    None
):
    source = _document()
    calls: list[str] = []
    result = edit_plan(
        "change it",
        plan_document=source,
        image_png_b64="old-raster",
        interpret=lambda *_: {"edit_en": "change it", "reply_fr": "Je change le plan."},
        rebuild=lambda *_: pytest.fail("missing command must not rebuild"),
        render_document=lambda _: calls.append("render") or "document-preview",
        notify_step=lambda *_: None,
        validate_document=lambda *_: pytest.fail(
            "no edit must not validate a changed document"
        ),
    )

    assert result["clarify"] is True
    assert result["edit_status"] == "clarification_required"
    assert result["image_png_b64"] == "document-preview"
    assert result["steps"] == ["edit", "render"]
    assert calls == ["render"]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (
            {
                "action": "add_furniture",
                "target_room_id": "r1",
                "position": {"x": 3, "y": 2.5},
                "catalog_id": "bed.double",
            },
            "edit_f1",
        ),
        (
            {
                "action": "add_opening",
                "target_id": "w_outer_1",
                "opening_type": "door",
                "offset_m": 0.5,
                "width_m": 0.9,
            },
            "edit_o1",
        ),
    ],
)
def test_add_furniture_and_opening_apply_to_copy(
    command: dict[str, Any], expected: str
) -> None:
    source = _document()
    original = deepcopy(source)
    from app.edit_commands import parse_edit_command

    updated = apply_edit_command(source, parse_edit_command(command))

    assert source == original
    collection = "furniture" if command["action"] == "add_furniture" else "openings"
    assert updated[collection][-1]["id"] == expected


@pytest.mark.parametrize(
    ("new_catalog_id", "existing_catalog_id"),
    [
        ("rug.rect", "sofa.2seat"),
        ("sofa.2seat", "rug.rect"),
    ],
)
def test_add_furniture_allows_rug_overlap_in_either_insertion_order(
    new_catalog_id: str, existing_catalog_id: str
) -> None:
    source = _document()
    source["furniture"] = [
        {
            "id": "existing-item",
            "catalog_id": existing_catalog_id,
            "room_id": "r1",
            "position": {"x": 3.0, "y": 2.5},
        }
    ]
    original = deepcopy(source)
    from app.edit_commands import parse_edit_command

    updated = apply_edit_command(
        source,
        parse_edit_command(
            {
                "action": "add_furniture",
                "target_room_id": "r1",
                "position": {"x": 3.0, "y": 2.5},
                "catalog_id": new_catalog_id,
            }
        ),
    )

    assert source == original
    assert len(updated["furniture"]) == 2
    assert updated["furniture"][0]["id"] == "existing-item"
    assert updated["furniture"][1]["id"] == "edit_f1"
    assert updated["furniture"][1]["catalog_id"] == new_catalog_id


def test_add_furniture_skips_generated_id_collisions_across_plan_collections() -> None:
    source = _document()
    source["walls"][0]["id"] = "edit_f1"
    original = deepcopy(source)
    from app.edit_commands import parse_edit_command

    updated = apply_edit_command(
        source,
        parse_edit_command(
            {
                "action": "add_furniture",
                "target_room_id": "r1",
                "position": {"x": 3.0, "y": 2.5},
                "catalog_id": "rug.rect",
            }
        ),
    )

    assert source == original
    assert source["walls"][0]["id"] == "edit_f1"
    assert updated["walls"][0]["id"] == "edit_f1"
    assert updated["furniture"][0]["id"] == "edit_f2"


def test_remove_opening_target_missing_is_rejected_without_mutating_input() -> None:
    source = _document()
    original = deepcopy(source)
    from app.edit_commands import parse_edit_command

    with pytest.raises(PlanDocumentError) as raised:
        apply_edit_command(
            source,
            parse_edit_command({"action": "remove_opening", "target_id": "missing"}),
        )

    assert raised.value.code == "target_not_found"
    assert source == original


@pytest.mark.parametrize(
    ("command", "collection", "expected_position"),
    [
        (
            {
                "action": "move_furniture",
                "target_id": "chair-1",
                "position": {"x": 3, "y": 2},
            },
            "furniture",
            {"x": 3.0, "y": 2.0},
        ),
        (
            {"action": "move_opening", "target_id": "door-1", "offset_m": 2.0},
            "openings",
            None,
        ),
    ],
)
def test_move_existing_furniture_and_opening_preserves_identity(
    command: dict[str, Any],
    collection: str,
    expected_position: dict[str, float] | None,
) -> None:
    source = _document()
    source["furniture"] = [
        {
            "id": "chair-1",
            "catalog_id": "chair.dining",
            "room_id": "r1",
            "position": {"x": 2.0, "y": 2.0},
            "rotation_deg": 0,
            "size_m": {"w": 0.45, "d": 0.5, "h": 0.9},
        }
    ]
    source["openings"] = [
        {
            "id": "door-1",
            "wall_id": "w_outer_1",
            "type": "door",
            "offset_m": 0.5,
            "width_m": 0.9,
        }
    ]
    original = deepcopy(source)
    from app.edit_commands import parse_edit_command

    updated = apply_edit_command(source, parse_edit_command(command))

    assert source == original
    assert updated[collection][0]["id"] == command["target_id"]
    if expected_position is not None:
        assert updated[collection][0]["position"] == expected_position
    else:
        assert updated[collection][0]["offset_m"] == 2.0


@pytest.mark.parametrize(
    ("position", "rotation_deg", "existing_furniture"),
    [
        ((1.1, 2.5), 0, []),
        ((2.0, 2.5), 45, []),
        (
            (3.0, 2.5),
            0,
            [
                {
                    "id": "bed-1",
                    "catalog_id": "bed.double",
                    "position": {"x": 3.0, "y": 2.5},
                    "rotation_deg": 0,
                    "size_m": {"w": 1.6, "d": 2.0, "h": 0.55},
                }
            ],
        ),
    ],
)
def test_add_furniture_rejects_footprint_outside_room_or_overlapping(
    position: tuple[float, float],
    rotation_deg: float,
    existing_furniture: list[dict[str, Any]],
) -> None:
    source = _document()
    source["furniture"] = deepcopy(existing_furniture)
    original = deepcopy(source)
    from app.edit_commands import parse_edit_command

    with pytest.raises(PlanDocumentError) as raised:
        apply_edit_command(
            source,
            parse_edit_command(
                {
                    "action": "add_furniture",
                    "target_room_id": "r1",
                    "position": {"x": position[0], "y": position[1]},
                    "catalog_id": "bed.double",
                    "rotation_deg": rotation_deg,
                }
            ),
        )

    assert raised.value.code == "constraint_violation"
    assert source == original


def test_move_furniture_rejects_an_unsafe_footprint_without_mutating_source() -> None:
    source = _document()
    source["furniture"] = [
        {
            "id": "chair-1",
            "catalog_id": "chair.dining",
            "room_id": "r1",
            "position": {"x": 2, "y": 2},
            "rotation_deg": 0,
            "size_m": {"w": 0.45, "d": 0.5, "h": 0.9},
        }
    ]
    original = deepcopy(source)
    from app.edit_commands import parse_edit_command

    with pytest.raises(PlanDocumentError) as raised:
        apply_edit_command(
            source,
            parse_edit_command(
                {
                    "action": "move_furniture",
                    "target_id": "chair-1",
                    "position": {"x": 1.1, "y": 2},
                }
            ),
        )

    assert raised.value.code == "constraint_violation"
    assert source == original


@pytest.mark.parametrize(
    ("command", "collection"),
    [
        ({"action": "remove_furniture", "target_id": "chair-1"}, "furniture"),
        ({"action": "remove_opening", "target_id": "door-1"}, "openings"),
    ],
)
def test_remove_furniture_and_opening_only_removes_target(
    command: dict[str, Any], collection: str
) -> None:
    source = _document()
    source["furniture"] = [{"id": "chair-1", "room_id": "r1"}, {"id": "desk-1"}]
    source["openings"] = [
        {
            "id": "door-1",
            "wall_id": "w_outer_1",
            "type": "door",
            "offset_m": 0.5,
            "width_m": 0.9,
        },
        {
            "id": "window-1",
            "wall_id": "w_outer_1",
            "type": "window",
            "offset_m": 2.0,
            "width_m": 1.2,
        },
    ]
    original = deepcopy(source)
    from app.edit_commands import parse_edit_command

    updated = apply_edit_command(source, parse_edit_command(command))

    assert source == original
    assert all(item["id"] != command["target_id"] for item in updated[collection])
    assert any(item["id"] != command["target_id"] for item in updated[collection])


@pytest.mark.parametrize(
    "command",
    [
        {
            "action": "move_furniture",
            "target_id": "missing",
            "position": {"x": 2, "y": 2},
        },
        {"action": "remove_furniture", "target_id": "missing"},
        {"action": "move_opening", "target_id": "missing", "offset_m": 1},
        {"action": "remove_opening", "target_id": "missing"},
        {
            "action": "add_opening",
            "target_id": "missing-wall",
            "opening_type": "door",
            "offset_m": 0,
            "width_m": 0.9,
        },
    ],
)
def test_commands_with_missing_targets_are_rejected_without_mutation(
    command: dict[str, Any],
) -> None:
    source = _document()
    original = deepcopy(source)
    from app.edit_commands import parse_edit_command

    with pytest.raises(PlanDocumentError) as raised:
        apply_edit_command(source, parse_edit_command(command))

    assert raised.value.code == "target_not_found"
    assert source == original


def test_move_room_translates_polygon_furniture_and_opening_without_mutating_source() -> (
    None
):
    source = _document()
    source["furniture"] = [
        {
            "id": "desk-1",
            "catalog_id": "desk",
            "room_id": "r1",
            "position": {"x": 2.0, "y": 2.0},
            "size_m": {"w": 1.2, "d": 0.6, "h": 0.75},
        }
    ]
    source["walls"].append(
        {
            "id": "w_room_1",
            "a": {"x": 1, "y": 1},
            "b": {"x": 5, "y": 1},
            "thickness_m": 0.1,
        }
    )
    source["openings"] = [
        {
            "id": "door-1",
            "wall_id": "w_room_1",
            "type": "door",
            "offset_m": 0.5,
            "width_m": 0.9,
        }
    ]
    original = deepcopy(source)
    from app.document_validation import validate_document

    result = edit_plan(
        "déplace le séjour",
        plan_document=source,
        interpret=lambda *_: {
            "edit_en": "move living room",
            "reply_fr": "Le séjour est déplacé.",
            "command": {
                "action": "move_room",
                "target_id": "r1",
                "position": {"x": 0.5, "y": 0.25},
            },
        },
        rebuild=lambda *_: pytest.fail("room movement is local"),
        render_document=lambda _: "preview-from-updated-document",
        notify_step=lambda *_: None,
        validate_document=validate_document,
    )

    assert source == original
    updated = result["plan_document"]
    assert updated["rooms"][0]["polygon"][0] == {"x": 1.5, "y": 1.25}
    assert updated["furniture"][0]["position"] == {"x": 2.5, "y": 2.25}
    moved_wall = next(wall for wall in updated["walls"] if wall["id"] == "w_room_1")
    assert moved_wall["a"] == {"x": 1.5, "y": 1.25}
    assert updated["openings"][0]["id"] == "door-1"
    assert updated["openings"][0]["offset_m"] == 0.5
    assert result["image_png_b64"] == "preview-from-updated-document"
    assert result["edit_status"] == "applied"
    assert [wall["id"] for wall in updated["walls"][:4]] == [
        "w_outer_1",
        "w_outer_2",
        "w_outer_3",
        "w_outer_4",
    ]


def test_move_room_validates_all_furniture_after_collective_translation() -> None:
    source = _document()
    source["furniture"] = [
        {
            "id": f"chair-{index}",
            "catalog_id": "chair.dining",
            "room_id": "r1",
            "position": {"x": x, "y": 2.0},
            "rotation_deg": 0,
            "size_m": {"w": 0.45, "d": 0.5, "h": 0.9},
        }
        for index, x in enumerate((2.0, 2.5), start=1)
    ]
    original = deepcopy(source)
    from app.document_validation import validate_document

    result = edit_plan(
        "déplace le séjour légèrement à droite",
        plan_document=source,
        interpret=lambda *_: {
            "edit_en": "move living room slightly right",
            "reply_fr": "Le séjour est déplacé.",
            "command": {
                "action": "move_room",
                "target_id": "r1",
                "position": {"x": 0.2, "y": 0},
            },
        },
        rebuild=lambda *_: pytest.fail("room movement is local"),
        render_document=lambda _: "preview",
        notify_step=lambda *_: None,
        validate_document=validate_document,
    )

    assert source == original
    moved_centers = [
        item["position"]["x"] for item in result["plan_document"]["furniture"]
    ]
    assert moved_centers == [2.2, 2.7]
    assert result["edit_status"] == "applied"


def test_move_room_out_of_bounds_is_rejected_before_render_and_preserves_source() -> (
    None
):
    source = _document()
    original = deepcopy(source)
    from app.document_validation import validate_document

    with pytest.raises(PlanDocumentError) as raised:
        edit_plan(
            "déplace le séjour",
            plan_document=source,
            interpret=lambda *_: {
                "edit_en": "move living room",
                "reply_fr": "Déplacement.",
                "command": {
                    "action": "move_room",
                    "target_id": "r1",
                    "position": {"x": 2, "y": 0},
                },
            },
            rebuild=lambda *_: pytest.fail("room movement is local"),
            render_document=lambda _: pytest.fail("invalid geometry must not render"),
            notify_step=lambda *_: None,
            validate_document=validate_document,
        )

    assert raised.value.code == "point_out_of_bounds"
    assert source == original


def test_move_room_overlap_is_rejected_without_partial_mutation() -> None:
    source = _document()
    source["rooms"][0]["polygon"] = [
        {"x": 1, "y": 1},
        {"x": 3, "y": 1},
        {"x": 3, "y": 4},
        {"x": 1, "y": 4},
    ]
    source["rooms"].append(
        {
            "id": "r2",
            "type": "bedroom",
            "polygon": [
                {"x": 3, "y": 1},
                {"x": 5, "y": 1},
                {"x": 5, "y": 4},
                {"x": 3, "y": 4},
            ],
        }
    )
    source["walls"].append(
        {
            "id": "w_internal_1",
            "a": {"x": 3, "y": 1},
            "b": {"x": 3, "y": 4},
            "thickness_m": 0.1,
        }
    )
    original = deepcopy(source)
    from app.document_validation import validate_document

    with pytest.raises(PlanDocumentError) as raised:
        edit_plan(
            "déplace le séjour",
            plan_document=source,
            interpret=lambda *_: {
                "edit_en": "move living room",
                "reply_fr": "Déplacement.",
                "command": {
                    "action": "move_room",
                    "target_id": "r1",
                    "position": {"x": 1, "y": 0},
                },
            },
            rebuild=lambda *_: pytest.fail("room movement is local"),
            render_document=lambda _: pytest.fail("overlapping layout must not render"),
            notify_step=lambda *_: None,
            validate_document=validate_document,
        )

    assert raised.value.code == "overlapping_rooms"
    assert source == original


@pytest.mark.parametrize("failure_stage", ["validate", "render"])
def test_late_edit_failures_never_mutate_the_source_or_return_applied(
    failure_stage: str,
) -> None:
    source = _document()
    source["furniture"] = [{"id": "chair-1", "room_id": "r1"}]
    original = deepcopy(source)

    def validate(_: dict[str, Any]) -> None:
        if failure_stage == "validate":
            raise PlanDocumentError("constraint_violation", "furniture")

    def render(_: dict[str, Any]) -> str:
        if failure_stage == "render":
            raise RuntimeError("renderer unavailable")
        return "preview"

    with pytest.raises((PlanDocumentError, RuntimeError)):
        edit_plan(
            "supprime la chaise",
            plan_document=source,
            interpret=lambda *_: {
                "edit_en": "remove chair",
                "reply_fr": "Chaise supprimée.",
                "command": {"action": "remove_furniture", "target_id": "chair-1"},
            },
            rebuild=lambda *_: pytest.fail("furniture removal is local"),
            render_document=render,
            notify_step=lambda *_: None,
            validate_document=validate,
        )

    assert source == original


def test_rebuild_without_document_is_not_reported_as_success() -> None:
    with pytest.raises(PlanDocumentError) as raised:
        edit_plan(
            "ajouter une veranda",
            interpret=lambda *_: {
                "edit_en": "add veranda",
                "reply_fr": "J'ajoute une veranda.",
                "rooms": [
                    {"type": "living", "count": 1},
                    {"type": "veranda", "count": 1},
                ],
            },
            rebuild=lambda *_: {},
            render_document=lambda _: "",
            notify_step=lambda *_: None,
            validate_document=lambda *_: None,
        )

    assert raised.value.code == "invalid_result"
