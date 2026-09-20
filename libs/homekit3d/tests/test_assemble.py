from __future__ import annotations

import math

import pytest

from homekit3d import Plan
from homekit3d.assemble import DEFAULT_ELEVATION, FIT_MAX, FIT_MIN, assemble


def plan_with(*items, **kw) -> Plan:
    plan = Plan(8, 6, seed=1)
    plan.rect_room("living", 0, 0, 8, 6)
    plan.rect_room("kitchen", 8, 0, 12, 6) if kw.get("kitchen") else None
    for role, x, y, rot, size in items:
        plan.place(role, x, y, rot, size=size)
    return plan


def test_a_known_role_becomes_a_placed_asset_at_its_position(catalog):
    placed = assemble(plan_with(("sofa", 3.0, 4.0, 180.0, None)), catalog).placed
    assert len(placed) == 1
    p = placed[0]
    assert (p.kind, p.role, p.x, p.y, p.rot) == ("asset", "sofa", 3.0, 4.0, 180.0)
    assert p.asset.role == "sofa" and p.scale[0] == pytest.approx(p.asset.scale)


def test_an_unknown_role_is_reported_not_silently_dropped(catalog):
    a = assemble(plan_with(("dragon", 1, 1, 0, None), ("sofa", 3, 3, 0, None)), catalog)
    assert a.skipped == ["dragon"] and len(a.placed) == 1


def test_the_model_is_chosen_close_to_the_requested_footprint(catalog):
    big = assemble(plan_with(("sofa", 3, 3, 0, (2.6, 1.0))), catalog).placed[0]
    small = assemble(plan_with(("sofa", 3, 3, 0, (1.6, 0.8))), catalog).placed[0]
    assert big.asset.footprint[0] >= small.asset.footprint[0] - 0.5


def test_the_scale_never_deviates_much_from_the_real_size(catalog):
    for size in ((0.5, 0.5), (5.0, 5.0), (2.0, 0.9)):
        p = assemble(plan_with(("sofa", 3, 3, 0, size)), catalog).placed[0]
        ratio = p.scale[0] / p.asset.scale
        assert FIT_MIN - 1e-9 <= ratio <= FIT_MAX + 1e-9
        assert p.scale[0] == p.scale[1] == p.scale[2]                 # échelle uniforme : pas de meuble déformé


def test_a_rug_is_stretched_flat_to_the_requested_size(catalog):
    p = assemble(plan_with(("rug", 4, 3, 0, (3.0, 2.0))), catalog).placed[0]
    assert p.scale[0] == pytest.approx(3.0 / p.asset.size[0]) and p.scale[2] == pytest.approx(2.0 / p.asset.size[2])
    assert p.scale[1] == p.asset.scale                              # l'épaisseur du tapis ne change pas


def test_wall_objects_get_a_default_height_and_ceiling_lights_hang_from_the_ceiling(catalog):
    plan = plan_with(("picture", 2, 0.1, 0, None), ("lamp.ceiling", 4, 3, 0, None))
    by_role = {p.role: p for p in assemble(plan, catalog).placed}
    assert by_role["picture"].z == DEFAULT_ELEVATION["picture"]
    assert 2.0 < by_role["lamp.ceiling"].z < plan.height


def test_an_explicit_elevation_wins_over_the_default(catalog):
    plan = Plan(6, 6)
    plan.rect_room("living", 0, 0, 6, 6)
    plan.place("picture", 1, 1, elevation=1.8)
    assert assemble(plan, catalog).placed[0].z == 1.8


def test_an_imposed_model_is_used(catalog):
    plan = Plan(6, 6)
    plan.rect_room("living", 0, 0, 6, 6)
    plan.place("sofa", 2, 2, asset="kaykit-furniture/couch")
    assert assemble(plan, catalog).placed[0].asset.id == "kaykit-furniture/couch"


def test_the_same_plan_and_seed_choose_the_same_models(catalog):
    a = [p.asset.id for p in assemble(plan_with(("chair.dining", 1, 1, 0, None), ("chair.dining", 2, 2, 0, None)), catalog).placed]
    b = [p.asset.id for p in assemble(plan_with(("chair.dining", 1, 1, 0, None), ("chair.dining", 2, 2, 0, None)), catalog).placed]
    assert a == b


def test_a_car_and_a_fireplace_are_built_by_code(catalog):
    a = assemble(plan_with(("car", 4, 3, 90.0, (4.2, 1.8)), ("fireplace", 1, 3, 90.0, (0.7, 0.55))), catalog)
    assert [p.kind for p in a.placed] == ["procedural", "procedural"] and not a.skipped
    car = a.placed[0]
    assert car.footprint == (4.2, 1.8) and car.rot == 180.0        # +90° : le modèle a sa longueur selon la profondeur


def test_a_car_lying_along_x_at_zero_degrees_is_turned_a_quarter(catalog):
    p = assemble(plan_with(("car", 4, 3, 0.0, (4.2, 1.8))), catalog).placed[0]
    assert p.rot == 90.0


def kitchen(length=3.0, others=()) -> Plan:
    plan = Plan(6, 4)
    plan.rect_room("kitchen", 0, 0, 6, 4)
    plan.place("kitchen.run", 3.0, 0.4, 0.0, size=(length, 0.62))
    for role, x, size in others:
        plan.place(role, x, 0.4, 0.0, size=size)
    return plan


def test_a_kitchen_run_is_tiled_into_base_units_that_fill_its_length(catalog):
    a = assemble(kitchen(3.0), catalog)
    xs = [p.x for p in a.placed]
    assert len(a.placed) >= 3 and xs == sorted(xs)
    widths = [p.asset.footprint[0] * p.scale[0] / p.asset.scale for p in a.placed]
    assert sum(widths) == pytest.approx(3.0, abs=0.05)
    assert all(p.rot == 0.0 for p in a.placed) and all(abs(p.y - 0.4) < 1e-9 for p in a.placed)


def test_a_kitchen_run_has_exactly_one_sink(catalog):
    roles = [p.role for p in assemble(kitchen(3.6), catalog).placed]
    assert roles.count("kitchen.sink") == 1 and roles.count("kitchen.base") >= 2


def test_the_run_leaves_room_for_the_stove_and_the_fridge(catalog):
    plan = kitchen(3.6, others=[("kitchen.stove", 2.4, (0.6, 0.6)), ("kitchen.fridge", 4.6, (0.7, 0.7))])
    units = [p for p in assemble(plan, catalog).placed if p.role.startswith("kitchen.") and p.role in ("kitchen.base", "kitchen.sink")]
    for u in units:
        half = u.asset.footprint[0] * u.scale[0] / u.asset.scale / 2
        assert not (2.4 - 0.3 - 0.02 < u.x + half and u.x - half < 2.4 + 0.3 + 0.02 and abs(u.x - 2.4) < half + 0.3), u.x


def test_a_rotated_kitchen_run_follows_its_axis(catalog):
    plan = Plan(4, 6)
    plan.rect_room("kitchen", 0, 0, 4, 6)
    plan.place("kitchen.run", 0.4, 3.0, 90.0, size=(3.0, 0.62))
    placed = assemble(plan, catalog).placed
    assert all(abs(p.x - 0.4) < 1e-9 for p in placed)                # le long de y, contre le mur ouest
    assert max(p.y for p in placed) - min(p.y for p in placed) > 1.5
    assert all(math.isclose(p.rot, 90.0) for p in placed)


def test_a_cutaway_drops_what_hangs_above_the_cut(catalog):
    plan = Plan(6, 6)
    plan.rect_room("living", 0, 0, 6, 6)
    plan.place("sofa", 3, 4, 180)
    plan.place("picture", 3, 5.9, 180, elevation=1.45)
    plan.place("lamp.ceiling", 3, 3, 0)
    full = {p.role for p in assemble(plan, catalog).placed}
    plan.cutaway = 1.2
    cut = {p.role for p in assemble(plan, catalog).placed}
    assert {"sofa", "picture", "lamp.ceiling"} <= full and cut == {"sofa"}
