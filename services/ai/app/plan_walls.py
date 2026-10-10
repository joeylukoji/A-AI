"""Construction des murs depuis les pièces, sans dépendance au rendu."""

from __future__ import annotations

from typing import Any


def perimeter_and_internal_walls(rooms: list[dict[str, Any]], width: float, depth: float) -> list[dict[str, Any]]:
    """Build the perimeter and unique partitions, leaving shared hallways open."""
    walls = [
        {
            "id": "w_outer_1",
            "a": {"x": 0, "y": 0},
            "b": {"x": width, "y": 0},
            "thickness_m": 0.2,
        },
        {
            "id": "w_outer_2",
            "a": {"x": width, "y": 0},
            "b": {"x": width, "y": depth},
            "thickness_m": 0.2,
        },
        {
            "id": "w_outer_3",
            "a": {"x": width, "y": depth},
            "b": {"x": 0, "y": depth},
            "thickness_m": 0.2,
        },
        {
            "id": "w_outer_4",
            "a": {"x": 0, "y": depth},
            "b": {"x": 0, "y": 0},
            "thickness_m": 0.2,
        },
    ]
    open_edges = _hallway_only_edges(rooms)
    seen: set[tuple[float, float, float, float]] = set()
    wid = 1
    for room in rooms:
        poly = room.get("polygon") or [] if isinstance(room, dict) else []
        if len(poly) < 3:
            continue
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            if _is_outer_edge(a, b, width, depth):
                continue
            key = _edge_key(a, b)
            if key in seen:
                continue
            seen.add(key)
            if key in open_edges:
                continue  # deux segments d'un même couloir : pas de mur entre eux
            walls.append(
                {
                    "id": f"w_i{wid}",
                    "a": {"x": key[0], "y": key[1]},
                    "b": {"x": key[2], "y": key[3]},
                    "thickness_m": 0.15,
                }
            )
            wid += 1
    return walls


def _hallway_only_edges(
    rooms: list[dict[str, Any]],
) -> set[tuple[float, float, float, float]]:
    """Arêtes que se partagent des segments de couloir et rien d'autre.

    Le packer découpe un couloir en plusieurs rectangles ; un mur entre deux d'entre eux ne
    sépare rien, et sans porte il scellerait le couloir en morceaux.
    """
    hall: dict[tuple[float, float, float, float], int] = {}
    other: set[tuple[float, float, float, float]] = set()
    for room in rooms:
        poly = room.get("polygon") or [] if isinstance(room, dict) else []
        if len(poly) < 3:
            continue
        for i in range(len(poly)):
            key = _edge_key(poly[i], poly[(i + 1) % len(poly)])
            if room.get("type") == "hallway":
                hall[key] = hall.get(key, 0) + 1
            else:
                other.add(key)
    return {key for key, n in hall.items() if n >= 2 and key not in other}


def _edge_key(a: dict[str, float], b: dict[str, float]) -> tuple[float, float, float, float]:
    ax, ay, bx, by = (
        round(a["x"], 3),
        round(a["y"], 3),
        round(b["x"], 3),
        round(b["y"], 3),
    )
    if (ax, ay) <= (bx, by):
        return ax, ay, bx, by
    return bx, by, ax, ay


def _is_outer_edge(a: dict[str, float], b: dict[str, float], width: float, depth: float) -> bool:
    xs = {a["x"], b["x"]}
    ys = {a["y"], b["y"]}
    on_left = xs == {0.0} or (min(xs) <= 0 and max(xs) <= 0)
    on_right = min(xs) >= width and max(xs) >= width
    on_top = ys == {0.0} or (min(ys) <= 0 and max(ys) <= 0)
    on_bottom = min(ys) >= depth and max(ys) >= depth
    return on_left or on_right or on_top or on_bottom
