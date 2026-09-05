"""Recettes paramétriques du catalogue 3D (sans bpy, sans Flux).

Chaque entrée est une liste de boîtes locales : size (w,d,h), loc (x,y,z),
couleur RGBA. L'origine est le centre de l'emprise au sol, z=0 au plancher.
Un fichier .glb optionnel dans catalog/glb/<id>.glb remplace la recette.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "catalog.json"
GLB_DIR = ROOT / "glb"

_WOOD = (0.42, 0.28, 0.16, 1.0)
_WOOD_DARK = (0.28, 0.17, 0.09, 1.0)
_LINEN = (0.86, 0.84, 0.78, 1.0)
_FABRIC = (0.45, 0.38, 0.32, 1.0)
_METAL = (0.55, 0.56, 0.58, 1.0)
_STONE = (0.78, 0.76, 0.72, 1.0)


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


CATALOG = load_catalog()


def glb_override(catalog_id: str) -> Path | None:
    if not known_id(catalog_id):
        return None
    path = (GLB_DIR / f"{catalog_id}.glb").resolve()
    root = GLB_DIR.resolve()
    if not path.is_relative_to(root):
        return None
    return path if path.is_file() else None


def known_id(catalog_id: str) -> bool:
    if catalog_id not in CATALOG:
        return False
    if any(sep in catalog_id for sep in ("/", "\\", "..")):
        return False
    return True


def default_size(catalog_id: str) -> tuple[float, float, float]:
    fp = CATALOG.get(catalog_id, {}).get("footprint_m") or [0.5, 0.5, 0.5]
    return float(fp[0]), float(fp[1]), float(fp[2])


def parts_for(catalog_id: str) -> list[dict[str, Any]]:
    fn = _BUILDERS.get(catalog_id)
    if fn is None:
        w, d, h = default_size(catalog_id)
        return [_box("body", w, d, h, 0, 0, h / 2, _WOOD)]
    return fn()


def world_boxes(
    catalog_id: str,
    x: float,
    y: float,
    rotation_deg: float,
    size_m: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Boîtes en coordonnées monde, prêtes pour OBJ stub ou cubes Blender."""
    if not known_id(catalog_id):
        return []
    dw, dd, dh = default_size(catalog_id)
    sw = float((size_m or {}).get("w") or dw) / dw
    sd = float((size_m or {}).get("d") or dd) / dd
    sh = float((size_m or {}).get("h") or dh) / dh
    rad = math.radians(rotation_deg)
    c, s = math.cos(rad), math.sin(rad)
    out: list[dict[str, Any]] = []
    for part in parts_for(catalog_id):
        px, py, pz = part["loc"]
        sx, sy, sz = part["size"]
        px, py, pz = px * sw, py * sd, pz * sh
        sx, sy, sz = sx * sw, sy * sd, sz * sh
        wx = x + px * c - py * s
        wy = y + px * s + py * c
        out.append({
            "size": (sx, sy, sz),
            "location": (wx, wy, pz),
            "rotation_z": rad,
            "color": part["color"],
            "name": part["name"],
        })
    return out


def boxes_to_obj(boxes: list[dict[str, Any]], *, comment: str = "a-ai catalog") -> str:
    lines = [f"# {comment}\n"]
    vid = 1
    for box in boxes:
        sx, sy, sz = box["size"]
        cx, cy, cz = box["location"]
        rz = float(box["rotation_z"])
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        corners = [
            (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
            (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz),
        ]
        cr, sr = math.cos(rz), math.sin(rz)
        for dx, dy, dz in corners:
            wx = cx + dx * cr - dy * sr
            wy = cy + dx * sr + dy * cr
            lines.append(f"v {wx:.5f} {cz + dz:.5f} {wy:.5f}\n")
        faces = (
            (1, 2, 3, 4), (5, 8, 7, 6), (1, 5, 6, 2),
            (2, 6, 7, 3), (3, 7, 8, 4), (4, 8, 5, 1),
        )
        for a, b, c, d in faces:
            lines.append(f"f {vid + a - 1} {vid + b - 1} {vid + c - 1} {vid + d - 1}\n")
        vid += 8
    return "".join(lines)


def _box(
    name: str, w: float, d: float, h: float, x: float, y: float, z: float, color: tuple
) -> dict[str, Any]:
    return {"name": name, "size": (w, d, h), "loc": (x, y, z), "color": color}


def _legs(prefix: str, w: float, d: float, thick: float, height: float, inset: float) -> list[dict[str, Any]]:
    hx, hy = w / 2 - inset, d / 2 - inset
    z = height / 2
    return [
        _box(f"{prefix}_fl", thick, thick, height, -hx, hy, z, _WOOD_DARK),
        _box(f"{prefix}_fr", thick, thick, height, hx, hy, z, _WOOD_DARK),
        _box(f"{prefix}_bl", thick, thick, height, -hx, -hy, z, _WOOD_DARK),
        _box(f"{prefix}_br", thick, thick, height, hx, -hy, z, _WOOD_DARK),
    ]


def _chair() -> list[dict[str, Any]]:
    return [
        *_legs("leg", 0.42, 0.40, 0.04, 0.44, 0.04),
        _box("seat", 0.42, 0.40, 0.05, 0, 0, 0.465, (0.90, 0.76, 0.22, 1.0)),
        _box("back", 0.42, 0.05, 0.42, 0, -0.175, 0.70, _WOOD),
    ]


def _bed(width: float) -> list[dict[str, Any]]:
    length = 2.00
    return [
        _box("frame", width, length, 0.22, 0, 0, 0.11, _WOOD_DARK),
        _box("mattress", width - 0.06, length - 0.06, 0.16, 0, 0, 0.30, _LINEN),
        _box("headboard", width, 0.06, 0.70, 0, -length / 2 + 0.03, 0.57, _WOOD),
        _box("pillow_l", width * 0.38, 0.28, 0.10, -width * 0.22, -length / 2 + 0.32, 0.43, (0.93, 0.91, 0.86, 1)),
        _box("pillow_r", width * 0.38, 0.28, 0.10, width * 0.22, -length / 2 + 0.32, 0.43, (0.93, 0.91, 0.86, 1)),
    ]


def _table_dining() -> list[dict[str, Any]]:
    return [
        *_legs("leg", 1.56, 0.86, 0.07, 0.70, 0.08),
        _box("top", 1.60, 0.90, 0.06, 0, 0, 0.73, _WOOD),
    ]


def _table_coffee() -> list[dict[str, Any]]:
    return [
        *_legs("leg", 1.04, 0.50, 0.05, 0.34, 0.06),
        _box("top", 1.10, 0.55, 0.05, 0, 0, 0.375, _WOOD),
    ]


def _sofa() -> list[dict[str, Any]]:
    return [
        _box("base", 1.80, 0.80, 0.38, 0, 0, 0.19, _FABRIC),
        _box("back", 1.80, 0.16, 0.42, 0, -0.32, 0.59, _FABRIC),
        _box("arm_l", 0.12, 0.80, 0.28, -0.84, 0, 0.52, _FABRIC),
        _box("arm_r", 0.12, 0.80, 0.28, 0.84, 0, 0.52, _FABRIC),
        _box("seat_l", 0.78, 0.58, 0.10, -0.38, 0.04, 0.43, (0.52, 0.44, 0.36, 1)),
        _box("seat_r", 0.78, 0.58, 0.10, 0.38, 0.04, 0.43, (0.52, 0.44, 0.36, 1)),
    ]


def _nightstand() -> list[dict[str, Any]]:
    return [
        _box("body", 0.45, 0.40, 0.42, 0, 0, 0.27, _WOOD),
        _box("top", 0.47, 0.42, 0.03, 0, 0, 0.495, _WOOD_DARK),
        _box("knob", 0.04, 0.04, 0.04, 0, 0.18, 0.30, _METAL),
    ]


def _wardrobe() -> list[dict[str, Any]]:
    return [
        _box("body", 1.20, 0.58, 1.92, 0, 0, 0.96, _WOOD),
        _box("door_l", 0.56, 0.04, 1.70, -0.30, 0.28, 1.00, _WOOD_DARK),
        _box("door_r", 0.56, 0.04, 1.70, 0.30, 0.28, 1.00, _WOOD_DARK),
        _box("handle_l", 0.03, 0.03, 0.12, -0.06, 0.31, 1.00, _METAL),
        _box("handle_r", 0.03, 0.03, 0.12, 0.06, 0.31, 1.00, _METAL),
    ]


def _counter() -> list[dict[str, Any]]:
    return [
        _box("carcass", 2.40, 0.60, 0.82, 0, 0, 0.41, _WOOD),
        _box("top", 2.42, 0.62, 0.04, 0, 0, 0.84, _STONE),
        _box("sink", 0.42, 0.36, 0.05, -0.65, 0, 0.87, _METAL),
    ]


def _sofa_l() -> list[dict[str, Any]]:
    fabric = (0.28, 0.29, 0.31, 1.0)
    return [
        _box("base", 2.40, 0.85, 0.38, 0, -0.35, 0.19, fabric),
        _box("chaise", 0.90, 1.60, 0.38, 0.75, 0.0, 0.19, fabric),
        _box("back", 2.40, 0.16, 0.42, 0, -0.70, 0.59, fabric),
        _box("arm", 0.12, 0.85, 0.28, -1.14, -0.35, 0.52, fabric),
    ]


def _armchair() -> list[dict[str, Any]]:
    fabric = (0.36, 0.24, 0.16, 1.0)
    return [
        _box("base", 0.78, 0.76, 0.36, 0, 0, 0.18, fabric),
        _box("back", 0.78, 0.14, 0.40, 0, -0.31, 0.56, fabric),
        _box("arm_l", 0.10, 0.76, 0.24, -0.34, 0, 0.48, fabric),
        _box("arm_r", 0.10, 0.76, 0.24, 0.34, 0, 0.48, fabric),
    ]


def _stove() -> list[dict[str, Any]]:
    return [
        _box("body", 0.60, 0.55, 0.88, 0, 0, 0.44, (0.16, 0.16, 0.17, 1)),
        _box("hob", 0.58, 0.52, 0.04, 0, 0, 0.90, (0.12, 0.12, 0.12, 1)),
    ]


def _desk() -> list[dict[str, Any]]:
    return [
        *_legs("leg", 1.16, 0.56, 0.05, 0.70, 0.06),
        _box("top", 1.20, 0.60, 0.04, 0, 0, 0.73, (0.22, 0.22, 0.24, 1)),
    ]


def _fireplace() -> list[dict[str, Any]]:
    return [
        _box("body", 0.70, 0.55, 1.18, 0, 0, 0.59, (0.10, 0.10, 0.11, 1)),
        _box("hearth", 0.42, 0.28, 0.36, 0, 0.08, 0.28, (0.22, 0.12, 0.08, 1)),
    ]


def _bathtub() -> list[dict[str, Any]]:
    return [
        _box("tub", 1.70, 0.75, 0.52, 0, 0, 0.26, (0.93, 0.93, 0.94, 1)),
        _box("water", 1.46, 0.52, 0.04, 0, 0, 0.40, (0.78, 0.86, 0.90, 1)),
    ]


def _toilet() -> list[dict[str, Any]]:
    return [
        _box("tank", 0.38, 0.16, 0.42, 0, -0.22, 0.55, (0.93, 0.93, 0.94, 1)),
        _box("bowl", 0.36, 0.48, 0.40, 0, 0.08, 0.22, (0.93, 0.93, 0.94, 1)),
    ]


def _sink() -> list[dict[str, Any]]:
    return [
        _box("pedestal", 0.22, 0.22, 0.70, 0, 0, 0.35, (0.93, 0.93, 0.94, 1)),
        _box("basin", 0.55, 0.42, 0.14, 0, 0, 0.78, (0.93, 0.93, 0.94, 1)),
    ]


def _car() -> list[dict[str, Any]]:
    body = (0.94, 0.94, 0.95, 1)
    return [
        _box("body", 4.20, 1.70, 1.10, 0, 0, 0.70, body),
        _box("cabin", 1.80, 1.55, 0.42, -0.20, 0, 1.28, (0.72, 0.80, 0.86, 1)),
        _box("wheel_fl", 0.32, 0.22, 0.32, -1.35, -0.85, 0.16, (0.12, 0.12, 0.13, 1)),
        _box("wheel_fr", 0.32, 0.22, 0.32, -1.35, 0.85, 0.16, (0.12, 0.12, 0.13, 1)),
        _box("wheel_bl", 0.32, 0.22, 0.32, 1.35, -0.85, 0.16, (0.12, 0.12, 0.13, 1)),
        _box("wheel_br", 0.32, 0.22, 0.32, 1.35, 0.85, 0.16, (0.12, 0.12, 0.13, 1)),
    ]


def _rug() -> list[dict[str, Any]]:
    return [_box("rug", 2.20, 1.60, 0.02, 0, 0, 0.01, (0.72, 0.32, 0.22, 1))]


def _plant() -> list[dict[str, Any]]:
    return [
        _box("pot", 0.28, 0.28, 0.28, 0, 0, 0.14, (0.42, 0.26, 0.14, 1)),
        _box("foliage", 0.45, 0.45, 0.55, 0, 0, 0.58, (0.22, 0.46, 0.16, 1)),
    ]


def _fridge() -> list[dict[str, Any]]:
    return [
        _box("body", 0.65, 0.62, 1.78, 0, 0, 0.89, (0.90, 0.91, 0.92, 1)),
        _box("handle", 0.04, 0.04, 0.42, 0.30, 0.28, 0.95, (0.55, 0.56, 0.58, 1)),
    ]


def _tv() -> list[dict[str, Any]]:
    return [
        _box("console", 1.60, 0.40, 0.42, 0, 0, 0.21, (0.22, 0.18, 0.14, 1)),
        _box("screen", 1.20, 0.08, 0.55, 0, -0.12, 0.82, (0.08, 0.08, 0.10, 1)),
    ]


_BUILDERS = {
    "chair.dining": _chair,
    "bed.single": lambda: _bed(0.90),
    "bed.double": lambda: _bed(1.60),
    "table.dining": _table_dining,
    "table.coffee": _table_coffee,
    "sofa.2seat": _sofa,
    "sofa.lshape": _sofa_l,
    "armchair": _armchair,
    "nightstand": _nightstand,
    "wardrobe": _wardrobe,
    "counter.kitchen": _counter,
    "stove": _stove,
    "desk": _desk,
    "fireplace": _fireplace,
    "bathtub": _bathtub,
    "toilet": _toilet,
    "sink.basin": _sink,
    "car.sedan": _car,
    "rug.rect": _rug,
    "plant.pot": _plant,
    "fridge": _fridge,
    "tv.console": _tv,
}
