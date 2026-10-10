"""Draw the stored walls and openings without making layout decisions."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from PIL import ImageDraw

from app.plan_geometry import opening_segment

Point = tuple[float, float]
Projection = Callable[[float, float], Point]


def draw_structure(
    draw: ImageDraw.ImageDraw,
    walls: list[dict[str, Any]],
    openings: list[dict[str, Any]],
    project: Projection,
    scale: float,
) -> None:
    """Paint existing wall segments first, then cut their explicit openings."""
    by_id = {str(wall.get("id")): wall for wall in walls}
    for wall in walls:
        a, b = wall["a"], wall["b"]
        points = [
            project(float(a["x"]), float(a["y"])),
            project(float(b["x"]), float(b["y"])),
        ]
        thickness = _wall_pixels(wall, scale)
        draw.line(points, fill=(88, 88, 86), width=thickness)
        draw.line(
            points,
            fill=(154, 154, 148),
            width=max(1, thickness - max(2, int(0.025 * scale))),
        )

    for opening in openings:
        wall = by_id.get(str(opening.get("wall_id")))
        if wall is None or opening.get("type") not in {"door", "window"}:
            continue
        segment = opening_segment(wall, opening)
        if segment is None:
            continue
        start, end = segment
        width = math.dist(start, end)
        ux, uy = (end[0] - start[0]) / width, (end[1] - start[1]) / width
        normal = (-uy, ux)
        gap = _wall_pixels(wall, scale) + 2
        draw.line([project(*start), project(*end)], fill=(255, 255, 255), width=gap)
        if opening["type"] == "window":
            _draw_window(draw, start, end, normal, project, scale)
        else:
            _draw_door(draw, start, end, normal, project, scale)


def _wall_pixels(wall: dict[str, Any], scale: float) -> int:
    default = 0.2 if str(wall.get("id", "")).startswith("w_outer") else 0.15
    return max(1, round(float(wall.get("thickness_m") or default) * scale))


def _draw_window(
    draw: ImageDraw.ImageDraw,
    start: Point,
    end: Point,
    normal: Point,
    project: Projection,
    scale: float,
) -> None:
    for offset in (-0.055, 0.055):
        points = [project(point[0] + normal[0] * offset, point[1] + normal[1] * offset) for point in (start, end)]
        draw.line(points, fill=(110, 114, 122), width=max(1, round(0.018 * scale)))
    draw.line(
        [project(*start), project(*end)],
        fill=(168, 196, 218),
        width=max(1, round(0.03 * scale)),
    )


def _draw_door(
    draw: ImageDraw.ImageDraw,
    start: Point,
    end: Point,
    normal: Point,
    project: Projection,
    scale: float,
) -> None:
    width = math.dist(start, end)
    leaf = (start[0] + normal[0] * width, start[1] + normal[1] * width)
    draw.line(
        [project(*start), project(*leaf)],
        fill=(168, 122, 72),
        width=max(2, round(0.035 * scale)),
    )
    # The schema has no hinge/swing field yet; this is a display convention,
    # never a new opening or a change to its position/width.
    ux, uy = (end[0] - start[0]) / width, (end[1] - start[1]) / width
    arc = []
    for step in range(17):
        angle = math.pi * step / 32
        arc.append(
            project(
                start[0] + width * (ux * math.cos(angle) + normal[0] * math.sin(angle)),
                start[1] + width * (uy * math.cos(angle) + normal[1] * math.sin(angle)),
            )
        )
    draw.line(arc, fill=(158, 162, 170), width=max(1, round(0.018 * scale)))
