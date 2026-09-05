#!/usr/bin/env python3
"""Charge model250000.pt et génère un plan de test."""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ai"))
os.environ["AI_STUB"] = "0"
os.environ.setdefault("HOUSEDIFFUSION_WEIGHTS", str(ROOT / "model250000.pt"))
os.environ.setdefault("HOUSEDIFFUSION_STEPS", "80")

from app.housediff import available, generate, rooms_from_spec, weights_path  # noqa: E402
from app.nlu import parse_brief  # noqa: E402


def main() -> None:
    print("poids:", weights_path(), "existe:", weights_path().is_file())
    print("available:", available())
    spec = parse_brief("Maison 2 chambres cuisine ouverte", {})
    print("programme:", rooms_from_spec(spec))
    out = generate(spec)
    rooms = out["layout"]["rooms"]
    print("method:", out.get("method"))
    print("pièces:", [(r["name"], r["type"], len(r["polygon"])) for r in rooms])
    dest = ROOT / "research" / "benchmarks" / "results" / "house_diffusion_test.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(out["image_png_b64"]))
    print("preview:", dest)
    if len(rooms) < 2:
        raise SystemExit("échec: moins de 2 pièces")
    print("OK")


if __name__ == "__main__":
    main()
