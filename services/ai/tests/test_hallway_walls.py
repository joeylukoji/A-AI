"""Un couloir découpé en segments n'a pas de mur entre ses segments."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import layout_partis as lp  # noqa: E402
from app.diffusion import perimeter_and_internal_walls  # noqa: E402
from test_layout_partis import _r  # noqa: E402


def _inner(walls: list[dict]) -> list[tuple]:
    return [(w["a"]["x"], w["a"]["y"], w["b"]["x"], w["b"]["y"]) for w in walls if str(w["id"]).startswith("w_i")]


def _has_wall(walls: list[dict], a: tuple[float, float], b: tuple[float, float]) -> bool:
    return any({(x0, y0), (x1, y1)} == {a, b} for x0, y0, x1, y1 in _inner(walls))


# Deux segments de couloir côte à côte (x 0-4 et 4-8), une chambre au nord de chacun.
PLAN = [
    _r("h1", "hallway", 0, 6, 4, 10), _r("h2", "hallway", 4, 6, 8, 10),
    _r("b1", "bedroom", 0, 0, 4, 6), _r("b2", "bedroom", 4, 0, 8, 6),
]


def test_no_wall_between_two_hallway_segments():
    assert not _has_wall(perimeter_and_internal_walls(PLAN, 8, 10), (4, 6), (4, 10))


def test_a_wall_still_separates_a_hallway_from_a_bedroom():
    walls = perimeter_and_internal_walls(PLAN, 8, 10)
    assert _has_wall(walls, (0, 6), (4, 6)) and _has_wall(walls, (4, 6), (8, 6))


def test_a_wall_still_separates_two_bedrooms():
    assert _has_wall(perimeter_and_internal_walls(PLAN, 8, 10), (4, 0), (4, 6))


def test_the_wall_between_a_hallway_and_another_room_survives_when_a_third_room_shares_the_edge():
    """Une arête commune à un couloir et à une pièce garde son mur, même si un autre couloir la touche."""
    plan = [_r("h1", "hallway", 0, 0, 4, 4), _r("h2", "hallway", 0, 0, 4, 4), _r("k", "kitchen", 4, 0, 8, 4)]
    assert _has_wall(perimeter_and_internal_walls(plan, 8, 4), (4, 0), (4, 4))


def test_hallway_segments_count_as_linked_for_accessibility():
    """Les portes des chambres ouvrent chacune sur leur segment ; l'entrée est sur le premier."""
    issues = lp.door_issues(PLAN, 8, 10)
    assert not any(i.startswith("inaccessible") for i in issues)


def test_a_bedroom_behind_the_second_hallway_segment_is_reachable():
    plan = [_r("h1", "hallway", 0, 6, 4, 10), _r("h2", "hallway", 4, 6, 8, 10), _r("b2", "bedroom", 4, 0, 8, 6)]
    issues = lp.door_issues(plan, 8, 10)
    assert "inaccessible:b2" not in issues and not any(i.startswith("traversee") for i in issues)


def test_a_lone_hallway_keeps_the_walls_that_face_nothing():
    """Une arête qu'un seul couloir borde (rien de l'autre côté) garde son mur."""
    walls = perimeter_and_internal_walls([_r("h", "hallway", 0, 0, 4, 4)], 8, 8)
    assert _has_wall(walls, (4, 0), (4, 4)) and _has_wall(walls, (0, 4), (4, 4))
