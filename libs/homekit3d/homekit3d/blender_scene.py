"""Construction de la scène dans Blender (bpy) et export GLB. À exécuter DANS Blender :

    blender -b --python -m homekit3d ...      (voir cli.py, qui lance Blender pour vous)

Vitesse : chaque modèle du catalogue n'est importé qu'UNE fois ; les meubles sont des objets qui PARTAGENT ses
maillages (instances liées). Douze chaises coûtent donc un seul import, et l'exportateur glTF écrit un seul maillage.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

from .assemble import Assembly, Placed, assemble
from .catalog import Catalog
from .geometry import Mesh, build_shell, planar_uvs
from .plan import Plan
from .procedural import PROCEDURAL_COLORS
from .procedural import build as build_procedural
from .surfaces import Surface, surface_for, textures_available

# (couleur, rugosité, métal, opacité)
BASE_MATERIALS = {
    "trim": ((0.97, 0.97, 0.96), 0.6, 0.0, 1.0), "door": ((0.58, 0.42, 0.30), 0.55, 0.0, 1.0),
    "handle": ((0.75, 0.72, 0.65), 0.3, 0.9, 1.0), "glass": ((0.70, 0.86, 0.95), 0.05, 0.0, 0.32),
    "garage": ((0.82, 0.83, 0.85), 0.5, 0.2, 1.0), "slab": ((0.50, 0.50, 0.50), 0.95, 0.0, 1.0),
    "plinth": ((0.42, 0.42, 0.41), 0.92, 0.0, 1.0),
}


def build_scene(plan: Plan, catalog: Catalog, out_path: str | Path, *, assembly: Assembly | None = None,
                export: bool = True, obj_path: str | Path | None = None) -> dict[str, Any]:
    """Construit la maison et l'écrit en GLB. Renvoie des statistiques (temps, triangles, modèles utilisés)."""
    import bpy  # type: ignore  # disponible seulement dans Blender

    t0 = time.perf_counter()
    plan.validate()
    assembly = assembly or assemble(plan, catalog)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    mats: dict[str, Any] = {}

    def material(name: str):
        if name in mats:
            return mats[name]
        surface = surface_for(name, plan.style) if _textured(plan) else None
        if surface and textures_available(surface):
            mats[name] = _make_textured_material(bpy, name, surface)
            return mats[name]
        if name == "wall_ext":
            spec = (plan.style.wall_exterior, 0.85, 0.0, 1.0)
        elif name == "wall_int":
            spec = (plan.style.wall_interior, 0.9, 0.0, 1.0)
        elif name.startswith("floor:"):
            kind = name.split(":", 1)[1]
            spec = (plan.style.floors.get(kind, (0.7, 0.68, 0.64)), 0.7, 0.0, 1.0)
        elif name in BASE_MATERIALS:
            spec = BASE_MATERIALS[name]
        elif name in PROCEDURAL_COLORS:
            spec = PROCEDURAL_COLORS[name]
        else:
            spec = ((0.7, 0.7, 0.7), 0.8, 0.0, 1.0)
        mats[name] = _make_material(bpy, name, *spec)
        return mats[name]

    shell = build_shell(plan)
    for mesh in shell.meshes.values():
        surface = surface_for(mesh.material, plan.style) if _textured(plan) else None
        tile = surface.tile if surface and textures_available(surface) else None
        _add_mesh_object(bpy, scene, f"shell.{mesh.material}", mesh, material(mesh.material), uv_tile=tile)
    t_shell = time.perf_counter()

    templates = _import_templates(bpy, sorted(assembly.asset_ids), catalog)
    t_import = time.perf_counter()
    instances = 0
    for n, placed in enumerate(assembly.placed):
        if placed.kind == "procedural":
            _add_procedural(bpy, scene, placed, material)
        else:
            instances += _add_instance(bpy, scene, placed, templates, n)
    t_place = time.perf_counter()

    stats: dict[str, Any] = {
        "objects": len(scene.objects), "instances": instances, "models": sorted(assembly.asset_ids),
        "skipped_roles": sorted(set(assembly.skipped)), "shell_triangles": shell.triangles,
        "seconds": {"shell": round(t_shell - t0, 2), "import": round(t_import - t_shell, 2),
                    "place": round(t_place - t_import, 2)},
    }
    if export:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix.lower() == ".blend":
            bpy.ops.wm.save_as_mainfile(filepath=str(out))
        else:
            bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", export_yup=True, export_apply=False,
                                      export_cameras=False, export_lights=False)
        stats["seconds"]["export"] = round(time.perf_counter() - t_place, 2)
        stats["bytes"] = out.stat().st_size
        if obj_path:
            t_obj = time.perf_counter()
            Path(obj_path).parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.obj_export(filepath=str(obj_path), export_materials=False, export_triangulated_mesh=False)
            stats["seconds"]["obj"] = round(time.perf_counter() - t_obj, 2)
    stats["seconds"]["total"] = round(time.perf_counter() - t0, 2)
    return stats


def _textured(plan: Plan) -> bool:
    """Textures de murs et de sols : styles réalistes seulement (les styles low-poly restent légers)."""
    return plan.textured and "realistic" in plan.style.tags


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _make_material(bpy, name: str, color: tuple[float, float, float], rough: float, metal: float, alpha: float):
    """Les palettes sont écrites en sRGB (comme un sélecteur de couleur) ; Blender veut du linéaire."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    color = tuple(srgb_to_linear(c) for c in color)
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        if hasattr(mat, "blend_method"):
            mat.blend_method = "BLEND"
    mat.diffuse_color = (*color, alpha)
    return mat


def _tinted_image(bpy, path: Path, tint: tuple[float, float, float], name: str):
    """Le grain d'une texture (sa lumière relative) avec la couleur `tint` : la texture ne fixe plus la couleur du mur."""
    import numpy as np  # fourni avec Blender

    src = bpy.data.images.load(str(path), check_existing=True)
    width, height = src.size
    px = np.empty(width * height * 4, dtype=np.float32)
    src.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    luma = px[:, 0] * 0.2126 + px[:, 1] * 0.7152 + px[:, 2] * 0.0722
    detail = (luma / max(float(luma.mean()), 1e-4))[:, None]
    px[:, :3] = np.clip(detail * np.asarray(tint, dtype=np.float32)[None, :], 0.0, 1.0)
    px[:, 3] = 1.0
    out = bpy.data.images.new(name, width, height)
    out.pixels.foreach_set(px.reshape(-1))
    out.file_format = "JPEG"
    out.pack()
    return out


def _make_textured_material(bpy, name: str, surface: Surface):
    """Principled BSDF avec couleur + relief : deux images, exportées telles quelles dans le GLB."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = surface.roughness
    bsdf.inputs["Metallic"].default_value = 0.0
    colour = nodes.new("ShaderNodeTexImage")
    if surface.tint is not None:
        colour.image = _tinted_image(bpy, surface.file("color"), surface.tint, f"{name}.tint")
    else:
        colour.image = bpy.data.images.load(str(surface.file("color")), check_existing=True)
    links.new(colour.outputs["Color"], bsdf.inputs["Base Color"])
    relief = nodes.new("ShaderNodeTexImage")
    relief.image = bpy.data.images.load(str(surface.file("normal")), check_existing=True)
    relief.image.colorspace_settings.name = "Non-Color"
    normal = nodes.new("ShaderNodeNormalMap")
    links.new(relief.outputs["Color"], normal.inputs["Color"])
    links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
    mat.diffuse_color = (*(surface.tint or (0.7, 0.7, 0.7)), 1.0)
    return mat


def _add_mesh_object(bpy, scene, name: str, mesh: Mesh, mat, uv_tile: float | None = None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(mesh.verts, [], [list(f) for f in mesh.faces])
    data.update()
    if uv_tile:
        layer = data.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", [c for uv in planar_uvs(mesh, uv_tile) for c in uv])
    data.materials.append(mat)
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    return obj


def _import_templates(bpy, asset_ids: list[str], catalog: Catalog) -> dict[str, list[tuple[Any, Any]]]:
    """Importe chaque modèle une fois ; renvoie, par modèle, la liste (données de maillage, matrice) à instancier."""
    templates: dict[str, list[tuple[Any, Any]]] = {}
    for asset_id in asset_ids:
        asset = catalog.get(asset_id)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(asset.path))
        new = [o for o in bpy.data.objects if o not in before]
        parts = [(o.data, o.matrix_world.copy(), o.name) for o in new if o.type == "MESH"]
        templates[asset_id] = [(data, mw) for data, mw, _ in parts]
        for o in new:
            bpy.data.objects.remove(o, do_unlink=True)
    return templates


def _add_instance(bpy, scene, placed: Placed, templates: dict, n: int) -> int:
    from mathutils import Matrix, Vector  # type: ignore

    asset = placed.asset
    parts = templates.get(asset.id) if asset else None
    if not parts:
        return 0
    ox, oy, oz = asset.center_offset                                   # glTF (x, y haut, z)
    # Repère Blender de l'asset importé : (x, -z, y). On ramène le centre de l'emprise et le sol à l'origine.
    centre = Vector((ox, -oz, oy))
    holder = bpy.data.objects.new(f"{placed.role}.{n}", None)
    scene.collection.objects.link(holder)
    sx, sy, sz = placed.scale                                          # (x, haut, profondeur) natifs
    holder.location = (placed.x, -placed.y, placed.z)
    holder.rotation_euler = (0, 0, -math.radians(placed.rot))
    holder.scale = (sx, sz, sy)                                        # Blender : x, y (profondeur), z (haut)
    for i, (data, mw) in enumerate(parts):
        obj = bpy.data.objects.new(f"{asset.name}.{n}.{i}", data)
        obj.parent = holder
        obj.matrix_basis = Matrix.Translation(-centre) @ mw
        scene.collection.objects.link(obj)
    return 1


def _add_procedural(bpy, scene, placed: Placed, material) -> None:
    meshes = build_procedural(placed.role, placed.footprint)
    holder = bpy.data.objects.new(f"{placed.role}.{placed.item_id}", None)
    scene.collection.objects.link(holder)
    holder.location = (placed.x, -placed.y, placed.z)
    holder.rotation_euler = (0, 0, -math.radians(placed.rot))
    for mesh in meshes.values():
        obj = _add_mesh_object(bpy, scene, f"{placed.role}.{mesh.material}", mesh, material(mesh.material))
        obj.parent = holder
