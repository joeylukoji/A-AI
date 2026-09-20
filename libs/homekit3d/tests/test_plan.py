from __future__ import annotations

import pytest

from homekit3d import Plan, PlanError


def test_a_room_needs_three_vertices_and_a_wall_a_length():
    plan = Plan(5, 5)
    with pytest.raises(PlanError):
        plan.room("living", [(0, 0), (1, 1)])
    with pytest.raises(PlanError):
        plan.wall((1, 1), (1.01, 1))


def test_outline_makes_four_exterior_walls_around_the_footprint():
    plan = Plan(6, 4)
    ids = plan.outline()
    assert len(ids) == 4 and all(w.exterior for w in plan.walls)
    assert sorted(round(w.length, 2) for w in plan.walls) == [4.0, 4.0, 6.0, 6.0]
    assert all(w.thickness == 0.25 for w in plan.walls)


def test_walls_from_rooms_makes_one_wall_per_shared_edge(house):
    inner = [w for w in house.walls if not w.exterior]
    keys = {house._edge_key(w.a, w.b) for w in inner}
    assert len(keys) == len(inner)                       # aucune arête en double
    assert any(abs(w.a[0] - 5) < 1e-6 and abs(w.b[0] - 5) < 1e-6 for w in inner)      # la cloison séjour / chambre


def test_walls_from_rooms_adds_the_outline_only_when_missing():
    plan = Plan(4, 4)
    plan.rect_room("living", 0, 0, 4, 4)
    plan.walls_from_rooms()
    assert sum(w.exterior for w in plan.walls) == 4
    count = len(plan.walls)
    plan.walls_from_rooms()
    assert len(plan.walls) == count


def test_an_opening_must_fit_in_its_wall(house):
    wall = house.wall_at(2.5, 0.0)
    with pytest.raises(PlanError):
        house.window(wall, 7.5, width=1.4)
    with pytest.raises(PlanError):
        house.door(wall, -0.1)
    assert len(house.openings) == 2


def test_a_wide_door_is_a_garage_door_and_taller(house):
    wall = house.wall_at(4.0, 6.0)
    op_id = house.door(wall, 1.0, width=2.4)
    op = next(o for o in house.openings if o.id == op_id)
    assert op.kind == "garage" and op.height > 2.1


def test_wall_at_and_room_at(house):
    assert house.wall_at(2.5, 0.0) is not None and house.wall_at(2.5, 2.0) is None
    assert house.get_room(house.room_at(1, 1)).type == "living"
    assert house.room_at(20, 20) is None


def test_place_assigns_the_room_it_stands_in(house):
    item_id = house.place("sofa", 2.0, 2.0)
    item = next(i for i in house.items if i.id == item_id)
    assert house.get_room(item.room).type == "living"


def test_validate_rejects_bad_dimensions_and_orphan_openings(house):
    house.validate()
    house.openings[0].offset = 99
    with pytest.raises(PlanError):
        house.validate()
    with pytest.raises(PlanError):
        Plan(0, 5).validate()
    with pytest.raises(PlanError):
        Plan(5, 5, height=1.0).validate()


def test_dict_round_trip_keeps_everything(house):
    house.place("bed.double", 6.5, 2.0, 90, size=(1.6, 2.0), elevation=0.1, note="x")
    again = Plan.from_dict(house.to_dict())
    assert again.to_dict() == house.to_dict()
    assert again.get_room(house.rooms[0].id).area == house.rooms[0].area


def test_ids_stay_unique_after_a_round_trip(house):
    again = Plan.from_dict(house.to_dict())
    new = again.place("plant", 1, 1)
    assert new not in {i.id for i in house.items}
    assert again.wall((0, 0), (1, 0)) not in {w.id for w in house.walls}


AAI_DOC = {
    "floor": {"height_m": 2.7, "bounds": {"width": 8, "depth": 6}},
    "walls": [{"id": "w_outer_1", "a": {"x": 0, "y": 0}, "b": {"x": 8, "y": 0}, "thickness_m": 0.2},
              {"id": "w_i1", "a": {"x": 4, "y": 0}, "b": {"x": 4, "y": 6}, "thickness_m": 0.15}],
    "rooms": [{"id": "r1", "type": "living", "name": "Séjour",
               "polygon": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 6}, {"x": 0, "y": 6}]},
              {"id": "bad", "type": "x", "polygon": [{"x": 0, "y": 0}]}],
    "openings": [{"id": "o1", "wall_id": "w_i1", "type": "door", "offset_m": 0.5, "width_m": 0.8},
                 {"id": "o2", "wall_id": "w_outer_1", "type": "window", "offset_m": 7.5, "width_m": 1.2},
                 {"id": "o3", "wall_id": "w_outer_1", "type": "door", "offset_m": 1.0, "width_m": 2.4},
                 {"id": "orphan", "wall_id": "nope", "type": "door"}],
    "furniture": [{"id": "f1", "catalog_id": "sofa.2seat", "room_id": "r1", "position": {"x": 2, "y": 5}, "rotation_deg": 180,
                   "size_m": {"w": 1.8, "d": 0.85, "h": 0.8}},
                  {"id": "f2", "catalog_id": "unknown.thing", "room_id": "r1", "position": {"x": 1, "y": 1}},
                  {"id": "f3", "catalog_id": "car.sedan", "room_id": "r1", "position": {"x": 2, "y": 3}, "rotation_deg": 90,
                   "size_m": {"w": 4.2, "d": 1.8, "h": 1.45}}],
}


def test_from_aai_converts_walls_rooms_openings_and_furniture():
    plan = Plan.from_aai(AAI_DOC)
    assert (plan.width, plan.depth, plan.height) == (8, 6, 2.7)
    assert {w.id: w.exterior for w in plan.walls} == {"w_outer_1": True, "w_i1": False}
    assert [r.id for r in plan.rooms] == ["r1"]                                  # la pièce à un sommet est ignorée
    kinds = {o.id: o.kind for o in plan.openings}
    assert kinds == {"o1": "door", "o2": "window", "o3": "garage"}              # l'ouverture sans mur est ignorée
    assert [(i.role, i.rot, i.size) for i in plan.items] == [("sofa", 180.0, (1.8, 0.85)), ("car", 90.0, (4.2, 1.8))]


def test_from_aai_clamps_an_opening_that_overruns_its_wall():
    plan = Plan.from_aai(AAI_DOC)
    window = next(o for o in plan.openings if o.id == "o2")
    assert window.offset + window.width <= 8 + 1e-9
    plan.validate()


def test_from_aai_is_robust_to_an_empty_document():
    plan = Plan.from_aai({})
    assert (plan.width, plan.depth) == (12, 10) and not plan.walls and not plan.items
