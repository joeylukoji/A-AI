"""Ligne de commande : `python -m homekit3d build plan.json maison.glb`.

Deux modes :
  * hors Blender : la commande retrouve Blender (option --blender, variable BLENDER_BIN, chemins usuels) et le lance ;
  * dans Blender : `blender -b --python homekit3d/cli.py -- build plan.json maison.glb` (utilisé par le premier mode).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent          # dossier qui contient le paquet `homekit3d`


def find_blender(explicit: str | None = None) -> str | None:
    for candidate in (explicit, os.environ.get("BLENDER_BIN")):
        if candidate and Path(candidate).exists():
            return candidate
    found = shutil.which("blender")
    if found:
        return found
    for pattern_root in ("C:/Program Files/Blender Foundation", "/Applications/Blender.app/Contents/MacOS", "/opt/blender",
                         "/usr/local/bin"):
        root = Path(pattern_root)
        if not root.exists():
            continue
        for exe in sorted(root.rglob("blender.exe"), reverse=True) + sorted(root.rglob("blender")):
            if exe.is_file():
                return str(exe)
    return None


def _load_plan(path: Path, seed: int | None):
    from .plan import Plan

    data = json.loads(path.read_text(encoding="utf-8"))
    if "walls" in data and "floor" in data:                      # PlanDocument d'A-AI
        own = (data.get("layout") or {}).get("seed")               # la graine du parti : même maison, même style
        return Plan.from_aai(data, seed=seed if seed is not None else (own if isinstance(own, int) else 0))
    plan = Plan.from_dict(data)
    if seed is not None:
        plan.seed = seed
    return plan


def run_in_blender(args: argparse.Namespace) -> int:
    from .blender_scene import build_scene
    from .catalog import Catalog
    from .stylist import Stylist

    plan = _load_plan(Path(args.plan), args.seed)
    cut = args.cutaway if args.cutaway is not None else _env_float("HOMEKIT_CUTAWAY")
    if cut:
        plan.cutaway = cut
    if os.environ.get("HOMEKIT_TEXTURES", "1").strip().lower() in ("0", "off", "false", "no"):
        plan.textured = False
    catalog = Catalog.load()
    stylist = Stylist(catalog, llm=None if args.no_ai else _default_llm())
    report = stylist.style(plan, furnish=not args.keep_furniture, style=args.style or os.environ.get("HOMEKIT_STYLE") or None)
    stats = build_scene(plan, catalog, args.out, obj_path=args.obj)
    stats["stylist"] = report
    print("HOMEKIT_STATS " + json.dumps(stats, ensure_ascii=False))
    if args.stats:
        Path(args.stats).write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


def _env_float(name: str) -> float | None:
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return None
    return value if value > 0 else None


def _default_llm():
    from .llm import from_env

    return from_env()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="homekit3d")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="plan JSON -> maison 3D (GLB ou .blend)")
    b.add_argument("plan")
    b.add_argument("out")
    b.add_argument("--blender")
    b.add_argument("--seed", type=int)
    b.add_argument("--stats")
    b.add_argument("--cutaway", type=float, metavar="M", help="coupe les murs à M mètres (aperçu où l'on voit l'intérieur ; 1,2 = plan en coupe)")
    b.add_argument("--style", help="impose un style : moderne, scandinave, chaleureux, classique (réalistes), premium (le plus détaillé, lourd), lowpoly, lowpoly-chaleureux (légers, style jouet)")
    b.add_argument("--obj", help="écrit aussi un OBJ (pour les outils qui n'acceptent pas le glTF)")
    b.add_argument("--no-ai", action="store_true", help="pas d'appel à un LLM : styliste déterministe")
    b.add_argument("--keep-furniture", action="store_true", help="ne pas ajouter ni retirer de meubles")
    b.add_argument("--in-blender", action="store_true", help=argparse.SUPPRESS)
    ls = sub.add_parser("catalog", help="liste les rôles et les modèles du catalogue")
    ls.add_argument("--role")
    args = parser.parse_args(argv)

    if args.cmd == "catalog":
        from .catalog import Catalog

        cat = Catalog.load()
        if args.role:
            for a in cat.find(args.role):
                print(f"{a.id:45s} {a.footprint[0]:.2f}x{a.footprint[1]:.2f}x{a.height:.2f} m  {a.tris} tris")
        else:
            for role, ids in cat.summary().items():
                print(f"{role:18s} {len(ids)}")
        return 0

    if args.in_blender:
        return run_in_blender(args)
    blender = find_blender(args.blender)
    if not blender:
        print("Blender introuvable : installez-le ou passez --blender / BLENDER_BIN.", file=sys.stderr)
        return 2
    # --factory-startup : ni préférences ni add-ons de l'utilisateur (plus rapide, et indépendant de la machine).
    cmd = [blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(Path(__file__).resolve()), "--",
           "build", str(Path(args.plan).resolve()), str(Path(args.out).resolve()), "--in-blender"]
    for flag in ("no_ai", "keep_furniture"):
        if getattr(args, flag):
            cmd.append("--" + flag.replace("_", "-"))
    if args.seed is not None:
        cmd += ["--seed", str(args.seed)]
    if args.stats:
        cmd += ["--stats", str(Path(args.stats).resolve())]
    if args.obj:
        cmd += ["--obj", str(Path(args.obj).resolve())]
    if args.style:
        cmd += ["--style", args.style]
    if args.cutaway is not None:
        cmd += ["--cutaway", str(args.cutaway)]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PACKAGE_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    started = time.perf_counter()
    # stdin vide : sous un lanceur (pytest, service) l'entrée héritée peut être invalide et faire planter Blender au démarrage.
    proc = subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL)
    print(f"terminé en {time.perf_counter() - started:.1f} s")
    return proc.returncode


if __name__ == "__main__":
    # Lancé par Blender (`--python cli.py -- build ...`) : les arguments utiles suivent le `--`.
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if str(PACKAGE_ROOT) not in sys.path:
        sys.path.insert(0, str(PACKAGE_ROOT))
    from homekit3d.cli import main as _main

    sys.exit(_main(argv))
