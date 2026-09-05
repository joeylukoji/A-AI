from app.layout_opt import optimize_rooms


def test_optimizer_makes_orthogonal_non_overlapping():
    rooms = [
        {"id": "a", "type": "living", "name": "Séjour", "area_m2": 20, "polygon": [{"x": 0, "y": 0}, {"x": 6.3, "y": 0.4}, {"x": 5.8, "y": 5.2}, {"x": 0.2, "y": 4.7}]},
        {"id": "b", "type": "kitchen", "name": "Cuisine", "area_m2": 10, "polygon": [{"x": 4, "y": 0}, {"x": 8, "y": 0.3}, {"x": 7.5, "y": 3.4}, {"x": 4.2, "y": 3.1}]},
        {"id": "c", "type": "bedroom", "name": "Chambre", "area_m2": 12, "polygon": [{"x": 1, "y": 3}, {"x": 5.5, "y": 3.2}, {"x": 5, "y": 8}, {"x": 0.8, "y": 7.6}]},
    ]
    spec = {"rooms": [
        {"type": "living", "area_m2": 24, "count": 1},
        {"type": "kitchen", "area_m2": 10, "count": 1},
        {"type": "bedroom", "area_m2": 12, "count": 1},
    ]}
    out = optimize_rooms(rooms, 12, 10, spec)
    assert len(out) >= 3
    for room in out:
        poly = room["polygon"]
        assert len(poly) == 4
        xs = {p["x"] for p in poly}
        ys = {p["y"] for p in poly}
        assert len(xs) == 2 and len(ys) == 2
        for p in poly:
            assert 0 <= p["x"] <= 12 + 1e-6
            assert 0 <= p["y"] <= 10 + 1e-6

    def box(room):
        xs = [p["x"] for p in room["polygon"]]
        ys = [p["y"] for p in room["polygon"]]
        return min(xs), min(ys), max(xs), max(ys)

    for i, a in enumerate(out):
        ax0, ay0, ax1, ay1 = box(a)
        for b in out[i + 1 :]:
            bx0, by0, bx1, by1 = box(b)
            ix = max(0, min(ax1, bx1) - max(ax0, bx0))
            iy = max(0, min(ay1, by1) - max(ay0, by0))
            assert ix * iy < 0.26


def test_packed_rooms_share_edges():
    rooms = [
        {"id": "a", "type": "living", "name": "Séjour", "area_m2": 24, "polygon": [{"x": 1, "y": 1}]},
        {"id": "b", "type": "kitchen", "name": "Cuisine", "area_m2": 10, "polygon": [{"x": 8, "y": 1}]},
        {"id": "c", "type": "bedroom", "name": "Chambre", "area_m2": 12, "polygon": [{"x": 1, "y": 8}]},
        {"id": "d", "type": "bathroom", "name": "SDB", "area_m2": 6, "polygon": [{"x": 8, "y": 8}]},
        {"id": "e", "type": "hallway", "name": "Entrée", "area_m2": 8, "polygon": [{"x": 5, "y": 5}]},
    ]
    out = optimize_rooms(rooms, 12, 10, {"rooms": [{"type": r["type"], "area_m2": r["area_m2"], "count": 1} for r in rooms]}, grid=0.1)
    from app.compliance import evaluate

    def box(room):
        xs = [p["x"] for p in room["polygon"]]
        ys = [p["y"] for p in room["polygon"]]
        return min(xs), min(ys), max(xs), max(ys)

    seams = 0
    for i, a in enumerate(out):
        ax0, ay0, ax1, ay1 = box(a)
        for b in out[i + 1 :]:
            bx0, by0, bx1, by1 = box(b)
            x_touch = abs(ax1 - bx0) < 1e-6 or abs(bx1 - ax0) < 1e-6
            y_touch = abs(ay1 - by0) < 1e-6 or abs(by1 - ay0) < 1e-6
            y_ov = min(ay1, by1) - max(ay0, by0)
            x_ov = min(ax1, bx1) - max(ax0, bx0)
            if (x_touch and y_ov > 0.5) or (y_touch and x_ov > 0.5):
                seams += 1
    assert seams >= 4
    report = evaluate({
        "floor": {"height_m": 2.7, "bounds": {"width": 12, "depth": 10}},
        "rooms": out,
        "walls": [{"id": "w_outer_1", "a": {"x": 0, "y": 0}, "b": {"x": 12, "y": 0}}],
        "openings": [{"type": "door", "wall_id": "w_outer_1", "width_m": 0.9}, {"type": "window", "width_m": 1.2, "wall_id": "w_outer_1"}],
    })
    by_key = {c["key"]: c for c in report["checks"]}
    assert by_key["access"]["ok"] is True, by_key["access"]
    assert by_key["facade"]["ok"] is True, by_key["facade"]


def test_house_pack_sweet_home_topology():
    from app.layout_opt import pack_house

    rooms = [
        {"id": "r1", "type": "living", "name": "Séjour", "area_m2": 28},
        {"id": "r2", "type": "kitchen", "name": "Cuisine", "area_m2": 12},
        {"id": "r3", "type": "bedroom", "name": "Chambre 1", "area_m2": 12},
        {"id": "r4", "type": "bedroom", "name": "Chambre 2", "area_m2": 12},
        {"id": "r5", "type": "bedroom", "name": "Chambre 3", "area_m2": 16},
        {"id": "r6", "type": "bathroom", "name": "SDB", "area_m2": 5},
        {"id": "r7", "type": "bathroom", "name": "SDB 2", "area_m2": 4},
        {"id": "r8", "type": "garage", "name": "Garage", "area_m2": 18},
    ]
    out = pack_house(rooms, 14, 11, grid=0.1, min_side=1.6)
    assert len(out) == 9
    assert any(r["type"] == "hallway" for r in out)

    def cy(room):
        ys = [p["y"] for p in room["polygon"]]
        return (min(ys) + max(ys)) / 2

    def cx(room):
        xs = [p["x"] for p in room["polygon"]]
        return (min(xs) + max(xs)) / 2

    living = next(r for r in out if r["type"] == "living")
    garage = next(r for r in out if r["type"] == "garage")
    kitchen = next(r for r in out if r["type"] == "kitchen")
    beds = [r for r in out if r["type"] == "bedroom"]
    assert cy(living) > 4.0
    assert cx(garage) > 8.0
    assert cx(kitchen) < 5.5
    assert all(min(p["y"] for p in b["polygon"]) < 5.5 for b in beds)


def test_pack_separates_wc_from_kitchen_and_bedrooms_from_living():
    from app.layout_opt import pack_house, sanitary_violations

    rooms = [
        {"id": "r1", "type": "living", "name": "Séjour", "area_m2": 28},
        {"id": "r2", "type": "kitchen", "name": "Cuisine", "area_m2": 12},
        {"id": "r3", "type": "bedroom", "name": "Chambre 1", "area_m2": 12},
        {"id": "r4", "type": "bedroom", "name": "Chambre 2", "area_m2": 12},
        {"id": "r5", "type": "bathroom", "name": "SDB", "area_m2": 5},
        {"id": "r6", "type": "wc", "name": "WC", "area_m2": 3.5},
        {"id": "r7", "type": "hallway", "name": "Couloir", "area_m2": 8},
    ]
    out = pack_house(rooms, 12, 10, grid=0.1, min_side=1.6)
    assert sanitary_violations(out) == []
    halls = [r for r in out if r["type"] == "hallway"]
    assert halls
    beds = [r for r in out if r["type"] == "bedroom"]
    living = next(r for r in out if r["type"] == "living")
    kitchen = next(r for r in out if r["type"] == "kitchen")
    wc = next(r for r in out if r["type"] == "wc")
    from app.layout_opt import share_edge

    assert not share_edge(kitchen, wc)
    for bed in beds:
        assert not share_edge(bed, living)
        assert any(share_edge(bed, h) for h in halls)
    assert any(share_edge(wc, h) for h in halls)
    for bed in beds:
        assert not share_edge(bed, wc)


def test_internal_doors_follow_sanitary_pairs():
    from app.diffusion import default_openings, expand_rooms, pack_rooms, perimeter_and_internal_walls
    from app.nlu import parse_brief

    spec = parse_brief("Maison 2 chambres avec toilettes", {})
    rooms = pack_rooms(expand_rooms(spec.get("rooms") or []), 12, 10)
    walls = perimeter_and_internal_walls(rooms, 12, 10)
    openings = default_openings(walls, 12, 10, rooms)
    by_id = {w["id"]: w for w in walls}
    inner = [o for o in openings if o["type"] == "door" and not str(o.get("wall_id", "")).startswith("w_outer")]
    assert inner
    from app.diffusion import _rooms_on_wall

    wc_from_hall = False

    for op in inner:
        pair = _rooms_on_wall(by_id[op["wall_id"]], rooms)
        types = {str(r.get("type")) for r in pair}
        assert types != {"kitchen", "wc"}
        assert types != {"bedroom", "living"}
        assert types != {"bedroom", "bedroom"}
        assert types != {"bedroom", "wc"}
        assert types != {"kitchen", "bathroom"}
        if types == {"wc", "hallway"}:
            wc_from_hall = True
    assert wc_from_hall


def test_pack_injects_hallway_when_missing():
    from app.layout_opt import pack_house

    rooms = [
        {"id": "r1", "type": "living", "area_m2": 24},
        {"id": "r2", "type": "kitchen", "area_m2": 10},
        {"id": "r3", "type": "bedroom", "area_m2": 12},
        {"id": "r4", "type": "bathroom", "area_m2": 5},
    ]
    out = pack_house(rooms, 12, 10, grid=0.1, min_side=1.6)
    assert any(r["type"] == "hallway" for r in out)


def test_place_habitables_swaps_interior_bedroom():
    from app.layout_opt import place_habitables_on_facade

    def rect(x, y, w, h):
        return [{"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]

    rooms = [
        {"id": "r1", "type": "living", "name": "Séjour", "area_m2": 48, "polygon": rect(0, 0, 12, 4)},
        {"id": "r2", "type": "kitchen", "name": "Cuisine", "area_m2": 16, "polygon": rect(0, 4, 4, 4)},
        {"id": "r3", "type": "bedroom", "name": "Chambre", "area_m2": 16, "polygon": rect(4, 4, 4, 4)},
        {"id": "r4", "type": "bathroom", "name": "SDB", "area_m2": 16, "polygon": rect(8, 4, 4, 4)},
        {"id": "r5", "type": "hallway", "name": "Entrée", "area_m2": 48, "polygon": rect(0, 8, 12, 4)},
    ]
    out = place_habitables_on_facade(rooms, 12, 12)
    bed = next(r for r in out if r["type"] == "bedroom")
    xs = [p["x"] for p in bed["polygon"]]
    ys = [p["y"] for p in bed["polygon"]]
    assert min(xs) <= 0.15 or min(ys) <= 0.15 or max(xs) >= 11.85 or max(ys) >= 11.85


# --- Invariants du pavage : un plan faux est le pire bug produit -------------


def _bbox(room):
    xs = [p["x"] for p in room["polygon"]]
    ys = [p["y"] for p in room["polygon"]]
    return min(xs), min(ys), max(xs), max(ys)


def _assert_sound_tiling(out, width, depth, *, min_coverage=0.90):
    """Rectangles jointifs : dans l'emprise, sans recouvrement, sans trou."""
    import itertools

    covered = 0.0
    for room in out:
        x0, y0, x1, y1 = _bbox(room)
        assert x1 - x0 > 0 and y1 - y0 > 0, f"pièce d'aire nulle: {room}"
        assert -1e-6 <= x0 and x1 <= width + 1e-6, f"hors emprise en x: {room}"
        assert -1e-6 <= y0 and y1 <= depth + 1e-6, f"hors emprise en y: {room}"
        covered += (x1 - x0) * (y1 - y0)
    for a, b in itertools.combinations(out, 2):
        ax0, ay0, ax1, ay1 = _bbox(a)
        bx0, by0, bx1, by1 = _bbox(b)
        ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        iy = max(0.0, min(ay1, by1) - max(ay0, by0))
        assert ix * iy <= 0.02, f"{a['id']} recouvre {b['id']} sur {ix * iy:.2f} m²"
    assert covered / (width * depth) >= min_coverage


def test_splits_never_leave_the_band():
    """`_splits` bornait mal ses positions : les dernières sortaient de la bande."""
    from app.layout_opt import _splits

    for span in (1.0, 1.5, 3.0, 8.0, 12.0):
        for n in range(1, 9):
            pos = _splits(span, [8.0] * n, [2.6] * n, 0.5)
            assert len(pos) == n + 1
            assert pos[0] == 0.0
            assert abs(pos[-1] - span) < 1e-9
            for i in range(1, len(pos)):
                assert pos[i] >= pos[i - 1] - 1e-9, (span, n, pos)
                assert pos[i] <= span + 1e-9, (span, n, pos)


def test_splits_respect_minimum_widths_when_they_fit():
    """La renormalisation finale écrasait les minimums (couloirs de 0,4 m)."""
    from app.layout_opt import _splits

    pos = _splits(12.0, [30.0, 4.0, 4.0], [2.6, 1.4, 1.4], 0.1)
    sizes = [round(pos[i + 1] - pos[i], 3) for i in range(3)]
    assert sizes[0] >= 2.6
    assert sizes[1] >= 1.4
    assert sizes[2] >= 1.4


def test_pack_keeps_every_room_of_the_program():
    """`_first` ne gardait qu'une cuisine / un séjour / un garage : les autres
    pièces disparaissaient du plan sans le moindre signal."""
    from app.layout_opt import pack_house

    rooms = [
        {"id": "k1", "type": "kitchen", "area_m2": 12},
        {"id": "k2", "type": "kitchen", "area_m2": 9},
        {"id": "l1", "type": "living", "area_m2": 24},
        {"id": "l2", "type": "living", "area_m2": 14},
        {"id": "g1", "type": "garage", "area_m2": 18},
        {"id": "g2", "type": "garage", "area_m2": 16},
        {"id": "b1", "type": "bedroom", "area_m2": 12},
    ]
    out = pack_house(rooms, 16, 12, grid=0.1, min_side=1.6)
    for room in rooms:
        assert any(r.get("id") == room["id"] for r in out), f"{room['id']} perdue"
    _assert_sound_tiling(out, 16, 12)


def test_pack_keeps_hallways_and_service_rooms_without_night_zone():
    """Sans zone nuit, les couloirs n'étaient rattachés à aucune rangée."""
    from app.layout_opt import pack_house

    rooms = [
        {"id": "d1", "type": "dining", "area_m2": 15},
        {"id": "h1", "type": "hallway", "area_m2": 5},
        {"id": "h2", "type": "hallway", "area_m2": 4},
        {"id": "s1", "type": "storage", "area_m2": 6},
        {"id": "o1", "type": "other", "area_m2": 8},
    ]
    out = pack_house(rooms, 10, 12, grid=0.1, min_side=1.6)
    assert {r["id"] for r in rooms} <= {r.get("id") for r in out}
    _assert_sound_tiling(out, 10, 12)


def test_pack_without_day_room_leaves_no_hole():
    """Un programme sans séjour/cuisine laissait ~30 % de l'emprise vide."""
    from app.layout_opt import pack_house

    rooms = [
        {"id": "o1", "type": "office", "area_m2": 9},
        {"id": "o2", "type": "office", "area_m2": 9},
        {"id": "b1", "type": "bedroom", "area_m2": 15},
        {"id": "h1", "type": "hallway", "area_m2": 8},
    ]
    out = pack_house(rooms, 8, 12.2, grid=0.1, min_side=1.6)
    _assert_sound_tiling(out, 8, 12.2, min_coverage=0.95)


def test_pack_stays_sound_on_cramped_and_odd_programs():
    """Balayage : bandes plus étroites que le pas de grille, garage sur emprise
    minimale, pièces plus nombreuses que la largeur ne le permet."""
    from app.layout_opt import pack_house

    from app.layout_opt import _snap

    types = ["living", "kitchen", "bedroom", "bathroom", "wc", "hallway",
             "garage", "office", "dining", "laundry", "storage", "other"]
    for n in (1, 2, 3, 5, 8):
        for size in (3.2, 4.3, 6.0, 9.5, 14.0):
            for grid in (0.1, 0.5):
                rooms = [
                    {"id": f"r{i}", "type": types[(i * 5 + n) % len(types)], "area_m2": 4 + 3 * i}
                    for i in range(n)
                ]
                out = pack_house(rooms, size, size * 1.3, grid=grid, min_side=1.6)
                assert {r["id"] for r in rooms} <= {r.get("id") for r in out}
                # `pack_house` cale l'emprise sur la grille avant de paver.
                w = _snap(max(size, 3.2), grid)
                d = _snap(max(size * 1.3, 3.2), grid)
                _assert_sound_tiling(out, w, d, min_coverage=0.80)


# --- Accès : aucune pièce murée, entrée devant une pièce d'accueil -----------


def _plan(prog, width, depth):
    from app.diffusion import (
        default_openings, expand_rooms, pack_rooms, perimeter_and_internal_walls,
    )

    rooms = pack_rooms(expand_rooms(prog), width, depth)
    walls = perimeter_and_internal_walls(rooms, width, depth)
    return rooms, walls, default_openings(walls, width, depth, rooms)


def _sealed_rooms(rooms, walls, openings):
    from app.diffusion import _served_rooms

    by_id = {str(w["id"]): w for w in walls}
    served = set()
    for op in openings:
        if op["type"] != "door":
            continue
        for room in _served_rooms(by_id[str(op["wall_id"])], op, rooms):
            served.add(id(room))
    return [r for r in rooms if id(r) not in served]


def test_every_room_gets_a_door():
    """La liste blanche `_DOOR_PAIRS` murait les pièces dont aucun voisinage
    n'était « souhaitable » (bureau entre cuisine et salle à manger, WC qui ne
    touche pas le couloir) : une pièce inaccessible, donc un plan faux."""
    programs = [
        [{"id": "a", "type": "office", "area_m2": 12}, {"id": "b", "type": "kitchen", "area_m2": 12},
         {"id": "c", "type": "dining", "area_m2": 14}],
        [{"id": "a", "type": "dining", "area_m2": 15}, {"id": "b", "type": "wc", "area_m2": 3}],
        [{"id": "a", "type": "kitchen", "area_m2": 10}, {"id": "b", "type": "kitchen", "area_m2": 10},
         {"id": "c", "type": "bathroom", "area_m2": 6}],
        [{"id": "a", "type": "living", "area_m2": 24}, {"id": "b", "type": "kitchen", "area_m2": 10},
         {"id": "c", "type": "bedroom", "area_m2": 12}, {"id": "d", "type": "bedroom", "area_m2": 12},
         {"id": "e", "type": "wc", "area_m2": 3}, {"id": "f", "type": "bathroom", "area_m2": 5}],
    ]
    for prog in programs:
        rooms, walls, openings = _plan(prog, 12, 10)
        sealed = _sealed_rooms(rooms, walls, openings)
        assert not sealed, [(r.get("id"), r.get("type")) for r in sealed]


def test_openings_stay_within_their_wall():
    from app.diffusion import _wall_len

    prog = [
        {"id": "a", "type": "living", "area_m2": 26}, {"id": "b", "type": "kitchen", "area_m2": 11},
        {"id": "c", "type": "bedroom", "area_m2": 12, "count": 2},
        {"id": "d", "type": "wc", "area_m2": 3}, {"id": "e", "type": "garage", "area_m2": 18},
    ]
    for width, depth in ((12, 10), (8, 13), (16, 7.5)):
        rooms, walls, openings = _plan(prog, width, depth)
        by_id = {str(w["id"]): w for w in walls}
        for op in openings:
            wall = by_id[str(op["wall_id"])]
            length = _wall_len(wall)
            assert op["offset_m"] >= -1e-9
            assert op["offset_m"] + op["width_m"] <= length + 1e-6, (op, length)


def test_entrance_door_opens_on_a_reception_room():
    """L'entrée était posée à 42 % de la façade sud, quelle que soit la pièce
    qui se trouvait derrière : elle pouvait déboucher dans la salle de bain."""
    from app.diffusion import _served_rooms

    prog = [
        {"id": "a", "type": "kitchen", "area_m2": 10},
        {"id": "b", "type": "bathroom", "area_m2": 6},
        {"id": "c", "type": "garage", "area_m2": 18},
    ]
    rooms, walls, openings = _plan(prog, 8, 7.3)
    south = next(w for w in walls if w["id"] == "w_outer_3")
    entry = next(o for o in openings if o["wall_id"] == "w_outer_3" and o["type"] == "door")
    types = {str(r.get("type")) for r in _served_rooms(south, entry, rooms)}
    assert types & {"hallway", "living", "dining", "kitchen", "office", "garage"}, types


def test_dining_room_never_shares_a_wall_with_the_wc():
    """La bande WC se colle au bout est de la rangée jour : une salle à manger
    à cet endroit produisait le mur commun WC / salle à manger interdit."""
    from app.layout_opt import pack_house, sanitary_violations

    programs = [
        [{"id": "a", "type": "living", "area_m2": 24}, {"id": "b", "type": "kitchen", "area_m2": 10},
         {"id": "c", "type": "dining", "area_m2": 12}, {"id": "d", "type": "wc", "area_m2": 3}],
        [{"id": "a", "type": "kitchen", "area_m2": 12}, {"id": "b", "type": "dining", "area_m2": 14},
         {"id": "c", "type": "wc", "area_m2": 3}, {"id": "d", "type": "bathroom", "area_m2": 5}],
        [{"id": "a", "type": "living", "area_m2": 26}, {"id": "b", "type": "kitchen", "area_m2": 11},
         {"id": "c", "type": "dining", "area_m2": 12}, {"id": "d", "type": "wc", "area_m2": 3},
         {"id": "e", "type": "bedroom", "area_m2": 12}, {"id": "f", "type": "bathroom", "area_m2": 5}],
    ]
    for prog in programs:
        out = pack_house(prog, 12, 10, grid=0.1, min_side=1.6)
        assert "wc_kitchen" not in sanitary_violations(out), [
            (r["type"], r["polygon"][0], r["polygon"][2]) for r in out
        ]


def test_realistic_briefs_produce_compliant_plans():
    """Garde-fou de bout en bout : brief -> programme -> pavage -> conformité."""
    from app.compliance import evaluate
    from app.diffusion import (
        default_openings, expand_rooms, pack_rooms, perimeter_and_internal_walls,
    )
    from app.layout_opt import sanitary_violations
    from app.nlu import parse_brief

    briefs = [
        "Maison 3 chambres avec garage et toilettes",
        "Maison 2 chambres",
        "Appartement T3 avec WC separe",
        "Maison avec salle a manger et toilettes",
        "Maison 4 chambres 2 salles de bain garage bureau",
        "Maison 1 chambre avec buanderie",
    ]
    for brief in briefs:
        spec = parse_brief(brief, {})
        rooms = pack_rooms(expand_rooms(spec.get("rooms") or []), 12, 10)
        walls = perimeter_and_internal_walls(rooms, 12, 10)
        openings = default_openings(walls, 12, 10, rooms)
        assert sanitary_violations(rooms) == [], brief
        report = evaluate({
            "floor": {"height_m": 2.7, "bounds": {"width": 12, "depth": 10}},
            "rooms": rooms, "walls": walls, "openings": openings,
        })
        failed = [c["key"] for c in report["checks"] if not c["ok"]]
        # `bedrooms` peut échouer sur une emprise 12x10 très chargée.
        assert not (set(failed) - {"bedrooms"}), (brief, failed)
        _assert_sound_tiling(rooms, 12, 10)
