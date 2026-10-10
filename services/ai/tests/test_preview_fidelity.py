"""Aperçu Gemini : le prompt décrit le plan FINAL (couloir compté une fois, total annoncé)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import diffusion  # noqa: E402


def _room(rid: str, typ: str, x0: float, y0: float, x1: float, y1: float, name: str | None = None) -> dict:
    return {"id": rid, "type": typ, "name": name or typ,
            "polygon": [{"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]}


# Le couloir final est découpé en trois segments, comme `plan_adapt` le fait.
PLAN = [
    _room("b1", "bedroom", 0, 0, 4, 4, "Chambre 1"),
    _room("b2", "bedroom", 4, 0, 8, 4, "Chambre 2"),
    _room("h1", "hallway", 0, 4, 3, 5, "Couloir 1"),
    _room("h2", "hallway", 3, 4, 6, 5, "Couloir 2"),
    _room("h3", "hallway", 6, 4, 8, 5, "Couloir 3"),
    _room("l", "living", 0, 5, 8, 9, "Séjour"),
]


# --- Décompte des pièces ------------------------------------------------------------------

def test_hallway_segments_count_as_one_room():
    assert diffusion._plan_counts(PLAN) == {"bedroom": 2, "hallway": 1, "living": 1}


def test_rooms_without_a_polygon_are_not_counted():
    assert diffusion._plan_counts([{"type": "bedroom", "polygon": []}, _room("l", "living", 0, 0, 5, 5)]) == {"living": 1}


def test_the_clause_states_the_total_from_the_final_plan():
    clause = diffusion._required_rooms_clause({"rooms": []}, PLAN)
    assert "2x bedroom" in clause and "1x hallway" in clause
    assert "exactly 4 enclosed spaces" in clause


def test_the_clause_follows_the_final_plan_over_the_initial_program():
    spec = {"rooms": [{"type": "bedroom", "count": 5}, {"type": "living", "count": 1}]}
    clause = diffusion._required_rooms_clause(spec, PLAN)
    assert "2x bedroom" in clause and "5x bedroom" not in clause


def test_the_clause_falls_back_to_the_program_without_a_plan():
    spec = {"rooms": [{"type": "bedroom", "count": 3}]}
    assert "3x bedroom" in diffusion._required_rooms_clause(spec)
    assert "3x bedroom" in diffusion._required_rooms_clause(spec, [])


# --- Positions ---------------------------------------------------------------------------

def test_the_topology_lists_the_hallway_once_with_all_its_parts():
    text = diffusion._topology_clause(PLAN, 8, 9)
    assert text.count("Hallway (") == 1 and "3 connected parts" in text
    assert "Couloir 2" not in text and "Couloir 3" not in text
    assert "x=3.0-6.0m, y=4.0-5.0m" in text            # chaque segment garde sa position
    assert "Chambre 1 (bedroom): x=0.0-4.0m, y=0.0-4.0m" in text


def test_a_single_hallway_part_is_singular():
    text = diffusion._topology_clause([_room("h", "hallway", 0, 0, 5, 1), _room("l", "living", 0, 1, 5, 5)], 5, 5)
    assert "1 connected part;" in text


def test_the_topology_never_says_the_corridor_has_no_walls():
    """Le guide dessine un mur le long de chaque arête : ne pas contredire l'image jointe."""
    assert "no walls" not in diffusion._topology_clause(PLAN, 8, 9)


def test_the_full_prompt_uses_the_final_plan():
    prompt = diffusion._flux_prompt(brief="maison", spec={"rooms": [{"type": "bedroom", "count": 9}]},
                                    rooms=PLAN, width=8, depth=9, layout_guided=True)
    assert "exactly 4 enclosed spaces" in prompt and "9x bedroom" not in prompt
