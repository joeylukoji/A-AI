"""Golden master des ouvertures : `default_openings` sur les plans du gabarit classique.

Généraliser la porte de garage (sur le mur extérieur où le garage se trouve, et
non plus toujours à l'est) ne doit pas changer un seul plan classique : le
garage y occupe déjà la façade est. Ce test épingle, pour chaque programme des
deux corpus, l'empreinte des murs et des ouvertures que `default_openings`
produit aujourd'hui.

Trois séries : `generate` (parcelle telle quelle, min_side 1,6), `stress`
(programmes mal posés) et `adapt` (min_side 2,0, comme l'étape d'adaptation).
Chaque série ne garde que la sortie du gabarit ; les partis n'y figurent pas.

Si ce test échoue, une ouverture d'un plan classique a bougé. C'est parfois
voulu ; on régénère alors explicitement,

    python tests/test_openings_golden.py --write

et le diff du JSON dit quels plans ont changé. On ne l'assouplit jamais pour
faire passer un changement non voulu.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from app.diffusion import default_openings, perimeter_and_internal_walls
from app.layout_opt import optimize_rooms, pack_house
from test_layout_invariants import ADAPT, CORPUS, CORPUS_STRESS, GENERATE

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "openings_classic.json"


def openings_hash(walls: list[dict[str, Any]], openings: list[dict[str, Any]]) -> str:
    """Empreinte des murs et des ouvertures, à 1 mm, indépendante de l'ordre des ouvertures."""
    def pt(p: dict[str, Any]) -> list[float]:
        return [round(float(p["x"]), 3), round(float(p["y"]), 3)]

    wall_part = sorted([str(w["id"]), pt(w["a"]), pt(w["b"]), round(float(w.get("thickness_m") or 0), 3)] for w in walls)
    op_part = sorted(
        [str(o["wall_id"]), str(o["type"]), round(float(o["offset_m"]), 3), round(float(o["width_m"]), 3)]
        for o in openings
    )
    blob = json.dumps([wall_part, op_part], separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _plan_hash(program: dict[str, Any], *, via_optimize: bool, grid: float, min_side: float) -> str:
    rooms = [dict(r) for r in program["rooms"]]
    if via_optimize:
        packed = optimize_rooms(rooms, program["width"], program["depth"], None, grid=grid, min_side=min_side)
    else:
        packed = pack_house(rooms, program["width"], program["depth"], grid=grid, min_side=min_side)
    xs = [q["x"] for r in packed for q in r["polygon"]]
    ys = [q["y"] for r in packed for q in r["polygon"]]
    width, depth = max(xs), max(ys)            # emprise calée sur la grille, comme l'étape d'adaptation
    walls = perimeter_and_internal_walls(packed, width, depth)
    return openings_hash(walls, default_openings(walls, width, depth, packed))


def compute() -> dict[str, list[str]]:
    gen = {k: v for k, v in GENERATE.items() if k in ("grid", "min_side")}
    ada = {k: v for k, v in ADAPT.items() if k in ("grid", "min_side")}
    return {
        "generate": [_plan_hash(p, via_optimize=False, **gen) for p in CORPUS],
        "stress": [_plan_hash(p, via_optimize=False, **gen) for p in CORPUS_STRESS],
        "adapt": [_plan_hash(p, via_optimize=True, **ada) for p in CORPUS],
    }


def _load() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _moved(expected: list[str], got: list[str]) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(expected, got, strict=True)) if a != b]


def test_golden_file_matches_the_corpus_sizes():
    golden = _load()
    assert len(golden["generate"]) == len(CORPUS)
    assert len(golden["stress"]) == len(CORPUS_STRESS)
    assert len(golden["adapt"]) == len(CORPUS)


def test_classic_openings_are_bit_identical_at_generation():
    moved = _moved(_load()["generate"], compute()["generate"])
    assert not moved, f"{len(moved)} plan(s) ont changé, programmes {moved[:8]}"


def test_classic_openings_are_bit_identical_on_ill_posed_briefs():
    moved = _moved(_load()["stress"], compute()["stress"])
    assert not moved, f"{len(moved)} plan(s) ont changé, programmes {moved[:8]}"


def test_classic_openings_are_bit_identical_at_adaptation():
    moved = _moved(_load()["adapt"], compute()["adapt"])
    assert not moved, f"{len(moved)} plan(s) ont changé, programmes {moved[:8]}"


def test_the_golden_set_really_contains_garage_plans():
    """Sans plan à garage, le golden ne protégerait pas ce qu'on s'apprête à changer."""
    assert sum(1 for p in CORPUS if any(r["type"] == "garage" for r in p["rooms"])) >= 50


def test_hash_is_sensitive_to_a_door_moving_by_a_millimetre():
    walls = [{"id": "w1", "a": {"x": 0, "y": 0}, "b": {"x": 10, "y": 0}, "thickness_m": 0.2}]
    door = {"wall_id": "w1", "type": "door", "offset_m": 4.0, "width_m": 0.9}
    base = openings_hash(walls, [door])
    assert openings_hash(walls, [{**door, "offset_m": 4.001}]) != base
    assert openings_hash(walls, [{**door, "offset_m": 4.0004}]) == base


def write() -> None:
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "note": "Empreintes des ouvertures du gabarit classique. Régénérer avec: python tests/test_openings_golden.py --write",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        **compute(),
    }
    GOLDEN_PATH.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"{sum(len(v) for v in payload.values() if isinstance(v, list))} empreintes écrites")


if __name__ == "__main__":
    if "--write" in sys.argv:
        write()
    else:
        print("Ajouter --write pour (ré)générer le fichier golden.")
