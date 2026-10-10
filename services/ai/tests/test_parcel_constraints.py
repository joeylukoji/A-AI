"""No generated envelope may silently expand an impossible parcel."""

import pytest
from app.main import app
from app.parcel_constraints import resolve_parcel, validate_request_dimensions
from app.plan_adapt import adapt
from app.plan_contracts import PlanConstraintError
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "field,value",
    [
        ("width_m", 0),
        ("width_m", -1),
        ("depth_m", float("nan")),
        ("width_m", float("inf")),
        ("width_m", True),
        ("setback_m", -1),
    ],
)
def test_invalid_parcel_values(field, value):
    with pytest.raises(PlanConstraintError) as error:
        resolve_parcel({field: value}, {}, {})
    assert field in error.value.fields


@pytest.mark.parametrize(
    "field,value",
    [
        ("grid_m", 0),
        ("grid_m", float("nan")),
        ("min_side_m", 0),
        ("min_side_m", True),
    ],
)
def test_invalid_rules(field, value):
    with pytest.raises(PlanConstraintError):
        resolve_parcel({}, {}, {field: value})


def test_setbacks_exhaust_parcel():
    with pytest.raises(PlanConstraintError, match="non_positive_usable_envelope"):
        resolve_parcel({"width_m": 4, "depth_m": 4, "setback_m": 3}, {}, {})


def test_snapped_envelope_cannot_be_regrown_by_packer():
    with pytest.raises(PlanConstraintError, match="unsupported_buildable_envelope"):
        resolve_parcel({"width_m": 4, "depth_m": 10}, {}, {"grid_m": 3, "min_side_m": 2})


def test_rounding_stays_inside_and_preserves_valid_grids():
    result = resolve_parcel({"width_m": 10.26, "depth_m": 10.2}, {}, {})
    assert result.buildable_width_m == pytest.approx(10.2)
    assert result.buildable_depth_m == pytest.approx(10.2)
    assert result.buildable_width_m <= result.width_m


def test_historical_work_limit_remains():
    result = resolve_parcel({"width_m": 1e9}, {}, {})
    assert result.width_m == 200


@pytest.mark.parametrize("grid", [0.001, 0.015, 1e-300])
def test_grid_matches_centimetre_precision_of_final_polygons(grid):
    with pytest.raises(PlanConstraintError, match="unsupported_grid_precision"):
        resolve_parcel({"width_m": 10.256, "depth_m": 10}, {}, {"grid_m": grid})


def test_invalid_parcel_fails_before_solver(monkeypatch):
    monkeypatch.setattr("app.plan_adapt.optimize_rooms", lambda *args, **kw: pytest.fail("solver called"))
    with pytest.raises(PlanConstraintError):
        adapt({"parcel": {"width_m": 0}})


@pytest.mark.parametrize("field", ["max_width_m", "max_depth_m", "parcel_width_m", "parcel_depth_m"])
def test_invalid_alias_fails_before_normalization(monkeypatch, field):
    from app import pipeline

    monkeypatch.setattr(pipeline.nlu, "parse_brief", lambda *args: pytest.fail("NLU called"))
    with pytest.raises(PlanConstraintError) as error:
        pipeline.generate_plan("Studio", {field: 0})
    assert field in error.value.fields


def test_none_dimensions_are_optional():
    validate_request_dimensions({"max_width_m": None, "parcel_width_m": None})


def test_positive_alias_is_not_enlarged_by_nlu(monkeypatch):
    from app import pipeline
    from app.opening_intervals import OpeningGeometryError
    from app.plan_openings import fit_generated_windows

    observed = []

    def inspect_openings(walls, openings, rooms, **kwargs):
        observed.extend(point["x"] for room in rooms for point in room["polygon"])
        return fit_generated_windows(walls, openings, rooms, **kwargs)

    monkeypatch.setattr("app.plan_adapt.fit_generated_windows", inspect_openings)

    monkeypatch.setenv("TOGETHER_NLU", "0")
    monkeypatch.setenv("TOGETHER_PLANNER", "0")
    monkeypatch.setenv("IMAGE_BACKEND", "procedural")
    monkeypatch.setenv("LAYOUT_SEED", "0")
    # The envelope stays narrow; the generated door now correctly fails instead
    # of returning a one-metre-wide plan with a door outside its wall.
    with pytest.raises(OpeningGeometryError, match="opening_out_of_bounds"):
        pipeline.generate_plan(
            "Studio",
            {"max_width_m": 1, "max_depth_m": 10, "rules": {"min_side_m": 0.5}},
        )
    assert max(observed) == 1


@pytest.mark.parametrize("constraints", [{"parcel_width_m": 0}, {"parcel_width_m": 4, "setback_m": 3}])
def test_pipeline_returns_structured_constraint_error(monkeypatch, constraints):
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.setenv("IMAGE_BACKEND", "procedural")
    monkeypatch.setenv("TOGETHER_NLU", "0")
    monkeypatch.setenv("TOGETHER_PLANNER", "0")
    monkeypatch.setenv("LAYOUT_SEED", "0")
    with TestClient(app) as client:
        response = client.post("/v1/pipeline", json={"brief": "Maison 2 chambres", "constraints": constraints})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] in {"invalid_numeric_constraint", "non_positive_usable_envelope"}
    assert any("width_m" in field for field in response.json()["detail"]["fields"])
