"""Solveur de plan : règles de conformité + emprise parcelle → cotes exactes."""
from __future__ import annotations

from typing import Any

from . import compliance
from .diffusion import default_openings, perimeter_and_internal_walls
from .furnish import furnish
from .layout_opt import optimize_rooms

DEFAULT_RULES: dict[str, Any] = {
    "height_m": 2.70,
    "grid_m": 0.10,
    "min_side_m": 2.0,
    "min_living_m2": 9.0,
    "min_bedroom_m2": 9.0,
    "min_kitchen_m2": 5.0,
    "min_bathroom_m2": 3.0,
    "min_hallway_m": 0.90,
    "min_office_m2": 5.0,
    "door_entry_m": 0.90,
    "door_inner_m": 0.80,
    "window_min_m": 1.20,
    "habitable_on_facade": True,
}

MIN_AREA = {
    "living": "min_living_m2",
    "bedroom": "min_bedroom_m2",
    "kitchen": "min_kitchen_m2",
    "bathroom": "min_bathroom_m2",
    "office": "min_office_m2",
    "dining": "min_living_m2",
}


def default_rules() -> dict[str, Any]:
    return dict(DEFAULT_RULES)


def _poly_area(poly: list[dict[str, float]]) -> float:
    if len(poly) < 3:
        return 0.0
    acc = 0.0
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        acc += float(p["x"]) * float(q["y"]) - float(q["x"]) * float(p["y"])
    return abs(acc) / 2


def _bbox(poly: list[dict[str, float]]) -> tuple[float, float, float, float]:
    xs = [float(p["x"]) for p in poly]
    ys = [float(p["y"]) for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _snap(v: float, grid: float) -> float:
    g = grid if grid > 0 else 0.1
    return round(v / g) * g


def _target_area(room: dict[str, Any], rules: dict[str, Any]) -> float:
    typ = str(room.get("type") or "")
    poly = room.get("polygon") or []
    current = float(room.get("area_m2") or _poly_area(poly) or 8)
    key = MIN_AREA.get(typ)
    minimum = float(rules[key]) if key else 4.0
    if typ == "hallway":
        side = float(rules.get("min_hallway_m") or 0.9)
        minimum = max(minimum, side * max(2.0, side))
    return max(current, minimum)


def _dimension_row(room: dict[str, Any]) -> dict[str, Any]:
    poly = room.get("polygon") or []
    if len(poly) < 3:
        return {
            "id": room.get("id"),
            "name": room.get("name") or room.get("type"),
            "type": room.get("type"),
            "width_m": 0,
            "depth_m": 0,
            "area_m2": 0,
        }
    x0, y0, x1, y1 = _bbox(poly)
    w, d = round(x1 - x0, 2), round(y1 - y0, 2)
    return {
        "id": room.get("id"),
        "name": room.get("name") or room.get("type"),
        "type": room.get("type"),
        "width_m": w,
        "depth_m": d,
        "area_m2": round(w * d, 2),
        "x_m": round(x0, 2),
        "y_m": round(y0, 2),
    }


def apply_opening_rules(openings: list[dict[str, Any]], rules: dict[str, Any], width: float, depth: float) -> list[dict[str, Any]]:
    entry = float(rules.get("door_entry_m") or 0.9)
    inner = float(rules.get("door_inner_m") or 0.8)
    window = float(rules.get("window_min_m") or 1.2)
    out = []
    for op in openings:
        item = dict(op)
        wall_id = str(item.get("wall_id") or "")
        if item.get("type") == "window":
            item["width_m"] = max(window, float(item.get("width_m") or 0))
        elif item.get("type") == "door":
            outer = wall_id.startswith("w_outer")
            item["width_m"] = entry if outer else inner
        out.append(item)
    _ = (width, depth)
    return out


def adapt(payload: dict[str, Any]) -> dict[str, Any]:
    plan = dict(payload.get("plan_document") or {})
    parcel = dict(payload.get("parcel") or {})
    rules = {**DEFAULT_RULES, **(payload.get("rules") or {})}
    grid = float(rules.get("grid_m") or 0.1)
    min_side = float(rules.get("min_side_m") or 2.0)
    setback = max(0.0, float(parcel.get("setback_m") or 0))

    bounds = (plan.get("floor") or {}).get("bounds") or {}
    # Bornée : `perimeter_and_internal_walls` / le rendu vectoriel itèrent en
    # mètres ; une valeur `parcel.width_m` absurde ferait boucler très
    # longtemps (DoS). Mêmes bornes que `nlu._clamp_dim`.
    lot_w = max(2.0, min(200.0, float(parcel.get("width_m") or bounds.get("width") or 12)))
    lot_d = max(2.0, min(200.0, float(parcel.get("depth_m") or bounds.get("depth") or 10)))
    house_w = _snap(max(min_side * 2, lot_w - 2 * setback), grid)
    house_d = _snap(max(min_side * 2, lot_d - 2 * setback), grid)
    height = float(rules.get("height_m") or 2.7)

    rooms_in = [r for r in (plan.get("rooms") or []) if (r.get("polygon") or r.get("type"))]
    if not rooms_in:
        raise ValueError("plan sans pièces : générez un plan avant d’adapter")

    spec_rooms = []
    work = []
    for i, room in enumerate(rooms_in):
        area = _target_area(room, rules)
        typ = str(room.get("type") or "other")
        item = {
            "id": room.get("id") or f"r{i+1}",
            "type": typ,
            "name": room.get("name") or typ,
            "area_m2": area,
            "polygon": room.get("polygon") or [],
        }
        work.append(item)
        spec_rooms.append({"type": typ, "area_m2": area, "count": 1})

    packed = optimize_rooms(work, house_w, house_d, {"rooms": spec_rooms}, grid=grid, min_side=min_side)
    walls = perimeter_and_internal_walls(packed, house_w, house_d)
    openings = default_openings(walls, house_w, house_d, packed)
    openings = apply_opening_rules(openings, rules, house_w, house_d)

    doc = {
        "version": "1.0",
        "units": "m",
        "floor": {
            "level": 0,
            "height_m": height,
            "bounds": {"width": house_w, "depth": house_d},
        },
        "walls": walls,
        "rooms": [
            {
                "id": r.get("id"),
                "name": r.get("name") or r.get("type"),
                "type": r.get("type"),
                "polygon": r.get("polygon") or [],
            }
            for r in packed
        ],
        "openings": openings,
        # Le mobilier suit les polygones repackés : le 3D (Blender) et le 2D
        # utilisent exactement les mêmes instances catalog_id/position/rotation.
        "furniture": furnish(packed),
    }
    dimensions = [_dimension_row(r) for r in doc["rooms"]]
    return {
        "plan_document": doc,
        "dimensions": dimensions,
        "parcel": {
            "width_m": lot_w,
            "depth_m": lot_d,
            "setback_m": setback,
            "buildable_width_m": house_w,
            "buildable_depth_m": house_d,
        },
        "rules": rules,
        "compliance_before": compliance.evaluate(plan),
        "compliance": compliance.evaluate(doc),
        "method": "rules-adapt",
    }
