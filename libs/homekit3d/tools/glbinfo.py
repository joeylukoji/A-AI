"""Lit un GLB sans Blender : boîte englobante MONDE (hiérarchie de nœuds appliquée), triangles, matériaux.

Les packs exportés d'Unity (Kenney) portent des rotations et des échelles sur leurs nœuds : lire seulement les
`min`/`max` des accessoires donnerait de fausses dimensions (des toilettes tournées de 90° et réduites à 47 %).
"""
from __future__ import annotations

import itertools
import json
import struct
import sys
from pathlib import Path

Matrix = list[list[float]]


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    magic, _, _ = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise ValueError(f"{path}: pas un GLB")
    off, js, bin_ = 12, None, b""
    while off < len(data):
        length, kind = struct.unpack_from("<II", data, off)
        chunk = data[off + 8: off + 8 + length]
        if kind == 0x4E4F534A:
            js = json.loads(chunk)
        elif kind == 0x004E4942:
            bin_ = chunk
        off += 8 + length
    return js or {}, bin_


def _identity() -> Matrix:
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def _mul(a: Matrix, b: Matrix) -> Matrix:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _trs(node: dict) -> Matrix:
    if "matrix" in node:
        m = node["matrix"]                                  # colonnes d'abord (glTF)
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = node.get("translation", (0, 0, 0))
    x, y, z, w = node.get("rotation", (0, 0, 0, 1))
    sx, sy, sz = node.get("scale", (1, 1, 1))
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx], [r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty],
            [r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz], [0.0, 0.0, 0.0, 1.0]]


def bounds(path: Path) -> dict:
    js, _ = read_glb(path)
    nodes, accessors = js.get("nodes", []), js.get("accessors", [])
    lo, hi = [1e9] * 3, [-1e9] * 3
    tris = 0

    def visit(index: int, parent: Matrix) -> None:
        nonlocal tris
        node = nodes[index]
        world = _mul(parent, _trs(node))
        if "mesh" in node:
            for prim in js["meshes"][node["mesh"]].get("primitives", []):
                pos = prim.get("attributes", {}).get("POSITION")
                if pos is not None:
                    a = accessors[pos]
                    for corner in itertools.product(*zip(a["min"], a["max"])):
                        p = [sum(world[i][k] * corner[k] for k in range(3)) + world[i][3] for i in range(3)]
                        for i in range(3):
                            lo[i], hi[i] = min(lo[i], p[i]), max(hi[i], p[i])
                if prim.get("indices") is not None:
                    tris += accessors[prim["indices"]]["count"] // 3
        for child in node.get("children", []):
            visit(child, world)

    scene = js["scenes"][js.get("scene", 0)]
    for root in scene.get("nodes", []):
        visit(root, _identity())
    return {"min": lo, "max": hi, "size": [round(hi[i] - lo[i], 3) for i in range(3)], "tris": tris,
            "materials": len(js.get("materials", [])), "textures": len(js.get("textures", [])), "nodes": len(nodes)}


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(arg, bounds(Path(arg)))
