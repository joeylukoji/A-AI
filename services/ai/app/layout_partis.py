"""Remplir les zones : de l'arrangement de zones au plan de pièces, contrôlé.

`layout_zones` énumère des arrangements de zones ; ce module les **réalise** :
il range les pièces de chaque zone avec les primitives éprouvées du gabarit
(`_row`, `_stack`, `_pack_band`), puis soumet le résultat à un contrôle exact.
Seuls les plans qui passent sont des partis réalisables.

Deux temps, de plus en plus coûteux :

  1. `hard_check` — géométrie et règles, sur les seuls rectangles : pavage exact
     de la parcelle, règles sanitaires (`sanitary_violations`), pièces
     habitables sur façade, aucune pièce absurdement étroite ;
  2. `compliance_regressions` — mur, ouvertures et `compliance.evaluate` : un
     plan n'est retenu que s'il ne fait échouer aucun contrôle que le gabarit
     classique réussit pour le même programme.

Le second temps compare au classique plutôt qu'à un seuil : certains contrôles
échouent à cause du programme lui-même (une chambre demandée à 7 m²), pas de
l'arrangement, et ne doivent pas disqualifier un parti.

Rien ici ne choisit entre les plans valides : c'est la politique de sélection,
l'étape suivante.
"""
from __future__ import annotations

import itertools
import random
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from . import layout_opt as lo
from . import layout_zones as z
from .layout_rules import ENTRANCE_TYPES, MIN_ENTRANCE_SPAN, MIN_GARAGE_CONTACT
from .sizing import resize_layout

# Une pièce dont le côté court est sous cette fraction de son minimum est
# absurde (une chambre de 1,4 m), pas seulement juste : elle disqualifie.
# Entre cette fraction et le minimum, c'est une préférence, comptée dans `thin`.
HARD_THIN_FRACTION = 0.75
_TOL = 1e-3

Room = dict[str, Any]


# --- Programme -> pièces par zone -------------------------------------------

def zone_items(rooms: list[Room]) -> tuple[dict[str, list[Room]], Room | None]:
    """Pièces de chaque zone, dans l'ordre d'usage du gabarit, et la salle de bain « ensuite ».

    Reprend les règles de `pack_house` : la dernière chambre et la dernière salle
    de bain forment la suite parentale quand il y a au moins deux salles de bain ;
    un couloir est créé dès qu'il en faut un (`_ensure_hallway`).
    """
    items: list[Room] = []
    for room in rooms:
        it = dict(room)
        it["type"] = str(room.get("type") or "other")
        it["name"] = room.get("name") or it["type"]
        it["area"] = max(float(room.get("area_m2") or 12), 2.0)
        items.append(it)

    def of(typ: str) -> list[Room]:
        return [i for i in items if i["type"] == typ]

    beds, baths, offices = of("bedroom"), of("bathroom"), of("office")
    ensuite = baths[-1] if len(baths) >= 2 and beds else None
    day_baths = baths[:-1] if ensuite else baths
    living = of("living")[0] if of("living") else None
    kitchen = of("kitchen")[0] if of("kitchen") else None
    halls = lo._ensure_hallway(of("hallway"), beds, living, kitchen, of("wc"), of("dining"))
    known = {"bedroom", "bathroom", "office", "hallway", "wc", "laundry", "storage", "garage",
             "living", "kitchen", "dining"}
    # Pièces de jour d'appoint : deuxième cuisine ou séjour, et tout type inconnu.
    extra = [i for i in items if i["type"] not in known] + of("kitchen")[1:] + of("living")[1:]

    zones: dict[str, list[Room]] = {
        z.NIGHT: lo._night_private(beds, offices, ensuite) + list(day_baths),
        z.HALL: list(halls),
        z.DAY: lo._day_sequence(kitchen, living, of("dining"), extra),
        z.SVC: of("wc") + of("laundry") + of("storage"),
        z.GARAGE: of("garage"),
    }
    return {k: v for k, v in zones.items() if v}, ensuite


# --- Remplissage --------------------------------------------------------------

def _snap_rect(r: z.Rect, grid: float) -> z.Rect:
    """Cale une zone sur la grille. Les arêtes communes restent communes : mêmes valeurs."""
    return tuple(lo._snap(round(v, 6), grid) for v in r)  # type: ignore[return-value]


def _hall_axis(rect: z.Rect, hall: z.Rect | None) -> str:
    """Axe le long duquel s'alignent les pièces : parallèle à l'arête commune avec le couloir.

    'x' : rangée est-ouest (couloir au nord ou au sud) ; 'y' : colonne nord-sud.
    Toutes les pièces d'une file parallèle au couloir le touchent, c'est ce qui
    satisfait « chambre et WC s'ouvrent sur la circulation ». Sans contact, l'axe
    est celui du grand côté.
    """
    x0, y0, x1, y1 = rect
    if hall is not None:
        hx0, hy0, hx1, hy1 = hall
        vertical = min(y1, hy1) - max(y0, hy0)      # arête verticale commune
        horizontal = min(x1, hx1) - max(x0, hx0)    # arête horizontale commune
        touches_v = vertical > 0 and (abs(x1 - hx0) < 0.05 or abs(hx1 - x0) < 0.05)
        touches_h = horizontal > 0 and (abs(y1 - hy0) < 0.05 or abs(hy1 - y0) < 0.05)
        if touches_v and touches_h:
            return "x" if horizontal >= vertical else "y"
        if touches_v:
            return "y"
        if touches_h:
            return "x"
    return "x" if (x1 - x0) >= (y1 - y0) else "y"


def _transposed(rooms: list[Room]) -> list[Room]:
    out = []
    for room in rooms:
        moved = dict(room)
        moved["polygon"] = [{"x": p["y"], "y": p["x"]} for p in room["polygon"]]
        out.append(moved)
    return out


def _pack(items: list[Room], rect: z.Rect, axis: str, line: bool, grid: float, min_side: float) -> list[Room]:
    x0, y0, x1, y1 = rect
    if line:
        # Une seule file parallèle au couloir : `_row` (est-ouest) ou `_stack` (nord-sud).
        if axis == "x":
            return lo._row(items, x0, y0, x1, y1, grid, min_side)
        return lo._stack(items, x0, y0, x1, y1, grid, min_side)
    # Sans exigence de couloir : colonnes empilées le long du grand côté.
    if (x1 - x0) >= (y1 - y0):
        return lo._pack_band(items, x0, y0, x1, y1, grid, min_side)
    return _transposed(lo._pack_band(items, y0, x0, y1, x1, grid, min_side))


def _orders(items: list[Room]) -> list[list[Room]]:
    """Ordre direct et inverse : les bouts d'une file touchent les zones voisines."""
    return [items] if len(items) < 2 else [items, list(reversed(items))]


def fill_zones(
    candidate: z.Candidate,
    zones: dict[str, list[Room]],
    ensuite: Room | None,
    *,
    grid: float = 0.1,
    min_side: float = 1.6,
) -> Iterator[list[Room]]:
    """Plans de pièces qui réalisent l'arrangement, un par combinaison d'ordres.

    Au plus 2^3 = 8 combinaisons (ordre direct ou inverse de la nuit, du jour et
    du service). Les ordres décident quelle pièce touche quelle zone voisine : ils
    servent à éviter, par exemple, la cuisine contre le WC.
    """
    rects = {name: _snap_rect(r, grid) for name, r in candidate.rects.items()}
    hall = rects.get(z.HALL)
    flexible = [name for name in (z.NIGHT, z.DAY, z.SVC) if name in zones]
    for combo in itertools.product(*(_orders(zones[name]) for name in flexible)):
        out: list[Room] = []
        for name, items in zip(flexible, combo, strict=True):
            line = name in (z.NIGHT, z.SVC) and any(i["type"] in lo._NEEDS_CIRCULATION for i in items)
            out += _pack(items, rects[name], _hall_axis(rects[name], hall), line, grid, min_side)
        for name in (z.HALL, z.GARAGE):
            if name in zones:
                rect = rects[name]
                out += _pack(zones[name], rect, "x" if (rect[2] - rect[0]) >= (rect[3] - rect[1]) else "y",
                             True, grid, min_side)
        if ensuite is not None:
            for room in out:
                if room.get("id") == ensuite.get("id"):
                    room["ensuite"] = True
        yield out


# --- Contrôle exact, premier temps ------------------------------------------

def _bbox(room: Room) -> tuple[float, float, float, float]:
    xs = [float(p["x"]) for p in room["polygon"]]
    ys = [float(p["y"]) for p in room["polygon"]]
    return min(xs), min(ys), max(xs), max(ys)


def thin_count(rooms: list[Room], min_side: float) -> int:
    """Pièces sous leur côté minimal : une préférence, pas un motif de rejet."""
    n = 0
    for room in rooms:
        x0, y0, x1, y1 = _bbox(room)
        if min(x1 - x0, y1 - y0) + 1e-6 < lo._min_side(str(room.get("type") or ""), min_side):
            n += 1
    return n


def hard_check(rooms: list[Room], width: float, depth: float, min_side: float = 1.6,
               conventions: bool = True) -> str | None:
    """Premier motif de rejet, ou None si le plan passe.

    Motifs : « emprise », « couverture » (trou ou recouvrement), « sanitaire »,
    « facade », « trop_fin », « entree » (l'entrée sud ne donne pas sur une pièce
    d'accueil), « garage » (aucune façade assez longue pour la porte de garage). Le nombre de pièces est vérifié par l'appelant. `conventions=False`
    ne contrôle que les règles de distribution, sans les conventions de façade
    de `default_openings` (entrée au sud, façade assez longue pour la porte de garage).
    """
    boxes = [_bbox(r) for r in rooms]
    for x0, y0, x1, y1 in boxes:
        if x0 < -_TOL or y0 < -_TOL or x1 > width + _TOL or y1 > depth + _TOL:
            return "emprise"
    for (a0, b0, a1, b1), (c0, d0, c1, d1) in itertools.combinations(boxes, 2):
        if min(a1, c1) - max(a0, c0) > _TOL and min(b1, d1) - max(b0, d0) > _TOL:
            return "couverture"
    if abs(sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in boxes) - width * depth) > _TOL * 10:
        return "couverture"
    if lo.sanitary_violations(rooms):
        return "sanitaire"
    for room in rooms:
        if room["type"] in lo.HABITABLE and not lo._on_facade(room["polygon"], width, depth):
            return "facade"
    for room, (x0, y0, x1, y1) in zip(rooms, boxes, strict=True):
        if min(x1 - x0, y1 - y0) < HARD_THIN_FRACTION * lo._min_side(room["type"], min_side):
            return "trop_fin"
    if conventions:
        if not _entrance_ok(rooms, boxes, depth):
            return "entree"
        if not _garage_door_ok(rooms, boxes, width, depth):
            return "garage"
    return None


def _entrance_ok(rooms: list[Room], boxes: list[tuple[float, float, float, float]], depth: float) -> bool:
    """L'entrée (mur sud) a devant elle une pièce d'accueil : couloir, séjour ou salle à manger.

    `default_openings` pose l'entrée sur le mur sud sans connaître le plan ; si
    la façade sud n'offre que des chambres, le porche s'ouvre sur elles. Sans
    pièce d'accueil dans le programme, il n'y a rien à exiger.
    """
    if not any(r["type"] in ENTRANCE_TYPES for r in rooms):
        return True
    return any(
        r["type"] in ENTRANCE_TYPES and y1 >= depth - 0.15 and (x1 - x0) >= MIN_ENTRANCE_SPAN
        for r, (x0, _y0, x1, y1) in zip(rooms, boxes, strict=True)
    )


def _garage_door_ok(rooms: list[Room], boxes: list[tuple[float, float, float, float]],
                    width: float, depth: float) -> bool:
    """Un garage a une façade assez longue pour sa porte (`diffusion._garage_door`)."""
    garages = [b for r, b in zip(rooms, boxes, strict=True) if r["type"] == "garage"]
    if not garages:
        return True
    return any(z.wall_contact(b, width, depth) >= MIN_GARAGE_CONTACT for b in garages)


def _targets(rooms: list[Room]) -> dict[Any, float]:
    """Aires demandées par identifiant : la cible de la cotation."""
    return {r.get("id"): float(r["area_m2"]) for r in rooms if r.get("area_m2")}


def refine(layout: list[Room], targets: dict[Any, float], width: float, depth: float,
           grid: float, min_side: float, conventions: bool = True) -> None:
    """Replace les coupes d'après les aires demandées (`sizing.resize_layout`), sous garde.

    Un remplissage est un pavage par découpes, donc `resize_layout` s'y applique
    tel quel. La garde de `resize_layout` interdit déjà d'ajouter une adjacence
    interdite ou une pièce sous son côté minimal ; on ajoute ici le contrôle dur
    complet, et on restaure le remplissage d'origine s'il ne passe plus.
    """
    backup = [(r, r["polygon"], r.get("area_m2")) for r in layout]
    resize_layout(layout, width, depth, targets=targets, grid=grid, min_side=min_side)
    if hard_check(layout, width, depth, min_side, conventions) is not None:
        for room, polygon, area in backup:
            room["polygon"] = polygon
            room["area_m2"] = area


# --- Réalisations --------------------------------------------------------------

@dataclass(frozen=True)
class Realization:
    """Un parti réalisable : un arrangement de zones et le plan de pièces qui le réalise."""

    tree: z.Tree
    rects: dict[str, z.Rect]
    rooms: list[Room]
    code: str                                   # arrangement, à un miroir près
    graph: frozenset[tuple[str, str]]           # zones qui se touchent
    thin: int                                   # pièces sous leur côté minimal
    strict: bool = False                        # aucun mur commun entre zones aux pièces incompatibles
    raw_code: str = ""                          # arrangement tel quel (côtés exacts, sans fusion de miroir)

    @property
    def klass(self) -> tuple[str, frozenset[tuple[str, str]]]:
        """Identité d'un parti : côté/sens des zones et graphe d'adjacence."""
        return (self.code, self.graph)


def _plot(width: float, depth: float, grid: float, min_side: float) -> tuple[float, float]:
    """Emprise calée sur la grille, comme `pack_house` : les polygones ont les mêmes bornes."""
    return lo._snap(max(width, min_side * 2), grid), lo._snap(max(depth, min_side * 2), grid)


def iter_realizations(
    rooms: list[Room],
    width: float,
    depth: float,
    *,
    grid: float = 0.1,
    min_side: float = 1.6,
    rng: random.Random | None = None,
    strict_first: bool = True,
    conventions: bool = True,
    exact: bool = True,
) -> Iterator[Realization]:
    """Réalisations valides, paresseusement, en balayant les arrangements de zones.

    Sans `rng` l'ordre est déterministe (arrangements stricts d'abord, puis le
    reste, dans l'ordre d'énumération). Avec un `rng`, l'ordre est tiré : deux
    graines donnent deux séquences différentes. Rien n'est calculé au-delà de ce
    que le consommateur demande.
    """
    width, depth = _plot(width, depth, grid, min_side)
    zones, ensuite = zone_items(rooms)
    if not zones:
        return
    cands = [c for c in z.candidates(rooms, width, depth, conventions) if c.verdict.connected]
    if rng is not None:
        rng.shuffle(cands)
    if strict_first:
        cands.sort(key=lambda c: not c.verdict.strict)  # tri stable : l'ordre (tiré ou non) est conservé
    expected = len(zone_total(zones))
    targets = _targets(rooms)
    # Le second temps n'a de sens qu'avec les conventions : sans elles, `default_openings`
    # poserait l'entrée et la porte de garage sur les mauvaises pièces.
    baseline = classic_baseline(rooms, width, depth, grid=grid, min_side=min_side) if exact and conventions else None
    for cand in cands:
        for layout in fill_zones(cand, zones, ensuite, grid=grid, min_side=min_side):
            if len(layout) != expected or hard_check(layout, width, depth, min_side, conventions) is not None:
                continue
            refine(layout, targets, width, depth, grid, min_side, conventions)
            if baseline is not None and not exact_ok(layout, width, depth, baseline):
                continue
            yield Realization(
                tree=cand.tree,
                rects=cand.rects,
                rooms=layout,
                code=z.canonical_code(z.arrangement_code(cand.rects, width, depth)),
                graph=z.adjacency_graph(cand.rects),
                thin=thin_count(layout, min_side),
                strict=cand.verdict.strict,
                raw_code=z.arrangement_code(cand.rects, width, depth),
            )
            break  # une réalisation par arrangement : les ordres ne sont que des essais


def zone_total(zones: dict[str, list[Room]]) -> list[Room]:
    return [r for items in zones.values() for r in items]


def realizations(
    rooms: list[Room],
    width: float,
    depth: float,
    *,
    grid: float = 0.1,
    min_side: float = 1.6,
    per_class: int = 1,
    tries_per_class: int = 6,
    conventions: bool = True,
    exact: bool = True,
    max_classes: int | None = None,
) -> list[Realization]:
    """Partis réalisables distincts : `per_class` réalisations par classe (côté/sens, adjacence).

    Les arrangements d'une même classe ne diffèrent que par leurs proportions ;
    `tries_per_class` borne les essais avant de déclarer la classe irréalisable,
    puisque la réussite dépend des proportions de la parcelle.

    `max_classes` borne le travail d'un programme riche (jusqu'à une centaine de
    classes). C'est une borne sur un NOMBRE, pas sur un temps : un délai rendrait
    le résultat dépendant de la machine. Les classes qui contiennent un
    arrangement strict passent d'abord, pour que la borne garde les meilleures.
    """
    width, depth = _plot(width, depth, grid, min_side)
    zones, ensuite = zone_items(rooms)
    if not zones:
        return []
    by_class: dict[Any, list[z.Candidate]] = {}
    for cand in z.candidates(rooms, width, depth, conventions):
        if cand.verdict.connected:
            key = (z.canonical_code(z.arrangement_code(cand.rects, width, depth)), z.adjacency_graph(cand.rects))
            by_class.setdefault(key, []).append(cand)
    out: list[Realization] = []
    expected = len(zone_total(zones))
    targets = _targets(rooms)
    baseline = classic_baseline(rooms, width, depth, grid=grid, min_side=min_side) if exact and conventions else None
    ordered = sorted(by_class.items(), key=lambda kv: not any(c.verdict.strict for c in kv[1]))  # tri stable
    for key, members in ordered[:max_classes]:
        members.sort(key=lambda c: not c.verdict.strict)
        found = 0
        for cand in members[:tries_per_class]:
            for layout in fill_zones(cand, zones, ensuite, grid=grid, min_side=min_side):
                if len(layout) == expected and hard_check(layout, width, depth, min_side, conventions) is None:
                    refine(layout, targets, width, depth, grid, min_side, conventions)
                    if baseline is not None and not exact_ok(layout, width, depth, baseline):
                        continue
                    out.append(Realization(cand.tree, cand.rects, layout, key[0], key[1],
                                           thin_count(layout, min_side), cand.verdict.strict,
                                           z.arrangement_code(cand.rects, width, depth)))
                    found += 1
                    break
            if found >= per_class:
                break
    return out


# --- Contrôle exact, second temps --------------------------------------------

def compliance_failures(rooms: list[Room], width: float, depth: float) -> set[str]:
    """Clés des contrôles de `compliance` qui échouent sur ce plan (murs et portes générés)."""
    from app.plan_openings import default_openings
    from app.plan_walls import perimeter_and_internal_walls

    from . import compliance

    walls = perimeter_and_internal_walls(rooms, width, depth)
    openings = default_openings(walls, width, depth, rooms)
    doc = {
        "floor": {"level": 0, "height_m": 2.7, "bounds": {"width": width, "depth": depth}},
        "walls": walls,
        "rooms": [{"id": r.get("id"), "name": r.get("name"), "type": r.get("type"), "polygon": r["polygon"]} for r in rooms],
        "openings": openings,
    }
    return {c["key"] for c in compliance.evaluate(doc)["checks"] if not c["ok"]}


def compliance_regressions(
    rooms: list[Room], width: float, depth: float, baseline: set[str]
) -> set[str]:
    """Contrôles que ce plan fait échouer et que le gabarit classique réussit."""
    return compliance_failures(rooms, width, depth) - baseline


MIN_WC_KITCHEN_GAP = 1.5  # m : un couloir seul ne suffit pas à éloigner le WC de la cuisine
MIN_WC_WALL = 0.05     # au-delà d'un simple coin, un mur commun WC / séjour est refusé

# Pièces qu'on peut traverser pour en atteindre une autre ; les chambres ne donnent que sur une salle d'eau.
_TRANSIT = {"hallway", "living", "dining"}
_ENSUITE = {"bathroom", "wc"}


def door_issues(rooms: list[Room], width: float, depth: float) -> set[str]:
    """Défauts de circulation du plan une fois murs et portes générés.

    * ``exterieure:<id>`` — une porte extérieure autre que l'entrée et la porte de
      garage. `default_openings` en ouvre une pour toute pièce qui n'aurait aucune
      porte autorisée vers ses voisines : la pièce n'est alors accessible que par
      le jardin ;
    * ``inaccessible:<id>`` — une pièce que les portes ne relient pas à l'entrée ;
    * ``traversee:<id>`` — une pièce qu'on n'atteint qu'en traversant une chambre, une
      cuisine ou une autre pièce privée (hors salle d'eau attenante à une chambre) ;
    * ``garage_sans_porte:<id>`` — un garage sans porte extérieure : `default_openings`
      n'en ouvre une que sur une façade assez longue et qui évite l'entrée.

    C'est un contrôle de circulation, que `compliance` ne fait pas : elle ne
    regarde que les murs communs, jamais les portes.
    """
    from app.plan_openings import _served_rooms, default_openings
    from app.plan_walls import perimeter_and_internal_walls

    walls = perimeter_and_internal_walls(rooms, width, depth)
    openings = default_openings(walls, width, depth, rooms)
    by_id = {str(w.get("id")): w for w in walls}
    links: dict[int, set[int]] = {id(r): set() for r in rooms}
    issues: set[str] = set()
    entrance: list[Room] = []
    entrance_seen = False
    garage_served: set[int] = set()
    for op in openings:
        if op.get("type") != "door":
            continue
        wall = by_id.get(str(op.get("wall_id")))
        if wall is None:
            continue
        served = _served_rooms(wall, op, rooms)
        if str(wall["id"]).startswith("w_outer"):
            if wall["id"] == "w_outer_3" and not entrance_seen:
                entrance_seen = True           # `default_openings` pose l'entrée en premier
                entrance += served
            elif served and all(r["type"] == "garage" for r in served):
                garage_served |= {id(r) for r in served}
            else:
                issues |= {f"exterieure:{r.get('id')}" for r in served}
        elif len(served) == 2:
            a, b = served
            links[id(a)].add(id(b))
            links[id(b)].add(id(a))
    # Deux segments de couloir voisins n'ont pas de mur entre eux : ils sont reliés sans porte.
    halls = [r for r in rooms if r["type"] == "hallway"]
    for i, a in enumerate(halls):
        for b in halls[i + 1:]:
            if _shared_wall(a, b) > MIN_WC_WALL:
                links[id(a)].add(id(b))
                links[id(b)].add(id(a))
    reached = {id(r) for r in entrance}
    frontier = list(reached)
    while frontier:
        for nxt in links.get(frontier.pop(), ()):
            if nxt not in reached:
                reached.add(nxt)
                frontier.append(nxt)
    issues |= {f"inaccessible:{r.get('id')}" for r in rooms if id(r) not in reached}
    # Traversée : on ne traverse que les pièces de circulation ; une chambre ne mène qu'à sa
    # salle d'eau (suite). Une pièce atteignable seulement à travers une autre pièce privée
    # est une pièce qu'on ne peut atteindre qu'en passant par une chambre, une cuisine, etc.
    # On ne signale que les chambres : ailleurs (couloir atteint par un rangement) c'est bénin.
    kind = {id(r): r["type"] for r in rooms}
    open_seen = {id(r) for r in entrance}
    frontier = list(open_seen)
    while frontier:
        cur = frontier.pop()
        for nxt in links.get(cur, ()):
            if nxt in open_seen:
                continue
            if kind[cur] in _TRANSIT or (kind[cur] == "bedroom" and kind[nxt] in _ENSUITE):
                open_seen.add(nxt)
                frontier.append(nxt)
    issues |= {f"traversee:{r.get('id')}" for r in rooms
               if r["type"] == "bedroom" and id(r) in reached and id(r) not in open_seen}
    issues |= {f"garage_sans_porte:{r.get('id')}" for r in rooms
               if r["type"] == "garage" and id(r) not in garage_served}
    return issues


@dataclass(frozen=True)
class Baseline:
    """Ce que le gabarit classique réussit et rate pour le même programme."""

    failures: set[str]      # contrôles de `compliance` qu'il fait échouer
    doors: set[str]         # défauts de circulation qu'il présente


def classic_baseline(rooms: list[Room], width: float, depth: float, *,
                     grid: float = 0.1, min_side: float = 1.6) -> Baseline:
    """Référence du gabarit classique : un parti n'est retenu que s'il ne fait pas pire."""
    plot_w, plot_d = _plot(width, depth, grid, min_side)
    classic = lo.pack_house([dict(r) for r in rooms], width, depth, grid=grid, min_side=min_side)
    return Baseline(compliance_failures(classic, plot_w, plot_d), door_issues(classic, plot_w, plot_d))


def _shared_wall(a: Room, b: Room) -> float:
    """Longueur du mur commun de deux pièces rectangulaires (0 si elles ne se touchent pas)."""
    x0, y0, x1, y1 = _bbox(a)
    u0, v0, u1, v1 = _bbox(b)
    if abs(x1 - u0) < 1e-6 or abs(u1 - x0) < 1e-6:
        return max(0.0, min(y1, v1) - max(y0, v0))
    if abs(y1 - v0) < 1e-6 or abs(v1 - y0) < 1e-6:
        return max(0.0, min(x1, u1) - max(x0, u0))
    return 0.0


def wc_touches_living(rooms: list[Room]) -> bool:
    """Un WC qui partage un mur avec le séjour : il donne, en pratique, sur la pièce de vie.

    Aucune règle de `compliance` ne l'interdit, mais c'est ce qu'un client voit d'abord. Mesuré :
    22 % des partis en avaient un, contre 3 % des plans classiques.
    """
    wcs = [r for r in rooms if r["type"] == "wc"]
    livings = [r for r in rooms if r["type"] == "living"]
    return any(_shared_wall(w, v) > MIN_WC_WALL for w in wcs for v in livings)


def _gap(a: Room, b: Room) -> float:
    """Distance entre les rectangles englobants de deux pièces (0 si elles se touchent, même d'un coin)."""
    x0, y0, x1, y1 = _bbox(a)
    u0, v0, u1, v1 = _bbox(b)
    dx = max(u0 - x1, x0 - u1, 0.0)
    dy = max(v0 - y1, y0 - v1, 0.0)
    return (dx * dx + dy * dy) ** 0.5


def wc_near_kitchen(rooms: list[Room]) -> bool:
    """Un WC à moins de `MIN_WC_KITCHEN_GAP` de la cuisine ou de la salle à manger.

    La règle `wc_kitchen` ne voit que le mur commun : un WC de l'autre côté d'un couloir, ou qui
    ne touche la cuisine que par un angle, passe. Mesuré : 46 % des partis avaient leur WC à plus de
    3 m de la cuisine, contre 83 % des plans classiques.
    """
    wcs = [r for r in rooms if r["type"] == "wc"]
    food = [r for r in rooms if r["type"] in {"kitchen", "dining"}]
    return any(_gap(w, k) < MIN_WC_KITCHEN_GAP for w in wcs for k in food)


def exact_ok(layout: list[Room], width: float, depth: float, baseline: Baseline) -> bool:
    """Second temps du contrôle exact : ni régression de conformité, ni défaut de circulation nouveau, ni WC contre le séjour ou près de la cuisine."""
    if compliance_regressions(layout, width, depth, baseline.failures) or wc_touches_living(layout)             or wc_near_kitchen(layout):
        return False
    issues = door_issues(layout, width, depth)
    # Une chambre à traverser n'est jamais admise, même si le classique l'a : c'est le défaut
    # qu'un parti doit corriger, pas hériter. Sans parti propre, `adapt` retombe sur le classique.
    return not issues - baseline.doors and not any(i.startswith("traversee:") for i in issues)
