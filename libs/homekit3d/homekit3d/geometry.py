"""Géométrie de la coque : murs avec vraies ouvertures, cadres, portes, vitrages, sols. Python pur.

Les sommets sont produits directement dans le repère Blender (X à droite, Y = -y du plan, Z en haut) : un plan
vu de dessus dans Blender ressemble au plan 2D, sans miroir. Chaque `Mesh` porte UN matériau ; les faces sont
indépendantes (ombrage plat, pas de sommets partagés).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .plan import Opening, Plan, Point, Wall

Vec = tuple[float, float, float]


@dataclass
class Mesh:
    material: str
    verts: list[Vec] = field(default_factory=list)
    faces: list[tuple[int, ...]] = field(default_factory=list)

    def add_face(self, pts: list[Vec]) -> None:
        base = len(self.verts)
        self.verts.extend(pts)
        self.faces.append(tuple(range(base, base + len(pts))))

    def triangles(self) -> int:
        return sum(max(0, len(f) - 2) for f in self.faces)

    def volume(self) -> float:
        """Volume signé (théorème de la divergence) : positif si les faces sont orientées vers l'extérieur."""
        total = 0.0
        for f in self.faces:
            p0 = self.verts[f[0]]
            for i in range(1, len(f) - 1):
                p1, p2 = self.verts[f[i]], self.verts[f[i + 1]]
                total += (p0[0] * (p1[1] * p2[2] - p1[2] * p2[1]) - p0[1] * (p1[0] * p2[2] - p1[2] * p2[0])
                          + p0[2] * (p1[0] * p2[1] - p1[1] * p2[0])) / 6.0
        return total


class Shell:
    """Accumulateur de maillages par matériau."""

    def __init__(self) -> None:
        self.meshes: dict[str, Mesh] = {}

    def mesh(self, material: str) -> Mesh:
        return self.meshes.setdefault(material, Mesh(material))

    def box(self, frame: "Frame", s0: float, s1: float, t0: float, t1: float, z0: float, z1: float,
            materials: dict[str, str] | str) -> None:
        """Boîte dans le repère d'un mur : s le long du mur, t en travers, z en hauteur.

        `materials` : un matériau pour toutes les faces, ou un dict par face parmi
        `top bottom back front start end` (`front` = côté t0, `back` = côté t1).
        """
        if s1 - s0 < 1e-6 or z1 - z0 < 1e-6 or t1 - t0 < 1e-6:
            return
        mats = {k: materials for k in ("top", "bottom", "front", "back", "start", "end")} if isinstance(materials, str) \
            else materials
        p = [frame.at(s, t, z) for z in (z0, z1) for (s, t) in ((s0, t0), (s1, t0), (s1, t1), (s0, t1))]
        faces = {"bottom": (0, 3, 2, 1), "top": (4, 5, 6, 7), "front": (0, 1, 5, 4), "back": (2, 3, 7, 6),
                 "start": (3, 0, 4, 7), "end": (1, 2, 6, 5)}
        for name, idx in faces.items():
            self.mesh(mats[name]).add_face([p[i] for i in idx])

    def polygon_top(self, poly: list[Point], z: float, material: str) -> None:
        """Face horizontale regardant vers le HAUT. Le miroir y -> -y inverse l'orientation : on triangule après miroir."""
        blender = [(p[0], -p[1]) for p in poly]
        for tri in triangulate(blender):
            self.mesh(material).add_face([(blender[i][0], blender[i][1], z) for i in tri])

    @property
    def triangles(self) -> int:
        return sum(m.triangles() for m in self.meshes.values())


@dataclass(frozen=True)
class Frame:
    """Repère d'un mur : origine au point `a`, u le long du mur, n en travers (n = z x u)."""

    ox: float
    oy: float
    ux: float
    uy: float

    @classmethod
    def of(cls, wall: Wall) -> "Frame":
        ax, ay = wall.a[0], -wall.a[1]
        bx, by = wall.b[0], -wall.b[1]
        length = math.hypot(bx - ax, by - ay) or 1.0
        return cls(ax, ay, (bx - ax) / length, (by - ay) / length)

    def at(self, s: float, t: float, z: float) -> Vec:
        return (self.ox + self.ux * s - self.uy * t, self.oy + self.uy * s + self.ux * t, z)

    def normal(self) -> tuple[float, float]:
        return (-self.uy, self.ux)


def planar_uvs(mesh: Mesh, tile: float) -> list[tuple[float, float]]:
    """Coordonnées de texture par sommet de face (dans l'ordre des faces), en projection plane sur l'axe dominant de la
    normale ; `tile` mètres = une répétition. Les murs et les sols étant droits, c'est exact et sans couture visible."""
    uvs: list[tuple[float, float]] = []
    for face in mesh.faces:
        pts = [mesh.verts[i] for i in face]
        nx = ny = nz = 0.0
        for k, a in enumerate(pts):                                    # normale de Newell
            b = pts[(k + 1) % len(pts)]
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        ax, ay, az = abs(nx), abs(ny), abs(nz)
        for x, y, z in pts:
            if az >= ax and az >= ay:
                uvs.append((x / tile, y / tile))
            elif ax >= ay:
                uvs.append((y / tile, z / tile))
            else:
                uvs.append((x / tile, z / tile))
    return uvs


# -- matériaux ------------------------------------------------------------------------------------
WALL_EXT, WALL_INT, TRIM, DOOR, GLASS, GARAGE, SLAB, HANDLE, PLINTH = ("wall_ext", "wall_int", "trim", "door", "glass",
                                                                       "garage", "slab", "handle", "plinth")
BASEBOARD_H, BASEBOARD_T, CROWN_H, CROWN_T, PLINTH_H = 0.10, 0.014, 0.07, 0.02, 0.25


def floor_material(room_type: str) -> str:
    return f"floor:{room_type}"


# -- coque -----------------------------------------------------------------------------------------
def build_shell(plan: Plan, *, extend_ends: bool = True, floors: bool = True, slab: bool = True,
                mouldings: bool = True) -> Shell:
    shell = Shell()
    centre = (plan.width / 2, -plan.depth / 2)
    by_wall: dict[str, list[Opening]] = {}
    for op in plan.openings:
        by_wall.setdefault(op.wall_id, []).append(op)
    for wall in plan.walls:
        _wall(shell, plan, wall, sorted(by_wall.get(wall.id, []), key=lambda o: o.offset), centre, extend_ends, mouldings)
    if floors:
        for room in plan.rooms:
            shell.polygon_top(room.polygon, 0.0, floor_material(room.type))
    if slab:
        w, d = plan.width, plan.depth
        pad = 0.05
        shell.polygon_top([(-pad, -pad), (w + pad, -pad), (w + pad, d + pad), (-pad, d + pad)], -0.005, SLAB)
    return shell


def _wall(shell: Shell, plan: Plan, wall: Wall, openings: list[Opening], centre: tuple[float, float],
          extend_ends: bool, mouldings: bool = True) -> None:
    frame = Frame.of(wall)
    length, th, height = wall.length, wall.thickness, plan.wall_height
    half = th / 2
    # Côté du mur tourné vers l'intérieur de la maison : c'est lui qui reçoit la peinture intérieure.
    mid = frame.at(length / 2, 0, 0)
    nx, ny = frame.normal()
    inward_is_back = (centre[0] - mid[0]) * nx + (centre[1] - mid[1]) * ny > 0        # côté +n regarde le centre
    if wall.exterior:
        mats = {"front": WALL_EXT if inward_is_back else WALL_INT, "back": WALL_INT if inward_is_back else WALL_EXT,
                "top": WALL_EXT, "bottom": WALL_EXT, "start": WALL_EXT, "end": WALL_EXT}
    else:
        mats = {k: WALL_INT for k in ("top", "bottom", "front", "back", "start", "end")}
    ext = half if extend_ends else 0.0
    s_lo, s_hi = -ext, length + ext

    def solid(s0: float, s1: float, z0: float, z1: float) -> None:
        shell.box(frame, s0, s1, -half, half, z0, z1, mats)

    cursor = s_lo
    for op in openings:
        o0 = max(cursor, op.offset)
        o1 = min(s_hi, op.offset + op.width)
        if o1 - o0 < 0.05:
            continue
        solid(cursor, o0, 0.0, height)                                    # plein jusqu'à l'ouverture
        if op.sill > 0:
            solid(o0, o1, 0.0, min(op.sill, height))                       # allège sous une fenêtre (jamais plus haute que la coupe)
        top = min(height, op.sill + op.height)
        if top < height - 1e-6:
            solid(o0, o1, top, height)                                    # linteau
        if op.sill < height - 0.1:                                        # une ouverture entièrement sous la coupe n'existe plus
            _opening_fittings(shell, frame, wall, op, o0, o1, top)
        cursor = o1
    solid(cursor, s_hi, 0.0, height)
    if mouldings:
        _mouldings(shell, frame, wall, openings, s_lo, s_hi, height, inward_is_back)


def _mouldings(shell: Shell, frame: Frame, wall: Wall, openings: list[Opening], s_lo: float, s_hi: float, height: float,
               inward_is_back: bool) -> None:
    """Plinthes au pied des murs, corniche sous le plafond, soubassement à l'extérieur : ce qui fait un mur fini."""
    half = wall.thickness / 2
    inner = [1.0 if inward_is_back else -1.0] if wall.exterior else [-1.0, 1.0]
    gaps = sorted((max(s_lo, o.offset), min(s_hi, o.offset + o.width)) for o in openings if o.kind != "window")
    runs, cursor = [], s_lo
    for g0, g1 in gaps:                                     # la plinthe s'arrête aux portes
        if g0 > cursor:
            runs.append((cursor, g0))
        cursor = max(cursor, g1)
    if s_hi > cursor:
        runs.append((cursor, s_hi))
    for sign in inner:
        t0, t1 = (half, half + BASEBOARD_T) if sign > 0 else (-half - BASEBOARD_T, -half)
        for a, b in runs:
            shell.box(frame, a, b, t0, t1, 0.0, BASEBOARD_H, TRIM)
        if height >= 2.3:                                   # pas de corniche sur un mur coupé pour l'aperçu
            c0, c1 = (half, half + CROWN_T) if sign > 0 else (-half - CROWN_T, -half)
            shell.box(frame, s_lo, s_hi, c0, c1, height - CROWN_H, height, TRIM)
    if wall.exterior:
        out = -inner[0]
        p0, p1 = (half, half + 0.012) if out > 0 else (-half - 0.012, -half)
        for a, b in runs:
            shell.box(frame, a, b, p0, p1, 0.0, PLINTH_H, PLINTH)


def _opening_fittings(shell: Shell, frame: Frame, wall: Wall, op: Opening, s0: float, s1: float, top: float) -> None:
    half = wall.thickness / 2
    z0 = op.sill
    tw = 0.05                                                              # largeur du chambranle
    trim_t = half + 0.012
    if op.kind == "window":
        shell.box(frame, s0, s0 + tw, -trim_t, trim_t, z0, top, TRIM)
        shell.box(frame, s1 - tw, s1, -trim_t, trim_t, z0, top, TRIM)
        shell.box(frame, s0, s1, -trim_t, trim_t, z0, z0 + tw, TRIM)
        shell.box(frame, s0, s1, -trim_t, trim_t, top - tw, top, TRIM)
        mid = (s0 + s1) / 2
        shell.box(frame, mid - 0.012, mid + 0.012, -0.012, 0.012, z0 + tw, top - tw, TRIM)          # meneau
        shell.box(frame, s0 + tw, s1 - tw, -0.008, 0.008, z0 + tw, top - tw, GLASS)               # vitre
        shell.box(frame, s0 - 0.03, s1 + 0.03, -trim_t - 0.05, trim_t + 0.05, z0 - 0.03, z0, TRIM)  # appui
        return
    if op.kind == "garage":
        shell.box(frame, s0, s1, -half * 0.6, half * 0.6, 0.0, top, GARAGE)
        for k in range(1, 4):                                                                      # panneaux
            z = top * k / 4
            shell.box(frame, s0, s1, -half * 0.6 - 0.008, half * 0.6 + 0.008, z - 0.012, z + 0.012, TRIM)
        return
    shell.box(frame, s0, s0 + tw, -trim_t, trim_t, 0.0, top, TRIM)
    shell.box(frame, s1 - tw, s1, -trim_t, trim_t, 0.0, top, TRIM)
    shell.box(frame, s0 + tw, s1 - tw, -trim_t, trim_t, top - tw, top, TRIM)
    shell.box(frame, s0 + tw, s1 - tw, -0.02, 0.02, 0.0, top - tw, DOOR)                          # vantail fermé
    for z0, z1 in ((0.12, 1.02), (1.22, top - tw - 0.12)):                                        # panneaux en relief
        if z1 - z0 > 0.2 and (s1 - s0) > 0.5:
            shell.box(frame, s0 + tw + 0.07, s1 - tw - 0.07, 0.02, 0.028, z0, z1, DOOR)
            shell.box(frame, s0 + tw + 0.07, s1 - tw - 0.07, -0.028, -0.02, z0, z1, DOOR)
    shell.box(frame, s1 - tw - 0.11, s1 - tw - 0.07, -0.05, 0.05, 1.0, 1.04, HANDLE)              # poignée


# -- triangulation ---------------------------------------------------------------------------------
def triangulate(poly: list[Point]) -> list[tuple[int, int, int]]:
    """Découpage en triangles d'un polygone simple (oreilles). Les triangles sortent antihoraires (normale vers +Z)."""
    n = len(poly)
    if n < 3:
        return []
    area2 = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    order = list(range(n)) if area2 > 0 else list(range(n))[::-1]
    tris: list[tuple[int, int, int]] = []
    guard = 0
    while len(order) > 3 and guard < 10000:
        guard += 1
        for k in range(len(order)):
            a, b, c = order[k - 1], order[k], order[(k + 1) % len(order)]
            if _cross(poly[a], poly[b], poly[c]) > 1e-12 and not any(
                    _inside(poly[o], poly[a], poly[b], poly[c]) for o in order if o not in (a, b, c)):
                tris.append((a, b, c))
                order.pop(k)
                break
        else:
            break
    if len(order) == 3:
        tris.append((order[0], order[1], order[2]))
    return tris


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _inside(p: Point, a: Point, b: Point, c: Point) -> bool:
    d1, d2, d3 = _cross(a, b, p), _cross(b, c, p), _cross(c, a, p)
    neg = d1 < -1e-12 or d2 < -1e-12 or d3 < -1e-12
    pos = d1 > 1e-12 or d2 > 1e-12 or d3 > 1e-12
    return not (neg and pos)
