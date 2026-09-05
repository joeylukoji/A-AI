#!/usr/bin/env python3
"""Constraint compliance: BuildingSpec vs PlanDocument."""
from __future__ import annotations

from typing import Any


def room_count_score(spec: dict[str, Any], plan: dict[str, Any]) -> float:
    expected = 0
    for r in spec.get("rooms") or []:
        expected += int(r.get("count") or 1)
    got = len(plan.get("rooms") or [])
    if expected == 0:
        return 1.0
    return max(0.0, 1.0 - abs(expected - got) / expected)


def evaluate(spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "room_count_score": room_count_score(spec, plan),
        "has_bounds": bool(plan.get("floor", {}).get("bounds")),
    }
