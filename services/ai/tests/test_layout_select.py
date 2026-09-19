"""Étape E/F du chantier « partis » : choisir un parti, et le brancher derrière un drapeau.

`layout_select` choisit entre les partis réalisables (score, tirage à graine parmi les
quasi-meilleurs, préférence pour l'arrangement mémorisé) et décide si le pipeline s'en
sert (`LAYOUT_VARIANTS` : off, shadow, on). Ces tests vérifient :

  * le score et ses composantes, sans terme de conformité ;
  * le choix : déterminisme par graine, variété entre graines, qualité bornée, stabilité
    à la retouche ;
  * le drapeau : éteint par défaut, la graine tirée à la génération seulement ;
  * le branchement de bout en bout (vectorisation, adaptation, pipeline), y compris le
    repli sur le gabarit classique quand le parti ne réalise pas le plan.

Aucun de ces tests n'appelle d'API payante : `IMAGE_BACKEND=procedural` (conftest) et le
planificateur Together est coupé par chaque test qui traverse le pipeline.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from functools import cache
from pathlib import Path

import pytest

from app import layout_opt as lo
from app import layout_partis as lp
from app import layout_select as sel
from app.main import PipelineRequest, _pipeline
from app.plan_adapt import adapt
from app.vectorize import vectorize
from test_layout_golden import canonical_hash
from test_layout_invariants import CORPUS

RICH = CORPUS[18]          # cinq zones, garage, deux chambres : beaucoup de partis
DIVERSE = CORPUS[7]        # huit arrangements distincts sur douze graines (mesuré)
SCHEMA = Path(__file__).resolve().parents[3] / "packages" / "plan-schema" / "plan-document.schema.json"


def _r(rid: str, typ: str, x0: float, y0: float, x1: float, y1: float) -> dict:
    return {"id": rid, "type": typ, "name": typ, "polygon": [
        {"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]}


def _real(*, thin=0, strict=False, rooms=None, code="night:N|day:S|hall:H|garage:-", raw=None) -> lp.Realization:
    return lp.Realization(tree="t", rects={}, rooms=rooms or [], code=code, graph=frozenset(), thin=thin,
                          strict=strict, raw_code=raw or code)


@cache
def _rich_pool():
    return sel.pool(RICH["rooms"], RICH["width"], RICH["depth"])


@cache
def _diverse_pool():
    return sel.pool(DIVERSE["rooms"], DIVERSE["width"], DIVERSE["depth"])


@pytest.fixture(autouse=True)
def _no_paid_calls(monkeypatch):
    """Le planificateur Together et Eden ne doivent jamais être joignables depuis un test."""
    monkeypatch.setenv("TOGETHER_PLANNER", "0")
    monkeypatch.setenv("TOGETHER_NLU", "0")
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.delenv("EDENAI_API_KEY", raising=False)
    monkeypatch.delenv("LAYOUT_VARIANTS", raising=False)
    monkeypatch.delenv("LAYOUT_SEED", raising=False)


# --- Score ---------------------------------------------------------------------------

def test_aspect_penalty_only_counts_habitable_rooms_beyond_the_tolerance():
    assert sel.aspect_penalty([_r("l", "living", 0, 0, 10, 2)]) == pytest.approx(5 - sel.ASPECT_OK)
    assert sel.aspect_penalty([_r("b", "bedroom", 0, 0, 3, 3)]) == 0
    assert sel.aspect_penalty([_r("b", "bedroom", 0, 0, 5, 2)]) == 0            # 2,5 : à la limite
    assert sel.aspect_penalty([_r("g", "garage", 0, 0, 10, 2), _r("h", "hallway", 0, 0, 12, 1)]) == 0


def test_circulation_penalty_counts_five_point_slices_above_the_norm():
    rooms = lambda hall: [_r("h", "hallway", 0, 0, 10, hall), _r("l", "living", 0, hall, 10, 10)]  # noqa: E731
    assert sel.circulation_penalty(rooms(1.2)) == 0                              # 12 %
    assert sel.circulation_penalty(rooms(1.7)) == pytest.approx(1.0)             # 17 % : une tranche
    assert sel.circulation_penalty([]) == 0


def test_area_error_is_the_mean_gap_to_the_requested_areas():
    rooms = [_r("a", "living", 0, 0, 5, 4), _r("b", "kitchen", 5, 0, 8, 4), _r("h", "hallway", 0, 4, 8, 5)]
    assert sel.area_error(rooms, {"a": 24.0, "b": 10.0}) == pytest.approx((4 + 2) / 2)   # le couloir n'a pas de cible
    assert sel.area_error(rooms, {}) == 0


def test_a_room_with_fewer_thin_rooms_scores_better_all_else_equal():
    assert sel.score(_real(thin=0), {}) < sel.score(_real(thin=2), {})


def test_a_strict_arrangement_gets_a_small_bonus():
    assert sel.score(_real(strict=True), {}) == pytest.approx(sel.score(_real(strict=False), {}) - sel.STRICT_BONUS)


def test_the_score_has_no_compliance_term(monkeypatch):
    """Conformité déjà garantie par le contrôle exact : la mettre dans l'objectif fausserait toute mesure."""
    def boom(*a, **k):
        raise AssertionError("le score ne doit pas appeler compliance")

    monkeypatch.setattr(lp, "compliance_failures", boom)
    monkeypatch.setattr(lp, "compliance_regressions", boom)
    assert isinstance(sel.score(_real(thin=1, rooms=[_r("l", "living", 0, 0, 5, 4)]), {"l": 20.0}), float)


# --- Choix -----------------------------------------------------------------------------

def test_picking_from_nothing_yields_nothing():
    assert sel.pick([], {}, seed=1) is None


def test_the_same_seed_always_picks_the_same_plan():
    pool = _rich_pool()
    targets = lp._targets(RICH["rooms"])
    assert sel.pick(pool, targets, seed=42) is sel.pick(pool, targets, seed=42)


def test_different_seeds_give_different_arrangements():
    """Le but : régénérer une maison n'en redonne pas la même, quand il en existe plusieurs."""
    pool, targets = _diverse_pool(), lp._targets(DIVERSE["rooms"])
    assert len({sel.pick(pool, targets, seed=s).code for s in range(20)}) >= 3


def test_quality_comes_first_when_the_alternatives_are_much_worse():
    """Un programme dont un seul arrangement respecte les côtés minimaux garde ce plan.

    Cas mesuré : « 3 chambres, 2 salles de bain, garage » sur 14 x 10 m. L'arrangement classique
    n'a aucune pièce sous son minimum, les quatre autres en ont cinq chacun.
    """
    cands = [_real(thin=0, code="A", raw="A")] + [_real(thin=5, code=c, raw=c) for c in "BCDE"]
    assert {sel.pick(cands, {}, seed=s).code for s in range(60)} == {"A"}


def test_the_tolerance_knob_trades_quality_for_variety(monkeypatch):
    cands = [_real(thin=0, code="A", raw="A")] + [_real(thin=5, code=c, raw=c) for c in "BCDE"]
    monkeypatch.setenv("LAYOUT_TOLERANCE", "6")
    assert len({sel.pick(cands, {}, seed=s).code for s in range(60)}) >= 3


@pytest.mark.parametrize("bad", ["", "abc", "-1", "21", "nan"])
def test_an_invalid_tolerance_falls_back_to_the_default(monkeypatch, bad):
    monkeypatch.setenv("LAYOUT_TOLERANCE", bad)
    assert sel.tolerance() == sel.TOLERANCE


def test_a_valid_tolerance_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("LAYOUT_TOLERANCE", "2.5")
    assert sel.tolerance() == 2.5
    monkeypatch.delenv("LAYOUT_TOLERANCE")
    assert sel.tolerance() == sel.TOLERANCE


def test_every_pick_stays_within_the_tolerance_of_the_best_score():
    pool, targets = _diverse_pool(), lp._targets(DIVERSE["rooms"])
    best = min(sel.score(r, targets) for r in pool)
    for seed in range(30):
        assert sel.score(sel.pick(pool, targets, seed=seed), targets) <= best + sel.TOLERANCE + 1e-9


def test_the_draw_is_over_distinct_arrangements_not_over_plans():
    """Un arrangement qui fournit trois plans ne doit pas être tiré trois fois plus souvent."""
    many = [_real(code="A", raw="A") for _ in range(3)] + [_real(code="B", raw="B")]
    picks = [sel.pick(many, {}, seed=s).code for s in range(400)]
    assert 0.35 < picks.count("A") / len(picks) < 0.65


def test_picking_does_not_mutate_the_candidates():
    pool, targets = _rich_pool(), lp._targets(RICH["rooms"])
    before = [(r.code, canonical_hash(r.rooms)) for r in pool]
    sel.pick(pool, targets, seed=3)
    assert [(r.code, canonical_hash(r.rooms)) for r in pool] == before


def test_the_remembered_arrangement_wins_if_it_is_close_to_the_best():
    cands = [_real(thin=0, code="A", raw="A"), _real(thin=1, code="B", raw="B")]
    assert all(sel.pick(cands, {}, seed=s, prefer="B").raw_code == "B" for s in range(10))   # 1 < 2 : tolère


def test_the_remembered_arrangement_is_dropped_if_it_is_much_worse():
    cands = [_real(thin=0, code="A", raw="A"), _real(thin=5, code="B", raw="B")]
    assert all(sel.pick(cands, {}, seed=s, prefer="B").raw_code == "A" for s in range(10))


def test_an_absent_remembered_arrangement_falls_back_to_the_normal_draw():
    cands = [_real(code="A", raw="A"), _real(code="B", raw="B")]
    assert sel.pick(cands, {}, seed=1, prefer="Z").raw_code in {"A", "B"}


def test_selected_plans_pass_the_hard_check():
    w, d = lp._plot(RICH["width"], RICH["depth"], 0.1, 1.6)
    for seed in range(6):
        chosen = sel.select(RICH["rooms"], RICH["width"], RICH["depth"], seed=seed)
        assert chosen is not None and lp.hard_check(chosen.rooms, w, d) is None


def test_a_plot_too_small_selects_nothing():
    assert sel.select(RICH["rooms"], 4.0, 4.0, seed=1) is None


# --- Interrupteur ----------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, "off"), ("", "off"), ("off", "off"), ("banana", "off"), ("  OFF ", "off"),
    ("on", "on"), ("ON", "on"), ("1", "on"), ("true", "on"), ("yes", "on"), (" on ", "on"),
    ("shadow", "shadow"), ("SHADOW", "shadow"),
])
def test_mode_reads_the_environment_and_defaults_to_off(monkeypatch, value, expected):
    if value is not None:
        monkeypatch.setenv("LAYOUT_VARIANTS", value)
    assert sel.mode() == expected


def test_no_variant_is_chosen_unless_the_flag_is_on(monkeypatch):
    assert sel.choose_variant({}) is None
    monkeypatch.setenv("LAYOUT_VARIANTS", "shadow")
    assert sel.choose_variant({}) is None


def test_the_variant_carries_the_zoned_parti_and_a_valid_seed(monkeypatch):
    monkeypatch.setenv("LAYOUT_VARIANTS", "on")
    v = sel.choose_variant({})
    assert v["parti"] == "zoned" and lo.normalize_variant(v) == v


def test_the_seed_can_be_fixed_by_constraint_then_by_environment(monkeypatch):
    monkeypatch.setenv("LAYOUT_VARIANTS", "on")
    monkeypatch.setenv("LAYOUT_SEED", "77")
    assert sel.choose_variant({"layout_seed": 5})["seed"] == 5
    assert sel.choose_variant({})["seed"] == 77


@pytest.mark.parametrize("bad", [True, -1, 2**31, "7", 1.5, None])
def test_an_invalid_seed_is_replaced_by_a_random_valid_one(monkeypatch, bad):
    monkeypatch.setenv("LAYOUT_VARIANTS", "on")
    seeds = {sel.choose_variant({"layout_seed": bad})["seed"] for _ in range(6)}
    assert all(isinstance(s, int) and 0 <= s <= 2**31 - 1 for s in seeds)
    assert len(seeds) > 1                                     # tirage aléatoire, pas une valeur fixe


def test_an_invalid_environment_seed_is_ignored(monkeypatch):
    monkeypatch.setenv("LAYOUT_VARIANTS", "on")
    monkeypatch.setenv("LAYOUT_SEED", "not-a-number")
    assert 0 <= sel.choose_variant({})["seed"] <= 2**31 - 1


# --- Enregistrement, repli ----------------------------------------------------------------------

def test_the_zoned_parti_is_reachable_through_pack_house_and_annotates_its_arrangement():
    out = lo.pack_house([dict(r) for r in RICH["rooms"]], RICH["width"], RICH["depth"], grid=0.1, min_side=1.6,
                        variant={"parti": "zoned", "seed": 3})
    assert len({r["_arr"] for r in out}) == 1 and re.match(r"^night:", out[0]["_arr"])
    assert sorted(r["id"] for r in out if r["type"] != "hallway") == sorted(
        r["id"] for r in RICH["rooms"] if r["type"] != "hallway")


def test_the_parti_is_found_in_a_fresh_interpreter_without_importing_the_module():
    """Import tardif : `layout_select` importe `layout_opt`, un import au chargement serait circulaire."""
    app_dir = str(Path(__file__).resolve().parents[1])
    code = (
        f"import sys; sys.path.insert(0, {app_dir!r})\n"
        "from app.layout_opt import pack_house\n"
        "rooms=[{'id':'a','type':'living','area_m2':20},{'id':'b','type':'kitchen','area_m2':9},"
        "{'id':'c','type':'bedroom','area_m2':12},{'id':'d','type':'bathroom','area_m2':5}]\n"
        "out = pack_house(rooms, 10.0, 8.0, grid=0.1, min_side=1.6, variant={'parti':'zoned','seed':1})\n"
        "print(len(out))"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert int(res.stdout.strip()) >= 4


def test_an_unavailable_parti_is_not_a_value_error():
    assert not issubclass(lo.PartiUnavailable, ValueError)     # sinon /v1/* répondrait 422 au lieu de replier


def test_a_plot_the_parti_cannot_realize_raises_partiunavailable():
    with pytest.raises(lo.PartiUnavailable):
        lo.pack_house([dict(r) for r in RICH["rooms"]], 4.0, 4.0, variant={"parti": "zoned", "seed": 1})


def _plan(**extra):
    return {
        "version": "1.0", "units": "m",
        "floor": {"level": 0, "height_m": 2.7, "bounds": {"width": 11.0, "depth": 11.5}},
        "walls": [], "openings": [],
        "rooms": [{"id": r["id"], "type": r["type"], "name": r["type"], "polygon": []} for r in RICH["rooms"]],
        **extra,
    }


def test_adapt_falls_back_to_the_classic_when_the_parti_cannot_realize_the_plan(monkeypatch):
    def refuse(*a, **k):
        raise lo.PartiUnavailable("non")

    monkeypatch.setitem(lo._PARTIS, "zoned", refuse)
    with_layout = adapt({"plan_document": _plan(layout={"parti": "zoned", "seed": 4}), "parcel": {}, "rules": {}})
    classic = adapt({"plan_document": _plan(), "parcel": {}, "rules": {}})
    assert "layout" not in with_layout["plan_document"]                         # aucun parti annoncé à tort
    assert canonical_hash(with_layout["plan_document"]["rooms"]) == canonical_hash(classic["plan_document"]["rooms"])


def test_adapt_records_the_arrangement_and_strips_the_internal_marker():
    out = adapt({"plan_document": _plan(layout={"parti": "zoned", "seed": 4}), "parcel": {}, "rules": {}})
    layout = out["plan_document"]["layout"]
    assert layout["parti"] == "zoned" and layout["seed"] == 4 and lo._ARRANGEMENT.match(layout["arr"])
    assert "_arr" not in json.dumps(out["plan_document"])


def test_the_recorded_arrangement_is_reproduced_whatever_the_seed_says():
    """Retouche : la graine seule tirerait un autre arrangement ; l'arrangement mémorisé le retient."""
    first = adapt({"plan_document": _plan(layout={"parti": "zoned", "seed": 4}), "parcel": {}, "rules": {}})
    arr = first["plan_document"]["layout"]["arr"]
    for other_seed in (0, 1, 2, 3, 5, 6):
        again = adapt({"plan_document": _plan(layout={"parti": "zoned", "seed": other_seed, "arr": arr}),
                       "parcel": {}, "rules": {}})
        assert again["plan_document"]["layout"]["arr"] == arr, other_seed


def test_without_the_recorded_arrangement_other_seeds_do_change_the_house(monkeypatch):
    """Sur un programme qui a plusieurs arrangements acceptables, la graine change la maison."""
    plan = {"version": "1.0", "units": "m", "walls": [], "openings": [],
            "floor": {"level": 0, "height_m": 2.7, "bounds": {"width": DIVERSE["width"], "depth": DIVERSE["depth"]}},
            "rooms": [{"id": r["id"], "type": r["type"], "name": r["type"], "polygon": []} for r in DIVERSE["rooms"]]}
    arrs = {adapt({"plan_document": {**plan, "layout": {"parti": "zoned", "seed": s}}, "parcel": {}, "rules": {}})
            ["plan_document"]["layout"]["arr"] for s in range(12)}
    assert len(arrs) >= 2


# --- vectorize ------------------------------------------------------------------------------------

_LAYOUT = {"width": 12.0, "depth": 10.0, "height_m": 2.7, "walls": [], "openings": [],
           "rooms": [dict(r, area=r["area_m2"]) for r in
                     lo.pack_house([dict(r) for r in RICH["rooms"]], 12.0, 10.0, grid=0.1, min_side=1.6)]}


def test_vectorize_adds_nothing_when_the_flag_is_off():
    assert "layout" not in vectorize({"layout": _LAYOUT, "building_spec": {}})["plan_document"]


def test_vectorize_draws_the_variant_at_generation_when_the_flag_is_on(monkeypatch):
    monkeypatch.setenv("LAYOUT_VARIANTS", "on")
    out = vectorize({"layout": _LAYOUT, "building_spec": {"constraints": {"layout_seed": 9}}})
    assert out["plan_document"]["layout"] == {"parti": "zoned", "seed": 9}


def test_a_variant_already_in_the_layout_wins_over_the_flag(monkeypatch):
    monkeypatch.setenv("LAYOUT_VARIANTS", "on")
    out = vectorize({"layout": {**_LAYOUT, "variant": {"parti": "zoned", "seed": 3}},
                     "building_spec": {"constraints": {"layout_seed": 9}}})
    assert out["plan_document"]["layout"]["seed"] == 3


def test_shadow_mode_logs_but_never_changes_the_plan(monkeypatch, caplog):
    monkeypatch.setenv("LAYOUT_VARIANTS", "shadow")
    with caplog.at_level(logging.INFO, logger="aai.layout"):
        out = vectorize({"layout": _LAYOUT, "building_spec": {}})
    assert "layout" not in out["plan_document"]
    events = [json.loads(r.message) for r in caplog.records if r.name == "aai.layout"]
    assert events and events[0]["event"] == "layout_shadow"
    assert {"classes", "distinct_arrangements", "picked", "thin_classic", "thin_zoned", "ms"} <= set(events[0])


def test_shadow_mode_never_breaks_a_generation(monkeypatch, caplog):
    monkeypatch.setenv("LAYOUT_VARIANTS", "shadow")
    monkeypatch.setattr(sel, "pool", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("panne")))
    with caplog.at_level(logging.WARNING, logger="aai.layout"):
        out = vectorize({"layout": _LAYOUT, "building_spec": {}})
    assert "plan_document" in out and any("layout_shadow failed" in r.message for r in caplog.records)


def test_shadow_and_off_leave_the_plan_byte_identical(monkeypatch):
    baseline = vectorize({"layout": _LAYOUT, "building_spec": {}})
    monkeypatch.setenv("LAYOUT_VARIANTS", "shadow")
    assert vectorize({"layout": _LAYOUT, "building_spec": {}}) == baseline


# --- Pipeline de bout en bout ---------------------------------------------------------------------

BRIEF = "Maison 3 chambres, 2 salles de bain, séjour, cuisine et garage"
CONSTRAINTS = {"parcel_width_m": 14, "parcel_depth_m": 10}
# Un brief dont la sélection varie avec la graine (mesuré : cinq arrangements). Le précédent n'en a qu'un.
BRIEF_VARIED = "Maison 2 chambres, séjour, cuisine, salle de bain et garage"
CONSTRAINTS_VARIED = {"parcel_width_m": 12, "parcel_depth_m": 9}


def _run(monkeypatch, mode, seed=None, brief=BRIEF, constraints=CONSTRAINTS):
    monkeypatch.setenv("LAYOUT_VARIANTS", mode)
    if seed is None:
        monkeypatch.delenv("LAYOUT_SEED", raising=False)
    else:
        monkeypatch.setenv("LAYOUT_SEED", str(seed))
    return _pipeline(PipelineRequest(brief=brief, constraints=dict(constraints)))


def test_the_pipeline_carries_a_zoned_parti_when_the_flag_is_on(monkeypatch):
    out = _run(monkeypatch, "on", seed=7)
    layout = out["plan_document"]["layout"]
    assert layout["parti"] == "zoned" and layout["seed"] == 7 and lo._ARRANGEMENT.match(layout["arr"])


def test_the_pipeline_is_unchanged_when_the_flag_is_off(monkeypatch):
    out = _run(monkeypatch, "off")
    assert "layout" not in out["plan_document"]


def test_a_zoned_plan_tiles_the_plot_and_keeps_every_room(monkeypatch):
    classic = _run(monkeypatch, "off")["plan_document"]
    zoned = _run(monkeypatch, "on", seed=7)["plan_document"]
    b = zoned["floor"]["bounds"]
    area = 0.0
    for room in zoned["rooms"]:
        xs = [p["x"] for p in room["polygon"]]
        ys = [p["y"] for p in room["polygon"]]
        area += (max(xs) - min(xs)) * (max(ys) - min(ys))
    assert abs(area - b["width"] * b["depth"]) < 1e-2
    assert sorted(r["id"] for r in zoned["rooms"]) == sorted(r["id"] for r in classic["rooms"])


def test_a_zoned_plan_never_scores_lower_than_the_classic(monkeypatch):
    """Le contrôle exact interdit toute régression de conformité."""
    classic = _run(monkeypatch, "off")["compliance"]["score"]
    for seed in (1, 2, 3):
        assert _run(monkeypatch, "on", seed=seed)["compliance"]["score"] >= classic


def test_the_same_seed_gives_the_same_house_and_other_seeds_give_others(monkeypatch):
    def house(seed):
        out = _run(monkeypatch, "on", seed=seed, brief=BRIEF_VARIED, constraints=CONSTRAINTS_VARIED)
        return canonical_hash(out["plan_document"]["rooms"])

    assert house(1) == house(1)
    assert len({house(s) for s in range(1, 7)}) >= 2


def test_a_program_with_one_workable_arrangement_keeps_its_house_whatever_the_seed(monkeypatch):
    """Qualité d'abord : ce brief n'a qu'un arrangement sans pièce sous son minimum."""
    houses = {canonical_hash(_run(monkeypatch, "on", seed=s)["plan_document"]["rooms"]) for s in range(1, 5)}
    assert len(houses) == 1


# --- Déterminisme entre processus ---------------------------------------------------------------

def test_the_selection_does_not_depend_on_the_hash_seed():
    here = Path(__file__).resolve()
    script = (
        f"import sys; sys.path.insert(0, {str(here.parents[1])!r}); sys.path.insert(0, {str(here.parent)!r})\n"
        "import hashlib, json\n"
        "from app import layout_select as sel\n"
        "from test_layout_golden import canonical_hash\n"
        "from test_layout_invariants import CORPUS\n"
        f"p = CORPUS[{CORPUS.index(RICH)}]\n"
        "out = [(s, sel.select(p['rooms'], p['width'], p['depth'], seed=s)) for s in range(8)]\n"
        "print(hashlib.sha256(json.dumps([(s, r.raw_code, canonical_hash(r.rooms)) for s, r in out]).encode()).hexdigest())\n"
    )
    digests = set()
    for hash_seed in ("0", "1", "4242"):
        out = subprocess.run([sys.executable, "-c", script], env={**os.environ, "PYTHONHASHSEED": hash_seed},
                             capture_output=True, text=True, check=True)
        digests.add(out.stdout.strip())
    assert len(digests) == 1, digests


# --- Contrat de schéma ------------------------------------------------------------------------------

def test_the_arrangement_pattern_matches_between_code_and_schema():
    layout = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]["layout"]
    assert layout["properties"]["arr"]["pattern"] == lo._ARRANGEMENT.pattern


def test_normalize_variant_keeps_a_valid_arrangement_and_refuses_a_bad_one():
    good = {"parti": "zoned", "seed": 1, "arr": "night:N|day:S|hall:H|garage:E"}
    assert lo.normalize_variant(good) == good
    for bad in ("night:N", "night:N|day:S|hall:H|garage:X", 5, "night:N|day:S|hall:H|garage:E; DROP"):
        with pytest.raises(ValueError):
            lo.normalize_variant({**good, "arr": bad})


def test_the_annotation_is_the_raw_code_so_that_a_retouch_reproduces_the_same_house():
    """`_arr` est le code brut (avec orientation), pas le code canonique : sinon un plan miroir serait perdu."""
    pool = _diverse_pool()
    mirrored = [r for r in pool if r.raw_code != r.code]
    assert mirrored, "le corpus doit contenir un arrangement dont le code brut diffère du canonique"
    target = mirrored[0].raw_code
    out = lo.pack_house([dict(r) for r in DIVERSE["rooms"]], DIVERSE["width"], DIVERSE["depth"], grid=0.1,
                        min_side=1.6, variant={"parti": "zoned", "seed": 0, "arr": target})
    assert {r["_arr"] for r in out} == {target}
