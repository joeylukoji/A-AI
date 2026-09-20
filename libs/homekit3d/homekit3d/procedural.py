"""Pièces construites par code quand aucun pack ne les fournit (voiture, cheminée). Python pur.

Repère local, déjà en Blender : origine au centre de l'emprise et au sol, +X à droite, l'avant de la pièce vers -Y
(le sud du plan, puisque Y = -y), Z en haut. Dimensions en mètres.
"""
from __future__ import annotations

import math

from .geometry import Mesh, Shell, Frame

PROCEDURAL_ROLES = {"car": (4.3, 1.8, 1.45), "fireplace": (0.9, 0.5, 1.15)}


def build(role: str, footprint: tuple[float, float] | None = None) -> dict[str, Mesh]:
    if role == "car":
        return _car(*(footprint or PROCEDURAL_ROLES["car"][:2]))
    if role == "fireplace":
        return _fireplace(*(footprint or PROCEDURAL_ROLES["fireplace"][:2]))
    raise KeyError(role)


def _frame() -> Frame:
    return Frame(0.0, 0.0, 1.0, 0.0)


def _car(length: float, width: float) -> dict[str, Mesh]:
    """Berline stylisée : caisse, habitacle vitré, quatre roues. `length` selon Y (avant vers -Y), `width` selon X."""
    sh, f = Shell(), _frame()
    # Dans le repère `Frame` (s = X, t = Y), on pose la longueur de la voiture selon t.
    hl, hw = length / 2, width / 2
    sh.box(f, -hw, hw, -hl, hl, 0.28, 0.78, "car_body")                                # caisse
    sh.box(f, -hw * 0.86, hw * 0.86, -hl * 0.42, hl * 0.30, 0.78, 1.32, "car_glass")   # habitacle
    sh.box(f, -hw * 0.80, hw * 0.80, -hl * 0.30, hl * 0.18, 1.32, 1.36, "car_body")    # toit
    sh.box(f, -hw * 0.9, hw * 0.9, -hl - 0.03, -hl + 0.06, 0.42, 0.62, "car_light")    # calandre
    for sx in (-1, 1):
        for ty in (-0.32, 0.30):
            cx, cy = sx * (hw - 0.09), ty * length
            _cylinder_x(sh, cx, cy, 0.34, 0.24, "tire")
    return sh.meshes


def _cylinder_x(sh: Shell, cx: float, cy: float, radius: float, thickness: float, material: str, seg: int = 14) -> None:
    """Roue : cylindre d'axe X posé au sol."""
    z0 = radius
    x0, x1 = cx - thickness / 2, cx + thickness / 2
    ring = [(cy + radius * math.cos(2 * math.pi * k / seg), z0 + radius * math.sin(2 * math.pi * k / seg)) for k in range(seg)]
    m = sh.mesh(material)
    for k in range(seg):
        (ya, za), (yb, zb) = ring[k], ring[(k + 1) % seg]
        m.add_face([(x0, ya, za), (x0, yb, zb), (x1, yb, zb), (x1, ya, za)])
    for x, order in ((x0, 1), (x1, -1)):
        pts = [(x, y, z) for y, z in ring]
        m.add_face(pts if order == 1 else pts[::-1])


def _fireplace(width: float, depth: float) -> dict[str, Mesh]:
    """Cheminée : socle, foyer sombre, manteau et conduit. Le dos est contre le mur (+Y)."""
    sh, f = Shell(), _frame()
    hw, hd = width / 2, depth / 2
    sh.box(f, -hw, hw, -hd, hd, 0.0, 0.16, "stone")                                     # âtre
    sh.box(f, -hw * 0.9, hw * 0.9, -hd * 0.5, hd, 0.16, 1.0, "stone")                   # corps
    sh.box(f, -hw * 0.55, hw * 0.55, -hd * 0.52, -hd * 0.3, 0.24, 0.70, "fire_box")      # foyer
    sh.box(f, -hw, hw, -hd * 0.7, hd, 1.0, 1.06, "wood_dark")                            # manteau
    sh.box(f, -hw * 0.45, hw * 0.45, hd * 0.1, hd, 1.06, 2.5, "stone")                  # conduit
    return sh.meshes


PROCEDURAL_COLORS = {
    "car_body": ((0.62, 0.66, 0.72), 0.35, 0.4, 1.0), "car_glass": ((0.35, 0.5, 0.62), 0.1, 0.0, 0.55),
    "car_light": ((0.95, 0.9, 0.6), 0.3, 0.0, 1.0), "tire": ((0.08, 0.08, 0.09), 0.9, 0.0, 1.0),
    "stone": ((0.72, 0.70, 0.66), 0.9, 0.0, 1.0), "fire_box": ((0.12, 0.10, 0.10), 0.9, 0.0, 1.0),
    "wood_dark": ((0.32, 0.22, 0.15), 0.6, 0.0, 1.0),
}
