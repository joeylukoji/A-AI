"""Planche-contact d'un catalogue : importe des modèles, les range en grille, rend une image (Blender).

    blender -b --python tools/contact_sheet.py -- out.png role1 role2 ...     (ou `all`)

Sert à vérifier à l'œil l'orientation (la « face » d'un meuble) et le style des modèles.
Un petit cube rouge marque le côté +Z du modèle (là où il regarde d'habitude).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy  # type: ignore
from mathutils import Vector  # type: ignore

ROOT = Path(__file__).resolve().parent.parent / "homekit3d"


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = Path(argv[0])
    wanted = set(argv[1:])
    manifest = json.loads((ROOT / "catalog" / "manifest.json").read_text(encoding="utf-8"))
    packs = {w[5:] for w in wanted if w.startswith("pack:")}
    wanted = {w for w in wanted if not w.startswith("pack:")}
    items = [i for i in manifest["items"] if not i["unused"] and (not packs or i["pack"] in packs)
             and (not wanted or "all" in wanted or i["role"] in wanted)]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cols = max(1, math.ceil(math.sqrt(len(items) * 1.4)))
    gap = 3.2
    red = bpy.data.materials.new("red")
    red.diffuse_color = (1, 0, 0, 1)
    for n, it in enumerate(items):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(ROOT / it["file"]))
        new = [o for o in bpy.data.objects if o not in before]
        root = bpy.data.objects.new(it["id"], None)
        bpy.context.scene.collection.objects.link(root)
        for o in new:
            if o.parent is None:
                o.parent = root
        root.scale = (it.get("scale", 1.0),) * 3          # taille réelle du rôle : les packs deviennent comparables
        # glTF est Y-up ; l'import Blender convertit en Z-up : le +Z glTF devient -Y Blender.
        cx, cy = (n % cols) * gap, -(n // cols) * gap
        root.location = (cx, cy, 0)
        # marqueur « face » : petit cube rouge devant (côté +Z glTF = -Y Blender)
        bpy.ops.mesh.primitive_cube_add(size=0.12, location=(cx, cy - 1.0, 0.06))
        bpy.context.active_object.data.materials.append(red)
        # étiquette
        bpy.ops.object.text_add(location=(cx - 1.2, cy + 1.25, 0))
        t = bpy.context.active_object
        t.data.body = it["name"][:22]
        t.data.size = 0.16
        t.rotation_euler = (0, 0, 0)
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
    bpy.context.active_object.data.energy = 3
    rows = math.ceil(len(items) / cols)
    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    cam.ortho_scale = max(cols, rows) * gap * 1.05
    co = bpy.data.objects.new("cam", cam)
    bpy.context.scene.collection.objects.link(co)
    centre = Vector(((cols - 1) * gap / 2, -(rows - 1) * gap / 2, 0))
    tilt, dist = math.radians(50), 60.0
    # La caméra regarde selon (0, sin, -cos) : on la recule le long de cette direction pour viser `centre`.
    co.location = centre + Vector((0, -dist * math.sin(tilt), dist * math.cos(tilt)))
    co.rotation_euler = (tilt, 0, 0)
    cam.clip_end = 500
    bpy.context.scene.camera = co
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.light = "STUDIO"
    sc.render.resolution_x = min(3200, 260 * cols)
    sc.render.resolution_y = min(2400, int(sc.render.resolution_x * 0.62 * rows / cols) + 200)
    sc.render.filepath = str(out)
    sc.world = bpy.data.worlds.new("w")
    sc.world.color = (0.93, 0.93, 0.92)
    bpy.ops.render.render(write_still=True)
    print("rendu:", out, len(items), "modèles")


main()
