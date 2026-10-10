"""Raster regression tests: the stored geometry must determine the drawing."""

from __future__ import annotations

import base64
import io
from typing import Any

import pytest
from app import diffusion, floorplan_render
from app.plan_adapt import apply_opening_rules, default_rules
from app.plan_geometry import opening_segment
from app.plan_walls import perimeter_and_internal_walls
from PIL import Image, ImageDraw


def _render(
    walls: list[dict[str, Any]],
    openings: list[dict[str, Any]],
    rooms: list[dict[str, Any]] | None = None,
) -> Image.Image:
    encoded = floorplan_render._render_floorplan(rooms or [], walls, openings, 4, 4, furniture=[])
    return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")


def _pixel(image: Image.Image, x: float, y: float) -> tuple[int, int, int]:
    # 4 x 4 m, 600 px floor depth, and the renderer's page margins.
    return image.getpixel((round(88 + x * 150), round(48 + y * 150)))


def _gray(pixel: tuple[int, int, int]) -> bool:
    return max(pixel) - min(pixel) < 12 and max(pixel) < 185


def test_explicit_wall_is_drawn_even_without_room_edges() -> None:
    walls = [
        {
            "id": "partition",
            "a": {"x": 2, "y": 0},
            "b": {"x": 2, "y": 4},
            "thickness_m": 0.15,
        }
    ]
    assert _gray(_pixel(_render(walls, []), 2, 1))
    assert not _gray(_pixel(_render([], []), 2, 1))


def test_empty_walls_do_not_create_a_perimeter() -> None:
    assert not _gray(_pixel(_render([], []), 2, 0))


def test_adjacent_hallway_segments_do_not_create_a_partition() -> None:
    rooms = [
        {
            "id": "h1",
            "type": "hallway",
            "polygon": [
                {"x": 0, "y": 0},
                {"x": 2, "y": 0},
                {"x": 2, "y": 4},
                {"x": 0, "y": 4},
            ],
        },
        {
            "id": "h2",
            "type": "hallway",
            "polygon": [
                {"x": 2, "y": 0},
                {"x": 4, "y": 0},
                {"x": 4, "y": 4},
                {"x": 2, "y": 4},
            ],
        },
    ]
    walls = perimeter_and_internal_walls(rooms, 4, 4)
    assert not _gray(_pixel(_render(walls, [], rooms), 2, 1))


@pytest.mark.parametrize(
    "wall_id,opened,closed",
    [
        ("w_outer_1", (1.5, 0), (2.5, 0)),
        ("w_outer_2", (4, 1.5), (4, 2.5)),
        ("w_outer_3", (2.5, 4), (1.5, 4)),
        ("w_outer_4", (0, 2.5), (0, 1.5)),
    ],
)
def test_door_offset_follows_the_oriented_wall(
    wall_id: str, opened: tuple[float, float], closed: tuple[float, float]
) -> None:
    walls = perimeter_and_internal_walls([], 4, 4)
    opening = {
        "id": "door",
        "type": "door",
        "wall_id": wall_id,
        "offset_m": 1.0,
        "width_m": 1.0,
    }
    image = _render(walls, [opening])
    assert min(_pixel(image, *opened)) > 210
    assert _gray(_pixel(image, *closed))


def test_window_is_visible_at_its_stored_position() -> None:
    walls = perimeter_and_internal_walls([], 4, 4)
    window = {
        "id": "window",
        "type": "window",
        "wall_id": "w_outer_1",
        "offset_m": 1,
        "width_m": 1,
    }
    pixel = _pixel(_render(walls, [window]), 1.5, 0)
    assert pixel[2] > pixel[0] + 20  # blue glass, not solid wall
    assert _gray(_pixel(_render(walls, []), 1.5, 0))


def test_explicit_empty_geometry_is_preserved_in_image_guide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def render(rooms: list, walls: list, openings: list, *args: Any, **kwargs: Any) -> str:
        assert walls == []
        assert openings == []
        assert kwargs["furniture"] == []
        return "png"

    monkeypatch.setattr(diffusion, "_render_floorplan", render)
    monkeypatch.setattr("app.together_image._png_b64_to_jpeg_uri", lambda image, **kw: image)
    assert diffusion._layout_guide_b64([{"id": "room"}], 4, 4, walls=[], openings=[], furniture=[]) == "png"


def test_adaptation_keeps_the_vehicle_door_width() -> None:
    openings = [
        {"id": "entry", "type": "door", "wall_id": "w_outer_3", "width_m": 0.9},
        {"id": "garage", "type": "door", "wall_id": "w_outer_2", "width_m": 2.4},
    ]
    result = apply_opening_rules(openings, default_rules(), 12, 10)
    assert result[0]["width_m"] == 0.9
    assert result[1]["width_m"] == 2.4
    assert openings[1]["width_m"] == 2.4


@pytest.mark.parametrize("offset,width", [(0, 1), (3, 1), (1, 2)])
def test_opening_projection_accepts_zero_offset_and_wall_end(offset: float, width: float) -> None:
    wall = {"a": {"x": 4, "y": 4}, "b": {"x": 0, "y": 4}}
    assert opening_segment(wall, {"offset_m": offset, "width_m": width}) == (
        (4 - offset, 4),
        (4 - offset - width, 4),
    )


@pytest.mark.parametrize(
    "opening",
    [
        {"offset_m": -1, "width_m": 1},
        {"offset_m": 3.5, "width_m": 1},
        {"offset_m": 1, "width_m": 0},
        {"offset_m": float("nan"), "width_m": 1},
        {"offset_m": 1, "width_m": float("inf")},
        {"offset_m": None, "width_m": 1},
    ],
)
def test_invalid_opening_is_not_relocated_into_the_drawing(
    opening: dict[str, Any],
) -> None:
    wall = {"a": {"x": 4, "y": 4}, "b": {"x": 0, "y": 4}}
    assert opening_segment(wall, opening) is None


def test_an_empty_furniture_list_does_not_add_illustrative_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("an empty furniture list must remain empty")

    monkeypatch.setattr(floorplan_render, "_furniture", unexpected)
    rooms = [
        {
            "type": "living",
            "polygon": [
                {"x": 0, "y": 0},
                {"x": 4, "y": 0},
                {"x": 4, "y": 4},
                {"x": 0, "y": 4},
            ],
        }
    ]
    _render([], [], rooms)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_l_shaped_sofa_symbol_stays_in_its_declared_footprint(rotation: int) -> None:
    import math

    image = Image.new("RGB", (800, 800), "white")
    item = {
        "catalog_id": "sofa.lshape",
        "position": {"x": 0, "y": 0},
        "rotation_deg": rotation,
        "size_m": {"w": 2.4, "d": 1.6},
    }
    floorplan_render._draw_catalog_item(
        image, ImageDraw.Draw(image), item, lambda x, y: (400 + x * 100, 400 + y * 100), 100
    )
    angle = math.radians(rotation)
    # This point lies beyond the declared depth, but inside the old extra chaise.
    dx, dy = 0.9, 1.1
    x = round(400 + 100 * (dx * math.cos(angle) - dy * math.sin(angle)))
    y = round(400 + 100 * (dx * math.sin(angle) + dy * math.cos(angle)))
    assert min(image.getpixel((x, y))) > 240


def test_real_adaptation_keeps_garage_opening(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import nlu, plan_adapt, vectorize
    from app.plan_openings import _served_rooms

    monkeypatch.setenv("LAYOUT_SEED", "42")
    monkeypatch.setenv("LAYOUT_VARIANTS", "on")
    monkeypatch.setenv("TOGETHER_PLANNER", "0")
    spec = nlu.parse_brief("Maison 3 chambres, séjour, cuisine, salle de bain, WC et garage", {})
    generated = diffusion.generate(spec, image=False)
    document = vectorize.vectorize({"layout": generated["layout"], "building_spec": spec})["plan_document"]
    final = plan_adapt.adapt({"plan_document": document})["plan_document"]
    by_id = {wall["id"]: wall for wall in final["walls"]}
    doors = []
    for opening in final["openings"]:
        if opening["type"] != "door" or not opening["wall_id"].startswith("w_outer"):
            continue
        served = _served_rooms(by_id[opening["wall_id"]], opening, final["rooms"])
        if served and all(room["type"] == "garage" for room in served):
            doors.append(opening)
    assert doors
    assert any(door["width_m"] >= 2.4 for door in doors)
