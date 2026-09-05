from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker import _stub_build  # noqa: E402


def test_stub_build_writes_obj_and_glb(tmp_path: Path):
    plan = {
        "floor": {"height_m": 2.7, "bounds": {"width": 10, "depth": 8}},
        "walls": [
            {"id": "w1", "a": {"x": 0, "y": 0}, "b": {"x": 10, "y": 0}, "thickness_m": 0.2},
        ],
        "rooms": [],
        "openings": [{"id": "o1", "wall_id": "w1", "type": "door", "offset_m": 1, "width_m": 0.9}],
    }
    obj = tmp_path / "m.obj"
    glb = tmp_path / "m.glb"
    _stub_build(plan, obj, glb)
    assert obj.exists() and obj.stat().st_size > 0
    assert "v " in obj.read_text(encoding="utf-8")
    data = json.loads(glb.read_text(encoding="utf-8"))
    assert data["extras"]["walls"] == 1
    assert data["extras"]["openings"] == 1
    assert data["extras"]["furniture"] == 0


def test_cutter_transform_door():
    from openings import cutter_transform

    wall = {"id": "w1", "a": {"x": 0, "y": 0}, "b": {"x": 10, "y": 0}, "thickness_m": 0.2}
    xf = cutter_transform(wall, {"type": "door", "offset_m": 1, "width_m": 0.9})
    assert xf["kind"] == "door"
    assert abs(xf["location"][0] - 1.45) < 1e-6
    assert xf["scale"][0] == 0.9
