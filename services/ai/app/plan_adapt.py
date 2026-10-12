"""Solveur de plan : règles de conformité + emprise parcelle → cotes exactes."""
from __future__ import annotations

from typing import Any

from app.document_validation import validate_generated_document
from app.parcel_constraints import resolve_parcel
from app.plan_openings import default_openings, fit_generated_windows
from app.plan_walls import perimeter_and_internal_walls

from . import compliance
from .furnish import furnish
from .layout_opt import PartiUnavailable, normalize_variant, optimize_rooms

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


# Part maximale du couloir dans la maison quand on n'a que des polygones pour cible.
HALLWAY_SHARE_CAP = 0.10


def _usable_program(plan: dict[str, Any], rooms_in: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Le programme demandé embarqué dans le plan, s'il décrit encore ce plan.

    Un document venu de l'éditeur peut avoir perdu ou gagné des pièces depuis : le programme n'est
    repris que si les types de pièces (couloirs exclus : le packer les découpe) sont les mêmes.
    """
    raw = plan.get("program")
    if not isinstance(raw, list) or not raw:
        return []
    out: list[dict[str, Any]] = []
    for item in raw[:64]:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            return []
        try:
            area = float(item.get("area_m2"))
        except (TypeError, ValueError):
            return []
        if not 0.5 <= area <= 500:
            return []
        out.append({"id": str(item.get("id") or f"p{len(out) + 1}"), "type": item["type"],
                    "name": str(item.get("name") or item["type"]), "area_m2": area,
                    **({"ensuite": True} if item.get("ensuite") is True else {})})

    def kinds(rooms: list[dict[str, Any]]) -> list[str]:
        return sorted(str(r.get("type") or "other") for r in rooms if r.get("type") != "hallway")

    return out if kinds(out) == kinds(rooms_in) else []


def _merge_hallways(rooms_in: list[dict[str, Any]], house_area: float) -> list[dict[str, Any]]:
    """Un seul couloir, de surface bornée, à la place de ses segments.

    Sans programme, chaque segment issu d'un premier tracé devenait une pièce cible : un couloir de
    31 m² en cinq morceaux.
    """
    halls = [r for r in rooms_in if r.get("type") == "hallway"]
    if len(halls) <= 1:
        return rooms_in
    total = sum(float(r.get("area_m2") or _poly_area(r.get("polygon") or [])) for r in halls)
    merged = {**halls[0], "area_m2": min(total, HALLWAY_SHARE_CAP * house_area), "polygon": []}
    out: list[dict[str, Any]] = []
    for room in rooms_in:
        if room.get("type") != "hallway":
            out.append(room)
        elif room is halls[0]:
            out.append(merged)
    return out


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
            # These are minimum widths, not replacements for wider vehicle doors.
            item["width_m"] = max(entry if outer else inner, float(item.get("width_m") or 0))
        out.append(item)
    _ = (width, depth)
    return out


def adapt(payload: dict[str, Any]) -> dict[str, Any]:
    plan = dict(payload.get("plan_document") or {})
    parcel = dict(payload.get("parcel") or {})
    rules = {**DEFAULT_RULES, **(payload.get("rules") or {})}
    bounds = (plan.get("floor") or {}).get("bounds") or {}
    resolved = resolve_parcel(parcel, bounds, rules)
    grid, min_side, setback = resolved.grid_m, resolved.min_side_m, resolved.setback_m
    lot_w, lot_d = resolved.width_m, resolved.depth_m
    house_w, house_d = resolved.buildable_width_m, resolved.buildable_depth_m
    height = float(rules.get("height_m") or 2.7)

    rooms_in = [r for r in (plan.get("rooms") or []) if (r.get("polygon") or r.get("type"))]
    if not rooms_in:
        raise ValueError("plan sans pièces : générez un plan avant d’adapter")

    program = _usable_program(plan, rooms_in)
    if program:
        rooms_in = program
    else:
        rooms_in = _merge_hallways(rooms_in, house_w * house_d)

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
            **({"ensuite": True} if room.get("ensuite") is True else {}),
        }
        work.append(item)
        spec_rooms.append({"type": typ, "area_m2": area, "count": 1})

    # `optimize_rooms` re-pave tout depuis les types et les aires : il ignore les
    # polygones du plan reçu. Sans le descripteur de variante, l'adaptation
    # effacerait donc le parti choisi à la génération. Il est relu ici, validé
    # (le document vient d'un appelant libre), et réécrit dans le plan produit.
    variant = normalize_variant(plan.get("layout"))
    try:
        packed = optimize_rooms(
            work, house_w, house_d, {"rooms": spec_rooms},
            grid=grid, min_side=min_side, variant=variant,
        )
    except PartiUnavailable:
        # Le parti demandé ne réalise pas ce plan (parcelle étroite, programme dense) : le
        # gabarit classique, lui, en réalise toujours un. On l'utilise, et on n'annonce
        # plus de parti : le plan produit ne prétend pas ce qu'il n'est pas.
        variant = None
        packed = optimize_rooms(
            work, house_w, house_d, {"rooms": spec_rooms}, grid=grid, min_side=min_side,
        )
    if variant is not None:
        # Le parti choisi note l'arrangement retenu : la retouche le retrouvera.
        arrangement = next((r["_arr"] for r in packed if r.get("_arr")), None)
        if arrangement:
            variant = {**variant, "arr": arrangement}
    for room in packed:
        room.pop("_arr", None)
    walls = perimeter_and_internal_walls(packed, house_w, house_d)
    original_openings = default_openings(walls, house_w, house_d, packed)
    openings = apply_opening_rules(original_openings, rules, house_w, house_d)
    openings = fit_generated_windows(walls, openings, packed, original_openings=original_openings)

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
        "furniture": furnish(packed, openings, walls),
    }
    if program:
        doc["program"] = program
    if variant is not None:
        # Absent pour le gabarit classique : le plan reste identique à celui
        # d'avant cette fonctionnalité.
        doc["layout"] = variant
    dimensions = [_dimension_row(r) for r in doc["rooms"]]
    validate_generated_document(doc)
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
