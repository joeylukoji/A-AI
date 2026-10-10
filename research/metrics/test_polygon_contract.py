"""Independent GEOS differential checks for the production overlap algorithm."""

from __future__ import annotations

import random

import pytest
from app.polygon_validation import intersection_area, simple_polygon
from shapely.geometry import Polygon


@pytest.mark.parametrize("seed", range(50))
def test_rectangle_overlap_area_matches_geos(seed):
    rng = random.Random(seed)
    polygons = []
    for _ in range(2):
        x, y = rng.uniform(0, 5), rng.uniform(0, 5)
        width, depth = rng.uniform(0.2, 4), rng.uniform(0.2, 4)
        polygons.append([(x, y), (x + width, y), (x + width, y + depth), (x, y + depth)])
    first, second = polygons
    assert intersection_area(first, second) == pytest.approx(
        Polygon(first).intersection(Polygon(second)).area, abs=1e-9
    )


@pytest.mark.parametrize("seed", range(50))
def test_concave_overlap_area_matches_geos(seed):
    rng = random.Random(seed)
    polygons = []
    for _ in range(2):
        x, y = rng.uniform(0, 3), rng.uniform(0, 3)
        width, depth = rng.uniform(2, 5), rng.uniform(2, 5)
        # Simple L shape with one re-entrant corner.
        polygons.append(
            [
                (x, y),
                (x + width, y),
                (x + width, y + depth / 3),
                (x + width / 3, y + depth / 3),
                (x + width / 3, y + depth),
                (x, y + depth),
            ]
        )
    first, second = polygons
    simple_polygon(first, "first")
    simple_polygon(second, "second")
    assert intersection_area(first, second) == pytest.approx(
        Polygon(first).intersection(Polygon(second)).area, abs=1e-9
    )


@pytest.mark.parametrize("seed", range(50))
def test_oblique_triangle_overlap_matches_geos(seed):
    rng = random.Random(seed + 1000)
    polygons = []
    for _ in range(2):
        x, y = rng.uniform(0, 2), rng.uniform(0, 2)
        width, depth = rng.uniform(1, 4), rng.uniform(1, 4)
        skew_x, skew_y = rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4)
        polygons.append([(x, y), (x + width, y + skew_y), (x + skew_x, y + depth)])
    first, second = polygons
    assert intersection_area(first, second) == pytest.approx(
        Polygon(first).intersection(Polygon(second)).area, abs=1e-9
    )
