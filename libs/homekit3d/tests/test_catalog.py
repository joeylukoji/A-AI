from __future__ import annotations

import json

import pytest

from homekit3d.catalog import DEFAULT_MANIFEST

# Tailles réelles attendues (m) : la normalisation par rôle doit ramener CHAQUE modèle de CHAQUE pack à peu près là.
REAL = {"bed.double": ("length", 1.7, 2.4), "bed.single": ("length", 1.7, 2.3), "sofa": ("length", 1.5, 2.4),
        "kitchen.fridge": ("height", 1.5, 2.1), "wardrobe": ("height", 1.7, 2.5), "toilet": ("length", 0.55, 0.85),
        "table.dining": ("length", 0.9, 2.4), "armchair": ("length", 0.7, 1.25), "bathtub": ("length", 1.4, 2.0)}


def test_every_file_of_the_manifest_exists(catalog):
    assert catalog.assets
    missing = [a.id for a in catalog.assets.values() if not a.path.exists()]
    assert not missing, missing[:5]


def test_every_polyhaven_model_has_its_license_record():
    root = DEFAULT_MANIFEST.parent.parent / "assets" / "polyhaven"
    for glb in root.glob("*.glb"):
        record = json.loads(glb.with_suffix(".license.json").read_text(encoding="utf-8"))
        assert record["license"] == "CC0-1.0" and record["authors"] and record["source"].startswith("https://polyhaven.com/")


def test_every_asset_file_is_in_the_manifest(catalog):
    listed = {a.path.resolve() for a in catalog.assets.values()}
    on_disk = {p.resolve() for p in (DEFAULT_MANIFEST.parent.parent / "assets").rglob("*.glb")}
    assert on_disk == listed


# Les modèles qui ne sont pas CC0 : Free Art License 1.3 (copyleft) et CC-BY 4.0 (citer l'auteur) ; voir ATTRIBUTION.md.
NOT_CC0 = {"sh3d-c": "Free Art License 1.3", "sh3d-luca": "Free Art License 1.3", "sh3d-scopia": "CC-BY-4.0",
           "sh3d-kator": "CC-BY-4.0", "sh3d-bby": "CC-BY-4.0", "vehicles": "CC-BY-4.0 (Sketchfab, non revérifiée)"}


def test_every_pack_has_a_known_license_and_a_credit(catalog):
    for pack, meta in json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))["packs"].items():
        assert meta["license"] == NOT_CC0.get(pack, "CC0-1.0") and meta["author"] and meta["source"].startswith("https://"), pack
    assert {a.pack for a in catalog.assets.values() if a.license != "CC0-1.0"} <= set(NOT_CC0)


def test_the_roles_needed_to_furnish_a_house_all_exist(catalog):
    needed = {"bed.double", "bed.single", "nightstand", "wardrobe", "sofa", "sofa.corner", "armchair", "table.coffee",
              "tv.console", "table.dining", "chair.dining", "desk", "kitchen.base", "kitchen.sink", "kitchen.stove",
              "kitchen.fridge", "toilet", "sink.bath", "bathtub", "shower", "lamp.floor", "lamp.table", "plant", "rug",
              "picture", "mirror", "bookcase", "coat.rack"}
    assert needed <= set(catalog.roles())


@pytest.mark.parametrize("role", sorted(REAL))
def test_each_role_is_normalised_to_a_real_world_size_in_every_pack(catalog, role):
    basis, lo, hi = REAL[role]
    for a in catalog.find(role):
        value = max(a.footprint) if basis == "length" else a.height
        assert lo <= value <= hi, (a.id, value)


def test_scales_and_dimensions_are_sane(catalog):
    for a in catalog.assets.values():
        assert a.scale > 0 and all(v > 0 for v in a.size), a.id
        assert all(abs(a.fit_size[i] - a.size[i] * a.scale) < 0.01 for i in range(3)), a.id
        assert a.bbox_max[0] > a.bbox_min[0] and a.tris > 0


def test_unused_models_are_never_returned(catalog):
    assert all(not a.unused for r in catalog.roles() for a in catalog.find(r))
    assert catalog.find("unused") == []


def test_find_filters_by_room_tags_and_footprint(catalog):
    assert all("bedroom" in a.rooms for a in catalog.find("nightstand", room="bedroom"))
    assert all("cozy" in a.tags for a in catalog.find("sofa", tags=["cozy"]))
    small = catalog.find("table.dining", max_footprint=(1.0, 1.0))
    assert all(a.footprint[0] <= 1.0 and a.footprint[1] <= 1.0 for a in small)
    assert catalog.find("sofa", tags=["no-such-tag"]) == []


def test_pick_is_deterministic_and_varies_with_the_seed(catalog):
    a = [catalog.pick("chair.dining", seed=s).id for s in range(30)]
    assert a == [catalog.pick("chair.dining", seed=s).id for s in range(30)]
    assert len(set(a)) > 1


def test_pick_prefers_the_requested_pack_and_style(catalog):
    assert all(catalog.pick("sofa", prefer_pack="kaykit-furniture", seed=s).pack == "kaykit-furniture" for s in range(10))
    assert all("cozy" in catalog.pick("sofa", style=["cozy"], seed=s).tags for s in range(10))
    assert catalog.pick("sofa", prefer_pack="no-such-pack", seed=1) is not None          # repli, jamais d'erreur


def test_pick_returns_none_for_an_unknown_role(catalog):
    assert catalog.pick("dragon") is None and catalog.pick_fit("dragon", (1, 1)) is None


def test_pick_fit_chooses_among_the_closest_sizes(catalog):
    wide = catalog.pick_fit("sofa", (2.6, 1.0), top=1, seed=0)
    narrow = catalog.pick_fit("sofa", (1.6, 0.8), top=1, seed=0)
    assert wide.footprint[0] >= narrow.footprint[0]


def test_summary_lists_usable_roles_only(catalog):
    s = catalog.summary()
    assert "unused" not in s and s["sofa"] == sorted(s["sofa"])
    assert "bathtub" not in catalog.summary(rooms=["bedroom"])


def test_attributions_credit_only_the_packs_used(catalog):
    a = catalog.attributions(["kenney-furniture/bedDouble"])
    assert [x["pack"] for x in a] == ["kenney-furniture"] and a[0]["license"] == "CC0-1.0"
    assert {a["pack"] for a in catalog.attributions()} == {"kenney-furniture", "kaykit-furniture", "kaykit-restaurant", "polyhaven", "sh3d-b", "sh3d-c", "sh3d-scopia", "sh3d-kator", "sh3d-bby", "sh3d-luca", "vehicles"}


def test_center_offset_points_at_the_footprint_centre_on_the_floor(catalog):
    a = catalog.get("kenney-furniture/bedDouble")
    ox, oy, oz = a.center_offset
    assert abs(ox - (a.bbox_min[0] + a.bbox_max[0]) / 2) < 1e-9 and oy == a.bbox_min[1]


def test_find_by_room_excludes_roles_that_do_not_belong_there(catalog):
    assert catalog.find("plant", room="bedroom") and catalog.find("plant", room="kitchen") == []
    assert catalog.find("toilet", room="living") == []


def test_the_style_wins_over_a_slightly_closer_footprint(catalog):
    """Un style réaliste ne doit pas retomber sur un jouet parce que celui-ci a une emprise un peu plus proche."""
    for seed in range(20):
        asset = catalog.pick_fit("sofa", (1.9, 0.8), style=["realistic"], seed=seed)
        assert "realistic" in asset.tags, asset.id


def test_the_realistic_packs_carry_real_sizes_and_the_realistic_tag(catalog):
    for a in catalog.assets.values():
        if a.pack in ("sh3d-b", "sh3d-c", "polyhaven", "sh3d-scopia", "sh3d-kator", "sh3d-bby", "sh3d-luca", "vehicles"):
            assert "realistic" in a.tags and a.scale == pytest.approx(1.0) or a.id == "polyhaven/modern_wooden_cabinet", a.id
