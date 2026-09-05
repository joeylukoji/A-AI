from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalog.primitives import (  # noqa: E402
    CATALOG,
    boxes_to_obj,
    default_size,
    parts_for,
    world_boxes,
)
from worker import _stub_build  # noqa: E402


def test_catalog_covers_core_components():
    for cid in (
        "chair.dining",
        "bed.double",
        "bed.single",
        "table.dining",
        "wall.exterior",
        "wall.interior",
    ):
        assert cid in CATALOG
        w, d, h = default_size(cid)
        assert w > 0 and d > 0 and h > 0


def test_chair_has_seat_back_and_legs():
    names = {p["name"] for p in parts_for("chair.dining")}
    assert "seat" in names
    assert "back" in names
    assert any(n.startswith("leg_") for n in names)


def test_world_boxes_rotate_around_instance_origin():
    boxes = world_boxes("table.dining", 3.0, 2.0, 90)
    assert boxes
    cx = sum(b["location"][0] for b in boxes) / len(boxes)
    cy = sum(b["location"][1] for b in boxes) / len(boxes)
    assert abs(cx - 3.0) < 0.25
    assert abs(cy - 2.0) < 0.25


def test_stub_build_instances_catalog_furniture(tmp_path: Path):
    plan = {
        "floor": {"height_m": 2.7, "bounds": {"width": 10, "depth": 8}},
        "walls": [
            {"id": "w1", "a": {"x": 0, "y": 0}, "b": {"x": 10, "y": 0}, "thickness_m": 0.2},
        ],
        "rooms": [],
        "openings": [{"id": "o1", "wall_id": "w1", "type": "door", "offset_m": 1, "width_m": 0.9}],
        "furniture": [
            {
                "id": "f1",
                "catalog_id": "chair.dining",
                "position": {"x": 2.0, "y": 2.0},
                "rotation_deg": 0,
                "size_m": {"w": 0.45, "d": 0.50, "h": 0.90},
            },
            {
                "id": "f2",
                "catalog_id": "bed.double",
                "position": {"x": 5.0, "y": 3.0},
                "rotation_deg": 0,
                "size_m": {"w": 1.60, "d": 2.00, "h": 0.55},
            },
            {
                "id": "f3",
                "catalog_id": "table.dining",
                "position": {"x": 7.0, "y": 4.0},
                "rotation_deg": 0,
                "size_m": {"w": 1.60, "d": 0.90, "h": 0.75},
            },
        ],
    }
    obj = tmp_path / "m.obj"
    glb = tmp_path / "m.glb"
    _stub_build(plan, obj, glb)
    text = obj.read_text(encoding="utf-8")
    assert text.count("v ") > 8
    data = json.loads(glb.read_text(encoding="utf-8"))
    assert data["extras"]["walls"] == 1
    assert data["extras"]["furniture"] == 3
    assert set(data["extras"]["catalog_ids"]) == {
        "chair.dining",
        "bed.double",
        "table.dining",
    }


def test_unknown_catalog_id_is_ignored():
    assert world_boxes("../etc/passwd", 0, 0, 0) == []
    assert world_boxes("not.a.piece", 0, 0, 0) == []
    mesh = boxes_to_obj(world_boxes("chair.dining", 0, 0, 0))
    assert mesh.startswith("#")
    assert "v " in mesh
    assert "f " in mesh
