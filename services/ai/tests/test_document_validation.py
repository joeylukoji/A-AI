"""The exact same fixture contract is exercised by internal/plan Go tests."""

import json
import math
from copy import deepcopy
from pathlib import Path

import pytest
from app.document_validation import validate_document, validate_generated_document
from app.plan_contracts import GeneratedDocumentError, PlanDocumentError

FIXTURES = json.loads(
    (Path(__file__).resolve().parents[3] / "packages/plan-schema/validation-cases.json").read_text(encoding="utf-8")
)


def fixture_document(case):
    document = deepcopy(FIXTURES["base"])
    for change in case["changes"]:
        path = change["path"]
        if not path:
            document = deepcopy(change["value"])
            continue
        parent = document
        for component in path[:-1]:
            parent = parent[component]
        if change.get("remove"):
            del parent[path[-1]]
        else:
            parent[path[-1]] = deepcopy(change["value"])
    return document


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda case: case["id"])
def test_shared_contract(case):
    document = fixture_document(case)
    before = deepcopy(document)
    if case["code"] is None:
        validate_document(document)
    else:
        with pytest.raises(PlanDocumentError) as error:
            validate_document(document)
        assert error.value.code == case["code"]
    assert document == before


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -(10**1000)])
def test_non_json_finite_numbers_rejected(value):
    document = deepcopy(FIXTURES["base"])
    document["floor"]["bounds"]["width"] = value
    with pytest.raises(PlanDocumentError, match="invalid_number"):
        validate_document(document)


def test_generated_invalid_document_is_internal_failure():
    with pytest.raises(GeneratedDocumentError) as error:
        validate_generated_document({})
    assert error.value.code == "invalid_header"
    assert isinstance(error.value.__cause__, PlanDocumentError)


def test_generated_document_error_maps_to_http_500():
    from app.api import _run_stage
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _run_stage(lambda: validate_generated_document({}))
    assert error.value.status_code == 500
    assert error.value.detail["code"] == "invalid_header"


@pytest.mark.parametrize("room_count,vertices_per_room", [(65, 4), (1, 65), (5, 52)])
def test_geometry_cost_limits(room_count, vertices_per_room):
    document = deepcopy(FIXTURES["base"])
    polygon = [
        {
            "x": 2 + math.cos(2 * math.pi * index / vertices_per_room),
            "y": 2 + math.sin(2 * math.pi * index / vertices_per_room),
        }
        for index in range(vertices_per_room)
    ]
    document["rooms"] = [{"id": f"r{index}", "polygon": polygon} for index in range(room_count)]
    with pytest.raises(PlanDocumentError, match="geometry_complexity_limit"):
        validate_document(document)
