"""World-space cutter boxes for doors / windows on a wall."""
from __future__ import annotations

import math
from typing import Any


def wall_length(wall: dict[str, Any]) -> float:
    a, b = wall["a"], wall["b"]
    return math.hypot(float(b["x"]) - float(a["x"]), float(b["y"]) - float(a["y"])) or 0.1


def cutter_transform(wall: dict[str, Any], opening: dict[str, Any]) -> dict[str, Any]:
    ax, ay = float(wall["a"]["x"]), float(wall["a"]["y"])
    bx, by = float(wall["b"]["x"]), float(wall["b"]["y"])
    length = wall_length(wall)
    ux, uy = (bx - ax) / length, (by - ay) / length
    offset = max(0.0, float(opening.get("offset_m") or 0.4))
    width = max(0.4, float(opening.get("width_m") or 0.9))
    if offset + width > length:
        offset = max(0.0, length - width)
    mid = offset + width / 2.0
    cx, cy = ax + ux * mid, ay + uy * mid
    kind = opening.get("type") or "door"
    thickness = float(wall.get("thickness_m") or 0.2) + 0.15
    if kind == "window":
        z, hz = 1.45, 1.1
    else:
        z, hz = 1.05, 2.1
    return {
        "kind": kind,
        "location": (cx, cy, z),
        "scale": (width, thickness, hz),
        "rotation_z": math.atan2(by - ay, bx - ax),
    }
