"""Place des instances du catalogue 3D dans chaque pièce.

Disposition calquée sur Sweet Home 3D : lits, canapé + fauteuils au salon,
cuisine sans table à manger, voiture au garage.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Empreintes locales (m) — même contrat que services/blender/catalog/catalog.json
CATALOG: dict[str, dict[str, float]] = {
    "chair.dining": {"w": 0.45, "d": 0.50, "h": 0.90},
    "bed.single": {"w": 0.90, "d": 2.00, "h": 0.55},
    "bed.double": {"w": 1.60, "d": 2.00, "h": 0.55},
    "table.dining": {"w": 1.80, "d": 1.00, "h": 0.75},
    "table.coffee": {"w": 1.10, "d": 0.55, "h": 0.40},
    "sofa.2seat": {"w": 1.80, "d": 0.85, "h": 0.80},
    "sofa.lshape": {"w": 2.40, "d": 1.60, "h": 0.80},
    "armchair": {"w": 0.80, "d": 0.80, "h": 0.78},
    "nightstand": {"w": 0.45, "d": 0.40, "h": 0.50},
    "wardrobe": {"w": 1.20, "d": 0.60, "h": 2.00},
    "counter.kitchen": {"w": 2.40, "d": 0.62, "h": 0.90},
    "stove": {"w": 0.60, "d": 0.55, "h": 0.90},
    "desk": {"w": 1.20, "d": 0.60, "h": 0.75},
    "fireplace": {"w": 0.70, "d": 0.55, "h": 1.20},
    "bathtub": {"w": 1.70, "d": 0.75, "h": 0.55},
    "toilet": {"w": 0.48, "d": 0.78, "h": 0.80},
    "sink.basin": {"w": 0.55, "d": 0.42, "h": 0.85},
    "car.sedan": {"w": 4.20, "d": 1.80, "h": 1.45},
    "rug.rect": {"w": 2.20, "d": 1.60, "h": 0.02},
    "plant.pot": {"w": 0.45, "d": 0.45, "h": 0.90},
    "fridge": {"w": 0.65, "d": 0.65, "h": 1.80},
    "tv.console": {"w": 1.60, "d": 0.40, "h": 0.45},
}

_MARGIN = 0.28
_Add = Callable[..., None]


def furnish(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retourne `furniture[]` à coller dans le PlanDocument."""
    rooms = [r for r in rooms if isinstance(r, dict)]
    types = {str(r.get("type") or "") for r in rooms}
    has_dining = "dining" in types
    has_kitchen = "kitchen" in types
    items: list[dict[str, Any]] = []
    n = 0
    for room in rooms:
        placed, n = _place_room(
            room, n, has_dining=has_dining, has_kitchen=has_kitchen
        )
        items.extend(placed)
    return items


def _place_room(
    room: dict[str, Any], n: int, *, has_dining: bool, has_kitchen: bool
) -> tuple[list[dict[str, Any]], int]:
    box = _bbox(room.get("polygon") or [])
    if box is None:
        return [], n
    typ = str(room.get("type") or "")
    inset = 0.10 if typ in {"wc", "bathroom"} else _MARGIN
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
    w, h = x1 - x0, y1 - y0
    if w < 0.55 or h < 0.55:
        return [], n
    _ = (has_dining, has_kitchen)
    rid = str(room.get("id") or "")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    out: list[dict[str, Any]] = []

    def add(
        catalog_id: str,
        px: float,
        py: float,
        rot: float = 0.0,
        size: dict[str, float] | None = None,
        *,
        required: bool = False,
    ) -> None:
        nonlocal n
        spec = dict(CATALOG[catalog_id])
        if size:
            spec.update(size)
        aw, ad = _world_footprint(spec["w"], spec["d"], rot)
        if not _inside(x0, y0, x1, y1, px, py, aw, ad):
            if not required:
                return
            px = (x0 + x1) / 2 if x1 - x0 < aw else min(max(px, x0 + aw / 2), x1 - aw / 2)
            py = (y0 + y1) / 2 if y1 - y0 < ad else min(max(py, y0 + ad / 2), y1 - ad / 2)
        n += 1
        out.append({
            "id": f"f{n}",
            "catalog_id": catalog_id,
            "room_id": rid,
            "position": {"x": round(px, 3), "y": round(py, 3)},
            "rotation_deg": rot,
            "size_m": {"w": spec["w"], "d": spec["d"], "h": spec["h"]},
        })

    if typ == "bedroom":
        # Un seul lit par chambre (double si ça rentre, sinon simple).
        bed_id = "bed.double" if w >= 2.2 and h >= 2.3 else "bed.single"
        bed = CATALOG[bed_id]
        add(bed_id, cx, y0 + bed["d"] / 2, 0, required=True)
        ns = CATALOG["nightstand"]
        add("nightstand", cx - bed["w"] / 2 - ns["w"] / 2 - 0.04, y0 + ns["d"] / 2, 0)
        add("nightstand", cx + bed["w"] / 2 + ns["w"] / 2 + 0.04, y0 + ns["d"] / 2, 0)
        if h > 3.4:
            wd = CATALOG["wardrobe"]
            add("wardrobe", x0 + wd["w"] / 2, y1 - wd["d"] / 2, 0)
    elif typ == "dining":
        _dining_set(add, cx, cy, w, n_chairs=6 if w >= 3.4 else 4)
    elif typ == "living":
        sofa_id = "sofa.lshape" if w >= 3.8 and h >= 3.4 else "sofa.2seat"
        sofa = CATALOG[sofa_id]
        sx = x1 - sofa["w"] / 2 - 0.05
        sy = y1 - sofa["d"] / 2
        add(
            "rug.rect",
            sx - 0.15,
            sy - 0.35,
            0,
            {"w": min(2.6, sofa["w"] + 0.7), "d": min(2.0, sofa["d"] + 1.1), "h": 0.02},
        )
        add(sofa_id, sx, sy, 0)
        add("table.coffee", sx - 0.1, sy - sofa["d"] / 2 - 0.42, 0)
        add("tv.console", cx, y0 + CATALOG["tv.console"]["d"] / 2 + 0.02, 0)
        add("fireplace", x0 + CATALOG["fireplace"]["d"] / 2 + 0.02, cy, 90)
        add("plant.pot", x0 + 0.3, y1 - 0.3, 0)
        _living_armchairs(add, x0, x1, sx, sy, sofa)
    elif typ == "kitchen":
        counter = CATALOG["counter.kitchen"]
        length = min(counter["w"], max(1.2, w - 0.85))
        add(
            "counter.kitchen",
            x0 + length / 2,
            y0 + counter["d"] / 2,
            0,
            {"w": length, "d": counter["d"], "h": counter["h"]},
        )
        add("stove", x0 + min(w * 0.42, length - 0.4), y0 + 0.32, 0)
        add("fridge", x1 - CATALOG["fridge"]["w"] / 2, y0 + CATALOG["fridge"]["d"] / 2, 0)
        if h >= 3.4:
            add(
                "counter.kitchen",
                x0 + counter["d"] / 2,
                y0 + min(h * 0.55, 2.4),
                90,
                {"w": min(2.2, h * 0.55), "d": counter["d"], "h": counter["h"]},
            )
    elif typ == "office":
        add("desk", x0 + 0.85, y0 + 0.4, 0)
        add("chair.dining", x0 + 0.85, y0 + 1.05, 180)
    elif typ in {"bathroom", "wc"}:
        tw, td = CATALOG["toilet"]["w"], CATALOG["toilet"]["d"]
        add("toilet", x0 + tw / 2 + 0.02, y0 + td / 2 + 0.02, 0, required=True)
        add("sink.basin", x1 - 0.32, y0 + 0.32, 0, required=typ == "wc")
        if typ == "bathroom":
            bath = CATALOG["bathtub"]
            before = len(out)
            add("bathtub", x1 - bath["w"] / 2 - 0.02, y1 - bath["d"] / 2, 0)
            if len(out) == before:
                add("bathtub", x1 - bath["d"] / 2, y1 - bath["w"] / 2, 90)
    elif typ == "garage":
        car = CATALOG["car.sedan"]
        if h >= car["w"] + 0.3:
            add("car.sedan", cx, cy, 90)
        else:
            add("car.sedan", cx, cy, 0)

    return out, n


def _living_armchairs(
    add: _Add, x0: float, x1: float, sx: float, sy: float, sofa: dict[str, float]
) -> None:
    """Deux fauteuils autour de la table basse, jamais une table à manger."""
    arm = CATALOG["armchair"]
    ay = sy - sofa["d"] / 2 - 0.42
    left = max(x0 + arm["w"] / 2 + 0.02, sx - sofa["w"] / 2 + 0.15)
    right = min(x1 - arm["w"] / 2 - 0.02, sx + sofa["w"] / 2 - 0.15)
    if right - left < arm["w"] + 0.5:
        left = max(x0 + arm["w"] / 2 + 0.02, sx - 0.95)
        right = min(x1 - arm["w"] / 2 - 0.02, sx + 0.95)
    add("armchair", left, ay, 0)
    add("armchair", right, ay, 0)


def _dining_set(add: _Add, cx: float, cy: float, w: float, n_chairs: int) -> None:
    table = CATALOG["table.dining"]
    chair = CATALOG["chair.dining"]
    add("table.dining", cx, cy, 0)
    gap = 0.10
    along_y = table["d"] / 2 + chair["d"] / 2 + gap
    along_x = table["w"] / 2 + chair["d"] / 2 + gap
    add("chair.dining", cx - 0.4, cy - along_y, 0)
    add("chair.dining", cx + 0.4, cy - along_y, 0)
    add("chair.dining", cx - 0.4, cy + along_y, 180)
    add("chair.dining", cx + 0.4, cy + along_y, 180)
    if n_chairs >= 6 and w >= 2.8:
        add("chair.dining", cx - along_x, cy, 90)
        add("chair.dining", cx + along_x, cy, 270)


def _bbox(poly: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    """Emprise du polygone, ou None s'il a moins de 3 sommets exploitables.

    Le `layout` de /v1/vectorize n'est pas validé : un sommet sans `x` faisait
    remonter KeyError en 500.
    """
    pts: list[tuple[float, float]] = []
    for p in poly:
        if not isinstance(p, dict):
            continue
        try:
            pts.append((float(p["x"]), float(p["y"])))
        except (KeyError, TypeError, ValueError):
            continue
    if len(pts) < 3:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _world_footprint(w: float, d: float, rot: float) -> tuple[float, float]:
    r = abs(rot) % 180
    if 45 <= r <= 135:
        return d, w
    return w, d


def _inside(
    x0: float, y0: float, x1: float, y1: float, px: float, py: float, w: float, d: float
) -> bool:
    return (
        px - w / 2 >= x0 - 1e-6
        and px + w / 2 <= x1 + 1e-6
        and py - d / 2 >= y0 - 1e-6
        and py + d / 2 <= y1 + 1e-6
    )
