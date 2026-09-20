"""Étape B du chantier « partis » : faire voyager la topologie, sans rien changer.

`plan_adapt.adapt` re-pave tout depuis les types et les aires : `pack_house` ne
lit jamais les polygones qu'on lui passe. Sans descripteur de variante, toute
topologie choisie à la génération serait donc effacée à l'étape suivante — et la
retouche par chat, qui passe par `adapt`, redessinerait toute la maison.

Ces tests vérifient la plomberie avec un parti factice (`probe`) qui délègue au
gabarit classique : aucun vrai parti n'existe encore, et c'est voulu. Ils
prouvent que le descripteur est validé, dispatché, conservé de bout en bout, et
qu'il n'ajoute **rien** au plan quand le parti est classique.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import layout_opt, vectorize
from app.layout_opt import (
    CLASSIC,
    UnknownParti,
    normalize_variant,
    optimize_rooms,
    pack_house,
    register_parti,
)
from app.main import PipelineRequest, _pipeline, app
from app.plan_adapt import adapt
from test_layout_golden import canonical_hash
from test_layout_invariants import CORPUS, GENERATE

client = TestClient(app)

SCHEMA = Path(__file__).resolve().parents[3] / "packages" / "plan-schema" / "plan-document.schema.json"


@pytest.fixture
def probe(monkeypatch):
    """Parti factice : enregistre ses appels et délègue au gabarit classique."""
    calls: list[dict[str, Any]] = []

    def fn(rooms, width, depth, grid, min_side, variant):
        calls.append({"variant": variant, "width": width, "depth": depth, "n": len(rooms)})
        return pack_house(rooms, width, depth, grid=grid, min_side=min_side)

    monkeypatch.setitem(layout_opt._PARTIS, "probe", fn)
    return calls


# --- Validation du descripteur ----------------------------------------------

@pytest.mark.parametrize("value", [None, {}, {"parti": "classic"}, {"parti": "classic", "seed": 9}])
def test_classic_descriptors_normalise_to_none(value):
    assert normalize_variant(value) is None


def test_a_valid_descriptor_is_normalised_with_a_default_seed():
    assert normalize_variant({"parti": "central-hall"}) == {"parti": "central-hall", "seed": 0}
    assert normalize_variant({"parti": "a_b-1", "seed": 3}) == {"parti": "a_b-1", "seed": 3}


def test_unknown_keys_are_dropped_not_propagated():
    """Le descripteur vient d'un document libre : on ne relaie que ce qu'on connaît."""
    assert normalize_variant({"parti": "p", "seed": 1, "extra": "x"}) == {"parti": "p", "seed": 1}


@pytest.mark.parametrize(
    "bad",
    [
        "central-hall",                          # pas un objet
        ["parti"],
        {"parti": 3},                            # nom non textuel
        {"parti": ""},
        {"parti": "Central"},                    # majuscule
        {"parti": "a b"},
        {"parti": "../etc"},
        {"parti": "x" * 33},                     # trop long
        {"parti": "p", "seed": -1},
        {"parti": "p", "seed": 2**31},
        {"parti": "p", "seed": 1.5},
        {"parti": "p", "seed": "3"},
        {"parti": "p", "seed": True},            # bool est un int en Python
    ],
)
def test_aberrant_descriptors_are_rejected(bad):
    with pytest.raises(ValueError):
        normalize_variant(bad)


def test_register_parti_refuses_classic_and_bad_names():
    for name in (CLASSIC, "", "Bad", "a b", "x" * 33):
        with pytest.raises(ValueError):
            register_parti(name)


# --- pack_house / optimize_rooms --------------------------------------------

def test_explicit_classic_is_identical_to_the_default():
    for program in CORPUS[:25]:
        rooms = lambda: [dict(r) for r in program["rooms"]]  # noqa: E731
        default = pack_house(rooms(), program["width"], program["depth"], **GENERATE)
        explicit = pack_house(rooms(), program["width"], program["depth"], **GENERATE, variant={"parti": "classic"})
        none = pack_house(rooms(), program["width"], program["depth"], **GENERATE, variant=None)
        assert canonical_hash(default) == canonical_hash(explicit) == canonical_hash(none)


def test_unknown_parti_raises_a_value_error():
    with pytest.raises(UnknownParti):
        pack_house([{"id": "a", "type": "living", "area_m2": 20}], 8, 8, variant={"parti": "nope"})
    assert issubclass(UnknownParti, ValueError)  # sinon /v1/* répond 500 au lieu de 422


def test_registered_parti_receives_the_call_and_its_result_is_returned(probe):
    rooms = [{"id": "a", "type": "living", "area_m2": 20}, {"id": "b", "type": "kitchen", "area_m2": 9}]
    out = pack_house(rooms, 9, 8, grid=0.1, min_side=1.6, variant={"parti": "probe", "seed": 5})
    assert probe == [{"variant": {"parti": "probe", "seed": 5}, "width": 9, "depth": 8, "n": 2}]
    assert {r["id"] for r in out} == {"a", "b"}


def test_optimize_rooms_forwards_the_variant(probe):
    rooms = [{"id": "a", "type": "living", "area_m2": 20}, {"id": "b", "type": "kitchen", "area_m2": 9}]
    optimize_rooms(rooms, 9, 8, None, grid=0.1, min_side=2.0, variant={"parti": "probe", "seed": 2})
    assert probe and probe[0]["variant"] == {"parti": "probe", "seed": 2}


def test_empty_program_short_circuits_before_any_dispatch(probe):
    assert pack_house([], 9, 8, variant={"parti": "probe"}) == []
    assert probe == []


# --- adapt : le descripteur survit ------------------------------------------

def _plan(**extra: Any) -> dict[str, Any]:
    return {
        "version": "1.0",
        "units": "m",
        "floor": {"level": 0, "height_m": 2.7, "bounds": {"width": 10.0, "depth": 8.0}},
        "walls": [],
        "rooms": [
            {"id": "r1", "type": "living", "name": "Séjour", "polygon": []},
            {"id": "r2", "type": "kitchen", "name": "Cuisine", "polygon": []},
            {"id": "r3", "type": "bedroom", "name": "Chambre", "polygon": []},
        ],
        "openings": [],
        **extra,
    }


def test_adapt_keeps_the_layout_descriptor_and_repacks_with_it(probe):
    out = adapt({"plan_document": _plan(layout={"parti": "probe", "seed": 7}), "parcel": {}, "rules": {}})
    assert out["plan_document"]["layout"] == {"parti": "probe", "seed": 7}
    assert [c["variant"] for c in probe] == [{"parti": "probe", "seed": 7}]


def test_adapt_adds_no_layout_field_for_the_classic_parti(probe):
    """Le plan classique reste identique octet pour octet à celui d'avant."""
    for layout in (None, {"parti": "classic"}, {}):
        extra = {} if layout is None else {"layout": layout}
        out = adapt({"plan_document": _plan(**extra), "parcel": {}, "rules": {}})
        assert "layout" not in out["plan_document"]
    assert probe == []


def test_adapt_output_key_set_is_unchanged_for_classic_plans():
    out = adapt({"plan_document": _plan(), "parcel": {}, "rules": {}})
    assert set(out["plan_document"]) == {"version", "units", "floor", "walls", "rooms", "openings", "furniture"}


def test_adapt_is_idempotent_on_the_descriptor(probe):
    first = adapt({"plan_document": _plan(layout={"parti": "probe", "seed": 4}), "parcel": {}, "rules": {}})
    second = adapt({"plan_document": first["plan_document"], "parcel": {}, "rules": {}})
    assert second["plan_document"]["layout"] == {"parti": "probe", "seed": 4}


# --- vectorize ---------------------------------------------------------------

_LAYOUT = {
    "width": 10.0, "depth": 8.0, "height_m": 2.7,
    "rooms": [{"id": "r1", "type": "living", "name": "S", "polygon": [
        {"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 8}, {"x": 0, "y": 8}]}],
    "walls": [], "openings": [],
}


def test_vectorize_carries_the_variant_into_the_plan():
    out = vectorize.vectorize({"layout": {**_LAYOUT, "variant": {"parti": "probe", "seed": 3}}, "building_spec": {}})
    assert out["plan_document"]["layout"] == {"parti": "probe", "seed": 3}


def test_vectorize_adds_nothing_without_a_variant(monkeypatch):
    monkeypatch.setenv("LAYOUT_VARIANTS", "off")
    for variant in (None, {"parti": "classic"}):
        layout = dict(_LAYOUT) if variant is None else {**_LAYOUT, "variant": variant}
        assert "layout" not in vectorize.vectorize({"layout": layout, "building_spec": {}})["plan_document"]


# --- bout en bout : génération -> vectorisation -> adaptation ----------------

def test_a_variant_set_at_generation_survives_the_whole_pipeline(monkeypatch, probe):
    """Le scénario exact que l'ancien code faisait échouer.

    Le parti est posé par l'étage d'implantation (`diffusion.generate`), traverse
    la vectorisation, puis l'adaptation re-pave : elle doit le relire et
    l'appliquer, pas retomber sur le gabarit.
    """
    from app import diffusion

    real_generate = diffusion.generate

    def generate_with_variant(spec, *, image=True):
        gen = real_generate(spec, image=image)
        gen["layout"]["variant"] = {"parti": "probe", "seed": 7}
        return gen

    monkeypatch.setattr(diffusion, "generate", generate_with_variant)
    result = _pipeline(PipelineRequest(brief="Maison 2 chambres, séjour, cuisine, salle de bain",
                                       constraints={"parcel_width_m": 12, "parcel_depth_m": 9}))
    assert result["plan_document"]["layout"] == {"parti": "probe", "seed": 7}
    assert probe and all(c["variant"] == {"parti": "probe", "seed": 7} for c in probe)


def test_the_pipeline_output_is_unchanged_for_the_classic_parti(monkeypatch):
    monkeypatch.setenv("LAYOUT_VARIANTS", "off")
    result = _pipeline(PipelineRequest(brief="Maison 2 chambres, séjour, cuisine, salle de bain",
                                       constraints={"parcel_width_m": 12, "parcel_depth_m": 9}))
    assert "layout" not in result["plan_document"]


# --- API : un descripteur aberrant donne 422, jamais 500 ---------------------

def test_api_adapt_accepts_a_registered_parti(probe):
    res = client.post("/v1/adapt", json={"plan_document": _plan(layout={"parti": "probe", "seed": 1})})
    assert res.status_code == 200, res.text
    assert res.json()["plan_document"]["layout"] == {"parti": "probe", "seed": 1}


@pytest.mark.parametrize("layout", [{"parti": "nope"}, {"parti": "BAD NAME"}, {"parti": "p", "seed": -3}, "x", 7])
def test_api_adapt_answers_422_for_a_bad_descriptor(layout):
    res = client.post("/v1/adapt", json={"plan_document": _plan(layout=layout)})
    assert res.status_code == 422, res.text


def test_api_adapt_is_unchanged_without_a_descriptor():
    res = client.post("/v1/adapt", json={"plan_document": _plan()})
    assert res.status_code == 200
    assert "layout" not in res.json()["plan_document"]


# --- schéma : une seule définition du nom et de la graine ---------------------

def test_schema_declares_the_optional_layout_field_and_stays_strict():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False  # la racine reste stricte
    assert "layout" in schema["properties"]
    assert "layout" not in schema["required"]        # optionnel : plans anciens valides


def test_schema_and_code_agree_on_the_parti_name_and_seed_range():
    layout = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]["layout"]
    assert layout["additionalProperties"] is False
    assert layout["properties"]["parti"]["pattern"] == layout_opt._PARTI_NAME.pattern
    assert layout["properties"]["seed"]["maximum"] == layout_opt._MAX_SEED
    assert layout["properties"]["seed"]["minimum"] == 0
    assert re.match(layout["properties"]["parti"]["pattern"], "central-hall")
