"""Importe dans le catalogue les modèles choisis d'un pack Sweet Home 3D (.sh3f), à la taille réelle.

    python tools/import_sh3d.py BlendSwap-CC-0.sh3f sh3d-b [--blender chemin]

Les modèles retenus sont ceux de `EXPLICIT[<pack>]` dans build_manifest.py (clé = nom du fichier .obj sans extension).
Un `.sh3f` est une archive ZIP : `PluginFurnitureCatalog.properties` donne pour chaque modèle son nom, sa catégorie et
ses dimensions (cm), que `sh3d_to_glb.py` applique au modèle. Sont écrits dans `assets/<pack>/` : un GLB par modèle,
`LICENSE.txt` (celle du pack) et `SOURCES.json` (nom d'origine, catégorie, chemin dans le pack).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
ASSETS = HERE.parent / "homekit3d" / "assets"


def catalog_entries(text: str) -> list[dict]:
    """Les fiches du fichier .properties : {name, category, model, width, depth, height, modelRotation}."""
    rec: dict[str, dict] = {}
    for m in re.finditer(r"^(name|category|model|width|depth|height|modelRotation)#?_?(\d+)\s*=\s*(.*)$", text, re.M):
        rec.setdefault(m.group(2), {})[m.group(1)] = m.group(3).strip()
    return [r for r in rec.values() if "model" in r and "width" in r]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sh3f")
    parser.add_argument("pack")
    parser.add_argument("--blender", default=None)
    args = parser.parse_args()
    from build_manifest import EXPLICIT
    from homekit3d.cli import find_blender

    wanted = set(EXPLICIT[args.pack])
    blender = find_blender(args.blender)
    if not blender:
        raise SystemExit("Blender introuvable (--blender ou BLENDER_BIN)")
    out = ASSETS / args.pack
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        with zipfile.ZipFile(args.sh3f) as z:
            z.extractall(work)
        entries = catalog_entries((work / "PluginFurnitureCatalog.properties").read_text(encoding="latin-1"))
        jobs, sources = [], {}
        for e in entries:
            stem = Path(e["model"]).stem
            if stem not in wanted:
                continue
            jobs.append({"obj": str(work / e["model"].lstrip("/")), "out": str(out / f"{stem}.glb"),
                         "size_cm": [float(e["width"]), float(e["depth"]), float(e["height"])],
                         "rotation": [float(v) for v in e["modelRotation"].split()] if e.get("modelRotation") else None})
            sources[stem] = {"name": e.get("name"), "category": e.get("category"), "model": e["model"]}
        missing = wanted - set(sources)
        if missing:
            print("absents du pack :", ", ".join(sorted(missing)))
        (work / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
        proc = subprocess.run([blender, "-b", "--factory-startup", "--python", str(HERE / "sh3d_to_glb.py"), "--",
                               str(work / "jobs.json")], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1800)
        bad = [line for line in proc.stdout.splitlines() if line.startswith("SH3D") and not line.endswith(" ok")]
        print("\n".join(bad) or f"{len(jobs)} modèles convertis")
        license_file = work / "LICENSE.TXT"
        if license_file.exists():
            (out / "LICENSE.txt").write_text(license_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    (out / "SOURCES.json").write_text(json.dumps(sources, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{args.pack}: {sum(f.stat().st_size for f in out.glob('*.glb')) / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
