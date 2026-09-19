"""Packer résidentiel : zones nuit / circulation / jour (pas un BSP naïf).

Convention du dessin (origine en haut à gauche, y vers le sud) :
  y = 0     → nord / fond de parcelle (chambres)
  y = depth → sud / jardin + entrée
  x = 0     → ouest (cuisine en zone jour, SDB au-dessus)
  x = width → est (WC, parentale, garage)

Règles sanitaires / distribution (RSD type, décret logement décent, usage courant) :
  - le WC ne partage pas de mur avec cuisine ni salle à manger ;
  - la salle de bain ne partage pas de mur avec cuisine ni salle à manger ;
  - les chambres ne donnent pas sur le séjour : un couloir les sépare ;
  - chaque chambre et chaque WC s'ouvrent sur la circulation, pas l'un dans l'autre.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

from .layout_rules import (
    HABITABLE_TYPES,
    RULES,
    WET_TYPES,
    ForbiddenPair,
    NeedsHall,
    forbidden_pairs,
    types_needing_hall,
)

GRID = 0.5
MIN_SIDE = 2.0
_EPS = 1e-6
# Dérivés de `layout_rules` : les règles sont déclarées une fois, là-bas.
HABITABLE = set(HABITABLE_TYPES)
WET = set(WET_TYPES)
# Types dont `sanitary_violations` exige un bord partagé avec le couloir.
_NEEDS_CIRCULATION = types_needing_hall()
# Autorise le découpage d'une bande en plusieurs colonnes. `pack_house` le
# coupe le temps d'un second essai quand le premier introduit un écart
# sanitaire : `_band_score` ne voit que sa propre bande, pas les adjacences
# entre bandes voisines. `ContextVar` et non une globale : le service sert des
# requêtes concurrentes (fil de travail + handlers), une globale serait une
# course.
_ALLOW_COLUMNS: ContextVar[bool] = ContextVar("layout_allow_columns", default=True)

# Paires dont `sanitary_violations` interdit le mur commun.
_FORBIDDEN_ADJACENCY = forbidden_pairs()


def _snap(v: float, grid: float = GRID) -> float:
    g = grid if grid > 0 else GRID
    return round(max(0.0, v) / g) * g


def _box(x0: float, y0: float, x1: float, y1: float) -> list[dict[str, float]]:
    return [
        {"x": x0, "y": y0},
        {"x": x1, "y": y0},
        {"x": x1, "y": y1},
        {"x": x0, "y": y1},
    ]


def _min_side(typ: str, default: float) -> float:
    return {
        "wc": min(1.4, default) if default < 1.5 else 1.4,
        "bathroom": min(1.5, default) if default < 1.6 else 1.5,
        "laundry": 1.5,
        "storage": 1.4,
        "hallway": 1.1,
        "kitchen": 2.2,
        "garage": 3.0,
        "bedroom": 2.6,
        "living": 3.0,
        "dining": 2.2,
        "office": 2.2,
    }.get(typ, default)


def _place(room: dict[str, Any], x0: float, y0: float, x1: float, y1: float, grid: float) -> dict[str, Any]:
    """Rectangle jointif dans la bande [x0, x1] x [y0, y1] telle qu'elle est donnée.

    Le calage sur la grille se fait en amont, dans `_splits` : le refaire ici
    écrasait les bornes d'une bande plus étroite que le pas de grille, puis la
    pièce était réélargie d'un pas de grille — elle sortait de sa bande et
    recouvrait la voisine. On remet donc seulement les bornes dans l'ordre et
    on garantit 1 cm d'épaisseur, sans jamais élargir d'un pas de grille.
    """
    _ = grid
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    x0, y0 = round(x0, 2), round(y0, 2)
    x1, y1 = round(max(x1, x0 + 0.01), 2), round(max(y1, y0 + 0.01), 2)
    out = dict(room)
    out["polygon"] = _box(x0, y0, x1, y1)
    out["area_m2"] = round((x1 - x0) * (y1 - y0), 2)
    return out


def _weights(items: list[dict[str, Any]]) -> list[float]:
    return [max(float(it.get("area") or it.get("area_m2") or 8), 2.0) for it in items]


def _splits(span: float, weights: list[float], mins: list[float], grid: float) -> list[float]:
    """Bornes [0, s1, s2, ..., span] d'une division proportionnelle, mins respectés si possible."""
    n = len(weights)
    if n <= 0:
        return [0.0, span]
    if n == 1:
        return [0.0, span]
    total = sum(weights) or float(n)
    raw = [span * w / total for w in weights]
    need = sum(max(0.0, m - r) for r, m in zip(raw, mins, strict=True))
    extra = sum(max(0.0, r - m) for r, m in zip(raw, mins, strict=True))
    sizes = []
    for r, m in zip(raw, mins, strict=True):
        if r < m and extra > 1e-9:
            sizes.append(m)
        elif r > m and need > 1e-9:
            take = (r - m) * min(1.0, need / extra)
            sizes.append(max(m, r - take))
        else:
            sizes.append(max(m * 0.5, r))
    ssum = sum(sizes) or 1.0
    sizes = [span * s / ssum for s in sizes]
    pos = [0.0]
    acc = 0.0
    for s in sizes[:-1]:
        acc += s
        pos.append(_snap(acc, grid))
    pos.append(span)
    return _monotone(pos, span, grid, mins)


def _floors(span: float, mins: list[float], grid: float) -> list[float]:
    """Largeur plancher réellement garantie à chaque pièce d'une bande.

    `_splits` renormalisait les tailles sur la bande (`span * s / ssum`), ce qui
    ré-écrasait tous les minimums qu'il venait d'appliquer : on obtenait des
    chambres de 0,7 m et des couloirs de 0,4 m. On garde donc les minimums, en
    les réduisant proportionnellement (et seulement alors) quand la bande est
    trop courte pour les tenir tous.
    """
    n = len(mins)
    if n <= 0:
        return []
    base = [max(0.0, m) for m in mins]
    total = sum(base)
    if total > span > 0:
        base = [m * span / total for m in base]
    floor = min(grid if grid > 0 else GRID, span / n)
    base = [max(m, floor) for m in base]
    total = sum(base)
    if total > span > 0:
        base = [m * span / total for m in base]
    return base


def _monotone(pos: list[float], span: float, grid: float, mins: list[float]) -> list[float]:
    """Bornes croissantes, toutes dans [0, span], extrémités exactes.

    L'ancienne version décollait chaque borne de la précédente d'un pas de
    grille *sans plafond* : sur une bande étroite les dernières bornes
    sortaient de la bande (`pos[-1] > span`), la pièce correspondante était
    posée au-delà de sa colonne et recouvrait la voisine — ou débordait de
    l'emprise.
    """
    n = len(pos) - 1
    span = max(0.0, span)
    if n <= 0:
        return [0.0, span]
    floors = _floors(span, mins, grid) if len(mins) == n else [span / n] * n
    tail = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        tail[i] = tail[i + 1] + floors[i]
    out = [0.0]
    for i in range(1, n):
        lo = out[-1] + floors[i - 1]
        hi = span - tail[i]
        out.append(min(max(pos[i], lo), max(lo, hi)))
    out.append(span)
    return out


def _stack(
    items: list[dict[str, Any]],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    grid: float,
    default_min: float,
) -> list[dict[str, Any]]:
    if not items:
        return []
    span = y1 - y0
    mins = [_min_side(str(it.get("type") or ""), default_min) for it in items]
    pos = _splits(span, _weights(items), mins, grid)
    return [
        _place(it, x0, y0 + pos[i], x1, y0 + pos[i + 1], grid)
        for i, it in enumerate(items)
    ]


def _row(
    items: list[dict[str, Any]],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    grid: float,
    default_min: float,
) -> list[dict[str, Any]]:
    if not items:
        return []
    span = x1 - x0
    mins = [_min_side(str(it.get("type") or ""), default_min) for it in items]
    pos = _splits(span, _weights(items), mins, grid)
    return [
        _place(it, x0 + pos[i], y0, x0 + pos[i + 1], y1, grid)
        for i, it in enumerate(items)
    ]


def _split_consecutive(items: list[dict[str, Any]], k: int) -> list[list[dict[str, Any]]]:
    """`k` groupes consécutifs, équilibrés en aire, dans l'ordre reçu.

    L'ordre porte la sémantique de zonage (`_day_sequence`, `_night_private`,
    `_food_off_east`) : on ne regroupe donc que des voisins, jamais en
    réordonnant.
    """
    n = len(items)
    k = max(1, min(k, n))
    if k == 1:
        return [list(items)]
    weights = _weights(items)
    total = sum(weights) or float(n)
    groups: list[list[dict[str, Any]]] = [[]]
    cum = 0.0
    for i, item in enumerate(items):
        groups[-1].append(item)
        cum += weights[i]
        need_open = k - len(groups)
        remaining = n - i - 1
        # On ferme le groupe quand sa part d'aire est servie, ou quand il faut
        # réserver une pièce à chacun des groupes encore à ouvrir.
        if need_open > 0 and (remaining <= need_open or cum >= total * len(groups) / k - _EPS):
            groups.append([])
    return [g for g in groups if g]


def _forbidden_count(rooms: list[dict[str, Any]]) -> int:
    """Nombre d'adjacences interdites réalisées dans un lot de pièces.

    Mêmes paires que `sanitary_violations`, déclarées une fois dans
    `_FORBIDDEN_ADJACENCY`. En une seule rangée, `_food_off_east` suffisait à
    les éviter ; dès qu'une bande peut passer en colonnes, il faut les compter.
    """
    total = 0
    for left, right in _FORBIDDEN_ADJACENCY:
        a = [r for r in rooms if str(r.get("type") or "") in left]
        b = [r for r in rooms if str(r.get("type") or "") in right]
        for ra in a:
            for rb in b:
                if ra is not rb and share_edge(ra, rb):
                    total += 1
    return total


def _band_score(rooms: list[dict[str, Any]], default_min: float) -> tuple[int, int, float]:
    """(adjacences interdites, pièces sous le côté minimal, pire allongement).

    Ordre lexicographique : une règle sanitaire ne se négocie pas, un côté
    minimal est un plancher d'habitabilité, l'allongement n'est qu'une
    préférence de proportion.
    """
    violations = 0
    worst = 1.0
    for room in rooms:
        box = _room_bbox(room)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        short, long = min(x1 - x0, y1 - y0), max(x1 - x0, y1 - y0)
        if short + _EPS < _min_side(str(room.get("type") or ""), default_min):
            violations += 1
        if short > _EPS:
            worst = max(worst, long / short)
    return _forbidden_count(rooms), violations, worst


def _pack_band(
    items: list[dict[str, Any]],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    grid: float,
    default_min: float,
) -> list[dict[str, Any]]:
    """Pave une bande en colonnes empilées, le nombre de colonnes étant choisi.

    `_row` ne découpait la bande que dans la largeur : quatre chambres
    donnaient quatre colonnes en peigne, et sur une bande étroite plus aucun
    côté minimal ne tenait — 920 des 925 violations mesurées portaient sur la
    largeur. On essaie donc toutes les répartitions en `k` colonnes, chacune
    empilée par `_stack`, et on garde la meilleure.

    `k = len(items)` reproduit exactement l'ancien comportement de `_row` :
    cette disposition est toujours dans les candidats, donc la recherche ne
    peut pas faire moins bien qu'avant.
    """
    if not items:
        return []
    if len(items) == 1:
        return [_place(items[0], x0, y0, x1, y1, grid)]

    # Les chambres et les WC doivent s'ouvrir sur la circulation, qui borde la
    # bande — une seule rangée touche ce bord. Empiler mettrait les pièces du
    # fond hors d'atteinte du couloir (`bedroom_hall`, `wc_hall`). Les mettre
    # en deux rangées demanderait de faire passer le couloir entre elles, donc
    # de changer la topologie : c'est le travail de dualisation, pas celui-ci.
    if not _ALLOW_COLUMNS.get():
        return _row(items, x0, y0, x1, y1, grid, default_min)
    if any(str(it.get("type") or "") in _NEEDS_CIRCULATION for it in items):
        return _row(items, x0, y0, x1, y1, grid, default_min)

    best: list[dict[str, Any]] | None = None
    best_score: tuple[int, int, float] | None = None
    for k in range(1, len(items) + 1):
        groups = _split_consecutive(items, k)
        if len(groups) != k:
            continue  # k inatteignable sans groupe vide
        weights = [sum(_weights(g)) for g in groups]
        mins = [
            max(_min_side(str(it.get("type") or ""), default_min) for it in g)
            for g in groups
        ]
        pos = _splits(x1 - x0, weights, mins, grid)
        out: list[dict[str, Any]] = []
        for j, group in enumerate(groups):
            out.extend(
                _stack(group, x0 + pos[j], y0, x0 + pos[j + 1], y1, grid, default_min)
            )
        score = _band_score(out, default_min)
        if best_score is None or score < best_score:
            best_score, best = score, out
    return best if best is not None else _row(items, x0, y0, x1, y1, grid, default_min)


def _first(items: list[dict[str, Any]], typ: str) -> dict[str, Any] | None:
    return next((it for it in items if it.get("type") == typ), None)


def _all(items: list[dict[str, Any]], typ: str) -> list[dict[str, Any]]:
    return [it for it in items if it.get("type") == typ]


# --- Variantes de pavage ("partis") -----------------------------------------
# Un parti est une façon d'arranger les grandes zones d'un plan. Le gabarit
# actuel (nuit au nord, couloir, jour au sud) est le parti « classic » ; c'est le
# comportement par défaut et il n'est jamais désigné explicitement dans un plan.
# Les autres partis se déclarent avec `register_parti` (module `layout_partis`).
#
# Le descripteur d'une variante est un petit dictionnaire JSON,
# ``{"parti": "central-hall", "seed": 3}``. Il est écrit dans le plan
# (`plan_document["layout"]`) pour que `plan_adapt` et la retouche re-pavent
# avec le MÊME parti : sans cela, `adapt` refait tout depuis les types et les
# aires et efface la topologie choisie à la génération.
CLASSIC = "classic"
_PARTI_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_MAX_SEED = 2**31 - 1
# Arrangement de zones tel que `layout_zones.arrangement_code` l'écrit, mémorisé dans le
# plan pour que la retouche retrouve le même arrangement.
_ARRANGEMENT = re.compile(r"^night:[NSEWC-]\|day:[NSEWC-]\|hall:[HV-]\|garage:[NSEWC-]$")


class UnknownParti(ValueError):
    """Le descripteur nomme un parti qui n'est pas enregistré.

    Sous-classe de `ValueError` : les endpoints `/v1/*` traduisent déjà cette
    erreur en HTTP 422 (`main._run_stage`) au lieu d'un 500.
    """


class PartiUnavailable(Exception):
    """Le parti demandé ne peut pas réaliser CE plan (parcelle étroite, aucun arrangement valide).

    Ce n'est pas une erreur d'entrée, donc pas une `ValueError` : `plan_adapt` retombe
    sur le gabarit classique, qui réalise toujours un plan.
    """


PartiFn = Callable[
    [list[dict[str, Any]], float, float, float, float, dict[str, Any]],
    list[dict[str, Any]],
]
_PARTIS: dict[str, PartiFn] = {}


def register_parti(name: str) -> Callable[[PartiFn], PartiFn]:
    """Décorateur : déclare `fn(rooms, width, depth, grid, min_side, variant)` comme parti `name`."""
    if name == CLASSIC or not _PARTI_NAME.match(name):
        raise ValueError(f"nom de parti invalide: {name!r}")

    def deco(fn: PartiFn) -> PartiFn:
        _PARTIS[name] = fn
        return fn

    return deco


def normalize_variant(variant: Any) -> dict[str, Any] | None:
    """Descripteur validé, ou None pour le gabarit classique.

    `None`, `{}` et `{"parti": "classic"}` désignent le comportement par défaut :
    on renvoie None, de sorte que le plan produit n'a **pas** de champ `layout`
    et reste identique octet pour octet à celui d'avant cette fonctionnalité.

    Le descripteur vient de documents libres (`/v1/adapt`) : type, nom et graine
    sont validés, une valeur aberrante lève `ValueError`.
    """
    if variant is None:
        return None
    if not isinstance(variant, dict):
        raise ValueError("layout: objet attendu")
    parti = variant.get("parti", CLASSIC)
    if not isinstance(parti, str) or not (parti == CLASSIC or _PARTI_NAME.match(parti)):
        raise ValueError("layout.parti: nom invalide")
    seed = variant.get("seed", 0)
    # bool est un sous-type de int : `True` passerait pour la graine 1.
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= _MAX_SEED:
        raise ValueError("layout.seed: entier entre 0 et 2^31-1 attendu")
    if parti == CLASSIC:
        return None
    out: dict[str, Any] = {"parti": parti, "seed": seed}
    arr = variant.get("arr")
    if arr is not None:
        if not isinstance(arr, str) or not _ARRANGEMENT.match(arr):
            raise ValueError("layout.arr: arrangement invalide")
        out["arr"] = arr
    return out


def _load_builtin_partis() -> None:
    """Importe les partis livrés avec le service : ils s'enregistrent à l'import.

    Import tardif : `layout_select` importe `layout_opt`, un import au chargement serait
    circulaire.
    """
    from . import layout_select  # noqa: F401


def pack_house(
    rooms: list[dict[str, Any]],
    width: float,
    depth: float,
    grid: float = GRID,
    min_side: float = MIN_SIDE,
    variant: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Pavé orthogonal jointif : nuit au nord, couloir, jour au sud.

    `variant` choisit un autre parti d'aménagement (cf. `normalize_variant`) ;
    sans lui, c'est le gabarit classique, inchangé.
    """
    if not rooms:
        return []
    chosen = normalize_variant(variant)
    if chosen is not None:
        fn = _PARTIS.get(chosen["parti"])
        if fn is None:
            _load_builtin_partis()
            fn = _PARTIS.get(chosen["parti"])
        if fn is None:
            raise UnknownParti(f"parti inconnu: {chosen['parti']!r}")
        return fn(rooms, width, depth, grid, min_side, chosen)
    width = _snap(max(width, min_side * 2), grid)
    depth = _snap(max(depth, min_side * 2), grid)
    items: list[dict[str, Any]] = []
    for room in rooms:
        it = dict(room)
        it["type"] = str(room.get("type") or "other")
        it["name"] = room.get("name") or it["type"]
        it["area"] = max(float(room.get("area_m2") or 12), 2.0)
        items.append(it)
    if len(items) == 1:
        return [_place(items[0], 0.0, 0.0, width, depth, grid)]

    beds = _all(items, "bedroom")
    baths = _all(items, "bathroom")
    wcs = _all(items, "wc")
    laundries = _all(items, "laundry")
    storages = _all(items, "storage")
    offices = _all(items, "office")
    dinings = _all(items, "dining")
    hallways = _all(items, "hallway")
    livings = _all(items, "living")
    kitchens = _all(items, "kitchen")
    garages = _all(items, "garage")
    living = livings[0] if livings else None
    kitchen = kitchens[0] if kitchens else None
    garage = garages[0] if garages else None
    leftovers = [
        it for it in items
        if it.get("type") not in {
            "bedroom", "bathroom", "wc", "laundry", "storage", "office",
            "dining", "hallway", "living", "kitchen", "garage",
        }
    ]
    # Une 2ᵉ cuisine / un 2ᵉ séjour / un 2ᵉ garage n'étaient portés par aucune
    # liste (`_first` n'en garde qu'un) : la pièce disparaissait du plan sans
    # le moindre signal. On les traite comme des pièces jour supplémentaires.
    leftovers.extend(kitchens[1:] + livings[1:] + garages[1:])
    ensuite = baths[-1] if len(baths) >= 2 and beds else None
    day_baths = baths[:-1] if ensuite else baths
    hallways = _ensure_hallway(hallways, beds, living, kitchen, wcs, dinings)
    args = (
        beds, day_baths, ensuite, wcs, laundries, storages, offices, dinings,
        hallways, leftovers, living, kitchen, garage,
        width, depth, grid, min_side,
    )
    packed = _pack_zoned(*args)
    issues = sanitary_violations(packed)
    if issues:
        # Le découpage en colonnes a pu créer une adjacence interdite entre
        # deux bandes. On réessaie en une seule rangée par bande — l'ancien
        # comportement — et on garde le meilleur des deux.
        token = _ALLOW_COLUMNS.set(False)
        try:
            single = _pack_zoned(*args)
        finally:
            _ALLOW_COLUMNS.reset(token)
        if len(sanitary_violations(single)) < len(issues):
            packed = single
    return _clip_footprint(packed, width, depth)


def _clip_footprint(
    rooms: list[dict[str, Any]], width: float, depth: float
) -> list[dict[str, Any]]:
    """Dernier garde-fou : aucune pièce ne dépasse l'emprise (rétrécit seulement).

    Les bandes sont désormais calculées pour rester dedans ; cette passe évite
    qu'une future régression n'expédie un mur hors de la parcelle sans que
    personne ne le voie. Elle ne fait que rogner, donc ne peut pas créer de
    recouvrement.
    """
    for room in rooms:
        box = _room_bbox(room)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        cx0, cy0 = max(0.0, min(x0, width)), max(0.0, min(y0, depth))
        cx1, cy1 = max(0.0, min(x1, width)), max(0.0, min(y1, depth))
        if (cx0, cy0, cx1, cy1) == (x0, y0, x1, y1):
            continue
        room["polygon"] = _box(round(cx0, 2), round(cy0, 2), round(cx1, 2), round(cy1, 2))
        room["area_m2"] = round(max(0.0, cx1 - cx0) * max(0.0, cy1 - cy0), 2)
    return rooms


def _ensure_hallway(
    hallways: list[dict[str, Any]],
    beds: list[dict[str, Any]],
    living: dict[str, Any] | None,
    kitchen: dict[str, Any] | None,
    wcs: list[dict[str, Any]],
    dinings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Couloir obligatoire dès qu'il y a des chambres, ou un WC à séparer de la cuisine.

    La salle à manger compte au même titre que la cuisine : la règle sanitaire
    interdit le mur commun WC / salle à manger, et sans couloir le WC n'avait
    aucune pièce sur laquelle s'ouvrir (porte impossible, pièce enclavée).
    """
    if hallways:
        return hallways
    if beds or (wcs and (kitchen or living or dinings)):
        return [{
            "id": "r_hall",
            "type": "hallway",
            "name": "Couloir",
            "area": 8.0,
            "area_m2": 8.0,
        }]
    return hallways


def _pack_zoned(
    beds: list[dict[str, Any]],
    day_baths: list[dict[str, Any]],
    ensuite: dict[str, Any] | None,
    wcs: list[dict[str, Any]],
    laundries: list[dict[str, Any]],
    storages: list[dict[str, Any]],
    offices: list[dict[str, Any]],
    dinings: list[dict[str, Any]],
    hallways: list[dict[str, Any]],
    leftovers: list[dict[str, Any]],
    living: dict[str, Any] | None,
    kitchen: dict[str, Any] | None,
    garage: dict[str, Any] | None,
    width: float,
    depth: float,
    grid: float,
    min_side: float,
) -> list[dict[str, Any]]:
    """Nuit (nord) + couloir + jour (sud). WC invités sur le couloir, pas dans une chambre."""
    garage_w = 0.0
    if garage:
        garage_w = max(3.2, min(width * 0.28, float(garage.get("area") or 18) / max(depth, 1.0)))
        garage_w = _snap(garage_w, grid)
        if garage_w > width - 6.0:
            garage_w = _snap(max(3.2, width * 0.24), grid)
        # Bande garage non vide : sur une emprise minimale `inner_w` valait
        # `width`, le garage était posé sur une bande de largeur nulle puis
        # élargi d'un pas de grille — hors de l'emprise.
        garage_w = min(max(garage_w, grid), max(grid, width - grid))
    inner_w = max(min_side * 2, width - garage_w)
    if garage:
        inner_w = min(inner_w, max(grid, width - grid))

    has_night = bool(beds or offices)
    guest = list(wcs) + list(laundries) + list(storages)
    leftovers = list(leftovers)
    hall_d = 0.0
    if hallways and (has_night or guest or (wcs and kitchen)):
        hall_d = _snap(min(1.5, max(1.4 if guest else 1.15, depth * 0.12)), grid)
        if depth - hall_d < (2.8 if has_night else 2.2) + 2.4:
            hall_d = _snap(max(1.4 if guest else 1.1, min(1.4, depth * 0.12)), grid)
        # Le couloir doit rester dans l'emprise et laisser de la place au reste.
        hall_d = min(max(hall_d, grid), max(grid, depth - 2 * grid))

    wet_w = 0.0
    if has_night and guest and hall_d > 0:
        wet_w = sum(_weights(guest)) / max(hall_d, 1.4)
        wet_w = _snap(max(1.6, min(inner_w * 0.30, wet_w)), grid)
        wet_w = min(wet_w, max(1.6, inner_w - 4.5))
        wet_w = min(max(wet_w, grid), max(grid, inner_w - grid))
    out: list[dict[str, Any]] = []
    if has_night:
        if guest and not wet_w:
            # Pas de bande humide (aucun couloir à desservir) : sans ce repli
            # les WC / buanderies / rangements n'étaient posés nulle part et
            # disparaissaient purement et simplement du plan rendu.
            leftovers = leftovers + guest
            guest = []
        if not (hallways and hall_d > 0):
            # Sans ce repli le couloir n'était rattaché à aucune rangée et
            # disparaissait du plan.
            leftovers = leftovers + list(hallways)
            hall_d = 0.0
        day_seq = _day_sequence(kitchen, living, dinings, leftovers)
        night_d = _snap(max(2.8, min(depth * 0.38, depth - hall_d - 3.0)), grid)
        if night_d + hall_d >= depth - 2.4:
            night_d = _snap(max(2.6, depth - hall_d - 2.6), grid)
        # Bornée : `max(2.6, ...)` réclamait plus de profondeur qu'il n'y en
        # avait sur une petite emprise, et la rangée jour partait au-delà de
        # la façade sud (coordonnées inversées par `_place`).
        night_d = min(max(night_d, grid), max(grid, depth - hall_d - grid))
        if not day_seq:
            # Programme sans pièce jour : la bande sud restait un trou dans
            # l'emprise (jusqu'à 30 % de la surface non couverte). Nuit et
            # couloir se partagent alors toute la profondeur.
            night_d = max(grid, depth - hall_d)
        hall_x1 = inner_w - wet_w if wet_w else inner_w
        night_priv = _night_private(beds, offices, ensuite) + list(day_baths)
        if night_priv:
            out.extend(_pack_band(night_priv, 0.0, 0.0, hall_x1, night_d, grid, min_side))
        if ensuite:
            for room in out:
                if room.get("id") == ensuite.get("id"):
                    room["ensuite"] = True
        if wet_w and hallways:
            stub = dict(hallways[0])
            stub["id"] = str(stub.get("id") or "r_hall") + "_n"
            stub["name"] = stub.get("name") or "Couloir"
            out.append(_place(stub, hall_x1, 0.0, inner_w, night_d, grid))
        y_hall = night_d
        if hallways and hall_d > 0:
            out.extend(_pack_band(hallways, 0.0, y_hall, hall_x1, y_hall + hall_d, grid, 1.1))
            if guest and wet_w:
                out.extend(_pack_band(guest, hall_x1, y_hall, inner_w, y_hall + hall_d, grid, 1.4))
        y_day = y_hall + hall_d
        if day_seq and depth - y_day > _EPS:
            day_seq = _food_off_east(day_seq, guest if wet_w else [])
            # Ne pas allonger la rangée jour sous la bande WC : sinon cuisine
            # ou séjour collent le sud des toilettes (mur commun interdit).
            day_x1 = hall_x1 if (wet_w and guest) else inner_w
            out.extend(_pack_band(day_seq, 0.0, y_day, day_x1, depth, grid, min_side))
            if wet_w and guest and hallways and day_x1 < inner_w - _EPS:
                stub = dict(hallways[0])
                stub["id"] = str(stub.get("id") or "r_hall") + "_s"
                stub["name"] = stub.get("name") or "Couloir"
                out.append(_place(stub, day_x1, y_day, inner_w, depth, grid))
        elif not night_priv:
            filler = leftovers or day_baths
            if filler:
                out.append(_place(filler[-1], 0.0, y_day, inner_w, depth, grid))
    else:
        main = _day_sequence(kitchen, living, dinings, leftovers)
        main.extend(day_baths)
        main.extend(offices)
        if main and hallways and hall_d > 0:
            out.extend(_pack_band(_food_off_east(main, guest),
                            0.0, 0.0, inner_w, depth - hall_d, grid, min_side))
            if guest:
                wet_w = _snap(max(1.6, min(inner_w * 0.28, sum(_weights(guest)) / max(hall_d, 1.4))), grid)
                wet_w = min(max(wet_w, grid), max(grid, inner_w - grid))
                hall_x1 = inner_w - wet_w
                out.extend(_pack_band(hallways, 0.0, depth - hall_d, hall_x1, depth, grid, 1.1))
                out.extend(_pack_band(guest, hall_x1, depth - hall_d, inner_w, depth, grid, 1.4))
            else:
                out.extend(_pack_band(hallways, 0.0, depth - hall_d, inner_w, depth, grid, 1.1))
        else:
            # Sans cette branche, un plan sans zone nuit perdait ses couloirs
            # (et ses pièces de service) dès que la bande couloir n'était pas
            # calculée : ils n'étaient rattachés à aucune rangée.
            rest = main + list(hallways) + list(guest)
            if rest:
                out.extend(_pack_band(rest, 0.0, 0.0, inner_w, depth, grid, min_side))

    if garage:
        out.append(_place(garage, inner_w, 0.0, width, depth, grid))
    return _fill_gaps(out, width, depth, grid)


def _night_private(
    beds: list[dict[str, Any]],
    offices: list[dict[str, Any]],
    ensuite: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Chambres + ensuite : jamais le WC invités (celui-ci s'ouvre sur le couloir)."""
    extra = list(beds[:-1]) if (ensuite and beds) else list(beds)
    master = [beds[-1]] if (ensuite and beds) else []
    ens = [ensuite] if ensuite else []
    return extra + list(offices) + master + ens


_FOOD = {"kitchen", "dining"}


def _food_off_east(row: list[dict[str, Any]], guest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Écarte cuisine / salle à manger du bout est d'une rangée quand la bande
    WC vient s'y coller.

    La bande humide occupe l'est du couloir : la pièce en bout de rangée
    partage forcément un mur avec elle. Une cuisine ou une salle à manger à
    cet endroit produit le mur commun WC / cuisine interdit (RSD).
    """
    if not row or not any(str(g.get("type") or "") == "wc" for g in guest):
        return row
    if str(row[-1].get("type") or "") not in _FOOD:
        return row
    swap = next(
        (i for i in range(len(row) - 2, -1, -1) if str(row[i].get("type") or "") not in _FOOD),
        None,
    )
    if swap is None:
        return row
    row = list(row)
    row[swap], row[-1] = row[-1], row[swap]
    return row


def _day_sequence(
    kitchen: dict[str, Any] | None,
    living: dict[str, Any] | None,
    dinings: list[dict[str, Any]],
    leftovers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Cuisine à l'ouest, séjour au centre — jamais un WC dans cette rangée."""
    day: list[dict[str, Any]] = []
    if kitchen:
        day.append(kitchen)
    if living:
        day.append(living)
    day.extend(dinings)
    day.extend(leftovers)
    return day


def _floor_grid(v: float, grid: float) -> float:
    """Arrondi *par défaut* au pas de grille : ne réclame jamais plus que libre."""
    g = grid if grid > 0 else GRID
    return max(0.0, int(max(0.0, v) / g + 1e-9) * g)


def _free_edge(
    rooms: list[dict[str, Any]], target: dict[str, Any],
    box: tuple[float, float, float, float], axis: str, side: str,
    width: float, depth: float,
) -> float:
    """Coordonnée jusqu'où `box` peut s'étendre sans mordre sur une voisine.

    `axis` = "x" (est/ouest) ou "y" (nord/sud) ; `side` = "lo" (vers 0) ou "hi".
    Seules les pièces qui chevauchent la bande de `box` sur l'autre axe font
    obstacle : la pièce étendue reste ainsi un rectangle jointif, sans
    recouvrement.

    `box` est passé explicitement (et non relu depuis `target`) pour que les
    extensions successives se contrôlent entre elles : en calculant les quatre
    côtés sur la boîte d'origine, une voisine seulement diagonale n'obstruait
    ni l'axe x ni l'axe y, et l'agrandissement simultané des deux axes
    l'avalait — deux pièces superposées.
    """
    x0, y0, x1, y1 = box
    horizontal = axis == "x"
    near, far = (x0, x1) if horizontal else (y0, y1)
    limit = 0.0 if side == "lo" else (width if horizontal else depth)
    for other in rooms:
        if other is target:
            continue
        ob = _room_bbox(other)
        if ob is None:
            continue
        ox0, oy0, ox1, oy1 = ob
        if horizontal:
            if min(y1, oy1) - max(y0, oy0) <= 1e-6:
                continue  # pas en face : n'obstrue pas cette bande
            lo_edge, hi_edge = ox1, ox0
        else:
            if min(x1, ox1) - max(x0, ox0) <= 1e-6:
                continue
            lo_edge, hi_edge = oy1, oy0
        if side == "lo" and lo_edge <= near + 1e-6:
            limit = max(limit, lo_edge)
        elif side == "hi" and hi_edge >= far - 1e-6:
            limit = min(limit, hi_edge)
    return limit


def _fill_gaps(
    rooms: list[dict[str, Any]], width: float, depth: float, grid: float
) -> list[dict[str, Any]]:
    """Étend le séjour (ou la plus grande pièce) s'il reste un trou d'emprise.

    Les découpes proportionnelles de `_splits` laissent parfois une bande vide
    contre une façade. On l'absorbe dans une seule pièce, et seulement du côté
    où la bande est réellement libre : le résultat reste un rectangle jointif,
    sans recouvrement (c'était auparavant une fonction morte — elle calculait
    la pièce cible puis renvoyait `rooms` inchangé).
    """
    if not rooms:
        return rooms
    covered = sum(float(r.get("area_m2") or 0) for r in rooms)
    foot = width * depth
    if covered / max(foot, 1.0) >= 0.92:
        return rooms
    living = next((r for r in rooms if r.get("type") == "living"), None)
    target = living or max(rooms, key=lambda r: float(r.get("area_m2") or 0))
    box = _room_bbox(target)
    if box is None:
        return rooms
    prev_poly = list(target.get("polygon") or [])
    prev_area = target.get("area_m2")
    x0, y0, x1, y1 = box
    x0 -= _floor_grid(x0 - _free_edge(rooms, target, (x0, y0, x1, y1), "x", "lo", width, depth), grid)
    x1 += _floor_grid(_free_edge(rooms, target, (x0, y0, x1, y1), "x", "hi", width, depth) - x1, grid)
    y0 -= _floor_grid(y0 - _free_edge(rooms, target, (x0, y0, x1, y1), "y", "lo", width, depth), grid)
    y1 += _floor_grid(_free_edge(rooms, target, (x0, y0, x1, y1), "y", "hi", width, depth) - y1, grid)
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(width, x1), min(depth, y1)
    if x1 - x0 < grid or y1 - y0 < grid:
        return rooms
    target["polygon"] = _box(round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))
    target["area_m2"] = round((x1 - x0) * (y1 - y0), 2)
    if sanitary_violations(rooms):
        target["polygon"] = prev_poly
        target["area_m2"] = prev_area
    return rooms


def optimize_rooms(
    rooms: list[dict[str, Any]],
    width: float,
    depth: float,
    spec: dict[str, Any] | None = None,
    grid: float = GRID,
    min_side: float = MIN_SIDE,
    variant: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Réarrange les pièces en plan orthogonal jointif (topologie maison)."""
    _ = spec
    return pack_house(rooms, width, depth, grid=grid, min_side=min_side, variant=variant)


def _on_facade(poly: list[dict[str, float]], width: float, depth: float, tol: float = 0.15) -> bool:
    if len(poly) < 3:
        return False
    xs = [float(p["x"]) for p in poly]
    ys = [float(p["y"]) for p in poly]
    return min(xs) <= tol or min(ys) <= tol or max(xs) >= width - tol or max(ys) >= depth - tol


def place_habitables_on_facade(
    rooms: list[dict[str, Any]],
    width: float,
    depth: float,
) -> list[dict[str, Any]]:
    """Échange une pièce habitable intérieure avec une pièce technique en façade."""
    service = [r for r in rooms if r.get("type") not in HABITABLE]
    for room in rooms:
        if room.get("type") not in HABITABLE:
            continue
        if _on_facade(room.get("polygon") or [], width, depth):
            continue
        donor = next((s for s in service if _on_facade(s.get("polygon") or [], width, depth)), None)
        if donor is None:
            break
        room["polygon"], donor["polygon"] = donor["polygon"], room["polygon"]
        room["area_m2"], donor["area_m2"] = donor.get("area_m2"), room.get("area_m2")
        service = [s for s in service if s is not donor]
    return rooms


def _room_bbox(room: dict[str, Any]) -> tuple[float, float, float, float] | None:
    poly = room.get("polygon") or []
    if len(poly) < 3:
        return None
    xs = [float(p["x"]) for p in poly]
    ys = [float(p["y"]) for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def share_edge(a: dict[str, Any], b: dict[str, Any], *, tol: float = 0.15, min_seam: float = 0.55) -> bool:
    """True si deux pièces partagent un mur (pas seulement un coin)."""
    ba, bb = _room_bbox(a), _room_bbox(b)
    if not ba or not bb:
        return False
    ax0, ay0, ax1, ay1 = ba
    bx0, by0, bx1, by1 = bb
    y_ov = min(ay1, by1) - max(ay0, by0)
    x_ov = min(ax1, bx1) - max(ax0, bx0)
    x_touch = abs(ax1 - bx0) <= tol or abs(bx1 - ax0) <= tol
    y_touch = abs(ay1 - by0) <= tol or abs(by1 - ay0) <= tol
    return (x_touch and y_ov >= min_seam) or (y_touch and x_ov >= min_seam)


def sanitary_violations(rooms: list[dict[str, Any]]) -> list[str]:
    """Écarts de distribution (cuisine/WC, chambres/séjour, accès couloir).

    Interprète `layout_rules.RULES`, dans l'ordre de la déclaration : l'ordre et
    le comptage des écarts sont ceux du contrôleur d'origine, dont
    `tests/test_layout_rules.py` conserve une copie comme oracle.
    """
    issues: list[str] = []
    halls = [r for r in rooms if r.get("type") == "hallway"]
    for rule in RULES:
        if isinstance(rule, ForbiddenPair):
            rights = [r for r in rooms if r.get("type") in rule.right]
            for left in (r for r in rooms if r.get("type") in rule.left):
                if any(share_edge(left, right) for right in rights):
                    issues.append(rule.name)
                    if not rule.per_room:
                        break
        elif isinstance(rule, NeedsHall):
            if not halls:
                continue
            for room in (r for r in rooms if r.get("type") in rule.types):
                if not any(share_edge(room, hall) for hall in halls):
                    issues.append(rule.name)
                    break
    return issues
