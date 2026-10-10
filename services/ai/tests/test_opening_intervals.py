"""Interval contract and conservative generated-window placement."""

from copy import deepcopy

import pytest
from app.opening_intervals import (
    OpeningGeometryError,
    nearest_free_offset,
    validate_openings,
)
from app.plan_openings import fit_generated_windows


def wall(reverse=False):
    a, b = {"x": 0, "y": 0}, {"x": 6, "y": 0}
    return {"id": "w", "a": b if reverse else a, "b": a if reverse else b}


def opening(identifier="o", offset=1, width=1, kind="window"):
    return {"id": identifier, "wall_id": "w", "offset_m": offset, "width_m": width, "type": kind}


def room(end=6):
    return {"id": "r", "polygon": [{"x": 0, "y": 0}, {"x": end, "y": 0}, {"x": end, "y": 3}, {"x": 0, "y": 3}]}


@pytest.mark.parametrize("reverse", [False, True])
def test_contact_and_exact_wall_end_are_valid(reverse):
    validate_openings([wall(reverse)], [opening("a", 0, 2), opening("b", 2, 4)])


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("offset_m", None, "invalid_number"),
        ("offset_m", True, "invalid_number"),
        ("offset_m", "1", "invalid_number"),
        ("offset_m", float("nan"), "invalid_number"),
        ("width_m", float("inf"), "invalid_number"),
        ("width_m", 0, "invalid_opening_width"),
        ("offset_m", -1, "opening_out_of_bounds"),
        ("width_m", 6, "opening_out_of_bounds"),
        ("wall_id", "missing", "unknown_wall"),
        ("type", "arch", "invalid_opening_type"),
    ],
)
def test_reject_invalid_interval(field, value, code):
    item = opening()
    item[field] = value
    with pytest.raises(OpeningGeometryError, match=code):
        validate_openings([wall()], [item])


def test_duplicate_and_overlapping_openings_rejected():
    with pytest.raises(OpeningGeometryError, match="invalid_opening_id"):
        validate_openings([wall()], [opening(), opening(offset=3)])
    with pytest.raises(OpeningGeometryError, match="overlapping_openings"):
        validate_openings([wall()], [opening("a"), opening("b", 1.5)])


@pytest.mark.parametrize("reverse", [False, True])
def test_window_moves_nearest_without_mutation_or_door_change(reverse):
    items = [opening("door", 2, 2, "door"), opening("window", 2.5)]
    original = deepcopy(items)
    result = fit_generated_windows([wall(reverse)], items, [room()])
    assert items == original
    assert result[0] == original[0]
    assert result[1]["offset_m"] == 1  # Tie: both displacements are 1.5 m.
    validate_openings([wall(reverse)], result)


def test_no_move_into_neighbouring_room():
    with pytest.raises(OpeningGeometryError, match="window_no_free_span"):
        fit_generated_windows([wall()], [opening("d", 0, 2.4, "door"), opening("w", 1, 1.4)], [room(3)])


def test_valid_openings_unchanged_and_impossible_doors_not_repaired():
    items = [opening("d", 0, 1, "door"), opening("w", 2)]
    assert fit_generated_windows([wall()], items, [room()]) == items
    with pytest.raises(OpeningGeometryError, match="opening_out_of_bounds"):
        fit_generated_windows([wall()], [opening("d", 5, 2, "door")], [room()])


def test_free_intervals_merge_obstacles_and_clip_to_room():
    assert nearest_free_offset(3, 1, (0, 6), [(2, 4), (3, 5)]) == 1
    assert nearest_free_offset(0, 1, (2, 6), [(0, 3)]) == 3
    assert nearest_free_offset(0, 2, (0, 3), [(1, 2)]) is None
    assert nearest_free_offset(0.1, 0.2, (0.1, 0.3), []) == 0.1


def test_enlargement_keeps_original_room():
    from app.plan_adapt import apply_opening_rules

    first = room(3)
    second = room(6)
    for point in second["polygon"]:
        if point["x"] == 0:
            point["x"] = 3
    second["id"] = "neighbour"
    original = [opening("d", 2, 1, "door"), opening("w", 2, 1)]
    enlarged = apply_opening_rules(original, {"window_min_m": 3}, 6, 3)
    with pytest.raises(OpeningGeometryError, match="window_no_free_span"):
        fit_generated_windows([wall()], enlarged, [first, second], original_openings=original)


def test_derived_nonfinite_values_rejected():
    huge = wall()
    huge["a"]["x"], huge["b"]["x"] = -1e308, 1e308
    with pytest.raises(OpeningGeometryError, match="invalid_wall_segment"):
        validate_openings([huge], [])
    with pytest.raises(OpeningGeometryError, match="invalid_number"):
        validate_openings([wall()], [opening(offset=1e308, width=1e308)])
    with pytest.raises(OpeningGeometryError, match="invalid_number"):
        validate_openings([wall()], [opening(width=10**1000)])


def test_generated_failure_is_not_reported_as_bad_user_input():
    from app.api import _run_stage
    from fastapi import HTTPException

    def fail():
        raise OpeningGeometryError("window_no_free_span", "o1")

    with pytest.raises(HTTPException) as error:
        _run_stage(fail)
    assert error.value.status_code == 500
    assert error.value.detail["code"] == "window_no_free_span"
