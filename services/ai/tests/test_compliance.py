from app.compliance import evaluate


def _rect(x: float, y: float, w: float, h: float) -> list[dict[str, float]]:
    return [{"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]


def _good_plan() -> dict:
    width, depth = 12.0, 10.0
    return {
        "version": "1.0",
        "units": "m",
        "floor": {"level": 0, "height_m": 2.7, "bounds": {"width": width, "depth": depth}},
        "rooms": [
            {"id": "r1", "type": "bedroom", "name": "Chambre", "polygon": _rect(0, 0, 8, 3.5)},
            {"id": "r2", "type": "bathroom", "name": "SDB", "polygon": _rect(8, 0, 4, 3.5)},
            {"id": "r3", "type": "hallway", "name": "Couloir", "polygon": _rect(0, 3.5, 12, 1.2)},
            {"id": "r4", "type": "kitchen", "name": "Cuisine", "polygon": _rect(0, 4.7, 4, 5.3)},
            {"id": "r5", "type": "living", "name": "Séjour", "polygon": _rect(4, 4.7, 8, 5.3)},
        ],
        "walls": [
            {"id": "w_outer_1", "a": {"x": 0, "y": 0}, "b": {"x": 12, "y": 0}},
            {"id": "w_outer_2", "a": {"x": 12, "y": 0}, "b": {"x": 12, "y": 10}},
            {"id": "w_outer_3", "a": {"x": 12, "y": 10}, "b": {"x": 0, "y": 10}},
            {"id": "w_outer_4", "a": {"x": 0, "y": 10}, "b": {"x": 0, "y": 0}},
            {"id": "w_i1", "a": {"x": 6, "y": 0}, "b": {"x": 6, "y": 6}},
            {"id": "w_i2", "a": {"x": 0, "y": 6}, "b": {"x": 6, "y": 6}},
        ],
        "openings": [
            {"id": "o1", "wall_id": "w_outer_1", "type": "door", "width_m": 0.9, "offset_m": 1},
            {"id": "o2", "wall_id": "w_outer_2", "type": "window", "width_m": 1.2, "offset_m": 1},
            {"id": "o3", "wall_id": "w_i1", "type": "door", "width_m": 0.8, "offset_m": 0.5},
        ],
    }


def test_empty_plan_is_low():
    out = evaluate({})
    assert out["score"] < 50
    assert out["grade"] in {"D", "E"}
    assert out["total"] == 20
    by_key = {c["key"]: c for c in out["checks"]}
    assert by_key["living"]["ok"] is False
    assert by_key["window"]["ok"] is False


def test_good_plan_scores_high():
    out = evaluate(_good_plan())
    assert out["score"] >= 80
    assert out["grade"] == "A"
    assert out["passed"] == out["total"]
    assert "indicatif" in out["disclaimer"].lower()


def test_tiny_bedroom_fails_that_check():
    plan = _good_plan()
    plan["rooms"][0]["polygon"] = _rect(6, 4, 2, 2)
    out = evaluate(plan)
    by_key = {c["key"]: c for c in out["checks"]}
    assert by_key["bedrooms"]["ok"] is False
    assert out["score"] < 100


def test_facade_uses_building_envelope():
    plan = {
        "floor": {"height_m": 2.7, "bounds": {"width": 16, "depth": 14}},
        "rooms": [
            {"id": "r1", "type": "living", "name": "Séjour", "polygon": _rect(0, 0, 6, 6)},
            {"id": "r2", "type": "bedroom", "name": "Chambre", "polygon": _rect(6, 0, 4, 6)},
        ],
        "walls": [],
        "openings": [],
    }
    out = evaluate(plan)
    by_key = {c["key"]: c for c in out["checks"]}
    assert by_key["facade"]["ok"] is True


def test_interior_habitable_fails_facade():
    plan = {
        "floor": {"height_m": 2.7, "bounds": {"width": 12, "depth": 12}},
        "rooms": [
            {"id": "r1", "type": "living", "name": "Séjour", "polygon": _rect(0, 0, 12, 4)},
            {"id": "r2", "type": "kitchen", "name": "Cuisine", "polygon": _rect(0, 4, 4, 4)},
            {"id": "r3", "type": "bedroom", "name": "Chambre", "polygon": _rect(4, 4, 4, 4)},
            {"id": "r4", "type": "bathroom", "name": "SDB", "polygon": _rect(8, 4, 4, 4)},
            {"id": "r5", "type": "hallway", "name": "Entrée", "polygon": _rect(0, 8, 12, 4)},
        ],
        "walls": [],
        "openings": [],
    }
    out = evaluate(plan)
    by_key = {c["key"]: c for c in out["checks"]}
    assert by_key["facade"]["ok"] is False
    assert "Chambre" in by_key["facade"]["detail"]


def test_pipeline_returns_compliance():
    from fastapi.testclient import TestClient
    from app.main import app

    res = TestClient(app).post("/v1/pipeline", json={"brief": "Maison 2 chambres"})
    assert res.status_code == 200
    body = res.json()
    assert "compliance" in body
    assert 0 <= body["compliance"]["score"] <= 100
    assert body["compliance"]["total"] == 20
    assert "plan_document" in body
    assert "compliance" not in body["plan_document"]
