"""Étape A du chantier « partis » : mesurer la ressemblance des plans.

Deux rôles :

  1. vérifier que l'instrument (`app.layout_signature`) discrimine ce qu'il
     prétend discriminer, sur des plans construits à la main ;
  2. fixer l'**état de départ** du moteur actuel, sur le corpus sous graine de
     `test_layout_invariants` — le chiffre que les étapes suivantes devront
     battre.

Les tests « état de départ » décrivent un défaut, pas un objectif : ils
échoueront volontairement quand un nouveau moteur aura résolu ce qu'ils
constatent, et il faudra alors les inverser en connaissance de cause. Ils
appellent `pack_house` avec son comportement par défaut, qui doit rester le
gabarit classique tant que le drapeau de variantes n'est pas activé.

Pour afficher le tableau :
    python tests/test_layout_diversity.py
"""
from __future__ import annotations

import itertools
import statistics
from typing import Any

from app.layout_opt import pack_house
from app.layout_signature import (
    circulation_share,
    follows_classic_template,
    topology_distance,
    topology_signature,
    zone_code,
)
from test_layout_invariants import CORPUS, GENERATE


def _r(rid: str, typ: str, x0: float, y0: float, x1: float, y1: float) -> dict[str, Any]:
    return {
        "id": rid,
        "type": typ,
        "polygon": [
            {"x": x0, "y": y0}, {"x": x1, "y": y0},
            {"x": x1, "y": y1}, {"x": x0, "y": y1},
        ],
    }


# Gabarit actuel, écrit à la main : chambres au nord, couloir, jour au sud.
CLASSIC = [
    _r("b1", "bedroom", 0, 0, 6, 4),
    _r("b2", "bedroom", 6, 0, 12, 4),
    _r("h", "hallway", 0, 4, 12, 5.2),
    _r("l", "living", 0, 5.2, 7, 10),
    _r("k", "kitchen", 7, 5.2, 12, 10),
]

# Couloir central desservant deux rangées de chambres, séjour à l'est.
CENTRAL_HALL = [
    _r("b1", "bedroom", 0, 0, 4, 4),
    _r("b2", "bedroom", 4, 0, 8, 4),
    _r("h", "hallway", 0, 4, 8, 5.2),
    _r("b3", "bedroom", 0, 5.2, 4, 10),
    _r("b4", "bedroom", 4, 5.2, 8, 10),
    _r("l", "living", 8, 0, 12, 6),
    _r("k", "kitchen", 8, 6, 12, 10),
]

# Le gabarit actuel pivoté d'un quart de tour : couloir nord-sud.
TRANSPOSED = [
    _r("b1", "bedroom", 0, 0, 4, 5),
    _r("b2", "bedroom", 0, 5, 4, 10),
    _r("h", "hallway", 4, 0, 5.2, 10),
    _r("l", "living", 5.2, 0, 12, 6),
    _r("k", "kitchen", 5.2, 6, 12, 10),
]


# --- L'instrument discrimine ce qu'il prétend discriminer ------------------

def test_zone_code_names_the_classic_arrangement():
    assert zone_code(CLASSIC, 12, 10) == "night:N|day:S|hall:H|garage:-"


def test_zone_code_distinguishes_other_arrangements():
    codes = {
        zone_code(CLASSIC, 12, 10),
        zone_code(CENTRAL_HALL, 12, 10),
        zone_code(TRANSPOSED, 12, 10),
    }
    assert len(codes) == 3


def test_classic_template_test_is_relational():
    assert follows_classic_template(CLASSIC)
    assert not follows_classic_template(CENTRAL_HALL)  # deux rangées de chambres
    assert not follows_classic_template(TRANSPOSED)    # couloir nord-sud


def test_classic_template_needs_all_three_zones():
    assert not follows_classic_template([])
    assert not follows_classic_template([r for r in CLASSIC if r["type"] != "hallway"])
    assert not follows_classic_template([r for r in CLASSIC if r["type"] != "bedroom"])


def test_classic_template_survives_a_garage_shifting_the_centroid():
    """Un garage à l'est décale le centre de gravité de la nuit vers l'ouest.

    Une règle fondée sur la position absolue des zones classait ce plan comme
    non classique ; la règle relationnelle non.
    """
    with_garage = [
        _r("b1", "bedroom", 0, 0, 4, 4),
        _r("b2", "bedroom", 4, 0, 8, 4),
        _r("h", "hallway", 0, 4, 8, 5.2),
        _r("l", "living", 0, 5.2, 5, 10),
        _r("k", "kitchen", 5, 5.2, 8, 10),
        _r("g", "garage", 8, 0, 12, 10),
    ]
    assert follows_classic_template(with_garage)


def test_hall_is_the_most_elongated_hallway_not_the_largest():
    """Un tronçon de couloir plus vaste que le couloir ne doit pas le supplanter."""
    rooms = [
        _r("h", "hallway", 0, 4, 7.6, 5.4),      # 7,6 x 1,4  = 10,6 m2, allongé
        _r("h_s", "hallway", 7.6, 5.4, 10.8, 11.3),  # 3,2 x 5,9 = 18,9 m2, plus grand
    ]
    assert zone_code(rooms, 10.8, 11.7).split("|")[2] == "hall:H"


def test_circulation_share_is_hallway_area_over_total():
    assert abs(circulation_share(CLASSIC) - 0.12) < 1e-9
    assert circulation_share([]) == 0.0


def test_signature_says_who_touches_whom():
    sig = topology_signature(CLASSIC, 12, 10)
    assert ("adj", "bedroom", "hallway") in sig
    assert ("adj", "hallway", "living") in sig
    # Le couloir sépare les chambres du séjour : c'est la règle sanitaire.
    assert ("adj", "bedroom", "living") not in sig
    assert ("facade", "bedroom", "N") in sig
    assert ("facade", "living", "S") in sig


def test_topology_distance_is_a_bounded_symmetric_distance():
    a = topology_signature(CLASSIC, 12, 10)
    b = topology_signature(CENTRAL_HALL, 12, 10)
    assert topology_distance(a, a) == 0.0
    assert topology_distance(frozenset(), frozenset()) == 0.0
    assert 0.0 < topology_distance(a, b) <= 1.0
    assert topology_distance(a, b) == topology_distance(b, a)
    assert topology_distance(a, frozenset({("adj", "x", "y")})) == 1.0


def test_topology_distance_is_exactly_jaccard_on_unequal_sets():
    """Tailles inégales : c'est là qu'une distance mal normalisée devient asymétrique.

    Les deux plans des tests précédents ont par hasard le même nombre de faits ;
    une formule normalisée par |A| au lieu de |A ∪ B| y passait inaperçue.
    """
    big = frozenset({("adj", "a", "b"), ("adj", "a", "c"), ("adj", "b", "c")})
    small = frozenset({("adj", "a", "b")})
    assert abs(topology_distance(big, small) - (1 - 1 / 3)) < 1e-12
    assert topology_distance(big, small) == topology_distance(small, big)
    assert topology_distance(small, small) == 0.0


def test_distance_ignores_dimensions():
    """Étirer un plan ne change pas sa topologie."""
    stretched = [
        {**r, "polygon": [{"x": p["x"] * 1.5, "y": p["y"]} for p in r["polygon"]]}
        for r in CLASSIC
    ]
    a = topology_signature(CLASSIC, 12, 10)
    b = topology_signature(stretched, 18, 10)
    assert topology_distance(a, b) == 0.0


# --- État de départ du moteur actuel ---------------------------------------
# Ces tests décrivent un DÉFAUT. Ils sont censés échouer le jour où un nouveau
# moteur le corrige ; il faut alors les inverser, pas les assouplir.

def _packed(program: dict[str, Any], width: float | None = None, depth: float | None = None):
    w = width if width is not None else program["width"]
    d = depth if depth is not None else program["depth"]
    rooms = pack_house([dict(r) for r in program["rooms"]], w, d, **GENERATE)
    return rooms, w, d


def _with_bedroom_and_hall(program: dict[str, Any]) -> bool:
    return any(r["type"] == "bedroom" for r in program["rooms"])


def template_share() -> tuple[int, int]:
    """(plans qui suivent le gabarit, plans concernés) sur le corpus ajusté."""
    followed = concerned = 0
    for program in CORPUS:
        if not _with_bedroom_and_hall(program):
            continue
        rooms, _, _ = _packed(program)
        if not any(r["type"] == "hallway" for r in rooms):
            continue
        concerned += 1
        followed += follows_classic_template(rooms)
    return followed, concerned


def test_baseline_almost_every_plan_follows_one_template():
    """L'impression « toutes les maisons se ressemblent », chiffrée : ~90 %."""
    followed, concerned = template_share()
    assert concerned >= 150
    assert followed / concerned >= 0.85, f"{followed}/{concerned}"


def _stub(room: dict[str, Any]) -> bool:
    return room["type"] == "hallway" and str(room["id"]).endswith(("_n", "_s"))


def _area_of(room: dict[str, Any]) -> float:
    xs = [p["x"] for p in room["polygon"]]
    ys = [p["y"] for p in room["polygon"]]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def stub_statistics() -> tuple[int, list[float]]:
    """(nombre de plans à tronçons, part de surface des tronçons dans ces plans)."""
    shares: list[float] = []
    for program in CORPUS:
        rooms, _, _ = _packed(program)
        total = sum(_area_of(r) for r in rooms)
        stubs = sum(_area_of(r) for r in rooms if _stub(r))
        if stubs > 0:
            shares.append(stubs / total)
    return len(shares), shares


def test_baseline_corridor_stubs_take_a_fifth_of_the_floor():
    """Les tronçons « couloir » des coins de la bande humide : surface perdue.

    Ils servent à tenir les WC à distance de la cuisine et des chambres, mais
    occupent en médiane près d'un cinquième du plan quand ils existent.
    """
    n_plans, shares = stub_statistics()
    assert n_plans >= 100, n_plans
    assert statistics.median(shares) >= 0.15, statistics.median(shares)


def test_baseline_real_hallway_is_within_the_usual_range():
    """Contrepoint : la bande de couloir elle-même est dans la norme (8 à 12 %)."""
    shares = []
    for program in CORPUS:
        rooms, _, _ = _packed(program)
        total = sum(_area_of(r) for r in rooms)
        band = sum(_area_of(r) for r in rooms if r["type"] == "hallway" and not _stub(r))
        if band > 0:
            shares.append(band / total)
    assert 0.07 <= statistics.median(shares) <= 0.13, statistics.median(shares)


def adaptation_distance() -> float:
    """Distance topologique moyenne d'un même programme sur trois formes de parcelle.

    Même aire, trois allongements : la forme d'origine, la forme transposée et
    un carré. Un moteur qui s'adapte à la parcelle change de topologie quand la
    parcelle change de forme ; le gabarit actuel ne fait que l'étirer.
    """
    distances: list[float] = []
    for program in CORPUS:
        w, d = program["width"], program["depth"]
        side = round((w * d) ** 0.5, 1)
        sigs = []
        for ww, dd in ((w, d), (d, w), (side, side)):
            rooms, _, _ = _packed(program, ww, dd)
            sigs.append(topology_signature(rooms, ww, dd))
        distances.extend(topology_distance(a, b) for a, b in itertools.combinations(sigs, 2))
    return sum(distances) / len(distances)


def test_baseline_topology_barely_adapts_to_the_plot_shape():
    assert adaptation_distance() < 0.10


def _report() -> str:
    followed, concerned = template_share()
    n_stub, shares = stub_statistics()
    lines = [
        "",
        f"Corpus ajusté : {len(CORPUS)} programmes, graines 0..{len(CORPUS) - 1}",
        "",
        "--- état de départ du moteur actuel",
        f"  gabarit unique (chambres N, couloir H, jour S) : {followed}/{concerned} = {100 * followed / concerned:.1f} %",
        f"  plans à tronçons de couloir                    : {n_stub}/{len(CORPUS)}",
        f"  part de surface des tronçons (médiane)         : {100 * statistics.median(shares):.1f} %",
        f"  distance topologique selon la forme de parcelle: {adaptation_distance():.3f}  (0 = identique)",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(_report())
