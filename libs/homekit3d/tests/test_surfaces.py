from __future__ import annotations

import json
from dataclasses import replace

import pytest

from homekit3d.plan import Style
from homekit3d.stylist import STYLES
from homekit3d.surfaces import TEXTURE_DIR, TILE_M, WOOD_ROOMS, TILED_ROOMS, luminance, surface_for, textures_available


def test_every_texture_has_its_color_and_relief_maps_a_real_size_and_a_cc0_record():
    for texture, tile in TILE_M.items():
        assert (TEXTURE_DIR / f"{texture}_diff.jpg").stat().st_size > 10_000, texture
        assert (TEXTURE_DIR / f"{texture}_nor.jpg").stat().st_size > 10_000, texture
        record = json.loads((TEXTURE_DIR / f"{texture}.license.json").read_text(encoding="utf-8"))
        assert record["license"] == "CC0-1.0" and record["authors"]
        assert tile == pytest.approx(record["size_mm"][0] / 1000, rel=0.05), texture      # l'échelle vient de Poly Haven


def test_walls_are_textured_and_tinted_with_the_palette_of_the_style():
    for name, style in STYLES.items():
        assert surface_for("wall_int", style).tint == style.wall_interior, name
        assert surface_for("wall_ext", style).tint == style.wall_exterior, name
    assert surface_for("wall_int", STYLES["moderne"]).texture != surface_for("wall_ext", STYLES["moderne"]).texture


def test_light_floors_get_a_light_wood_and_dark_floors_a_dark_wood():
    light = replace(Style(), floors={"living": (0.9, 0.8, 0.6)})
    dark = replace(Style(), floors={"living": (0.25, 0.15, 0.1)})
    assert surface_for("floor:living", light).texture == "oak_wood_planks"
    assert surface_for("floor:living", dark).texture == "old_wood_floor"
    assert luminance((1, 1, 1)) == pytest.approx(1.0)


@pytest.mark.parametrize("room", sorted(WOOD_ROOMS | TILED_ROOMS | {"garage"}))
def test_every_room_type_has_a_floor(room):
    surface = surface_for(f"floor:{room}", STYLES["moderne"])
    assert surface and textures_available(surface)
    assert (surface.tint is not None) == (room in TILED_ROOMS)          # les carreaux prennent la couleur du style, le bois non


def test_frames_glass_and_slab_stay_plain():
    for material in ("trim", "door", "glass", "handle", "slab", "garage", "plinth"):
        assert surface_for(material, STYLES["moderne"]) is None
