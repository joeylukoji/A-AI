from __future__ import annotations

from constraints import evaluate as cons_eval
from topology import evaluate as topo_eval


def sample_plan():
    return {
        "version": "1.0",
        "units": "m",
        "floor": {"level": 0, "height_m": 2.7, "bounds": {"width": 10, "depth": 8}},
        "walls": [
            {"id": "w1", "a": {"x": 0, "y": 0}, "b": {"x": 10, "y": 0}, "thickness_m": 0.2},
            {"id": "w2", "a": {"x": 10, "y": 0}, "b": {"x": 10, "y": 8}, "thickness_m": 0.2},
            {"id": "w3", "a": {"x": 10, "y": 8}, "b": {"x": 0, "y": 8}, "thickness_m": 0.2},
            {"id": "w4", "a": {"x": 0, "y": 8}, "b": {"x": 0, "y": 0}, "thickness_m": 0.2},
        ],
        "rooms": [
            {
                "id": "r1",
                "type": "living",
                "polygon": [
                    {"x": 0, "y": 0},
                    {"x": 5, "y": 0},
                    {"x": 5, "y": 4},
                    {"x": 0, "y": 4},
                ],
            }
        ],
        "openings": [],
    }


def test_topology_ok():
    m = topo_eval(sample_plan())
    assert m["closed_perimeter"] is True
    assert m["room_polygon_ratio"] == 1.0
    assert m["orthogonality"] == 1.0


def test_constraints_room_count():
    spec = {"rooms": [{"id": "r1", "type": "living", "count": 1}]}
    m = cons_eval(spec, sample_plan())
    assert m["room_count_score"] == 1.0
    assert m["has_bounds"] is True
