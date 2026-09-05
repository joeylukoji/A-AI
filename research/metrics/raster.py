"""Paired raster metrics (no extra deps): MAE + IoU binaire murs."""
from __future__ import annotations

from typing import Any


def mae_norm(pred: Any, target: Any) -> float:
    """Mean absolute error on 0-1 arrays (PIL or list-like)."""
    a = _as01(pred)
    b = _as01(target)
    if len(a) != len(b) or not a:
        return 1.0
    return sum(abs(x - y) for x, y in zip(a, b, strict=True)) / len(a)


def wall_iou(pred: Any, target: Any, thresh: float = 0.45) -> float:
    a = [x < thresh for x in _as01(pred)]
    b = [x < thresh for x in _as01(target)]
    inter = sum(1 for x, y in zip(a, b, strict=True) if x and y)
    union = sum(1 for x, y in zip(a, b, strict=True) if x or y)
    return inter / union if union else 0.0


def evaluate_pair(pred: Any, target: Any) -> dict[str, float]:
    return {"mae": mae_norm(pred, target), "wall_iou": wall_iou(pred, target)}


def _as01(img: Any) -> list[float]:
    if hasattr(img, "convert"):
        pix = list(img.convert("L").getdata())
        return [p / 255.0 for p in pix]
    if hasattr(img, "tolist"):
        flat: list[float] = []
        for row in img.tolist():
            if isinstance(row, list):
                flat.extend(float(x) for x in row)
            else:
                flat.append(float(row))
        mx = max(flat) if flat else 1.0
        if mx > 1.5:
            return [x / 255.0 for x in flat]
        return flat
    return [float(x) for x in img]
