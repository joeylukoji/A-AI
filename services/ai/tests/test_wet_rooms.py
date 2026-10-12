"""Salles d'eau : suite parentale seulement si demandée, une seule porte, consignes Gemini."""

import random

import pytest

from app import diffusion, nlu, pipeline
from app.plan_openings import _served_rooms


@pytest.fixture(autouse=True)
def _local_only(monkeypatch):
    monkeypatch.setenv("TOGETHER_PLANNER", "0")
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.delenv("EDENAI_API_KEY", raising=False)


@pytest.mark.parametrize(
    "brief",
    [
        "suite parentale",
        "chambre avec sa salle de bain",
        "chambre parentale avec sa propre douche",
        "toilettes dans la chambre",
        "salle de bain privative",
        "salle d'eau attenante",
        "en-suite bathroom",
    ],
)
def test_ensuite_when_asked(brief):
    assert nlu._wants_ensuite(brief)


@pytest.mark.parametrize(
    "brief",
    [
        "maison 3 chambres avec toilettes",
        "3 chambres avec salle de bain et wc",
        "je veux 3 chambres, ensuite un garage",
        "deux salles de bain et wc",
    ],
)
def test_no_ensuite_unless_asked(brief):
    assert not nlu._wants_ensuite(brief)


def _wet_room_doors(doc):
    rooms, walls = doc["rooms"], {w["id"]: w for w in doc["walls"]}
    out = {}
    for room in rooms:
        if room["type"] not in {"bathroom", "wc"}:
            continue
        neighbours = []
        for op in doc["openings"]:
            served = _served_rooms(walls[op["wall_id"]], op, rooms) if op["type"] == "door" else []
            if any(r is room for r in served):
                neighbours += [r["type"] for r in served if r is not room]
        out[room["id"]] = neighbours
    return out


def test_toilets_alone_stay_shared():
    doc = pipeline.generate_plan("maison 3 chambres avec toilettes", {})["plan_document"]
    doors = _wet_room_doors(doc)
    assert doors and all(n == ["hallway"] for n in doors.values()), doors


def test_requested_suite_opens_onto_a_bedroom():
    doc = pipeline.generate_plan("maison 3 chambres dont une suite parentale avec salle de bain", {})["plan_document"]
    assert sorted(n for ns in _wet_room_doors(doc).values() for n in ns) == ["bedroom", "hallway"]
    assert any(p.get("ensuite") for p in doc["program"])


def test_every_wet_room_has_exactly_one_door():
    rnd = random.Random(3)
    briefs = [
        "maison {n} chambres avec toilettes",
        "maison {n} chambres, deux salles de bain, wc",
        "villa {n} chambres garage wc bureau",
        "maison {n} chambres suite parentale avec salle de bain, wc",
    ]
    for _ in range(40):
        brief = rnd.choice(briefs).format(n=rnd.randint(1, 4))
        constraints = {"max_width_m": rnd.choice([10, 12, 14]), "max_depth_m": rnd.choice([9, 10, 12])}
        out = diffusion.generate(nlu.parse_brief(brief, constraints), image=False)["layout"]
        for room_id, neighbours in _wet_room_doors(out).items():
            assert len(neighbours) == 1, (brief, room_id, neighbours)


def test_gemini_prompt_pins_shapes_and_wet_room_doors():
    doc = pipeline.generate_plan("maison 2 chambres avec wc", {})["plan_document"]
    prompt = diffusion._flux_prompt(
        brief="maison", rooms=doc["rooms"], width=12, depth=10, layout_guided=True,
        walls=doc["walls"], openings=doc["openings"],
    )
    assert "exactly ONE door" in prompt
    assert "the WC at x=" in prompt and "has its only door on its" in prompt
