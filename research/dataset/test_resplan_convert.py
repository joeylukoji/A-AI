from __future__ import annotations

from types import SimpleNamespace

from resplan_convert import convert_plan


class FakePoly:
    def __init__(self, coords: list[tuple[float, float]], area: float | None = None) -> None:
        self.exterior = SimpleNamespace(coords=coords + [coords[0]])
        self.is_empty = False
        w = max(p[0] for p in coords) - min(p[0] for p in coords)
        d = max(p[1] for p in coords) - min(p[1] for p in coords)
        self.area = area if area is not None else w * d
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        self.bounds = (min(xs), min(ys), max(xs), max(ys))
        self.centroid = SimpleNamespace(x=sum(xs) / len(xs), y=sum(ys) / len(ys))


def test_convert_synthetic_plan():
    inner = FakePoly([(0, 0), (10, 0), (10, 8), (0, 8)], area=80)
    raw = {
        "id": 42,
        "area": 80,
        "net_area": 72,
        "unitType": "apartment",
        "wall_depth": 0.2,
        "inner": inner,
        "living": FakePoly([(0, 0), (6, 0), (6, 8), (0, 8)]),
        "bedroom": FakePoly([(6, 0), (10, 0), (10, 8), (6, 8)]),
        "wall": FakePoly([(0, 0), (10, 0), (10, 0.2), (0, 0.2)]),
        "door": FakePoly([(2, 0), (2.9, 0), (2.9, 0.2), (2, 0.2)]),
    }
    spec, plan = convert_plan(raw)
    assert spec["version"] == "1.0"
    assert plan["version"] == "1.0"
    assert len(plan["rooms"]) == 2
    assert plan["floor"]["bounds"]["width"] > 0
    assert any(r["type"] == "bedroom" for r in plan["rooms"])
    assert plan["openings"]
