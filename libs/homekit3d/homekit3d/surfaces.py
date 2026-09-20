"""Matériaux texturés de la coque (murs, sols) : quelle texture pour quelle surface, selon le style. Python pur.

Les textures sont des scans PBR de Poly Haven (CC0), dans `assets/textures/<id>_diff.jpg` (couleur) et `<id>_nor.jpg`
(relief). Une texture « teintée » ne sert qu'à donner du grain : sa couleur est remplacée par celle de la palette du
style, pour que « moderne » et « chaleureux » gardent des murs et des sols de couleurs différentes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .plan import Style

TEXTURE_DIR = Path(__file__).resolve().parent / "assets" / "textures"

# Taille réelle, en mètres, du carré couvert par la texture (champ `size_mm` de Poly Haven).
TILE_M = {"beige_wall_001": 3.0, "white_stucco": 2.0, "oak_wood_planks": 1.2, "old_wood_floor": 3.0,
          "interior_tiles": 1.9, "garage_floor": 1.9}

WOOD_ROOMS = {"living", "dining", "bedroom", "office", "hallway", "storage"}
TILED_ROOMS = {"kitchen", "bathroom", "wc", "laundry"}


@dataclass(frozen=True)
class Surface:
    texture: str
    tint: tuple[float, float, float] | None      # couleur sRGB qui remplace celle de la texture (None : telle quelle)
    roughness: float

    @property
    def tile(self) -> float:
        return TILE_M[self.texture]

    def file(self, kind: str) -> Path:
        return TEXTURE_DIR / f"{self.texture}_{'diff' if kind == 'color' else 'nor'}.jpg"


def luminance(rgb: tuple[float, float, float]) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def surface_for(material: str, style: Style) -> Surface | None:
    """La surface texturée d'un matériau de la coque, ou None s'il reste uni (cadres, vitres, dalle…)."""
    if material == "wall_int":
        return Surface("beige_wall_001", style.wall_interior, 0.9)
    if material == "wall_ext":
        return Surface("white_stucco", style.wall_exterior, 0.95)
    if not material.startswith("floor:"):
        return None
    kind = material.split(":", 1)[1]
    palette = style.floors.get(kind, (0.7, 0.68, 0.64))
    if kind in WOOD_ROOMS:
        return Surface("oak_wood_planks" if luminance(palette) > 0.45 else "old_wood_floor", None, 0.55)
    if kind in TILED_ROOMS:
        return Surface("interior_tiles", palette, 0.35)
    return Surface("garage_floor", None, 0.8)


def textures_available(surface: Surface) -> bool:
    return surface.file("color").exists() and surface.file("normal").exists()
