"""Score de conformité indicatif (heuristiques FR, pas un contrôle légal)."""
from __future__ import annotations

from typing import Any

from .layout_opt import sanitary_violations


HABITABLE = {"living", "bedroom", "dining", "office"}
TOL = 0.15
MIN_SEAM = 0.55


def _pt(p: Any) -> tuple[float, float] | None:
    """(x, y) d'un sommet, ou None si le point est malformé.

    `evaluate` tourne sur le `plan_document` brut envoyé à /v1/adapt : les
    sommets ne sont pas validés en amont, un `{"x": null}` ou un entier à la
    place d'un dict faisait remonter KeyError/TypeError en 500.
    """
    if not isinstance(p, dict):
        return None
    try:
        return float(p["x"]), float(p["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _points(poly: Any) -> list[tuple[float, float]]:
    if not isinstance(poly, list):
        return []
    pts = [_pt(p) for p in poly]
    return [p for p in pts if p is not None]


def _area(poly: list[dict[str, float]]) -> float:
    pts = _points(poly)
    if len(pts) < 3:
        return 0.0
    acc = 0.0
    for i, (px, py) in enumerate(pts):
        qx, qy = pts[(i + 1) % len(pts)]
        acc += px * qy - qx * py
    return abs(acc) / 2


def _bbox(poly: list[dict[str, float]]) -> tuple[float, float, float, float]:
    pts = _points(poly)
    if not pts:
        return 0.0, 0.0, 0.0, 0.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
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
    return bool(
        x0 <= TOL
        or y0 <= TOL
        or (width > 0 and x1 >= width - TOL)
        or (depth > 0 and y1 >= depth - TOL)
    )


def _is_outer_wall(wall: dict[str, Any] | None, width: float, depth: float) -> bool:
    if not isinstance(wall, dict):
        return False
    a, b = _pt(wall.get("a")), _pt(wall.get("b"))
    if a is None or b is None:
        return False
    xs = {a[0], b[0]}
    ys = {a[1], b[1]}
    return (
        max(xs) <= TOL
        or min(xs) >= width - TOL
        or max(ys) <= TOL
        or min(ys) >= depth - TOL
        or str(wall.get("id", "")).startswith("w_outer")
    )


def evaluate(plan: dict[str, Any]) -> dict[str, Any]:
    # Entrées non validées (plan_document libre côté /v1/adapt) : on ignore
    # silencieusement les éléments malformés plutôt que de planter.
    rooms = [
        r for r in (plan.get("rooms") or [])
        if isinstance(r, dict) and len(_points(r.get("polygon"))) >= 3
    ]
    walls = [w for w in (plan.get("walls") or []) if isinstance(w, dict)]
    openings = [o for o in (plan.get("openings") or []) if isinstance(o, dict)]
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

    issues = sanitary_violations(rooms)
    checks.append(check(
        "wc_kitchen",
        "WC séparé de la cuisine / salle à manger",
        "wc_kitchen" not in issues,
        10,
        "ok" if "wc_kitchen" not in issues else "mur commun interdit (RSD / logement décent)",
    ))
    checks.append(check(
        "kitchen_bath",
        "Salle de bain séparée de la cuisine / salle à manger",
        "kitchen_bath" not in issues,
        8,
        "ok" if "kitchen_bath" not in issues else "mur commun interdit (pièces humides / cuisine)",
    ))
    checks.append(check(
        "bedroom_living",
        "Chambres séparées du séjour par un couloir",
        "bedroom_living" not in issues,
        10,
        "ok" if "bedroom_living" not in issues else "chambre collée au séjour",
    ))
    need_hall = bool(beds)
    hall_ok = (not need_hall) or (bool(halls) and "bedroom_hall" not in issues and "wc_hall" not in issues)
    guest_ok = (
        "wc_hall" not in issues
        and "wc_bedroom" not in issues
        and "wc_kitchen" not in issues
        and "kitchen_bath" not in issues
    )
    checks.append(check(
        "bedroom_hall",
        "Chambres et WC desservis par le couloir",
        hall_ok,
        8,
        "ok" if hall_ok else "accès hors circulation",
    ))
    checks.append(check(
        "wc_guest",
        "WC invités sans traverser chambre ni cuisine",
        guest_ok,
        8,
        "ok" if guest_ok else "WC accessible seulement via une pièce privée",
    ))

    ortho = True
    checked_walls = 0
    for w in walls:
        a, b = _pt(w.get("a")), _pt(w.get("b"))
        if a is None or b is None:
            continue  # mur malformé : ignoré, pas d'exception
        checked_walls += 1
        if abs(a[0] - b[0]) > 1e-6 and abs(a[1] - b[1]) > 1e-6:
            ortho = False
            break
    checks.append(check("ortho", "Murs orthogonaux", bool(checked_walls) and ortho, 6))

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
