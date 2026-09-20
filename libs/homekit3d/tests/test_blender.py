"""Intégration : lance vraiment Blender (ignoré si introuvable). Vérifie le GLB produit et le budget de temps."""
from __future__ import annotations

import json
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest

from homekit3d import Plan
from homekit3d.cli import find_blender

BLENDER = find_blender()
pytestmark = [pytest.mark.blender, pytest.mark.skipif(BLENDER is None, reason="Blender introuvable")]
TIME_BUDGET_S = 30.0


def read_glb(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and version == 2 and length == len(data)
    clen, kind = struct.unpack_from("<II", data, 12)
    assert kind == 0x4E4F534A
    return json.loads(data[20:20 + clen])


def build(tmp_path: Path, plan: Plan, *extra: str) -> tuple[dict, dict, float]:
    src, out, stats = tmp_path / "plan.json", tmp_path / "house.glb", tmp_path / "stats.json"
    src.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "homekit3d", "build", str(src), str(out), "--stats", str(stats),
                           "--no-ai", *extra], capture_output=True, text=True, timeout=120, cwd=Path(__file__).resolve().parent.parent,
                          stdin=subprocess.DEVNULL)
    elapsed = time.perf_counter() - t0
    assert proc.returncode == 0, proc.stdout[-1500:] + proc.stderr[-1500:]
    return read_glb(out), json.loads(stats.read_text(encoding="utf-8")), elapsed


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    plan = Plan(10.0, 7.0, seed=2)
    plan.rect_room("living", 0, 0, 6, 4)
    plan.rect_room("bedroom", 6, 0, 10, 4)
    plan.rect_room("kitchen", 0, 4, 5, 7)
    plan.rect_room("bathroom", 5, 4, 10, 7)
    plan.outline()
    plan.walls_from_rooms()
    plan.door(plan.wall_at(6.0, 2.0), 0.5)
    plan.window(plan.wall_at(3.0, 0.0), 1.5, width=1.4)
    return build(tmp_path_factory.mktemp("bl"), plan)


def test_the_glb_is_valid_gltf_2(built):
    gltf, _, _ = built
    assert gltf["asset"]["version"] == "2.0" and gltf["scenes"] and gltf["meshes"] and gltf["materials"]


def test_a_house_builds_well_under_thirty_seconds(built):
    _, stats, elapsed = built
    assert elapsed < TIME_BUDGET_S and stats["seconds"]["total"] < TIME_BUDGET_S


def test_furniture_shares_its_meshes_instead_of_copying_them(built):
    gltf, stats, _ = built
    assert stats["instances"] > 10
    assert len(gltf["meshes"]) < len(gltf["nodes"])         # plusieurs nœuds pour un même maillage


def _mesh_box(gltf: dict, name_prefix: str) -> tuple[list[float], list[float]]:
    lo, hi = [1e9] * 3, [-1e9] * 3
    for mesh in gltf["meshes"]:
        if mesh.get("name", "").startswith(name_prefix):
            for prim in mesh["primitives"]:
                a = gltf["accessors"][prim["attributes"]["POSITION"]]
                lo = [min(lo[i], a["min"][i]) for i in range(3)]
                hi = [max(hi[i], a["max"][i]) for i in range(3)]
    return lo, hi


def test_the_house_is_metric_and_not_mirrored(built):
    """Y haut, z = y du plan : le séjour du plan (x 0-6, y 0-4) occupe x 0-6 et z 0-4, le sol est à y = 0."""
    gltf, _, _ = built
    lo, hi = _mesh_box(gltf, "shell.floor:living")
    assert [round(v, 2) for v in (lo[0], hi[0], lo[2], hi[2])] == [0.0, 6.0, 0.0, 4.0]
    assert abs(lo[1]) < 0.01 and abs(hi[1]) < 0.01
    lo, hi = _mesh_box(gltf, "shell.wall_ext")
    assert 2.6 < hi[1] < 2.8 and 10.0 < hi[0] - lo[0] < 10.5 and 7.0 < hi[2] - lo[2] < 7.5      # 10 x 7 m + épaisseur des murs


def test_glass_is_translucent_and_floors_are_visible_from_above(built):
    gltf, _, _ = built
    glass = next(m for m in gltf["materials"] if m["name"] == "glass")
    assert glass.get("alphaMode") == "BLEND"
    floor = next(m for m in gltf["materials"] if m["name"].startswith("floor:"))
    assert floor.get("alphaMode", "OPAQUE") == "OPAQUE"


def test_every_used_model_is_reported_with_its_credits(built):
    _, stats, _ = built
    assert stats["models"] and stats["skipped_roles"] == []


def test_a_plan_with_a_garage_and_a_car_builds(tmp_path):
    plan = Plan(8.0, 5.0)
    plan.rect_room("garage", 0, 0, 8, 5)
    plan.outline()
    plan.door(plan.wall_at(4.0, 5.0), 2.0, width=2.4)
    gltf, stats, _ = build(tmp_path, plan)
    assert any(n["name"].startswith("car") for n in gltf["nodes"])


def test_an_invalid_plan_fails_cleanly(tmp_path):
    src = tmp_path / "bad.json"
    src.write_text(json.dumps({"width": 5, "depth": 5, "walls": [], "rooms": [], "openings": [
        {"id": "o", "wall_id": "nope", "kind": "door", "offset": 0}], "items": []}), encoding="utf-8")
    proc = subprocess.run([sys.executable, "-m", "homekit3d", "build", str(src), str(tmp_path / "x.glb"), "--no-ai"],
                          capture_output=True, text=True, timeout=120, cwd=Path(__file__).resolve().parent.parent)
    assert proc.returncode != 0 and not (tmp_path / "x.glb").exists()


# --- murs et sols texturés ------------------------------------------------------------------------------
def small_house() -> Plan:
    plan = Plan(8.0, 5.0, seed=4)
    plan.rect_room("living", 0, 0, 5, 5)
    plan.rect_room("bathroom", 5, 0, 8, 5)
    plan.outline()
    plan.walls_from_rooms()
    plan.door(plan.wall_at(5.0, 2.0), 0.5)
    return plan


def shell_materials(gltf: dict) -> dict[str, dict]:
    return {m["name"]: m for m in gltf["materials"]}


def test_a_realistic_house_has_textured_walls_and_floors_with_relief_and_uvs(tmp_path):
    gltf, _, _ = build(tmp_path, small_house(), "--style", "moderne")
    mats = shell_materials(gltf)
    for name in ("wall_int", "wall_ext", "floor:living", "floor:bathroom"):
        pbr = mats[name]["pbrMetallicRoughness"]
        assert "baseColorTexture" in pbr and "normalTexture" in mats[name], name
    shell_prims = [p for m in gltf["meshes"] if m["name"].startswith("shell.") for p in m["primitives"]]
    textured = {gltf["materials"][p["material"]]["name"]: p for p in shell_prims}
    assert "TEXCOORD_0" in textured["wall_int"]["attributes"] and "TEXCOORD_0" in textured["floor:living"]["attributes"]
    assert len(gltf["images"]) >= 6


def test_a_low_poly_house_stays_untextured_and_light(tmp_path):
    gltf, stats, _ = build(tmp_path, small_house(), "--style", "lowpoly")
    assert "baseColorTexture" not in shell_materials(gltf)["wall_int"]["pbrMetallicRoughness"]
    assert stats["bytes"] < 3_000_000


def test_textures_can_be_switched_off_by_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMEKIT_TEXTURES", "0")
    gltf, _, _ = build(tmp_path, small_house(), "--style", "moderne")
    assert "baseColorTexture" not in shell_materials(gltf)["wall_int"]["pbrMetallicRoughness"]


def test_the_wall_texture_is_embedded_in_the_glb_as_an_image(tmp_path):
    gltf, _, _ = build(tmp_path, small_house(), "--style", "chaleureux")
    tex = shell_materials(gltf)["wall_int"]["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    assert gltf["images"][gltf["textures"][tex]["source"]]["mimeType"] in ("image/jpeg", "image/png")
