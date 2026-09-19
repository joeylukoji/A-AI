"""Étape C2 du chantier « partis » : énumérer les arrangements de zones.

`layout_zones` produit des CANDIDATS (arbres de découpe de cinq zones) et leur
applique des conditions nécessaires. Ces tests vérifient trois choses :

  * l'énumération est **exacte** : 4, 36, 528, 10 800 arbres, canoniques, sans
    doublon (la formule de Schröder est vérifiée, pas seulement citée) ;
  * chaque candidat pave la parcelle sans trou ni recouvrement ;
  * les conditions sont **dérivées** de `layout_rules` (une règle ajoutée là-bas
    change les candidats), et chaque niveau du jugement est éprouvé à la main.

Pour afficher le tableau de l'article (30 s) :
    python tests/test_layout_zones.py
"""
from __future__ import annotations

import itertools
import statistics
from functools import cache

import pytest

from app import layout_rules
from app import layout_zones as z
from app.layout_opt import _min_side
from test_layout_invariants import CORPUS


def _rooms(*spec: tuple[str, float]) -> list[dict]:
    return [{"id": f"r{i}", "type": t, "area_m2": a} for i, (t, a) in enumerate(spec)]


# Un programme par nombre de zones : nuit+couloir+jour (3), + service (4), + garage (5).
PROG_3 = _rooms(("bedroom", 12), ("bedroom", 11), ("bathroom", 5), ("living", 24), ("kitchen", 10))
PROG_4 = PROG_3 + _rooms(("wc", 2))
PROG_5 = PROG_4 + _rooms(("garage", 16))


@cache
def _cands(name: str, width: float, depth: float, conventions: bool = False):
    """Par défaut : les règles de distribution SEULES, sans les conventions de façade."""
    return z.candidates({"3": PROG_3, "4": PROG_4, "5": PROG_5}[name], width, depth, conventions)


# --- Énumération -------------------------------------------------------------

@pytest.mark.parametrize("n,expected", [(1, 1), (2, 4), (3, 36), (4, 528), (5, 10800)])
def test_tree_counts_match_the_schroder_formula(n, expected):
    assert z.tree_count(n) == expected
    assert len(z.enumerate_trees(z.ZONES[:n])) == expected


@pytest.mark.parametrize("n,fubini", [(2, 3), (3, 13), (4, 75), (5, 541)])
def test_ordered_partitions_are_the_fubini_numbers_minus_the_trivial_one(n, fubini):
    assert len(z._ordered_partitions(tuple("abcde"[:n]))) == fubini - 1


def _is_canonical(tree, zones) -> bool:
    if isinstance(tree, str):
        return True
    orient, children = tree
    if orient not in ("V", "H") or len(children) < 2:
        return False
    for child in children:
        if not isinstance(child, str) and child[0] == orient:  # deux coupes de même sens de suite
            return False
        if not _is_canonical(child, zones):
            return False
    return True


def test_trees_are_canonical_complete_and_distinct():
    zones = z.ZONES[:4]
    trees = z.enumerate_trees(zones)
    assert len(set(trees)) == len(trees) == 528
    for tree in trees:
        assert sorted(z._leaves(tree)) == sorted(zones)   # chaque zone exactement une fois
        assert _is_canonical(tree, zones)


def test_enumeration_ignores_input_order_and_handles_small_sets():
    assert z.enumerate_trees(("day", "night")) == z.enumerate_trees(("night", "day"))
    assert z.enumerate_trees(()) == ()
    assert z.enumerate_trees(("day",)) == ("day",)


# --- Zones et programme --------------------------------------------------------

@pytest.mark.parametrize("typ,zone", [
    ("bedroom", "night"), ("office", "night"), ("bathroom", "night"),
    ("hallway", "hall"),
    ("living", "day"), ("kitchen", "day"), ("dining", "day"),
    ("wc", "svc"), ("laundry", "svc"), ("storage", "svc"),
    ("garage", "garage"),
])
def test_every_known_type_has_a_zone(typ, zone):
    assert z.zone_of(typ) == zone


def test_an_unknown_type_belongs_to_the_day_zone():
    assert z.zone_of("veranda") == z.DAY


def test_hall_is_implied_by_a_bedroom_or_a_wc_with_a_day_room():
    assert z.HALL in z.program_from_rooms(_rooms(("bedroom", 12), ("living", 20))).demand
    assert z.HALL in z.program_from_rooms(_rooms(("wc", 2), ("kitchen", 9))).demand
    assert z.HALL not in z.program_from_rooms(_rooms(("wc", 2), ("garage", 15))).demand
    assert z.HALL not in z.program_from_rooms(_rooms(("living", 20), ("kitchen", 9))).demand


def test_an_explicit_hallway_is_kept_not_duplicated():
    prog = z.program_from_rooms(_rooms(("bedroom", 12), ("hallway", 9), ("living", 20)))
    assert prog.demand[z.HALL] == 9.0


def test_zone_demand_and_min_side_come_from_the_rooms():
    prog = z.program_from_rooms(PROG_4)
    assert prog.demand[z.NIGHT] == 12 + 11 + 5
    assert prog.demand[z.DAY] == 34
    assert prog.min_side[z.NIGHT] == _min_side("bedroom", 1.6)   # 2,6 : la plus exigeante
    assert prog.min_side[z.DAY] == _min_side("living", 1.6)      # 3,0
    assert prog.min_side[z.HALL] <= z.HALL_THICKNESS


# --- Dimensionnement : chaque candidat pave la parcelle -----------------------

@pytest.mark.parametrize("name,w,d", [("3", 12.0, 10.0), ("4", 12.0, 10.0), ("5", 14.0, 11.0)])
def test_every_candidate_tiles_the_plot_exactly(name, w, d):
    cands = _cands(name, w, d)
    assert cands, "aucun candidat dimensionnable"
    for c in cands:
        rects = list(c.rects.values())
        assert abs(sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects) - w * d) < 1e-6
        for r in rects:
            assert -1e-9 <= r[0] < r[2] <= w + 1e-9 and -1e-9 <= r[1] < r[3] <= d + 1e-9
        for a, b in itertools.combinations(rects, 2):
            ox = min(a[2], b[2]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[1], b[1])
            assert not (ox > 1e-6 and oy > 1e-6), "recouvrement"


@pytest.mark.parametrize("name,w,d", [("4", 12.0, 10.0), ("5", 14.0, 11.0)])
def test_candidates_respect_zone_minimum_sides_and_hall_thickness(name, w, d):
    prog = z.program_from_rooms({"4": PROG_4, "5": PROG_5}[name])
    for c in _cands(name, w, d):
        for zone, (x0, y0, x1, y1) in c.rects.items():
            short = min(x1 - x0, y1 - y0)
            assert short + 1e-6 >= min(prog.min_side[zone], z.HALL_THICKNESS), (zone, short)
        hall = c.rects[z.HALL]
        assert min(hall[2] - hall[0], hall[3] - hall[1]) <= z.HALL_THICKNESS + 1e-6


def test_a_plot_too_small_for_the_minimum_sides_yields_no_candidate():
    assert z.candidates(PROG_5, 5.0, 5.0) == []


def test_candidates_are_deterministic():
    a = z.candidates(PROG_4, 12.0, 10.0)
    b = z.candidates(PROG_4, 12.0, 10.0)
    assert [c.tree for c in a] == [c.tree for c in b]
    assert [c.rects for c in a] == [c.rects for c in b]


# --- Déterminisme entre processus ---------------------------------------------------

_DETERMINISM_SCRIPT = """
import sys, hashlib, json
sys.path.insert(0, {root!r})
from app import layout_zones as z
rooms = [{{"id": f"r{{i}}", "type": t, "area_m2": a}} for i, (t, a) in enumerate(
    [("bedroom", 12), ("bedroom", 11), ("bathroom", 5), ("living", 24), ("kitchen", 10), ("wc", 2), ("garage", 16)])]
out = []
for conventions in (False, True):
    for c in z.candidates(rooms, 14.0, 11.0, conventions):
        v = c.verdict
        out.append([repr(c.tree), sorted(c.rects.items()), v.necessary, v.connected, v.strict, list(v.reasons)])
print(hashlib.sha256(json.dumps(out, default=str).encode()).hexdigest())
"""


def test_candidates_and_verdicts_do_not_depend_on_the_hash_seed():
    """`frozenset` de chaînes : l'ordre d'itération change à chaque processus (PYTHONHASHSEED).

    Un verdict dont les motifs de rejet sortent dans un ordre variable n'est pas
    déterministe, même si les arbres et les rectangles le sont.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = str(Path(__file__).resolve().parents[1])
    digests = set()
    for seed in ("0", "1", "2", "12345"):
        out = subprocess.run([sys.executable, "-c", _DETERMINISM_SCRIPT.format(root=root)],
                             env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, text=True, check=True)
        digests.add(out.stdout.strip())
    assert len(digests) == 1, digests


# --- Contacts ------------------------------------------------------------------

def test_contact_length_counts_a_shared_wall_not_a_corner():
    a = (0.0, 0.0, 4.0, 4.0)
    assert z.contact_length(a, (4.0, 0.0, 8.0, 4.0)) == 4.0          # mur complet
    assert z.contact_length(a, (4.0, 2.0, 8.0, 9.0)) == 2.0          # T : recouvrement partiel
    assert z.contact_length(a, (0.0, 4.0, 4.0, 6.0)) == 4.0          # au sud
    assert z.contact_length(a, (4.0, 4.0, 8.0, 8.0)) == 0.0          # simple coin
    assert z.contact_length(a, (5.0, 0.0, 8.0, 4.0)) == 0.0          # écart de 1 m
    assert z.contact_length(a, (1.0, 1.0, 3.0, 3.0)) == 0.0          # inclus, pas contigu


def test_contact_length_is_symmetric():
    a, b = (0.0, 0.0, 4.0, 4.0), (4.0, 1.0, 9.0, 7.0)
    assert z.contact_length(a, b) == z.contact_length(b, a) == 3.0


def test_perimeter_length_sums_the_edges_on_the_boundary():
    assert z.perimeter_length((0, 0, 10, 4), 10, 10) == 10 + 4 + 4   # nord + ouest + est
    assert z.perimeter_length((0, 0, 10, 10), 10, 10) == 40
    assert z.perimeter_length((3, 3, 7, 7), 10, 10) == 0
    assert z.perimeter_length((0, 3, 4, 7), 10, 10) == 4


# --- Contraintes : dérivées de layout_rules ------------------------------------

def test_constraints_are_derived_from_the_declared_rules():
    prog = z.program_from_rooms(_rooms(("bedroom", 12), ("bathroom", 5), ("living", 20), ("kitchen", 9), ("wc", 2)))
    cons = z.constraints_for(prog)
    assert cons.needs_hall == {z.NIGHT, z.SVC}
    assert cons.perimeter == {z.NIGHT, z.DAY}
    assert cons.forbidden == {frozenset({z.NIGHT, z.DAY}), frozenset({z.SVC, z.DAY}), frozenset({z.SVC, z.NIGHT})}


def test_a_pair_whose_types_are_absent_is_not_forbidden():
    """Sans chambre, WC et nuit peuvent se toucher : la règle wc/chambre est sans objet."""
    prog = z.program_from_rooms(_rooms(("bathroom", 5), ("living", 20), ("kitchen", 9), ("wc", 2)))
    cons = z.constraints_for(prog)
    assert frozenset({z.SVC, z.NIGHT}) not in cons.forbidden
    assert frozenset({z.NIGHT, z.DAY}) in cons.forbidden       # salle de bain / cuisine
    assert z.NIGHT not in cons.needs_hall                       # pas de chambre


def test_a_rule_added_to_layout_rules_changes_the_constraints(monkeypatch):
    prog = z.program_from_rooms(PROG_5)
    assert frozenset({z.GARAGE, z.NIGHT}) not in z.constraints_for(prog).forbidden
    extra = layout_rules.ForbiddenPair("garage_bedroom", frozenset({"garage"}), frozenset({"bedroom"}), per_room=True)
    monkeypatch.setattr(layout_rules, "RULES", layout_rules.RULES + (extra,))
    assert frozenset({z.GARAGE, z.NIGHT}) in z.constraints_for(prog).forbidden


def test_a_needs_hall_rule_added_to_layout_rules_changes_the_constraints(monkeypatch):
    prog = z.program_from_rooms(PROG_5)
    assert z.GARAGE not in z.constraints_for(prog).needs_hall
    monkeypatch.setattr(layout_rules, "RULES", layout_rules.RULES + (layout_rules.NeedsHall("garage_hall", frozenset({"garage"})),))
    assert z.GARAGE in z.constraints_for(prog).needs_hall


# --- Jugement, cas construits à la main ----------------------------------------

def _judge(rects, types, w=10.0, d=10.0, conventions=False):
    prog = z.program_from_rooms([{"type": t, "area_m2": 10} for t in types])
    return z.judge(rects, prog, w, d, conventions=conventions)


BASIC = ("bedroom", "living", "kitchen")


def test_classic_stack_passes_every_level():
    v = _judge({z.NIGHT: (0, 0, 10, 4), z.HALL: (0, 4, 10, 5.3), z.DAY: (0, 5.3, 10, 10)}, BASIC)
    assert (v.necessary, v.connected, v.strict) == (True, True, True)


def test_night_not_touching_the_hall_fails_the_necessary_level():
    v = _judge({z.NIGHT: (0, 0, 10, 4), z.DAY: (0, 4, 10, 8.7), z.HALL: (0, 8.7, 10, 10)}, BASIC)
    assert not v.necessary and not v.connected and not v.strict
    assert any("night ne touche pas le couloir" in r for r in v.reasons)


def test_night_beside_day_is_necessary_and_connected_but_not_strict():
    """Nuit et jour se touchent tous deux le couloir, mais aussi entre eux."""
    v = _judge({z.NIGHT: (0, 0, 5, 6), z.DAY: (5, 0, 10, 6), z.HALL: (0, 6, 10, 7.3), "garage": (0, 7.3, 10, 10)},
               BASIC + ("garage",))
    assert v.necessary and v.connected
    assert not v.strict


def test_day_not_touching_the_hall_fails_connected_only():
    v = _judge({z.NIGHT: (0, 0, 10, 4), z.HALL: (0, 4, 10, 5.3), z.GARAGE: (0, 5.3, 10, 8), z.DAY: (0, 8, 10, 10)},
               BASIC + ("garage",))
    assert v.necessary and not v.connected and not v.strict


def test_an_inner_habitable_zone_fails_the_perimeter_condition():
    v = _judge({z.NIGHT: (3, 3, 7, 7), z.HALL: (0, 0, 10, 1.3), z.DAY: (0, 7, 10, 10)}, BASIC)
    assert any("night ne touche pas le périmètre" in r for r in v.reasons)
    assert not v.necessary


def test_a_squat_hall_is_not_a_circulation():
    v = _judge({z.NIGHT: (0, 0, 10, 4), z.HALL: (0, 4, 2, 6), z.DAY: (2, 4, 10, 10)}, BASIC)
    assert any("couloir trop court" in r for r in v.reasons)


def test_without_a_hall_there_is_nothing_to_touch():
    """`NeedsHall` ne s'applique que s'il existe un couloir."""
    v = _judge({z.DAY: (0, 0, 10, 6), z.GARAGE: (0, 6, 10, 10)}, ("living", "kitchen", "garage"))
    assert v.necessary and v.connected


def test_wc_must_touch_the_hall_and_stay_away_from_the_bedroom_in_strict_mode():
    types = ("bedroom", "living", "kitchen", "wc")
    ok = {z.NIGHT: (0, 0, 6, 4), z.HALL: (0, 4, 10, 5.3), z.DAY: (0, 5.3, 10, 10), z.SVC: (6, 0, 10, 4)}
    v = _judge(ok, types)
    assert v.necessary and not v.strict                         # le WC touche la chambre
    away = {z.NIGHT: (0, 0, 5, 4), z.SVC: (7, 0, 10, 4), z.GARAGE: (5, 0, 7, 4),
            z.HALL: (0, 4, 10, 5.3), z.DAY: (0, 5.3, 10, 10)}
    assert _judge(away, types + ("garage",)).strict


# --- Conventions de façade (entrée au sud, porte de garage à l'est) ----------------

def _conv(rects, types, w=10.0, d=10.0):
    return _judge(rects, types, w, d, conventions=True)


def test_south_length_is_the_edge_on_the_south_wall():
    assert z.south_length((0, 5, 10, 10), 10) == 10
    assert z.south_length((2, 5, 6, 10), 10) == 4
    assert z.south_length((0, 0, 10, 5), 10) == 0


def test_bedrooms_alone_on_the_south_wall_fail_the_entrance_convention():
    rects = {z.DAY: (0, 0, 10, 4.7), z.HALL: (0, 4.7, 10, 6.0), z.NIGHT: (0, 6.0, 10, 10)}
    assert _judge(rects, BASIC, conventions=False).necessary
    v = _conv(rects, BASIC)
    assert not v.necessary and any("façade sud" in r for r in v.reasons)


def test_the_day_zone_or_the_hall_on_the_south_wall_receives_the_entrance():
    stack = {z.NIGHT: (0, 0, 10, 4), z.HALL: (0, 4, 10, 5.3), z.DAY: (0, 5.3, 10, 10)}
    assert _conv(stack, BASIC).necessary
    spine = {z.NIGHT: (0, 0, 4, 10), z.HALL: (4, 0, 5.3, 10), z.DAY: (5.3, 0, 10, 10)}
    assert _conv(spine, BASIC).necessary          # les trois colonnes touchent le mur sud


def test_a_garage_must_hold_the_east_wall_where_the_door_is():
    types = BASIC + ("garage",)
    east = {z.NIGHT: (0, 0, 6, 4), z.HALL: (0, 4, 6, 5.3), z.DAY: (0, 5.3, 6, 10), z.GARAGE: (6, 0, 10, 10)}
    assert not any("garage" in r for r in _conv(east, types).reasons)
    west = {z.NIGHT: (6, 0, 10, 4), z.HALL: (6, 4, 10, 5.3), z.DAY: (6, 5.3, 10, 10), z.GARAGE: (0, 0, 6, 10)}
    assert any("garage" in r for r in _conv(west, types).reasons)


def test_a_garage_above_the_door_span_fails_and_one_covering_it_passes():
    types = BASIC + ("garage",)
    high = {z.NIGHT: (0, 0, 6, 4), z.HALL: (0, 4, 6, 5.3), z.DAY: (0, 5.3, 6, 10), z.GARAGE: (6, 0, 10, 3)}
    assert any("garage" in r for r in _conv(high, types).reasons)
    covering = {z.NIGHT: (0, 0, 6, 4), z.HALL: (0, 4, 6, 5.3), z.DAY: (0, 5.3, 6, 10), z.GARAGE: (6, 0, 10, 10)}
    assert not any("garage" in r for r in _conv(covering, types).reasons)


def test_without_a_garage_the_garage_convention_asks_nothing():
    stack = {z.NIGHT: (0, 0, 10, 4), z.HALL: (0, 4, 10, 5.3), z.DAY: (0, 5.3, 10, 10)}
    assert not any("garage" in r for r in _conv(stack, BASIC).reasons)


def test_conventions_are_off_by_a_flag_and_only_narrow_the_candidates():
    for name, w, d in (("3", 12.0, 10.0), ("4", 12.0, 10.0), ("5", 14.0, 11.0)):
        pure = {c.tree for c in _cands(name, w, d) if c.verdict.necessary}
        conv = {c.tree for c in _cands(name, w, d, True) if c.verdict.necessary}
        assert conv <= pure, name
    assert len(conv) < len(pure)                    # elles éliminent bel et bien des arrangements


def test_constraints_name_the_entrance_zones_and_the_garage():
    cons = z.constraints_for(z.program_from_rooms(PROG_5))
    assert cons.entrance == {z.HALL, z.DAY} and cons.garage
    assert z.constraints_for(z.program_from_rooms(PROG_4)).garage is False


# --- Propriétés sur les candidats ----------------------------------------------

@pytest.mark.parametrize("name,w,d", [("3", 12.0, 10.0), ("4", 12.0, 10.0), ("5", 14.0, 11.0)])
def test_levels_are_nested(name, w, d):
    for c in _cands(name, w, d):
        v = c.verdict
        assert (not v.strict or v.connected) and (not v.connected or v.necessary)


def _adjacency_graph(c):
    return frozenset(
        (a, b) for a, b in itertools.combinations(sorted(c.rects), 2)
        if z.contact_length(c.rects[a], c.rects[b]) > z.MIN_CONTACT
    )


def test_three_zones_admit_a_single_topology():
    """Nuit, couloir, jour : la seule topologie stricte est le chemin nuit—couloir—jour.

    Un fait structurel, pas un défaut du générateur : tout ce qui varie est
    l'orientation et le sens. La diversité d'un petit programme ne peut venir
    que de l'intérieur des zones.
    """
    strict = [c for c in _cands("3", 12.0, 10.0) if c.verdict.strict]
    assert strict
    assert {_adjacency_graph(c) for c in strict} == {frozenset({(z.HALL, z.NIGHT), (z.DAY, z.HALL)})}


def test_five_zones_admit_several_strict_topologies():
    strict = [c for c in _cands("5", 14.0, 11.0) if c.verdict.strict]
    assert len({_adjacency_graph(c) for c in strict}) >= 2


PLOTS = [(12.0, 10.0), (14.0, 9.0), (10.0, 12.0), (16.0, 11.0), (9.5, 9.5)]


def test_a_wc_with_a_bedroom_and_no_buffer_zone_has_no_strict_arrangement():
    """Résultat d'exhaustion : nuit, couloir, jour, service — avec WC et chambre.

    Les contacts exigés forment une étoile : le couloir doit toucher la nuit, le
    jour et le service, qui ne doivent se toucher deux à deux en aucun point. On
    ne connaît aucun découpage d'un rectangle en quatre rectangles dont le graphe
    de contacts soit une étoile, et l'énumération complète (528 arrangements par
    parcelle) n'en trouve aucun. C'est la raison d'être des tronçons de couloir du
    gabarit actuel : pour ce programme, un tampon est structurellement nécessaire.

    L'énumération reste utile : le niveau `connected` a des candidats, dont le
    remplissage exact (une salle de bain ou le séjour contre le WC) peut réussir.
    """
    for w, d in PLOTS:
        cands = z.candidates(PROG_4, w, d, conventions=False)
        assert cands, (w, d)
        assert not [c for c in cands if c.verdict.strict], (w, d)
        assert [c for c in cands if c.verdict.connected], (w, d)


def test_a_garage_can_buffer_the_wc_without_any_corridor_stub():
    """Avec un garage, le WC touche le couloir sans tronçon tampon."""
    strict = [c for c in _cands("5", 14.0, 11.0) if c.verdict.strict]
    assert strict
    for c in strict:
        assert z.contact_length(c.rects[z.SVC], c.rects[z.HALL]) >= z.MIN_CONTACT
        assert z.contact_length(c.rects[z.SVC], c.rects[z.NIGHT]) <= 0.05
        assert z.contact_length(c.rects[z.SVC], c.rects[z.DAY]) <= 0.05


def test_a_service_zone_without_a_wc_creates_no_forbidden_contact():
    """Buanderie et rangement n'ont aucune règle d'adjacence : le strict redevient possible."""
    laundry = _rooms(("bedroom", 12), ("bedroom", 11), ("bathroom", 5), ("living", 24),
                     ("kitchen", 10), ("laundry", 4))
    for w, d in PLOTS:
        assert [c for c in z.candidates(laundry, w, d, conventions=False) if c.verdict.strict], (w, d)


def test_a_wc_without_a_bedroom_creates_no_star():
    """Sans chambre, la règle WC/chambre est sans objet : la contrainte n'est plus une étoile."""
    no_bed = _rooms(("bathroom", 5), ("living", 24), ("kitchen", 10), ("wc", 2))
    prog = z.program_from_rooms(no_bed)
    assert z.HALL in prog.demand and z.NIGHT in prog.demand     # couloir implicite, salle de bain en nuit
    assert [c for c in z.candidates(no_bed, 12.0, 10.0, conventions=False) if c.verdict.strict]


def test_the_classic_arrangement_is_among_the_candidates():
    codes = {z.arrangement_code(c.rects, 12.0, 10.0) for c in _cands("3", 12.0, 10.0) if c.verdict.strict}
    assert "night:N|day:S|hall:H|garage:-" in codes
    assert len(codes) >= 2                                      # et d'autres, qui ne le sont pas


def test_arrangement_code_describes_side_and_hall_direction():
    stack = {z.NIGHT: (0, 0, 10, 4), z.HALL: (0, 4, 10, 5.3), z.DAY: (0, 5.3, 10, 10)}
    assert z.arrangement_code(stack, 10, 10) == "night:N|day:S|hall:H|garage:-"
    spine = {z.NIGHT: (6.3, 0, 10, 10), z.HALL: (5, 0, 6.3, 10), z.DAY: (0, 0, 5, 10), z.GARAGE: (0, 0, 0.01, 0.01)}
    assert z.arrangement_code(spine, 10, 10).startswith("night:E|day:W|hall:V")


# --- Outils de comparaison : miroir et graphe d'adjacence ----------------------------

def test_canonical_code_merges_east_west_mirrors_but_not_north_south():
    a = "night:W|day:E|hall:V|garage:-"
    b = "night:E|day:W|hall:V|garage:-"
    assert z.canonical_code(a) == z.canonical_code(b)
    assert z.canonical_code("night:N|day:S|hall:H|garage:-") != z.canonical_code("night:S|day:N|hall:H|garage:-")
    assert z.canonical_code(z.canonical_code(a)) == z.canonical_code(a)          # idempotent


def test_canonical_code_leaves_the_hall_direction_alone():
    assert z.canonical_code("night:W|day:E|hall:V|garage:-") != z.canonical_code("night:W|day:E|hall:H|garage:-")


def test_adjacency_graph_lists_the_zones_that_really_touch():
    stack = {z.NIGHT: (0, 0, 10, 4), z.HALL: (0, 4, 10, 5.3), z.DAY: (0, 5.3, 10, 10)}
    assert z.adjacency_graph(stack) == {(z.HALL, z.NIGHT), (z.DAY, z.HALL)}


def test_adjacency_graph_ignores_a_corner_and_a_too_short_contact():
    corner = {z.NIGHT: (0, 0, 5, 5), z.DAY: (5, 5, 10, 10)}
    assert z.adjacency_graph(corner) == set()
    short = {z.NIGHT: (0, 0, 5, 5), z.DAY: (5, 4.5, 10, 10)}       # 0,5 m de mur commun : pas une porte
    assert z.adjacency_graph(short) == set()


# --- Tableau de l'article ---------------------------------------------------------

def _report() -> str:
    def mirror(code: str) -> str:
        return code.replace(":W", ":#").replace(":E", ":W").replace(":#", ":E")

    rows = []
    for p in CORPUS:
        w, d = p["width"], p["depth"]
        cs = z.candidates(p["rooms"], w, d)
        strict = [c for c in cs if c.verdict.strict]
        necessary = [c for c in cs if c.verdict.necessary]
        rows.append({
            "zones": len(z.program_from_rooms(p["rooms"]).zones),
            "strict": len(strict),
            "graphs": len({_adjacency_graph(c) for c in strict}),
            "codes_strict": len({min(k, mirror(k)) for k in (z.arrangement_code(c.rects, w, d) for c in strict)}),
            "codes_nec": len({min(k, mirror(k)) for k in (z.arrangement_code(c.rects, w, d) for c in necessary)}),
        })
    lines = ["", f"Corpus ajusté : {len(rows)} programmes", ""]
    for key, label in (("strict", "arrangements stricts"), ("graphs", "topologies strictes distinctes"),
                       ("codes_strict", "codes côté/sens stricts (miroir E-O)"), ("codes_nec", "codes côté/sens nécessaires")):
        v = [r[key] for r in rows]
        lines.append(f"  {label:<40} min {min(v):>4}  médiane {statistics.median(v):>5.0f}  max {max(v):>5}   sans/moins de 3 : {sum(1 for x in v if x < 3)}/{len(v)}")
    lines.append("")
    for nz in sorted({r["zones"] for r in rows}):
        v = [r["graphs"] for r in rows if r["zones"] == nz]
        lines.append(f"  {nz} zones : {len(v):>3} programmes, topologies strictes médiane {statistics.median(v):.0f} (min {min(v)}, max {max(v)})")
    return "\n".join(lines)


if __name__ == "__main__":
    print(_report())
