#!/usr/bin/env python3
"""Build (coarse, mask, clean) pairs from PlanDocument JSON or on-the-fly synthesis."""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "ai"))

from app.diffusion import generate
from app.nlu import parse_brief
from app.plan_render import degrade, render_clean_and_mask
from app.vectorize import vectorize

BRIEFS = [
    "Maison {n} chambres avec garage et cuisine ouverte",
    "Appartement {n} chambres cuisine ouverte",
    "Villa contemporaine {n} chambres avec bureau",
    "Maison traditionnelle {n} chambres salle de bain",
]


def _plans_from_json_dir(src: Path, limit: int) -> list[dict]:
    files = sorted(src.glob("*.json"))
    files = [p for p in files if p.name not in {"manifest.json", "gan_index.json"}]
    if limit:
        files = files[:limit]
    out = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        plan = data.get("plan_document") or data
        if plan.get("walls"):
            out.append(plan)
    return out


def _plans_synthetic(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    plans = []
    for _ in range(count):
        n = rng.choice([2, 3, 4, 5])
        brief = rng.choice(BRIEFS).format(n=n)
        spec = parse_brief(brief, {"total_area_m2": 80 + n * 20})
        gen = generate(spec)
        plans.append(vectorize({"layout": gen["layout"], "building_spec": spec})["plan_document"])
    return plans


def write_pairs(plans: list[dict], out: Path, size: int, seed: int) -> dict:
    rng = random.Random(seed)
    splits = {"train": [], "val": [], "test": []}
    n = len(plans)
    n_train = int(n * 0.8)
    n_val = int(n * 0.1)
    for i, plan in enumerate(plans):
        clean, mask = render_clean_and_mask(plan, size=size)
        coarse = degrade(clean, rng)
        if i < n_train:
            split = "train"
        elif i < n_train + n_val:
            split = "val"
        else:
            split = "test"
        dest = out / split
        dest.mkdir(parents=True, exist_ok=True)
        stem = f"{i:05d}"
        coarse.save(dest / f"{stem}_in.png")
        mask.save(dest / f"{stem}_mask.png")
        clean.save(dest / f"{stem}_out.png")
        splits[split].append(stem)
    manifest = {"count": n, "size": size, "license": "synthetic-A-AI", "splits": {k: len(v) for k, v in splits.items()}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, help="Dossier de JSON PlanDocument (optionnel)")
    parser.add_argument("--out", type=Path, default=ROOT / "research" / "dataset" / "data" / "refine_pairs")
    parser.add_argument("--count", type=int, default=512, help="si --src absent : synthese")
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if args.src and args.src.exists():
        plans = _plans_from_json_dir(args.src, args.limit)
        if not plans:
            raise SystemExit(f"Aucun PlanDocument dans {args.src}")
    else:
        plans = _plans_synthetic(args.count, args.seed)
    manifest = write_pairs(plans, args.out, args.size, args.seed)
    print(f"Done: {manifest['count']} paires -> {args.out} {manifest['splits']}")


if __name__ == "__main__":
    main()
