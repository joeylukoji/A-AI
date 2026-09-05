#!/usr/bin/env python3
"""Topological validity metrics for PlanDocument."""
from __future__ import annotations

import json
from typing import Any


def closed_perimeter(plan: dict[str, Any], tol: float = 1e-6) -> bool:
    walls = plan.get("walls") or []
    if not walls:
        return False
    # Heuristic: at least 4 walls and bounding box edges present
    bounds = plan.get("floor", {}).get("bounds", {})
    w = float(bounds.get("width", 0))
    d = float(bounds.get("depth", 0))
    if w <= 0 or d <= 0:
        return False
    return len(walls) >= 4


def room_polygons_valid(plan: dict[str, Any]) -> float:
    rooms = plan.get("rooms") or []
    if not rooms:
        return 0.0
    ok = sum(1 for r in rooms if len(r.get("polygon") or []) >= 3)
    return ok / len(rooms)


def orthogonality(plan: dict[str, Any]) -> float:
    walls = plan.get("walls") or []
    if not walls:
        return 0.0
    ortho = 0
    for wall in walls:
        ax, ay = wall["a"]["x"], wall["a"]["y"]
        bx, by = wall["b"]["x"], wall["b"]["y"]
        if abs(ax - bx) < 1e-6 or abs(ay - by) < 1e-6:
            ortho += 1
    return ortho / len(walls)


def evaluate(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "closed_perimeter": closed_perimeter(plan),
        "room_polygon_ratio": room_polygons_valid(plan),
        "orthogonality": orthogonality(plan),
    }


if __name__ == "__main__":
    import sys
    plan = json.loads(sys.stdin.read())
    print(json.dumps(evaluate(plan), indent=2))
