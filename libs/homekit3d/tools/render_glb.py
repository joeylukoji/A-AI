"""Rend un GLB en image isométrique (Blender, Workbench) : `blender -b --python tools/render_glb.py -- maison.glb out.png [vue]`.

`vue` : iso (défaut), top (dessus), south (façade sud), cut (isométrique avec murs abaissés pour voir l'intérieur).
"""
from __future__ import annotations

import math
import sys

import bpy  # type: ignore
from mathutils import Vector  # type: ignore

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[0], argv[1]
view = argv[2] if len(argv) > 2 else "iso"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
pts = [o.matrix_world @ Vector(c) for o in bpy.data.objects if o.type == "MESH" for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
centre = (lo + hi) / 2
size = max(hi.x - lo.x, hi.y - lo.y)
if view == "cut":                       # murs abaissés à 1,1 m : on voit l'intérieur sans plafond
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith("shell.wall"):
            o.scale.z = 1.1 / 2.7
            for pv in (o,):
                pass
cam = bpy.data.cameras.new("c")
cam.type = "ORTHO"
# L'échelle orthographique porte sur la plus grande dimension de l'image (largeur, 3:2) : on cadre aussi la profondeur.
cam.ortho_scale = max(hi.x - lo.x, (hi.y - lo.y) * 1.5) * (1.08 if view == "top" else 1.45)
cam.clip_end = 1000
co = bpy.data.objects.new("c", cam)
bpy.context.scene.collection.objects.link(co)
tilt, yaw = {"top": (0.0, 0.0), "south": (88.0, 0.0)}.get(view, (55.0, 25.0))
d = 60
t, y = math.radians(tilt), math.radians(yaw)
# Avec la rotation (t, 0, y), la caméra regarde selon (-sin t sin y, sin t cos y, -cos t) : on la recule dans cette direction.
forward = Vector((-math.sin(t) * math.sin(y), math.sin(t) * math.cos(y), -math.cos(t)))
co.location = centre - forward * d
co.rotation_euler = (t, 0, y)
bpy.context.scene.camera = co
sun = bpy.data.lights.new("s", "SUN")
sun.energy = 3
so = bpy.data.objects.new("s", sun)
bpy.context.scene.collection.objects.link(so)
so.rotation_euler = (math.radians(50), math.radians(10), math.radians(-30))
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.color_type = "TEXTURE"
sc.display.shading.light = "STUDIO"
sc.display.shading.show_shadows = True
sc.display.shading.shadow_intensity = 0.4
sc.render.resolution_x, sc.render.resolution_y = 1500, 1000
sc.render.film_transparent = False
sc.world = bpy.data.worlds.new("w")
sc.world.color = (0.97, 0.97, 0.96)
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
