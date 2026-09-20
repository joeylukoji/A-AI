"""Du plan aux objets à poser : choix des modèles, échelle, pose, cuisine en éléments juxtaposés. Python pur.

Blender n'intervient qu'après : `blender_scene` lit la liste de `Placed` produite ici. Tout ce qui peut se
tromper (orientation, taille, choix du modèle) est donc testable sans lancer Blender.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .catalog import Asset, Catalog
from .plan import Item, Plan
from .procedural import PROCEDURAL_ROLES

# Hauteur de pose (m) des objets fixés au mur ou au plafond, si l'objet n'en précise pas.
DEFAULT_ELEVATION = {"picture": 1.45, "mirror": 1.25, "lamp.wall": 1.85, "kitchen.upper": 1.45, "shelf.wall": 1.5}
# Rôles étirés à la taille demandée (plats : l'épaisseur ne bouge pas).
STRETCH_ROLES = {"rug"}
# Rôles dont la longueur est selon x dans le plan A-AI et selon la profondeur dans le modèle : tournés d'un quart de tour.
LENGTHWISE_ROLES = {"car"}
# Rôles portés par un autre meuble (posés sur lui) : la hauteur vient de l'objet porteur.
FIT_MIN, FIT_MAX = 0.7, 1.25


@dataclass
class Placed:
    """Un objet prêt à être posé dans la scène (repère plan : x, y vers le bas ; rotation horaire en degrés)."""

    kind: str                       # asset | procedural
    role: str
    x: float
    y: float
    z: float = 0.0
    rot: float = 0.0
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)    # échelle appliquée aux axes NATIFS du fichier (x, y haut, z)
    asset: Asset | None = None
    footprint: tuple[float, float] | None = None           # pour les objets construits par code
    item_id: str = ""
    room: str = ""


@dataclass
class Assembly:
    placed: list[Placed] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)       # rôles sans modèle : signalés, jamais silencieux

    @property
    def asset_ids(self) -> set[str]:
        return {p.asset.id for p in self.placed if p.asset}


def assemble(plan: Plan, catalog: Catalog) -> Assembly:
    out = Assembly()
    rooms = {r.id: r for r in plan.rooms}
    style_tags = list(plan.style.tags)
    runs = [i for i in plan.items if i.role == "kitchen.run"]
    for item in plan.items:
        if plan.cutaway and (item.elevation >= plan.cutaway - 0.05 or item.role == "lamp.ceiling"):
            continue                                   # accroché au-dessus de la coupe : il n'existe plus dans l'aperçu
        room_type = rooms[item.room].type if item.room in rooms else None
        if item.role == "kitchen.run":
            out.placed.extend(_kitchen_run(item, plan, catalog, room_type, runs))
            continue
        size = _catalog_size(item)
        if item.role in PROCEDURAL_ROLES and not item.asset:
            # Un modèle du catalogue si le style est réaliste et en a un (la Ferrari) ; sinon la pièce construite par code.
            pick = catalog.pick_fit(item.role, size, room=room_type, style=style_tags, seed=f"{plan.seed}:{item.id}",
                                    prefer_pack=plan.style.prefer_pack)
            if pick is None or not set(style_tags) & set(pick.tags):
                out.placed.append(_procedural(item))
                continue
            out.placed.append(_place_asset(item, pick, plan))
            continue
        asset = catalog.get(item.asset) if item.asset else catalog.pick_fit(
            item.role, size, room=room_type, style=style_tags, seed=f"{plan.seed}:{item.id}",
            prefer_pack=plan.style.prefer_pack)
        if asset is None:
            out.skipped.append(item.role)
            continue
        out.placed.append(_place_asset(item, asset, plan))
    return out


def _catalog_size(item: Item) -> tuple[float, float] | None:
    """A-AI donne la voiture couchée selon x ; les modèles du catalogue ont leur longueur selon la profondeur."""
    if item.size and item.role in LENGTHWISE_ROLES:
        return item.size[1], item.size[0]
    return item.size


def _place_asset(item: Item, asset: Asset, plan: Plan) -> Placed:
    s = asset.scale
    sx = sy = sz = s
    aw, ad = asset.footprint
    if item.size and item.role in LENGTHWISE_ROLES:
        k = min(FIT_MAX, max(FIT_MIN, item.size[0] / max(ad, 1e-6)))      # une voiture se cale sur sa longueur, pas ses rétroviseurs
        return Placed("asset", item.role, item.x, item.y, item.elevation, item.rot + 90.0, (s * k,) * 3, asset,
                      item_id=item.id, room=item.room)
    if item.size:
        w, d = item.size
        if item.role in STRETCH_ROLES:
            sx, sz = w / max(asset.size[0], 1e-6), d / max(asset.size[2], 1e-6)     # tapis : à la taille demandée
        else:
            fit = min(w / max(aw, 1e-6), d / max(ad, 1e-6))
            k = min(FIT_MAX, max(FIT_MIN, fit))
            sx, sy, sz = s * k, s * k, s * k
    z = item.elevation or DEFAULT_ELEVATION.get(item.role, 0.0)
    if item.role == "lamp.ceiling":
        z = plan.height - asset.height * (sy / s)
    return Placed("asset", item.role, item.x, item.y, z, item.rot, (sx, sy, sz), asset, item_id=item.id, room=item.room)


def _procedural(item: Item) -> Placed:
    length, width, _ = PROCEDURAL_ROLES[item.role]
    if item.size:
        # A-AI donne la longueur selon x local (voiture couchée à 0°) ; le modèle a sa longueur selon la profondeur.
        length, width = (item.size[0], item.size[1]) if item.role == "car" else (item.size[1], item.size[0])
    rot = item.rot + (90.0 if item.role == "car" else 0.0)
    return Placed("procedural", item.role, item.x, item.y, item.elevation, rot, footprint=(length, width) if item.role == "car"
                  else (width, length), item_id=item.id, room=item.room)


def _run_axis(item: Item) -> tuple[float, float]:
    """Vecteur unitaire (plan) le long de la longueur d'un plan de travail : sa largeur `w` est selon x local."""
    r = math.radians(item.rot)
    return math.cos(r), math.sin(r)


def _kitchen_run(item: Item, plan: Plan, catalog: Catalog, room_type: str | None, runs: list[Item]) -> list[Placed]:
    """Un plan de travail A-AI devient une file d'éléments : meubles bas, un évier, en évitant cuisinière et frigo."""
    length, depth = item.size or (2.4, 0.62)
    ux, uy = _run_axis(item)
    # Frontières occupées par cuisinière et frigo posés dans la même pièce, projetées sur l'axe du plan de travail.
    blocked: list[tuple[float, float]] = []
    for other in plan.items:
        if other.room == item.room and other.role in ("kitchen.stove", "kitchen.fridge") and other.size:
            proj = (other.x - item.x) * ux + (other.y - item.y) * uy
            blocked.append((proj - other.size[0] / 2 - 0.02, proj + other.size[0] / 2 + 0.02))
    lo, hi = -length / 2, length / 2
    free: list[tuple[float, float]] = []
    cur = lo
    for b0, b1 in sorted(blocked):
        if b1 <= cur or b0 >= hi:
            continue
        if b0 - cur > 0.3:
            free.append((cur, min(b0, hi)))
        cur = max(cur, b1)
    if hi - cur > 0.3:
        free.append((cur, hi))
    base = catalog.pick_fit("kitchen.base", (0.9, depth), room="kitchen", style=plan.style.tags,
                            seed=f"{plan.seed}:{item.id}", prefer_pack=plan.style.prefer_pack)
    sink = catalog.pick("kitchen.sink", room="kitchen", style=plan.style.tags, seed=f"{plan.seed}:{item.id}",
                        prefer_pack=base.pack if base else plan.style.prefer_pack)
    out: list[Placed] = []
    if base is None:
        return out
    sink_done = False
    longest = max(free, key=lambda f: f[1] - f[0], default=None)
    for a, b in free:
        n = max(1, round((b - a) / max(base.footprint[0], 0.3)))
        step = (b - a) / n
        for k in range(n):
            centre = a + step * (k + 0.5)
            use_sink = sink is not None and not sink_done and (a, b) == longest and k == n // 2 and n >= 2
            asset = sink if use_sink else base
            sink_done = sink_done or use_sink
            s = asset.scale
            sx = s * step / max(asset.footprint[0], 1e-6)              # la file remplit exactement la longueur
            sz = s * min(1.15, max(0.85, depth / max(asset.footprint[1], 1e-6)))
            out.append(Placed("asset", "kitchen.sink" if use_sink else "kitchen.base",
                              item.x + ux * centre, item.y + uy * centre, 0.0, item.rot, (sx, s, sz), asset,
                              item_id=f"{item.id}.{len(out)}", room=item.room))
    return out
