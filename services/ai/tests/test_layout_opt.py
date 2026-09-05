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
    assert len(out) == 3
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
    assert len(out) == 8

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
