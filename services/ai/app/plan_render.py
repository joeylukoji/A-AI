"""Render a PlanDocument to clean raster + room mask, and degrade for refine pairs."""
from __future__ import annotations

import random
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOM_GRAY: dict[str, int] = {
    "living": 70,
    "dining": 90,
    "kitchen": 110,
    "bedroom": 140,
    "bathroom": 170,
    "hallway": 190,
    "office": 210,
    "garage": 230,
    "storage": 200,
    "other": 120,
}


def _bounds(plan: dict[str, Any]) -> tuple[float, float]:
    b = (plan.get("floor") or {}).get("bounds") or {}
    return float(b.get("width") or 12), float(b.get("depth") or 10)


def render_clean_and_mask(plan: dict[str, Any], size: int = 128) -> tuple[Image.Image, Image.Image]:
    width_m, depth_m = _bounds(plan)
    sx = size / max(width_m, 1e-6)
    sy = size / max(depth_m, 1e-6)
    clean = Image.new("L", (size, size), 245)
    mask = Image.new("L", (size, size), 0)
    dc = ImageDraw.Draw(clean)
    dm = ImageDraw.Draw(mask)

    for room in plan.get("rooms") or []:
        pts = _scaled_points(room.get("polygon"), sx, sy)
        if len(pts) < 3:
            continue
        gray = ROOM_GRAY.get(str(room.get("type") or "other"), 120)
        dm.polygon(pts, fill=gray)
        dc.polygon(pts, fill=230, outline=40)

    for wall in plan.get("walls") or []:
        if not isinstance(wall, dict):
            continue
        ends = _scaled_points([wall.get("a"), wall.get("b")], sx, sy)
        if len(ends) != 2:
            continue  # mur malformé : ignoré plutôt que KeyError
        thick = max(1, int(float(wall.get("thickness_m") or 0.2) * sx * 1.2))
        dc.line(ends, fill=20, width=thick)

    return clean, mask


def _scaled_points(poly: Any, sx: float, sy: float) -> list[tuple[float, float]]:
    """Sommets convertis en pixels ; les points malformés sont écartés."""
    if not isinstance(poly, list):
        return []
    out: list[tuple[float, float]] = []
    for p in poly:
        if not isinstance(p, dict):
            continue
        try:
            out.append((float(p["x"]) * sx, float(p["y"]) * sy))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def degrade(clean: Image.Image, rng: random.Random | None = None) -> Image.Image:
    rng = rng or random.Random()
    # Le bruit poivre-et-sel ci-dessous écrit des entiers : sur une image RGB
    # `px[x, y]` renvoie un tuple et `int(...)` lèverait TypeError.
    img = clean.copy() if clean.mode == "L" else clean.convert("L")
    if rng.random() < 0.8:
        img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.4, 1.6)))
    factor = rng.choice([0.35, 0.45, 0.55])
    small = img.resize(
        (max(8, int(img.width * factor)), max(8, int(img.height * factor))),
        Image.Resampling.BILINEAR,
    )
    img = small.resize(clean.size, Image.Resampling.BILINEAR)
    px = img.load()
    if px is not None:  # `load()` peut échouer sur une image fermée
        for _ in range(rng.randint(80, 220)):
            x = rng.randint(0, img.width - 1)
            y = rng.randint(0, img.height - 1)
            n = rng.randint(-40, 40)
            value = px[x, y]
            if isinstance(value, tuple):
                # Impossible ici (l'image est forcée en mode "L" plus haut),
                # mais le typage de Pillow ne peut pas le prouver.
                continue
            px[x, y] = max(0, min(255, int(value) + n))
    if rng.random() < 0.5:
        img = ImageOps.autocontrast(img)
    return img


def layout_to_plan(layout: dict[str, Any] | None) -> dict[str, Any]:
    layout = layout or {}
    return {
        "version": "1.0",
        "units": "m",
        "floor": {
            "level": 0,
            "height_m": float(layout.get("height_m") or 2.7),
            "bounds": {
                "width": float(layout.get("width") or 12),
                "depth": float(layout.get("depth") or 10),
            },
        },
        "walls": layout.get("walls") or [],
        "rooms": layout.get("rooms") or [],
        "openings": layout.get("openings") or [],
    }
