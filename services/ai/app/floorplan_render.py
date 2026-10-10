"""Rendu local du plan : textures, mobilier, traits et annotations Pillow."""

from __future__ import annotations

import base64
import io
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.plan_drawing import draw_structure
from app.plan_geometry import opening_segment
from app.room_program import _label

_Font = ImageFont.ImageFont | ImageFont.FreeTypeFont


_ROOM_FILL_SOFT: dict[str, tuple[int, int, int]] = {
    "living": (196, 148, 72),
    "kitchen": (248, 248, 246),
    "dining": (210, 170, 110),
    "bedroom": (232, 214, 176),
    "bathroom": (210, 214, 216),
    "wc": (210, 214, 216),
    "hallway": (220, 196, 150),
    "garage": (210, 210, 208),
    "office": (232, 214, 176),
    "storage": (210, 210, 208),
    "laundry": (210, 214, 216),
}
_FLOOR_WOOD = (232, 214, 176)
_FLOOR_WOOD_LINE = (210, 188, 148)
_FLOOR_HONEY = (196, 148, 72)
_FLOOR_HONEY_LINE = (176, 128, 58)
_FLOOR_TILE = (248, 248, 246)
_FLOOR_TILE_LINE = (214, 214, 212)
_FLOOR_BATH = (210, 214, 216)
_FLOOR_BATH_LINE = (186, 192, 196)
_FLOOR_HARD = (210, 210, 208)
_RUG = (90, 78, 68)
_PLANT = (86, 130, 64)
_PLANT_IN = (58, 96, 42)
_WALL = (138, 138, 136)
_WALL_DARK = (88, 88, 86)
_WALL_LIGHT = (168, 168, 166)
_FURN = (72, 68, 64)
_FURN_FILL = (248, 248, 246)
_FURN_SOFT = (236, 236, 234)
_SHADOW = (30, 28, 24, 42)
_TEXT = (36, 36, 34)
_TEXT_SOFT = (92, 92, 88)
_PAGE_BG = (232, 232, 230)
_GRASS = (118, 154, 74)
_GRASS_DARK = (96, 132, 58)
_PORCH = (176, 138, 86)
_PORCH_LINE = (148, 112, 64)
_DOOR = (168, 122, 72)
_SS = 3  # supersampling : dessin à 3x puis réduction LANCZOS -> traits et texte nets


def _rrect(d: ImageDraw.ImageDraw, box: Any, r: float, **kw: Any) -> None:
    try:
        d.rounded_rectangle(box, radius=max(1, r), **kw)
    except (AttributeError, TypeError):
        d.rectangle(box, **{k: v for k, v in kw.items() if k != "radius"})


def _wood_planks(
    d: ImageDraw.ImageDraw,
    P: Any,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    tones: list[tuple[int, int, int]],
    sc: float,
    ph: float = 0.135,
    pw: float = 0.88,
) -> None:
    """Parquet à lames décalées, couleur un peu variable."""
    tw = max(1, int(0.008 * sc))
    row, yy = 0, y0
    while yy < y1 - 1e-6:
        yb = min(y1, yy + ph)
        off = (row % 2) * (pw * 0.38)
        xx, col = x0 - off, 0
        while xx < x1:
            xb = min(x1, xx + pw)
            xa = max(x0, xx)
            if xb > xa + 0.02:
                tone = tones[(row * 3 + col) % len(tones)]
                d.rectangle([P(xa, yy), P(xb, yb)], fill=tone)
                seam = (
                    max(40, tone[0] - 28),
                    max(28, tone[1] - 28),
                    max(16, tone[2] - 18),
                )
                d.line([P(xa, yy), P(xb, yy)], fill=seam, width=tw)
            xx += pw
            col += 1
        yy += ph
        row += 1


def _floor_texture(
    d: ImageDraw.ImageDraw,
    typ: str,
    bm: tuple[float, float, float, float],
    P: Any,
    sc: float,
) -> None:
    """Sol de la pièce : parquet à lames, carrelage damier, dalle."""
    x0, y0, x1, y1 = bm
    tw = max(1, int(0.01 * sc))
    if typ in ("living", "dining", "hallway"):
        d.rectangle([P(x0, y0), P(x1, y1)], fill=_FLOOR_HONEY)
        _wood_planks(
            d,
            P,
            x0,
            y0,
            x1,
            y1,
            [
                (196, 148, 72),
                (180, 130, 56),
                (208, 164, 86),
                (168, 120, 48),
                (200, 154, 80),
            ],
            sc,
        )
    elif typ in ("bedroom", "office"):
        d.rectangle([P(x0, y0), P(x1, y1)], fill=_FLOOR_WOOD)
        _wood_planks(
            d,
            P,
            x0,
            y0,
            x1,
            y1,
            [
                (232, 212, 176),
                (222, 202, 164),
                (240, 224, 192),
                (212, 190, 152),
                (234, 216, 180),
            ],
            sc,
        )
    elif typ == "kitchen":
        d.rectangle([P(x0, y0), P(x1, y1)], fill=(216, 212, 204))
        tile, g = 0.38, 0.018
        xx, col = x0, 0
        while xx < x1:
            yy, row = y0, 0
            while yy < y1:
                xa, ya = xx + g, yy + g
                xb, yb = min(x1, xx + tile - g), min(y1, yy + tile - g)
                if xb > xa and yb > ya:
                    fill = (246, 244, 238) if (row + col) % 2 == 0 else (232, 228, 220)
                    d.rectangle([P(xa, ya), P(xb, yb)], fill=fill)
                yy += tile
                row += 1
            xx += tile
            col += 1
    elif typ in ("bathroom", "wc", "laundry"):
        d.rectangle([P(x0, y0), P(x1, y1)], fill=(200, 206, 210))
        tile, g = 0.22, 0.012
        xx, col = x0, 0
        while xx < x1:
            yy, row = y0, 0
            while yy < y1:
                xa, ya = xx + g, yy + g
                xb, yb = min(x1, xx + tile - g), min(y1, yy + tile - g)
                if xb > xa and yb > ya:
                    fill = (228, 234, 238) if (row + col) % 2 == 0 else (208, 216, 220)
                    d.rectangle([P(xa, ya), P(xb, yb)], fill=fill)
                yy += tile
                row += 1
            xx += tile
            col += 1
    elif typ in ("garage", "storage"):
        d.rectangle([P(x0, y0), P(x1, y1)], fill=_FLOOR_HARD)
        step = 1.4
        xx = x0 + step
        while xx < x1:
            d.line([P(xx, y0), P(xx, y1)], fill=(160, 160, 156), width=tw)
            xx += step
        yy = y0 + step
        while yy < y1:
            d.line([P(x0, yy), P(x1, yy)], fill=(160, 160, 156), width=tw)
            yy += step
    else:
        d.rectangle([P(x0, y0), P(x1, y1)], fill=_ROOM_FILL_SOFT.get(typ, (238, 239, 241)))


def _xf(P: Any, px: float, py: float, rot: float) -> Any:
    import math

    rad = math.radians(rot)
    c, s = math.cos(rad), math.sin(rad)

    def T(lx: float, ly: float) -> tuple[float, float]:
        return P(px + lx * c - ly * s, py + lx * s + ly * c)

    return T


def _poly(
    d: ImageDraw.ImageDraw,
    pts: list[tuple[float, float]],
    fill: Any,
    outline: Any,
    lw: int,
) -> None:
    d.polygon(pts, fill=fill, outline=outline)
    if lw > 1:
        d.line(pts + [pts[0]], fill=outline, width=lw)


def _rr_local(
    d: ImageDraw.ImageDraw,
    T: Any,
    a: float,
    b: float,
    c: float,
    e: float,
    fill: Any,
    outline: Any,
    lw: int,
) -> None:
    _poly(d, [T(a, b), T(c, b), T(c, e), T(a, e)], fill, outline, lw)


def _stamp(
    img: Image.Image,
    P: Any,
    px: float,
    py: float,
    rot: float,
    wm: float,
    dm: float,
    sc: float,
    paint: Any,
) -> None:
    """Dessine un meuble en local (non tourné) puis le colle avec rotation."""
    pad = max(10, int(0.28 * sc))
    W = max(16, int(wm * sc) + pad * 2)
    H = max(16, int(dm * sc) + pad * 2)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer, "RGBA")
    ox, oy = W / 2, H / 2
    lw = max(1, int(0.016 * sc))

    def L(lx: float, ly: float) -> tuple[float, float]:
        return ox + lx * sc, oy + ly * sc

    def box(x0: float, y0: float, x1: float, y1: float) -> list[float]:
        a, b = L(x0, y0), L(x1, y1)
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]

    def rr(
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        rad: float,
        fill: Any,
        outline: Any = None,
    ) -> None:
        _rrect(
            dr,
            box(x0, y0, x1, y1),
            max(1, rad * sc),
            fill=fill,
            outline=outline,
            width=lw,
        )

    def ell(x: float, y: float, rx: float, ry: float, fill: Any, outline: Any = None) -> None:
        dr.ellipse(box(x - rx, y - ry, x + rx, y + ry), fill=fill, outline=outline, width=lw)

    ell(0.05, 0.06, wm * 0.5, dm * 0.46, (24, 18, 12, 55))
    paint(dr, L, rr, ell, lw)
    if abs(rot) > 0.4:
        layer = layer.rotate(-rot, expand=True, resample=Image.Resampling.BICUBIC)
    wx, wy = P(px, py)
    img.paste(
        layer,
        (int(round(wx - layer.width / 2)), int(round(wy - layer.height / 2))),
        layer,
    )


def _draw_catalog_item(img: Image.Image, d: ImageDraw.ImageDraw, item: dict[str, Any], P: Any, sc: float) -> None:
    """Glyphe 2D réaliste (vue du dessus) pour une instance catalogue."""
    _ = d
    cid = str(item.get("catalog_id") or "")
    pos = item.get("position") or {}
    try:
        px, py = float(pos["x"]), float(pos["y"])
        w = float((item.get("size_m") or {}).get("w") or 0.5)
        dd = float((item.get("size_m") or {}).get("d") or 0.5)
        rot = float(item.get("rotation_deg") or 0)
    except (TypeError, ValueError, KeyError):
        return
    hx, hy = w / 2, dd / 2

    def bed(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        dark = cid.endswith("double") and w >= 1.4
        frame = (61, 46, 36) if dark else (196, 168, 130)
        linen = (62, 66, 72) if dark else (244, 239, 230)
        rr(-hx, -hy, hx, hy, 0.08, frame, (42, 30, 24) if dark else (138, 106, 72))
        rr(
            -hx + 0.04,
            -hy + 0.16,
            hx - 0.04,
            hy - 0.06,
            0.07,
            linen,
            (42, 46, 50) if dark else (208, 198, 180),
        )
        rr(
            -hx,
            -hy,
            hx,
            -hy + 0.16,
            0.03,
            (36, 28, 24) if dark else (184, 154, 120),
            (42, 30, 24),
        )
        pw, ph = w * 0.26, 0.26
        for sx in (-w * 0.22, w * 0.22):
            ell(sx, -hy + 0.38, pw, ph, (251, 248, 242), (212, 207, 196))
            ell(sx - 0.05, -hy + 0.34, pw * 0.4, ph * 0.35, (255, 255, 255, 90))
        rr(
            -hx + 0.08,
            hy - 0.46,
            hx - 0.08,
            hy - 0.14,
            0.05,
            (74, 68, 64) if dark else (228, 212, 184),
            (46, 42, 40) if dark else (196, 176, 144),
        )

    def sofa(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        fabric, dark, seat = (90, 94, 102), (58, 62, 68), (106, 110, 118)
        # size_m already includes the chaise: draw it inside that footprint.
        body_end = hy - min(0.72, dd * 0.45) if cid == "sofa.lshape" else hy
        rr(-hx, -hy, hx, body_end, 0.12, fabric, (42, 46, 52))
        rr(-hx, -hy, hx, -hy + 0.2, 0.07, dark, (36, 40, 44))
        rr(-hx, -hy, -hx + 0.18, body_end, 0.07, dark, (36, 40, 44))
        rr(hx - 0.18, -hy, hx, hy, 0.07, dark, (36, 40, 44))
        seats = 3 if cid == "sofa.lshape" else 2
        inner = w - 0.4
        for i in range(seats):
            x0 = -hx + 0.22 + i * (inner / seats)
            rr(
                x0,
                -hy + 0.24,
                x0 + inner / seats - 0.04,
                body_end - 0.08,
                0.08,
                seat,
                (62, 66, 72),
            )
        if cid == "sofa.lshape":
            rr(hx - 1.02, -hy, hx, hy, 0.12, fabric, (42, 46, 52))
            rr(
                hx - 0.92,
                body_end - 0.06,
                hx - 0.22,
                hy - 0.08,
                0.08,
                seat,
                (62, 66, 72),
            )

    def armchair(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.14, (110, 74, 48), (58, 36, 20))
        rr(-hx, -hy, hx, -hy + 0.16, 0.06, (84, 54, 28), (58, 36, 20))
        rr(-hx, -hy, -hx + 0.12, hy, 0.05, (84, 54, 28), (58, 36, 20))
        rr(hx - 0.12, -hy, hx, hy, 0.05, (84, 54, 28), (58, 36, 20))
        ell(0, 0.06, w * 0.3, dd * 0.24, (138, 96, 64), (74, 48, 28))

    def table_dining(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        ell(0, 0, hx, hy, (138, 88, 40), (90, 52, 20))
        ell(0, 0, hx - 0.06, hy - 0.06, (196, 138, 72), (138, 90, 40))
        for k in (0.22, 0.42, 0.62):
            ell(0, 0, hx * k, hy * k, None, (90, 50, 18, 70))
        ell(-w * 0.14, -dd * 0.12, w * 0.18, dd * 0.08, (255, 230, 180, 50))

    def chair(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        ell(0, 0.06, w * 0.44, dd * 0.36, (236, 196, 74), (176, 138, 24))
        rr(-w * 0.36, -hy, w * 0.36, -hy + 0.11, 0.04, (212, 168, 46), (138, 106, 20))
        ell(-0.05, 0.0, w * 0.16, dd * 0.1, (255, 255, 220, 90))

    def coffee(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.08, (232, 228, 218), (184, 180, 170))
        rr(
            -hx + 0.05,
            -hy + 0.05,
            hx - 0.05,
            hy - 0.05,
            0.05,
            (250, 248, 244),
            (212, 207, 198),
        )
        ell(-w * 0.18, 0, 0.06, 0.06, (180, 80, 50, 90))
        ell(w * 0.12, 0.04, 0.045, 0.045, (40, 90, 140, 70))

    def counter(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.03, (236, 232, 224), (184, 180, 172))
        n = max(2, int(round(w / 0.55)))
        for i in range(1, n):
            x = -hx + (w * i) / n
            dr.line([L(x, -hy + 0.1), L(x, hy - 0.04)], fill=(160, 156, 148, 140), width=lw)
        # Petit évier encastré (carré), pas une cuve / baignoire.
        sw, sd = 0.32, min(0.28, max(0.18, dd * 0.42))
        sx = -w * 0.12
        rr(
            sx - sw / 2,
            -sd / 2,
            sx + sw / 2,
            sd / 2,
            0.03,
            (214, 216, 218),
            (120, 124, 128),
        )
        rr(
            sx - sw / 2 + 0.04,
            -sd / 2 + 0.04,
            sx + sw / 2 - 0.04,
            sd / 2 - 0.04,
            0.02,
            (198, 202, 206),
            (140, 144, 148),
        )
        ell(sx, -hy + 0.07, 0.028, 0.028, (138, 144, 150), (74, 80, 86))

    def stove(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.04, (42, 42, 44), (16, 16, 18))
        for ix, iy, r in (
            (-0.15, -0.13, 0.11),
            (0.15, -0.13, 0.09),
            (-0.15, 0.13, 0.09),
            (0.15, 0.13, 0.11),
        ):
            ell(ix, iy, r, r, (22, 22, 24), (106, 106, 112))
            ell(ix, iy, r * 0.35, r * 0.35, (58, 58, 62), (138, 138, 144))

    def night(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.04, (122, 82, 48), (62, 42, 24))
        ell(0, -0.02, 0.075, 0.075, (240, 220, 156), (196, 160, 96))
        ell(0, -0.02, 0.035, 0.035, (255, 248, 210, 180))

    def wardrobe(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.03, (110, 78, 50), (58, 40, 24))
        dr.line([L(0, -hy + 0.04), L(0, hy - 0.04)], fill=(58, 40, 24), width=lw)
        ell(-0.09, 0, 0.028, 0.028, (208, 204, 196), (138, 134, 128))
        ell(0.09, 0, 0.028, 0.028, (208, 204, 196), (138, 134, 128))

    def desk(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.04, (62, 62, 66), (28, 28, 32))
        rr(
            w * 0.08,
            -dd * 0.16,
            w * 0.08 + 0.32,
            -dd * 0.16 + 0.22,
            0.02,
            (22, 22, 26),
            (8, 8, 12),
        )
        rr(
            w * 0.12,
            -dd * 0.12,
            w * 0.12 + 0.24,
            -dd * 0.12 + 0.14,
            0.01,
            (30, 58, 82),
            (12, 28, 40),
        )

    def fireplace(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.04, (74, 70, 68), (28, 26, 24))
        rr(-hx + 0.08, -hy + 0.1, hx - 0.08, hy - 0.1, 0.03, (42, 34, 32), (12, 8, 8))
        ell(0, hy - 0.22, 0.14, 0.09, (196, 74, 34))
        ell(0, hy - 0.26, 0.07, 0.06, (240, 192, 64))

    def bathtub(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rad = min(w, dd) * 0.32
        rr(-hx, -hy, hx, hy, rad, (246, 246, 244), (176, 176, 180))
        rr(
            -hx + 0.1,
            -hy + 0.1,
            hx - 0.1,
            hy - 0.1,
            rad * 0.8,
            (200, 221, 230),
            (138, 168, 180),
        )
        ell(hx - 0.22, 0, 0.04, 0.04, (138, 142, 146), (90, 94, 98))

    def toilet(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, -hy + 0.2, 0.03, (242, 242, 240), (184, 184, 188))
        ell(0, 0.1, w * 0.44, dd * 0.38, (248, 248, 246), (184, 184, 188))
        ell(0, 0.12, w * 0.24, dd * 0.2, (220, 230, 234), (160, 168, 172))

    def sink(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        ell(0, 0.05, w * 0.44, dd * 0.4, (246, 246, 244), (184, 184, 188))
        ell(0, 0.07, w * 0.28, dd * 0.24, (208, 224, 230), (144, 164, 172))
        rr(-0.04, -hy, 0.04, -hy + 0.14, 0.02, (200, 204, 208), (138, 142, 146))

    def car(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx + 0.08, -hy, hx - 0.12, hy, 0.28, (236, 236, 234), (154, 154, 160))
        rr(
            -w * 0.16,
            -hy + 0.14,
            -w * 0.16 + w * 0.4,
            hy - 0.14,
            0.14,
            (122, 160, 180),
            (74, 112, 132),
        )
        for wx_, wy_ in (
            (-hx + 0.38, -hy - 0.04),
            (hx - 0.72, -hy - 0.04),
            (-hx + 0.38, hy - 0.08),
            (hx - 0.72, hy - 0.08),
        ):
            rr(wx_, wy_, wx_ + 0.38, wy_ + 0.12, 0.04, (28, 28, 30), (8, 8, 10))
        ell(-hx + 0.1, -dd * 0.22, 0.07, 0.05, (244, 232, 144))
        ell(-hx + 0.1, dd * 0.22, 0.07, 0.05, (244, 232, 144))
        ell(hx - 0.12, -dd * 0.2, 0.05, 0.04, (224, 112, 96))
        ell(hx - 0.12, dd * 0.2, 0.05, 0.04, (224, 112, 96))

    def rug(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.06, (196, 90, 58), (138, 56, 32))
        rr(
            -hx + 0.08,
            -hy + 0.08,
            hx - 0.08,
            hy - 0.08,
            0.04,
            (212, 120, 76),
            (160, 72, 40),
        )
        rr(-hx + 0.16, -hy + 0.16, hx - 0.16, hy - 0.16, 0.03, (255, 220, 180, 40))

    def plant(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        ell(0, 0.08, w * 0.28, dd * 0.22, (138, 90, 50), (90, 56, 24))
        for x, y, r, col in (
            (-0.08, -0.1, 0.16, (74, 138, 44)),
            (0.1, -0.12, 0.18, (46, 106, 28)),
            (0.0, -0.18, 0.14, (90, 154, 52)),
            (-0.12, 0.0, 0.12, (46, 106, 28)),
            (0.12, 0.02, 0.13, (74, 138, 44)),
        ):
            ell(x, y, r, r * 0.85, col, (30, 74, 16))

    def fridge(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.04, (232, 236, 238), (168, 176, 180))
        dr.line([L(-hx + 0.04, 0.02), L(hx - 0.04, 0.02)], fill=(176, 184, 188), width=lw)
        rr(
            hx - 0.1,
            -hy + 0.12,
            hx - 0.05,
            -hy + 0.3,
            0.015,
            (200, 206, 210),
            (138, 144, 148),
        )

    def tv(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.03, (58, 50, 44), (28, 24, 20))
        rr(
            -hx + 0.12,
            -hy + 0.04,
            hx - 0.12,
            -hy + 0.14,
            0.015,
            (18, 20, 22),
            (8, 8, 10),
        )

    def generic(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.06, (200, 184, 164), (106, 90, 72))

    painters = {
        "sofa.2seat": sofa,
        "sofa.lshape": sofa,
        "armchair": armchair,
        "table.dining": table_dining,
        "chair.dining": chair,
        "table.coffee": coffee,
        "counter.kitchen": counter,
        "stove": stove,
        "nightstand": night,
        "wardrobe": wardrobe,
        "desk": desk,
        "fireplace": fireplace,
        "bathtub": bathtub,
        "toilet": toilet,
        "sink.basin": sink,
        "sink": sink,
        "car.sedan": car,
        "rug.rect": rug,
        "plant.pot": plant,
        "fridge": fridge,
        "tv.console": tv,
    }
    painter = painters.get(cid, generic)
    if cid.startswith("bed."):
        painter = bed
    extra_d = dd + 0.18
    extra_w = w + (0.2 if cid == "car.sedan" else 0.14)
    _stamp(img, P, px, py, rot, extra_w, extra_d + 0.12, sc, painter)


def _furniture(
    d: ImageDraw.ImageDraw,
    typ: str,
    bx: tuple[float, float, float, float],
    P: Any,
    sc: float,
) -> None:
    """Mobilier de repli (sans catalogue) : mêmes couleurs que Sweet Home 3D."""
    m = 0.25
    x0, y0, x1, y1 = bx[0] + m, bx[1] + m, bx[2] - m, bx[3] - m
    w, h = x1 - x0, y1 - y0
    if w < 0.8 or h < 0.8:
        return
    lw = max(1, int(0.02 * sc))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def sh(a: float, b: float, c: float, e: float, rad: float = 0.12) -> None:
        _rrect(d, [P(a + 0.05, b + 0.07), P(c + 0.05, e + 0.07)], rad * sc, fill=_SHADOW)

    def rect(a: float, b: float, c: float, e: float, fill: Any = _FURN_FILL) -> None:
        d.rectangle([P(a, b), P(c, e)], fill=fill, outline=_FURN, width=lw)

    def rr(
        a: float,
        b: float,
        c: float,
        e: float,
        rad: float = 0.12,
        fill: Any = _FURN_FILL,
    ) -> None:
        _rrect(d, [P(a, b), P(c, e)], rad * sc, fill=fill, outline=_FURN, width=lw)

    def circ(a: float, b: float, rad: float, fill: Any = _FURN_FILL) -> None:
        d.ellipse(
            [P(a - rad, b - rad), P(a + rad, b + rad)],
            fill=fill,
            outline=_FURN,
            width=lw,
        )

    def line(a: float, b: float, c: float, e: float, fill: Any = _FURN) -> None:
        d.line([P(a, b), P(c, e)], fill=fill, width=lw)

    if typ == "bedroom":
        bw, bh = min(1.8, w - 0.7), min(2.05, h - 0.9)
        if bw < 1.2 or bh < 1.6:
            return
        xb0, xb1 = cx - bw / 2, cx + bw / 2
        if h - bh > 1.1:  # tapis au pied du lit
            rr(
                max(x0, xb0 - 0.45),
                y0 + bh - 0.5,
                min(x1, xb1 + 0.45),
                min(y1 - 0.1, y0 + bh + 0.7),
                0.08,
                fill=_RUG,
            )
        sh(xb0, y0, xb1, y0 + bh, 0.1)
        rr(xb0, y0, xb1, y0 + bh, 0.1)  # lit
        rect(xb0, y0, xb1, y0 + 0.14, fill=(232, 233, 238))  # tête de lit
        pw = bw / 2 - 0.28
        rr(xb0 + 0.14, y0 + 0.2, xb0 + 0.14 + pw, y0 + 0.52, 0.06)  # oreillers
        rr(xb1 - 0.14 - pw, y0 + 0.2, xb1 - 0.14, y0 + 0.52, 0.06)
        line(xb0 + 0.08, y0 + bh * 0.58, xb1 - 0.08, y0 + bh * 0.58)  # pli de couette
        rect(xb0 + 0.06, y0 + bh - 0.48, xb1 - 0.06, y0 + bh - 0.08, fill=(238, 231, 219))  # jeté
        for s in (-1, 1):  # tables de nuit + lampes
            nx0 = xb0 - 0.62 if s < 0 else xb1 + 0.12
            if nx0 >= x0 - 0.01 and nx0 + 0.5 <= x1 + 0.26:
                rect(nx0, y0, nx0 + 0.5, y0 + 0.42)
                circ(nx0 + 0.25, y0 + 0.21, 0.09)
        if h - bh > 1.0:  # penderie sur le mur du fond
            wr = min(w, 2.4)
            rect(x0, y1 - 0.62, x0 + wr, y1, fill=_FURN_SOFT)
            xx = x0 + 0.6
            while xx < x0 + wr - 0.15:
                line(xx, y1 - 0.62, xx, y1)
                circ(xx - 0.11, y1 - 0.31, 0.035, fill=_FURN)
                xx += 0.6
    elif typ == "living":
        if w >= h:  # canapé contre le mur du fond, TV sur le mur d'en face
            sw = min(2.4, w - 0.9)
            if sw < 1.2:
                return
            sx0, sx1 = x0 + 0.35, x0 + 0.35 + sw
            sy0, sy1 = y1 - 0.98, y1 - 0.03
            rr(sx0, max(y0 + 0.55, sy0 - 1.35), sx1 + 0.2, sy0 - 0.25, 0.1, fill=_RUG)
            rect(x0 + 0.4, y0, x0 + 2.0, y0 + 0.38, fill=_FURN_SOFT)  # meuble TV
            rect(x0 + 0.58, y0 + 0.04, x0 + 1.82, y0 + 0.22, fill=(58, 61, 68))
            sh(sx0, sy0, sx1, sy1, 0.16)
            rr(sx0, sy0, sx1, sy1, 0.16, fill=(72, 74, 78))  # canapé
            rect(sx0, sy0, sx0 + 0.24, sy1, fill=(88, 90, 94))  # accoudoirs
            rect(sx1 - 0.24, sy0, sx1, sy1, fill=(88, 90, 94))
            line(sx0 + 0.24, sy0 + 0.3, sx1 - 0.24, sy0 + 0.3)  # dossier
            n = max(2, int(sw // 0.8))
            for i in range(1, n):  # coussins
                xx = sx0 + 0.24 + (sw - 0.48) * i / n
                line(xx, sy0 + 0.3, xx, sy1)
            sh(cx - 0.42, cy - 0.62, cx + 0.42, cy - 0.28, 0.06)
            rr(cx - 0.42, cy - 0.62, cx + 0.42, cy - 0.28, 0.06, fill=(248, 248, 246))  # table basse
            rect(cx - 0.32, cy + 0.15, cx + 0.32, cy + 0.85, fill=(28, 28, 30))  # cheminée
            # deux fauteuils, jamais une table à manger
            rr(cx - 1.45, cy - 0.55, cx - 0.62, cy + 0.22, 0.14, fill=(92, 62, 42))
            line(cx - 1.32, cy - 0.55, cx - 1.32, cy + 0.22)
            rr(cx + 0.62, cy - 0.55, cx + 1.45, cy + 0.22, 0.14, fill=(92, 62, 42))
            line(cx + 1.32, cy - 0.55, cx + 1.32, cy + 0.22)
            circ(x1 - 0.38, y0 + 0.75, 0.3, fill=_PLANT)  # plante
            circ(x1 - 0.38, y0 + 0.75, 0.16, fill=_PLANT_IN)
        else:  # pièce en hauteur : canapé contre le mur gauche
            sd = min(2.4, h - 0.9)
            if sd < 1.2:
                return
            sy0, sy1 = y0 + 0.35, y0 + 0.35 + sd
            sx0, sx1 = x0 + 0.03, x0 + 0.98
            rr(sx1 + 0.25, sy0, min(x1, sx1 + 1.6), sy1, 0.1, fill=_RUG)
            rect(x1 - 0.38, y0 + 0.4, x1, y0 + 2.0, fill=_FURN_SOFT)
            rect(x1 - 0.22, y0 + 0.58, x1 - 0.04, y0 + 1.82, fill=(58, 61, 68))
            sh(sx0, sy0, sx1, sy1, 0.16)
            rr(sx0, sy0, sx1, sy1, 0.16, fill=(72, 74, 78))
            rect(sx0, sy0, sx1, sy0 + 0.24, fill=(88, 90, 94))
            rect(sx0, sy1 - 0.24, sx1, sy1, fill=(88, 90, 94))
            line(sx0 + 0.3, sy0 + 0.24, sx0 + 0.3, sy1 - 0.24)
            n = max(2, int(sd // 0.8))
            for i in range(1, n):
                yy = sy0 + 0.24 + (sd - 0.48) * i / n
                line(sx0 + 0.3, yy, sx1, yy)
            rr(cx + 0.08, cy - 0.38, cx + 0.52, cy + 0.38, 0.06, fill=(248, 248, 246))  # table basse
            rr(cx - 0.95, cy - 0.95, cx - 0.18, cy - 0.18, 0.14, fill=(92, 62, 42))
            line(cx - 0.82, cy - 0.95, cx - 0.18, cy - 0.95)
            rr(cx - 0.95, cy + 0.18, cx - 0.18, cy + 0.95, 0.14, fill=(92, 62, 42))
            line(cx - 0.82, cy + 0.18, cx - 0.18, cy + 0.18)
            circ(x1 - 0.42, y1 - 0.55, 0.3, fill=_PLANT)
            circ(x1 - 0.42, y1 - 0.55, 0.16, fill=_PLANT_IN)
    elif typ == "kitchen":
        rect(x0, y0, x1, y0 + 0.62)  # plan de travail
        line(x0, y0 + 0.62, x1, y0 + 0.62)
        if h > 2.4:  # retour en L
            rect(x0, y0, x0 + 0.62, y0 + min(h - 0.6, 3.4))
            line(x0 + 0.62, y0, x0 + 0.62, y0 + min(h - 0.6, 3.4))
        rect(x1 - 0.68, y0 + 0.03, x1 - 0.04, y0 + 0.59, fill=_FURN_SOFT)  # frigo
        line(x1 - 0.68, y0 + 0.31, x1 - 0.04, y0 + 0.31)
        ex = x0 + 0.85  # petit évier encastré, pas une cuve
        if ex + 0.55 < x1 - 0.75:
            rect(ex, y0 + 0.14, ex + 0.38, y0 + 0.46, fill=(214, 216, 218))
            rect(ex + 0.05, y0 + 0.18, ex + 0.33, y0 + 0.42, fill=(198, 202, 206))
            circ(ex + 0.19, y0 + 0.10, 0.035, fill=_FURN)
        px = min(x0 + max(2.1, w * 0.45), x1 - 1.75)  # plaques 4 foyers
        if px > x0 and px + 0.75 < x1 - 0.75:
            for i in range(2):
                for j in range(2):
                    circ(
                        px + 0.2 + i * 0.32,
                        y0 + 0.17 + j * 0.28,
                        0.085 if (i + j) % 2 else 0.115,
                    )
    elif typ == "dining":
        tw, th = min(1.9, w - 1.7), min(1.05, h - 1.7)
        if tw < 1.0 or th < 0.75:
            return
        tx0, ty0, tx1, ty1 = cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2
        sh(tx0, ty0, tx1, ty1, 0.06)
        rr(tx0, ty0, tx1, ty1, 0.06, fill=(168, 118, 64))  # table
        rect(tx0 + 0.12, ty0 + 0.12, tx1 - 0.12, ty1 - 0.12, fill=(184, 132, 74))
        yellow = (232, 196, 64)
        for fx in (-tw / 4, tw / 4):  # 6 chaises
            rr(cx + fx - 0.21, ty0 - 0.6, cx + fx + 0.21, ty0 - 0.16, 0.08, fill=yellow)
            rr(cx + fx - 0.21, ty1 + 0.16, cx + fx + 0.21, ty1 + 0.6, 0.08, fill=yellow)
        rr(tx0 - 0.6, cy - 0.21, tx0 - 0.16, cy + 0.21, 0.08, fill=yellow)
        rr(tx1 + 0.16, cy - 0.21, tx1 + 0.6, cy + 0.21, 0.08, fill=yellow)
        if h - th > 2.0:  # buffet
            rect(x0, y1 - 0.48, x0 + min(1.9, w * 0.45), y1, fill=_FURN_SOFT)
    elif typ in ("bathroom", "wc"):
        txx = x0 + 0.08  # WC : réservoir + cuvette bien lisible
        tw = min(0.55, max(0.42, w * 0.35))
        rect(txx, y0 + 0.04, txx + tw, y0 + 0.28, fill=(248, 248, 246))
        d.ellipse(
            [P(txx - 0.04, y0 + 0.22), P(txx + tw + 0.04, y0 + 0.95)],
            fill=_FURN_FILL,
            outline=_FURN,
            width=max(lw, 2),
        )
        d.ellipse(
            [P(txx + 0.08, y0 + 0.36), P(txx + tw - 0.08, y0 + 0.82)],
            outline=_FURN,
            width=max(lw, 2),
        )
        if typ == "wc":
            circ(x1 - min(0.32, w * 0.22), y0 + 0.32, min(0.2, w * 0.14))
            return
        bw_ = min(1.75, w - 0.85)
        if bw_ >= 1.2 and h >= 1.9:  # baignoire
            bx0 = x0 + 0.72
            sh(bx0, y1 - 0.85, bx0 + bw_, y1 - 0.05, 0.2)
            rr(bx0, y1 - 0.85, bx0 + bw_, y1 - 0.05, 0.2)
            rr(bx0 + 0.15, y1 - 0.7, bx0 + bw_ - 0.15, y1 - 0.2, 0.13, fill=_FURN_SOFT)
            circ(bx0 + bw_ - 0.22, y1 - 0.45, 0.05, fill=_FURN)  # bonde
            circ(bx0 + 0.14, y1 - 0.45, 0.045, fill=_FURN)  # robinet
        if w >= 1.9:  # meuble vasque
            rect(x1 - 0.58, y0 + 0.02, x1 - 0.02, y0 + 0.62)
            circ(x1 - 0.3, y0 + 0.32, 0.16)
    elif typ == "office":
        dw_ = min(1.7, w - 0.5)
        sh(x0, y0, x0 + dw_, y0 + 0.7, 0.04)
        rect(x0, y0, x0 + dw_, y0 + 0.7)  # bureau
        line(x0 + 0.15, y0 + 0.35, x0 + dw_ - 0.15, y0 + 0.35)
        ax_ = x0 + min(0.9, dw_ / 2)
        circ(ax_, y0 + 1.14, 0.26)  # fauteuil
        line(ax_ - 0.19, y0 + 0.94, ax_ + 0.19, y0 + 0.94)
        if w >= 2.3:  # bibliothèque
            hh = min(1.8, h - 0.8)
            rect(x1 - 0.38, y0, x1, y0 + hh, fill=_FURN_SOFT)
            yy = y0 + 0.45
            while yy < y0 + hh - 0.15:
                line(x1 - 0.38, yy, x1, yy)
                yy += 0.45
        if h > 2.2:
            circ(x1 - 0.45, y1 - 0.5, 0.28, fill=_PLANT)
    elif typ == "garage":
        cw_, ch_ = min(4.6, w - 0.6), min(1.95, h - 0.7)
        if cw_ < 3.0 or ch_ < 1.35:
            return
        gx0, gy0, gx1, gy1 = cx - cw_ / 2, cy - ch_ / 2, cx + cw_ / 2, cy + ch_ / 2
        sh(gx0, gy0, gx1, gy1, 0.42)
        rr(gx0, gy0, gx1, gy1, 0.42)  # voiture
        rr(gx0 + cw_ * 0.3, gy0 + 0.12, gx0 + cw_ * 0.64, gy1 - 0.12, 0.18)  # pavillon
        line(gx0 + cw_ * 0.3, gy0 + 0.12, gx0 + cw_ * 0.22, gy0 + 0.02)  # pare-brise
        line(gx0 + cw_ * 0.3, gy1 - 0.12, gx0 + cw_ * 0.22, gy1 - 0.02)
        line(gx0 + cw_ * 0.64, gy0 + 0.12, gx0 + cw_ * 0.72, gy0 + 0.02)  # lunette arrière
        line(gx0 + cw_ * 0.64, gy1 - 0.12, gx0 + cw_ * 0.72, gy1 - 0.02)
        for wx_ in (gx0 + cw_ * 0.15, gx0 + cw_ * 0.73):  # roues
            d.rectangle([P(wx_, gy0 - 0.1), P(wx_ + 0.32, gy0 + 0.07)], fill=(70, 72, 78))
            d.rectangle([P(wx_, gy1 - 0.07), P(wx_ + 0.32, gy1 + 0.1)], fill=(70, 72, 78))
    elif typ == "laundry":
        for i in range(2):  # machines hublot
            mx = x0 + i * 0.72
            if mx + 0.66 > x1:
                break
            rect(mx, y0, mx + 0.66, y0 + 0.68)
            circ(mx + 0.33, y0 + 0.4, 0.2)
            rect(mx + 0.1, y0 + 0.05, mx + 0.34, y0 + 0.12, fill=_FURN_SOFT)
    elif typ == "storage":
        sw_ = min(w, 2.2)
        rect(x0, y0, x0 + sw_, y0 + 0.42, fill=_FURN_SOFT)  # étagères
        xx = x0 + 0.55
        while xx < x0 + sw_ - 0.1:
            line(xx, y0, xx, y0 + 0.42)
            xx += 0.55
        if w > 1.6 and h > 1.4:  # cartons
            rr(x1 - 0.75, y1 - 0.75, x1 - 0.25, y1 - 0.25, 0.05)
            rr(x1 - 1.25, y1 - 0.6, x1 - 0.85, y1 - 0.2, 0.05)
    elif typ == "hallway":
        if w > 2.4:
            rr(x0 + 0.3, cy - 0.38, x1 - 0.3, cy + 0.38, 0.1, fill=_RUG)  # tapis de couloir
        if w >= 2.2:
            rect(x0, y0, x0 + min(1.2, w * 0.4), y0 + 0.34, fill=_FURN_SOFT)  # console


def _room_caption(
    d: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    name: str,
    area: Any,
    sc: float,
) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    avail = (x1 - x0) - 10 * _SS
    disp = name
    fs = int(min(max(11 * _SS, (x1 - x0) * 0.22), 30 * _SS))
    while fs > 9 * _SS:
        f = _room_font(fs)
        if d.textlength(disp, font=f) <= avail:
            break
        fs -= _SS
    f = _room_font(fs)
    sub = f"{float(area):.0f} m²" if area else ""
    fsub = _room_font(max(8 * _SS, int(fs * 0.62)))
    oy = -fs * 0.42 if sub else 0
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):  # halo blanc pour lisibilité
        d.text(
            (cx + dx, cy + oy + dy),
            disp,
            font=f,
            fill=(255, 255, 255, 235),
            anchor="mm",
        )
    d.text((cx, cy + oy), disp, font=f, fill=(38, 38, 42), anchor="mm")
    if sub:
        d.text((cx, cy + oy + fs * 0.92), sub, font=fsub, fill=(122, 122, 128), anchor="mm")


def _edges_m(poly: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    xs = [p["x"] for p in poly]
    ys = [p["y"] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _render_floorplan(
    rooms: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    openings: list[dict[str, Any]],
    width: float,
    depth: float,
    veranda_depth: float = 0.0,
    annotate: bool = False,
    furniture: list[dict[str, Any]] | None = None,
) -> str:
    """Rendu vectoriel style Sweet Home 3D : sols, mobilier texturé, jardin, porche sud."""
    width = max(1.0, float(width))
    depth = max(1.0, float(depth))
    base_scale = max(24.0, min(900.0 / width, 600.0 / depth))
    sc = base_scale * _SS
    pad_l, pad_r, pad_t0, pad_b = 88 * _SS, 110 * _SS, 48 * _SS, 150 * _SS
    vpx = int(round(veranda_depth * sc)) if veranda_depth and veranda_depth > 0 else 0
    pad_t = pad_t0 + vpx
    ox, oy = pad_l, pad_t
    cw = int(width * sc) + pad_l + pad_r
    ch = int(depth * sc) + pad_t + pad_b

    img = Image.new("RGB", (cw, ch), _PAGE_BG)
    d = ImageDraw.Draw(img, "RGBA")

    def P(mx: float, my: float) -> tuple[float, float]:
        return ox + mx * sc, oy + my * sc

    def X(mx: float) -> float:
        return ox + mx * sc

    def Y(my: float) -> float:
        return oy + my * sc

    hx0, hy0, hx1, hy1 = X(0), Y(0), X(width), Y(depth)
    ew = max(7, int(0.32 * sc))  # mur extérieur

    # Jardin L (sud + est) façon Sweet Home 3D
    d.rectangle([0, 0, cw, ch], fill=_GRASS)
    for i in range(280):
        gx = int((i * 73 + 19) % max(1, cw))
        gy = int((i * 47 + 31) % max(1, ch))
        rx = max(3, int(0.12 * sc + (i % 5)))
        col = _GRASS_DARK if i % 2 else (148, 186, 78)
        d.ellipse([gx - rx, gy - int(rx * 0.7), gx + rx, gy + int(rx * 0.7)], fill=(*col, 90))

    def _tree(mx: float, my: float, r: float) -> None:
        cx_, cy_ = P(mx, my)
        rr = r * sc
        d.ellipse(
            [cx_ - rr + 3, cy_ - rr + 4, cx_ + rr + 3, cy_ + rr + 4],
            fill=(30, 50, 16, 50),
        )
        d.ellipse([cx_ - rr, cy_ - rr, cx_ + rr, cy_ + rr], fill=(58, 106, 34))
        d.ellipse(
            [cx_ - rr * 0.45, cy_ - rr * 0.55, cx_ + rr * 0.35, cy_ + rr * 0.15],
            fill=(90, 148, 52),
        )
        d.ellipse(
            [cx_ - rr * 0.18, cy_ - rr * 0.18, cx_ + rr * 0.18, cy_ + rr * 0.18],
            fill=(106, 74, 40),
        )

    _tree(width + 0.85, depth * 0.28, 0.55)
    _tree(width + 1.15, depth * 0.62, 0.7)
    _tree(width * 0.22, depth + 1.05, 0.5)
    _tree(width * 0.55, depth + 1.2, 0.65)
    _tree(width * 0.85, depth + 0.95, 0.45)
    hedge = max(4, int(0.12 * sc))
    d.line(
        [P(width + 0.25, 0.15), P(width + 0.25, depth + 0.2)],
        fill=(70, 110, 40),
        width=hedge,
    )
    d.line(
        [P(0.1, depth + 0.25), P(width + 0.25, depth + 0.25)],
        fill=(70, 110, 40),
        width=hedge,
    )
    if annotate:
        d.text(
            (hx1 + (cw - hx1) / 2, (hy0 + hy1) / 2),
            "Jardin",
            fill=(62, 92, 40),
            font=_room_font(13 * _SS),
            anchor="mm",
        )
        d.text(
            ((hx0 + hx1) / 2, hy1 + 52 * _SS),
            "Jardin",
            fill=(62, 92, 40),
            font=_room_font(13 * _SS),
            anchor="mm",
        )

    if vpx:
        d.rectangle(
            [hx0 - ew // 2, hy0 - vpx, hx1 + ew // 2, hy0],
            fill=(216, 199, 172),
            outline=(122, 108, 84),
            width=max(2, _SS),
        )
        for gx in range(int(hx0), int(hx1), int(0.5 * sc) or 12):
            d.line(
                [(gx, hy0 - vpx + 5), (gx, hy0 - 5)],
                fill=(150, 133, 107, 130),
                width=max(1, _SS),
            )

    d.rectangle([hx0, hy0, hx1, hy1], fill=(255, 255, 255))

    boxes = []
    for room in rooms:
        poly = room.get("polygon") or []
        if len(poly) < 3:
            continue
        bm = _edges_m(poly)
        boxes.append((room, bm))
        _floor_texture(d, str(room.get("type") or ""), bm, P, sc)

    items = furniture or []
    if items:
        ordered = sorted(
            items,
            key=lambda it: 0 if str(it.get("catalog_id") or "").startswith("rug") else 1,
        )
        for it in ordered:
            _draw_catalog_item(img, d, it, P, sc)
    elif furniture is None:
        for room, bm in boxes:
            _furniture(d, str(room.get("type") or ""), bm, P, sc)

    # The porch is decorative; its position still follows the stored south door.
    walls_by_id = {str(wall.get("id")): wall for wall in walls}
    for opening in openings:
        if opening.get("type") != "door":
            continue
        wall = walls_by_id.get(str(opening.get("wall_id")))
        segment = opening_segment(wall, opening) if wall else None
        if segment is None or any(abs(point[1] - depth) > 1e-6 for point in segment):
            continue
        entry_left = min(point[0] for point in segment)
        entry_right = max(point[0] for point in segment)
        px0, px1 = entry_left - 0.35, entry_right + 0.35
        d.rectangle(
            [P(px0, depth), P(px1, depth + 1.15)],
            fill=_PORCH,
            outline=_PORCH_LINE,
            width=max(1, _SS),
        )
        yy = depth
        while yy < depth + 1.15:
            d.line([P(px0, yy), P(px1, yy)], fill=_PORCH_LINE, width=max(1, _SS))
            yy += 0.18
        if annotate:
            d.text(
                (X((entry_left + entry_right) / 2), Y(depth) + 28 * _SS),
                "Entrée",
                fill=_TEXT_SOFT,
                font=_room_font(10 * _SS),
                anchor="mm",
            )
        break

    draw_structure(d, walls, openings, P, sc)

    if annotate:
        for room, bm in boxes:
            area = float(room.get("area_m2") or 0)
            if area <= 0:
                area = max(0.0, (bm[2] - bm[0]) * (bm[3] - bm[1]))
            _room_caption(
                d,
                (X(bm[0]), Y(bm[1]), X(bm[2]), Y(bm[3])),
                str(room.get("name") or ""),
                area,
                sc,
            )

    # cotes avec lignes d'attache et ticks à 45°
    if annotate:
        dimf = _room_font(12 * _SS)
        dg = (150, 150, 154)
        yy = hy0 - vpx - 34 * _SS
        for xx in (hx0, hx1):
            d.line(
                [(xx, hy0 - vpx - 8 * _SS), (xx, yy + 5 * _SS)],
                fill=dg,
                width=max(1, _SS),
            )
            d.line(
                [(xx - 4 * _SS, yy + 4 * _SS), (xx + 4 * _SS, yy - 4 * _SS)],
                fill=dg,
                width=max(1, _SS),
            )
        d.line([(hx0, yy), (hx1, yy)], fill=dg, width=max(1, _SS))
        d.text(
            ((hx0 + hx1) / 2, yy - 11 * _SS),
            f"{width:.1f} m",
            fill=(104, 104, 108),
            font=dimf,
            anchor="mm",
        )
        xx = hx0 - 26 * _SS
        for yv in (hy0, hy1):
            d.line([(hx0 - 8 * _SS, yv), (xx + 5 * _SS, yv)], fill=dg, width=max(1, _SS))
            d.line(
                [(xx - 4 * _SS, yv - 4 * _SS), (xx + 4 * _SS, yv + 4 * _SS)],
                fill=dg,
                width=max(1, _SS),
            )
        d.line([(xx, hy0), (xx, hy1)], fill=dg, width=max(1, _SS))
        d.text(
            (xx - 9 * _SS, (hy0 + hy1) / 2),
            f"{depth:.1f} m",
            fill=(104, 104, 108),
            font=dimf,
            anchor="rm",
        )

    # cartouche : titre, surface, échelle, boussole (sous le jardin sud)
    fb = hy1 + 78 * _SS
    if annotate:
        d.line([(hx0, fb), (hx1, fb)], fill=(208, 203, 193), width=max(1, _SS))
        area = 0.0
        for r, bm in boxes:
            if str(r.get("type") or "") in {"garage", "storage"}:
                continue
            a = float(r.get("area_m2") or 0)
            if a <= 0:
                a = max(0.0, (bm[2] - bm[0]) * (bm[3] - bm[1]))
            area += a
        d.text(
            (hx0, fb + 16 * _SS),
            "PLAN DU REZ-DE-CHAUSSÉE",
            fill=_TEXT,
            font=_room_font(15 * _SS),
            anchor="lm",
        )
        d.text(
            (hx0, fb + 36 * _SS),
            f"{width:.1f} × {depth:.1f} m  —  Surface habitable ≈ {area:.0f} m²",
            fill=_TEXT_SOFT,
            font=_room_font(11 * _SS),
            anchor="lm",
        )
        sbx0, sbx1 = hx1 - sc - 34 * _SS, hx1 - 34 * _SS
        sby = fb + 26 * _SS
        d.line([(sbx0, sby), (sbx1, sby)], fill=_TEXT_SOFT, width=max(2, _SS))
        for t in (sbx0, sbx1):
            d.line(
                [(t, sby - 4 * _SS), (t, sby + 4 * _SS)],
                fill=_TEXT_SOFT,
                width=max(1, _SS),
            )
        d.text(
            ((sbx0 + sbx1) / 2, sby - 9 * _SS),
            "1 m",
            fill=_TEXT_SOFT,
            font=_room_font(10 * _SS),
            anchor="mm",
        )
        nx, ny = hx1 - 12 * _SS, fb + 26 * _SS
        d.ellipse(
            [nx - 10 * _SS, ny - 10 * _SS, nx + 10 * _SS, ny + 10 * _SS],
            outline=_TEXT_SOFT,
            width=max(1, _SS),
        )
        d.polygon(
            [
                (nx - 3.5 * _SS, ny + 4 * _SS),
                (nx + 3.5 * _SS, ny + 4 * _SS),
                (nx, ny - 6 * _SS),
            ],
            fill=_TEXT,
        )
        d.text(
            (nx, ny - 15 * _SS),
            "N",
            fill=_TEXT_SOFT,
            font=_room_font(10 * _SS),
            anchor="mm",
        )

    out = img.resize((cw // _SS, ch // _SS), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _overlay_room_labels(png_b64: str, rooms: list[dict[str, Any]], width: float, depth: float) -> str:
    """Pose les libellés canoniques sur une image (FLUX) pour éviter les fautes du modèle."""
    try:
        raw = base64.b64decode(png_b64)
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:  # noqa: BLE001
        return png_b64
    d = ImageDraw.Draw(img, "RGBA")
    iw, ih = img.size
    mx, my = max(width, 0.1), max(depth, 0.1)
    pad = min(iw, ih) * 0.06

    def P(mx0: float, my0: float) -> tuple[float, float]:
        return pad + mx0 / mx * (iw - 2 * pad), pad + my0 / my * (ih - 2 * pad)

    for room in rooms:
        poly = room.get("polygon") or []
        if len(poly) < 3:
            continue
        x0, y0, x1, y1 = _edges_m(poly)
        name = str(room.get("name") or "")
        if not name:
            continue
        bx = (P(x0, y0)[0], P(x0, y0)[1], P(x1, y1)[0], P(x1, y1)[1])
        _room_caption(d, bx, name, None, max(1.0, (iw / 900) * 2))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


ROOM_FILL: dict[str, tuple[int, int, int]] = {
    "living": (236, 214, 176),
    "kitchen": (232, 168, 120),
    "bedroom": (176, 198, 222),
    "bathroom": (152, 196, 196),
    "hallway": (228, 222, 214),
    "garage": (196, 196, 190),
    "office": (196, 184, 214),
    "dining": (222, 190, 168),
    "storage": (210, 206, 196),
}


def _room_font(size: int) -> _Font:
    for path in (
        "arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _draw_room_contents(draw: ImageDraw.ImageDraw, room: dict[str, Any], sx: float, sy: float, font: _Font) -> None:
    poly = room.get("polygon") or []
    if len(poly) < 3:
        return
    xs = [float(p["x"]) for p in poly]
    ys = [float(p["y"]) for p in poly]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    rw, rd = x1 - x0, y1 - y0
    typ = str(room.get("type") or "")

    def box(mx0: float, my0: float, mx1: float, my1: float, fill: tuple[int, int, int]) -> None:
        draw.rectangle([mx0 * sx, my0 * sy, mx1 * sx, my1 * sy], fill=fill, outline=(50, 50, 50))

    if typ == "kitchen":
        t = min(0.6, rd * 0.28)
        box(x0, y0, x1, y0 + t, (196, 160, 112))
        sink_x = x0 + rw * 0.2
        box(sink_x, y0 + 0.08, sink_x + 0.5, y0 + t - 0.08, (197, 216, 224))
        stove = x0 + rw * 0.55
        box(stove, y0 + 0.1, stove + 0.55, y0 + t - 0.1, (63, 63, 63))
    elif typ == "bathroom":
        box(x1 - min(1.7, rw - 0.3), y0 + 0.2, x1 - 0.2, y0 + 0.9, (184, 205, 212))
        cx, cy = x0 + 0.45, y1 - 0.45
        draw.ellipse(
            [(cx - 0.2) * sx, (cy - 0.22) * sy, (cx + 0.2) * sx, (cy + 0.22) * sy],
            fill=(236, 236, 236),
            outline=(50, 50, 50),
        )
    elif typ == "bedroom":
        box(
            x0 + 0.25,
            y0 + 0.25,
            x0 + min(2.0, rw - 0.35),
            y0 + min(1.5, rd - 0.35),
            (154, 168, 188),
        )
    elif typ == "living":
        box(x0 + 0.25, y1 - 0.85, x0 + min(2.4, rw - 0.35), y1 - 0.25, (138, 115, 88))

    name = str(room.get("name") or _label(typ, None))
    cx = (x0 + x1) / 2 * sx
    cy = (y0 + y1) / 2 * sy
    try:
        draw.text((cx, cy), name, fill=(28, 25, 23), font=font, anchor="mm")
    except TypeError:
        bbox = draw.textbbox((0, 0), name, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - tw / 2, cy - th / 2), name, fill=(28, 25, 23), font=font)
