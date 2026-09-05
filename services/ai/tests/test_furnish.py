from __future__ import annotations

from app.furnish import CATALOG, furnish
from app.nlu import parse_brief
from app.diffusion import generate
from app.vectorize import vectorize


def _rect(x: float, y: float, w: float, d: float) -> list[dict[str, float]]:
    return [
        {"x": x, "y": y},
        {"x": x + w, "y": y},
        {"x": x + w, "y": y + d},
        {"x": x, "y": y + d},
    ]


def test_bedroom_gets_a_bed():
    items = furnish([
        {"id": "r1", "type": "bedroom", "polygon": _rect(0, 0, 4, 4)},
    ])
    ids = [it["catalog_id"] for it in items]
    assert "bed.double" in ids
    assert all(it["catalog_id"] in CATALOG for it in items)
    bed = next(it for it in items if it["catalog_id"].startswith("bed."))
    assert 0 < bed["position"]["x"] < 4
    assert 0 < bed["position"]["y"] < 4


def test_dining_gets_table_and_chairs():
    items = furnish([
        {"id": "r1", "type": "dining", "polygon": _rect(0, 0, 5, 4)},
    ])
    ids = [it["catalog_id"] for it in items]
    assert ids.count("table.dining") == 1
    assert ids.count("chair.dining") >= 4


def test_living_has_sofa_armchairs_not_dining():
    items = furnish([
        {"id": "r1", "type": "living", "polygon": _rect(0, 0, 6, 5)},
    ])
    ids = [it["catalog_id"] for it in items]
    assert "sofa.2seat" in ids or "sofa.lshape" in ids
    assert ids.count("armchair") >= 2
    assert "table.coffee" in ids
    assert "table.dining" not in ids
    assert "chair.dining" not in ids


def test_living_gets_rug_tv_and_kitchen_fridge():
    items = furnish([
        {"id": "r1", "type": "living", "polygon": _rect(0, 0, 6, 5)},
        {"id": "r2", "type": "kitchen", "polygon": _rect(6, 0, 4, 5)},
    ])
    ids = [it["catalog_id"] for it in items]
    assert "rug.rect" in ids
    assert "tv.console" in ids
    assert "plant.pot" in ids
    assert "fridge" in ids
    assert all(it["catalog_id"] in CATALOG for it in items)


def test_living_skips_dining_when_kitchen_exists():
    items = furnish([
        {"id": "r1", "type": "living", "polygon": _rect(0, 0, 6, 5)},
        {"id": "r2", "type": "kitchen", "polygon": _rect(6, 0, 4, 5)},
    ])
    living = [it for it in items if it["room_id"] == "r1"]
    assert "table.dining" not in [it["catalog_id"] for it in living]


def test_living_skips_dining_set_when_dining_room_exists():
    items = furnish([
        {"id": "r1", "type": "living", "polygon": _rect(0, 0, 6, 5)},
        {"id": "r2", "type": "dining", "polygon": _rect(6, 0, 4, 4)},
    ])
    living = [it for it in items if it["room_id"] == "r1"]
    living_ids = [it["catalog_id"] for it in living]
    assert "sofa.2seat" in living_ids or "sofa.lshape" in living_ids
    assert "table.dining" not in living_ids


def test_kitchen_has_counters_not_dining_or_tub():
    items = furnish([
        {"id": "r1", "type": "kitchen", "polygon": _rect(0, 0, 4.5, 5)},
    ])
    ids = [it["catalog_id"] for it in items]
    assert "counter.kitchen" in ids
    assert "fridge" in ids
    assert "table.dining" not in ids
    assert "chair.dining" not in ids
    assert "bathtub" not in ids


def test_bathroom_and_garage_get_fixtures():
    items = furnish([
        {"id": "r1", "type": "bathroom", "polygon": _rect(0, 0, 3, 3)},
        {"id": "r2", "type": "garage", "polygon": _rect(3, 0, 5, 5)},
    ])
    ids = [it["catalog_id"] for it in items]
    assert "toilet" in ids
    assert "bathtub" in ids
    assert "car.sedan" in ids


def test_tiny_room_gets_no_furniture():
    items = furnish([
        {"id": "r1", "type": "bedroom", "polygon": _rect(0, 0, 1.0, 1.0)},
    ])
    assert items == []


def test_vectorize_embeds_catalog_instances():
    spec = parse_brief("Maison 2 chambres", {"total_area_m2": 100})
    gen = generate(spec)
    plan = vectorize({"layout": gen["layout"], "building_spec": spec})["plan_document"]
    furniture = plan["furniture"]
    assert furniture
    ids = {it["catalog_id"] for it in furniture}
    assert "bed.double" in ids or "bed.single" in ids
    room_ids = {r["id"] for r in plan["rooms"]}
    for it in furniture:
        assert it["room_id"] in room_ids
        assert "position" in it and "x" in it["position"]
