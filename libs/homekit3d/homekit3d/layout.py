"""Aides de placement : emprises, occupation du sol, zones de portes, positions contre les murs. Python pur."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .catalog import Catalog
from .plan import Item, Plan, Room

Rect = tuple[float, float, float, float]          # x0, y0, x1, y1 (plan, y vers le bas)
SIDES = ("N", "S", "W", "E")
# Rotation d'un meuble collé au mur `side`, dos au mur (0° = dos au nord, façade au sud ; sens horaire).
SIDE_ROT = {"N": 0.0, "S": 180.0, "W": 270.0, "E": 90.0}


def rect_of(x: float, y: float, w: float, d: float, rot: float) -> Rect:
    """Boîte englobante d'un objet de largeur `w` (x local) et profondeur `d` (y local) tourné de `rot` degrés."""
    r = math.radians(rot)
    c, s = abs(math.cos(r)), abs(math.sin(r))
    hw, hd = (w * c + d * s) / 2, (w * s + d * c) / 2
    return (x - hw, y - hd, x + hw, y + hd)


def overlaps(a: Rect, b: Rect, margin: float = 0.0) -> bool:
    return a[0] < b[2] + margin - 1e-6 and a[2] > b[0] - margin + 1e-6 and a[1] < b[3] + margin - 1e-6 and a[3] > b[1] - margin + 1e-6


def inside(box: Rect, room: Rect, margin: float = 0.0) -> bool:
    return box[0] >= room[0] + margin - 1e-6 and box[1] >= room[1] + margin - 1e-6 \
        and box[2] <= room[2] - margin + 1e-6 and box[3] <= room[3] - margin + 1e-6


def room_box(room: Room) -> Rect:
    return room.bbox()


def door_zones(plan: Plan) -> list[Rect]:
    """Carrés de dégagement des portes battantes (les deux côtés : le sens d'ouverture n'est pas modélisé). Pas les garages."""
    walls = {w.id: w for w in plan.walls}
    zones: list[Rect] = []
    for op in plan.openings:
        if op.kind != "door" or op.wall_id not in walls:
            continue
        w = walls[op.wall_id]
        length = w.length
        ux, uy = (w.b[0] - w.a[0]) / length, (w.b[1] - w.a[1]) / length
        p0 = (w.a[0] + ux * op.offset, w.a[1] + uy * op.offset)
        p1 = (p0[0] + ux * op.width, p0[1] + uy * op.width)
        r = op.width + 0.05
        xs, ys = sorted((p0[0], p1[0])), sorted((p0[1], p1[1]))
        if abs(uy) < 1e-6:
            zones.append((xs[0], ys[0] - r, xs[1], ys[0] + r))
        else:
            zones.append((xs[0] - r, ys[0], xs[0] + r, ys[1]))
    return zones


@dataclass
class Occupancy:
    """Ce qui est déjà posé (meubles et dégagements de portes) : sert à trouver de la place."""

    rects: list[Rect] = field(default_factory=list)
    zones: list[Rect] = field(default_factory=list)

    def free(self, box: Rect, room: Rect, *, margin: float = 0.03, keep_doors_clear: bool = True) -> bool:
        if not inside(box, room, 0.02):
            return False
        if any(overlaps(box, r, margin) for r in self.rects):
            return False
        return not (keep_doors_clear and any(overlaps(box, z) for z in self.zones))

    def add(self, box: Rect) -> None:
        self.rects.append(box)


def footprint(item: Item, catalog: Catalog, plan: Plan) -> tuple[float, float]:
    if item.size:
        return item.size
    asset = catalog.get(item.asset) if item.asset else catalog.pick_fit(item.role, None, seed=f"{plan.seed}:{item.id}",
                                                                          prefer_pack=plan.style.prefer_pack)
    return asset.footprint if asset else (0.6, 0.6)


def occupancy_of(plan: Plan, catalog: Catalog) -> Occupancy:
    occ = Occupancy(zones=door_zones(plan))
    for it in plan.items:
        if it.elevation > 0.3 or it.role.startswith(("rug", "picture", "mirror", "lamp.ceiling", "lamp.wall")):
            continue                    # objets muraux, plafonniers, tapis : ne prennent pas de place au sol
        w, d = footprint(it, catalog, plan)
        occ.add(rect_of(it.x, it.y, w, d, it.rot))
    return occ


WALL_INSET = 0.1        # les murs sont centrés sur les arêtes des pièces : un meuble « au mur » est décalé de leur demi-épaisseur


def spot(box: Rect, side: str, w: float, d: float, along: float | None = None) -> tuple[float, float, float]:
    """Position (x, y, rot) d'un meuble de largeur `w` (le long du mur) et profondeur `d`, dos au mur `side`."""
    x0, y0, x1, y1 = box
    k = WALL_INSET
    if side == "N":
        return (along if along is not None else (x0 + x1) / 2, y0 + k + d / 2, SIDE_ROT["N"])
    if side == "S":
        return (along if along is not None else (x0 + x1) / 2, y1 - k - d / 2, SIDE_ROT["S"])
    if side == "W":
        return (x0 + k + d / 2, along if along is not None else (y0 + y1) / 2, SIDE_ROT["W"])
    return (x1 - k - d / 2, along if along is not None else (y0 + y1) / 2, SIDE_ROT["E"])


def wall_span(box: Rect, side: str) -> tuple[float, float]:
    x0, y0, x1, y1 = box
    return (x0, x1) if side in "NS" else (y0, y1)


def find_along_wall(occ: Occupancy, box: Rect, sides: str, w: float, d: float, *, step: float = 0.25,
                    prefer_centre: bool = False) -> tuple[float, float, float] | None:
    """Premier emplacement libre contre l'un des murs `sides` (dans l'ordre), en balayant le long du mur."""
    for side in sides:
        lo, hi = wall_span(box, side)
        lo, hi = lo + WALL_INSET, hi - WALL_INSET
        half = w / 2
        if hi - lo < w - 1e-6:
            continue
        mid = (lo + hi) / 2
        offsets = [0.0]
        k = 1
        while mid - k * step >= lo + half - 1e-6 or mid + k * step <= hi - half + 1e-6:
            offsets += [-k * step, k * step]
            k += 1
        if not prefer_centre:
            offsets = sorted(offsets, key=lambda o: -abs(o))               # coins d'abord
        for off in offsets:
            along = mid + off
            if along - half < lo - 1e-6 or along + half > hi + 1e-6:
                continue
            x, y, rot = spot(box, side, w, d, along)
            if occ.free(rect_of(x, y, w, d, rot), box):
                return x, y, rot
    return None


def in_front(x: float, y: float, rot: float, distance: float) -> tuple[float, float]:
    """Le point à `distance` devant un meuble (sa façade regarde vers +y plan à 0°, tourne dans le sens horaire)."""
    r = math.radians(rot)
    return x - math.sin(r) * distance, y + math.cos(r) * distance
