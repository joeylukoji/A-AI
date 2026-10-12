from __future__ import annotations

from typing import Any

from app.plan_openings import default_openings
from app.room_program import expand_rooms

from .furnish import furnish
from .layout_opt import normalize_variant


def _obj(value: Any) -> dict[str, Any]:
    """Sous-objet d'un payload libre : `{}` si ce n'en est pas un.

    `/v1/vectorize` accepte un document non validé : un `{"layout": "x"}`
    faisait remonter un AttributeError — donc un 500 — au lieu d'une entrée
    simplement ignorée.
    """
    return value if isinstance(value, dict) else {}


def _seq(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _program(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Pièces DEMANDÉES (type, nombre, surface), une entrée par pièce.

    `plan_adapt` re-pave le plan : sans ce programme il n'a que les polygones du premier tracé,
    donc reproduit ses déformations (couloir découpé en cinq « pièces » de 30 m², séjour rogné)
    au lieu de viser les surfaces demandées.
    """
    out: list[dict[str, Any]] = []
    for room in expand_rooms(_seq(spec.get("rooms"))):
        out.append(
            {
                "id": str(room["id"]),
                "type": str(room["type"]),
                "name": str(room.get("name") or room["type"]),
                "area_m2": round(float(room["area_m2"]), 1),
                **({"ensuite": True} if room.get("ensuite") else {}),
            }
        )
    return out


def vectorize(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _obj(payload)
    layout = _obj(payload.get("layout"))
    spec = _obj(payload.get("building_spec"))
    constraints = _obj(spec.get("constraints"))
    width = float(layout.get("width") or constraints.get("max_width_m") or 12)
    depth = float(layout.get("depth") or constraints.get("max_depth_m") or 10)
    height = float(layout.get("height_m") or 2.7)

    rooms = [r for r in _seq(layout.get("rooms")) if isinstance(r, dict)]
    walls = [w for w in _seq(layout.get("walls")) if isinstance(w, dict)]
    openings = [
        o
        for o in _seq(layout.get("openings"))
        if isinstance(o, dict) and o.get("wall_id")
    ]
    if not openings and walls:
        openings = default_openings(walls, width, depth, rooms)

    plan = {
        "version": "1.0",
        "units": "m",
        "floor": {
            "level": 0,
            "height_m": height,
            "bounds": {"width": width, "depth": depth},
        },
        "walls": walls,
        "rooms": [
            {
                "id": r.get("id"),
                "name": r.get("name") or r.get("type"),
                "type": r.get("type"),
                "polygon": r.get("polygon") or [],
            }
            for r in rooms
        ],
        "openings": openings,
        "furniture": furnish(rooms, openings, walls),
    }
    program = _program(spec)
    if program:
        plan["program"] = program
    # Le parti choisi à l'implantation voyage avec le plan, pour que l'adaptation
    # et la retouche re-pavent avec le même (cf. `plan_adapt.adapt`).
    preferred_layout = _obj(payload.get("preferred_layout"))
    variant = normalize_variant(preferred_layout or layout.get("variant"))
    if variant is None:
        # Import tardif : `layout_select` charge tout le moteur de partis. Drapeau
        # `LAYOUT_VARIANTS` éteint par défaut : `choose_variant` rend alors None et
        # `shadow` ne fait rien, le plan reste celui d'avant.
        from . import layout_select

        variant = layout_select.choose_variant(constraints)
        layout_select.shadow(layout, spec)
    if variant is not None:
        plan["layout"] = variant
    return {"plan_document": plan}
