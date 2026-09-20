"""Styliste : choisit un style, meuble ce qui est vide et décore. Un LLM propose, des règles disposent.

Le principe (repris de Holodeck, CVPR 2024) : le modèle de langage apporte le bon sens (quel style, quel décor pour
quelle pièce) mais ne place JAMAIS rien lui-même ; ses réponses sont validées contre le catalogue puis un solveur
déterministe cherche la place, hors des dégagements de portes. Sans LLM, ou si sa réponse est invalide ou trop lente,
les mêmes choix sont faits par des règles à graine : le résultat est identique d'un lancement à l'autre.
"""
from __future__ import annotations

import json
import random
from dataclasses import replace
from typing import Callable

from .catalog import Asset, Catalog
from .furnish import autofurnish
from .layout import Occupancy, in_front, occupancy_of, rect_of, room_box
from .plan import Item, Plan, Room, Style

LLM = Callable[[str, str], str]

STYLES: dict[str, Style] = {
    "moderne": Style("moderne", ["realistic"], "sh3d-b", (0.93, 0.91, 0.87), (0.96, 0.95, 0.92)),
    "scandinave": Style("scandinave", ["realistic"], "sh3d-b", (0.95, 0.94, 0.91), (0.98, 0.98, 0.96),
                        floors={"living": (0.86, 0.75, 0.58), "dining": (0.86, 0.75, 0.58), "bedroom": (0.88, 0.78, 0.62),
                                "office": (0.86, 0.76, 0.60), "hallway": (0.82, 0.72, 0.56), "kitchen": (0.90, 0.90, 0.88),
                                "bathroom": (0.80, 0.86, 0.88), "wc": (0.80, 0.86, 0.88), "laundry": (0.86, 0.88, 0.88),
                                "garage": (0.66, 0.66, 0.64), "storage": (0.78, 0.76, 0.72)}, accent=(0.55, 0.68, 0.70)),
    "chaleureux": Style("chaleureux", ["realistic"], "sh3d-c", (0.90, 0.84, 0.74), (0.96, 0.92, 0.84),
                        floors={"living": (0.62, 0.44, 0.30), "dining": (0.62, 0.44, 0.30), "bedroom": (0.68, 0.50, 0.34),
                                "office": (0.64, 0.46, 0.32), "hallway": (0.60, 0.43, 0.30), "kitchen": (0.82, 0.78, 0.70),
                                "bathroom": (0.70, 0.76, 0.78), "wc": (0.70, 0.76, 0.78), "laundry": (0.78, 0.78, 0.76),
                                "garage": (0.58, 0.58, 0.56), "storage": (0.66, 0.62, 0.56)}, accent=(0.72, 0.44, 0.28)),
    # Poly Haven (scans à textures 1k, CC0) d'abord, puis les autres modèles réalistes ; plus lourd que les autres styles.
    "premium": Style("premium", ["realistic"], "polyhaven", (0.94, 0.93, 0.90), (0.97, 0.96, 0.94),
                     floors={"living": (0.70, 0.55, 0.38), "dining": (0.70, 0.55, 0.38), "bedroom": (0.74, 0.60, 0.42),
                             "office": (0.72, 0.58, 0.40), "hallway": (0.66, 0.52, 0.36), "kitchen": (0.84, 0.83, 0.80),
                             "bathroom": (0.74, 0.80, 0.83), "wc": (0.74, 0.80, 0.83), "laundry": (0.82, 0.83, 0.84),
                             "garage": (0.60, 0.60, 0.58), "storage": (0.70, 0.67, 0.62)}, accent=(0.30, 0.28, 0.26)),
    "classique": Style("classique", ["realistic"], "sh3d-c", (0.88, 0.85, 0.80), (0.94, 0.92, 0.88),
                       floors={"living": (0.55, 0.40, 0.28), "dining": (0.55, 0.40, 0.28), "bedroom": (0.60, 0.45, 0.32),
                               "office": (0.56, 0.42, 0.30), "hallway": (0.52, 0.38, 0.27), "kitchen": (0.78, 0.74, 0.68),
                               "bathroom": (0.66, 0.72, 0.74), "wc": (0.66, 0.72, 0.74), "laundry": (0.74, 0.74, 0.72),
                               "garage": (0.55, 0.55, 0.54), "storage": (0.62, 0.58, 0.52)}, accent=(0.45, 0.30, 0.22)),
}

# Les deux styles « jouet » (packs low-poly Kenney et KayKit) : gardés pour les maisons légères, jamais tirés au hasard.
STYLES["lowpoly"] = replace(STYLES["moderne"], name="lowpoly", tags=["modern"], prefer_pack="kenney-furniture")
STYLES["lowpoly-chaleureux"] = replace(STYLES["chaleureux"], name="lowpoly-chaleureux", tags=["cozy", "warm"],
                                       prefer_pack="kaykit-furniture")
# Styles choisis à la demande, jamais par tirage : le plus lourd (Poly Haven, plusieurs Mo de textures) et les deux low-poly.
HEAVY_STYLES = {"premium", "lowpoly", "lowpoly-chaleureux"}
def _shade(style: Style, floors: float = 0.80, exterior: float = 0.84, interior: float = 0.92) -> Style:
    """Les viewers web (model-viewer) éclairent fort : des teintes trop claires ressortent en aplats blancs."""
    def k(rgb, f):
        return tuple(round(c * f, 3) for c in rgb)
    style.wall_exterior, style.wall_interior = k(style.wall_exterior, exterior), k(style.wall_interior, interior)
    style.floors = {name: k(rgb, floors) for name, rgb in style.floors.items()}
    return style


for _style in STYLES.values():
    _shade(_style)

DECOR_ROLES = ["plant", "plant.small", "lamp.floor", "lamp.table", "picture", "rug", "books"]
MAX_DECOR_PER_ROOM = 4
DEFAULT_DECOR = {
    "living": ["plant", "lamp.floor", "picture", "rug"], "bedroom": ["lamp.table", "picture", "rug", "plant.small"],
    "dining": ["picture", "plant"], "kitchen": ["plant.small"], "hallway": ["plant", "picture"],
    "office": ["lamp.table", "plant.small", "books"], "bathroom": [], "wc": [], "garage": [], "laundry": [],
}


class Stylist:
    def __init__(self, catalog: Catalog, llm: LLM | None = None) -> None:
        self.catalog, self.llm = catalog, llm

    # -- point d'entrée ----------------------------------------------------------------------
    def style(self, plan: Plan, *, furnish: bool = True, brief: str = "", style: str | None = None) -> dict:
        """`style` impose un style (ex. « premium ») ; sinon le LLM propose, à défaut les règles tirent par graine."""
        report: dict = {"ai": False, "fallback_reason": None}
        proposal = self._ask(plan, brief, report)
        name = style if style in STYLES else (proposal.get("style") if proposal.get("style") in STYLES else self._pick_style(plan))
        plan.style = replace(STYLES[name])
        report["style"] = name
        if furnish:
            report["furnished"] = autofurnish(plan, self.catalog, only_empty=True)
        decor = self._decor(plan, proposal.get("rooms") or {})
        report["decor"] = self._place_decor(plan, decor)
        report["ai"] = bool(proposal)
        return report

    # -- choix -------------------------------------------------------------------------------
    def _pick_style(self, plan: Plan) -> str:
        names = sorted(n for n in STYLES if n not in HEAVY_STYLES)      # jamais 10 Mo de textures par hasard
        return names[random.Random(f"style:{plan.seed}").randrange(len(names))]

    def _ask(self, plan: Plan, brief: str, report: dict) -> dict:
        if self.llm is None:
            report["fallback_reason"] = "pas de LLM"
            return {}
        try:
            raw = self.llm(SYSTEM_PROMPT, json.dumps(self._context(plan, brief), ensure_ascii=False))
            return self._validate(json.loads(raw), plan)
        except Exception as exc:  # noqa: BLE001 - un LLM lent, en panne ou bavard ne doit jamais bloquer la génération
            report["fallback_reason"] = f"{type(exc).__name__}: {exc}"[:160]
            return {}

    def _context(self, plan: Plan, brief: str) -> dict:
        rooms = []
        for r in plan.rooms:
            x0, y0, x1, y1 = room_box(r)
            rooms.append({"id": r.id, "type": r.type, "area_m2": round(r.area, 1), "size_m": [round(x1 - x0, 1), round(y1 - y0, 1)],
                          "already_has": sorted({i.role for i in plan.items if i.room == r.id})})
        return {"brief": brief, "styles": {k: v.tags for k, v in STYLES.items()}, "decor_roles": DECOR_ROLES,
                "max_decor_per_room": MAX_DECOR_PER_ROOM, "rooms": rooms}

    def _validate(self, data: dict, plan: Plan) -> dict:
        if not isinstance(data, dict):
            raise ValueError("réponse non objet")
        out: dict = {}
        if data.get("style") in STYLES:
            out["style"] = data["style"]
        rooms = {}
        known = {r.id for r in plan.rooms}
        for room_id, roles in (data.get("rooms") or {}).items():
            if room_id in known and isinstance(roles, list):
                rooms[room_id] = [r for r in roles if r in DECOR_ROLES][:MAX_DECOR_PER_ROOM]
        out["rooms"] = rooms
        if not out.get("style") and not rooms:
            raise ValueError("réponse sans style ni décor")
        return out

    def _decor(self, plan: Plan, proposed: dict[str, list[str]]) -> dict[str, list[str]]:
        rng = random.Random(f"decor:{plan.seed}")
        out: dict[str, list[str]] = {}
        for room in plan.rooms:
            if room.id in proposed:
                out[room.id] = proposed[room.id]
                continue
            pool = list(DEFAULT_DECOR.get(room.type, []))
            keep = min(len(pool), max(1, int(room.area // 8)), MAX_DECOR_PER_ROOM) if pool else 0
            out[room.id] = rng.sample(pool, keep) if keep else []
        return out

    # -- pose du décor -----------------------------------------------------------------------
    def _place_decor(self, plan: Plan, decor: dict[str, list[str]]) -> dict[str, list[str]]:
        occ = occupancy_of(plan, self.catalog)
        done: dict[str, list[str]] = {}
        for room in plan.rooms:
            placed = []
            for role in decor.get(room.id, []):
                if self._decorate(plan, room, role, occ):
                    placed.append(role)
            done[room.id] = placed
        return done

    def _asset(self, plan: Plan, room: Room, role: str) -> Asset | None:
        return self.catalog.pick_fit(role, None, room=room.type, style=plan.style.tags, seed=f"{plan.seed}:{room.id}:{role}",
                                     prefer_pack=plan.style.prefer_pack)

    def _decorate(self, plan: Plan, room: Room, role: str, occ: Occupancy) -> bool:
        asset = self._asset(plan, room, role)
        if asset is None:
            return False
        items = [i for i in plan.items if i.room == room.id]
        w, d = asset.footprint
        box = room_box(room)
        if role == "picture":
            base = next((i for i in items if i.role in ("sofa", "sofa.corner", "sofa.long", "bed.double", "bed.single")), None)
            if base is None:
                return False
            bw, bd = base.size or (1.0, 1.0)
            x, y = in_front(base.x, base.y, base.rot, -(bd / 2 + 0.03))
            plan.place("picture", x, y, base.rot, room=room.id, asset=asset.id, size=(w, max(d, 0.04)), elevation=1.45)
            return True
        if role == "rug":
            if any(i.role == "rug" for i in items):
                return False
            bed = next((i for i in items if i.role.startswith("bed.")), None)
            if bed is None:
                return False
            bw, bl = bed.size or (1.6, 2.0)
            x, y = in_front(bed.x, bed.y, bed.rot, 0.35)
            plan.place("rug", x, y, bed.rot, room=room.id, asset=asset.id, size=(bw + 1.0, bl * 0.8), elevation=0.0)
            return True
        if role in ("lamp.table", "books", "plant.small"):
            surface = next((i for i in items if i.role in ("nightstand", "desk", "table.coffee", "tv.console", "dresser")), None)
            if surface is None:
                return False
            sw, sd = surface.size or (0.5, 0.4)
            top = self._surface_height(plan, surface)
            plan.place(role, surface.x, surface.y, surface.rot, room=room.id, asset=asset.id, size=(min(w, sw), min(d, sd)),
                       elevation=top)
            return True
        # plantes et lampadaires au sol : un coin libre de la pièce
        for cx, cy in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])):
            x = cx + (w / 2 + 0.05) * (1 if cx == box[0] else -1)
            y = cy + (d / 2 + 0.05) * (1 if cy == box[1] else -1)
            rect = rect_of(x, y, w, d, 0.0)
            if occ.free(rect, box):
                plan.place(role, x, y, 0.0, room=room.id, asset=asset.id, size=(w, d))
                occ.add(rect)
                return True
        return False

    def _surface_height(self, plan: Plan, item: Item) -> float:
        asset = self.catalog.get(item.asset) if item.asset else self.catalog.pick_fit(
            item.role, item.size, style=plan.style.tags, seed=f"{plan.seed}:{item.id}", prefer_pack=plan.style.prefer_pack)
        return round(asset.height, 2) if asset else 0.55


SYSTEM_PROMPT = (
    "You are an interior design assistant. You receive a house plan summary as JSON and answer with ONE JSON object: "
    '{"style": <one of the given style names>, "rooms": {<room id>: [<decor roles>]}}. '
    "Use only the given style names and decor roles, at most max_decor_per_room roles per room, never invent room ids. "
    "Pick decor that suits each room (a plant and a floor lamp in a living room, a table lamp and a picture in a bedroom). "
    "Styles moderne, scandinave, chaleureux and classique all use realistic textured models. Style 'premium' prefers the most "
    "detailed scans and makes the file about 10 MB: pick it only if the brief explicitly asks for a luxurious or high-quality look. "
    "Styles 'lowpoly' and 'lowpoly-chaleureux' are cartoon-like and light: pick one only if the brief asks for a simple or "
    "light model. "
    "Do not place anything or give coordinates: a solver does that. No commentary."
)
