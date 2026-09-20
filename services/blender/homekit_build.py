"""Construction 3D par la bibliothèque `homekit3d` (libs/homekit3d), avec repli sur l'ancien constructeur.

La bibliothèque est un projet à part : ici on ne fait que la lancer dans Blender. Elle produit GLB et OBJ en quelques
secondes (chaque modèle importé une fois, meubles en instances liées) et n'appelle un LLM que pour le style et le décor,
avec un délai court et un repli déterministe : elle ne bloque jamais la génération.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from shutil import which

# Dossier qui CONTIENT le paquet `homekit3d` : dans l'image, /opt/homekit3d ; en développement, libs/homekit3d.
_DEV_DIR = Path(__file__).resolve().parent.parent.parent / "libs" / "homekit3d"


def library_dir() -> Path | None:
    for candidate in (os.getenv("HOMEKIT_DIR"), "/opt/homekit3d", str(_DEV_DIR)):
        if candidate and (Path(candidate) / "homekit3d" / "cli.py").exists():
            return Path(candidate)
    return None


def enabled() -> bool:
    """Actif par défaut dès que la bibliothèque est présente ; `HOMEKIT3D=0` la coupe."""
    flag = (os.getenv("HOMEKIT3D") or "1").strip().lower()
    return flag not in {"0", "off", "false", "no"} and library_dir() is not None


def build(plan_path: Path, obj_path: Path, glb_path: Path, *, blender_bin: str, timeout: float) -> str:
    """Lance la construction dans Blender. Renvoie la ligne de statistiques ; lève RuntimeError en cas d'échec."""
    lib = library_dir()
    if lib is None or not (which(blender_bin) or Path(blender_bin).exists()):
        raise RuntimeError("homekit3d ou Blender indisponible")
    cmd = [blender_bin, "-b", "--factory-startup", "--python-exit-code", "1",
           "--python", str(lib / "homekit3d" / "cli.py"), "--",
           "build", str(plan_path), str(glb_path), "--obj", str(obj_path), "--in-blender"]
    if (os.getenv("HOMEKIT_LLM") or "1").strip().lower() in {"0", "off", "false", "no"}:
        cmd.append("--no-ai")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(lib) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        # stdin vide : sous un service, l'entrée héritée peut être invalide et faire planter Blender au démarrage.
        result = subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"homekit3d timed out after {timeout}s") from exc
    output = (result.stdout or b"").decode("utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"homekit3d exited with {result.returncode}: {output[-2000:]}")
    if not obj_path.exists() or not glb_path.exists():
        raise RuntimeError("homekit3d did not produce obj/glb")
    return next((line for line in output.splitlines() if line.startswith("HOMEKIT_STATS")), "")
