from __future__ import annotations

from typing import Any

from .furnish import furnish


def vectorize(payload: dict[str, Any]) -> dict[str, Any]:
    layout = payload.get("layout") or {}
    spec = payload.get("building_spec") or {}
    width = float(layout.get("width") or (spec.get("constraints") or {}).get("max_width_m") or 12)
    depth = float(layout.get("depth") or (spec.get("constraints") or {}).get("max_depth_m") or 10)
    height = float(layout.get("height_m") or 2.7)

    rooms = layout.get("rooms") or []
    walls = layout.get("walls") or []
    openings = [o for o in (layout.get("openings") or []) if o.get("wall_id")]
    if not openings and walls:
        from .diffusion import default_openings

        openings = default_openings(walls, width, depth)

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
        "furniture": furnish(rooms),
    }
    return {"plan_document": plan}
