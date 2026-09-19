"""Étape C1 du chantier « partis » : les règles de distribution, déclarées une fois.

`sanitary_violations` interprète désormais `layout_rules.RULES` au lieu de porter
les règles en dur. Ce refactoring ne doit changer **aucun résultat**, pas même
l'ordre ni la multiplicité des écarts (`pack_house` compare `len(issues)` entre
deux essais).

La preuve est différentielle : l'implémentation d'origine est conservée ici,
verbatim, comme oracle, et comparée à la nouvelle sur les plans produits par le
moteur (600 plans) et sur des plans aléatoires (3 000) qui couvrent des
situations que le moteur ne produit jamais (plusieurs couloirs, aucun couloir,
pièces empilées n'importe comment).
"""
from __future__ import annotations

import random
from typing import Any

import pytest

from app import compliance, layout_opt, layout_rules
from app.layout_opt import optimize_rooms, pack_house, sanitary_violations, share_edge
from test_layout_invariants import ADAPT, CORPUS, CORPUS_STRESS, GENERATE


def _legacy_sanitary_violations(rooms: list[dict[str, Any]]) -> list[str]:
    """ORACLE : `sanitary_violations` d'avant la déclaration des règles, verbatim."""
    issues: list[str] = []
    beds = [r for r in rooms if r.get("type") == "bedroom"]
    halls = [r for r in rooms if r.get("type") == "hallway"]
    kitchens = [r for r in rooms if r.get("type") in {"kitchen", "dining"}]
    baths = [r for r in rooms if r.get("type") == "bathroom"]
    wcs = [r for r in rooms if r.get("type") == "wc"]
    livings = [r for r in rooms if r.get("type") == "living"]
    for wet in wcs:
        for food in kitchens:
            if share_edge(wet, food):
                issues.append("wc_kitchen")
                break
    for bath in baths:
        for food in kitchens:
            if share_edge(bath, food):
                issues.append("kitchen_bath")
                break
    for bed in beds:
        for living in livings:
            if share_edge(bed, living):
                issues.append("bedroom_living")
                break
    if halls:
        for bed in beds:
            if not any(share_edge(bed, hall) for hall in halls):
                issues.append("bedroom_hall")
                break
        for wet in wcs:
            if not any(share_edge(wet, hall) for hall in halls):
                issues.append("wc_hall")
                break
    for wet in wcs:
        if any(share_edge(wet, bed) for bed in beds):
            issues.append("wc_bedroom")
            break
    return issues


# --- Plans aléatoires -------------------------------------------------------

_TYPES = ["bedroom", "bedroom", "wc", "wc", "kitchen", "dining", "bathroom", "bathroom",
          "living", "living", "hallway", "hallway", "laundry", "storage", "office", "garage"]


def _random_layout(rng: random.Random) -> list[dict[str, Any]]:
    """Découpe guillotine aléatoire d'un rectangle, types tirés au hasard.

    Volontairement dépourvu de sens architectural : il doit exercer les règles,
    y compris les cas dégénérés (aucun couloir, dix couloirs, tout en WC).
    """
    width, depth = rng.uniform(5, 18), rng.uniform(5, 18)
    n = rng.randint(2, 11)
    rects = [(0.0, 0.0, width, depth)]
    while len(rects) < n:
        i = max(range(len(rects)), key=lambda k: (rects[k][2] - rects[k][0]) * (rects[k][3] - rects[k][1]))
        x0, y0, x1, y1 = rects.pop(i)
        f = rng.uniform(0.3, 0.7)
        if rng.random() < 0.5 and (x1 - x0) > 1.0:
            m = x0 + (x1 - x0) * f
            rects += [(x0, y0, m, y1), (m, y0, x1, y1)]
        else:
            m = y0 + (y1 - y0) * f
            rects += [(x0, y0, x1, m), (x0, m, x1, y1)]
    rng.shuffle(rects)
    return [
        {
            "id": f"r{k}",
            "type": rng.choice(_TYPES),
            "polygon": [{"x": round(a, 2), "y": round(b, 2)}, {"x": round(c, 2), "y": round(b, 2)},
                        {"x": round(c, 2), "y": round(d, 2)}, {"x": round(a, 2), "y": round(d, 2)}],
        }
        for k, (a, b, c, d) in enumerate(rects)
    ]


RANDOM_LAYOUTS = [_random_layout(random.Random(50_000 + s)) for s in range(3000)]


# --- Équivalence avec l'implémentation d'origine ---------------------------

def _engine_plans() -> list[list[dict[str, Any]]]:
    gen = {k: v for k, v in GENERATE.items() if k in ("grid", "min_side")}
    ada = {k: v for k, v in ADAPT.items() if k in ("grid", "min_side")}
    plans = []
    for p in CORPUS:
        plans.append(pack_house([dict(r) for r in p["rooms"]], p["width"], p["depth"], **gen))
        plans.append(optimize_rooms([dict(r) for r in p["rooms"]], p["width"], p["depth"], None, **ada))
    for p in CORPUS_STRESS:
        plans.append(pack_house([dict(r) for r in p["rooms"]], p["width"], p["depth"], **gen))
    return plans


def test_same_issues_as_the_original_on_engine_plans():
    plans = _engine_plans()
    assert len(plans) == 600
    for i, rooms in enumerate(plans):
        assert sanitary_violations(rooms) == _legacy_sanitary_violations(rooms), f"plan {i}"


def test_same_issues_as_the_original_on_random_layouts():
    for i, rooms in enumerate(RANDOM_LAYOUTS):
        assert sanitary_violations(rooms) == _legacy_sanitary_violations(rooms), f"plan aléatoire {i}"


def test_random_layouts_actually_exercise_every_rule():
    """Sans cela, l'équivalence pourrait être vraie parce que rien n'est jamais déclenché."""
    seen: set[str] = set()
    multi = False
    for rooms in RANDOM_LAYOUTS:
        issues = sanitary_violations(rooms)
        seen |= set(issues)
        multi = multi or any(issues.count(name) > 1 for name in set(issues))
    assert seen == {r.name for r in layout_rules.RULES}, seen
    assert multi, "aucun plan n'a produit deux fois le même écart : le comptage par pièce n'est pas éprouvé"


def test_random_layouts_include_degenerate_cases():
    counts = [sum(1 for r in rooms if r["type"] == "hallway") for rooms in RANDOM_LAYOUTS]
    assert 0 in counts and max(counts) >= 3


# --- Les déclarations elles-mêmes -------------------------------------------

def test_rules_are_emitted_in_the_original_order():
    assert [r.name for r in layout_rules.RULES] == [
        "wc_kitchen", "kitchen_bath", "bedroom_living", "bedroom_hall", "wc_hall", "wc_bedroom",
    ]


def test_counting_regime_matches_the_original():
    per_room = {r.name: r.per_room for r in layout_rules.RULES if isinstance(r, layout_rules.ForbiddenPair)}
    assert per_room == {"wc_kitchen": True, "kitchen_bath": True, "bedroom_living": True, "wc_bedroom": False}


def test_generator_constants_are_derived_from_the_declarations():
    assert layout_opt._FORBIDDEN_ADJACENCY == layout_rules.forbidden_pairs()
    assert layout_opt._NEEDS_CIRCULATION == layout_rules.types_needing_hall() == {"bedroom", "wc"}


def test_habitable_and_wet_sets_are_not_duplicated_out_of_sync():
    assert layout_opt.HABITABLE == set(layout_rules.HABITABLE_TYPES)
    assert layout_opt.WET == set(layout_rules.WET_TYPES)
    # `compliance` garde sa propre copie : ce test détecte toute dérive.
    assert compliance.HABITABLE == set(layout_rules.HABITABLE_TYPES)


def test_forbidden_count_uses_the_declared_pairs():
    def room(rid, typ, x0, y0, x1, y1):
        return {"id": rid, "type": typ, "polygon": [
            {"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]}

    apart = [room("w", "wc", 0, 0, 2, 3), room("k", "kitchen", 5, 0, 9, 3)]
    touching = [room("w", "wc", 0, 0, 2, 3), room("k", "kitchen", 2, 0, 6, 3)]
    assert layout_opt._forbidden_count(apart) == 0
    assert layout_opt._forbidden_count(touching) == 1
    # Chaque paire déclarée est comptée.
    for left, right in layout_rules.forbidden_pairs():
        a, b = sorted(left)[0], sorted(right)[0]
        assert layout_opt._forbidden_count([room("a", a, 0, 0, 3, 3), room("b", b, 3, 0, 6, 3)]) == 1, (a, b)


@pytest.mark.parametrize("name", ["wc_kitchen", "kitchen_bath", "bedroom_living", "bedroom_hall", "wc_hall", "wc_bedroom"])
def test_every_issue_name_is_one_that_compliance_knows(name):
    """Le contrat de noms : `compliance` les teste par appartenance."""
    src = open(compliance.__file__, encoding="utf-8").read()
    assert f'"{name}"' in src


# --- Conventions de façade : dérive avec `default_openings` -------------------------
# Ces tests décrivent le comportement ACTUEL de `diffusion.default_openings`. S'ils
# échouent, c'est que `default_openings` a été généralisé : il faut alors assouplir
# `layout_rules.ENTRANCE_TYPES` / `MIN_GARAGE_CONTACT`, pas les tests.

def _door_on(walls, openings, wall_id):
    return next((o for o in openings if o["wall_id"] == wall_id and o["type"] == "door"), None)


def _rect(rid, typ, x0, y0, x1, y1):
    return {"id": rid, "type": typ, "polygon": [
        {"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]}


def _open(rooms, w, d):
    from app.diffusion import default_openings, perimeter_and_internal_walls

    walls = perimeter_and_internal_walls(rooms, w, d)
    return walls, default_openings(walls, w, d, rooms)


@pytest.mark.parametrize("w,d", [(10, 8), (12, 9.3), (14, 11), (9, 6.5), (16, 12.7)])
def test_the_historic_garage_door_is_kept_when_the_garage_holds_the_east_wall(w, d):
    """Compatibilité : un garage qui tient la façade est garde EXACTEMENT sa porte d'avant.

    C'est ce qui rend la généralisation invisible pour le gabarit classique.
    """
    rooms = [_rect("g", "garage", w - 4, 0, w, d), _rect("l", "living", 0, 0, w - 4, d)]
    walls, ops = _open(rooms, w, d)
    door = _door_on(walls, ops, "w_outer_2")
    assert door is not None
    assert abs(door["offset_m"] - max(0.4, min(d - 2.6, d * 0.55))) < 1e-9
    assert abs(door["width_m"] - min(2.4, d * 0.45)) < 1e-9


def test_the_garage_door_opens_on_the_garages_own_wall():
    """La raison d'être de la généralisation : un garage à l'ouest a sa porte à l'ouest."""
    west = [_rect("g", "garage", 0, 0, 4, 10), _rect("l", "living", 4, 0, 10, 10)]
    walls, ops = _open(west, 10, 10)
    door = _door_on(walls, ops, "w_outer_4")
    assert door is not None and door["width_m"] == layout_rules.GARAGE_DOOR_WIDTH
    north = [_rect("g", "garage", 0, 0, 10, 4), _rect("l", "living", 0, 4, 10, 10)]
    walls, ops = _open(north, 10, 10)
    assert _door_on(walls, ops, "w_outer_1") is not None


def test_an_east_garage_off_the_historic_span_gets_a_door_centred_on_its_facade():
    """Garage à l'angle nord-est d'un mur de 12 m : l'ancien emplacement (y 6,6 à 9,2) est hors garage."""
    rooms = [_rect("g", "garage", 6, 0, 10, 4), _rect("l", "living", 0, 0, 6, 12), _rect("k", "kitchen", 6, 4, 10, 12)]
    walls, ops = _open(rooms, 10, 12)
    door = _door_on(walls, ops, "w_outer_2")
    assert door is not None and abs(door["offset_m"] - 0.8) < 1e-9       # (4 - 2,4) / 2


def test_a_corner_garage_uses_its_longest_facade():
    tall = [_rect("g", "garage", 7, 0, 10, 8), _rect("l", "living", 0, 0, 7, 10), _rect("k", "kitchen", 7, 8, 10, 10)]
    walls, ops = _open(tall, 10, 10)
    assert _door_on(walls, ops, "w_outer_2") is not None and _door_on(walls, ops, "w_outer_1") is None
    wide = [_rect("g", "garage", 0, 0, 8, 3.2), _rect("l", "living", 0, 3.2, 10, 10), _rect("k", "kitchen", 8, 0, 10, 3.2)]
    walls, ops = _open(wide, 10, 10)
    assert _door_on(walls, ops, "w_outer_1") is not None and _door_on(walls, ops, "w_outer_4") is None


def test_equal_facades_prefer_east_then_west_then_north_then_south():
    """À contact égal, l'ordre de préférence est celui de la convention historique : est d'abord."""
    ne = [_rect("g", "garage", 6, 0, 10, 4), _rect("l", "living", 0, 0, 6, 10), _rect("k", "kitchen", 6, 4, 10, 10)]
    walls, ops = _open(ne, 10, 10)
    assert _door_on(walls, ops, "w_outer_2") is not None and _door_on(walls, ops, "w_outer_1") is None
    nw = [_rect("g", "garage", 0, 0, 4, 4), _rect("l", "living", 4, 0, 10, 10), _rect("k", "kitchen", 0, 4, 4, 10)]
    walls, ops = _open(nw, 10, 10)
    assert _door_on(walls, ops, "w_outer_4") is not None and _door_on(walls, ops, "w_outer_1") is None


def test_a_garage_with_a_short_facade_gets_no_exterior_door():
    from app.diffusion import _served_rooms

    rooms = [_rect("g", "garage", 0, 0, 2.5, 2.5), _rect("l", "living", 0, 2.5, 10, 10), _rect("k", "kitchen", 2.5, 0, 10, 2.5)]
    walls, ops = _open(rooms, 10, 10)
    by_id = {w["id"]: w for w in walls}
    exterior = [o for o in ops if o["type"] == "door" and o["wall_id"].startswith("w_outer")]
    assert not any(any(r["type"] == "garage" for r in _served_rooms(by_id[o["wall_id"]], o, rooms)) for o in exterior)


def test_an_inner_garage_gets_no_exterior_door():
    from app.diffusion import _served_rooms

    rooms = [_rect("g", "garage", 3, 3, 7, 7), _rect("a", "storage", 0, 0, 10, 3), _rect("b", "storage", 0, 7, 10, 10),
             _rect("c", "storage", 0, 3, 3, 7), _rect("e", "storage", 7, 3, 10, 7)]
    walls, ops = _open(rooms, 10, 10)
    by_id = {w["id"]: w for w in walls}
    exterior = [o for o in ops if o["type"] == "door" and o["wall_id"].startswith("w_outer")]
    assert not any(any(r["type"] == "garage" for r in _served_rooms(by_id[o["wall_id"]], o, rooms)) for o in exterior)


def test_the_garage_door_avoids_the_entrance_on_the_south_wall():
    from app.diffusion import _garage_door, perimeter_and_internal_walls

    rooms = [_rect("g", "garage", 6, 8, 10, 10), _rect("l", "living", 0, 0, 10, 8)]
    walls = perimeter_and_internal_walls(rooms, 10, 10)
    by_id = {w["id"]: w for w in walls}
    quad = (by_id["w_outer_2"], by_id["w_outer_4"], by_id["w_outer_1"], by_id["w_outer_3"])
    # Le garage ne touche le mur est que sur 2 m : seule la façade sud (4 m) convient.
    assert _garage_door(quad, rooms, None)[0]["id"] == "w_outer_3"
    assert _garage_door(quad, rooms, (0.8, 0.9)) is None                    # l'entrée y est déjà


def test_the_declared_garage_constants_match_diffusion():
    from app import diffusion

    assert diffusion._GARAGE_DOOR_WIDTH == layout_rules.GARAGE_DOOR_WIDTH
    assert diffusion._MIN_GARAGE_CONTACT == layout_rules.MIN_GARAGE_CONTACT


def test_the_entrance_is_on_the_south_wall_whatever_the_plan():
    from app.diffusion import default_openings, perimeter_and_internal_walls

    rooms = [_rect("l", "living", 0, 0, 10, 4), _rect("b", "bedroom", 0, 4, 10, 10)]      # chambre au sud
    walls = perimeter_and_internal_walls(rooms, 10, 10)
    ops = default_openings(walls, 10, 10, rooms)
    door = _door_on(walls, ops, "w_outer_3")
    assert door is not None
    # Elle est bien devant la chambre : c'est ce que `layout_partis` interdit.
    assert door["offset_m"] + door["width_m"] / 2 < 10


def test_entrance_types_are_the_head_of_the_entrance_preference_order():
    from app.diffusion import _ENTRANCE_ORDER

    assert tuple(_ENTRANCE_ORDER[: len(layout_rules.ENTRANCE_TYPES)]) == layout_rules.ENTRANCE_TYPES
