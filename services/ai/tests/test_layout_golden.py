"""Golden master du gabarit classique : la sortie actuelle de `pack_house`, au bit près.

Le chantier « partis » ajoute des façons de pavoir un plan. Une seule promesse
doit tenir pendant tout le chantier : **le gabarit actuel reste identique**.
Ce test l'épingle. Pour chacun des programmes des deux corpus sous graine, on
compare l'empreinte exacte (identifiant, type, nom, polygone à 1 cm) du pavage à
celle enregistrée dans `golden/pack_house_classic.json`.

Trois séries sont épinglées, celles qui passent réellement en production :
  * `generate` — `pack_house` à l'étage d'implantation (côté minimal 1,6 m) ;
  * `stress`   — idem sur les programmes mal posés ;
  * `adapt`    — `optimize_rooms` à l'étage d'adaptation (côté minimal 2,0 m).

Si ce test échoue, le comportement du gabarit classique a changé. C'est parfois
voulu (une correction du moteur) : dans ce cas on régénère explicitement,

    python tests/test_layout_golden.py --write

et le diff du fichier JSON, relu, dit exactement quels plans ont bougé. On ne
l'assouplit jamais pour « faire passer » un changement non voulu.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from app.layout_opt import optimize_rooms, pack_house
from test_layout_invariants import ADAPT, CORPUS, CORPUS_STRESS, GENERATE

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "pack_house_classic.json"


def canonical_hash(rooms: list[dict[str, Any]]) -> str:
    """Empreinte d'un pavage : indépendante de l'ordre des pièces, sensible à 1 cm."""
    canon = []
    for room in sorted(rooms, key=lambda r: str(r.get("id"))):
        poly = [(round(float(p["x"]), 2), round(float(p["y"]), 2)) for p in room["polygon"]]
        canon.append([
            str(room.get("id")),
            str(room.get("type")),
            str(room.get("name")),
            bool(room.get("ensuite")),
            poly,
        ])
    blob = json.dumps(canon, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _pack(program: dict[str, Any], *, via_optimize: bool, grid: float, min_side: float):
    rooms = [dict(r) for r in program["rooms"]]
    if via_optimize:
        return optimize_rooms(rooms, program["width"], program["depth"], None, grid=grid, min_side=min_side)
    return pack_house(rooms, program["width"], program["depth"], grid=grid, min_side=min_side)


def compute() -> dict[str, list[str]]:
    gen = {k: v for k, v in GENERATE.items() if k in ("grid", "min_side")}
    ada = {k: v for k, v in ADAPT.items() if k in ("grid", "min_side")}
    return {
        "generate": [canonical_hash(_pack(p, via_optimize=False, **gen)) for p in CORPUS],
        "stress": [canonical_hash(_pack(p, via_optimize=False, **gen)) for p in CORPUS_STRESS],
        "adapt": [canonical_hash(_pack(p, via_optimize=True, **ada)) for p in CORPUS],
    }


def _load() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _diff(expected: list[str], got: list[str]) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(expected, got, strict=True)) if a != b]


def test_golden_file_matches_the_corpus_sizes():
    golden = _load()
    assert len(golden["generate"]) == len(CORPUS)
    assert len(golden["stress"]) == len(CORPUS_STRESS)
    assert len(golden["adapt"]) == len(CORPUS)


def test_classic_layout_is_bit_identical_at_generation():
    expected = _load()["generate"]
    moved = _diff(expected, compute()["generate"])
    assert not moved, f"{len(moved)} plan(s) ont changé, programmes {moved[:8]}"


def test_classic_layout_is_bit_identical_on_ill_posed_briefs():
    expected = _load()["stress"]
    moved = _diff(expected, compute()["stress"])
    assert not moved, f"{len(moved)} plan(s) ont changé, programmes {moved[:8]}"


def test_classic_layout_is_bit_identical_at_adaptation():
    expected = _load()["adapt"]
    moved = _diff(expected, compute()["adapt"])
    assert not moved, f"{len(moved)} plan(s) ont changé, programmes {moved[:8]}"


def test_hash_is_sensitive_to_one_centimetre_and_blind_to_room_order():
    rooms = [
        {"id": "a", "type": "living", "name": "S", "polygon": [{"x": 0, "y": 0}, {"x": 5, "y": 0}, {"x": 5, "y": 4}, {"x": 0, "y": 4}]},
        {"id": "b", "type": "kitchen", "name": "C", "polygon": [{"x": 5, "y": 0}, {"x": 8, "y": 0}, {"x": 8, "y": 4}, {"x": 5, "y": 4}]},
    ]
    base = canonical_hash(rooms)
    assert canonical_hash(list(reversed(rooms))) == base
    moved = json.loads(json.dumps(rooms))
    moved[0]["polygon"][1]["x"] = 5.01
    assert canonical_hash(moved) != base
    sub_centimetre = json.loads(json.dumps(rooms))
    sub_centimetre[0]["polygon"][1]["x"] = 5.004
    assert canonical_hash(sub_centimetre) == base


def write() -> None:
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "note": "Empreintes du gabarit classique. Régénérer avec: python tests/test_layout_golden.py --write",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        **compute(),
    }
    GOLDEN_PATH.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    n = sum(len(v) for k, v in payload.items() if isinstance(v, list))
    print(f"{n} empreintes écrites dans {GOLDEN_PATH}")


if __name__ == "__main__":
    if "--write" in sys.argv:
        write()
    else:
        print("Ajouter --write pour (ré)générer le fichier golden.")
