from __future__ import annotations

import io
import json

import pytest

from homekit3d import Plan
from homekit3d import llm as llm_module
from homekit3d.layout import door_zones, overlaps, rect_of
from homekit3d.stylist import DECOR_ROLES, MAX_DECOR_PER_ROOM, STYLES, Stylist


@pytest.fixture
def blank() -> Plan:
    plan = Plan(10.0, 7.0, seed=5)
    plan.rect_room("living", 0, 0, 6, 4, name="Séjour")
    plan.rect_room("bedroom", 6, 0, 10, 4, name="Chambre")
    plan.rect_room("kitchen", 0, 4, 5, 7, name="Cuisine")
    plan.rect_room("bathroom", 5, 4, 10, 7, name="SDB")
    plan.outline()
    plan.walls_from_rooms()
    plan.door(plan.wall_at(6.0, 2.0), 0.5)
    return plan


def fake_llm(payload):
    calls = []

    def call(system: str, user: str) -> str:
        calls.append((system, user))
        return payload if isinstance(payload, str) else json.dumps(payload)

    call.calls = calls
    return call


# --- sans LLM -------------------------------------------------------------------------------------
def test_without_an_llm_the_stylist_uses_rules_and_says_so(catalog, blank):
    report = Stylist(catalog).style(blank)
    assert report["ai"] is False and report["fallback_reason"] == "pas de LLM" and report["style"] in STYLES
    assert blank.style.name == report["style"]


def test_the_rule_based_result_is_identical_from_one_run_to_the_next(catalog, blank):
    def run():
        plan = Plan.from_dict(blank.to_dict())
        Stylist(catalog).style(plan)
        return plan.to_dict()

    assert run() == run()


def test_different_seeds_can_give_different_styles_and_decor(catalog, blank):
    seen = set()
    for seed in range(12):
        plan = Plan.from_dict(blank.to_dict())
        plan.seed = seed
        seen.add((Stylist(catalog).style(plan)["style"], len(plan.items)))
    assert len(seen) > 2


def test_the_stylist_furnishes_empty_rooms_and_decorates(catalog, blank):
    report = Stylist(catalog).style(blank)
    assert set(report["furnished"]) == {r.id for r in blank.rooms} and sum(report["furnished"].values()) >= 15
    roles = {i.role for i in blank.items}
    assert {"bed.double", "sofa", "toilet"} <= roles or {"bed.single", "sofa", "toilet"} <= roles
    assert roles & {"plant", "plant.small", "lamp.floor", "lamp.table", "picture", "rug"}


def test_furnish_false_keeps_the_existing_furniture_untouched(catalog, blank):
    Stylist(catalog).style(blank, furnish=False)
    assert not any(i.role in ("bed.double", "bed.single", "toilet", "kitchen.run") for i in blank.items)


def test_decor_never_lands_in_a_door_swing_or_on_furniture(catalog, blank):
    Stylist(catalog).style(blank)
    zones = door_zones(blank)
    floor_items = [i for i in blank.items if not i.elevation and not i.role.startswith(("rug", "picture", "mirror", "kitchen.upper"))]
    for it in floor_items:
        if it.role in ("plant", "lamp.floor"):
            box = rect_of(it.x, it.y, it.size[0], it.size[1], it.rot)
            assert not any(overlaps(box, z) for z in zones), it.role


def test_decor_is_bounded_per_room(catalog, blank):
    report = Stylist(catalog).style(blank)
    assert all(len(v) <= MAX_DECOR_PER_ROOM for v in report["decor"].values())


def test_pictures_hang_at_wall_height_and_lamps_stand_on_furniture(catalog, blank):
    Stylist(catalog).style(blank)
    for it in blank.items:
        if it.role == "picture":
            assert it.elevation > 1.0
        if it.role in ("lamp.table", "books"):
            assert it.elevation > 0.3


# --- avec un LLM ----------------------------------------------------------------------------------
def test_a_valid_llm_answer_is_used(catalog, blank):
    living, bedroom = blank.rooms[0].id, blank.rooms[1].id
    llm = fake_llm({"style": "chaleureux", "rooms": {living: ["plant", "lamp.floor"], bedroom: ["lamp.table"]}})
    report = Stylist(catalog, llm).style(blank, brief="maison chaleureuse")
    assert report["ai"] is True and report["style"] == "chaleureux" and blank.style.prefer_pack == "sh3d-c"
    assert set(report["decor"][living]) <= {"plant", "lamp.floor"}                   # rien d'autre que ce que le LLM a demandé
    assert report["decor"][bedroom] in (["lamp.table"], [])                           # posée si un chevet existe
    assert "maison chaleureuse" in llm.calls[0][1] and llm.calls[0][0].startswith("You are an interior design assistant")


def test_the_llm_never_sees_coordinates_and_cannot_place_anything(catalog, blank):
    llm = fake_llm({"style": "moderne", "rooms": {}, "x": 3, "items": [{"role": "sofa", "x": 1, "y": 1}]})
    Stylist(catalog, llm).style(blank)
    context = json.loads(llm.calls[0][1])
    assert set(context) == {"brief", "styles", "decor_roles", "max_decor_per_room", "rooms"}
    assert all(set(r) == {"id", "type", "area_m2", "size_m", "already_has"} for r in context["rooms"])
    assert sorted(context["decor_roles"]) == sorted(DECOR_ROLES)


def test_invented_roles_rooms_and_styles_are_dropped(catalog, blank):
    room = blank.rooms[0].id
    llm = fake_llm({"style": "baroque", "rooms": {room: ["plant", "dragon", "sofa", "picture", "rug", "books"], "nope": ["plant"]}})
    report = Stylist(catalog, llm).style(blank)
    assert report["style"] in STYLES and report["style"] != "baroque"
    assert "dragon" not in json.dumps(report["decor"]) and "nope" not in report["decor"]
    assert len(report["decor"][room]) <= MAX_DECOR_PER_ROOM


@pytest.mark.parametrize("bad", ["not json", "[]", "{}", '{"style": 5}', json.dumps({"rooms": {"zz": ["plant"]}}), ""])
def test_a_bad_llm_answer_falls_back_to_the_rules(catalog, blank, bad):
    report = Stylist(catalog, fake_llm(bad)).style(blank)
    assert report["ai"] is False and report["fallback_reason"] and blank.items


def test_a_failing_llm_never_breaks_the_build(catalog, blank):
    def boom(system, user):
        raise TimeoutError("trop lent")

    report = Stylist(catalog, boom).style(blank)
    assert report["ai"] is False and "TimeoutError" in report["fallback_reason"] and blank.items


def test_the_rules_and_a_failed_llm_give_the_same_plan(catalog, blank):
    a, b = Plan.from_dict(blank.to_dict()), Plan.from_dict(blank.to_dict())
    Stylist(catalog).style(a)
    Stylist(catalog, fake_llm("garbage")).style(b)
    assert a.to_dict() == b.to_dict()


# --- client LLM -----------------------------------------------------------------------------------
def test_from_env_is_none_without_a_key(monkeypatch):
    for name in ("HOMEKIT_LLM_KEY", "TOGETHER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert llm_module.from_env() is None


def test_from_env_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("HOMEKIT_LLM_KEY", "k")
    monkeypatch.setenv("HOMEKIT_LLM", "0")
    assert llm_module.from_env() is None
    monkeypatch.setenv("HOMEKIT_LLM", "1")
    assert callable(llm_module.from_env())


def test_the_chat_client_posts_an_openai_style_request_and_returns_the_content(monkeypatch):
    seen = {}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        seen["url"], seen["auth"], seen["timeout"] = req.full_url, req.headers.get("Authorization"), timeout
        seen["body"] = json.loads(req.data)
        return Resp(json.dumps({"choices": [{"message": {"content": ' {"style": "moderne"} '}}]}).encode())

    monkeypatch.setattr(llm_module.urllib.request, "urlopen", fake_urlopen)
    out = llm_module.chat_client("https://llm.example/v1/chat", "secret", "some-model", timeout=7)("sys", "usr")
    assert out == '{"style": "moderne"}'
    assert seen["url"] == "https://llm.example/v1/chat" and seen["auth"] == "Bearer secret" and seen["timeout"] == 7
    assert seen["body"]["model"] == "some-model" and [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]
    assert seen["body"]["response_format"] == {"type": "json_object"}


def test_the_api_key_is_never_part_of_the_prompt(catalog, blank, monkeypatch):
    llm = fake_llm({"style": "moderne", "rooms": {}})
    Stylist(catalog, llm).style(blank)
    assert "secret" not in llm.calls[0][0] + llm.calls[0][1]


def test_validation_keeps_only_known_rooms_and_roles(catalog, blank):
    room = blank.rooms[0].id
    out = Stylist(catalog)._validate({"style": "moderne", "rooms": {room: ["plant", "dragon", "sofa"], "nope": ["plant"]}}, blank)
    assert out == {"style": "moderne", "rooms": {room: ["plant"]}}


def test_the_heavy_style_is_never_drawn_by_chance(catalog, blank):
    styles = set()
    for seed in range(60):
        plan = Plan.from_dict(blank.to_dict())
        plan.seed = seed
        styles.add(Stylist(catalog).style(plan)["style"])
    assert not styles & {"premium", "lowpoly", "lowpoly-chaleureux"} and len(styles) >= 3


def test_a_style_can_be_imposed_even_over_the_llm_and_uses_the_detailed_models(catalog, blank):
    llm = fake_llm({"style": "moderne", "rooms": {}})
    report = Stylist(catalog, llm).style(blank, style="premium")
    assert report["style"] == "premium" and blank.style.prefer_pack == "polyhaven"
    assert any(i.asset.startswith("polyhaven/") for i in blank.items if i.asset)


def test_an_unknown_imposed_style_is_ignored(catalog, blank):
    assert Stylist(catalog).style(blank, style="baroque")["style"] in STYLES


def test_the_llm_may_choose_the_heavy_style_and_is_warned_about_its_weight(catalog, blank):
    llm = fake_llm({"style": "premium", "rooms": {}})
    assert Stylist(catalog, llm).style(blank)["style"] == "premium"
    assert "10 MB" in llm.calls[0][0]



# --- réalisme par défaut ------------------------------------------------------------------------------
REALISTIC_PACKS = {"sh3d-b", "sh3d-c", "polyhaven"}


def test_the_default_styles_furnish_with_realistic_models_not_toys(catalog, blank):
    for seed in range(12):
        plan = Plan.from_dict(blank.to_dict())
        plan.seed = seed
        Stylist(catalog).style(plan)
        packs = {catalog.get(i.asset).pack for i in plan.items if i.asset}
        assert packs and packs <= REALISTIC_PACKS | {"kenney-furniture", "kaykit-furniture", "kaykit-restaurant"}
        bulky = {catalog.get(i.asset).pack for i in plan.items if i.asset and i.role in ("bed.double", "sofa", "wardrobe")}
        assert bulky <= REALISTIC_PACKS, (seed, bulky)


def test_the_low_poly_styles_stay_available_on_request(catalog, blank):
    report = Stylist(catalog).style(blank, style="lowpoly")
    assert report["style"] == "lowpoly"
    assert {catalog.get(i.asset).pack for i in blank.items if i.asset and i.role in ("bed.double", "sofa")} <= {"kenney-furniture"}
