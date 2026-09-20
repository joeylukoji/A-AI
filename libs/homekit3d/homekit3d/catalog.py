"""Catalogue des composants : recherche par rôle, pièce et style. Python pur (pas de Blender)."""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = PACKAGE_DIR / "catalog" / "manifest.json"


@dataclass(frozen=True)
class Asset:
    """Un modèle 3D du catalogue. Les dimensions sont en mètres, axes glTF (x = largeur, y = hauteur, z = profondeur)."""

    id: str
    pack: str
    name: str
    path: Path
    role: str
    rooms: tuple[str, ...]
    tags: tuple[str, ...]
    size: tuple[float, float, float]          # dimensions natives du fichier
    scale: float                              # facteur qui ramène le modèle à sa taille réelle
    fit_size: tuple[float, float, float]      # dimensions réelles (natives x scale)
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    tris: int
    license: str
    author: str
    unused: bool = False

    @property
    def footprint(self) -> tuple[float, float]:
        """Largeur (x) et profondeur (z) réelles."""
        return self.fit_size[0], self.fit_size[2]

    @property
    def height(self) -> float:
        return self.fit_size[1]

    @property
    def center_offset(self) -> tuple[float, float, float]:
        """Décalage (natif) de l'origine du fichier au centre de son emprise, sol à y = 0."""
        return ((self.bbox_min[0] + self.bbox_max[0]) / 2, self.bbox_min[1], (self.bbox_min[2] + self.bbox_max[2]) / 2)


@dataclass
class Catalog:
    assets: dict[str, Asset] = field(default_factory=dict)
    packs: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, manifest: Path | str | None = None) -> "Catalog":
        path = Path(manifest) if manifest else DEFAULT_MANIFEST
        data = json.loads(path.read_text(encoding="utf-8"))
        root = path.parent.parent
        cat = cls(packs=data.get("packs", {}))
        for it in data["items"]:
            pack = data["packs"].get(it["pack"], {})
            cat.assets[it["id"]] = Asset(
                id=it["id"], pack=it["pack"], name=it["name"], path=root / it["file"], role=it["role"],
                rooms=tuple(it["rooms"]), tags=tuple(it["tags"]), size=tuple(it["size"]), scale=float(it["scale"]),
                fit_size=tuple(it["fit_size"]), bbox_min=tuple(it["min"]), bbox_max=tuple(it["max"]),
                tris=int(it["tris"]), license=pack.get("license", "CC0-1.0"), author=pack.get("author", ""),
                unused=bool(it["unused"]),
            )
        return cat

    # -- consultation ---------------------------------------------------------------------
    def get(self, asset_id: str) -> Asset:
        return self.assets[asset_id]

    def roles(self) -> list[str]:
        return sorted({a.role for a in self.assets.values() if not a.unused})

    def find(self, role: str, *, room: str | None = None, tags: Iterable[str] = (), exclude: Iterable[str] = (),
             max_footprint: tuple[float, float] | None = None) -> list[Asset]:
        """Les modèles utilisables d'un rôle, filtrés. Tri stable par identifiant (déterminisme)."""
        want, ban = set(tags), set(exclude)
        out = []
        for a in self.assets.values():
            if a.unused or a.role != role or a.id in ban:
                continue
            if room and a.rooms and room not in a.rooms:
                continue
            if want and not want <= set(a.tags):
                continue
            if max_footprint and (a.footprint[0] > max_footprint[0] + 1e-6 or a.footprint[1] > max_footprint[1] + 1e-6):
                continue
            out.append(a)
        return sorted(out, key=lambda a: a.id)

    def pick(self, role: str, *, room: str | None = None, style: Iterable[str] = (), seed: int | str = 0,
             prefer_pack: str | None = None, tags: Iterable[str] = (), max_footprint: tuple[float, float] | None = None
             ) -> Asset | None:
        """Un modèle du rôle : d'abord ceux du style demandé, puis n'importe lequel ; tirage déterministe par graine."""
        pool = self.find(role, room=room, tags=tags, max_footprint=max_footprint)
        if not pool and room:
            pool = self.find(role, tags=tags, max_footprint=max_footprint)      # à défaut, hors pièce d'usage
        if not pool:
            return None
        style = set(style)
        if prefer_pack:
            in_pack = [a for a in pool if a.pack == prefer_pack]
            pool = in_pack or pool
        if style:
            matching = [a for a in pool if style & set(a.tags)]
            pool = matching or pool
        return random.Random(f"{seed}:{role}:{room or ''}").choice(pool)

    def pick_fit(self, role: str, size: tuple[float, float] | None, *, room: str | None = None,
                 style: Iterable[str] = (), seed: int | str = 0, prefer_pack: str | None = None,
                 top: int = 3) -> Asset | None:
        """Comme `pick`, mais parmi les modèles dont l'emprise réelle ressemble le plus à `size` (largeur, profondeur)."""
        pool = self.find(role, room=room) or self.find(role)
        if not pool:
            return None
        style = set(style)
        if prefer_pack:                                   # le style d'abord, la ressemblance de taille ensuite : un style
            pool = [a for a in pool if a.pack == prefer_pack] or pool       # réaliste ne doit pas retomber sur un jouet
        if style:                                         # parce que celui-ci a une emprise un peu plus proche
            pool = [a for a in pool if style & set(a.tags)] or pool
        if size and size[0] > 0 and size[1] > 0:
            def error(a: Asset) -> float:
                w, d = a.footprint
                return abs(math.log(max(w, 1e-3) / size[0])) + abs(math.log(max(d, 1e-3) / size[1]))
            pool = sorted(pool, key=lambda a: (error(a), a.id))[:max(1, top * 2)]
        return random.Random(f"{seed}:{role}:{room or ''}").choice(pool[:max(1, top)])

    def summary(self, rooms: Iterable[str] | None = None) -> dict[str, list[str]]:
        """Vue compacte pour un LLM : rôle -> identifiants courts (pack/nom) utilisables."""
        wanted = set(rooms) if rooms else None
        out: dict[str, list[str]] = {}
        for a in self.assets.values():
            if a.unused or (wanted and a.rooms and not (wanted & set(a.rooms))):
                continue
            out.setdefault(a.role, []).append(a.id)
        return {role: sorted(ids) for role, ids in sorted(out.items())}

    def attributions(self, used: Iterable[str] | None = None) -> list[dict]:
        """Crédits des modèles réellement utilisés (ou de tout le catalogue)."""
        ids = set(used) if used is not None else None
        seen: dict[str, dict] = {}
        for a in self.assets.values():
            if ids is not None and a.id not in ids:
                continue
            seen.setdefault(a.pack, {"pack": a.pack, "author": a.author, "license": a.license,
                                     "source": self.packs.get(a.pack, {}).get("source", "")})
        return sorted(seen.values(), key=lambda d: d["pack"])
