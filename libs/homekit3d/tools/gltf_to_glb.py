"""Convertit un glTF (fichiers séparés) en GLB autonome, textures en JPEG : `blender -b --python gltf_to_glb.py -- in.gltf out.glb`."""
from __future__ import annotations

import sys

import bpy  # type: ignore

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_yup=True, export_image_format="JPEG",
                          export_jpeg_quality=82, export_cameras=False, export_lights=False)
