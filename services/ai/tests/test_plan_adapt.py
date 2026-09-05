from app.plan_adapt import adapt, default_rules


def _rect(x, y, w, h):
    return [{"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]


def _plan():
    return {
        "version": "1.0",
        "units": "m",
        "floor": {"level": 0, "height_m": 2.4, "bounds": {"width": 12, "depth": 10}},
        "rooms": [
            {"id": "r1", "type": "living", "name": "Séjour", "polygon": _rect(0, 0, 5, 4)},
            {"id": "r2", "type": "kitchen", "name": "Cuisine", "polygon": _rect(5, 0, 3, 3)},
            {"id": "r3", "type": "bedroom", "name": "Chambre", "polygon": _rect(5, 3, 2, 2)},
            {"id": "r4", "type": "bathroom", "name": "SDB", "polygon": _rect(0, 4, 3, 3)},
            {"id": "r5", "type": "hallway", "name": "Entrée", "polygon": _rect(3, 4, 2, 3)},
        ],
        "walls": [],
        "openings": [],
    }


def test_adapt_fits_parcel_and_snaps():
    out = adapt({
        "plan_document": _plan(),
        "parcel": {"width_m": 14, "depth_m": 11, "setback_m": 1},
        "rules": {"grid_m": 0.1, "height_m": 2.7},
    })
    doc = out["plan_document"]
    assert doc["floor"]["bounds"]["width"] == 12.0
    assert doc["floor"]["bounds"]["depth"] == 9.0
    assert doc["floor"]["height_m"] == 2.7
    assert out["parcel"]["buildable_width_m"] == 12.0
    assert len(doc["rooms"]) == 5
    for row in out["dimensions"]:
        assert row["width_m"] > 0
        assert abs(row["width_m"] * 10 - round(row["width_m"] * 10)) < 1e-6
    assert out["compliance"]["score"] >= out["compliance_before"]["score"]
    doors = [o for o in doc["openings"] if o["type"] == "door"]
    assert doors
    assert all(o["width_m"] >= 0.8 for o in doors)
    by_key = {c["key"]: c for c in out["compliance"]["checks"]}
    assert by_key["facade"]["ok"] is True, by_key["facade"]


def test_adapt_tiny_bedroom_grows():
    out = adapt({"plan_document": _plan(), "parcel": {"width_m": 12, "depth_m": 10}})
    bed = next(r for r in out["dimensions"] if r["type"] == "bedroom")
    assert bed["area_m2"] >= 9


def test_default_rules_are_complete():
    rules = default_rules()
    assert rules["door_entry_m"] == 0.9
    assert rules["min_living_m2"] == 9
