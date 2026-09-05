from __future__ import annotations

from pathlib import Path

from make_refine_pairs import write_pairs


def test_write_pairs(tmp_path: Path):
    plan = {
        "floor": {"bounds": {"width": 8, "depth": 6}, "height_m": 2.7},
        "walls": [
            {"id": "w1", "a": {"x": 0, "y": 0}, "b": {"x": 8, "y": 0}, "thickness_m": 0.2},
            {"id": "w2", "a": {"x": 8, "y": 0}, "b": {"x": 8, "y": 6}, "thickness_m": 0.2},
            {"id": "w3", "a": {"x": 8, "y": 6}, "b": {"x": 0, "y": 6}, "thickness_m": 0.2},
            {"id": "w4", "a": {"x": 0, "y": 6}, "b": {"x": 0, "y": 0}, "thickness_m": 0.2},
        ],
        "rooms": [
            {
                "id": "r1",
                "type": "living",
                "polygon": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 3}, {"x": 0, "y": 3}],
            }
        ],
    }
    man = write_pairs([plan] * 12, tmp_path, size=32, seed=0)
    assert man["count"] == 12
    assert (tmp_path / "train" / "00000_in.png").is_file()
    assert (tmp_path / "train" / "00000_mask.png").is_file()
    assert (tmp_path / "train" / "00000_out.png").is_file()
    assert man["splits"]["train"] >= 1
