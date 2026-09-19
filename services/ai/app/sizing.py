"""Cotation d'un pavage : replace les coupes d'après les aires demandées.

Le pavage de `layout_opt` produit une **partition exacte** de l'emprise — zéro
chevauchement, couverture 1,0000 — mais ses coupes horizontales sont posées par
des constantes (bande nuit à 38 % de la profondeur, couloir à 12 %) qui ignorent
les surfaces du programme. D'où un écart moyen de ~8,8 m² entre l'aire demandée
et l'aire obtenue, mesuré sur le corpus de `tests/test_layout_invariants.py`.

Ce module ne redessine rien. Il reconnaît la structure de découpe du pavage
existant, puis **replace les mêmes coupes** en les répartissant d'après les
aires cibles. Comme seules les positions bougent et que les coupes restent
partagées entre voisins, la partition reste exacte par construction : c'est la
propriété qu'il ne faut surtout pas perdre.

Méthode. Un pavage sliçable se décrit par un arbre : chaque nœud coupe sa
région en bandes (V = côte à côte, H = empilées), chaque feuille est une pièce.
L'arbre est retrouvé en cherchant les lignes de coupe qu'aucune pièce ne
traverse. Puis, de la racine vers les feuilles, chaque longueur de bande est
allouée proportionnellement à la somme des aires cibles de son sous-arbre, les
côtés minimaux étant servis d'abord par remplissage progressif.

Portée. Un pavage non sliçable (configuration en moulinet) n'est pas reconnu :
la fonction rend alors l'entrée inchangée. C'est le cas que l'étape 3b du
chantier viendra couvrir.
"""
from __future__ import annotations

from typing import Any

from .layout_opt import MIN_SIDE, _forbidden_count, _min_side


_EPS = 1e-6


def _bbox(room: dict[str, Any]) -> tuple[float, float, float, float] | None:
    poly = room.get("polygon") or []
    if len(poly) < 3:
        return None
    xs = [float(p["x"]) for p in poly]
    ys = [float(p["y"]) for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _box(x0: float, y0: float, x1: float, y1: float) -> list[dict[str, float]]:
    return [
        {"x": round(x0, 2), "y": round(y0, 2)},
        {"x": round(x1, 2), "y": round(y0, 2)},
        {"x": round(x1, 2), "y": round(y1, 2)},
        {"x": round(x0, 2), "y": round(y1, 2)},
    ]


def _snap(v: float, grid: float) -> float:
    g = grid if grid > 0 else 0.1
    return round(v / g) * g


# --- Reconnaissance de l'arbre de découpe ---------------------------------

Box = tuple[dict[str, Any], tuple[float, float, float, float]]


def _free_cuts(boxes: list[Box], lo: float, hi: float, axis: int) -> list[float]:
    """Positions dans (lo, hi) qu'aucune boîte ne traverse.

    `axis` vaut 0 pour une coupe verticale (on regarde les x), 1 pour une
    coupe horizontale (les y).
    """
    edges: set[float] = set()
    for _, b in boxes:
        for v in (b[axis], b[axis + 2]):
            if lo + _EPS < v < hi - _EPS:
                edges.add(round(v, 6))
    out = []
    for cut in sorted(edges):
        if all(not (b[axis] + _EPS < cut < b[axis + 2] - _EPS) for _, b in boxes):
            out.append(cut)
    return out


def _build(boxes: list[Box], x0: float, y0: float, x1: float, y1: float) -> dict[str, Any] | None:
    """Arbre de découpe de la région, ou None si elle n'est pas sliçable."""
    if len(boxes) == 1:
        return {"kind": "leaf", "room": boxes[0][0]}
    for axis, (lo, hi) in ((0, (x0, x1)), (1, (y0, y1))):
        cuts = _free_cuts(boxes, lo, hi, axis)
        if not cuts:
            continue
        bounds = [lo, *cuts, hi]
        children: list[dict[str, Any]] = []
        seen = 0
        for i in range(len(bounds) - 1):
            a, b = bounds[i], bounds[i + 1]
            group = [
                (r, bb) for r, bb in boxes
                if bb[axis] >= a - _EPS and bb[axis + 2] <= b + _EPS
            ]
            if not group:
                return None
            seen += len(group)
            sub = (
                _build(group, a, y0, b, y1) if axis == 0
                else _build(group, x0, a, x1, b)
            )
            if sub is None:
                return None
            children.append(sub)
        # Une boîte tombée dans aucune bande (ou dans deux) : la région n'est
        # pas une partition propre, on renonce plutôt que de coter de travers.
        if seen != len(boxes):
            return None
        return {"kind": "V" if axis == 0 else "H", "children": children}
    return None


def slicing_tree(
    rooms: list[dict[str, Any]], width: float, depth: float
) -> dict[str, Any] | None:
    """Arbre de découpe d'un pavage, ou None s'il n'est pas sliçable."""
    boxes: list[Box] = []
    for room in rooms:
        box = _bbox(room)
        if box is None:
            return None
        boxes.append((room, box))
    if not boxes:
        return None
    return _build(boxes, 0.0, 0.0, float(width), float(depth))


# --- Besoins d'un sous-arbre ----------------------------------------------

def _target(node: dict[str, Any], targets: dict[Any, float]) -> float:
    if node["kind"] == "leaf":
        room = node["room"]
        fallback = float(room.get("area_m2") or room.get("area") or 8.0)
        return max(float(targets.get(room.get("id"), fallback)), 0.5)
    return sum(_target(c, targets) for c in node["children"])


def _freeze_targets(node: dict[str, Any], targets: dict[Any, float]) -> float:
    """Fige les aires cibles de chaque sous-arbre dans l'arbre, avant cotation.

    `_assign` réécrit `area_m2` au fur et à mesure ; or c'est la valeur de repli
    des pièces sans cible (le couloir ajouté par `_ensure_hallway`). Lire les
    cibles pendant la descente reviendrait donc à pondérer certaines bandes
    avec des aires déjà réécrites. On les fige d'abord, une fois.
    """
    if node["kind"] == "leaf":
        return _target(node, targets)
    node["_w"] = [_freeze_targets(c, targets) for c in node["children"]]
    return sum(node["_w"])


def _min_span(node: dict[str, Any], axis: int, min_side: float) -> float:
    """Largeur (axis=0) ou hauteur (axis=1) minimale du sous-arbre.

    Les bandes parallèles à l'axe s'additionnent, les bandes perpendiculaires
    se recouvrent : on prend le maximum.
    """
    if node["kind"] == "leaf":
        return _min_side(str(node["room"].get("type") or ""), min_side)
    parallel = (node["kind"] == "V") == (axis == 0)
    spans = [_min_span(c, axis, min_side) for c in node["children"]]
    return sum(spans) if parallel else max(spans)


# --- Allocation d'une longueur --------------------------------------------

def _effective_mins(span: float, mins: list[float]) -> list[float]:
    """Minimums réellement tenables dans `span`.

    Quand la somme des minimums dépasse la bande, on les réduit tous dans la
    même proportion plutôt que d'en sacrifier un entièrement. `_waterfill` et
    `_positions` doivent partir des **mêmes** valeurs : sinon les garde-fous de
    `_positions` réclament plus de place qu'il n'y en a, les bornes sortent de
    la bande, et la dernière — forcée à `span` — inverse un intervalle. Le
    rectangle correspondant recouvre alors ses voisins.
    """
    need = sum(mins)
    if need <= max(span, 0.0) - _EPS or need <= 0:
        return list(mins)
    scale = max(span, 0.0) / need
    return [m * scale for m in mins]


def _waterfill(span: float, weights: list[float], mins: list[float]) -> list[float]:
    """Longueurs sommant à `span`, proportionnelles aux poids, minimums d'abord.

    Remplissage progressif : on sert les minimums de ceux que la répartition
    proportionnelle laisserait trop courts, puis on redistribue le reste entre
    les autres, jusqu'à stabilisation. `mins` est supposé déjà tenable
    (cf. `_effective_mins`).
    """
    n = len(weights)
    if n == 0:
        return []
    if n == 1:
        return [span]
    if sum(mins) >= span - _EPS:
        return list(mins)

    fixed = [False] * n
    out = [0.0] * n
    while True:
        free = [i for i in range(n) if not fixed[i]]
        rest = span - sum(out[i] for i in range(n) if fixed[i])
        total = sum(weights[i] for i in free) or float(len(free))
        changed = False
        for i in free:
            out[i] = rest * (weights[i] / total if total else 1.0 / len(free))
        for i in free:
            if out[i] < mins[i] - _EPS:
                out[i] = mins[i]
                fixed[i] = True
                changed = True
        if not changed:
            return out


def _positions(span: float, lens: list[float], mins: list[float], grid: float) -> list[float]:
    """Bornes [0, ..., span] calées sur la grille, croissantes, minimums tenus."""
    n = len(lens)
    if n <= 1:
        return [0.0, span]
    # Queue = place minimale encore nécessaire après chaque borne, pour ne
    # jamais avancer une coupe au point d'étrangler les suivantes.
    tail = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        tail[i] = tail[i + 1] + mins[i]
    out = [0.0]
    acc = 0.0
    for i in range(n - 1):
        acc += lens[i]
        lo = out[-1] + mins[i]
        hi = span - tail[i + 1]
        out.append(min(max(_snap(acc, grid), lo), max(lo, hi)))
    out.append(span)
    return out


# --- Cotation --------------------------------------------------------------

def _assign(
    node: dict[str, Any],
    x0: float, y0: float, x1: float, y1: float,
    targets: dict[Any, float],
    grid: float,
    min_side: float,
) -> None:
    if node["kind"] == "leaf":
        room = node["room"]
        room["polygon"] = _box(x0, y0, x1, y1)
        room["area_m2"] = round(max(0.0, x1 - x0) * max(0.0, y1 - y0), 2)
        return

    children = node["children"]
    axis = 0 if node["kind"] == "V" else 1
    span = max(0.0, (x1 - x0) if axis == 0 else (y1 - y0))
    weights = [node["_w"][i] for i in range(len(children))]
    mins = _effective_mins(span, [_min_span(c, axis, min_side) for c in children])
    lens = _waterfill(span, weights, mins)
    pos = _positions(span, lens, mins, grid)

    base = x0 if axis == 0 else y0
    for i, child in enumerate(children):
        a, b = base + pos[i], base + pos[i + 1]
        if axis == 0:
            _assign(child, a, y0, b, y1, targets, grid, min_side)
        else:
            _assign(child, x0, a, x1, b, targets, grid, min_side)


def _quality(
    rooms: list[dict[str, Any]], targets: dict[Any, float], min_side: float
) -> tuple[int, int, float]:
    """(adjacences interdites, pièces sous le côté minimal, écart aux aires).

    Trois critères séparés, volontairement non agrégés : une règle sanitaire ne
    se négocie pas, un côté minimal est un plancher d'habitabilité, une aire
    n'est qu'une préférence. Les mêler derrière une pondération arbitraire
    ferait accepter un plan qui étrangle une chambre pour gagner un mètre carré
    ailleurs.

    Replacer une coupe peut faire franchir à un bord partagé le seuil de
    longueur de `share_edge` : une adjacence interdite peut donc apparaître
    sans qu'aucune pièce n'ait changé de voisin. D'où le premier terme.
    """
    thin = 0
    err = 0.0
    for room in rooms:
        box = _bbox(room)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        if min(x1 - x0, y1 - y0) + _EPS < _min_side(str(room.get("type") or ""), min_side):
            thin += 1
        target = targets.get(room.get("id"))
        if target:
            err += ((x1 - x0) * (y1 - y0) - float(target)) ** 2
    return _forbidden_count(rooms), thin, err


def resize_layout(
    rooms: list[dict[str, Any]],
    width: float,
    depth: float,
    *,
    targets: dict[Any, float] | None = None,
    grid: float = 0.1,
    min_side: float = MIN_SIDE,
    only_if_better: bool = True,
) -> tuple[list[dict[str, Any]], bool]:
    """Recote un pavage d'après les aires demandées.

    Renvoie `(rooms, applied)`. Les pièces sont rendues **inchangées** dans deux
    cas, sans aucune perte : le pavage n'est pas sliçable, ou la cotation
    n'améliorerait pas le plan.

    `only_if_better` garde la cotation seulement si elle réduit strictement
    l'écart aux aires *sans* ajouter d'adjacence interdite ni de pièce sous son
    côté minimal. C'est le
    motif déjà employé par `_fill_gaps` — tenter, vérifier, revenir en arrière —
    et il rend la régression impossible : au pire le plan est celui d'avant.

    La cotation ne crée ni ne supprime aucune pièce et ne change aucune
    adjacence : seules les positions des coupes bougent. La partition reste
    exacte, et les règles de distribution déjà satisfaites le restent.
    """
    if not rooms:
        return rooms, False
    tree = slicing_tree(rooms, width, depth)
    if tree is None:
        return rooms, False

    targets = targets or {}
    before = _quality(rooms, targets, min_side) if only_if_better else None
    snapshot = [(r, r.get("polygon"), r.get("area_m2")) for r in rooms]

    _freeze_targets(tree, targets)
    _assign(tree, 0.0, 0.0, float(width), float(depth), targets, grid, min_side)

    if before is not None:
        after = _quality(rooms, targets, min_side)
        if not (after[0] <= before[0] and after[1] <= before[1] and after[2] < before[2]):
            for room, poly, area in snapshot:
                room["polygon"] = poly
                room["area_m2"] = area
            return rooms, False
    return rooms, True
