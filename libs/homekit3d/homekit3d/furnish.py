"""Ameublement automatique d'un plan vierge : règles par type de pièce, sur les rôles du catalogue. Python pur.

Ce n'est pas un solveur de contraintes généraliste : ce sont les dispositions courantes (lit tête au mur et
chevets, canapé face à un meuble télé, cuisine en file le long du plus long mur…), posées seulement là où il y a de la
place et hors des dégagements de portes. Les rôles sans modèle dans le catalogue sont ignorés, jamais inventés.
"""
from __future__ import annotations

import math

from .catalog import Asset, Catalog
from .layout import (Occupancy, Rect, SIDE_ROT, SIDES, find_along_wall, in_front, occupancy_of, rect_of, room_box,
                     spot, wall_span)
from .plan import Plan, Room


class _Ctx:
    def __init__(self, plan: Plan, catalog: Catalog, room: Room, occ: Occupancy) -> None:
        self.plan, self.catalog, self.room, self.occ = plan, catalog, room, occ
        self.box: Rect = room_box(room)

    def asset(self, role: str, size: tuple[float, float] | None = None) -> Asset | None:
        return self.catalog.pick_fit(role, size, room=self.room.type, style=self.plan.style.tags,
                                     seed=f"{self.plan.seed}:{self.room.id}", prefer_pack=self.plan.style.prefer_pack)

    def put(self, role: str, x: float, y: float, rot: float, size: tuple[float, float], *, asset: Asset | None = None,
            elevation: float = 0.0, footprint: bool = True, **meta) -> str:
        item_id = self.plan.place(role, x, y, rot, room=self.room.id, size=size, elevation=elevation,
                                  asset=asset.id if asset else "", **meta)
        if footprint:
            self.occ.add(rect_of(x, y, size[0], size[1], rot))
        return item_id

    def against(self, role: str, sides: str, *, size: tuple[float, float] | None = None, centre: bool = False,
                elevation: float = 0.0) -> tuple[float, float, float, tuple[float, float]] | None:
        asset = self.asset(role, size)
        if asset is None:
            return None
        w, d = size or asset.footprint
        spotted = find_along_wall(self.occ, self.box, sides, w, d, prefer_centre=centre)
        if spotted is None:
            return None
        x, y, rot = spotted
        self.put(role, x, y, rot, (w, d), asset=asset, elevation=elevation)
        return x, y, rot, (w, d)

    def free_span(self, side: str) -> float:
        lo, hi = wall_span(self.box, side)
        return hi - lo


def autofurnish(plan: Plan, catalog: Catalog, *, only_empty: bool = True) -> dict[str, int]:
    """Meuble les pièces (par défaut seulement celles qui n'ont aucun objet). Renvoie le nombre d'objets par pièce."""
    occ = occupancy_of(plan, catalog)
    added: dict[str, int] = {}
    handlers = {"bedroom": _bedroom, "living": _living, "dining": _dining, "kitchen": _kitchen, "bathroom": _bathroom,
                "wc": _wc, "office": _office, "hallway": _hallway, "garage": _garage, "laundry": _laundry}
    for room in plan.rooms:
        if only_empty and any(i.room == room.id for i in plan.items):
            continue
        handler = handlers.get(room.type)
        if handler is None:
            continue
        before = len(plan.items)
        handler(_Ctx(plan, catalog, room, occ))
        added[room.id] = len(plan.items) - before
    return added


def _sides_by_span(ctx: _Ctx) -> str:
    """Les murs de la pièce, du plus long au plus court."""
    return "".join(sorted(SIDES, key=lambda s: -ctx.free_span(s)))


def _bedroom(ctx: _Ctx) -> None:
    role = "bed.double" if min(ctx.box[2] - ctx.box[0], ctx.box[3] - ctx.box[1]) >= 2.6 else "bed.single"
    bed = ctx.asset(role)
    if bed is None:
        return
    bw, bl = bed.footprint
    placed = None
    for side in "NWES":                                                # tête au mur, plutôt côté nord ou ouest
        got = find_along_wall(ctx.occ, ctx.box, side, bw, bl, prefer_centre=True)
        if got:
            placed = (side, got)
            break
    if placed is None:
        return
    side, (x, y, rot) = placed
    ctx.put(role, x, y, rot, (bw, bl), asset=bed)
    stand = ctx.asset("nightstand")
    if stand:
        sw, sd = stand.footprint
        ux, uy = math.cos(math.radians(rot)), math.sin(math.radians(rot))          # sens « le long du mur »
        for sign in (-1, 1):
            off = sign * (bw / 2 + sw / 2 + 0.04)
            sx, sy = x + ux * off, y + uy * off
            # Le chevet est collé au mur, à hauteur de la tête du lit.
            sx, sy = _shift_to_head(x, y, rot, bl, sd, sx, sy)
            box = rect_of(sx, sy, sw, sd, rot)
            if ctx.occ.free(box, ctx.box):
                ctx.put("nightstand", sx, sy, rot, (sw, sd), asset=stand)
    wardrobe = ctx.asset("wardrobe")
    if wardrobe:
        ww, wd = wardrobe.footprint
        sides = "".join(s for s in "SENW" if s != side) + side
        ctx.against("wardrobe", sides, size=(max(ww, 0.9), wd))
    if (ctx.room.area >= 14):
        ctx.against("desk", "".join(s for s in "WEN" if s != side), size=None)


def _shift_to_head(x: float, y: float, rot: float, bed_len: float, stand_d: float, sx: float, sy: float) -> tuple[float, float]:
    """Ramène un chevet au niveau du chevet du lit (dos au mur) plutôt qu'au milieu du lit."""
    r = math.radians(rot)
    back = (bed_len - stand_d) / 2                                      # distance centre du lit -> centre du chevet, vers le mur
    return sx + math.sin(r) * back, sy - math.cos(r) * back


def _living(ctx: _Ctx) -> None:
    sofa_role = "sofa.corner" if ctx.room.area >= 26 else "sofa"
    sofa = ctx.asset(sofa_role) or ctx.asset("sofa")
    if sofa is None:
        return
    sw, sd = sofa.footprint
    got = find_along_wall(ctx.occ, ctx.box, _sides_by_span(ctx), sw, sd, prefer_centre=True)
    if got is None:
        return
    x, y, rot = got
    ctx.put(sofa.role, x, y, rot, (sw, sd), asset=sofa)
    table = ctx.asset("table.coffee")
    front = 0.55 + sd / 2
    if table:
        tw, td = table.footprint
        tx, ty = in_front(x, y, rot, front + td / 2)
        if ctx.occ.free(rect_of(tx, ty, tw, td, rot), ctx.box, margin=0.0):
            ctx.put("table.coffee", tx, ty, rot, (tw, td), asset=table)
            rug = ctx.asset("rug")
            if rug:
                rw, rd = min(2.4, sw + 0.4), min(1.8, td + 1.6)
                ctx.put("rug", *in_front(x, y, rot, front + td / 2 - 0.1), rot, (rw, rd), asset=rug, footprint=False)
    opposite = {"N": "S", "S": "N", "W": "E", "E": "W"}
    facing = _wall_side_of(rot)
    ctx.against("tv.console", opposite.get(facing, "N"), centre=True)
    armchair = ctx.asset("armchair")
    if armchair and ctx.room.area >= 20:
        aw, ad = armchair.footprint
        ax, ay = in_front(x, y, rot, front + 0.35)
        ux, uy = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        off = sw / 2 + aw / 2 + 0.2
        for sign, yaw in ((1, 90), (-1, -90)):
            px, py = ax + ux * off * sign, ay + uy * off * sign
            if ctx.occ.free(rect_of(px, py, aw, ad, rot + yaw), ctx.box, margin=0.0):
                ctx.put("armchair", px, py, rot + yaw, (aw, ad), asset=armchair)
                break


def _wall_side_of(rot: float) -> str:
    """Le mur contre lequel un meuble de rotation `rot` a le dos."""
    for side, r in SIDE_ROT.items():
        if abs(((rot - r + 180) % 360) - 180) < 1e-6:
            return side
    return "N"


def _dining(ctx: _Ctx) -> None:
    table = ctx.asset("table.dining")
    chair = ctx.asset("chair.dining")
    if table is None:
        return
    tw, td = table.footprint
    if tw < td:
        tw, td = td, tw
    cx, cy = (ctx.box[0] + ctx.box[2]) / 2, (ctx.box[1] + ctx.box[3]) / 2
    ctx.put("table.dining", cx, cy, 0.0, (tw, td), asset=table)
    if chair is None:
        return
    cw, cd = chair.footprint
    for k, dx in enumerate((-0.45, 0.45)):
        for sign in (-1, 1):
            y = cy + sign * (td / 2 + cd / 2 + 0.05)
            ctx.put("chair.dining", cx + dx, y, 0.0 if sign < 0 else 180.0, (cw, cd), asset=chair)
    if tw >= 1.6:
        for sign in (-1, 1):
            ctx.put("chair.dining", cx + sign * (tw / 2 + cd / 2 + 0.05), cy, 270.0 if sign < 0 else 90.0, (cw, cd), asset=chair)


def _kitchen(ctx: _Ctx) -> None:
    side = _sides_by_span(ctx)
    base = ctx.asset("kitchen.base")
    if base is None:
        return
    depth = 0.62
    fridge = ctx.asset("kitchen.fridge")
    stove = ctx.asset("kitchen.stove")
    fw = fridge.footprint[0] if fridge else 0.0
    for s in side:
        lo, hi = wall_span(ctx.box, s)
        length = min(hi - lo - 0.1, 3.6)
        if length < 1.6:
            continue
        run_w = length - (fw + 0.05 if fridge else 0.0)
        x, y, rot = spot(ctx.box, s, run_w, depth, along=(lo + hi) / 2 - (fw + 0.05) / 2 if fridge else (lo + hi) / 2)
        box = rect_of(x, y, run_w, depth, rot)
        if not ctx.occ.free(box, ctx.box):
            continue
        ctx.put("kitchen.run", x, y, rot, (run_w, depth), asset=None)
        if stove:
            step = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            sx, sy = x + step[0] * run_w * 0.18, y + step[1] * run_w * 0.18
            ctx.put("kitchen.stove", sx, sy, rot, (stove.footprint[0], min(stove.footprint[1], depth)), asset=stove, footprint=False)
        if fridge:
            fx, fy, frot = spot(ctx.box, s, fw, fridge.footprint[1], along=(lo + hi) / 2 + (run_w + 0.05) / 2)
            ctx.put("kitchen.fridge", fx, fy, frot, (fw, fridge.footprint[1]), asset=fridge)
        ux, uy = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        upper = ctx.asset("kitchen.upper")
        if upper:
            uw, ud = upper.footprint
            n = max(1, int(run_w // max(uw, 0.6)) - 1)
            for k in range(n):
                off = (k - (n - 1) / 2) * (run_w / n) - 0.1
                ctx.put("kitchen.upper", x + ux * off, y + uy * off, rot, (min(uw, run_w / n), min(ud, 0.4)), asset=upper,
                        elevation=1.45, footprint=False)
        return


def _bathroom(ctx: _Ctx) -> None:
    for role, sides in (("toilet", "NEWS"), ("sink.bath", "EWNS"), ("bathtub", "SNWE")):
        placed = ctx.against(role, sides)
        if placed is None and role == "bathtub":
            ctx.against("shower", "SNWE")
    mirror = next((i for i in ctx.plan.items if i.room == ctx.room.id and i.role == "sink.bath"), None)
    if mirror:
        ctx.plan.place("mirror", mirror.x, mirror.y, mirror.rot, room=ctx.room.id, elevation=1.25, size=(0.5, 0.05))


def _wc(ctx: _Ctx) -> None:
    ctx.against("toilet", "NEWS")
    ctx.against("sink.bath", "EWNS", size=(0.45, 0.35))


def _office(ctx: _Ctx) -> None:
    desk = ctx.against("desk", _sides_by_span(ctx), centre=True)
    if desk:
        x, y, rot, (w, d) = desk
        chair = ctx.asset("chair.desk")
        if chair:
            cx, cy = in_front(x, y, rot, d / 2 + chair.footprint[1] / 2 + 0.1)
            ctx.put("chair.desk", cx, cy, rot + 180, chair.footprint, asset=chair)
    ctx.against("bookcase", "NEWS")


def _hallway(ctx: _Ctx) -> None:
    ctx.against("coat.rack", "NWES", size=None)


def _laundry(ctx: _Ctx) -> None:
    ctx.against("laundry.machine", "NEWS")


def _garage(ctx: _Ctx) -> None:
    cx, cy = (ctx.box[0] + ctx.box[2]) / 2, (ctx.box[1] + ctx.box[3]) / 2
    w, d = ctx.box[2] - ctx.box[0], ctx.box[3] - ctx.box[1]
    if max(w, d) >= 4.6 and min(w, d) >= 2.2:
        rot = 0.0 if w >= d else 90.0
        ctx.plan.place("car", cx, cy, rot, room=ctx.room.id, size=(4.3, 1.8))
