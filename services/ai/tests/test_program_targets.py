"""L'adaptation vise les surfaces DEMANDÉES, pas celles du premier tracé."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import plan_adapt  # noqa: E402
from app.main import PipelineRequest, _pipeline  # noqa: E402
from app.vectorize import _program, vectorize  # noqa: E402


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    for name, value in (("TOGETHER_PLANNER", "0"), ("TOGETHER_NLU", "0"), ("IMAGE_BACKEND", "procedural")):
        monkeypatch.setenv(name, value)
    for name in ("TOGETHER_API_KEY", "EDENAI_API_KEY", "LAYOUT_VARIANTS", "LAYOUT_SEED"):
        monkeypatch.delenv(name, raising=False)


def _rect(x0, y0, x1, y1):
    return [{"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]


def _area(room):
    xs = [p["x"] for p in room["polygon"]]
    ys = [p["y"] for p in room["polygon"]]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


SPEC = {"rooms": [
    {"type": "living", "area_m2": 30, "count": 1},
    {"type": "bedroom", "area_m2": 12, "count": 2},
    {"type": "kitchen", "area_m2": 12, "count": 1},
    {"type": "bathroom", "area_m2": 6, "count": 1},
]}


# --- vectorize embarque le programme --------------------------------------------------------

def test_the_program_lists_one_entry_per_requested_room():
    program = _program(SPEC)
    assert [(p["type"], p["area_m2"]) for p in program] == [
        ("living", 30.0), ("bedroom", 12.0), ("bedroom", 12.0), ("kitchen", 12.0), ("bathroom", 6.0)]
    assert len({p["id"] for p in program}) == len(program)


def test_a_spec_without_rooms_gives_an_empty_program():
    assert _program({}) == [] and _program({"rooms": "x"}) == []


def test_vectorize_carries_the_program_in_the_plan():
    layout = {"width": 12, "depth": 10, "rooms": [{"id": "a", "type": "living", "polygon": _rect(0, 0, 12, 10)}]}
    out = vectorize({"layout": layout, "building_spec": SPEC})["plan_document"]
    assert [p["type"] for p in out["program"]].count("bedroom") == 2


def test_vectorize_adds_no_program_without_a_spec():
    layout = {"width": 12, "depth": 10, "rooms": [{"id": "a", "type": "living", "polygon": _rect(0, 0, 12, 10)}]}
    assert "program" not in vectorize({"layout": layout, "building_spec": {}})["plan_document"]


# --- l'adaptation s'en sert -----------------------------------------------------------------

def _doc(living_depth: float, program=None):
    """Un plan dont le séjour est minuscule : sans programme, l'adaptation le garderait minuscule."""
    rooms = [
        {"id": "l", "type": "living", "name": "Séjour", "polygon": _rect(0, 0, 3, living_depth)},
        {"id": "b1", "type": "bedroom", "name": "Chambre 1", "polygon": _rect(3, 0, 7, 3)},
        {"id": "b2", "type": "bedroom", "name": "Chambre 2", "polygon": _rect(7, 0, 11, 3)},
        {"id": "k", "type": "kitchen", "name": "Cuisine", "polygon": _rect(0, 5, 4, 8)},
        {"id": "s", "type": "bathroom", "name": "SDB", "polygon": _rect(4, 5, 7, 8)},
    ]
    doc = {"version": "1.0", "units": "m",
           "floor": {"level": 0, "height_m": 2.7, "bounds": {"width": 12, "depth": 10}},
           "walls": [], "rooms": rooms, "openings": []}
    if program is not None:
        doc["program"] = program
    return doc


def _adapt(doc):
    return plan_adapt.adapt({"plan_document": doc, "parcel": {"width_m": 12, "depth_m": 10}, "rules": {}})["plan_document"]


def _living(doc):
    return next(_area(r) for r in doc["rooms"] if r["type"] == "living")


def test_the_requested_areas_replace_the_first_layout_areas():
    program = _program(SPEC)
    with_program = _adapt(_doc(2.0, program))
    without = _adapt(_doc(2.0))
    assert _living(with_program) > _living(without) + 5          # le séjour demandé (30) l'emporte sur le tracé (6)
    assert with_program["program"] == program                    # et le programme voyage encore avec le plan


def test_a_program_that_no_longer_matches_the_plan_is_ignored():
    stale = _program({"rooms": SPEC["rooms"] + [{"type": "office", "area_m2": 10, "count": 1}]})
    out = _adapt(_doc(2.0, stale))
    assert "program" not in out and all(r["type"] != "office" for r in out["rooms"])


@pytest.mark.parametrize("bad", [
    "x", [], [1], [{"type": "living"}], [{"type": "living", "area_m2": -3}], [{"type": "living", "area_m2": "abc"}],
    [{"type": 7, "area_m2": 10}], [{"type": "living", "area_m2": 1e9}],
])
def test_a_malformed_program_is_ignored_without_error(bad):
    out = _adapt(_doc(2.0, bad))
    assert "program" not in out and any(r["type"] == "living" for r in out["rooms"])


@pytest.mark.parametrize("area", [-3, 0, 0.2, 1e9, 501])
def test_an_out_of_range_area_invalidates_an_otherwise_matching_program(area):
    program = _program(SPEC)
    program[0]["area_m2"] = area
    assert "program" not in _adapt(_doc(2.0, program))


def test_hallway_segments_are_merged_into_one_bounded_target():
    halls = [{"id": f"h{i}", "type": "hallway", "area_m2": 6.0, "polygon": []} for i in range(5)]
    rooms = [{"id": "l", "type": "living", "area_m2": 20.0}] + halls
    merged = plan_adapt._merge_hallways(rooms, 120.0)
    assert [r["type"] for r in merged].count("hallway") == 1
    hall = next(r for r in merged if r["type"] == "hallway")
    assert hall["area_m2"] == pytest.approx(12.0)                # 30 m² de segments, plafonnés à 10 % de la maison


def test_a_single_hallway_is_left_alone():
    rooms = [{"id": "h", "type": "hallway", "area_m2": 30.0}]
    assert plan_adapt._merge_hallways(rooms, 120.0) == rooms


def test_the_program_still_applies_when_the_packer_split_the_hallway():
    """Le packer découpe les couloirs : leur nombre ne doit pas invalider le programme."""
    doc = _doc(2.0, _program(SPEC))
    doc["rooms"] += [{"id": f"h{i}", "type": "hallway", "name": "Couloir", "polygon": _rect(0, 8 + i, 1, 9 + i)}
                     for i in range(3)]
    assert "program" in _adapt(doc)


# --- bout en bout : on retrouve la maison demandée ---------------------------------------------

def test_the_pipeline_respects_the_requested_proportions(monkeypatch):
    monkeypatch.setenv("LAYOUT_VARIANTS", "on")
    monkeypatch.setenv("LAYOUT_SEED", "3")
    out = _pipeline(PipelineRequest(brief="Maison 3 chambres, séjour, cuisine, salle de bain, WC et garage",
                                    constraints={"parcel_width_m": 12, "parcel_depth_m": 10}))["plan_document"]
    total = sum(_area(r) for r in out["rooms"])
    hall = sum(_area(r) for r in out["rooms"] if r["type"] == "hallway")
    assert hall / total < 0.15                                    # le couloir n'est plus le quart de la maison
    assert sum(1 for r in out["rooms"] if r["type"] == "hallway") == 1
    assert _living(out) > 20
    bedrooms = [_area(r) for r in out["rooms"] if r["type"] == "bedroom"]
    assert len(bedrooms) == 3 and all(9 <= a <= 16 for a in bedrooms)
