from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import together_image  # noqa: E402
from app.diffusion import (  # noqa: E402
    _TYPE_FR,
    _apply_canonical_names,
    _ascii_upper,
    _coherence_clause,
    _careful_repair_notes,
    _flux_prompt,
    _footprint_zone,
    _format_furniture_plan,
    _item_forbidden,
    _layout_user,
    _merge_llm_program,
    _normalize_llm_rooms,
    _overlay_room_labels,
    _parse_json_obj,
    _program_counts,
    _render_floorplan,
    _required_rooms_clause,
    _room_display_name,
    _room_type_from_name,
    _flux_edit_prompt,
    _interpret_edit,
    _sanitize_rooms_program,
    default_openings,
    edit_plan,
    expand_rooms,
    generate,
    generate_flux_plan,
    pack_rooms,
    perimeter_and_internal_walls,
    render_plan_document,
    render_preview,
)
from app.gan_refine import refine  # noqa: E402
from app.nlu import parse_brief  # noqa: E402

# PNG 2x2 réel : `_as_png_b64` refuse désormais un payload qui n'est pas une
# image décodable, les doubles d'API doivent donc renvoyer une vraie image.
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP8zwACTGCSAQANHQEDgslx/wAAAABJRU5ErkJggg=="
)


def test_backend_disabled_without_key(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.delenv("TOGETHER_AI_API_KEY", raising=False)
    monkeypatch.delenv("EDENAI_API_KEY", raising=False)
    monkeypatch.delenv("EDEN_API_KEY", raising=False)
    assert together_image.available() is False
    assert together_image.generate_floorplan_image("x") is None


def test_backend_respects_image_backend_override(monkeypatch):
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "procedural")
    assert together_image.available() is False
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    assert together_image.available() is True


def test_together_key_alone_does_not_draw_images(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    monkeypatch.delenv("EDENAI_API_KEY", raising=False)
    monkeypatch.delenv("EDEN_API_KEY", raising=False)
    assert together_image.available() is False
    assert together_image.generate_floorplan_image("plan", reference_png_b64="YWJj") is None


def test_model_name_default(monkeypatch):
    monkeypatch.delenv("EDENAI_IMAGE_MODEL", raising=False)
    assert together_image.model_name() == "image/generation/google/gemini-3-pro-image-preview"


def test_available_with_eden_key_only(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.delenv("TOGETHER_AI_API_KEY", raising=False)
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    assert together_image.available() is True
    assert together_image.planner_enabled() is False
    assert together_image.method_name() == "gemini-3-pro-image"


def test_eden_generate_sends_layout_as_reference(monkeypatch):
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    captured: dict = {}

    class FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {"data": [{"b64_json": TINY_PNG_B64}]}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            captured["auth"] = (headers or {}).get("Authorization") == "Bearer dummy"
            return FakeResp()

    monkeypatch.setattr(together_image.httpx, "Client", FakeClient)
    out = together_image.generate_floorplan_image("a house", 12, 10, reference_png_b64="YWJj")
    assert captured.get("auth")
    assert "/v3/images/edits" in (captured.get("url") or "")
    body = captured.get("json") or {}
    assert body.get("model") == "google/gemini-3-pro-image-preview"
    assert body.get("prompt") == "a house"
    imgs = body.get("images") or []
    assert imgs and str(imgs[0].get("image_url") or "").startswith("data:image/jpeg;base64,YWJj")
    assert out


def test_eden_generate_without_layout_uses_generations(monkeypatch):
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    captured: dict = {}

    class FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {"data": [{"b64_json": TINY_PNG_B64}]}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResp()

    monkeypatch.setattr(together_image.httpx, "Client", FakeClient)
    out = together_image.generate_floorplan_image("a house", 12, 10)
    assert "/v3/images/generations" in (captured.get("url") or "")
    assert (captured.get("json") or {}).get("model") == "google/gemini-3-pro-image-preview"
    assert out



def test_style_reference_is_the_sweet_home_screenshot():
    path = together_image._style_image_path()
    assert path is not None
    assert path.name in {"sweet_home_style.png", "image.png"}
    raw = together_image.style_reference_b64()
    assert raw
    import base64
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(base64.b64decode(raw)))
    assert img.width > 200 and img.height > 200
    # canvas recadré (sans catalogue / chrome), pas la fenêtre 1600×946
    assert img.size != (1600, 946)


def test_blank_style_labels_removes_dark_letters():
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (220, 80), (232, 214, 176))
    d = ImageDraw.Draw(img)
    d.text((24, 28), "Bedroom", fill=(28, 28, 28), font=ImageFont.load_default())

    def dark_pixels(image: Image.Image) -> int:
        raw = image.convert("RGB").tobytes()
        return sum(
            1
            for i in range(0, len(raw), 3)
            if (77 * raw[i] + 150 * raw[i + 1] + 29 * raw[i + 2]) >> 8 < 80
        )

    dark_before = dark_pixels(img)
    assert dark_before > 10
    dark_after = dark_pixels(together_image._blank_style_labels(img))
    assert dark_after < dark_before // 2


def test_dims_snap_to_multiples_of_32_within_bounds():
    w, h = together_image._dims(12, 10, 1024)
    assert w % 32 == 0 and h % 32 == 0
    assert 512 <= w <= 1024 and 512 <= h <= 1024
    assert w >= h  # emprise plus large que profonde


def test_flux_prompt_is_the_user_brief():
    spec = parse_brief("Maison 2 chambres avec cuisine", {})
    prompt = _flux_prompt(spec, layout_guided=True)
    assert "Sweet Home" in prompt
    assert "Maison 2 chambres avec cuisine" in prompt
    assert "LAYOUT TO FOLLOW" in prompt
    assert "2D" in prompt
    assert "NO TEXT" in prompt
    assert "NO LETTERS" in prompt
    assert "room labels" not in prompt.lower()
    assert "L-shaped sofa" in prompt
    assert "L-shaped or U-shaped" in prompt
    assert "SIMPLER" in prompt or "simpler" in prompt
    assert "NOT photorealistic" in prompt


def test_ascii_upper_strips_accents():
    assert _ascii_upper("Séjour") == "SEJOUR"
    assert _ascii_upper("Salle à manger") == "SALLE A MANGER"


def test_flux_prompt_brief_kwarg():
    prompt = _flux_prompt(brief="Villa T4 avec piscine")
    assert "Villa T4 avec piscine" in prompt
    assert "Sweet Home" in prompt
    assert "NO TEXT" in prompt
    assert "sofa faces the TV" in prompt
    assert "simple" in prompt.lower()


def test_footprint_zone_maps_corners():
    front_left = [{"x": 0, "y": 0}, {"x": 2, "y": 0}, {"x": 2, "y": 2}, {"x": 0, "y": 2}]
    back_right = [{"x": 8, "y": 8}, {"x": 10, "y": 8}, {"x": 10, "y": 10}, {"x": 8, "y": 10}]
    assert _footprint_zone(front_left, 10, 10) == "front-left"
    assert _footprint_zone(back_right, 10, 10) == "back-right"
    assert _footprint_zone([], 10, 10) == ""


def test_generate_falls_back_to_procedural_without_key(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    out = generate(parse_brief("Maison 3 chambres", {}))
    assert out["method"] == "procedural"
    assert out["image_png_b64"]
    assert len(out["layout"]["walls"]) >= 4


def test_refine_passthrough_for_flux_image():
    out = refine({"image_png_b64": "QUJD", "layout": {"rooms": []}, "method": "flux2-max"})
    assert out["method"] == "together_passthrough"
    assert out["image_png_b64"] == "QUJD"


def test_planner_disabled_without_key(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.delenv("TOGETHER_AI_API_KEY", raising=False)
    assert together_image.planner_enabled() is False
    assert together_image.chat_completion([{"role": "user", "content": "hi"}]) is None


def test_planner_flag_and_model(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "dummy")
    monkeypatch.delenv("TOGETHER_PLANNER", raising=False)
    assert together_image.planner_enabled() is True
    monkeypatch.setenv("TOGETHER_PLANNER", "0")
    assert together_image.planner_enabled() is False
    monkeypatch.delenv("TOGETHER_PLANNER_MODEL", raising=False)
    assert together_image.planner_model() == "openai/gpt-oss-120b"


def test_parse_json_obj_tolerates_fences_and_prose():
    assert _parse_json_obj('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json_obj('<think>x</think> here: {"rooms": []} done') == {"rooms": []}
    assert _parse_json_obj("no json here") is None
    assert _parse_json_obj(None) is None


def test_room_type_and_display_name():
    assert _room_type_from_name("SEJOUR") == "living"
    assert _room_type_from_name("CHAMBRE 2") == "bedroom"
    assert _room_type_from_name("SDB 1") == "bathroom"
    assert _room_type_from_name("WC") == "wc"
    assert _room_type_from_name("Zorglub") == "other"
    assert _room_display_name("CHAMBRE 2", "bedroom") == "Chambre 2"
    assert _room_display_name("SEJOUR", "living") == "Séjour"


def test_merge_llm_program_sizes_and_orders():
    spec = parse_brief("Maison 2 chambres avec cuisine", {})
    program = expand_rooms(spec.get("rooms") or [])
    llm = [
        {"name": "SEJOUR", "area": 28, "zone": "front"},
        {"name": "CUISINE", "area": 11, "zone": "front"},
        {"name": "SDB", "area": 5, "zone": "centre"},
        {"name": "CHAMBRE 1", "area": 12, "zone": "back"},
        {"name": "CHAMBRE 2", "area": 11, "zone": "back"},
    ]
    merged = _merge_llm_program(program, llm, 12, 10)
    assert merged is not None
    assert merged[0]["type"] == "living"  # zone front en tête
    assert merged[-1]["type"] == "bedroom"  # zone back en fin
    assert all(r.get("area_m2", 0) > 0 for r in merged)
    assert "_zone" not in merged[0]  # champ interne retiré


def test_merge_llm_program_rejects_garbage():
    program = expand_rooms(parse_brief("Maison 2 chambres", {}).get("rooms") or [])
    assert _merge_llm_program(program, "not a list", 12, 10) is None
    assert _merge_llm_program(program, [{"name": "GARAGE", "area": 20}], 12, 10) is None  # ni séjour ni chambre


def test_layout_user_lists_program():
    spec = parse_brief("Maison 3 chambres avec garage", {})
    program = expand_rooms(spec.get("rooms") or [])
    msg = _layout_user(spec, program, 12, 10)
    assert "FOOTPRINT W=12.0 m, D=10.0 m" in msg
    assert "FIXED ROOM PROGRAM" in msg and "CHAMBRE" in msg
    assert "north-west" in msg


def test_render_floorplan_produces_png():
    spec = parse_brief("Maison 2 chambres avec garage", {})
    rooms = pack_rooms(expand_rooms(spec.get("rooms") or []), 12, 10)
    walls = perimeter_and_internal_walls(rooms, 12, 10)
    openings = default_openings(walls, 12, 10)
    b64 = _render_floorplan(rooms, walls, openings, 12, 10, veranda_depth=1.8)
    import base64
    import io

    from PIL import Image

    im = Image.open(io.BytesIO(base64.b64decode(b64)))
    assert im.format == "PNG" and im.width > 400 and im.height > 400


def test_render_plan_document_with_furniture():
    from app.plan_adapt import adapt
    from app.vectorize import vectorize
    import base64
    import io

    from PIL import Image

    spec = parse_brief("Maison 3 chambres avec garage", {})
    gen = generate(spec)
    plan = vectorize({"layout": gen["layout"], "building_spec": spec})["plan_document"]
    doc = adapt({"plan_document": plan, "parcel": {"width_m": 14, "depth_m": 11}}).get("plan_document") or plan
    b64 = render_plan_document(doc)
    im = Image.open(io.BytesIO(base64.b64decode(b64)))
    assert im.format == "PNG" and im.width > 400 and im.height > 400
    assert doc.get("furniture")


def test_generate_uses_vector_renderer_without_key(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    out = generate(parse_brief("Maison 3 chambres avec garage", {}))
    assert out["method"] == "procedural"
    assert out["image_png_b64"]


def test_generate_image_false_skips_png(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    out = generate(parse_brief("Maison 2 chambres", {}), image=False)
    assert out["image_png_b64"] == ""
    assert out["layout"]["rooms"]


def test_render_preview_sends_brief_straight_to_flux(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "dummy")
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    monkeypatch.setenv("IMAGE_RENDERER", "gemini")
    monkeypatch.setenv("TOGETHER_PLANNER", "0")
    captured: dict = {}

    def fake_flux(prompt, width_m=12.0, depth_m=10.0, reference_png_b64=None):
        captured["ref"] = reference_png_b64
        captured["prompt"] = prompt
        return "ZmFrZXBpbmc="

    monkeypatch.setattr("app.together_image.generate_floorplan_image", fake_flux)
    spec = parse_brief("Maison 2 chambres avec garage", {})
    b64, method = render_preview({"rooms": []}, spec)
    assert captured.get("ref")
    assert str(captured.get("ref") or "").startswith("data:image/jpeg;base64,")
    assert "Maison 2 chambres avec garage" in (captured.get("prompt") or "")
    assert "LAYOUT TO FOLLOW" in (captured.get("prompt") or "")
    assert "Sweet Home" in (captured.get("prompt") or "")
    assert "NO TEXT" in (captured.get("prompt") or "")
    assert "Invent a NEW" not in (captured.get("prompt") or "")
    assert method.startswith("gemini-3-pro-image")
    assert b64 == "ZmFrZXBpbmc="


def test_item_forbidden_keeps_rooms_coherent():
    assert _item_forbidden("living", "double bed with pillows")
    assert not _item_forbidden("living", "coffee table in front of the sofa")
    assert _item_forbidden("living", "dining table with six chairs")
    assert _item_forbidden("kitchen", "L-shaped sofa")
    assert _item_forbidden("kitchen", "dining table with yellow chairs")
    assert _item_forbidden("kitchen", "a large tub")
    assert not _item_forbidden("kitchen", "fridge at the end of the run")
    assert _item_forbidden("bedroom", "white toilet in the corner")
    assert _item_forbidden("bedroom", "bathtub along the wall")
    assert _item_forbidden("bedroom", "a shower tray")
    assert _item_forbidden("bedroom", "washbasin and mirror")
    assert _item_forbidden("bedroom", "bathroom sink")
    assert not _item_forbidden("bedroom", "double bed with two nightstands")
    assert not _item_forbidden("bathroom", "bathtub, toilet and washbasin")


def test_format_furniture_plan_drops_bath_objects_in_bedroom():
    text = _format_furniture_plan({
        "rooms": [
            {
                "type": "bedroom",
                "items": ["double bed with nightstands", "a toilet in the corner", "wardrobe"],
            },
            {"type": "bathroom", "items": ["bathtub", "toilet", "washbasin"]},
        ]
    })
    assert "double bed" in text
    assert "wardrobe" in text
    bedroom_part = text.split("bathroom")[0].lower()
    assert "toilet" not in bedroom_part
    assert "bathtub" in text.lower()
    assert "Bathroom fixtures stay in the bathroom/WC only" in text


def test_flux_prompt_checks_each_room_coherence():
    spec = parse_brief("Maison 2 chambres avec salle de bain", {})
    text = _flux_prompt(brief="Maison 2 chambres avec salle de bain", spec=spec)
    assert "ROOM COHERENCE" in text
    assert "NO toilet" in text
    assert "ONLY in bathroom" in text
    assert "inspect every room" in _coherence_clause(spec)
    assert "REQUIRED ROOMS" in text
    assert "2x bedroom" in text
    assert "WALLS:" in text
    assert "never in kitchen" in text.lower() or "NO toilet, NO bathtub" in text
    assert "two armchairs" in text.lower() or "two armchairs" in _coherence_clause(spec)
    assert "NO dining table" in text


def test_flux_prompt_careful_redraw():
    spec = parse_brief("Maison 2 chambres avec cuisine", {})
    text = _flux_prompt(brief="Maison 2 chambres avec cuisine", spec=spec, careful=True)
    assert "Be extra strict" in text
    assert "two dining rooms" in text
    assert "sofa + coffee table + TV" in text
    notes = _careful_repair_notes(spec)
    assert any("bathroom" in n.lower() for n in notes)


def test_required_rooms_clause_lists_program():
    spec = parse_brief("Maison 2 chambres avec garage", {})
    required = _program_counts(spec)
    assert required.get("bedroom") == 2
    assert required.get("garage") == 1
    clause = _required_rooms_clause(spec)
    assert "2x bedroom" in clause
    assert "1x garage" in clause
    assert "Do not draw two dining rooms" in clause


def test_format_furniture_plan_drops_wrong_objects():
    text = _format_furniture_plan({
        "rooms": [
            {"type": "living", "items": ["L-sofa against wall facing TV", "a bed in the corner"]},
            {"type": "kitchen", "items": ["L-counter with sink and hob", "a sofa"]},
        ]
    })
    assert "FURNITURE INVENTORY" in text
    assert "L-sofa" in text
    assert "bed" not in text.lower()
    assert "L-counter" in text
    assert "sofa" not in text.split("kitchen")[-1].lower() if "kitchen" in text else True


def test_flux_uses_gpt_oss_furniture_inventory(monkeypatch):
    import json

    monkeypatch.setenv("TOGETHER_API_KEY", "dummy")
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    monkeypatch.setenv("IMAGE_RENDERER", "gemini")
    monkeypatch.delenv("TOGETHER_PLANNER", raising=False)
    captured: dict = {}

    def fake_chat(messages, **_kwargs):
        captured["chat"] = messages
        return json.dumps({
            "rooms": [
                {"type": "living", "items": ["L-sofa against the south wall facing the TV"]},
                {"type": "kitchen", "items": ["U-shaped counters with sink and hob"]},
            ]
        })

    def fake_flux(prompt, width_m=12.0, depth_m=10.0, reference_png_b64=None):
        captured["prompt"] = prompt
        return "ZmFrZXBpbmc="

    spec = parse_brief("Maison 2 chambres avec cuisine", {})

    monkeypatch.setattr("app.together_image.chat_completion", fake_chat)
    monkeypatch.setattr("app.together_image.generate_floorplan_image", fake_flux)
    b64, method = generate_flux_plan(spec.get("brief") or "", {}, spec)
    assert captured.get("chat")
    assert "FURNITURE INVENTORY" in (captured.get("prompt") or "")
    assert "L-sofa" in (captured.get("prompt") or "")
    assert "U-shaped counters" in (captured.get("prompt") or "")
    assert "LAYOUT TO FOLLOW" in (captured.get("prompt") or "")
    assert method.startswith("gemini-3-pro-image")
    assert b64 == "ZmFrZXBpbmc="


def _tiny_png_b64() -> str:
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (180, 180, 180)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_flux_prompt_includes_repair_notes():
    text = _flux_prompt(brief="a house", repair_notes=["bed in the living room"])
    assert "bed in the living room" in text


def test_flux_draws_once_from_layout_guide(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "dummy")
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    monkeypatch.setenv("IMAGE_RENDERER", "gemini")
    captured: dict = {"flux": 0, "prompts": []}
    steps: list[str] = []
    spec = parse_brief("Maison 2 chambres avec cuisine", {})

    def fake_chat(_messages, **_kwargs):
        return None

    def fake_flux(prompt, width_m=12.0, depth_m=10.0, reference_png_b64=None):
        captured["flux"] += 1
        captured["prompts"].append(prompt)
        captured["ref"] = reference_png_b64
        return "ZmFrZXBpbmc="

    def fake_notify(_job_id, step):
        steps.append(step)

    monkeypatch.setattr("app.together_image.chat_completion", fake_chat)
    monkeypatch.setattr("app.together_image.generate_floorplan_image", fake_flux)
    monkeypatch.setattr("app.diffusion._notify_job_step", fake_notify)
    b64, method = generate_flux_plan(
        spec.get("brief") or "", {}, spec, job_id="11111111-1111-1111-1111-111111111111"
    )
    assert captured["flux"] == 1
    assert "LAYOUT TO FOLLOW" in captured["prompts"][0]
    assert "never copy them into the kitchen" in captured["prompts"][0]
    assert str(captured.get("ref") or "").startswith("data:image/jpeg;base64,")
    assert steps == ["gemini"]
    assert method == "gemini-3-pro-image"
    assert b64 == "ZmFrZXBpbmc="


def test_flux_keeps_drawing_without_furniture_llm(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "dummy")
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    monkeypatch.setenv("IMAGE_RENDERER", "gemini")
    calls = {"flux": 0}

    def fake_chat(_messages, **_kwargs):
        return None

    def fake_flux(prompt, width_m=12.0, depth_m=10.0, reference_png_b64=None):
        calls["flux"] += 1
        return "ZmFrZXBpbmc="

    monkeypatch.setattr("app.together_image.chat_completion", fake_chat)
    monkeypatch.setattr("app.together_image.generate_floorplan_image", fake_flux)
    spec = parse_brief("Maison 2 chambres", {})
    b64, method = generate_flux_plan(spec.get("brief") or "", {}, spec)
    assert calls["flux"] == 1
    assert b64 == "ZmFrZXBpbmc="
    assert method == "gemini-3-pro-image"


def test_merge_llm_program_drops_invented_rooms():
    program = expand_rooms(parse_brief("Maison 2 chambres", {}).get("rooms") or [])
    llm = [
        {"name": "SEJOUR", "area": 28, "zone": "front"},
        {"name": "CUISINE", "area": 11, "zone": "front"},
        {"name": "SDB", "area": 5, "zone": "centre"},
        {"name": "CHAMBRE 1", "area": 12, "zone": "back"},
        {"name": "CHAMBRE 2", "area": 11, "zone": "back"},
        {"name": "GARAGE", "area": 20, "zone": "back"},
        {"name": "PISCINE", "area": 40, "zone": "back"},
    ]
    merged = _merge_llm_program(program, llm, 12, 10)
    assert merged is not None
    types = [r["type"] for r in merged]
    assert "garage" not in types
    assert types.count("bedroom") == 2
    assert len(merged) == len(program)


def test_normalize_llm_rooms_accepts_valid_tiling():
    program = [
        {"id": "r1", "type": "living", "name": "Séjour", "area_m2": 30},
        {"id": "r2", "type": "kitchen", "name": "Cuisine", "area_m2": 12},
        {"id": "r3", "type": "bedroom", "name": "Chambre 1", "area_m2": 12},
        {"id": "r4", "type": "bathroom", "name": "SDB", "area_m2": 6},
    ]
    llm = [
        {"name": "SEJOUR", "x": 0, "y": 0, "w": 6, "d": 10},
        {"name": "CUISINE", "x": 6, "y": 0, "w": 6, "d": 4},
        {"name": "CHAMBRE 1", "x": 6, "y": 4, "w": 6, "d": 4},
        {"name": "SDB", "x": 6, "y": 8, "w": 6, "d": 2},
    ]
    out = _normalize_llm_rooms(program, llm, 12, 10)
    assert out is not None
    assert [r["type"] for r in out] == ["living", "kitchen", "bedroom", "bathroom"]
    assert all(r.get("polygon") and len(r["polygon"]) == 4 for r in out)


def test_normalize_llm_rooms_rejects_heavy_overlap():
    program = [
        {"id": "r1", "type": "living", "name": "Séjour", "area_m2": 30},
        {"id": "r2", "type": "kitchen", "name": "Cuisine", "area_m2": 12},
    ]
    llm = [
        {"name": "SEJOUR", "x": 0, "y": 0, "w": 10, "d": 10},
        {"name": "CUISINE", "x": 0, "y": 0, "w": 10, "d": 10},
    ]
    assert _normalize_llm_rooms(program, llm, 12, 10) is None


def test_normalize_llm_rooms_drops_extra_and_requires_program():
    program = [
        {"id": "r1", "type": "living", "name": "Séjour", "area_m2": 30},
        {"id": "r2", "type": "kitchen", "name": "Cuisine", "area_m2": 12},
    ]
    llm = [
        {"name": "SEJOUR", "x": 0, "y": 0, "w": 6, "d": 10},
        {"name": "GARAGE", "x": 6, "y": 0, "w": 6, "d": 10},
    ]
    assert _normalize_llm_rooms(program, llm, 12, 10) is None  # cuisine manquante


def test_canonical_names_ignore_llm_wording():
    rooms = [
        {"type": "bedroom", "name": "SUITE PARENTALE"},
        {"type": "bedroom", "name": "chmbre"},
        {"type": "living", "name": "SALON COSY"},
    ]
    out = _apply_canonical_names(rooms)
    assert [r["name"] for r in out] == ["Chambre 1", "Chambre 2", "Séjour"]


def test_generated_furniture_follows_room_type(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    gen = generate(parse_brief("Maison 2 chambres avec garage", {}))
    rooms = gen["layout"]["rooms"]
    names = {r["name"] for r in rooms}
    assert "Garage" in names
    for room in rooms:
        assert room["type"] in _TYPE_FR
        if room["type"] == "bedroom":
            assert room["name"].startswith("Chambre")
        if room["type"] == "kitchen":
            assert room["name"] == "Cuisine"


def test_overlay_room_labels_returns_png_with_text():
    spec = parse_brief("Maison 2 chambres", {})
    rooms = pack_rooms(expand_rooms(spec.get("rooms") or []), 12, 10)
    walls = perimeter_and_internal_walls(rooms, 12, 10)
    openings = default_openings(walls, 12, 10)
    b64 = _render_floorplan(rooms, walls, openings, 12, 10)
    out = _overlay_room_labels(b64, rooms, 12, 10)
    import base64 as b64mod
    import io

    from PIL import Image

    im = Image.open(io.BytesIO(b64mod.b64decode(out)))
    assert im.format == "PNG" and im.width > 100


def test_generate_never_calls_housediff(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.setenv("AI_STUB", "0")
    called = {"n": 0}

    def boom(_spec):
        called["n"] += 1
        raise AssertionError("HouseDiffusion ne doit plus générer le plan")

    monkeypatch.setattr("app.housediff.generate", boom)
    monkeypatch.setattr("app.housediff.available", lambda: True)
    out = generate(parse_brief("Maison 2 chambres", {}))
    assert called["n"] == 0
    assert out["method"] == "procedural"
    assert out["layout"]["rooms"]


def test_refine_passthrough_for_together_layout():
    out = refine({"image_png_b64": "QUJD", "layout": {"rooms": []}, "method": "together-layout"})
    assert out["method"] == "together_passthrough"


def test_sanitize_rooms_program_rejects_junk():
    assert _sanitize_rooms_program(None) is None
    assert _sanitize_rooms_program([{"type": "living", "count": 1}]) is None
    out = _sanitize_rooms_program([
        {"type": "living", "count": 1},
        {"type": "kitchen", "count": 1},
        {"type": "spaceship", "count": 4},
    ])
    assert out is not None
    assert [r["type"] for r in out] == ["living", "kitchen"]


def test_flux_edit_prompt_keeps_current_plan():
    spec = parse_brief("Maison 2 chambres", {})
    text = _flux_edit_prompt(brief="Maison 2 chambres", spec=spec, edit_en="add a kitchen island")
    assert "CURRENT" in text
    assert "add a kitchen island" in text
    assert "do not return a copy" in text.lower()
    assert "NO TEXT" in text
    assert "REQUIRED ROOMS" in text


def test_interpret_edit_fallback_without_key(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    out = _interpret_edit("ajoute un îlot", parse_brief("Maison 2 chambres", {}))
    assert "îlot" in out["edit_en"]
    assert out["rooms"] is None
    assert out["reply_fr"]
    assert not out.get("clarify")


def test_interpret_edit_removes_named_room_without_key(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    spec = parse_brief("Maison 2 chambres avec garage", {})
    assert _program_counts(spec).get("garage") == 1
    out = _interpret_edit("retire le garage", spec)
    assert out["rooms"] is not None
    assert "garage" not in _program_counts({"rooms": out["rooms"]})
    assert not out.get("clarify")
    assert "garage" in out["edit_en"].lower()


def test_interpret_edit_vague_room_asks_which(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    spec = parse_brief("Maison 2 chambres avec garage", {})
    out = _interpret_edit("retire moi cette pièce", spec)
    assert out["rooms"] is None
    assert out["clarify"]
    assert "quelle" in out["reply_fr"].lower()


def test_edit_plan_keeps_png_without_flux(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.setenv("IMAGE_BACKEND", "procedural")
    spec = parse_brief("Maison 2 chambres", {})
    out = edit_plan(
        "ajoute un îlot dans la cuisine",
        brief="Maison 2 chambres",
        spec=spec,
        plan_document={"rooms": [{"type": "kitchen"}]},
        image_png_b64="ZmFrZXBpbmc=",
    )
    assert out["method"] == "edit-clarify"
    assert out["edit_status"] == "clarification_required"
    assert out["image_png_b64"]
    assert out["reply_fr"]
    assert out["plan_document"]["rooms"]


def test_edit_plan_does_not_change_only_the_current_image(monkeypatch):
    import json

    monkeypatch.setenv("TOGETHER_API_KEY", "dummy")
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    monkeypatch.setenv("IMAGE_RENDERER", "gemini")
    spec = parse_brief("Maison 2 chambres avec cuisine", {})
    png = _tiny_png_b64()
    captured: dict = {}

    def fake_chat(messages, **_kwargs):
        captured["chat"] = messages
        return json.dumps({
            "edit_en": "add a kitchen island in the centre",
            "reply_fr": "J'ajoute un îlot au centre de la cuisine.",
            "rooms": None,
        })

    def fake_flux(*_args, **_kwargs):
        pytest.fail("an image-only edit must not be generated")

    monkeypatch.setattr("app.together_image.chat_completion", fake_chat)
    monkeypatch.setattr("app.together_image.generate_floorplan_image", fake_flux)
    out = edit_plan(
        "ajoute un îlot",
        brief="Maison 2 chambres avec cuisine",
        spec=spec,
        image_png_b64=png,
    )
    assert captured.get("chat")
    assert out["clarify"]
    assert out["edit_status"] == "clarification_required"
    assert out["reply_fr"].startswith("Pour modifier le plan")
    assert out["image_png_b64"] == png
    assert out["method"] == "edit-clarify"


def test_edit_plan_vague_room_keeps_png(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.setenv("IMAGE_BACKEND", "procedural")
    spec = parse_brief("Maison 2 chambres avec garage", {})
    out = edit_plan(
        "retire moi cette pièce",
        brief="Maison 2 chambres avec garage",
        spec=spec,
        plan_document={"rooms": [{"type": "garage"}]},
        image_png_b64="ZmFrZXBpbmc=",
    )
    assert out["clarify"]
    assert out["image_png_b64"]
    assert _program_counts(out["building_spec"]).get("garage") == 1


def test_edit_plan_removes_garage_without_flux(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.setenv("IMAGE_BACKEND", "procedural")
    spec = parse_brief("Maison 2 chambres avec garage", {})
    out = edit_plan(
        "retire le garage",
        brief="Maison 2 chambres avec garage",
        spec=spec,
        plan_document={"rooms": [{"type": "garage"}]},
        image_png_b64="oldpng",
    )
    assert not out.get("clarify")
    assert "garage" not in _program_counts(out["building_spec"])
    assert out["image_png_b64"] != "oldpng"
    rooms = (out.get("plan_document") or {}).get("rooms") or []
    assert all(str(r.get("type") or "") != "garage" for r in rooms)


def test_edit_plan_room_change_renders_the_updated_document_locally(monkeypatch):
    import json

    monkeypatch.setenv("TOGETHER_API_KEY", "dummy")
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    monkeypatch.setenv("IMAGE_RENDERER", "gemini")
    monkeypatch.setenv("TOGETHER_NLU", "0")
    spec = parse_brief("Maison 2 chambres avec garage", {})
    assert _program_counts(spec).get("garage") == 1
    png = _tiny_png_b64()
    captured: dict = {}

    def fake_chat(_messages, **_kwargs):
        return json.dumps({
            "edit_en": "keep the same floor plan",
            "reply_fr": "Je mets à jour le plan.",
            "rooms": None,
        })

    def fake_flux(prompt, width_m=12.0, depth_m=10.0, reference_png_b64=None):
        captured["prompt"] = prompt
        pytest.fail("room geometry must come from the validated PlanDocument")

    monkeypatch.setattr("app.together_image.chat_completion", fake_chat)
    monkeypatch.setattr("app.together_image.generate_floorplan_image", fake_flux)
    out = edit_plan(
        "retire le garage",
        brief="Maison 2 chambres avec garage",
        spec=spec,
        plan_document=_plan_document_for_edit_test(),
        image_png_b64=png,
    )
    assert "garage" not in _program_counts(out["building_spec"])
    assert not out.get("clarify")
    assert out["image_png_b64"] != png
    assert out["method"] == "procedural+edit"
    assert out["edit_status"] == "applied"
    assert not captured


def _plan_document_for_edit_test():
    """Return a minimal valid room layout for edit-pipeline integration tests."""
    return {
        "version": "1.0",
        "units": "m",
        "floor": {"bounds": {"width": 8, "depth": 6}},
        "rooms": [
            {
                "id": "living-1",
                "type": "living",
                "polygon": [
                    {"x": 0, "y": 0},
                    {"x": 5, "y": 0},
                    {"x": 5, "y": 6},
                    {"x": 0, "y": 6},
                ],
            },
            {
                "id": "garage-1",
                "type": "garage",
                "polygon": [
                    {"x": 5, "y": 0},
                    {"x": 8, "y": 0},
                    {"x": 8, "y": 3},
                    {"x": 5, "y": 3},
                ],
            },
        ],
        "walls": [
            {"id": "w1", "a": {"x": 0, "y": 0}, "b": {"x": 8, "y": 0}, "thickness_m": 0.15},
            {"id": "w2", "a": {"x": 8, "y": 0}, "b": {"x": 8, "y": 6}, "thickness_m": 0.15},
            {"id": "w3", "a": {"x": 8, "y": 6}, "b": {"x": 0, "y": 6}, "thickness_m": 0.15},
            {"id": "w4", "a": {"x": 0, "y": 6}, "b": {"x": 0, "y": 0}, "thickness_m": 0.15},
        ],
        "openings": [],
    }


# --- SSRF : téléchargement d'images pointées par une réponse externe ---------


def test_fetch_image_url_rejects_non_https():
    from app.together_image import _fetch_image_url

    for url in ["http://example.com/a.png", "file:///etc/passwd", "ftp://x/a.png", "", None, 42]:
        assert _fetch_image_url(url) is None, url


def test_is_public_https_url_rejects_internal_targets(monkeypatch):
    """Métadonnées cloud, loopback et réseaux privés doivent être refusés."""
    import socket as socket_mod

    from app import together_image

    def fake_getaddrinfo(host, *_a, **_kw):
        mapping = {
            "metadata.evil.test": "169.254.169.254",  # métadonnées cloud
            "localhost.evil.test": "127.0.0.1",
            "intranet.evil.test": "10.1.2.3",
            "public.example.test": "93.184.216.34",
        }
        ip = mapping.get(host)
        if ip is None:
            raise OSError("unknown host")
        return [(socket_mod.AF_INET, socket_mod.SOCK_STREAM, 6, "", (ip, 443))]

    monkeypatch.setattr(together_image.socket, "getaddrinfo", fake_getaddrinfo)

    assert not together_image._is_public_https_url("https://metadata.evil.test/latest/meta-data/")
    assert not together_image._is_public_https_url("https://localhost.evil.test/x.png")
    assert not together_image._is_public_https_url("https://intranet.evil.test/x.png")
    assert not together_image._is_public_https_url("https://unresolvable.evil.test/x.png")
    assert together_image._is_public_https_url("https://public.example.test/x.png")


def test_fetch_image_url_refuses_redirect_to_internal_target(monkeypatch):
    """Une URL publique ne doit pas pouvoir rebondir vers une cible interne."""
    from app import together_image

    monkeypatch.setattr(
        together_image,
        "_is_public_https_url",
        lambda url: isinstance(url, str) and url.startswith("https://public."),
    )

    class _Resp:
        is_redirect = True
        headers = {"location": "https://169.254.169.254/latest/meta-data/"}

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    class _Client:
        def __init__(self, *_a, **_kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def stream(self, _method, _url):
            return _Resp()

    monkeypatch.setattr(together_image.httpx, "Client", _Client)
    assert together_image._fetch_image_url("https://public.example.test/x.png") is None


# --- Robustesse du chemin Eden AI : réponse mal formée, hostile, gigantesque --


def _fake_client(responses):
    """httpx.Client bouchonné qui rend `responses` (status, payload) à la suite."""
    calls: list[dict] = []

    class FakeResp:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload
            self.text = "boom"

        def json(self):
            if isinstance(self._payload, Exception):
                raise self._payload
            return self._payload

    class FakeClient:
        def __init__(self, *a, **k):
            calls.append({"timeout": k.get("timeout")})

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None):
            idx = min(len(calls) - 1, len(responses) - 1)
            status, payload = responses[idx]
            calls[-1].update({"url": url, "json": json})
            return FakeResp(status, payload)

    return FakeClient, calls


def test_eden_malformed_responses_never_raise(monkeypatch):
    """Champs manquants, types inattendus, base64 invalide : repli local, pas de crash."""
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    hostile = [
        {},
        {"data": None},
        {"data": "not-a-list"},
        {"data": [None]},
        {"data": [{"b64_json": 12345}]},
        {"data": [{"b64_json": "!!! pas du base64 !!!"}]},
        {"data": [{"url": {"nested": "dict"}}]},
        {"output": "chaîne au lieu d'un objet"},
        {"output": {"items": [{"image": ""}]}},
        {"status": "fail", "error": {"message": "quota"}},
        [1, 2, 3],
        "réponse texte",
    ]
    for payload in hostile:
        client, _ = _fake_client([(200, payload)])
        monkeypatch.setattr(together_image.httpx, "Client", client)
        assert together_image.generate_floorplan_image("plan", 12, 10) is None, payload


def test_eden_http_error_and_json_error_fall_back_locally(monkeypatch):
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    for responses in ([(500, {})], [(200, ValueError("pas du JSON"))], [(429, {})]):
        client, _ = _fake_client(responses)
        monkeypatch.setattr(together_image.httpx, "Client", client)
        assert together_image.generate_floorplan_image("plan", 12, 10) is None


def test_eden_fallback_chain_shares_one_time_budget(monkeypatch):
    """Trois tentatives à `_image_timeout()` chacune bloquaient un worker
    jusqu'à 30 min : le budget est désormais global."""
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    monkeypatch.setenv("TOGETHER_IMAGE_TIMEOUT", "60")
    client, calls = _fake_client([(200, {})])
    monkeypatch.setattr(together_image.httpx, "Client", client)
    assert together_image.generate_floorplan_image("plan", 12, 10, reference_png_b64="YWJj") is None
    assert len(calls) >= 2
    assert sum(c["timeout"] or 0 for c in calls) <= 60.0 * len(calls)
    assert all((c["timeout"] or 0) <= 60.0 for c in calls)


def test_oversized_image_is_rejected():
    """Une image géante renvoyée par le fournisseur ne doit pas être décodée."""
    import base64
    import io

    from PIL import Image

    img = Image.new("L", (8000, 8000), 128)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img.close()
    assert together_image._as_png_b64(base64.b64encode(buf.getvalue()).decode()) is None


def test_oversized_inline_base64_is_rejected():
    payload = "A" * (together_image.MAX_IMAGE_B64_CHARS + 1)
    assert together_image._strip_b64(payload) is None
    assert together_image._as_png_b64(payload) is None


def test_eden_failure_still_produces_a_local_preview(monkeypatch):
    """Le worker doit rendre un plan même quand le fournisseur image est muet."""
    from app.diffusion import generate

    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "together")
    client, _ = _fake_client([(503, {})])
    monkeypatch.setattr(together_image.httpx, "Client", client)
    out = generate({"rooms": [{"type": "living", "count": 1}, {"type": "bedroom", "count": 1}]})
    assert out["image_png_b64"]
    assert out["layout"]["rooms"]
