"""Modèle de plan et outils pour en construire un directement, sans dépendre d'un autre projet.

Repère : mètres, x vers la droite, y vers le BAS (comme un plan vu de dessus). Un meuble tourné de 0° a le dos
au nord (y décroissant) et regarde le sud ; la rotation est en degrés, dans le sens des aiguilles d'une montre.

    plan = Plan(width=10, depth=8)
    salon = plan.room("living", [(0, 0), (6, 0), (6, 5), (0, 5)], name="Séjour")
    plan.walls_from_rooms()
    plan.door(plan.wall_between(salon, ...), at=1.0)
    plan.place("sofa", x=3.0, y=4.3, rot=0, room=salon)
"""
from __future__ import annotations

import itertools
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

Point = tuple[float, float]

# Correspondance avec les identifiants du catalogue historique d'A-AI (`furnish.py`).
AAI_ROLES = {
    "bed.single": "bed.single", "bed.double": "bed.double", "table.dining": "table.dining", "table.coffee": "table.coffee",
    "sofa.2seat": "sofa", "sofa.lshape": "sofa.corner", "armchair": "armchair", "nightstand": "nightstand",
    "wardrobe": "wardrobe", "counter.kitchen": "kitchen.run", "stove": "kitchen.stove", "desk": "desk",
    "fireplace": "fireplace", "bathtub": "bathtub", "toilet": "toilet", "sink.basin": "sink.bath",
    "car.sedan": "car", "rug.rect": "rug", "plant.pot": "plant", "fridge": "kitchen.fridge",
    "tv.console": "tv.console", "chair.dining": "chair.dining",
}

DOOR_HEIGHT, WINDOW_SILL, WINDOW_HEIGHT, GARAGE_DOOR_MIN_WIDTH = 2.05, 0.9, 1.2, 1.3


@dataclass
class Wall:
    id: str
    a: Point
    b: Point
    thickness: float = 0.15
    exterior: bool = False

    @property
    def length(self) -> float:
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])


@dataclass
class Room:
    id: str
    type: str
    polygon: list[Point]
    name: str = ""

    def bbox(self) -> tuple[float, float, float, float]:
        xs, ys = [p[0] for p in self.polygon], [p[1] for p in self.polygon]
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def area(self) -> float:
        s = 0.0
        for i, p in enumerate(self.polygon):
            q = self.polygon[(i + 1) % len(self.polygon)]
            s += p[0] * q[1] - q[0] * p[1]
        return abs(s) / 2


@dataclass
class Opening:
    id: str
    wall_id: str
    kind: str                     # door | window | garage
    offset: float                 # distance depuis le point `a` du mur
    width: float = 0.9
    height: float = DOOR_HEIGHT
    sill: float = 0.0


@dataclass
class Item:
    """Un objet posé : un rôle du catalogue (ou un modèle précis), une position au sol et une rotation."""

    id: str
    role: str
    x: float
    y: float
    rot: float = 0.0
    room: str = ""
    asset: str = ""               # identifiant de modèle imposé ; sinon choisi par le styliste
    size: tuple[float, float] | None = None       # (largeur x, profondeur z) voulues, sinon celles du modèle
    elevation: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Style:
    name: str = "moderne"
    tags: list[str] = field(default_factory=lambda: ["modern"])
    prefer_pack: str = "kenney-furniture"
    wall_exterior: tuple[float, float, float] = (0.93, 0.91, 0.87)
    wall_interior: tuple[float, float, float] = (0.96, 0.95, 0.92)
    floors: dict[str, tuple[float, float, float]] = field(default_factory=lambda: {
        "living": (0.78, 0.64, 0.46), "dining": (0.78, 0.64, 0.46), "bedroom": (0.82, 0.70, 0.52),
        "office": (0.80, 0.68, 0.50), "hallway": (0.74, 0.62, 0.45), "kitchen": (0.86, 0.85, 0.82),
        "bathroom": (0.72, 0.80, 0.85), "wc": (0.72, 0.80, 0.85), "laundry": (0.80, 0.82, 0.84),
        "garage": (0.62, 0.62, 0.60), "storage": (0.72, 0.70, 0.66),
    })
    accent: tuple[float, float, float] = (0.36, 0.55, 0.55)


class PlanError(ValueError):
    pass


@dataclass
class Plan:
    width: float
    depth: float
    height: float = 2.7
    walls: list[Wall] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)
    openings: list[Opening] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    style: Style = field(default_factory=Style)
    seed: int = 0
    cutaway: float | None = None          # hauteur de coupe des murs (m) pour un aperçu « maison de poupée » ; None = murs entiers
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1), repr=False, compare=False)

    # -- construction ---------------------------------------------------------------------
    def _new_id(self, prefix: str) -> str:
        return f"{prefix}{next(self._ids)}"

    def wall(self, a: Point, b: Point, *, thickness: float | None = None, exterior: bool | None = None,
             id: str | None = None) -> str:
        if exterior is None:
            exterior = self._on_boundary(a, b)
        wall = Wall(id or self._new_id("w"), (float(a[0]), float(a[1])), (float(b[0]), float(b[1])),
                    thickness if thickness is not None else (0.25 if exterior else 0.12), bool(exterior))
        if wall.length < 0.05:
            raise PlanError(f"mur trop court : {a} -> {b}")
        self.walls.append(wall)
        return wall.id

    def room(self, type: str, polygon: Iterable[Point], *, name: str = "", id: str | None = None) -> str:
        pts = [(float(x), float(y)) for x, y in polygon]
        if len(pts) < 3:
            raise PlanError("une pièce a au moins 3 sommets")
        room = Room(id or self._new_id("r"), type, pts, name or type)
        self.rooms.append(room)
        return room.id

    def rect_room(self, type: str, x0: float, y0: float, x1: float, y1: float, **kw: Any) -> str:
        return self.room(type, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **kw)

    def outline(self) -> list[str]:
        """Les quatre murs extérieurs de l'emprise."""
        w, d = self.width, self.depth
        return [self.wall((0, 0), (w, 0), exterior=True), self.wall((w, 0), (w, d), exterior=True),
                self.wall((w, d), (0, d), exterior=True), self.wall((0, d), (0, 0), exterior=True)]

    def walls_from_rooms(self) -> list[str]:
        """Un mur par arête de pièce (les arêtes communes n'en donnent qu'un), plus les murs de l'emprise s'ils manquent."""
        made: list[str] = []
        seen = {self._edge_key(w.a, w.b) for w in self.walls}
        for room in self.rooms:
            for i, p in enumerate(room.polygon):
                q = room.polygon[(i + 1) % len(room.polygon)]
                key = self._edge_key(p, q)
                if key in seen or self._on_boundary(p, q):
                    continue
                seen.add(key)
                made.append(self.wall(p, q, exterior=False))
        if not any(w.exterior for w in self.walls):
            made += self.outline()
        return made

    def wall_at(self, x: float, y: float, *, tol: float = 0.2) -> str | None:
        """Le mur le plus proche d'un point (dans `tol`), ou None."""
        best, best_d = None, tol
        for w in self.walls:
            d = _dist_point_segment((x, y), w.a, w.b)
            if d < best_d:
                best, best_d = w.id, d
        return best

    def door(self, wall_id: str, at: float, *, width: float = 0.9, kind: str | None = None) -> str:
        wall = self._wall(wall_id)
        kind = kind or ("garage" if width >= GARAGE_DOOR_MIN_WIDTH else "door")
        height = 2.3 if kind == "garage" else DOOR_HEIGHT
        return self._opening(wall, kind, at, width, height, 0.0)

    def window(self, wall_id: str, at: float, *, width: float = 1.2, sill: float = WINDOW_SILL,
               height: float = WINDOW_HEIGHT) -> str:
        return self._opening(self._wall(wall_id), "window", at, width, height, sill)

    def place(self, role: str, x: float, y: float, rot: float = 0.0, *, room: str = "", asset: str = "",
              size: tuple[float, float] | None = None, elevation: float = 0.0, **meta: Any) -> str:
        item = Item(self._new_id("i"), role, float(x), float(y), float(rot), room or self.room_at(x, y) or "", asset,
                    size, elevation, dict(meta))
        self.items.append(item)
        return item.id

    # -- consultation ---------------------------------------------------------------------
    def room_at(self, x: float, y: float) -> str | None:
        for room in self.rooms:
            if _point_in_polygon((x, y), room.polygon):
                return room.id
        return None

    def get_room(self, room_id: str) -> Room:
        for r in self.rooms:
            if r.id == room_id:
                return r
        raise KeyError(room_id)

    def rooms_of(self, type: str) -> list[Room]:
        return [r for r in self.rooms if r.type == type]

    def _wall(self, wall_id: str) -> Wall:
        for w in self.walls:
            if w.id == wall_id:
                return w
        raise PlanError(f"mur inconnu : {wall_id}")

    def _opening(self, wall: Wall, kind: str, at: float, width: float, height: float, sill: float) -> str:
        offset = float(at)
        if offset < 0 or offset + width > wall.length + 1e-6:
            raise PlanError(f"{kind} hors du mur {wall.id} (offset {offset}, largeur {width}, mur {wall.length:.2f} m)")
        op = Opening(self._new_id("o"), wall.id, kind, offset, float(width), float(height), float(sill))
        self.openings.append(op)
        return op.id

    def _on_boundary(self, a: Point, b: Point, tol: float = 0.05) -> bool:
        w, d = self.width, self.depth
        return ((abs(a[0]) < tol and abs(b[0]) < tol) or (abs(a[0] - w) < tol and abs(b[0] - w) < tol)
                or (abs(a[1]) < tol and abs(b[1]) < tol) or (abs(a[1] - d) < tol and abs(b[1] - d) < tol))

    @staticmethod
    def _edge_key(a: Point, b: Point) -> tuple:
        p, q = (round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2))
        return (p, q) if p <= q else (q, p)

    # -- validation, sérialisation ----------------------------------------------------------
    @property
    def wall_height(self) -> float:
        """Hauteur à laquelle les murs sont construits : la coupe si elle est demandée, sinon la hauteur sous plafond."""
        return min(self.cutaway, self.height) if self.cutaway else self.height

    def validate(self) -> None:
        if self.width <= 0 or self.depth <= 0 or not 2.0 <= self.height <= 6.0:
            raise PlanError("emprise ou hauteur invalide")
        if self.cutaway is not None and not 0.3 <= self.cutaway <= self.height:
            raise PlanError("hauteur de coupe invalide")
        ids = [w.id for w in self.walls]
        if len(ids) != len(set(ids)):
            raise PlanError("identifiants de mur en double")
        for op in self.openings:
            wall = self._wall(op.wall_id)
            if op.offset < -1e-6 or op.offset + op.width > wall.length + 1e-6:
                raise PlanError(f"ouverture {op.id} hors du mur {wall.id}")
        for room in self.rooms:
            if room.area <= 0.5:
                raise PlanError(f"pièce {room.id} de surface nulle")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1, "width": self.width, "depth": self.depth, "height": self.height, "seed": self.seed,
            "cutaway": self.cutaway,
            "walls": [asdict(w) for w in self.walls], "rooms": [asdict(r) for r in self.rooms],
            "openings": [asdict(o) for o in self.openings], "items": [asdict(i) for i in self.items],
            "style": asdict(self.style),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        plan = cls(float(data["width"]), float(data["depth"]), float(data.get("height", 2.7)), seed=int(data.get("seed", 0)))
        plan.cutaway = float(data["cutaway"]) if data.get("cutaway") else None
        plan.walls = [Wall(w["id"], tuple(w["a"]), tuple(w["b"]), float(w.get("thickness", 0.15)), bool(w.get("exterior")))
                      for w in data.get("walls", [])]
        plan.rooms = [Room(r["id"], r["type"], [tuple(p) for p in r["polygon"]], r.get("name", r["type"]))
                      for r in data.get("rooms", [])]
        plan.openings = [Opening(o["id"], o["wall_id"], o["kind"], float(o["offset"]), float(o.get("width", 0.9)),
                                 float(o.get("height", DOOR_HEIGHT)), float(o.get("sill", 0.0)))
                         for o in data.get("openings", [])]
        plan.items = [Item(i["id"], i["role"], float(i["x"]), float(i["y"]), float(i.get("rot", 0.0)), i.get("room", ""),
                           i.get("asset", ""), tuple(i["size"]) if i.get("size") else None, float(i.get("elevation", 0.0)),
                           dict(i.get("meta") or {})) for i in data.get("items", [])]
        style = data.get("style")
        if style:
            base = Style()
            for key, value in style.items():
                if key in ("wall_exterior", "wall_interior", "accent"):
                    value = tuple(value)
                elif key == "floors":
                    value = {k: tuple(v) for k, v in value.items()}
                if hasattr(base, key):
                    setattr(base, key, value)
            plan.style = base
        plan._ids = itertools.count(1 + len(plan.walls) + len(plan.rooms) + len(plan.openings) + len(plan.items) + 1000)
        return plan

    # -- pont vers A-AI ---------------------------------------------------------------------
    @classmethod
    def from_aai(cls, doc: dict[str, Any], *, seed: int = 0) -> "Plan":
        """Convertit un `PlanDocument` d'A-AI (murs, pièces, ouvertures, mobilier déjà posé)."""
        bounds = (doc.get("floor") or {}).get("bounds") or {}
        plan = cls(float(bounds.get("width") or 12), float(bounds.get("depth") or 10),
                   float((doc.get("floor") or {}).get("height_m") or 2.7), seed=seed)
        for w in doc.get("walls") or []:
            a, b = (float(w["a"]["x"]), float(w["a"]["y"])), (float(w["b"]["x"]), float(w["b"]["y"]))
            exterior = str(w.get("id", "")).startswith("w_outer") or plan._on_boundary(a, b)
            thickness = float(w.get("thickness_m") or (0.25 if exterior else 0.12))
            plan.walls.append(Wall(str(w["id"]), a, b, max(0.08, thickness), exterior))
        for r in doc.get("rooms") or []:
            poly = [(float(p["x"]), float(p["y"])) for p in r.get("polygon") or []]
            if len(poly) >= 3:
                plan.rooms.append(Room(str(r["id"]), str(r.get("type") or "other"), poly, str(r.get("name") or r.get("type") or "")))
        walls = {w.id: w for w in plan.walls}
        for o in doc.get("openings") or []:
            wall = walls.get(str(o.get("wall_id")))
            if wall is None:
                continue
            width = float(o.get("width_m") or (1.2 if o.get("type") == "window" else 0.9))
            offset = max(0.0, min(float(o.get("offset_m") or 0.0), max(0.0, wall.length - width)))
            if o.get("type") == "window":
                plan.openings.append(Opening(str(o["id"]), wall.id, "window", offset, width, WINDOW_HEIGHT, WINDOW_SILL))
            else:
                kind = "garage" if width >= GARAGE_DOOR_MIN_WIDTH else "door"
                plan.openings.append(Opening(str(o["id"]), wall.id, kind, offset, width, 2.3 if kind == "garage" else DOOR_HEIGHT, 0.0))
        for f in doc.get("furniture") or []:
            pos, size = f.get("position") or {}, f.get("size_m") or {}
            role = AAI_ROLES.get(str(f.get("catalog_id")))
            if role is None or "x" not in pos:
                continue
            plan.items.append(Item(str(f.get("id") or plan._new_id("i")), role, float(pos["x"]), float(pos["y"]),
                                   float(f.get("rotation_deg") or 0.0), str(f.get("room_id") or ""), "",
                                   (float(size["w"]), float(size["d"])) if size.get("w") and size.get("d") else None,
                                   0.0, {"catalog_id": f.get("catalog_id"), "height": size.get("h")}))
        plan._ids = itertools.count(5000)
        return plan


# -- géométrie 2D élémentaire -------------------------------------------------------------------
def _dist_point_segment(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def _point_in_polygon(p: Point, poly: list[Point]) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1, x2, y2 = poly[i][0], poly[i][1], poly[(i + 1) % n][0], poly[(i + 1) % n][1]
        if (y1 > p[1]) != (y2 > p[1]) and p[0] < (x2 - x1) * (p[1] - y1) / ((y2 - y1) or 1e-12) + x1:
            inside = not inside
    return inside
