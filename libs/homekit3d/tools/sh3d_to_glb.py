"""Convertit des modèles OBJ/MTL d'un pack Sweet Home 3D en GLB autonomes, à la taille réelle du catalogue.

    blender -b --factory-startup --python tools/sh3d_to_glb.py -- jobs.json

`jobs.json` : [{"obj": "chemin/modele.obj", "out": "sortie.glb", "size_cm": [largeur, profondeur, hauteur],
"rotation": [9 nombres, ligne par ligne, facultatif]}, ...]

Un modèle Sweet Home 3D a son axe vertical en Y et sa face avant vers +Z, comme glTF ; certains portent en plus une
« modelRotation » (matrice 3×3 dans le repère du modèle) qui les remet d'aplomb : on l'applique avant de les ajuster. Sweet Home 3D
ajuste le modèle aux dimensions (largeur × profondeur × hauteur) déclarées dans le catalogue ; on fait pareil, si bien que
le GLB est directement en mètres. Les textures sont recompressées en JPEG.
"""
from __future__ import annotations

import json
import sys

import bpy  # type: ignore
from mathutils import Matrix, Vector  # type: ignore


def bounds(objects):
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for ob in objects:
        for corner in ob.bound_box:
            w = ob.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def convert(job: dict) -> str:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=job["obj"], forward_axis="NEGATIVE_Z", up_axis="Y")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        return "aucun maillage"
    if job.get("rotation"):
        r = job["rotation"]
        rot = Matrix([r[0:3], r[3:6], r[6:9]])                          # dans le repère Y-haut du fichier
        to_blender = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))         # (x, y, z) -> (x, -z, y), l'import Y-haut -> Z-haut
        rot_b = (to_blender @ rot @ to_blender.inverted()).to_4x4()
        for ob in meshes:
            ob.matrix_world = rot_b @ ob.matrix_world
        bpy.context.view_layer.update()
    lo, hi = bounds(meshes)
    size = hi - lo
    if min(size) <= 1e-9:
        return "boîte dégénérée"
    w, d, h = (v / 100.0 for v in job["size_cm"])
    # repère Blender (Z haut) : x = largeur, y = profondeur, z = hauteur
    factor = Vector((w / size.x, d / size.y, h / size.z))
    for ob in meshes:
        ob.location = Vector((ob.location[i] * factor[i] for i in range(3)))
        ob.scale = Vector((ob.scale[i] * factor[i] for i in range(3)))
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    for ob in meshes:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for ob in meshes:  # les MTL de Sweet Home 3D laissent parfois des matériaux sans nom ou des alphas à 0
        for slot in ob.material_slots:
            mat = slot.material
            if mat and mat.use_nodes:
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf and bsdf.inputs["Alpha"].default_value < 0.05 and not bsdf.inputs["Alpha"].links:
                    bsdf.inputs["Alpha"].default_value = 1.0
    bpy.ops.export_scene.gltf(filepath=job["out"], export_format="GLB", export_yup=True, export_image_format="JPEG",
                              export_jpeg_quality=85, export_cameras=False, export_lights=False,
                              use_selection=False)
    return "ok"


def main() -> None:
    jobs = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
    for job in jobs:
        try:
            print("SH3D", job["out"], convert(job), flush=True)
        except Exception as exc:  # un modèle défectueux ne doit pas arrêter le lot
            print("SH3D", job["out"], "ERREUR", exc, flush=True)


main()
