#!/usr/bin/env python3
"""Ablation harness: diffusion-only vs diffusion+GAN (stub pipeline)."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "services" / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "services" / "ai"))
if str(ROOT / "research" / "metrics") not in sys.path:
    sys.path.insert(0, str(ROOT / "research" / "metrics"))

from app.diffusion import generate
from app.gan_refine import refine
from app.nlu import parse_brief
from app.vectorize import vectorize
from constraints import evaluate as cons_eval
from topology import evaluate as topo_eval


def run_once(brief: str, use_gan: bool) -> dict:
    t0 = time.perf_counter()
    spec = parse_brief(brief, {})
    gen = generate(spec)
    layout = gen["layout"]
    if use_gan:
        refined = refine(
            {
                "image_png_b64": gen["image_png_b64"],
                "layout": layout,
                "building_spec": spec,
            }
        )
        layout = refined.get("layout") or layout
        method = refined.get("method")
    else:
        method = "none"
    plan = vectorize({"layout": layout, "building_spec": spec})["plan_document"]
    dt = time.perf_counter() - t0
    return {
        "latency_s": dt,
        "topology": topo_eval(plan),
        "constraints": cons_eval(spec, plan),
        "use_gan": use_gan,
        "refine_method": method,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("research/benchmarks/results/ablation_stub.json"),
    )
    parser.add_argument(
        "--briefs",
        nargs="*",
        default=[
            "Maison 4 chambres avec garage et cuisine ouverte",
            "Appartement 2 chambres cuisine ouverte",
            "Villa 5 chambres avec bureau",
        ],
    )
    args = parser.parse_args()
    results: dict[str, list] = {"diffusion_only": [], "diffusion_gan": []}
    for brief in args.briefs:
        results["diffusion_only"].append({"brief": brief, **run_once(brief, False)})
        results["diffusion_gan"].append({"brief": brief, **run_once(brief, True)})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
