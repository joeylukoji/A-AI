"""Resolve a buildable rectangle without silently enlarging its parcel."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.plan_contracts import PlanConstraintError


@dataclass(frozen=True)
class BuildableParcel:
    """Validated dimensions in metres, snapped inside the available envelope."""

    width_m: float
    depth_m: float
    setback_m: float
    buildable_width_m: float
    buildable_depth_m: float
    grid_m: float
    min_side_m: float


def _finite(value: Any, field: str, *, allow_zero: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PlanConstraintError("invalid_numeric_constraint", (field,), "nombre fini requis") from exc
    if isinstance(value, bool) or not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        raise PlanConstraintError("invalid_numeric_constraint", (field,), "valeur positive finie requise")
    return number


def _value(source: dict[str, Any], field: str, fallback: Any) -> Any:
    value = source.get(field)
    return fallback if value is None else value


def validate_request_dimensions(constraints: dict[str, Any]) -> None:
    """Reject invalid raw aliases before the NLU can normalize them away."""
    for field in ("parcel_width_m", "parcel_depth_m", "max_width_m", "max_depth_m", "setback_m"):
        if constraints.get(field) is not None:
            _finite(constraints[field], field, allow_zero=field == "setback_m")


def resolve_parcel(parcel: dict[str, Any], bounds: dict[str, Any], rules: dict[str, Any]) -> BuildableParcel:
    """Reject impossible envelopes and preserve the historical 200 m work limit.

    The two-times-minimum-side limit belongs to the current packer, not to any
    regulatory definition of a feasible building.
    """
    width = min(200.0, _finite(_value(parcel, "width_m", _value(bounds, "width", 12)), "width_m"))
    depth = min(200.0, _finite(_value(parcel, "depth_m", _value(bounds, "depth", 10)), "depth_m"))
    setback = _finite(_value(parcel, "setback_m", 0), "setback_m", allow_zero=True)
    grid = _finite(_value(rules, "grid_m", 0.1), "grid_m")
    minimum = _finite(_value(rules, "min_side_m", 2.0), "min_side_m")
    # The layout engine serializes vertices to centimetres. A finer or
    # incompatible grid can round the final polygon outside the requested lot.
    centimetres = grid * 100
    if (
        not math.isfinite(centimetres)
        or grid < 0.01
        or not math.isclose(
            centimetres,
            round(centimetres),
            rel_tol=0,
            abs_tol=1e-8,
        )
    ):
        raise PlanConstraintError(
            "unsupported_grid_precision",
            ("grid_m",),
            "la grille doit être un multiple de 0,01 m",
        )

    def snap_inside(length: float, dimension: str) -> float:
        usable = length - 2 * setback
        if usable <= 0:
            raise PlanConstraintError(
                "non_positive_usable_envelope",
                (dimension, "setback_m"),
                "les retraits épuisent la parcelle",
            )
        steps = usable / grid
        if not math.isfinite(steps):
            raise PlanConstraintError("invalid_grid", ("grid_m",), "grille trop fine pour cette emprise")
        snapped = round(steps) * grid
        if snapped - usable > 1e-9:
            snapped = math.floor(steps) * grid
        if snapped < 2 * minimum:
            raise PlanConstraintError(
                "unsupported_buildable_envelope",
                (dimension, "setback_m", "grid_m", "min_side_m"),
                "emprise après retraits et grille inférieure au minimum du moteur",
            )
        return snapped

    return BuildableParcel(
        width, depth, setback, snap_inside(width, "width_m"), snap_inside(depth, "depth_m"), grid, minimum
    )
