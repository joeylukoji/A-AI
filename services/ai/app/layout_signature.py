"""Signature d'un plan : mesurer à quel point deux plans se ressemblent.

« Toutes les maisons se ressemblent » n'était qu'une impression. Ce module la
rend mesurable, à deux niveaux :

  * `zone_code` — l'arrangement des grandes zones (où sont la nuit, le jour, le
    garage, dans quel sens court le couloir). C'est à ce niveau que le gabarit
    actuel est identique d'un plan à l'autre.
  * `topology_signature` / `topology_distance` — qui touche qui, et quelle pièce
    donne sur quelle façade. Sert à comparer deux plans d'un même programme
    (diversité) ou d'une même parcelle vue sous deux formes (adaptation).

Convention du dessin, celle de `layout_opt` : origine en haut à gauche,
y = 0 au nord, y = depth au sud, x = 0 à l'ouest.

Aucune dépendance au reste du pipeline : le module ne lit que des polygones.
"""
from __future__ import annotations

from typing import Any

from .layout_opt import share_edge

# Zones par type de pièce. Les pièces humides (salle de bain, WC…) ne sont pas
# une zone : leur place suit celle des pièces qu'elles desservent.
NIGHT = {"bedroom", "office"}
DAY = {"living", "kitchen", "dining"}

# Une zone dont le centre de gravité est à moins de cette fraction du centre de
# l'emprise est dite centrale ('C') plutôt que rattachée à un bord.
_CENTRAL = 0.15
# Même tolérance que `layout_opt._on_facade`.
_FACADE_TOL = 0.15


def _bbox(room: dict[str, Any]) -> tuple[float, float, float, float] | None:
    poly = room.get("polygon") or []
    if len(poly) < 3:
        return None
    xs = [float(p["x"]) for p in poly]
    ys = [float(p["y"]) for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _dominant_side(
    rooms: list[dict[str, Any]], width: float, depth: float
) -> str:
    """Bord de l'emprise dont le centre de gravité de ces pièces est le plus proche.

    '-' si le lot est vide, 'C' si le centre de gravité est proche du centre.
    """
    total = cx = cy = 0.0
    for room in rooms:
        box = _bbox(room)
        if box is None:
            continue
        a = _area(box)
        total += a
        cx += a * (box[0] + box[2]) / 2.0
        cy += a * (box[1] + box[3]) / 2.0
    if total <= 0.0 or width <= 0.0 or depth <= 0.0:
        return "-"
    dx = (cx / total - width / 2.0) / (width / 2.0)
    dy = (cy / total - depth / 2.0) / (depth / 2.0)
    if max(abs(dx), abs(dy)) < _CENTRAL:
        return "C"
    if abs(dy) >= abs(dx):
        return "N" if dy < 0 else "S"
    return "W" if dx < 0 else "E"


def _hall_orientation(rooms: list[dict[str, Any]]) -> str:
    """'H' si le couloir court d'est en ouest, 'V' du nord au sud, '-' sans couloir.

    Le couloir est le rectangle « couloir » le plus **allongé**, pas le plus
    grand : le gabarit actuel étend aussi des tronçons typés « couloir » dans
    les coins de la bande humide, parfois plus vastes que le couloir lui-même
    (3,2 x 5,9 m contre 7,6 x 1,4 m). Retenir la plus grande aire prenait ces
    tronçons pour la circulation et faussait l'orientation.
    """
    halls = [(r, _bbox(r)) for r in rooms if r.get("type") == "hallway"]
    halls = [(r, b) for r, b in halls if b is not None]
    if not halls:
        return "-"
    _, box = max(
        halls,
        key=lambda rb: (max(rb[1][2] - rb[1][0], rb[1][3] - rb[1][1]), _area(rb[1])),
    )
    return "H" if (box[2] - box[0]) >= (box[3] - box[1]) else "V"


def circulation_share(rooms: list[dict[str, Any]]) -> float:
    """Part de la surface occupée par des pièces typées « couloir » (0 à 1).

    Un plan d'habitation courant y consacre de l'ordre de 8 à 12 %. Au-delà, de
    la surface est mobilisée par de la circulation au lieu de pièces.
    """
    total = hall = 0.0
    for room in rooms:
        box = _bbox(room)
        if box is None:
            continue
        a = _area(box)
        total += a
        if room.get("type") == "hallway":
            hall += a
    return hall / total if total > 0 else 0.0


def zone_code(rooms: list[dict[str, Any]], width: float, depth: float) -> str:
    """Arrangement des grandes zones, sous forme d'un code court et comparable.

    Exemple : ``night:N|day:S|hall:H|garage:E`` — chambres au nord, pièces de
    jour au sud, couloir horizontal, garage à l'est. C'est le gabarit actuel.
    """
    night = [r for r in rooms if r.get("type") in NIGHT]
    day = [r for r in rooms if r.get("type") in DAY]
    garage = [r for r in rooms if r.get("type") == "garage"]
    return "|".join((
        f"night:{_dominant_side(night, width, depth)}",
        f"day:{_dominant_side(day, width, depth)}",
        f"hall:{_hall_orientation(rooms)}",
        f"garage:{_dominant_side(garage, width, depth)}",
    ))


def _centroid_y(rooms: list[dict[str, Any]]) -> float | None:
    total = cy = 0.0
    for room in rooms:
        box = _bbox(room)
        if box is None:
            continue
        a = _area(box)
        total += a
        cy += a * (box[1] + box[3]) / 2.0
    return cy / total if total > 0.0 else None


def follows_classic_template(rooms: list[dict[str, Any]]) -> bool:
    """Vrai si le plan suit le gabarit actuel : chambres, puis couloir, puis jour, du nord au sud.

    Test **relationnel** : la nuit est au nord du couloir, le couloir court d'est
    en ouest, le jour est au sud. Une règle fondée sur la position absolue des
    zones se trompait dès qu'un garage décalait leur centre de gravité vers
    l'ouest. Faux si une des trois zones manque : un plan sans chambre ou sans
    couloir n'est pas concerné par la question.
    """
    halls = [r for r in rooms if r.get("type") == "hallway" and _bbox(r) is not None]
    if not halls or _hall_orientation(rooms) != "H":
        return False
    main = max(
        halls,
        key=lambda r: (
            max(_bbox(r)[2] - _bbox(r)[0], _bbox(r)[3] - _bbox(r)[1]),  # type: ignore[index]
            _area(_bbox(r)),  # type: ignore[arg-type]
        ),
    )
    night_y = _centroid_y([r for r in rooms if r.get("type") in NIGHT])
    day_y = _centroid_y([r for r in rooms if r.get("type") in DAY])
    hall_y = _centroid_y([main])
    if night_y is None or day_y is None or hall_y is None:
        return False
    return night_y < hall_y < day_y


def _facade_sides(
    box: tuple[float, float, float, float], width: float, depth: float
) -> list[str]:
    sides = []
    if box[1] <= _FACADE_TOL:
        sides.append("N")
    if box[3] >= depth - _FACADE_TOL:
        sides.append("S")
    if box[0] <= _FACADE_TOL:
        sides.append("W")
    if box[2] >= width - _FACADE_TOL:
        sides.append("E")
    return sides


def topology_signature(
    rooms: list[dict[str, Any]], width: float, depth: float
) -> frozenset[tuple[str, ...]]:
    """Ensemble de faits topologiques : adjacences entre types, façades par type.

    Deux plans qui réalisent les mêmes faits ont la même signature, quelles que
    soient leurs cotes. Deux chambres jointives comptent comme un seul fait
    (chambre, chambre) : la signature ne compte pas les pièces, elle décrit la
    manière dont les types se touchent et s'orientent.
    """
    facts: set[tuple[str, ...]] = set()
    typed = [(str(r.get("type") or ""), r) for r in rooms]
    for i, (ta, ra) in enumerate(typed):
        box = _bbox(ra)
        if box is not None:
            for side in _facade_sides(box, width, depth):
                facts.add(("facade", ta, side))
        for tb, rb in typed[i + 1:]:
            if share_edge(ra, rb):
                lo, hi = sorted((ta, tb))
                facts.add(("adj", lo, hi))
    return frozenset(facts)


def topology_distance(
    a: frozenset[tuple[str, ...]], b: frozenset[tuple[str, ...]]
) -> float:
    """Distance de Jaccard entre deux signatures : 0 = identiques, 1 = sans rien en commun."""
    union = a | b
    if not union:
        return 0.0
    return 1.0 - len(a & b) / len(union)
