#!/usr/bin/env python3
"""Download ResPlan (~17k) from Zenodo and place ResPlan.pkl under resplan/."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PKL = ROOT / "resplan" / "ResPlan.pkl"
ZENODO_ZIP = "https://zenodo.org/api/records/20061236/files/ResPlan_data.zip/content"
KAGGLE_PAGE = "https://www.kaggle.com/datasets/resplan/resplan"
ZENODO_PAGE = "https://zenodo.org/records/20061236"


def _find_pkl(root: Path) -> Path | None:
    matches = list(root.rglob("*.pkl"))
    if not matches:
        return None
    matches.sort(key=lambda p: p.stat().st_size, reverse=True)
    return matches[0]


def download_zenodo(dest_zip: Path) -> None:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    print(f"Téléchargement Zenodo (~107 Mo) → {dest_zip}")
    req = urllib.request.Request(ZENODO_ZIP, headers={"User-Agent": "A-AI-resplan-download"})
    with urllib.request.urlopen(req, timeout=120) as resp, dest_zip.open("wb") as out:
        shutil.copyfileobj(resp, out)
    print(f"OK {dest_zip.stat().st_size / (1024 * 1024):.1f} Mo")


def extract_pkl(zip_path: Path, pkl_path: Path) -> None:
    extract_dir = zip_path.parent / "resplan_extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    found = _find_pkl(extract_dir)
    if found is None:
        raise SystemExit(f"Aucun .pkl dans {zip_path}. Contenu: {list(extract_dir.rglob('*'))[:20]}")
    pkl_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(found, pkl_path)
    print(f"Copié {found.name} → {pkl_path}")


def write_manifest(out: Path, pkl: Path, ready: bool, note: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    size_mb = round(pkl.stat().st_size / (1024 * 1024), 1) if pkl.exists() else 0
    manifest = {
        "source": "resplan",
        "expected_count": 17000,
        "pkl": str(pkl),
        "ready": ready,
        "size_mb": size_mb,
        "kaggle": KAGGLE_PAGE,
        "zenodo": ZENODO_PAGE,
        "note": note,
        "next": "python research/dataset/resplan_convert.py",
        "items": [],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pkl", type=Path, default=DEFAULT_PKL)
    parser.add_argument("--out", type=Path, default=ROOT / "research" / "dataset" / "data" / "public")
    parser.add_argument("--fetch", action="store_true", help="Télécharger depuis Zenodo si le pkl manque")
    args = parser.parse_args()

    if args.pkl.exists():
        write_manifest(args.out, args.pkl, True, "ResPlan.pkl déjà présent")
        print(f"ResPlan.pkl OK ({args.pkl.stat().st_size / (1024 * 1024):.1f} Mo).")
        print("Ensuite: python research/dataset/resplan_convert.py")
        return

    if args.fetch:
        dest_zip = ROOT / "resplan" / "ResPlan_data.zip"
        download_zenodo(dest_zip)
        extract_pkl(dest_zip, args.pkl)
        write_manifest(args.out, args.pkl, True, "Téléchargé depuis Zenodo")
        print("Ensuite: python research/dataset/resplan_convert.py")
        return

    note = (
        "ResPlan.pkl manquant.\n"
        f"  Zenodo (recommandé, sans compte): {ZENODO_PAGE}\n"
        f"  lien direct zip: {ZENODO_ZIP}\n"
        f"  Kaggle (compte requis): {KAGGLE_PAGE}\n"
        f"  ou: python research/dataset/download.py --fetch"
    )
    write_manifest(args.out, args.pkl, False, note)
    print(note)
    sys.exit(1)


if __name__ == "__main__":
    main()
