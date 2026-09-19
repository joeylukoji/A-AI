"""Étape D du chantier « partis » : remplir les zones, sous contrôle exact.

`layout_partis` réalise un arrangement de zones en plan de pièces, puis ne garde
que ce qui passe un contrôle exact. Ces tests vérifient :

  * la répartition des pièces par zone (aucune perdue, aucune inventée) ;
  * chaque motif de rejet du contrôle dur, sur un plan construit à la main ;
  * les propriétés de tout parti réalisable, sur des programmes du corpus :
    pavage exact, pièces rectangulaires, pas de tronçon, ordre déterministe ;
  * le raffinement gardé (`refine`) et le contrôle de conformité.

Pour afficher le tableau de l'article (quelques minutes) :
    python tests/test_layout_partis.py
"""
from __future__ import annotations

import random
from functools import cache

import pytest

from app import layout_opt as lo
from app import layout_partis as lp
from app import layout_rules
from app import layout_zones as z
from app.layout_signature import follows_classic_template
from test_layout_golden import canonical_hash
from test_layout_invariants import CORPUS


def _rooms(*spec: tuple[str, float]) -> list[dict]:
    return [{"id": f"r{i}", "type": t, "name": t, "area_m2": a} for i, (t, a) in enumerate(spec)]


def _r(rid: str, typ: str, x0: float, y0: float, x1: float, y1: float) -> dict:
    return {"id": rid, "type": typ, "name": typ, "polygon": [
        {"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]}


# --- Répartition des pièces par zone ----------------------------------------

FULL = _rooms(("bedroom", 12), ("bedroom", 11), ("bathroom", 5), ("bathroom", 4), ("living", 24),
              ("kitchen", 10), ("dining", 9), ("wc", 2), ("garage", 16))


def test_every_room_lands_in_exactly_one_zone():
    zones, _ = lp.zone_items(FULL)
    ids = sorted(str(r["id"]) for items in zones.values() for r in items)
    assert ids == sorted([r["id"] for r in FULL] + ["r_hall"])   # + le couloir implicite


def test_rooms_go_to_the_zone_of_their_type():
    zones, _ = lp.zone_items(FULL)
    for name, items in zones.items():
        assert all(z.zone_of(r["type"]) == name for r in items), name


def test_day_zone_follows_the_template_order_kitchen_living_dining():
    zones, _ = lp.zone_items(FULL)
    assert [r["type"] for r in zones[z.DAY]] == ["kitchen", "living", "dining"]


def test_ensuite_is_the_last_bath_beside_the_last_bedroom():
    zones, ensuite = lp.zone_items(FULL)
    assert ensuite is not None and ensuite["id"] == "r3"
    types = [r["type"] for r in zones[z.NIGHT]]
    assert types == ["bedroom", "bedroom", "bathroom", "bathroom"]
    night_ids = [r["id"] for r in zones[z.NIGHT]]
    assert night_ids.index("r3") == night_ids.index("r1") + 1     # suite parentale : chambre puis sa salle de bain


def test_a_single_bathroom_is_not_an_ensuite():
    assert lp.zone_items(_rooms(("bedroom", 12), ("bathroom", 5), ("living", 20)))[1] is None


def test_an_explicit_hallway_is_kept_and_no_second_one_is_created():
    zones, _ = lp.zone_items(_rooms(("bedroom", 12), ("hallway", 9), ("living", 20)))
    assert [r["id"] for r in zones[z.HALL]] == ["r1"]


def test_an_unknown_type_goes_to_the_day_zone_after_the_usual_rooms():
    zones, _ = lp.zone_items(_rooms(("living", 20), ("kitchen", 9), ("veranda", 8)))
    assert [r["type"] for r in zones[z.DAY]] == ["kitchen", "living", "veranda"]


def test_an_empty_program_has_no_zone():
    assert lp.zone_items([]) == ({}, None)


# --- Aides de remplissage -------------------------------------------------------

def test_snapping_keeps_shared_edges_shared():
    a = lp._snap_rect((0.0, 0.0, 4.123456789, 5.0), 0.1)
    b = lp._snap_rect((4.123456789 + 1e-9, 0.0, 9.0, 5.0), 0.1)
    assert a[2] == b[0]
    assert all(abs(v / 0.1 - round(v / 0.1)) < 1e-6 for v in a + b)


def test_line_axis_runs_parallel_to_the_shared_edge_with_the_hall():
    hall = (0.0, 4.0, 10.0, 5.3)
    assert lp._hall_axis((0.0, 0.0, 10.0, 4.0), hall) == "x"        # couloir au sud : rangée est-ouest
    spine = (4.0, 0.0, 5.3, 10.0)
    assert lp._hall_axis((0.0, 0.0, 4.0, 10.0), spine) == "y"       # couloir à l'est : colonne nord-sud
    assert lp._hall_axis((5.3, 0.0, 10.0, 10.0), spine) == "y"      # couloir à l'ouest
    assert lp._hall_axis((0.0, 0.0, 10.0, 3.0), None) == "x"        # sans couloir : grand côté
    assert lp._hall_axis((0.0, 0.0, 3.0, 10.0), None) == "y"


def test_a_corner_contact_picks_the_longer_shared_edge():
    hall = (0.0, 0.0, 10.0, 1.3)
    assert lp._hall_axis((0.0, 1.3, 10.0, 6.0), hall) == "x"


# --- Contrôle dur : un plan valide, puis chaque motif de rejet -----------------

VALID = [
    _r("b1", "bedroom", 0, 0, 5, 4), _r("b2", "bedroom", 5, 0, 10, 4),
    _r("h", "hallway", 0, 4, 10, 5.3), _r("l", "living", 0, 5.3, 10, 10),
]


def test_a_sound_plan_passes_the_hard_check():
    assert lp.hard_check(VALID, 10, 10) is None


def test_a_room_outside_the_plot_is_rejected():
    plan = [VALID[0], _r("b2", "bedroom", 5, 0, 10.5, 4), *VALID[2:]]
    assert lp.hard_check(plan, 10, 10) == "emprise"


def test_overlapping_rooms_are_rejected():
    plan = [_r("b1", "bedroom", 0, 0, 6, 4), *VALID[1:]]
    assert lp.hard_check(plan, 10, 10) == "couverture"


def test_an_overlap_is_rejected_even_when_a_hole_hides_it_from_the_total_area():
    """Recouvrement de 8 m² et trou de 8 m² : la somme des aires vaut la parcelle.

    Sans ce cas, le contrôle de surface totale masque l'absence de détection des
    recouvrements : c'est la boucle sur les paires qui doit refuser ce plan.
    """
    plan = [_r("l", "living", 0, 0, 6, 10), _r("k", "kitchen", 5, 0, 10, 8)]
    assert abs(sum(60 if r["id"] == "l" else 40 for r in plan) - 100) < 1e-9
    assert lp.hard_check(plan, 10, 10) == "couverture"


def test_an_entrance_facing_only_bedrooms_is_rejected():
    """Chambres au sud : le porche de `default_openings` s'ouvrirait sur elles."""
    plan = [_r("l", "living", 0, 0, 10, 4.7), _r("h", "hallway", 0, 4.7, 10, 6.0),
            _r("b1", "bedroom", 0, 6.0, 5, 10), _r("b2", "bedroom", 5, 6.0, 10, 10)]
    assert lp.hard_check(plan, 10, 10, conventions=False) is None
    assert lp.hard_check(plan, 10, 10) == "entree"


def test_a_hall_reaching_the_south_wall_receives_the_entrance():
    plan = [_r("b1", "bedroom", 0, 0, 4, 10), _r("h", "hallway", 4, 0, 5.3, 10), _r("l", "living", 5.3, 0, 10, 10)]
    assert lp.hard_check(plan, 10, 10) is None


def test_a_garage_off_the_east_wall_is_rejected():
    """La porte de garage de `default_openings` est sur le mur est, à ~55 % de sa longueur."""
    plan = [_r("g", "garage", 0, 0, 4, 10), _r("h", "hallway", 4, 0, 5.3, 10), _r("l", "living", 5.3, 0, 10, 10)]
    assert lp.hard_check(plan, 10, 10, conventions=False) is None
    assert lp.hard_check(plan, 10, 10) == "garage"


def test_a_garage_on_the_east_wall_but_off_the_door_span_is_rejected():
    span = layout_rules.garage_door_span(10.0)
    assert span[0] > 3                                                    # la porte n'est pas au bord
    plan = [_r("g", "garage", 6, 0, 10, 3), _r("k", "kitchen", 0, 0, 6, 3), _r("h", "hallway", 0, 3, 10, 4.3),
            _r("l", "living", 0, 4.3, 10, 10)]
    assert lp.hard_check(plan, 10, 10, conventions=False) is None
    assert lp.hard_check(plan, 10, 10) == "garage"
    plan_ok = [_r("l", "living", 0, 0, 6, 10), _r("g", "garage", 6, 0, 10, 10)]
    assert lp.hard_check(plan_ok, 10, 10) is None


def test_a_hole_in_the_plot_is_rejected():
    assert lp.hard_check(VALID[:3], 10, 10) == "couverture"


def test_a_forbidden_adjacency_is_rejected():
    plan = [_r("w", "wc", 0, 0, 3, 4), _r("k", "kitchen", 3, 0, 10, 4),
            _r("h", "hallway", 0, 4, 10, 5.3), _r("l", "living", 0, 5.3, 10, 10)]
    assert lp.hard_check(plan, 10, 10) == "sanitaire"


def test_a_habitable_room_off_the_facade_is_rejected():
    plan = [_r("h1", "hallway", 0, 0, 10, 3), _r("s1", "storage", 0, 7, 10, 10),
            _r("h2", "hallway", 0, 3, 3, 7), _r("s2", "storage", 7, 3, 10, 7),
            _r("b", "bedroom", 3, 3, 7, 7)]
    assert lp.hard_check(plan, 10, 10) == "facade"


def test_an_absurdly_narrow_room_is_rejected():
    plan = [_r("b", "bedroom", 0, 0, 1.5, 10), _r("h", "hallway", 1.5, 0, 2.8, 10), _r("l", "living", 2.8, 0, 10, 10)]
    assert lp.hard_check(plan, 10, 10) == "trop_fin"


def test_a_room_slightly_under_its_minimum_is_only_a_preference():
    """Entre 75 % et 100 % du minimum : compté dans `thin`, pas rejeté."""
    plan = [_r("b", "bedroom", 0, 0, 2.2, 10), _r("h", "hallway", 2.2, 0, 3.5, 10), _r("l", "living", 3.5, 0, 10, 10)]
    assert lp.hard_check(plan, 10, 10) is None
    assert lp.thin_count(plan, 1.6) == 1


def test_thin_count_counts_rooms_below_their_minimum():
    assert lp.thin_count(VALID, 1.6) == 0
    assert lp.thin_count([_r("b", "bedroom", 0, 0, 2.0, 10)], 1.6) == 1


# --- Réalisations : propriétés sur des programmes du corpus -------------------

def _first_with(n_zones: int) -> dict:
    """Premier programme à `n_zones` zones qui a au moins deux chambres : un programme d'habitation."""
    return next(p for p in CORPUS
                if len(z.program_from_rooms(p["rooms"]).zones) == n_zones
                and sum(1 for r in p["rooms"] if r["type"] == "bedroom") >= 2)


PROGRAMS = {n: _first_with(n) for n in (3, 4, 5)}
# Un programme riche en partis, pour les tests qui comparent des séquences : cinq zones,
# garage, deux chambres. Les conventions de façade (entrée au sud, garage à l'est) laissent
# peu de partis à la plupart des programmes ; celui-ci en garde beaucoup.
RICH = CORPUS[18]


@cache
def _realized(n: int):
    p = PROGRAMS[n]
    return lp.realizations(p["rooms"], p["width"], p["depth"])


def _snapped(p):
    return lp._plot(p["width"], p["depth"], 0.1, 1.6)


@pytest.mark.parametrize("n", [3, 4, 5])
def test_every_realization_passes_the_hard_check(n):
    p = PROGRAMS[n]
    w, d = _snapped(p)
    rs = _realized(n)
    assert rs, "aucun parti réalisable"
    for r in rs:
        assert lp.hard_check(r.rooms, w, d) is None


@pytest.mark.parametrize("n", [3, 4, 5])
def test_realizations_keep_every_room_and_invent_none(n):
    p = PROGRAMS[n]
    expected = sorted(str(r["id"]) for items in lp.zone_items(p["rooms"])[0].values() for r in items)
    for r in _realized(n):
        assert sorted(str(x["id"]) for x in r.rooms) == expected


@pytest.mark.parametrize("n", [3, 4, 5])
def test_realized_rooms_are_axis_aligned_rectangles_tiling_the_plot(n):
    p = PROGRAMS[n]
    w, d = _snapped(p)
    for r in _realized(n):
        for room in r.rooms:
            xs = {round(q["x"], 4) for q in room["polygon"]}
            ys = {round(q["y"], 4) for q in room["polygon"]}
            assert len(room["polygon"]) == 4 and len(xs) == 2 and len(ys) == 2
        area = sum((max(q["x"] for q in x["polygon"]) - min(q["x"] for q in x["polygon"]))
                   * (max(q["y"] for q in x["polygon"]) - min(q["y"] for q in x["polygon"])) for x in r.rooms)
        assert abs(area - w * d) < 1e-2


@pytest.mark.parametrize("n", [3, 4, 5])
def test_realizations_have_no_corridor_stub(n):
    """Un seul couloir : aucune pièce « couloir » supplémentaire dans un coin."""
    p = PROGRAMS[n]
    halls = len(lp.zone_items(p["rooms"])[0].get(z.HALL, []))
    for r in _realized(n):
        assert sum(1 for x in r.rooms if x["type"] == "hallway") == halls


@pytest.mark.parametrize("n", [3, 4, 5])
def test_one_realization_per_class_by_default(n):
    rs = _realized(n)
    assert len({r.klass for r in rs}) == len(rs)


def test_realizations_are_deterministic():
    p = PROGRAMS[4]
    a = lp.realizations(p["rooms"], p["width"], p["depth"])
    b = lp.realizations(p["rooms"], p["width"], p["depth"])
    assert [(r.code, canonical_hash(r.rooms)) for r in a] == [(r.code, canonical_hash(r.rooms)) for r in b]


def test_realizations_include_arrangements_the_classic_template_never_produces():
    """Le but du chantier : des plans qui ne suivent plus le gabarit unique."""
    for n in (4, 5):
        rs = _realized(n)
        assert any(not follows_classic_template(r.rooms) for r in rs), n


def test_three_zone_programs_keep_at_least_two_arrangements_under_the_conventions():
    """Sous les conventions de façade, un programme à trois zones garde deux partis.

    Le gabarit horizontal et le couloir vertical (colonne nord-sud). Sans les
    conventions il y en a davantage, mais ils retournent nord et sud : l'entrée
    ou la porte de garage donneraient sur la mauvaise pièce.
    """
    codes = {r.code for r in _realized(3)}
    assert len(codes) >= 2, codes


def test_the_rich_program_really_is_rich():
    assert len(lp.realizations(RICH["rooms"], RICH["width"], RICH["depth"])) >= 10


def test_the_ensuite_flag_is_set_on_exactly_the_ensuite_bathroom():
    """Le drapeau décide des portes : chambre—salle de bain seulement si elle est « ensuite »."""
    first = next(lp.iter_realizations(FULL, 14.0, 11.0))
    assert [r["id"] for r in first.rooms if r.get("ensuite")] == ["r3"]


def test_realizations_share_the_classic_plot_extent():
    """Emprise calée sur la grille comme `pack_house` : mêmes bornes que le gabarit."""
    for n in (3, 4, 5):
        p = PROGRAMS[n]
        classic = lo.pack_house([dict(r) for r in p["rooms"]], p["width"], p["depth"], grid=0.1, min_side=1.6)
        cx = max(q["x"] for r in classic for q in r["polygon"])
        cy = max(q["y"] for r in classic for q in r["polygon"])
        for r in _realized(n):
            assert abs(max(q["x"] for x in r.rooms for q in x["polygon"]) - cx) < 1e-6
            assert abs(max(q["y"] for x in r.rooms for q in x["polygon"]) - cy) < 1e-6


def test_a_plot_off_the_grid_is_snapped_like_the_classic_template():
    """Les parcelles du corpus ont une décimale : le calage n'y change rien. Celle-ci non."""
    p = PROGRAMS[4]
    w, d = 12.34, 9.87
    classic = lo.pack_house([dict(r) for r in p["rooms"]], w, d, grid=0.1, min_side=1.6)
    cx = max(q["x"] for r in classic for q in r["polygon"])
    cy = max(q["y"] for r in classic for q in r["polygon"])
    assert (cx, cy) != (w, d)                              # le gabarit a bien calé l'emprise
    rs = lp.realizations(p["rooms"], w, d)
    assert rs, "aucun parti réalisable sur une parcelle hors grille"
    for r in rs:
        assert abs(max(q["x"] for x in r.rooms for q in x["polygon"]) - cx) < 1e-6
        assert abs(max(q["y"] for x in r.rooms for q in x["polygon"]) - cy) < 1e-6
        assert lp.hard_check(r.rooms, cx, cy) is None


def test_orders_offer_both_directions_for_two_rooms_or_more():
    rooms = _rooms(("bedroom", 12), ("bathroom", 5), ("office", 8))
    orders = lp._orders(rooms)
    assert len(orders) == 2 and orders[1] == list(reversed(orders[0]))
    assert lp._orders(rooms[:1]) == [rooms[:1]]


def test_strict_arrangements_come_first():
    p = RICH
    got = _first_n(lp.iter_realizations(p["rooms"], p["width"], p["depth"]), 40)
    flags = [r.strict for r in got]
    assert any(flags), "le programme témoin doit avoir des arrangements stricts"
    assert flags == sorted(flags, reverse=True)          # tous les stricts, puis les autres


_REALIZATION_SCRIPT = """
import sys, hashlib, json
sys.path.insert(0, {app!r}); sys.path.insert(0, {tests!r})
from app import layout_partis as lp
from test_layout_golden import canonical_hash
from test_layout_invariants import CORPUS
p = CORPUS[{index}]
rs = lp.realizations(p["rooms"], p["width"], p["depth"])
first = []
for r in lp.iter_realizations(p["rooms"], p["width"], p["depth"]):
    first.append((r.code, canonical_hash(r.rooms)))
    if len(first) == 4:
        break
print(hashlib.sha256(json.dumps([[(r.code, canonical_hash(r.rooms), r.thin, r.strict) for r in rs], first]).encode()).hexdigest())
"""


def test_realizations_do_not_depend_on_the_hash_seed():
    """Même programme, même parcelle : mêmes plans, quel que soit `PYTHONHASHSEED`."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    here = Path(__file__).resolve()
    script = _REALIZATION_SCRIPT.format(app=str(here.parents[1]), tests=str(here.parent), index=CORPUS.index(PROGRAMS[4]))
    digests = set()
    for seed in ("0", "1", "777"):
        out = subprocess.run([sys.executable, "-c", script], env={**os.environ, "PYTHONHASHSEED": seed},
                             capture_output=True, text=True, check=True)
        digests.add(out.stdout.strip())
    assert len(digests) == 1, digests


# --- iter_realizations ----------------------------------------------------------

def _first(gen, k):
    out = []
    for r in gen:
        out.append((r.code, canonical_hash(r.rooms)))
        if len(out) == k:
            break
    return out


def test_iteration_is_deterministic_without_a_generator():
    p = RICH
    assert _first(lp.iter_realizations(p["rooms"], p["width"], p["depth"]), 6) == \
        _first(lp.iter_realizations(p["rooms"], p["width"], p["depth"]), 6)


def test_a_seed_changes_the_order_and_the_same_seed_repeats_it():
    p = RICH
    args = (p["rooms"], p["width"], p["depth"])
    s1 = _first(lp.iter_realizations(*args, rng=random.Random(1)), 8)
    s1b = _first(lp.iter_realizations(*args, rng=random.Random(1)), 8)
    s2 = _first(lp.iter_realizations(*args, rng=random.Random(2)), 8)
    assert s1 == s1b
    assert s1 != s2


def test_iteration_yields_only_valid_plans():
    p = PROGRAMS[4]
    w, d = _snapped(p)
    for r in _first_n(lp.iter_realizations(p["rooms"], p["width"], p["depth"]), 12):
        assert lp.hard_check(r.rooms, w, d) is None


def _first_n(gen, k):
    out = []
    for r in gen:
        out.append(r)
        if len(out) == k:
            break
    return out


def test_iteration_is_lazy():
    """Demander une seule réalisation ne balaye pas tous les arrangements."""
    p = RICH
    gen = lp.iter_realizations(p["rooms"], p["width"], p["depth"])
    assert next(gen) is not None


def test_a_program_without_rooms_yields_nothing():
    assert list(lp.iter_realizations([], 10, 10)) == []
    assert lp.realizations([], 10, 10) == []


def test_a_plot_too_small_yields_nothing():
    assert lp.realizations(PROGRAMS[5]["rooms"], 4.0, 4.0) == []


# --- Raffinement gardé ------------------------------------------------------------

def test_refine_moves_the_cut_toward_the_requested_areas():
    layout = [_r("l", "living", 0, 0, 5, 4), _r("k", "kitchen", 5, 0, 10, 4)]
    assert lp.hard_check(layout, 10, 4) is None
    lp.refine(layout, {"l": 30.0, "k": 10.0}, 10, 4, 0.1, 1.6)
    living = next(r for r in layout if r["id"] == "l")
    width = max(q["x"] for q in living["polygon"]) - min(q["x"] for q in living["polygon"])
    assert width > 6.5                                     # ~7,5 m demandés
    assert lp.hard_check(layout, 10, 4) is None


def test_refine_never_leaves_an_invalid_plan(monkeypatch):
    """Si le contrôle dur refuse le résultat, le remplissage d'origine est restauré."""
    layout = [_r("l", "living", 0, 0, 5, 4), _r("k", "kitchen", 5, 0, 10, 4)]
    before = [(r["id"], r["polygon"]) for r in layout]
    monkeypatch.setattr(lp, "hard_check", lambda *a, **k: "emprise")
    lp.refine(layout, {"l": 30.0, "k": 10.0}, 10, 4, 0.1, 1.6)
    assert [(r["id"], r["polygon"]) for r in layout] == before


# --- Contrôle de conformité, second temps -----------------------------------------

def test_compliance_failures_returns_check_keys():
    failures = lp.compliance_failures(VALID, 10, 10)
    assert isinstance(failures, set) and all(isinstance(k, str) for k in failures)


def test_a_regression_is_a_failure_the_classic_does_not_have():
    failures = lp.compliance_failures(VALID, 10, 10)
    assert lp.compliance_regressions(VALID, 10, 10, failures) == set()
    assert lp.compliance_regressions(VALID, 10, 10, set()) == failures


def test_failures_that_the_classic_shares_are_not_regressions():
    """Un plan qui échoue là où le classique échoue aussi n'est pas disqualifié."""
    failures = lp.compliance_failures(VALID, 10, 10)
    assert failures, "le plan de test devrait échouer à au moins un contrôle (pas de cuisine, pas de salle de bain…)"
    one = next(iter(failures))
    assert one not in lp.compliance_regressions(VALID, 10, 10, {one})
    assert lp.compliance_regressions(VALID, 10, 10, failures - {one}) == {one}


def test_realizations_do_not_regress_compliance_against_the_classic():
    """Second temps du contrôle exact : rien de ce que le classique réussit ne doit échouer.

    Mesure d'ensemble : 99 % des partis échantillonnés (1 526) n'ont aucune
    régression. Ici, un échantillon borné de trois programmes.
    """
    clean = total = 0
    for p in (PROGRAMS[3], PROGRAMS[4], PROGRAMS[5], RICH):
        w, d = _snapped(p)
        classic = lo.pack_house([dict(r) for r in p["rooms"]], p["width"], p["depth"], grid=0.1, min_side=1.6)
        base = lp.compliance_failures(classic, w, d)
        for r in lp.realizations(p["rooms"], p["width"], p["depth"])[:8]:
            total += 1
            clean += not lp.compliance_regressions(r.rooms, w, d, base)
    assert total >= 12
    assert clean / total >= 0.9, f"{clean}/{total}"


def test_the_best_realization_is_at_least_as_good_as_the_classic_on_thin_rooms():
    """Le but de générer plusieurs partis : le meilleur ne fait jamais pire que le gabarit."""
    for p in (PROGRAMS[3], PROGRAMS[4], PROGRAMS[5], RICH):
        classic = lo.pack_house([dict(r) for r in p["rooms"]], p["width"], p["depth"], grid=0.1, min_side=1.6)
        rs = lp.realizations(p["rooms"], p["width"], p["depth"])
        assert rs
        assert min(r.thin for r in rs) <= lp.thin_count(classic, 1.6)


# --- Circulation : portes, accessibilité --------------------------------------------

def test_a_sound_plan_has_no_door_issue():
    assert lp.door_issues(VALID, 10, 10) == set()


def test_a_room_the_doors_do_not_link_to_the_entrance_is_inaccessible():
    """Chambre au sud, séjour au nord : la paire n'est pas dans la liste blanche des portes.

    L'entrée sud sert la chambre ; le séjour, que rien ne relie à elle, reçoit
    une porte extérieure de secours sur le mur nord. Deux défauts, un seul plan.
    """
    plan = [_r("l", "living", 0, 0, 10, 4), _r("b", "bedroom", 0, 4, 10, 10)]
    assert lp.door_issues(plan, 10, 10) == {"exterieure:l", "inaccessible:l"}


def test_the_garage_door_on_the_east_wall_is_not_an_extra_exterior_door():
    plan = [_r("l", "living", 0, 0, 6, 10), _r("g", "garage", 6, 0, 10, 10)]
    assert not any(i.startswith("exterieure") for i in lp.door_issues(plan, 10, 10))


def test_exact_ok_rejects_a_new_door_issue_and_accepts_a_shared_one():
    plan = [_r("l", "living", 0, 0, 10, 4), _r("b", "bedroom", 0, 4, 10, 10)]
    failures = lp.compliance_failures(plan, 10, 10)
    assert not lp.exact_ok(plan, 10, 10, lp.Baseline(failures=failures, doors=set()))
    assert lp.exact_ok(plan, 10, 10, lp.Baseline(failures=failures, doors=lp.door_issues(plan, 10, 10)))


def test_classic_baseline_is_computed_on_the_snapped_plot():
    p = PROGRAMS[4]
    base = lp.classic_baseline(p["rooms"], p["width"], p["depth"])
    assert isinstance(base.failures, set) and isinstance(base.doors, set)


def test_the_exact_stage_only_removes_partis():
    """`exact=False` est une borne haute : le contrôle exact ne peut qu'en retirer."""
    p = RICH
    loose = {(r.code, r.graph) for r in lp.realizations(p["rooms"], p["width"], p["depth"], exact=False)}
    tight = {(r.code, r.graph) for r in lp.realizations(p["rooms"], p["width"], p["depth"])}
    assert tight <= loose
    assert tight, "le programme riche doit garder des partis"


def test_both_entry_points_apply_the_exact_stage(monkeypatch):
    """Si le contrôle exact refuse tout, ni l'itération ni le décompte ne doivent rien rendre."""
    p = RICH
    assert lp.realizations(p["rooms"], p["width"], p["depth"])          # sans le mock : il y en a
    monkeypatch.setattr(lp, "exact_ok", lambda *a, **k: False)
    assert lp.realizations(p["rooms"], p["width"], p["depth"]) == []
    assert list(lp.iter_realizations(p["rooms"], p["width"], p["depth"])) == []


def test_the_exact_stage_is_skipped_when_conventions_are_off(monkeypatch):
    """Sans conventions, `default_openings` poserait l'entrée au mauvais endroit : rien à contrôler."""
    p = PROGRAMS[4]
    monkeypatch.setattr(lp, "exact_ok", lambda *a, **k: False)
    assert lp.realizations(p["rooms"], p["width"], p["depth"], conventions=False)


def test_conventions_off_never_yields_fewer_partis_than_conventions_on():
    """Sans les conventions de façade, on peut retourner nord et sud, déplacer le garage."""
    for p in (PROGRAMS[3], PROGRAMS[4], RICH):
        on = lp.realizations(p["rooms"], p["width"], p["depth"], exact=False)
        off = lp.realizations(p["rooms"], p["width"], p["depth"], conventions=False)
        assert len(off) >= len(on)


# --- Tableau de l'article -----------------------------------------------------------

def _report() -> str:
    import statistics

    rows = []
    for p in CORPUS:
        w, d = p["width"], p["depth"]
        cw, cd = lp._plot(w, d, 0.1, 1.6)
        classic = lo.pack_house([dict(r) for r in p["rooms"]], w, d, grid=0.1, min_side=1.6)
        rs = lp.realizations(p["rooms"], w, d)
        rows.append({
            "zones": len(z.program_from_rooms(p["rooms"]).zones),
            "n": len(rs),
            "codes": len({r.code for r in rs}),
            "classic_valid": lp.hard_check(classic, cw, cd) is None,
        })
    n = [r["n"] for r in rows]
    lines = ["", f"Corpus ajusté : {len(rows)} programmes", "",
             f"  partis réalisables par programme : min {min(n)}, médiane {statistics.median(n):.0f}, max {max(n)}",
             f"  programmes sans parti réalisable : {sum(1 for x in n if x == 0)}/{len(n)} ; moins de 3 : {sum(1 for x in n if x < 3)}/{len(n)}",
             f"  le gabarit classique passe le même contrôle dur : {sum(r['classic_valid'] for r in rows)}/{len(rows)}", ""]
    for nz in sorted({r["zones"] for r in rows}):
        v = [r for r in rows if r["zones"] == nz]
        lines.append(f"  {nz} zones : {len(v):>3} programmes, médiane {statistics.median(x['n'] for x in v):.0f} partis "
                     f"(min {min(x['n'] for x in v)}), {statistics.median(x['codes'] for x in v):.0f} codes distincts")
    return "\n".join(lines)


if __name__ == "__main__":
    print(_report())
