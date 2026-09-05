from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import PipelineRequest, app, api_pipeline  # noqa: E402
from app.nlu import parse_brief  # noqa: E402
from app.diffusion import generate  # noqa: E402
from app.vectorize import vectorize  # noqa: E402


client = TestClient(app)


def test_healthz():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_pipeline_accepts_null_constraints():
    res = client.post("/v1/pipeline", json={"brief": "Maison 3 chambres avec garage", "constraints": None})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "plan_document" in body
    assert body["plan_document"]["version"] == "1.0"
    assert len(body["plan_document"]["rooms"]) >= 1
    assert len(body["plan_document"]["walls"]) >= 4


def test_pipeline_without_constraints_key():
    res = client.post("/v1/pipeline", json={"brief": "Appartement 2 chambres cuisine ouverte"})
    assert res.status_code == 200, res.text


def test_nlu_filters_invented_rooms():
    from app.nlu import _filter_invented_rooms

    rooms = [
        {"type": "living", "count": 1},
        {"type": "kitchen", "count": 1},
        {"type": "garage", "count": 1},
        {"type": "office", "count": 1},
    ]
    out = _filter_invented_rooms("Maison 3 chambres", rooms)
    types = {r["type"] for r in out}
    assert "garage" not in types and "office" not in types
    assert {"living", "kitchen"} <= types


def test_nlu_extracts_bedrooms():
    spec = parse_brief("Maison 4 chambres avec garage et cuisine ouverte", {})
    types = {r["type"] for r in spec["rooms"]}
    assert "bedroom" in types
    assert "garage" in types
    assert "kitchen" in types
    bedroom = next(r for r in spec["rooms"] if r["type"] == "bedroom")
    assert bedroom.get("count") == 4


def test_housediff_room_program():
    from app.housediff import rooms_from_spec

    spec = parse_brief("Maison 2 chambres", {})
    types = rooms_from_spec(spec)
    assert types[0] == "living"
    assert "kitchen" in types
    assert types.count("bedroom") == 2


def test_nlu_default_house_has_core_rooms():
    spec = parse_brief("Maison contemporaine", {})
    types = {r["type"] for r in spec["rooms"]}
    assert {"living", "kitchen", "bedroom", "bathroom", "hallway"} <= types
    bedroom = next(r for r in spec["rooms"] if r["type"] == "bedroom")
    assert bedroom.get("count") == 2


def test_nlu_t3_is_two_bedrooms():
    spec = parse_brief("Appartement T3", {})
    bedroom = next(r for r in spec["rooms"] if r["type"] == "bedroom")
    assert bedroom.get("count") == 2


def test_nlu_one_bedroom_has_hallway():
    spec = parse_brief("Maison 1 chambre", {})
    types = {r["type"] for r in spec["rooms"]}
    assert "hallway" in types
    assert "bedroom" in types


def test_nlu_does_not_invent_garage():
    spec = parse_brief("Maison 2 chambres", {})
    assert all(r["type"] != "garage" for r in spec["rooms"])


def test_nlu_wc_is_separate_from_bathroom():
    spec = parse_brief("Maison 2 chambres avec wc", {})
    types = [r["type"] for r in spec["rooms"]]
    assert "wc" in types
    assert types.count("bathroom") >= 1


def test_nlu_toilettes_adds_wc_room():
    spec = parse_brief("Maison 2 chambres avec toilettes", {})
    types = [r["type"] for r in spec["rooms"]]
    assert "wc" in types
    wc = next(r for r in spec["rooms"] if r["type"] == "wc")
    assert float(wc.get("area_m2") or 0) >= 3.0


def test_generated_rooms_are_named():
    spec = parse_brief("Maison contemporaine", {})
    rooms = generate(spec)["layout"]["rooms"]
    names = {r["name"] for r in rooms}
    types = {r["type"] for r in rooms}
    assert "Cuisine" in names
    assert "Séjour" in names
    assert {"kitchen", "living", "bedroom", "bathroom"} <= types


def test_diffusion_and_vectorize_orthogonal():
    spec = parse_brief("Maison 2 chambres", {"total_area_m2": 100})
    gen = generate(spec)
    plan = vectorize({"layout": gen["layout"], "building_spec": spec})["plan_document"]
    for wall in plan["walls"]:
        ax, ay = wall["a"]["x"], wall["a"]["y"]
        bx, by = wall["b"]["x"], wall["b"]["y"]
        assert abs(ax - bx) < 1e-6 or abs(ay - by) < 1e-6
    assert plan["openings"]
    wall_ids = {w["id"] for w in plan["walls"]}
    for op in plan["openings"]:
        assert op["wall_id"] in wall_ids
        assert op["type"] in {"door", "window"}
        assert op["width_m"] > 0
    w = plan["floor"]["bounds"]["width"]
    d = plan["floor"]["bounds"]["depth"]
    assert len(plan["rooms"]) >= 5
    furniture = plan["furniture"]
    assert furniture
    assert any(it["catalog_id"].startswith("bed.") for it in furniture)
    for room in plan["rooms"]:
        assert len(room["polygon"]) >= 4
        for p in room["polygon"]:
            assert 0 <= p["x"] <= w + 1e-6
            assert 0 <= p["y"] <= d + 1e-6


def test_api_pipeline_helper():
    out = api_pipeline(PipelineRequest(brief="Villa 5 chambres avec bureau", constraints={}))
    assert "building_spec" in out
    assert out["plan_document"]["floor"]["height_m"] > 0
    assert 0 <= out["compliance"]["score"] <= 100


@pytest.mark.parametrize(
    "brief",
    [
        "Maison 4 chambres avec garage",
        "studio",
        "Bureau avec salle de bain",
    ],
)
def test_pipeline_briefs(brief: str):
    res = client.post("/v1/pipeline", json={"brief": brief})
    assert res.status_code == 200


def test_edit_requires_instruction():
    res = client.post("/v1/edit", json={"instruction": "  ", "brief": "Maison"})
    assert res.status_code == 400


def test_nlu_clamps_absurd_dimensions():
    """Une largeur/surface hors bornes venue de `constraints` ne doit pas se
    propager telle quelle : les boucles de rendu vectoriel itèrent en mètres,
    une valeur type 1e9 bloquerait un worker pendant des heures (DoS)."""
    spec = parse_brief("Maison 2 chambres", {"max_width_m": 1e9, "max_depth_m": 1e9})
    assert spec["constraints"]["max_width_m"] <= 200.0
    assert spec["constraints"]["max_depth_m"] <= 200.0


def test_diffusion_generate_clamps_absurd_dimensions():
    spec = parse_brief("Maison 2 chambres", {})
    spec["constraints"]["max_width_m"] = 1e9
    spec["constraints"]["max_depth_m"] = 1e9
    out = generate(spec, image=False)
    assert out["layout"]["width"] <= 200.0
    assert out["layout"]["depth"] <= 200.0


def test_plan_adapt_clamps_absurd_parcel(monkeypatch):
    from app.plan_adapt import adapt

    spec = parse_brief("Maison 2 chambres", {})
    gen = generate(spec)
    plan = vectorize({"layout": gen["layout"], "building_spec": spec})["plan_document"]
    out = adapt({
        "plan_document": plan,
        "parcel": {"width_m": 1e9, "depth_m": 1e9},
    })
    assert out["parcel"]["buildable_width_m"] <= 200.0
    assert out["parcel"]["buildable_depth_m"] <= 200.0


def test_adapt_endpoint_rejects_plan_without_rooms():
    """`plan_adapt.adapt` lève `ValueError` pour un plan sans pièces : l'API doit
    renvoyer un 422 propre plutôt qu'un 500 générique."""
    res = client.post("/v1/adapt", json={"plan_document": {"rooms": []}})
    assert res.status_code == 422, res.text


def test_pipeline_rejects_oversized_brief():
    huge_brief = "Maison " + "x" * 5000
    res = client.post("/v1/pipeline", json={"brief": huge_brief})
    assert res.status_code == 422


def test_edit_keeps_plan_without_together_key(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    res = client.post("/v1/edit", json={
        "instruction": "ajoute un îlot",
        "brief": "Maison 2 chambres",
        "image_png_b64": "ZmFrZQ==",
        "plan_document": {"rooms": []},
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["image_png_b64"] == "ZmFrZQ=="
    assert body["reply_fr"]


def test_free_form_payloads_never_return_500():
    """Les endpoints acceptent des documents libres : un sous-objet du mauvais
    type (`{"layout": "x"}`) partait en AttributeError → 500 côté API."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    weird = ["x", 3, None, [], {}, [1], {"a": 1}, True, -1, 1e300, "", [[]]]
    builders = {
        "/v1/vectorize": lambda v: {"layout": v, "building_spec": v},
        "/v1/refine": lambda v: {"layout": v, "building_spec": v},
        "/v1/generate": lambda v: {"rooms": v, "constraints": v, "style": v},
        "/v1/adapt": lambda v: {"plan_document": {"rooms": v, "walls": v, "floor": v}},
        "/v1/edit": lambda v: {
            "instruction": "agrandir", "plan_document": {"rooms": v, "walls": v},
        },
    }
    for path, build in builders.items():
        for value in weird:
            body = build(value)
            res = client.post(path, json=body)
            assert res.status_code < 500, (path, body, res.status_code, res.text[:200])


def test_malformed_polygons_are_ignored_not_fatal():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    for poly in ([{"x": 1}], [{"x": "a", "y": 1}], ["x"], [{"x": 1, "y": None}], [[0, 0]]):
        res = client.post("/v1/vectorize", json={
            "layout": {
                "rooms": [{"type": "living", "polygon": poly}],
                "walls": [{"a": {"x": 0, "y": 0}, "b": poly}],
            }
        })
        assert res.status_code < 500, (poly, res.text[:200])
