"""Arrangements de zones : énumérer TOUTES les façons de disposer les grandes zones.

Le gabarit actuel ne connaît qu'un arrangement (chambres au nord, couloir, jour
au sud). Ce module change d'échelle : au lieu de découper des pièces, il
découpe des **zones** — nuit, couloir, jour, service, garage. Cinq nœuds au
plus : on peut donc énumérer exhaustivement les arbres de découpe, au lieu de
les échantillonner.

Un arbre de découpe est canonique : ses nœuds alternent V (enfants côte à côte)
et H (enfants empilés) ; deux coupes consécutives de même sens sont fusionnées,
ce qui écarte les doublons géométriques. Pour n zones étiquetées il y en a
``2 · n! · s(n-1)`` (s = nombres de Schröder 1, 3, 11, 45…) : 4, 36, 528, puis
10 800 pour cinq zones.

Ce module ne remplit pas les zones et ne juge pas un plan : il produit des
CANDIDATS et applique des conditions **nécessaires**, dérivées de
`layout_rules`. Une condition nécessaire élimine à coup sûr (une chambre ne peut
pas toucher un couloir si sa zone n'en touche aucun) ; elle ne garantit pas que
le remplissage réussira. Le remplissage et le contrôle exact viennent après.

Trois niveaux, du plus large au plus strict :
  * ``necessary``  — condition nécessaire ;
  * ``connected``  — plus : le jour donne sur le couloir ;
  * ``strict``     — plus : aucun mur commun entre zones dont des pièces sont
                     interdites de contact (nuit/jour, service/nuit, service/jour).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from .layout_opt import _min_side
from .layout_rules import HABITABLE_TYPES, forbidden_pairs, types_needing_hall
from .sizing import _effective_mins, _waterfill

NIGHT, HALL, DAY, SVC, GARAGE = "night", "hall", "day", "svc", "garage"
ZONES: tuple[str, ...] = (NIGHT, HALL, DAY, SVC, GARAGE)

_ZONE_OF: dict[str, str] = {
    "bedroom": NIGHT, "office": NIGHT, "bathroom": NIGHT,
    "hallway": HALL,
    "living": DAY, "kitchen": DAY, "dining": DAY,
    "wc": SVC, "laundry": SVC, "storage": SVC,
    "garage": GARAGE,
}

# Épaisseur imposée à un couloir : c'est une circulation, pas une pièce. Le
# gabarit actuel la place entre 1,15 m et 1,5 m.
HALL_THICKNESS = 1.3
# Un couloir est allongé : côté long au moins deux fois le côté court.
HALL_MIN_ASPECT = 2.0
# Contact minimal entre deux zones pour y ouvrir une porte (largeur 0,80 m + marge).
MIN_CONTACT = 0.9
# Contact minimal d'une zone d'habitation avec le périmètre (une fenêtre, un dégagement).
MIN_PERIMETER = 1.5
_TOL = 0.05

Tree = Any  # str (feuille) | tuple[str, tuple[Tree, ...]] (nœud : sens, enfants)
Rect = tuple[float, float, float, float]


def zone_of(room_type: str) -> str:
    """Zone d'un type de pièce. Un type inconnu relève du jour (pièce d'appoint)."""
    return _ZONE_OF.get(room_type, DAY)


# --- Énumération -------------------------------------------------------------

def _ordered_partitions(items: tuple[str, ...]) -> list[tuple[tuple[str, ...], ...]]:
    """Toutes les partitions ordonnées de `items` en au moins deux blocs non vides."""
    assert len(items) >= 2
    out: list[tuple[tuple[str, ...], ...]] = []

    def rec(remaining: tuple[str, ...], acc: tuple[tuple[str, ...], ...]) -> None:
        if not remaining:
            if len(acc) >= 2:
                out.append(acc)
            return
        m = len(remaining)
        for mask in range(1, 2**m):
            block = tuple(remaining[i] for i in range(m) if mask >> i & 1)
            rest = tuple(remaining[i] for i in range(m) if not mask >> i & 1)
            # Le bloc unique (tout le lot) n'est pas une coupe.
            if not acc and not rest:
                continue
            rec(rest, acc + (block,))

    rec(items, ())
    return out


@lru_cache(maxsize=None)
def _trees(zones: tuple[str, ...], orient: str) -> tuple[Tree, ...]:
    """Arbres dont la racine est une coupe de sens `orient` (feuille si un seul zone)."""
    if len(zones) == 1:
        return (zones[0],)
    other = "H" if orient == "V" else "V"
    out: list[Tree] = []
    for blocks in _ordered_partitions(zones):
        options = [_trees(block, other) for block in blocks]
        for combo in itertools.product(*options):
            out.append((orient, tuple(combo)))
    return tuple(out)


@lru_cache(maxsize=None)
def enumerate_trees(zones: tuple[str, ...]) -> tuple[Tree, ...]:
    """Tous les arbres de découpe canoniques sur ces zones, dans un ordre déterministe."""
    zones = tuple(sorted(zones))
    if not zones:
        return ()
    if len(zones) == 1:
        return (zones[0],)
    return _trees(zones, "V") + _trees(zones, "H")


def tree_count(n: int) -> int:
    """Nombre attendu d'arbres pour `n` zones : 2 · n! · s(n-1), s = Schröder."""
    if n <= 0:
        return 0
    if n == 1:
        return 1
    schroder = [1, 1]  # s(0)=1, s(1)=1 ; s(k) = ((6k-3)·s(k-1) - (k-2)·s(k-2)) / (k+1)
    for k in range(2, n):
        schroder.append(((6 * k - 3) * schroder[k - 1] - (k - 2) * schroder[k - 2]) // (k + 1))
    # s(n-1) parmi les arbres non étiquetés à n feuilles, par sens de racine.
    factorial = 1
    for k in range(2, n + 1):
        factorial *= k
    return 2 * factorial * schroder[n - 1]


# --- Programme -> zones ------------------------------------------------------

@dataclass(frozen=True)
class Program:
    """Ce qu'un programme demande, ramené aux zones."""

    demand: dict[str, float]            # aire demandée par zone (m²)
    types: frozenset[str]               # types de pièces présents (couloir implicite inclus)
    min_side: dict[str, float]          # côté minimal exigé par zone

    @property
    def zones(self) -> tuple[str, ...]:
        return tuple(z for z in ZONES if z in self.demand)


def program_from_rooms(rooms: list[dict[str, Any]]) -> Program:
    """Zones demandées par un programme de pièces (une entrée par pièce).

    Le couloir est implicite dès qu'il y a une chambre, ou un WC avec une pièce
    de jour (même règle que `layout_opt._ensure_hallway`) : la zone existe alors
    même si le programme n'en parle pas.
    """
    demand: dict[str, float] = {}
    types: set[str] = set()
    for room in rooms:
        typ = str(room.get("type") or "other")
        types.add(typ)
        zone = zone_of(typ)
        area = float(room.get("area_m2") or room.get("area") or 12.0)
        demand[zone] = demand.get(zone, 0.0) + max(area, 2.0)
    has_day = any(zone_of(t) == DAY for t in types)
    if HALL not in demand and ("bedroom" in types or ("wc" in types and has_day)):
        demand[HALL] = 8.0
        types.add("hallway")
    mins: dict[str, float] = {}
    for zone in demand:
        present = [t for t in types if zone_of(t) == zone]
        mins[zone] = max((_min_side(t, 1.6) for t in present), default=1.6)
    if HALL in mins:
        mins[HALL] = min(mins[HALL], HALL_THICKNESS)
    return Program(demand=demand, types=frozenset(types), min_side=mins)


# --- Dimensionnement d'un arbre ---------------------------------------------

def _leaves(tree: Tree) -> tuple[str, ...]:
    return (tree,) if isinstance(tree, str) else tuple(z for c in tree[1] for z in _leaves(c))


def _demand(tree: Tree, prog: Program) -> float:
    if isinstance(tree, str):
        return prog.demand[tree]
    return sum(_demand(c, prog) for c in tree[1])


def _min_span(tree: Tree, axis: str, prog: Program) -> float:
    """Largeur (axe 'x') ou hauteur ('y') minimale : somme le long de l'axe, max en travers."""
    if isinstance(tree, str):
        return prog.min_side[tree]
    parallel = (tree[0] == "V") == (axis == "x")
    spans = [_min_span(c, axis, prog) for c in tree[1]]
    return sum(spans) if parallel else max(spans)


def size_tree(tree: Tree, prog: Program, width: float, depth: float) -> dict[str, Rect] | None:
    """Rectangle de chaque zone, ou None si un côté minimal ne peut pas être tenu.

    Les zones se partagent une longueur au prorata de leurs aires demandées ; un
    couloir feuille reçoit son épaisseur fixe `HALL_THICKNESS`. Rien n'est calé
    sur une grille : ce sont des candidats, le dimensionnement fin vient après.
    """
    rects: dict[str, Rect] = {}
    ok = _assign(tree, (0.0, 0.0, float(width), float(depth)), prog, rects)
    return rects if ok else None


def _assign(tree: Tree, box: Rect, prog: Program, rects: dict[str, Rect]) -> bool:
    if isinstance(tree, str):
        rects[tree] = box
        return True
    x0, y0, x1, y1 = box
    axis = "x" if tree[0] == "V" else "y"
    span = (x1 - x0) if axis == "x" else (y1 - y0)
    children = tree[1]
    mins = [_min_span(c, axis, prog) for c in children]
    fixed = [c == HALL for c in children]  # couloir feuille : épaisseur imposée
    if sum(m for m, f in zip(mins, fixed, strict=True) if not f) + HALL_THICKNESS * sum(fixed) > span + 1e-9:
        return False
    free_idx = [i for i, f in enumerate(fixed) if not f]
    room = span - HALL_THICKNESS * sum(fixed)
    lens = [HALL_THICKNESS if f else 0.0 for f in fixed]
    if free_idx:
        weights = [_demand(children[i], prog) for i in free_idx]
        fmins = _effective_mins(room, [mins[i] for i in free_idx])
        for i, ln in zip(free_idx, _waterfill(room, weights, fmins), strict=True):
            lens[i] = ln
    pos = x0 if axis == "x" else y0
    for child, ln in zip(children, lens, strict=True):
        sub = (pos, y0, pos + ln, y1) if axis == "x" else (x0, pos, x1, pos + ln)
        if not _assign(child, sub, prog, rects):
            return False
        pos += ln
    return True


# --- Contacts ----------------------------------------------------------------

def contact_length(a: Rect, b: Rect) -> float:
    """Longueur du mur commun de deux rectangles (0 s'ils ne se touchent que par un coin)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    y_ov = min(ay1, by1) - max(ay0, by0)
    x_ov = min(ax1, bx1) - max(ax0, bx0)
    length = 0.0
    if (abs(ax1 - bx0) <= _TOL or abs(bx1 - ax0) <= _TOL) and y_ov > _TOL:
        length = max(length, y_ov)
    if (abs(ay1 - by0) <= _TOL or abs(by1 - ay0) <= _TOL) and x_ov > _TOL:
        length = max(length, x_ov)
    return length


def perimeter_length(r: Rect, width: float, depth: float) -> float:
    """Longueur de la zone qui borde le périmètre de l'emprise."""
    x0, y0, x1, y1 = r
    total = 0.0
    if x0 <= _TOL:
        total += y1 - y0
    if x1 >= width - _TOL:
        total += y1 - y0
    if y0 <= _TOL:
        total += x1 - x0
    if y1 >= depth - _TOL:
        total += x1 - x0
    return total


# --- Conditions, dérivées de layout_rules -----------------------------------

@dataclass(frozen=True)
class Constraints:
    """Contraintes de zones pour un programme, tirées de `layout_rules`."""

    needs_hall: frozenset[str]               # zones dont des pièces doivent toucher un couloir
    perimeter: frozenset[str]                # zones habitables : doivent toucher le périmètre
    forbidden: frozenset[frozenset[str]]     # paires de zones dont des pièces ne doivent pas se toucher


def constraints_for(prog: Program) -> Constraints:
    present = prog.types
    needs_hall = frozenset(zone_of(t) for t in types_needing_hall() if t in present) - {HALL}
    perimeter = frozenset(zone_of(t) for t in HABITABLE_TYPES if t in present)
    forbidden: set[frozenset[str]] = set()
    for left, right in forbidden_pairs():
        for a in left & present:
            for b in right & present:
                za, zb = zone_of(a), zone_of(b)
                if za != zb:
                    forbidden.add(frozenset({za, zb}))
    return Constraints(needs_hall, perimeter, frozenset(forbidden))


@dataclass(frozen=True)
class Verdict:
    necessary: bool
    connected: bool
    strict: bool
    reasons: tuple[str, ...] = field(default=())


def judge(rects: dict[str, Rect], prog: Program, width: float, depth: float,
          cons: Constraints | None = None) -> Verdict:
    """Applique les conditions à un arrangement dimensionné."""
    cons = cons or constraints_for(prog)
    reasons: list[str] = []

    hall = rects.get(HALL)
    if hall is not None:
        w, h = hall[2] - hall[0], hall[3] - hall[1]
        if max(w, h) < HALL_MIN_ASPECT * max(min(w, h), 1e-9):
            reasons.append("couloir trop court pour être une circulation")
        for zone in cons.needs_hall:
            if contact_length(rects[zone], hall) < MIN_CONTACT:
                reasons.append(f"{zone} ne touche pas le couloir")
    # Sans couloir, rien à toucher : `NeedsHall` ne s'applique que s'il en existe un.
    for zone in cons.perimeter:
        if perimeter_length(rects[zone], width, depth) < MIN_PERIMETER:
            reasons.append(f"{zone} ne touche pas le périmètre")
    necessary = not reasons

    day_ok = True
    if hall is not None and DAY in rects:
        day_ok = contact_length(rects[DAY], hall) >= MIN_CONTACT
    connected = necessary and day_ok

    strict = connected
    if strict:
        for pair in cons.forbidden:
            a, b = tuple(pair)
            if contact_length(rects[a], rects[b]) > _TOL:
                strict = False
                break
    return Verdict(necessary, connected, strict, tuple(reasons))


# --- Candidats ---------------------------------------------------------------

@dataclass(frozen=True)
class Candidate:
    tree: Tree
    rects: dict[str, Rect]
    verdict: Verdict


def candidates(rooms: list[dict[str, Any]], width: float, depth: float) -> list[Candidate]:
    """Tous les arrangements de zones dimensionnables, chacun avec son verdict.

    Ordre déterministe (celui de `enumerate_trees`). Les arrangements dont un
    côté minimal ne peut pas être tenu sont écartés : ils n'ont pas de rectangle.
    """
    prog = program_from_rooms(rooms)
    cons = constraints_for(prog)
    out: list[Candidate] = []
    for tree in enumerate_trees(prog.zones):
        rects = size_tree(tree, prog, width, depth)
        if rects is None:
            continue
        out.append(Candidate(tree, rects, judge(rects, prog, width, depth, cons)))
    return out


def arrangement_code(rects: dict[str, Rect], width: float, depth: float) -> str:
    """Code court d'un arrangement : côté dominant de chaque zone, sens du couloir.

    Même vocabulaire que `layout_signature.zone_code`, pour comparer les
    arrangements candidats aux plans réellement produits.
    """
    def side(r: Rect | None) -> str:
        if r is None:
            return "-"
        dx = ((r[0] + r[2]) / 2 - width / 2) / (width / 2)
        dy = ((r[1] + r[3]) / 2 - depth / 2) / (depth / 2)
        if max(abs(dx), abs(dy)) < 0.15:
            return "C"
        if abs(dy) >= abs(dx):
            return "N" if dy < 0 else "S"
        return "W" if dx < 0 else "E"

    hall = rects.get(HALL)
    orient = "-" if hall is None else ("H" if (hall[2] - hall[0]) >= (hall[3] - hall[1]) else "V")
    return f"night:{side(rects.get(NIGHT))}|day:{side(rects.get(DAY))}|hall:{orient}|garage:{side(rects.get(GARAGE))}"
