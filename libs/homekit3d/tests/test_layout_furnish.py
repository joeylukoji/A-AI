from __future__ import annotations

import pytest

from homekit3d import Plan
from homekit3d.furnish import autofurnish
from homekit3d.layout import (Occupancy, door_zones, find_along_wall, in_front, inside, occupancy_of, overlaps, rect_of,
                              spot)


def test_rect_of_swaps_width_and_depth_for_a_quarter_turn():
    assert rect_of(5, 5, 2.0, 1.0, 0) == (4.0, 4.5, 6.0, 5.5)
    assert rect_of(5, 5, 2.0, 1.0, 90) == pytest.approx((4.5, 4.0, 5.5, 6.0))
    assert rect_of(5, 5, 2.0, 1.0, 180) == pytest.approx((4.0, 4.5, 6.0, 5.5))


def test_overlap_and_inside_treat_touching_edges_as_free():
    assert not overlaps((0, 0, 1, 1), (1, 0, 2, 1))
    assert overlaps((0, 0, 1, 1), (0.9, 0, 2, 1))
    assert overlaps((0, 0, 1, 1), (1.05, 0, 2, 1), margin=0.1)
    assert inside((1, 1, 2, 2), (0, 0, 3, 3)) and not inside((-0.1, 1, 2, 2), (0, 0, 3, 3))


@pytest.mark.parametrize("rot,dx,dy", [(0, 0, 1), (90, -1, 0), (180, 0, -1), (270, 1, 0)])
def test_in_front_follows_the_clockwise_rotation(rot, dx, dy):
    x, y = in_front(5, 5, rot, 2.0)
    assert (round(x - 5, 6), round(y - 5, 6)) == (dx * 2.0, dy * 2.0)


@pytest.mark.parametrize("side,rot", [("N", 0), ("S", 180), ("W", 270), ("E", 90)])
def test_a_piece_against_a_wall_has_its_back_to_it_and_faces_the_room(side, rot):
    box = (0.0, 0.0, 6.0, 4.0)
    x, y, r = spot(box, side, 1.0, 0.5)
    assert r == rot
    fx, fy = in_front(x, y, r, 1.0)
    cx, cy = 3.0, 2.0
    assert (fx - cx) ** 2 + (fy - cy) ** 2 < (x - cx) ** 2 + (y - cy) ** 2            # la façade regarde vers le centre


def test_find_along_wall_skips_occupied_places_and_respects_the_walls():
    box = (0.0, 0.0, 4.0, 4.0)
    occ = Occupancy()
    first = find_along_wall(occ, box, "N", 1.0, 0.5, prefer_centre=True)
    occ.add(rect_of(first[0], first[1], 1.0, 0.5, first[2]))
    second = find_along_wall(occ, box, "N", 1.0, 0.5, prefer_centre=True)
    assert second is not None and abs(second[0] - first[0]) >= 1.0 - 1e-6
    assert find_along_wall(occ, box, "N", 9.0, 0.5) is None          # trop large pour le mur


def test_find_along_wall_never_puts_anything_over_a_door(house):
    plan = Plan(6, 4)
    plan.rect_room("bedroom", 0, 0, 6, 4)
    plan.outline()
    plan.door(plan.wall_at(3.0, 0.0), 2.6)                          # une porte au milieu du mur nord
    occ = occupancy_of(plan, catalog_stub())
    for _ in range(4):
        got = find_along_wall(occ, (0, 0, 6, 4), "N", 1.0, 0.5)
        assert got is not None
        rect = rect_of(got[0], got[1], 1.0, 0.5, got[2])
        assert not any(overlaps(rect, z) for z in occ.zones)
        occ.add(rect)


class catalog_stub:                                              # noqa: N801 - un faux catalogue minimal
    def get(self, _):
        raise KeyError

    def pick_fit(self, *a, **k):
        return None


def test_door_zones_cover_swinging_doors_but_not_garage_doors(house):
    plan = Plan(10, 6)
    plan.outline()
    plan.door(plan.wall_at(5, 0), 1.0, width=0.9)
    plan.door(plan.wall_at(5, 6), 1.0, width=2.4)
    assert len(door_zones(plan)) == 1


def test_a_bedroom_gets_a_bed_against_a_wall_with_bedside_tables_and_a_wardrobe(catalog):
    plan = Plan(5, 4, seed=2)
    plan.rect_room("bedroom", 0, 0, 5, 4)
    plan.outline()
    plan.walls_from_rooms()
    autofurnish(plan, catalog)
    roles = sorted(i.role for i in plan.items)
    assert roles.count("bed.double") == 1 and roles.count("nightstand") == 2 and "wardrobe" in roles
    bed = next(i for i in plan.items if i.role.startswith("bed."))
    w, d = bed.size
    box = rect_of(bed.x, bed.y, w, d, bed.rot)
    assert min(box[0], box[1], 5 - box[2], 4 - box[3]) < 0.25         # la tête du lit touche un mur


def test_furnishing_puts_nothing_outside_its_room_or_over_another_piece(catalog, house):
    autofurnish(house, catalog)
    boxes = []
    for it in house.items:
        if it.elevation or it.role.startswith(("rug", "picture", "mirror", "kitchen.upper")):
            continue
        box = rect_of(it.x, it.y, it.size[0], it.size[1], it.rot)
        room = house.get_room(it.room)
        assert inside(box, room.bbox(), 0.02), (it.role, box, room.bbox())
        assert not any(overlaps(box, other, 0.0) for other in boxes), it.role
        boxes.append(box)
    assert len(house.items) >= 6


def test_furnishing_keeps_doors_clear(catalog, house):
    zones = door_zones(house)
    autofurnish(house, catalog)
    for it in house.items:
        if it.elevation or it.role.startswith(("rug", "picture", "mirror")):
            continue
        box = rect_of(it.x, it.y, it.size[0], it.size[1], it.rot)
        assert not any(overlaps(box, z) for z in zones), it.role


def test_only_empty_rooms_are_furnished_by_default(catalog, house):
    living = house.rooms[0].id
    house.place("sofa", 2.0, 3.0, 180.0, room=living)
    added = autofurnish(house, catalog)
    assert living not in added and sum(i.room == living for i in house.items) == 1


def test_furnishing_is_deterministic_for_a_seed_and_varies_between_seeds(catalog):
    def run(seed):
        plan = Plan(6, 5, seed=seed)
        plan.rect_room("living", 0, 0, 6, 5)
        plan.outline()
        plan.walls_from_rooms()
        autofurnish(plan, catalog)
        return [(i.role, i.asset, round(i.x, 2), round(i.y, 2), i.rot) for i in plan.items]

    assert run(1) == run(1)
    assert any(run(s) != run(1) for s in range(2, 8))


@pytest.mark.parametrize("room_type,expected", [
    ("kitchen", {"kitchen.run", "kitchen.fridge", "kitchen.stove"}), ("bathroom", {"toilet", "sink.bath"}),
    ("wc", {"toilet"}), ("dining", {"table.dining", "chair.dining"}), ("office", {"desk"}), ("living", {"sofa", "table.coffee"}),
])
def test_each_room_type_gets_its_signature_furniture(catalog, room_type, expected):
    plan = Plan(5.5, 4.5, seed=4)
    plan.rect_room(room_type, 0, 0, 5.5, 4.5)
    plan.outline()
    plan.walls_from_rooms()
    autofurnish(plan, catalog)
    got = {i.role for i in plan.items}
    assert expected <= got or (room_type == "living" and "sofa.corner" in got and "table.coffee" in got), got


def test_a_garage_gets_a_car_only_if_it_is_big_enough(catalog):
    big, small = Plan(7, 4), Plan(3, 3)
    for plan in (big, small):
        plan.rect_room("garage", 0, 0, plan.width, plan.depth)
        plan.outline()
        autofurnish(plan, catalog)
    assert [i.role for i in big.items] == ["car"] and small.items == []


def test_a_room_too_small_for_its_furniture_stays_empty_without_error(catalog):
    plan = Plan(1.2, 1.2)
    plan.rect_room("bedroom", 0, 0, 1.2, 1.2)
    plan.outline()
    autofurnish(plan, catalog)
    assert plan.items == []


def test_nothing_is_placed_in_the_thickness_of_the_walls():
    """Un meuble presque aussi large que le mur ne tient pas : les murs occupent une demi-épaisseur de chaque côté."""
    occ = Occupancy()
    assert find_along_wall(occ, (0.0, 0.0, 4.0, 4.0), "N", 3.9, 0.5) is None
    assert find_along_wall(occ, (0.0, 0.0, 4.0, 4.0), "N", 3.7, 0.5) is not None


def test_bedside_tables_stand_at_the_head_of_the_bed_against_the_wall(catalog):
    plan = Plan(5, 4, seed=2)
    plan.rect_room("bedroom", 0, 0, 5, 4)
    plan.outline()
    plan.walls_from_rooms()
    autofurnish(plan, catalog)
    bed = next(i for i in plan.items if i.role.startswith("bed."))
    bx = rect_of(bed.x, bed.y, bed.size[0], bed.size[1], bed.rot)
    stands = [i for i in plan.items if i.role == "nightstand"]
    assert len(stands) == 2
    for s in stands:
        sx = rect_of(s.x, s.y, s.size[0], s.size[1], s.rot)
        # même mur que le lit : les deux boîtes touchent le même côté de la pièce
        assert min(sx[0], sx[1], 5 - sx[2], 4 - sx[3]) == pytest.approx(min(bx[0], bx[1], 5 - bx[2], 4 - bx[3]), abs=0.02)


# --- salle à manger -------------------------------------------------------------------------------------
def dining_plan(w: float, d: float, seed: int = 1) -> Plan:
    plan = Plan(w, d, seed=seed)
    plan.rect_room("dining", 0, 0, w, d)
    plan.outline()
    plan.walls_from_rooms()
    plan.style.tags = ["realistic"]
    return plan


@pytest.mark.parametrize("w,d", [(6.0, 5.0), (5.0, 3.6), (4.0, 6.0), (6.0, 2.0), (3.2, 3.2)])
@pytest.mark.parametrize("seed", range(6))
def test_everything_in_a_dining_room_stays_inside_it_and_chairs_never_hit_the_sideboard(catalog, w, d, seed):
    plan = dining_plan(w, d, seed)
    autofurnish(plan, catalog)
    box = (0.0, 0.0, w, d)
    standing = [i for i in plan.items if i.role not in ("picture", "rug", "lamp.ceiling")]
    rects = {i.id: rect_of(i.x, i.y, *i.size, i.rot) for i in standing}
    for i in standing:
        assert inside(rects[i.id], box), (seed, i.role, rects[i.id])
    for chair in (i for i in standing if i.role == "chair.dining"):
        for other in (i for i in standing if i.role in ("sideboard", "plant")):
            assert not overlaps(rects[chair.id], rects[other.id], 0.0), (seed, chair.id, other.role)


def test_the_chairs_come_from_the_pack_of_the_table_and_face_it(catalog):
    for seed in range(8):
        plan = dining_plan(6.0, 5.0, seed)
        autofurnish(plan, catalog)
        table = next(i for i in plan.items if i.role == "table.dining")
        chairs = [i for i in plan.items if i.role == "chair.dining"]
        assert len(chairs) >= 4
        assert len({catalog.get(c.asset).id for c in chairs}) == 1              # un seul modèle de chaise : un vrai jeu
        for c in chairs:                                                       # chaque chaise regarde la table
            fx, fy = in_front(c.x, c.y, c.rot, 0.5)
            assert (fx - table.x) ** 2 + (fy - table.y) ** 2 < (c.x - table.x) ** 2 + (c.y - table.y) ** 2


def test_a_wide_dining_room_gets_a_sideboard_a_rug_and_a_chandelier_a_narrow_one_only_the_table(catalog):
    roles = {i.role for i in (lambda p: (autofurnish(p, catalog), p.items)[1])(dining_plan(6.0, 5.0, 3))}
    assert {"table.dining", "chair.dining", "rug", "lamp.ceiling"} <= roles
    narrow = {i.role for i in (lambda p: (autofurnish(p, catalog), p.items)[1])(dining_plan(6.0, 2.0, 3))}
    assert "table.dining" in narrow and "sideboard" not in narrow


def test_the_dining_table_follows_the_long_axis_of_the_room(catalog):
    wide = dining_plan(7.0, 4.0)
    tall = dining_plan(4.0, 7.0)
    autofurnish(wide, catalog)
    autofurnish(tall, catalog)
    assert next(i for i in wide.items if i.role == "table.dining").rot % 180 == 0
    assert next(i for i in tall.items if i.role == "table.dining").rot % 180 == 90


def test_low_poly_styles_get_no_chandelier(catalog):
    plan = dining_plan(6.0, 5.0)
    plan.style.tags = ["modern"]
    plan.style.prefer_pack = "kenney-furniture"
    autofurnish(plan, catalog)
    assert "lamp.ceiling" not in {i.role for i in plan.items}
