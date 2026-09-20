"""Convertit un glTF/GLB en GLB autonome sans compression Draco, textures en JPEG :

    blender -b --python gltf_to_glb.py -- in.gltf out.glb [rotation_degrés]

`rotation_degrés` tourne le modèle autour de la verticale (pour que sa face avant regarde vers +Z glTF, le repère du catalogue).
"""
from __future__ import annotations

import math
import sys

import bpy  # type: ignore
from mathutils import Matrix  # type: ignore

args = sys.argv[sys.argv.index("--") + 1:]
src, out = args[:2]
turn = float(args[2]) if len(args) > 2 else 0.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
if turn:
    spin = Matrix.Rotation(math.radians(turn), 4, "Z")           # Z est la verticale de Blender (Y en glTF)
    for ob in bpy.context.scene.objects:
        if ob.parent is None:
            ob.matrix_world = spin @ ob.matrix_world
    bpy.context.view_layer.update()
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_yup=True, export_image_format="JPEG",
                          export_jpeg_quality=82, export_cameras=False, export_lights=False, export_draco_mesh_compression_enable=False)
