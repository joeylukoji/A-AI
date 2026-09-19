"""Le nombre de salles de bain vient du brief, pas du nombre de chambres."""
from __future__ import annotations

import pytest

from app.nlu import _heuristic_parse


def _bathrooms(brief: str) -> int:
    spec = _heuristic_parse(brief, {})
    return sum(r.get("count", 1) for r in spec["rooms"] if r["type"] == "bathroom")


@pytest.mark.parametrize("brief", [
    "Maison 3 chambres, séjour, cuisine, salle de bain et garage",
    "Maison 4 chambres, séjour, cuisine, salle de bain, WC",
    "Maison 5 chambres avec une salle de bain",
])
def test_one_bathroom_asked_gives_one_whatever_the_bedrooms(brief):
    assert _bathrooms(brief) == 1


@pytest.mark.parametrize("brief", [
    "Maison 3 chambres, 2 salles de bain, séjour, cuisine",
    "Maison 2 chambres et deux salles de bain",
])
def test_two_bathrooms_asked_gives_two(brief):
    assert _bathrooms(brief) == 2
