#!/usr/bin/env python3
"""Convert ResPlan pickle plans to A-AI BuildingSpec + PlanDocument JSON."""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "resplan") not in sys.path:
    sys.path.insert(0, str(ROOT / "resplan"))

ROOM_KEYS = (
    "living",
    "bedroom",
    "bathroom",
    "kitchen",
    "storage",
    "parking",
    "stair",
    "balcony",
    "garden",
    "office",
)

ROOM_TYPE = {
    "living": "living",
    "bedroom": "bedroom",
    "bathroom": "bathroom",
    "kitchen": "kitchen",
    "storage": "storage",
    "parking": "garage",
    "stair": "hallway",
    "balcony": "other",
    "garden": "other",
    "office": "office",
}


def _geoms(value: Any) -> list[Any]:
    if value is None:
        return []
    if getattr(value, "is_empty", False):
        return []
    geoms = getattr(value, "geoms", None)
    if geoms is not None:
        return [g for g in geoms if g is not None and not g.is_empty]
    return [value]


def _poly_points(poly: Any, ox: float, oy: float, scale: float) -> list[dict[str, float]]:
    coords = list(poly.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [{"x": round((x - ox) * scale, 4), "y": round((y - oy) * scale, 4)} for x, y in coords]


def _longest_edges(poly: Any, ox: float, oy: float, scale: float, thickness: float, prefix: str, start: int) -> list[dict[str, Any]]:
    coords = list(poly.exterior.coords)
    walls: list[dict[str, Any]] = []
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if length * scale < 0.35:
            continue
        walls.append(
            {
                "id": f"{prefix}{start + len(walls)}",
                "a": {"x": round((x1 - ox) * scale, 4), "y": round((y1 - oy) * scale, 4)},
                "b": {"x": round((x2 - ox) * scale, 4), "y": round((y2 - oy) * scale, 4)},
                "thickness_m": thickness,
            }
        )
    return walls


def _opening_on_wall(centroid: tuple[float, float], walls: list[dict[str, Any]], oid: str, kind: str) -> dict[str, Any] | None:
    cx, cy = centroid
    best: tuple[float, str, float] | None = None
    for wall in walls:
        ax, ay = wall["a"]["x"], wall["a"]["y"]
        bx, by = wall["b"]["x"], wall["b"]["y"]
        dx, dy = bx - ax, by - ay
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-6:
            continue
        t = max(0.0, min(1.0, ((cx - ax) * dx + (cy - ay) * dy) / (length * length)))
        px, py = ax + t * dx, ay + t * dy
        dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
        if best is None or dist < best[0]:
            best = (dist, wall["id"], t * length)
    if best is None:
        return None
    return {
        "id": oid,
        "wall_id": best[1],
        "type": kind,
        "offset_m": round(best[2], 4),
        "width_m": 0.9 if kind == "door" else 1.2,
    }


def convert_plan(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    inner = raw.get("inner")
    if inner is None or getattr(inner, "is_empty", False):
        raise ValueError(f"plan {raw.get('id')} has no inner polygon")
    minx, miny, maxx, maxy = inner.bounds
    width_u = max(maxx - minx, 1e-6)
    depth_u = max(maxy - miny, 1e-6)
    shapely_area = float(inner.area) or (width_u * depth_u)
    target_area = float(raw.get("net_area") or raw.get("area") or shapely_area)
    scale = (target_area / shapely_area) ** 0.5 if shapely_area > 0 else 1.0
    thickness = max(0.1, float(raw.get("wall_depth") or 0.2) * scale)
    ox, oy = minx, miny
    width_m = round(width_u * scale, 3)
    depth_m = round(depth_u * scale, 3)

    rooms: list[dict[str, Any]] = []
    spec_rooms: list[dict[str, Any]] = []
    rid = 1
    for key in ROOM_KEYS:
        parts = _geoms(raw.get(key))
        if not parts:
            continue
        rtype = ROOM_TYPE.get(key, "other")
        for part in parts:
            if not hasattr(part, "exterior"):
                continue
            poly = _poly_points(part, ox, oy, scale)
            if len(poly) < 3:
                continue
            rid_s = f"r{rid}"
            area_m2 = round(float(part.area) * (scale**2), 2)
            rooms.append({"id": rid_s, "name": key, "type": rtype, "polygon": poly})
            spec_rooms.append({"id": rid_s, "type": rtype, "area_m2": max(area_m2, 0.1), "count": 1})
            rid += 1

    walls: list[dict[str, Any]] = []
    for geom in _geoms(raw.get("wall")):
        if hasattr(geom, "exterior"):
            walls.extend(_longest_edges(geom, ox, oy, scale, thickness, "w", len(walls) + 1))
    if not walls:
        walls = [
            {"id": "w1", "a": {"x": 0, "y": 0}, "b": {"x": width_m, "y": 0}, "thickness_m": thickness},
            {"id": "w2", "a": {"x": width_m, "y": 0}, "b": {"x": width_m, "y": depth_m}, "thickness_m": thickness},
            {"id": "w3", "a": {"x": width_m, "y": depth_m}, "b": {"x": 0, "y": depth_m}, "thickness_m": thickness},
            {"id": "w4", "a": {"x": 0, "y": depth_m}, "b": {"x": 0, "y": 0}, "thickness_m": thickness},
        ]

    openings: list[dict[str, Any]] = []
    oid = 1
    for key, kind in (("door", "door"), ("front_door", "door"), ("window", "window")):
        for geom in _geoms(raw.get(key)):
            c = geom.centroid
            opening = _opening_on_wall(((c.x - ox) * scale, (c.y - oy) * scale), walls, f"o{oid}", kind)
            if opening:
                openings.append(opening)
                oid += 1

    adjacencies: dict[str, list[str]] = {}
    graph = raw.get("graph")
    if graph is not None and hasattr(graph, "nodes"):
        node_ids = list(graph.nodes())
        type_to_rooms = {}
        for room in rooms:
            type_to_rooms.setdefault(room["type"], []).append(room["id"])
        for a, b, data in graph.edges(data=True):
            ta = graph.nodes[a].get("type")
            tb = graph.nodes[b].get("type")
            ra = type_to_rooms.get(ROOM_TYPE.get(ta, ta), [])
            rb = type_to_rooms.get(ROOM_TYPE.get(tb, tb), [])
            if not ra or not rb:
                continue
            adjacencies.setdefault(ra[0], []).append(rb[0])
        _ = node_ids

    for spec in spec_rooms:
        adj = adjacencies.get(spec["id"])
        if adj:
            spec["adjacent_to"] = sorted(set(adj))

    plan_document = {
        "version": "1.0",
        "units": "m",
        "floor": {"level": 0, "height_m": 2.7, "bounds": {"width": width_m, "depth": depth_m}},
        "walls": walls,
        "rooms": rooms,
        "openings": openings,
    }
    building_spec = {
        "version": "1.0",
        "brief": f"ResPlan #{raw.get('id')} {raw.get('unitType') or ''} {len(rooms)} pieces".strip(),
        "total_area_m2": round(float(raw.get("area") or target_area), 2),
        "floors": 1,
        "style": "other",
        "rooms": spec_rooms or [{"id": "r1", "type": "living", "area_m2": target_area, "count": 1}],
        "constraints": {"orthogonal": False, "max_width_m": width_m, "max_depth_m": depth_m},
    }
    return building_spec, plan_document


def load_pickle(path: Path) -> list[dict[str, Any]]:
    with path.open("rb") as f:
        data = pickle.load(f)
    if not isinstance(data, list):
        raise TypeError(f"expected list of plans in {path}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert ResPlan.pkl to A-AI JSON samples")
    parser.add_argument("--pkl", type=Path, default=ROOT / "resplan" / "ResPlan.pkl")
    parser.add_argument("--split", type=Path, default=ROOT / "resplan" / "split.json")
    parser.add_argument("--out", type=Path, default=ROOT / "research" / "dataset" / "data" / "resplan")
    parser.add_argument("--limit", type=int, default=0, help="0 = all plans")
    args = parser.parse_args()

    if not args.pkl.exists():
        raise SystemExit(
            f"ResPlan.pkl introuvable: {args.pkl}\n"
            "Télécharge-le depuis https://www.kaggle.com/datasets/mohamedabouagour/resplan\n"
            "et place-le dans resplan/ResPlan.pkl"
        )

    plans = load_pickle(args.pkl)
    splits = json.loads(args.split.read_text(encoding="utf-8")) if args.split.exists() else {}
    id_to_split = {}
    for name in ("train", "val", "test"):
        for pid in splits.get(name, []):
            id_to_split[int(pid)] = name

    args.out.mkdir(parents=True, exist_ok=True)
    items = []
    errors = 0
    iterable = plans if not args.limit else plans[: args.limit]
    for raw in iterable:
        pid = int(raw.get("id", len(items)))
        building_id = f"resplan-{pid}"
        try:
            spec, plan = convert_plan(raw)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"skip {building_id}: {exc}")
            continue
        sample = {
            "building_id": building_id,
            "source": "resplan",
            "split": id_to_split.get(pid, "unspecified"),
            "brief": spec["brief"],
            "building_spec": spec,
            "plan_document": plan,
        }
        path = args.out / f"{building_id}.json"
        path.write_text(json.dumps(sample), encoding="utf-8")
        items.append({"building_id": building_id, "path": str(path), "split": sample["split"]})
        if len(items) % 1000 == 0:
            print(f"converted {len(items)}")

    manifest = {
        "source": "resplan",
        "count": len(items),
        "errors": errors,
        "items": items,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Done: {len(items)} samples ({errors} skipped) -> {args.out}")


if __name__ == "__main__":
    main()
