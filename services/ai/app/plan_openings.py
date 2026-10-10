"""Placement des portes et fenêtres sur les murs du plan."""

from __future__ import annotations

from typing import Any

from app.opening_intervals import (
    EPSILON_M,
    OpeningGeometryError,
    nearest_free_offset,
    opening_interval,
    overlaps,
    validate_openings,
    wall_lengths,
)
from app.plan_geometry import room_bounds as _room_bbox


def fit_generated_windows(
    walls: list[dict[str, Any]],
    openings: list[dict[str, Any]],
    rooms: list[dict[str, Any]],
    *,
    original_openings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Repair conflicting generated windows without moving doors or changing rooms.

    This is a generation-only operation, not a repair of user-saved documents.
    Room spans use the rectangular geometry of the current packing engine.
    An impossible placement fails explicitly before furniture and rendering.
    """
    lengths = wall_lengths(walls)
    by_id = {wall["id"]: wall for wall in walls}
    originals = {
        opening["id"]: opening for opening in (original_openings if original_openings is not None else openings)
    }
    result = [dict(opening) for opening in openings]
    doors = [opening for opening in result if opening.get("type") != "window"]
    validate_openings(walls, doors)
    occupied: dict[str, list[tuple[float, float]]] = {}
    for opening in doors:
        occupied.setdefault(opening["wall_id"], []).append(opening_interval(opening, lengths))
    for opening in result:
        if opening.get("type") != "window":
            continue
        interval = opening_interval(opening, lengths)
        wall_id = opening["wall_id"]
        reserved = occupied.setdefault(wall_id, [])
        conflict = any(overlaps(interval, other) for other in reserved)
        original = originals[opening["id"]]
        enlarged = opening["width_m"] > original["width_m"]
        if enlarged or conflict or interval[0] < -EPSILON_M or interval[1] > lengths[wall_id] + EPSILON_M:
            wall = by_id[wall_id]
            served = _served_rooms(wall, original, rooms)
            spans = [_wall_span_for_room(wall, room) for room in served]
            if not spans or any(span is None for span in spans):
                raise OpeningGeometryError("window_room_unknown", opening["id"])
            known_spans = [span for span in spans if span is not None]
            span = (max(0.0, *(s[0] for s in known_spans)), min(lengths[wall_id], *(s[1] for s in known_spans)))
            offset = nearest_free_offset(interval[0], opening["width_m"], span, reserved)
            if offset is None:
                raise OpeningGeometryError("window_no_free_span", opening["id"])
            opening["offset_m"] = offset
            interval = opening_interval(opening, lengths)
        reserved.append(interval)
    validate_openings(walls, result)
    return result


def default_openings(
    walls: list[dict[str, Any]],
    width: float,
    depth: float,
    rooms: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Porte d'entrée sud + porte de garage + fenêtres façades + portes internes autorisées.

    La porte de garage s'ouvre sur le mur extérieur où le garage se trouve (`_garage_door`).
    """
    openings: list[dict[str, Any]] = []
    oid = 1
    internals = [w for w in walls if not str(w.get("id", "")).startswith("w_outer")]
    by_id = {str(w.get("id")): w for w in walls}
    south = by_id.get("w_outer_3")
    east = by_id.get("w_outer_2")
    north = by_id.get("w_outer_1")
    west = by_id.get("w_outer_4")
    room_list = [r for r in (rooms or []) if len(r.get("polygon") or []) >= 3]
    has_garage = any(r.get("type") == "garage" for r in room_list)

    if south:
        flen = _wall_len(south)
        openings.append(
            {
                "id": f"o{oid}",
                "wall_id": south["id"],
                "type": "door",
                # 42 % de la façade tombait au hasard : l'entrée pouvait déboucher
                # dans la salle de bain. On la cale sur l'entrée / le séjour dès
                # qu'on connaît les pièces.
                "offset_m": _entrance_offset(south, flen, room_list),
                "width_m": 0.9,
            }
        )
        oid += 1
    if has_garage:
        entrance = next((o for o in openings if south and o.get("wall_id") == south["id"]), None)
        garage_door = _garage_door(
            (east, west, north, south),
            room_list,
            (float(entrance["offset_m"]), float(entrance["width_m"])) if entrance else None,
        )
        if garage_door:
            wall, offset, width_m = garage_door
            openings.append(
                {
                    "id": f"o{oid}",
                    "wall_id": wall["id"],
                    "type": "door",
                    "offset_m": offset,
                    "width_m": width_m,
                }
            )
            oid += 1
    for wall in (north, west):
        if not wall:
            continue
        wl = _wall_len(wall)
        if wl < 1.6:
            continue
        openings.append(
            {
                "id": f"o{oid}",
                "wall_id": wall["id"],
                "type": "window",
                "offset_m": max(0.3, wl * 0.25),
                "width_m": min(1.4, wl * 0.35),
            }
        )
        oid += 1

    for wall in internals:
        wl = _wall_len(wall)
        if wl < 1.05:
            continue
        if room_list and not _allow_internal_door(wall, room_list):
            continue
        if not room_list and wl < 1.2:
            continue
        openings.append(
            {
                "id": f"o{oid}",
                "wall_id": wall["id"],
                "type": "door",
                "offset_m": max(0.2, min(wl - 1.0, wl * 0.4)),
                "width_m": 0.8,
            }
        )
        oid += 1
    if room_list:
        _add_missing_room_doors(openings, walls, internals, room_list, oid)
    _ = (width, depth)
    return assign_door_semantics(openings, walls, room_list)


# Voisinages qu'on refuse même en dernier recours : ouvrir une de ces portes
# vaut un écart sanitaire signalé par `compliance.evaluate`.
_FORBIDDEN_PAIRS = {
    frozenset({"wc", "kitchen"}),
    frozenset({"wc", "dining"}),
    frozenset({"wc", "bedroom"}),
    frozenset({"bedroom", "living"}),
    frozenset({"kitchen", "bathroom"}),
}
# Pièces auxquelles une porte de façade convient si aucune porte intérieure
# n'est acceptable (un WC ou une chambre ne s'ouvre pas sur le jardin).
_FACADE_DOOR_OK = {
    "garage",
    "living",
    "kitchen",
    "dining",
    "hallway",
    "office",
    "storage",
    "laundry",
}
_NEIGHBOUR_RANK = {
    "hallway": 4,
    "living": 3,
    "dining": 3,
    "kitchen": 2,
    "office": 2,
    "garage": 2,
}


def _wall_span_for_room(wall: dict[str, Any], room: dict[str, Any]) -> tuple[float, float] | None:
    """Portion du mur en vis-à-vis de `room`, en mètres depuis l'extrémité `a`.

    Un mur de façade court le long de toute la maison : centrer une ouverture
    sur le mur la posait devant une autre pièce (porte d'entrée débouchant
    dans la salle de bain, porte de secours percée chez le voisin).
    """
    a, b = _wall_point(wall.get("a")), _wall_point(wall.get("b"))
    box = _room_bbox(room)
    if a is None or b is None or box is None:
        return None
    x0, y0, x1, y1 = box
    if abs(a[0] - b[0]) <= 0.15:  # mur vertical
        if abs(x0 - a[0]) > 0.15 and abs(x1 - a[0]) > 0.15:
            return None
        lo, hi = max(min(a[1], b[1]), y0), min(max(a[1], b[1]), y1)
        if hi - lo <= 0.05:
            return None
        return (lo - a[1], hi - a[1]) if b[1] >= a[1] else (a[1] - hi, a[1] - lo)
    if abs(a[1] - b[1]) > 0.15:  # mur oblique : pas de découpe fiable
        return None
    if abs(y0 - a[1]) > 0.15 and abs(y1 - a[1]) > 0.15:
        return None
    lo, hi = max(min(a[0], b[0]), x0), min(max(a[0], b[0]), x1)
    if hi - lo <= 0.05:
        return None
    return (lo - a[0], hi - a[0]) if b[0] >= a[0] else (a[0] - hi, a[0] - lo)


def _centred_offset(span: tuple[float, float], width_m: float, wall_len: float) -> float:
    lo, hi = span
    off = lo + max(0.0, (hi - lo - width_m) / 2)
    return round(max(0.0, min(off, max(0.0, wall_len - width_m))), 3)


def _served_rooms(wall: dict[str, Any], opening: dict[str, Any], rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pièces réellement desservies par une ouverture (au droit de sa position)."""
    a, b = _wall_point(wall.get("a")), _wall_point(wall.get("b"))
    if a is None or b is None:
        return []
    length = _wall_len(wall)
    try:
        mid = float(opening.get("offset_m") or 0) + float(opening.get("width_m") or 0) / 2
    except (TypeError, ValueError):
        return []
    t = min(1.0, max(0.0, mid / length)) if length > 0 else 0.5
    px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
    out: list[dict[str, Any]] = []
    for room in rooms:
        box = _room_bbox(room)
        if not box:
            continue
        x0, y0, x1, y1 = box
        on_v = (abs(x0 - px) <= 0.15 or abs(x1 - px) <= 0.15) and y0 - 0.15 <= py <= y1 + 0.15
        on_h = (abs(y0 - py) <= 0.15 or abs(y1 - py) <= 0.15) and x0 - 0.15 <= px <= x1 + 0.15
        if on_v or on_h:
            out.append(room)
    return out


def assign_door_semantics(
    openings: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    rooms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return copies with stable hinge and swing semantics for every door.

    A door shared with a hallway swings into the other room. Otherwise the
    smallest adjacent room is chosen deterministically. The hinge is parked
    closest to that room's wall-span edge, leaving the centre more usable.
    Existing explicit semantics are preserved.
    """
    by_id = {str(wall.get("id")): wall for wall in walls}
    result: list[dict[str, Any]] = []
    for source in openings:
        opening = dict(source)
        result.append(opening)
        if opening.get("type") != "door":
            continue
        if "hinge" in opening and "swing" in opening:
            continue
        wall = by_id.get(str(opening.get("wall_id")))
        if wall is None:
            opening.update(hinge="start", swing="positive")
            continue
        served = _served_rooms(wall, opening, rooms)
        candidates = [room for room in served if room.get("type") != "hallway"] or served
        target = min(candidates, key=_room_semantics_rank) if candidates else None
        if target is None:
            opening.update(hinge="start", swing="positive")
            continue
        a, b = _wall_point(wall.get("a")), _wall_point(wall.get("b"))
        box = _room_bbox(target)
        if a is None or b is None or box is None:
            opening.update(hinge="start", swing="positive")
            continue
        center_x, center_y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        cross = (b[0] - a[0]) * (center_y - a[1]) - (b[1] - a[1]) * (center_x - a[0])
        opening["swing"] = "positive" if cross >= 0 else "negative"
        span = _wall_span_for_room(wall, target) or (0.0, _wall_len(wall))
        start = float(opening.get("offset_m") or 0)
        end = start + float(opening.get("width_m") or 0)
        opening["hinge"] = "start" if abs(start - span[0]) <= abs(span[1] - end) else "end"
    return result


def _room_semantics_rank(room: dict[str, Any]) -> tuple[float, str]:
    box = _room_bbox(room)
    area = (box[2] - box[0]) * (box[3] - box[1]) if box else float("inf")
    return area, str(room.get("id") or "")


def _add_missing_room_doors(
    openings: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    internals: list[dict[str, Any]],
    rooms: list[dict[str, Any]],
    oid: int,
) -> None:
    """Donne une porte à toute pièce qui n'en a aucune.

    La liste blanche `_DOOR_PAIRS` sait dire quelles portes sont *souhaitables*,
    mais rien ne garantissait qu'il en reste au moins une par pièce : un bureau
    coincé entre cuisine et salle à manger, ou un WC qui ne touche pas le
    couloir, se retrouvait muré — une pièce inaccessible, donc un plan faux.
    """
    by_id = {str(w.get("id")): w for w in walls}
    served: set[int] = set()
    for op in openings:
        if op.get("type") != "door":
            continue
        wall = by_id.get(str(op.get("wall_id")))
        if wall is None:
            continue
        for room in _served_rooms(wall, op, rooms):
            served.add(id(room))
    for room in rooms:
        if id(room) in served:
            continue
        wall = _best_access_wall(room, internals, walls, rooms)
        if wall is None:
            continue
        wl = _wall_len(wall)
        span = _wall_span_for_room(wall, room) or (0.0, wl)
        usable = span[1] - span[0]
        width_m = 0.8 if usable >= 0.85 else max(0.6, usable - 0.05)
        openings.append(
            {
                "id": f"o{oid}",
                "wall_id": wall["id"],
                "type": "door",
                "offset_m": _centred_offset(span, width_m, wl),
                "width_m": round(width_m, 2),
            }
        )
        oid += 1
        served.add(id(room))


def _best_access_wall(
    room: dict[str, Any],
    internals: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    rooms: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Meilleur mur pour percer la porte manquante d'une pièce enclavée."""
    typ = str(room.get("type") or "")
    best: tuple[tuple[float, float, float], dict[str, Any]] | None = None
    for wall in internals:
        pair = _rooms_on_wall(wall, rooms)
        if len(pair) != 2 or all(r is not room for r in pair):
            continue
        other = next(r for r in pair if r is not room)
        other_t = str(other.get("type") or "")
        if frozenset({typ, other_t}) in _FORBIDDEN_PAIRS:
            continue
        span = _wall_span_for_room(wall, room)
        usable = (span[1] - span[0]) if span else _wall_len(wall)
        if usable < 0.7:
            continue
        # Un mur assez large pour une porte réglementaire (0,80 m) passe avant
        # un voisinage mieux classé mais trop étroit.
        rank = (
            1.0 if usable >= 0.85 else 0.0,
            float(_NEIGHBOUR_RANK.get(other_t, 1)),
            usable,
        )
        if best is None or rank > best[0]:
            best = (rank, wall)
    if best is not None:
        return best[1]
    facade: list[tuple[float, dict[str, Any]]] = []
    if typ in _FACADE_DOOR_OK:
        for w in walls:
            if not str(w.get("id", "")).startswith("w_outer"):
                continue
            span = _wall_span_for_room(w, room)
            if span and span[1] - span[0] >= 1.0:
                facade.append((span[1] - span[0], w))
    if facade:
        return max(facade, key=lambda it: it[0])[1]
    return _last_resort_wall(room, internals, rooms)


def _last_resort_wall(
    room: dict[str, Any], internals: list[dict[str, Any]], rooms: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Mur le plus large, voisinage déconseillé compris.

    Une pièce murée est pire qu'un écart sanitaire : celui-ci est au moins
    signalé par `compliance.evaluate`, l'autre rend le plan inutilisable.
    """
    best: tuple[float, dict[str, Any]] | None = None
    for wall in internals:
        pair = _rooms_on_wall(wall, rooms)
        if len(pair) != 2 or all(r is not room for r in pair):
            continue
        span = _wall_span_for_room(wall, room)
        usable = (span[1] - span[0]) if span else _wall_len(wall)
        if usable >= 0.7 and (best is None or usable > best[0]):
            best = (usable, wall)
    return best[1] if best else None


# Pièces qui peuvent recevoir la porte d'entrée, de la meilleure à la pire.
_ENTRANCE_ORDER = ("hallway", "living", "dining", "kitchen", "office", "garage")

# Porte de garage : 2,4 m, avec 0,2 m de part et d'autre dans la façade du garage.
_GARAGE_DOOR_WIDTH = 2.4
_MIN_GARAGE_CONTACT = _GARAGE_DOOR_WIDTH + 0.4


def _garage_door(
    walls: tuple[dict[str, Any] | None, ...],
    rooms: list[dict[str, Any]],
    entrance: tuple[float, float] | None,
) -> tuple[dict[str, Any], float, float] | None:
    """Mur, position et largeur de la porte de garage, ou None s'il n'y a pas de façade pour l'ouvrir.

    La porte était toujours posée sur le mur est, à 55 % de sa longueur, où que soit le
    garage : un garage à l'ouest ou au nord avait sa porte devant une autre pièce. Elle
    s'ouvre désormais sur le mur extérieur où un garage se trouve.

    1. L'emplacement historique (mur est) est conservé tel quel dès qu'un garage l'occupe :
       les plans dont le garage tient toute la façade est ne changent pas d'un millimètre.
    2. Sinon, le mur où un garage a le plus long contact (au moins `_MIN_GARAGE_CONTACT`),
       préférence est, ouest, nord, sud à contact égal, la porte centrée sur ce contact. Sur
       le mur sud, elle évite la porte d'entrée (`entrance` : position et largeur).
    """
    east, west, north, south = walls
    garages = [r for r in rooms if r.get("type") == "garage"]
    if east and _wall_len(east) >= 2.4:
        wl = _wall_len(east)
        offset, width_m = max(0.4, min(wl - 2.6, wl * 0.55)), min(2.4, wl * 0.45)
        for garage in garages:
            span = _wall_span_for_room(east, garage)
            if span and span[0] <= offset + 0.05 and span[1] >= offset + width_m - 0.05:
                return east, offset, width_m
    best: tuple[tuple[float, int], dict[str, Any], float] | None = None
    for rank, wall in enumerate(walls):
        if wall is None:
            continue
        for garage in garages:
            span = _wall_span_for_room(wall, garage)
            if not span or span[1] - span[0] < _MIN_GARAGE_CONTACT:
                continue
            offset = _centred_offset(span, _GARAGE_DOOR_WIDTH, _wall_len(wall))
            if (
                wall is south
                and entrance
                and offset < entrance[0] + entrance[1]
                and entrance[0] < offset + _GARAGE_DOOR_WIDTH
            ):
                continue
            key = (-round(span[1] - span[0], 3), rank)
            if best is None or key < best[0]:
                best = (key, wall, offset)
    return (best[1], best[2], _GARAGE_DOOR_WIDTH) if best else None


def _entrance_offset(south: dict[str, Any], flen: float, rooms: list[dict[str, Any]]) -> float:
    """Position de la porte d'entrée sur la façade sud, devant une pièce d'accueil."""
    default = max(0.4, min(flen - 1.2, flen * 0.42))
    if not rooms:
        return default
    best: tuple[int, float, tuple[float, float]] | None = None
    for room in rooms:
        span = _wall_span_for_room(south, room)
        if not span or span[1] - span[0] < 1.1:
            continue
        typ = str(room.get("type") or "")
        rank = _ENTRANCE_ORDER.index(typ) if typ in _ENTRANCE_ORDER else len(_ENTRANCE_ORDER)
        key = (rank, -(span[1] - span[0]), span)
        if best is None or key[:2] < best[:2]:
            best = key
    if best is None:
        return default
    return _centred_offset(best[2], 0.9, flen)


_DOOR_PAIRS = {
    frozenset({"bedroom", "hallway"}),
    frozenset({"bathroom", "hallway"}),
    frozenset({"wc", "hallway"}),
    frozenset({"laundry", "hallway"}),
    frozenset({"storage", "hallway"}),
    frozenset({"office", "hallway"}),
    frozenset({"kitchen", "living"}),
    frozenset({"kitchen", "dining"}),
    frozenset({"kitchen", "hallway"}),
    frozenset({"living", "hallway"}),
    frozenset({"living", "dining"}),
    frozenset({"living", "office"}),
    frozenset({"dining", "hallway"}),
    frozenset({"garage", "hallway"}),
    frozenset({"garage", "living"}),
}


def _rooms_on_wall(wall: dict[str, Any], rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    a = _wall_point(wall.get("a"))
    b = _wall_point(wall.get("b"))
    if a is None or b is None:
        return []
    ax, ay = a
    bx, by = b
    vertical = abs(ax - bx) <= 0.15
    hits: list[dict[str, Any]] = []
    for room in rooms:
        box = _room_bbox(room)
        if not box:
            continue
        x0, y0, x1, y1 = box
        if vertical:
            x = (ax + bx) / 2
            ylo, yhi = min(ay, by), max(ay, by)
            if abs(x0 - x) > 0.15 and abs(x1 - x) > 0.15:
                continue
            if min(y1, yhi) - max(y0, ylo) >= 0.5:
                hits.append(room)
        else:
            y = (ay + by) / 2
            xlo, xhi = min(ax, bx), max(ax, bx)
            if abs(y0 - y) > 0.15 and abs(y1 - y) > 0.15:
                continue
            if min(x1, xhi) - max(x0, xlo) >= 0.5:
                hits.append(room)
    return hits


def _allow_internal_door(wall: dict[str, Any], rooms: list[dict[str, Any]]) -> bool:
    pair = _rooms_on_wall(wall, rooms)
    if len(pair) != 2:
        return False
    types = [str(r.get("type") or "") for r in pair]
    key = frozenset(types)
    if key == {"bedroom", "bathroom"}:
        return any(bool(r.get("ensuite")) for r in pair if r.get("type") == "bathroom")
    if key == {"bathroom", "hallway"}:
        bath = next(r for r in pair if r.get("type") == "bathroom")
        return not bath.get("ensuite")
    return key in _DOOR_PAIRS


def _wall_point(node: Any) -> tuple[float, float] | None:
    """(x, y) d'une extrémité de mur, ou None si le mur est malformé.

    Les murs peuvent venir d'un `layout` libre (/v1/vectorize) : un `{}` ou un
    `{"a": 3}` faisait remonter KeyError/TypeError en 500.
    """
    if not isinstance(node, dict):
        return None
    try:
        return float(node["x"]), float(node["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _wall_len(wall: dict[str, Any]) -> float:
    a = _wall_point(wall.get("a")) if isinstance(wall, dict) else None
    b = _wall_point(wall.get("b")) if isinstance(wall, dict) else None
    if a is None or b is None:
        return 0.0
    return max(0.1, ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5)
