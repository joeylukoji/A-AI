"""
Blender 4.2+ headless: PlanDocument JSON -> OBJ + GLB.

Les murs sont extrudés depuis walls[] ; le mobilier est instancié depuis
le catalogue (chair.dining, bed.*, table.dining, …). Pas de Flux.

Usage:
  blender --background --python build_model.py -- plan.json out.obj out.glb
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    if len(argv) < 3:
        raise SystemExit("usage: build_model.py plan.json out.obj out.glb")

    plan_path, obj_path, glb_path = Path(argv[0]), Path(argv[1]), Path(argv[2])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    import bpy  # type: ignore  # runs inside Blender

    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    height = float(plan.get("floor", {}).get("height_m", 2.7))
    default_thickness = 0.15
    bounds = plan.get("floor", {}).get("bounds", {})
    width = float(bounds.get("width", 10))
    depth = float(bounds.get("depth", 8))

    wall_ext = _material(bpy, "WallExterior", (0.82, 0.78, 0.70, 1.0))
    wall_int = _material(bpy, "WallInterior", (0.90, 0.88, 0.84, 1.0))
    floor_mat = _material(bpy, "Floor", (0.55, 0.58, 0.62, 1.0))

    walls = plan.get("walls") or []
    if not walls:
        # Filet de sécurité : pas de murs -> on extrude les arêtes des pièces,
        # pour que le 3D suive la disposition 2D (polygones) telle quelle.
        walls = _walls_from_rooms(plan.get("rooms") or [])

    wall_objs: dict[str, object] = {}
    for i, wall in enumerate(walls):
        ax, ay = float(wall["a"]["x"]), float(wall["a"]["y"])
        bx, by = float(wall["b"]["x"]), float(wall["b"]["y"])
        mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
        length = math.hypot(bx - ax, by - ay) or 0.1
        thickness = float(wall.get("thickness_m") or default_thickness)
        exterior = _is_exterior(wall, width, depth)

        bpy.ops.mesh.primitive_cube_add(size=1, location=(mx, my, height / 2.0))
        obj = bpy.context.active_object
        obj.name = wall.get("id") or f"wall_{i}"
        obj.scale = (length, thickness, height)
        obj.rotation_euler[2] = math.atan2(by - ay, bx - ax)
        mat = wall_ext if exterior else wall_int
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
        wall_objs[obj.name] = (obj, wall)

    _cut_openings(bpy, plan.get("openings") or [], wall_objs)

    # Dalle de base sous toute l'emprise (fondation)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(width / 2.0, depth / 2.0, -0.11))
    slab = bpy.context.active_object
    slab.name = "floor_base"
    slab.scale = (width, depth, 0.1)
    if slab.data.materials:
        slab.data.materials[0] = floor_mat
    else:
        slab.data.materials.append(floor_mat)

    # Un sol par polygone de pièce : le 3D épouse la disposition 2D réelle.
    _build_room_floors(bpy, plan.get("rooms") or [])

    _place_furniture(bpy, plan.get("furniture") or [])

    light_data = bpy.data.lights.new(name="Sun", type="SUN")
    light_data.energy = 2.0
    light_obj = bpy.data.objects.new(name="Sun", object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    light_obj.rotation_euler = (math.radians(45), 0, math.radians(30))

    obj_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.obj_export(
        filepath=str(obj_path),
        export_selected_objects=False,
        apply_modifiers=True,
    )
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=False,
    )
    print(f"exported {obj_path} and {glb_path}")


def _material(bpy, name: str, color: tuple) -> object:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs[0].default_value = color
    return mat


# Teintes de sol par type de pièce (parquet clair pièces de vie, gris pièces humides)
_ROOM_FLOOR_COLORS: dict[str, tuple] = {
    "living": (0.72, 0.60, 0.44, 1.0),
    "dining": (0.72, 0.60, 0.44, 1.0),
    "bedroom": (0.76, 0.66, 0.52, 1.0),
    "office": (0.70, 0.62, 0.50, 1.0),
    "kitchen": (0.62, 0.64, 0.66, 1.0),
    "bathroom": (0.58, 0.62, 0.66, 1.0),
    "wc": (0.58, 0.62, 0.66, 1.0),
    "laundry": (0.60, 0.63, 0.66, 1.0),
    "hallway": (0.68, 0.62, 0.52, 1.0),
    "garage": (0.45, 0.46, 0.48, 1.0),
}


def _build_room_floors(bpy, rooms: list) -> None:
    """Un sol fin (2 cm) par polygone de pièce, teinté selon le type."""
    mats: dict[tuple, object] = {}
    for i, room in enumerate(rooms):
        poly = room.get("polygon") or []
        if len(poly) < 3:
            continue
        verts = [(float(p["x"]), float(p["y"]), -0.06) for p in poly]
        mesh = bpy.data.meshes.new(name=f"roomfloor_mesh_{i}")
        mesh.from_pydata(verts, [], [list(range(len(verts)))])
        mesh.update()
        obj = bpy.data.objects.new(room.get("id") or f"roomfloor_{i}", mesh)
        bpy.context.collection.objects.link(obj)
        # extrusion fine vers le haut pour donner de l'épaisseur
        mod = obj.modifiers.new(name="solidify", type="SOLIDIFY")
        mod.thickness = 0.06
        mod.offset = 1.0
        color = _ROOM_FLOOR_COLORS.get(str(room.get("type") or ""), (0.66, 0.64, 0.60, 1.0))
        mat = mats.get(color)
        if mat is None:
            mat = _material(bpy, f"roomfloor_{len(mats)}", color)
            mats[color] = mat
        obj.data.materials.append(mat)


def _walls_from_rooms(rooms: list) -> list:
    """Déduit des segments de mur depuis les arêtes des polygones de pièces.

    Les arêtes partagées par deux pièces ne sont extrudées qu'une fois
    (dédupliquées à 1 cm près).
    """
    seen: set[tuple] = set()
    walls: list[dict] = []
    for room in rooms:
        poly = room.get("polygon") or []
        n = len(poly)
        for i in range(n):
            p = poly[i]
            q = poly[(i + 1) % n]
            ax, ay = round(float(p["x"]), 2), round(float(p["y"]), 2)
            bx, by = round(float(q["x"]), 2), round(float(q["y"]), 2)
            if ax == bx and ay == by:
                continue
            key = (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
            if key in seen:
                continue
            seen.add(key)
            walls.append({
                "id": f"w_room_{len(walls)}",
                "a": {"x": ax, "y": ay},
                "b": {"x": bx, "y": by},
                "thickness_m": 0.15,
            })
    return walls


def _is_exterior(wall: dict, width: float, depth: float) -> bool:
    ax, ay = float(wall["a"]["x"]), float(wall["a"]["y"])
    bx, by = float(wall["b"]["x"]), float(wall["b"]["y"])
    e = 0.08
    on_edge = (
        (abs(ax) <= e and abs(bx) <= e)
        or (abs(ax - width) <= e and abs(bx - width) <= e)
        or (abs(ay) <= e and abs(by) <= e)
        or (abs(ay - depth) <= e and abs(by - depth) <= e)
    )
    return on_edge


def _place_furniture(bpy, furniture: list) -> None:
    from catalog.primitives import glb_override, known_id, world_boxes

    mats: dict[tuple, object] = {}
    for item in furniture:
        cid = str(item.get("catalog_id") or "")
        if not cid or not known_id(cid):
            continue
        pos = item.get("position") or {}
        x, y = float(pos.get("x") or 0), float(pos.get("y") or 0)
        rot = float(item.get("rotation_deg") or 0)
        size = item.get("size_m") if isinstance(item.get("size_m"), dict) else None
        fid = str(item.get("id") or cid)

        override = glb_override(cid)
        if override is not None:
            _instance_glb(bpy, override, fid, x, y, rot)
            continue

        for box in world_boxes(cid, x, y, rot, size):
            bpy.ops.mesh.primitive_cube_add(size=1, location=box["location"])
            obj = bpy.context.active_object
            obj.name = f"{fid}_{box['name']}"
            sx, sy, sz = box["size"]
            obj.scale = (sx, sy, sz)
            obj.rotation_euler[2] = box["rotation_z"]
            color = tuple(box["color"])
            mat = mats.get(color)
            if mat is None:
                mat = _material(bpy, f"cat_{len(mats)}", color)
                mats[color] = mat
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)


def _instance_glb(bpy, path: Path, name: str, x: float, y: float, rot: float) -> None:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = [o for o in bpy.data.objects if o not in before]
    if not imported:
        return
    root = imported[0]
    root.name = name
    root.location = (x, y, 0.0)
    root.rotation_euler[2] = math.radians(rot)


def _cut_openings(bpy, openings: list, wall_objs: dict) -> None:
    from openings import cutter_transform

    for i, opening in enumerate(openings):
        pair = wall_objs.get(opening.get("wall_id") or "")
        if not pair:
            continue
        wall_obj, wall = pair
        xf = cutter_transform(wall, opening)
        bpy.ops.mesh.primitive_cube_add(size=1, location=xf["location"])
        cutter = bpy.context.active_object
        cutter.name = f"cut_{opening.get('id') or i}"
        cutter.scale = xf["scale"]
        cutter.rotation_euler[2] = xf["rotation_z"]
        mod = wall_obj.modifiers.new(name=cutter.name, type="BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cutter
        bpy.context.view_layer.objects.active = wall_obj
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception:
            wall_obj.modifiers.remove(mod)
        bpy.data.objects.remove(cutter, do_unlink=True)


if __name__ == "__main__":
    main()
