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


Zone = tuple[float, float, float, float]
MAX_LEAF = 1.3      # au-delà, c'est une porte de garage : elle n'a pas de battant
PASSAGE = 0.8       # profondeur réservée devant une porte, du côté où elle ne s'ouvre pas
# Seuls ces gros meubles doivent laisser le passage : dans une petite pièce, exiger 80 cm devant
# chaque porte pour tout le mobilier priverait la chambre de son armoire.
BULKY = frozenset({"sofa.2seat", "sofa.lshape", "table.dining"})


def door_zones(openings: list[dict[str, Any]] | None, walls: list[dict[str, Any]] | None) -> list[Zone]:
    """Carrés de débattement des portes (x0, y0, x1, y1) : rien de facultatif ne doit s'y trouver.

    Le battant tourne autour de la charnière (début de l'ouverture sur le mur) et balaie un quart
    de disque du côté de la normale (-uy, ux) : c'est le sens dessiné par l'éditeur. La zone est le
    carré qui contient ce quart de disque. Les portes de garage (plus larges que `MAX_LEAF`) n'ont
    pas de battant : elles ne réservent rien. Le passage de l'autre côté est dans `door_passages`.
    """
    by_id = {str(w.get("id")): w for w in walls or [] if isinstance(w, dict)}
    zones: list[Zone] = []
    for op in openings or []:
        if not isinstance(op, dict) or op.get("type") != "door":
            continue
        wall = by_id.get(str(op.get("wall_id")))
        try:
            ax, ay = float(wall["a"]["x"]), float(wall["a"]["y"])  # type: ignore[index]
            bx, by = float(wall["b"]["x"]), float(wall["b"]["y"])  # type: ignore[index]
            offset, width = float(op.get("offset_m") or 0), float(op.get("width_m") or 0.9)
        except (TypeError, ValueError, KeyError):
            continue
        length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        if length < 1e-6 or width > MAX_LEAF:
            continue
        ux, uy = (bx - ax) / length, (by - ay) / length
        p0 = (ax + ux * offset, ay + uy * offset)
        p1 = (p0[0] + ux * width, p0[1] + uy * width)
        r = width + 0.05
        nx, ny = -uy, ux
        corners = [p0, (p0[0] + ux * r, p0[1] + uy * r), (p0[0] + nx * r, p0[1] + ny * r),
                   (p0[0] + (ux + nx) * r, p0[1] + (uy + ny) * r)]
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        zones.append((min(xs), min(ys), max(xs), max(ys)))
    return zones


def door_passages(openings: list[dict[str, Any]] | None, walls: list[dict[str, Any]] | None) -> list[Zone]:
    """Passage devant chaque porte, du côté où elle ne s'ouvre pas : un canapé collé la condamnerait."""
    by_id = {str(w.get("id")): w for w in walls or [] if isinstance(w, dict)}
    out: list[Zone] = []
    for op in openings or []:
        if not isinstance(op, dict) or op.get("type") != "door":
            continue
        wall = by_id.get(str(op.get("wall_id")))
        try:
            ax, ay = float(wall["a"]["x"]), float(wall["a"]["y"])  # type: ignore[index]
            bx, by = float(wall["b"]["x"]), float(wall["b"]["y"])  # type: ignore[index]
            offset, width = float(op.get("offset_m") or 0), float(op.get("width_m") or 0.9)
        except (TypeError, ValueError, KeyError):
            continue
        length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        if length < 1e-6 or width > MAX_LEAF:
            continue
        ux, uy = (bx - ax) / length, (by - ay) / length
        p0 = (ax + ux * offset, ay + uy * offset)
        p1 = (p0[0] + ux * width, p0[1] + uy * width)
        back = [p0, p1, (p0[0] + uy * PASSAGE, p0[1] - ux * PASSAGE), (p1[0] + uy * PASSAGE, p1[1] - ux * PASSAGE)]
        out.append((min(c[0] for c in back), min(c[1] for c in back), max(c[0] for c in back), max(c[1] for c in back)))
    return out


def furnish(
    rooms: list[dict[str, Any]],
    openings: list[dict[str, Any]] | None = None,
    walls: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Retourne `furniture[]` à coller dans le PlanDocument.

    Avec `openings` et `walls`, les meubles facultatifs évitent le débattement des portes.
    """
    zones = door_zones(openings, walls)
    passages = door_passages(openings, walls)
    rooms = [r for r in rooms if isinstance(r, dict)]
    types = {str(r.get("type") or "") for r in rooms}
    has_dining = "dining" in types
    has_kitchen = "kitchen" in types
    items: list[dict[str, Any]] = []
    n = 0
    for room in rooms:
        placed, n = _place_room(
            room, n, has_dining=has_dining, has_kitchen=has_kitchen, zones=zones, passages=passages
        )
        items.extend(placed)
    return items


def _place_room(
    room: dict[str, Any], n: int, *, has_dining: bool, has_kitchen: bool, zones: list[Zone] | tuple = (),
    passages: list[Zone] | tuple = ()
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

    def blocked(px: float, py: float, aw: float, ad: float, catalog_id: str = "") -> bool:
        areas = list(zones) + (list(passages) if catalog_id in BULKY else [])
        return any(
            px - aw / 2 < zx1 - 1e-6 and px + aw / 2 > zx0 + 1e-6
            and py - ad / 2 < zy1 - 1e-6 and py + ad / 2 > zy0 + 1e-6
            for zx0, zy0, zx1, zy1 in areas
        )

    def fits(catalog_id: str, px: float, py: float, rot: float = 0.0, *, ignore_zones: bool = False) -> bool:
        aw, ad = _world_footprint(CATALOG[catalog_id]["w"], CATALOG[catalog_id]["d"], rot)
        if not _inside(x0, y0, x1, y1, px, py, aw, ad):
            return False
        if not ignore_zones and blocked(px, py, aw, ad, catalog_id):
            return False
        for other in out:                        # ni sur un meuble déjà posé (le tapis se traverse)
            if other["catalog_id"].startswith("rug"):
                continue
            ow, od = _world_footprint(other["size_m"]["w"], other["size_m"]["d"], other["rotation_deg"])
            if (abs(px - other["position"]["x"]) < (aw + ow) / 2 - 1e-6
                    and abs(py - other["position"]["y"]) < (ad + od) / 2 - 1e-6):
                return False
        return True

    def along_walls(catalog_id: str, order: str, step: float = 0.25) -> list[tuple[float, float, float]]:
        """Emplacements contre les murs (N, S, W, E dans l'ordre demandé), dos au mur, coins d'abord."""
        cw, cd = CATALOG[catalog_id]["w"], CATALOG[catalog_id]["d"]
        out_c: list[tuple[float, float, float]] = []
        for side in order:
            if side in "NS":
                span, y = (x1 - x0) - cw, (y0 + cd / 2 if side == "N" else y1 - cd / 2)
                rot = 0.0 if side == "N" else 180.0
                if span < -1e-6:
                    continue
                for k in range(int(span / step) + 1):
                    out_c.append((x0 + cw / 2 + k * step, y, rot))
                    if k * step + 1e-6 < span:
                        out_c.append((x1 - cw / 2 - k * step, y, rot))
                out_c.append((x1 - cw / 2, y, rot))
            else:
                span, x = (y1 - y0) - cw, (x0 + cd / 2 if side == "W" else x1 - cd / 2)
                rot = 270.0 if side == "W" else 90.0
                if span < -1e-6:
                    continue
                for k in range(int(span / step) + 1):
                    out_c.append((x, y0 + cw / 2 + k * step, rot))
                    out_c.append((x, y1 - cw / 2 - k * step, rot))
        return out_c

    def add_first(catalog_id: str, candidates: list[tuple[float, float, float]], *, required: bool = False,
                  essential: bool = True) -> None:
        """Le premier emplacement libre ; à défaut, le premier (si `required`, il est ramené dans la pièce)."""
        for px, py, rot in candidates:
            if fits(catalog_id, px, py, rot):
                add(catalog_id, px, py, rot, required=required)
                return
        # Aucun emplacement libre de battant : un meuble essentiel ne disparaît pas pour autant,
        # un meuble d'agrément (armoire) est simplement omis.
        for px, py, rot in candidates if (essential or required) else ():
            if fits(catalog_id, px, py, rot, ignore_zones=True):
                add(catalog_id, px, py, rot, required=required, force=True)
                return
        if required:
            px, py, rot = candidates[0]
            add(catalog_id, px, py, rot, required=True)

    def add(
        catalog_id: str,
        px: float,
        py: float,
        rot: float = 0.0,
        size: dict[str, float] | None = None,
        *,
        required: bool = False,
        force: bool = False,
    ) -> None:
        nonlocal n
        spec = dict(CATALOG[catalog_id])
        if size:
            spec.update(size)
        aw, ad = _world_footprint(spec["w"], spec["d"], rot)
        if not required and not force and blocked(px, py, aw, ad, catalog_id):
            return                      # facultatif : on n'encombre pas le battant d'une porte
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
        _bedroom(add, add_first, fits, along_walls, x0, y0, x1, y1)
    elif typ == "dining":
        _dining_set(add, cx, cy, w, n_chairs=6 if w >= 3.4 else 4)
    elif typ == "living":
        preferred = "sofa.lshape" if w >= 3.8 and h >= 3.4 else "sofa.2seat"
        # Contre le mur sud, du côté qui ne gêne aucune porte (l'entrée donne souvent sur le séjour) ;
        # le deux places si l'angle ne tient nulle part sans gêner ; à défaut on tolère un battant
        # plutôt que de perdre le canapé.
        sofa_id, sx, sy = preferred, None, y1 - CATALOG[preferred]["d"] / 2
        for candidate in dict.fromkeys((preferred, "sofa.2seat")):
            cd = CATALOG[candidate]
            row = [(x1 - cd["w"] / 2 - 0.05, 0.0), (x0 + cd["w"] / 2 + 0.05, 0.0), (cx, 0.0)]
            row += [(c[0], 0.0) for c in along_walls(candidate, "S")]
            found = next((c[0] for c in row if fits(candidate, c[0], y1 - cd["d"] / 2)), None)
            if found is not None:
                sofa_id, sx, sy = candidate, found, y1 - cd["d"] / 2
                break
        sofa = CATALOG[sofa_id]
        if sx is None:
            sx = x1 - sofa["w"] / 2 - 0.05
        add(
            "rug.rect",
            sx - 0.15,
            sy - 0.35,
            0,
            {"w": min(2.6, sofa["w"] + 0.7), "d": min(2.0, sofa["d"] + 1.1), "h": 0.02},
        )
        add(sofa_id, sx, sy, 0, force=True)
        add("table.coffee", sx - 0.1, sy - sofa["d"] / 2 - 0.42, 0)
        tv = CATALOG["tv.console"]
        ty = y0 + tv["d"] / 2 + 0.02
        add_first("tv.console", [(cx, ty, 0), (x0 + tv["w"] / 2 + 0.1, ty, 0), (x1 - tv["w"] / 2 - 0.1, ty, 0)])
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
            force=True,                      # essentiel : jamais omis à cause d'une porte
        )
        add("stove", x0 + min(w * 0.42, length - 0.4), y0 + 0.32, 0, force=True)
        fr = CATALOG["fridge"]
        add_first("fridge", [(x1 - fr["w"] / 2, y0 + fr["d"] / 2, 0), (x1 - fr["w"] / 2, y1 - fr["d"] / 2, 180),
                             (x0 + fr["w"] / 2, y1 - fr["d"] / 2, 180)])
        if h >= 3.4:
            add(
                "counter.kitchen",
                x0 + counter["d"] / 2,
                y0 + min(h * 0.55, 2.4),
                90,
                {"w": min(2.2, h * 0.55), "d": counter["d"], "h": counter["h"]},
                force=True,
            )
    elif typ == "office":
        add("desk", x0 + 0.85, y0 + 0.4, 0, force=True)
        add("chair.dining", x0 + 0.85, y0 + 1.05, 180, force=True)
    elif typ in {"bathroom", "wc"}:
        tw, td = CATALOG["toilet"]["w"], CATALOG["toilet"]["d"]
        first = [(x0 + tw / 2 + 0.02, y0 + td / 2 + 0.02, 0.0)]
        add_first("toilet", first + along_walls("toilet", "NSWE"), required=True)
        add_first("sink.basin", [(x1 - 0.32, y0 + 0.32, 0.0)] + along_walls("sink.basin", "NESW"), required=typ == "wc")
        if typ == "bathroom":
            add_first("bathtub", along_walls("bathtub", "SNWE"))
    elif typ == "garage":
        car = CATALOG["car.sedan"]
        if h >= car["w"] + 0.3:
            add("car.sedan", cx, cy, 90, force=True)
        else:
            add("car.sedan", cx, cy, 0, force=True)

    return out, n


def _bedroom(add: _Add, add_first: Callable[..., None], fits: Callable[..., bool],
             along_walls: Callable[..., list[tuple[float, float, float]]],
             x0: float, y0: float, x1: float, y1: float) -> None:
    """Lit (double si possible, dans le sens de la pièce), chevets et armoire.

    Quatre orientations, tête au nord, à l'ouest, à l'est ou au sud : on garde la première où le lit
    tient sans gêner le battant d'une porte. La rotation suit le dessin 2D (0 = tête vers le nord).
    """
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ns, wd = CATALOG["nightstand"], CATALOG["wardrobe"]
    # (tête, rotation) et, pour un lit de largeur `bw` et de longueur `bl`, position du lit
    def placement(head: str, bl: float) -> tuple[float, float, float]:
        return {"N": (cx, y0 + bl / 2, 0.0), "S": (cx, y1 - bl / 2, 180.0),
                "W": (x0 + bl / 2, cy, 270.0), "E": (x1 - bl / 2, cy, 90.0)}[head]

    def roomy(bed_id: str, head: str) -> bool:
        bed = CATALOG[bed_id]
        if bed_id == "bed.single":
            return True
        across, along = (w, h) if head in "NS" else (h, w)
        return across >= bed["w"] + (0.4 if head in "NS" else 0.15) and along >= bed["d"] + (0.3 if head in "NS" else 0.6)

    # La taille du lit prime sur la porte : on prend d'abord le lit (double si la pièce le permet, dans
    # une orientation quelconque), puis, parmi les orientations possibles, la première qui ne gêne
    # aucun battant ; à défaut la première, plutôt qu'un lit simple couché en travers.
    chosen: tuple[str, str] | None = None
    for bed_id in ("bed.double", "bed.single"):
        possible = []
        for head in ("N", "W", "E", "S"):
            px, py, rot = placement(head, CATALOG[bed_id]["d"])
            if roomy(bed_id, head) and fits(bed_id, px, py, rot, ignore_zones=True):
                possible.append(head)
        if possible:
            free = [h for h in possible if fits(bed_id, *placement(h, CATALOG[bed_id]["d"]))]
            chosen = (bed_id, (free or possible)[0])
            break
    bed_id, head = chosen or ("bed.single", "N")
    bed = CATALOG[bed_id]
    px, py, rot = placement(head, bed["d"])
    add(bed_id, px, py, rot, required=True)
    side = bed["w"] / 2 + ns["w"] / 2 + 0.04
    for sign in (-1, 1):
        if head in "NS":
            add("nightstand", cx + sign * side, y0 + ns["d"] / 2 if head == "N" else y1 - ns["d"] / 2, rot)
        else:
            add("nightstand", x0 + ns["d"] / 2 if head == "W" else x1 - ns["d"] / 2, cy + sign * side, rot)
    # Armoire contre le mur opposé à la tête (puis les autres), dos au mur, jamais devant une porte ;
    # une seconde si la chambre est grande. `essential=False` : mieux vaut pas d'armoire qu'une armoire
    # dans le battant.
    if w * h >= 6.5:
        order = {"N": "SEW", "S": "NEW", "W": "ENS", "E": "WNS"}[head]
        add_first("wardrobe", along_walls("wardrobe", order), essential=False)
        if w * h >= 12:
            add_first("wardrobe", along_walls("wardrobe", order), essential=False)


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
