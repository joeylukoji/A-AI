from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from homekit3d import Catalog, Plan  # noqa: E402


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return Catalog.load()


@pytest.fixture
def house() -> Plan:
    """Un petit plan complet : séjour + chambre + couloir, une porte, une fenêtre."""
    plan = Plan(8.0, 6.0, seed=3)
    plan.rect_room("living", 0, 0, 5, 4, name="Séjour")
    plan.rect_room("bedroom", 5, 0, 8, 4, name="Chambre")
    plan.rect_room("hallway", 0, 4, 8, 6, name="Couloir")
    plan.outline()
    plan.walls_from_rooms()
    plan.door(plan.wall_at(5.0, 1.0), 0.5)
    plan.window(plan.wall_at(2.5, 0.0), 1.0, width=1.4)
    return plan
