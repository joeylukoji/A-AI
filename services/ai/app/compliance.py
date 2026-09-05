"""Score de conformité indicatif (heuristiques FR, pas un contrôle légal)."""
from __future__ import annotations

from typing import Any


HABITABLE = {"living", "bedroom", "dining", "office"}
TOL = 0.15
MIN_SEAM = 0.55


def _area(poly: list[dict[str, float]]) -> float:
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


def _sides(poly: list[dict[str, float]]) -> tuple[float, float]:
    x0, y0, x1, y1 = _bbox(poly)
    return x1 - x0, y1 - y0


def _overlap(a: list[dict[str, float]], b: list[dict[str, float]]) -> float:
    ax0, ay0, ax1, ay1 = _bbox(a)
    bx0, by0, bx1, by1 = _bbox(b)
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    return ix * iy


def _share_edge(a: list[dict[str, float]], b: list[dict[str, float]]) -> bool:
    ax0, ay0, ax1, ay1 = _bbox(a)
    bx0, by0, bx1, by1 = _bbox(b)
    y_ov = min(ay1, by1) - max(ay0, by0)
    x_ov = min(ax1, bx1) - max(ax0, bx0)
    x_touch = abs(ax1 - bx0) <= TOL or abs(bx1 - ax0) <= TOL
    y_touch = abs(ay1 - by0) <= TOL or abs(by1 - ay0) <= TOL
    return (x_touch and y_ov >= MIN_SEAM) or (y_touch and x_ov >= MIN_SEAM)


def _connected(rooms: list[dict[str, Any]]) -> list[str]:
    """Pièces hors graphe séjour/couloir (adjacence transitive)."""
    if not rooms:
        return []
    hubs = [i for i, r in enumerate(rooms) if r.get("type") in {"living", "hallway"}]
    if not hubs:
        hubs = list(range(len(rooms)))
    seen = set(hubs)
    stack = list(hubs)
    while stack:
        i = stack.pop()
        for j, other in enumerate(rooms):
            if j in seen:
                continue
            if _share_edge(rooms[i]["polygon"], other["polygon"]):
                seen.add(j)
                stack.append(j)
    return [str(r.get("name") or r.get("type")) for i, r in enumerate(rooms) if i not in seen]


def _envelope(rooms: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    boxes = [_bbox(r["polygon"]) for r in rooms if len(r.get("polygon") or []) >= 3]
    if not boxes:
        return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def _touches_outer(
    poly: list[dict[str, float]],
    width: float,
    depth: float,
    env: tuple[float, float, float, float] | None = None,
) -> bool:
    x0, y0, x1, y1 = _bbox(poly)
    if env:
        ex0, ey0, ex1, ey1 = env
        if x0 <= ex0 + TOL or y0 <= ey0 + TOL or x1 >= ex1 - TOL or y1 >= ey1 - TOL:
            return True
    return x0 <= TOL or y0 <= TOL or (width and x1 >= width - TOL) or (depth and y1 >= depth - TOL)


def _is_outer_wall(wall: dict[str, Any] | None, width: float, depth: float) -> bool:
    if not wall or "a" not in wall or "b" not in wall:
        return False
    xs = {float(wall["a"]["x"]), float(wall["b"]["x"])}
    ys = {float(wall["a"]["y"]), float(wall["b"]["y"])}
    return (
        max(xs) <= TOL
        or min(xs) >= width - TOL
        or max(ys) <= TOL
        or min(ys) >= depth - TOL
        or str(wall.get("id", "")).startswith("w_outer")
    )


def evaluate(plan: dict[str, Any]) -> dict[str, Any]:
    rooms = [r for r in (plan.get("rooms") or []) if len(r.get("polygon") or []) >= 3]
    walls = plan.get("walls") or []
    openings = plan.get("openings") or []
    floor = plan.get("floor") or {}
    bounds = floor.get("bounds") or {}
    width = float(bounds.get("width") or 0)
    depth = float(bounds.get("depth") or 0)
    height = float(floor.get("height_m") or 0)
    by_id = {w.get("id"): w for w in walls}

    def check(key: str, label: str, ok: bool, weight: int, detail: str = "") -> dict[str, Any]:
        return {"key": key, "label": label, "ok": ok, "weight": weight, "detail": detail}

    checks: list[dict[str, Any]] = []
    living = [r for r in rooms if r.get("type") == "living"]
    beds = [r for r in rooms if r.get("type") == "bedroom"]
    kitchens = [r for r in rooms if r.get("type") == "kitchen"]
    baths = [r for r in rooms if r.get("type") == "bathroom"]
    halls = [r for r in rooms if r.get("type") == "hallway"]
    habit = [r for r in rooms if r.get("type") in HABITABLE]

    checks.append(check("height", "Hauteur sous plafond ≥ 2,20 m", height >= 2.20, 8, f"{height:.2f} m"))
    checks.append(check("living", "Séjour présent", bool(living), 8))
    liv_area = _area(living[0]["polygon"]) if living else 0.0
    checks.append(check("living_area", "Séjour ≥ 9 m²", liv_area >= 9, 10, f"{liv_area:.1f} m²"))
    small_beds = [r for r in beds if _area(r["polygon"]) < 9]
    checks.append(check("bedrooms", "Chaque chambre ≥ 9 m²", bool(beds) and not small_beds, 10,
                        "ok" if beds and not small_beds else ("aucune chambre" if not beds else f"{len(small_beds)} trop petite(s)")))
    checks.append(check("kitchen", "Cuisine présente", bool(kitchens), 6))
    checks.append(check("bathroom", "Salle de bain présente", bool(baths), 6))

    env = _envelope(rooms)
    no_facade = [r.get("name") or r.get("type") for r in habit if not _touches_outer(r["polygon"], width, depth, env)]
    checks.append(check("facade", "Pièces habitables sur façade", not no_facade and bool(habit), 12,
                        "ok" if not no_facade else ", ".join(str(x) for x in no_facade)))

    windows = [o for o in openings if o.get("type") == "window"]
    checks.append(check("window", "Au moins une fenêtre", bool(windows), 6))
    outer_doors = [
        o for o in openings
        if o.get("type") == "door" and _is_outer_wall(by_id.get(o.get("wall_id")) or {}, width, depth)
    ]
    checks.append(check("entry", "Porte d’entrée sur façade", bool(outer_doors), 6))

    isolated = _connected(rooms)
    checks.append(check("access", "Pièces accessibles (bord partagé)", not isolated, 10,
                        "ok" if not isolated else ", ".join(isolated)))

    narrow_hall = [r for r in halls if min(_sides(r["polygon"])) < 0.90]
    checks.append(check("hall", "Couloir ≥ 0,90 m si présent", not narrow_hall, 6,
                        "pas de couloir" if not halls else ("ok" if not narrow_hall else "trop étroit")))

    thin_doors = [o for o in openings if o.get("type") == "door" and float(o.get("width_m") or 0) < 0.80]
    checks.append(check("doors", "Portes ≥ 0,80 m", bool(openings) and not thin_doors, 4))

    ortho = True
    for w in walls:
        ax, ay, bx, by = float(w["a"]["x"]), float(w["a"]["y"]), float(w["b"]["x"]), float(w["b"]["y"])
        if abs(ax - bx) > 1e-6 and abs(ay - by) > 1e-6:
            ortho = False
            break
    checks.append(check("ortho", "Murs orthogonaux", bool(walls) and ortho, 6))

    overlaps = 0.0
    for i, a in enumerate(rooms):
        for b in rooms[i + 1 :]:
            overlaps += _overlap(a["polygon"], b["polygon"])
    checks.append(check("overlap", "Pas de chevauchement", overlaps < 0.25, 8, f"{overlaps:.2f} m²"))

    oob = False
    if width and depth:
        for r in rooms:
            x0, y0, x1, y1 = _bbox(r["polygon"])
            if x0 < -TOL or y0 < -TOL or x1 > width + TOL or y1 > depth + TOL:
                oob = True
    checks.append(check("bounds", "Pièces dans l’emprise", bool(rooms) and not oob, 4))

    total_w = sum(c["weight"] for c in checks)
    got = sum(c["weight"] for c in checks if c["ok"])
    score = int(round(100 * got / total_w)) if total_w else 0
    if score >= 80:
        grade = "A"
    elif score >= 65:
        grade = "B"
    elif score >= 50:
        grade = "C"
    elif score >= 35:
        grade = "D"
    else:
        grade = "E"
    return {
        "score": score,
        "grade": grade,
        "passed": sum(1 for c in checks if c["ok"]),
        "total": len(checks),
        "checks": checks,
        "disclaimer": "Indicatif (heuristiques d’habitabilité). Pas un contrôle réglementaire ni un permis.",
    }
