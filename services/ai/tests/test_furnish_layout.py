"""Placement du mobilier : lits dans le sens de la pièce, armoires, portes dégagées."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import furnish as fu  # noqa: E402
from app.diffusion import default_openings, perimeter_and_internal_walls  # noqa: E402
from app.furnish import CATALOG, door_passages, door_zones, furnish  # noqa: E402
from app.layout_opt import pack_house  # noqa: E402
from test_layout_invariants import CORPUS  # noqa: E402


def _room(rid, typ, x0, y0, x1, y1):
    return {"id": rid, "type": typ, "name": typ,
            "polygon": [{"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]}


def _wall(wid, ax, ay, bx, by):
    return {"id": wid, "a": {"x": ax, "y": ay}, "b": {"x": bx, "y": by}, "thickness_m": 0.15}


def _door(wall_id, offset, width=0.9):
    return {"id": f"o_{wall_id}", "wall_id": wall_id, "type": "door", "offset_m": offset, "width_m": width}


def _footprint(item):
    w, d = fu._world_footprint(item["size_m"]["w"], item["size_m"]["d"], item["rotation_deg"])
    x, y = item["position"]["x"], item["position"]["y"]
    return x - w / 2, y - d / 2, x + w / 2, y + d / 2


def _overlap(a, b):
    return a[0] < b[2] - 1e-6 and a[2] > b[0] + 1e-6 and a[1] < b[3] - 1e-6 and a[3] > b[1] + 1e-6


# --- Zones de débattement -------------------------------------------------------------------

def test_a_door_on_a_horizontal_wall_reserves_the_square_on_its_swing_side():
    zones = door_zones([_door("w", 2.0)], [_wall("w", 0, 0, 10, 0)])
    assert zones == [pytest.approx((2.0, 0.0, 2.95, 0.95))]        # normale (-uy, ux) = +y : la pièce du sud


def test_a_door_on_a_vertical_wall_swings_to_the_west():
    zones = door_zones([_door("w", 3.0)], [_wall("w", 0, 0, 0, 10)])
    assert zones == [pytest.approx((-0.95, 3.0, 0.0, 3.95))]


def test_the_swing_side_follows_the_wall_direction():
    """`w_outer_3` va de l'est vers l'ouest : le battant s'ouvre de l'autre côté."""
    zones = door_zones([_door("w", 2.0)], [_wall("w", 10, 0, 0, 0)])
    assert zones == [pytest.approx((7.05, -0.95, 8.0, 0.0))]


def test_a_garage_door_has_no_leaf_and_reserves_nothing():
    assert door_zones([_door("w", 1.0, 2.4)], [_wall("w", 0, 0, 10, 0)]) == []
    assert door_passages([_door("w", 1.0, 2.4)], [_wall("w", 0, 0, 10, 0)]) == []


def test_windows_and_unknown_walls_reserve_nothing():
    window = {"id": "o", "wall_id": "w", "type": "window", "offset_m": 1, "width_m": 1.2}
    assert door_zones([window], [_wall("w", 0, 0, 10, 0)]) == []
    assert door_zones([_door("missing", 1)], [_wall("w", 0, 0, 10, 0)]) == []
    assert door_zones(None, None) == [] and door_zones([{"type": "door"}, 3], [{"id": "w"}]) == []


def test_the_passage_is_on_the_side_the_door_does_not_open_to():
    passage = door_passages([_door("w", 2.0)], [_wall("w", 0, 0, 10, 0)])
    assert passage == [pytest.approx((2.0, -fu.PASSAGE, 2.9, 0.0))]


@pytest.mark.parametrize(
    "hinge,swing,expected",
    [
        ("start", "positive", (2.0, 0.0, 2.95, 0.95)),
        ("end", "positive", (1.95, 0.0, 2.9, 0.95)),
        ("start", "negative", (2.0, -0.95, 2.95, 0.0)),
        ("end", "negative", (1.95, -0.95, 2.9, 0.0)),
    ],
)
def test_explicit_door_semantics_control_the_reserved_swing_square(hinge, swing, expected):
    door = {**_door("w", 2.0), "hinge": hinge, "swing": swing}
    assert door_zones([door], [_wall("w", 0, 0, 10, 0)]) == [pytest.approx(expected)]


def test_explicit_swing_moves_the_passage_to_the_opposite_side():
    door = {**_door("w", 2.0), "hinge": "end", "swing": "negative"}
    passage = door_passages([door], [_wall("w", 0, 0, 10, 0)])
    assert passage == [pytest.approx((2.0, 0.0, 2.9, fu.PASSAGE))]


@pytest.mark.parametrize(
    "wall,expected_zone,expected_passage",
    [
        (_wall("w", 0, 0, 0, 10), (-0.95, 2.0, 0.0, 2.95), (0.0, 2.0, fu.PASSAGE, 2.9)),
        (_wall("w", 10, 0, 0, 0), (7.05, -0.95, 8.0, 0.0), (7.1, 0.0, 8.0, fu.PASSAGE)),
    ],
)
def test_explicit_semantics_follow_vertical_and_reversed_walls(wall, expected_zone, expected_passage):
    door = {**_door("w", 2.0), "hinge": "start", "swing": "positive"}
    assert door_zones([door], [wall]) == [pytest.approx(expected_zone)]
    assert door_passages([door], [wall]) == [pytest.approx(expected_passage)]


# --- Lits et armoires -----------------------------------------------------------------------

def _bedroom_items(w, h, **kw):
    return furnish([_room("b", "bedroom", 0, 0, w, h)], **kw)


def test_a_wide_shallow_bedroom_gets_a_double_bed_lying_across_it():
    items = _bedroom_items(5.0, 2.4)
    bed = next(i for i in items if i["catalog_id"].startswith("bed."))
    assert bed["catalog_id"] == "bed.double" and bed["rotation_deg"] == 270      # tête à l'ouest
    x0, y0, x1, y1 = _footprint(bed)
    assert x0 >= 0 and y0 >= 0 and x1 <= 5.0 and y1 <= 2.4


def test_a_deep_bedroom_keeps_the_head_at_the_north_wall():
    bed = next(i for i in _bedroom_items(3.6, 4.0) if i["catalog_id"].startswith("bed."))
    assert bed["catalog_id"] == "bed.double" and bed["rotation_deg"] == 0


def test_a_narrow_bedroom_still_takes_a_double_bed():
    """2,7 m de large : un lit de 1,6 m laisse 1,1 m de passage."""
    bed = next(i for i in _bedroom_items(2.7, 4.6) if i["catalog_id"].startswith("bed."))
    assert bed["catalog_id"] == "bed.double"


def test_a_tiny_bedroom_falls_back_to_a_single_bed():
    bed = next(i for i in _bedroom_items(2.0, 3.0) if i["catalog_id"].startswith("bed."))
    assert bed["catalog_id"] == "bed.single"


@pytest.mark.parametrize("size", [(4.0, 3.2), (5.0, 2.4), (3.6, 4.0)])
def test_a_regular_bedroom_has_a_wardrobe_that_touches_neither_bed_nor_walls(size):
    items = _bedroom_items(*size)
    wardrobe = next(i for i in items if i["catalog_id"] == "wardrobe")
    bed = next(i for i in items if i["catalog_id"].startswith("bed."))
    assert not _overlap(_footprint(wardrobe), _footprint(bed))
    x0, y0, x1, y1 = _footprint(wardrobe)
    assert x0 >= 0 and y0 >= 0 and x1 <= size[0] and y1 <= size[1]


def test_a_large_bedroom_gets_a_second_wardrobe():
    assert sum(i["catalog_id"] == "wardrobe" for i in _bedroom_items(5.0, 3.4)) == 2


# --- Portes dégagées ------------------------------------------------------------------------

def _with_door_everywhere_on_the_north_wall():
    """Une porte dont le battant balaie tout le nord de la chambre."""
    rooms = [_room("b", "bedroom", 0, 0, 4.0, 3.2)]
    walls = [_wall("n", 0, 0, 4.0, 0)]
    return rooms, [_door("n", 1.0, 1.4)], walls


def test_an_optional_piece_is_not_placed_in_a_door_swing():
    rooms, openings, walls = _with_door_everywhere_on_the_north_wall()
    zones = door_zones(openings, walls)
    for item in furnish(rooms, openings, walls):
        if item["catalog_id"] in {"nightstand", "wardrobe"}:
            assert not any(_overlap(_footprint(item), z) for z in zones), item


def test_a_night_table_is_left_out_rather_than_put_in_a_door_swing():
    rooms = [_room("b", "bedroom", 0, 0, 4.0, 3.2)]
    walls = [_wall("n", 0, 0, 4.0, 0)]
    door = _door("n", 2.8, 1.2)                  # le battant couvre l'emplacement du chevet de droite
    items = furnish(rooms, [door], walls)
    zones = door_zones([door], walls)
    stands = [i for i in items if i["catalog_id"] == "nightstand"]
    assert len(stands) == 1 and not any(_overlap(_footprint(i), z) for i in stands for z in zones)


def _boxed_in(width, depth, wall_ids):
    """Une pièce dont chaque mur porte assez de portes pour que leurs battants la remplissent presque."""
    room = [_room("r", "bedroom", 0, 0, width, depth)]
    walls, doors = [], []
    for wid, (ax, ay, bx, by) in wall_ids.items():
        walls.append(_wall(wid, ax, ay, bx, by))
        length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        k = 0.0
        while k < length:
            doors.append(_door(wid, k, 1.3))
            k += 1.35
    return room, doors, walls


def test_an_optional_wardrobe_is_omitted_when_every_place_is_in_a_swing():
    room, doors, walls = _boxed_in(4.0, 3.2, {"n": (0, 0, 4.0, 0), "s": (4.0, 3.2, 0, 3.2),
                                              "w": (0, 3.2, 0, 0), "e": (4.0, 0, 4.0, 3.2)})
    assert not any(i["catalog_id"] == "wardrobe" for i in furnish(room, doors, walls))


def test_an_essential_bathtub_is_still_placed_when_every_place_is_in_a_swing():
    room = [_room("b", "bathroom", 0, 0, 3.0, 1.5)]
    walls = [_wall("n", 0, 0, 3.0, 0)]
    doors = [_door("n", 0.0, 1.3), _door("n", 1.4, 1.3)]
    assert any(i["catalog_id"] == "bathtub" for i in furnish(room, doors, walls))


def test_the_bed_size_wins_over_a_door_swing():
    """Un lit double sous le battant vaut mieux qu'un lit simple couché en travers."""
    rooms = [_room("b", "bedroom", 0, 0, 2.8, 4.5)]
    walls = [_wall("n", 0, 0, 2.8, 0), _wall("s", 2.8, 4.5, 0, 4.5)]
    doors = [_door("n", 0.9, 0.9), _door("s", 0.9, 0.9)]          # ni la tête au nord ni au sud n'échappe
    bed = next(i for i in furnish(rooms, doors, walls) if i["catalog_id"].startswith("bed."))
    assert bed["catalog_id"] == "bed.double" and bed["rotation_deg"] in (0, 180)


def test_the_double_bed_turns_to_the_free_end_of_a_room_with_one_door():
    rooms = [_room("b", "bedroom", 0, 0, 2.8, 4.5)]
    walls = [_wall("n", 0, 0, 2.8, 0)]
    door = _door("n", 0.9, 0.9)
    bed = next(i for i in furnish(rooms, [door], walls) if i["catalog_id"].startswith("bed."))
    assert bed["catalog_id"] == "bed.double" and bed["rotation_deg"] == 180
    assert not any(_overlap(_footprint(bed), z) for z in door_zones([door], walls))


def test_the_bed_turns_away_from_a_door_swing_when_it_can():
    rooms = [_room("b", "bedroom", 0, 0, 5.0, 2.6)]
    walls = [_wall("w", 0, 2.6, 0, 0)]              # mur ouest, porte au milieu : la tête ne s'y met pas
    door = _door("w", 0.8, 1.0)
    bed = next(i for i in furnish(rooms, [door], walls) if i["catalog_id"].startswith("bed."))
    assert bed["catalog_id"] == "bed.double"
    assert not any(_overlap(_footprint(bed), z) for z in door_zones([door], walls))


def test_the_bed_is_kept_even_when_a_door_swing_covers_its_spot():
    rooms, openings, walls = _with_door_everywhere_on_the_north_wall()
    assert any(i["catalog_id"].startswith("bed.") for i in furnish(rooms, openings, walls))


def test_without_openings_nothing_changes():
    rooms = [_room("b", "bedroom", 0, 0, 4.0, 3.2)]
    assert furnish(rooms) == furnish(rooms, None, None) == furnish(rooms, [], [])


def test_essential_pieces_survive_a_door_swing():
    """Cuisine et séjour sans plan de travail ni canapé : le pire résultat possible."""
    kitchen = [_room("k", "kitchen", 0, 0, 4.0, 3.0)]
    walls = [_wall("n", 0, 0, 4.0, 0)]
    openings = [_door("n", 0.2, 1.2)]
    kinds = {i["catalog_id"] for i in furnish(kitchen, openings, walls)}
    assert {"counter.kitchen", "stove", "fridge"} <= kinds
    living = [_room("l", "living", 0, 0, 4.4, 6.0)]
    south = [_wall("s", 0, 6.0, 4.4, 6.0)]
    kinds = {i["catalog_id"] for i in furnish(living, [_door("s", 0.3, 1.0)], south)}
    assert kinds & {"sofa.2seat", "sofa.lshape"}


def test_the_sofa_moves_away_from_the_passage_of_a_door():
    living = [_room("l", "living", 0, 0, 6.0, 5.0)]
    south = [_wall("s", 0, 5.0, 6.0, 5.0)]
    door = _door("s", 4.6, 0.9)                        # tout contre l'angle sud-est, où le canapé irait
    sofa = next(i for i in furnish(living, [door], south) if i["catalog_id"].startswith("sofa."))
    zones = door_zones([door], south) + door_passages([door], south)
    assert not any(_overlap(_footprint(sofa), z) for z in zones)


def test_a_garage_door_does_not_remove_the_car():
    garage = [_room("g", "garage", 0, 0, 6.0, 3.0)]
    walls = [_wall("s", 0, 3.0, 6.0, 3.0)]
    assert any(i["catalog_id"] == "car.sedan" for i in furnish(garage, [_door("s", 1.0, 2.4)], walls))


# --- Sanitaires -----------------------------------------------------------------------------

def test_a_bathroom_gets_toilet_sink_and_tub_without_overlaps():
    items = furnish([_room("b", "bathroom", 0, 0, 4.4, 1.5)])
    kinds = sorted(i["catalog_id"] for i in items)
    assert kinds == ["bathtub", "sink.basin", "toilet"]
    boxes = [_footprint(i) for i in items]
    assert not any(_overlap(a, b) for n, a in enumerate(boxes) for b in boxes[n + 1:])


def test_the_toilet_moves_out_of_a_door_swing_but_never_disappears():
    room = [_room("w", "wc", 0, 0, 2.0, 2.0)]
    walls = [_wall("n", 0, 0, 2.0, 0)]
    door = _door("n", 0.0, 0.9)                       # sur l'emplacement habituel du WC
    toilet = next(i for i in furnish(room, [door], walls) if i["catalog_id"] == "toilet")
    assert not any(_overlap(_footprint(toilet), z) for z in door_zones([door], walls))
    tight = [_room("w", "wc", 0, 0, 1.6, 1.6)]
    assert any(i["catalog_id"] == "toilet" for i in furnish(tight, [_door("n", 0.0, 1.2)], [_wall("n", 0, 0, 1.6, 0)]))


# --- Sur de vrais programmes ----------------------------------------------------------------

def _corpus_plan(c):
    rooms = pack_house([dict(r) for r in c["rooms"]], c["width"], c["depth"], grid=0.1, min_side=1.6)
    walls = perimeter_and_internal_walls(rooms, c["width"], c["depth"])
    return rooms, default_openings(walls, c["width"], c["depth"], rooms), walls


@pytest.mark.parametrize("c", CORPUS[::10], ids=lambda c: f"{c['width']}x{c['depth']}")
def test_every_item_stays_inside_its_room_and_no_two_fixed_items_overlap(c):
    rooms, openings, walls = _corpus_plan(c)
    by_id = {r["id"]: r for r in rooms}
    items = furnish(rooms, openings, walls)
    for it in items:
        xs = [p["x"] for p in by_id[it["room_id"]]["polygon"]]
        ys = [p["y"] for p in by_id[it["room_id"]]["polygon"]]
        a = _footprint(it)
        assert a[0] >= min(xs) - 0.05 and a[1] >= min(ys) - 0.05 and a[2] <= max(xs) + 0.05 and a[3] <= max(ys) + 0.05, it
    for kind in ("bedroom", "bathroom", "wc"):
        for room in (r for r in rooms if r["type"] == kind):
            xs = [p["x"] for p in room["polygon"]]
            ys = [p["y"] for p in room["polygon"]]
            if min(max(xs) - min(xs), max(ys) - min(ys)) < 1.3:
                continue          # sous la taille minimale d'un WC : le lavabo obligatoire déborde forcément
            boxes = [(i["catalog_id"], _footprint(i)) for i in items if i["room_id"] == room["id"]]
            for n, (ka, a) in enumerate(boxes):
                for kb, b in boxes[n + 1:]:
                    assert not _overlap(a, b), (kind, ka, kb)


def test_the_catalog_ids_used_by_the_placement_all_exist():
    rooms, openings, walls = _corpus_plan(CORPUS[18])
    assert {i["catalog_id"] for i in furnish(rooms, openings, walls)} <= set(CATALOG)
