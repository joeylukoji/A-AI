"""Télécharge des modèles Poly Haven (CC0) et les convertit en GLB autonome, prêts pour le catalogue.

    python tools/fetch_polyhaven.py modern_arm_chair_01 dining_chair_02 [--res 1k] [--blender chemin]
    python tools/fetch_polyhaven.py --list furniture          # les modèles d'une catégorie

Poly Haven publie tout sous CC0 (https://polyhaven.com/license). Son API publique n'exige ni clé ni compte ; les
conditions demandent un crédit « Powered by Poly Haven » à qui construit sur l'API en direct, pas à qui utilise les
fichiers téléchargés : les crédits sont tout de même écrits dans ATTRIBUTION.md.

Les modèles sont des scans détaillés avec textures : bien plus lourds que les packs low-poly (`--res 1k` et une
compression JPEG limitent la casse). À réserver aux pièces maîtresses (fauteuil, canapé, table).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

API = "https://api.polyhaven.com"
ROOT = Path(__file__).resolve().parent.parent / "homekit3d" / "assets" / "polyhaven"
HERE = Path(__file__).resolve().parent


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "homekit3d-fetch/0.1 (asset library builder)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "homekit3d-fetch/0.1"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        dest.write_bytes(resp.read())


def list_category(category: str) -> None:
    for asset_id, meta in sorted(get_json(f"{API}/assets?t=models&c={category}").items()):
        print(f"{asset_id:34s} {meta.get('name', ''):32s} {', '.join(meta.get('categories', []))}")


def fetch(asset_id: str, res: str, blender: str) -> Path:
    files = get_json(f"{API}/files/{asset_id}")
    entry = files["gltf"][res]["gltf"]
    info = get_json(f"{API}/info/{asset_id}")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        download(entry["url"], work / f"{asset_id}.gltf")
        for rel, inc in (entry.get("include") or {}).items():
            download(inc["url"], work / rel)
        out = ROOT / f"{asset_id}.glb"
        out.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run([blender, "-b", "--factory-startup", "--python", str(HERE / "gltf_to_glb.py"), "--",
                               str(work / f"{asset_id}.gltf"), str(out)], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=300)
        if proc.returncode != 0 or not out.exists():
            raise SystemExit(f"conversion échouée pour {asset_id}:\n{(proc.stdout + proc.stderr)[-1500:]}")
    authors = ", ".join(sorted((info.get("authors") or {}).keys())) or "Poly Haven"
    (ROOT / f"{asset_id}.license.json").write_text(json.dumps(
        {"id": asset_id, "name": info.get("name"), "authors": authors, "license": "CC0-1.0",
         "source": f"https://polyhaven.com/a/{asset_id}", "resolution": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{asset_id}: {out.stat().st_size / 1e6:.2f} Mo  ({authors})")
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")       # les noms d'auteurs ne sont pas tous en cp1252
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--res", default="1k")
    parser.add_argument("--blender", default=None)
    parser.add_argument("--list", metavar="CATEGORIE")
    args = parser.parse_args()
    if args.list:
        list_category(args.list)
        return
    if not args.ids:
        parser.error("donnez au moins un identifiant, ou --list <catégorie>")
    sys.path.insert(0, str(HERE.parent))
    from homekit3d.cli import find_blender

    blender = find_blender(args.blender)
    if not blender:
        raise SystemExit("Blender introuvable (--blender ou BLENDER_BIN)")
    for asset_id in args.ids:
        if (ROOT / f"{asset_id}.glb").exists() and (ROOT / f"{asset_id}.license.json").exists():
            continue                                                  # déjà téléchargé
        fetch(asset_id, args.res, blender)


if __name__ == "__main__":
    main()
