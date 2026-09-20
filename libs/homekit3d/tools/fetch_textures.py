"""Télécharge des textures PBR de Poly Haven (CC0) pour les murs et les sols de la coque.

    python tools/fetch_textures.py beige_wall_001 white_stucco oak_wood_planks

Chaque texture donne `assets/textures/<id>_diff.jpg` (couleur, 1k) et `<id>_nor.jpg` (relief, convention OpenGL, celle de
glTF) avec `<id>.license.json`. Poly Haven publie tout sous CC0 (https://polyhaven.com/license).
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

API = "https://api.polyhaven.com"
ROOT = Path(__file__).resolve().parent.parent / "homekit3d" / "assets" / "textures"


def _open(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "homekit3d-fetch/0.1 (asset library builder)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch(texture_id: str, res: str = "1k") -> None:
    files = json.loads(_open(f"{API}/files/{texture_id}"))
    info = json.loads(_open(f"{API}/info/{texture_id}"))
    ROOT.mkdir(parents=True, exist_ok=True)
    for key, suffix in (("Diffuse", "diff"), ("nor_gl", "nor")):
        (ROOT / f"{texture_id}_{suffix}.jpg").write_bytes(_open(files[key][res]["jpg"]["url"]))
    authors = ", ".join(sorted((info.get("authors") or {}).keys())) or "Poly Haven"
    (ROOT / f"{texture_id}.license.json").write_text(json.dumps(
        {"id": texture_id, "name": info.get("name"), "authors": authors, "license": "CC0-1.0",
         "source": f"https://polyhaven.com/a/{texture_id}", "resolution": res,
         "size_mm": info.get("dimensions")}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{texture_id}: {authors}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for texture_id in sys.argv[1:]:
        fetch(texture_id)


if __name__ == "__main__":
    main()
