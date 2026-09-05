from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from shutil import which
from typing import Any

import httpx
import redis

from s3util import upload_file

QUEUE = "queue:generate_3d"
# Le process Blender peut rester silencieux longtemps sur de gros plans ;
# ce timeout borne le blocage du worker (un seul job traité à la fois).
BLENDER_TIMEOUT_S = float(os.getenv("BLENDER_TIMEOUT_S", "600"))


def main() -> None:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_timeout=None,
        socket_connect_timeout=5,
        health_check_interval=30,
    )
    api = os.getenv("API_CALLBACK_BASE", "http://localhost:8080")
    token = os.getenv("INTERNAL_TOKEN", "dev-internal-token")
    print(
        "blender-worker listening",
        QUEUE,
        "stub=",
        os.getenv("AI_STUB", "0"),
        "blender=",
        os.getenv("BLENDER_BIN", "blender"),
    )
    while True:
        try:
            item = r.brpop(QUEUE, timeout=5)
            if not item:
                continue
            _, raw = item
            job = json.loads(raw)
            process(job, api, token)
        except redis.TimeoutError:
            continue
        except Exception as exc:  # noqa: BLE001
            print("error", exc)
            time.sleep(1)


def _is_valid_uuid(value: Any) -> bool:
    """True si `value` est un UUID bien formé (jamais de '..' ni de séparateur)."""
    if not isinstance(value, str) or not value:
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def process(job: dict[str, Any], api: str, token: str) -> None:
    job_id_raw = job.get("job_id")
    headers = {"X-Internal-Token": token, "Content-Type": "application/json"}

    if not _is_valid_uuid(job_id_raw):
        # Sans job_id fiable on ne peut pas notifier l'API en toute sécurité
        # (le job_id sert à construire l'URL) : on journalise et on abandonne
        # ce message plutôt que de risquer une requête vers une route inattendue.
        print("invalid job_id, dropping message", job.get("job_id"))
        return
    job_id = job_id_raw

    project_id = job.get("project_id") or ""
    if not _is_valid_uuid(project_id):
        _fail(api, headers, job_id, f"invalid project_id: {project_id!r}")
        return

    out_dir: Path | None = None
    try:
        inp = job.get("input") or {}
        plan = inp.get("plan_document")
        if isinstance(plan, str):
            plan = json.loads(plan)
        if not plan:
            _fail(api, headers, job_id, "missing plan_document")
            return

        with httpx.Client(timeout=300.0) as client:
            client.post(f"{api}/internal/jobs/{job_id}/running", headers=headers, json={"step": "blender"})
            out_dir = Path(tempfile.mkdtemp(prefix="aai3d-"))
            plan_path = out_dir / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            obj_path = out_dir / "model.obj"
            glb_path = out_dir / "model.glb"

            try:
                _build(plan, plan_path, obj_path, glb_path)
            except Exception as exc:  # noqa: BLE001
                _fail(api, headers, job_id, f"blender build failed: {exc}")
                return

            try:
                artifacts = _upload_and_register(
                    client, api, headers, project_id, job_id, inp.get("revision_id"), obj_path, glb_path
                )
            except Exception as exc:  # noqa: BLE001
                _fail(api, headers, job_id, f"minio upload failed: {exc}")
                return

            client.post(
                f"{api}/internal/jobs/{job_id}/complete",
                headers=headers,
                json={
                    "status": "succeeded",
                    "step": "blender",
                    "output": {
                        "revision_id": inp.get("revision_id"),
                        "artifacts": artifacts,
                        "glb_artifact_id": artifacts.get("glb", {}).get("id"),
                        "obj_artifact_id": artifacts.get("obj", {}).get("id"),
                    },
                },
            )
            print("completed", job_id, artifacts)
    except Exception as exc:  # noqa: BLE001
        # Filet de sécurité : toute erreur inattendue ici (JSON invalide, panne
        # réseau lors du marquage "running"/"complete", ...) ne doit jamais
        # laisser le job bloqué en "running" indéfiniment côté API.
        _fail(api, headers, job_id, f"unexpected worker error: {exc}")
    finally:
        if out_dir is not None:
            shutil.rmtree(out_dir, ignore_errors=True)


def _build(plan: dict[str, Any], plan_path: Path, obj_path: Path, glb_path: Path) -> None:
    blender_bin = os.getenv("BLENDER_BIN", "blender")
    script = Path(__file__).resolve().parent / "scripts" / "build_model.py"
    stub = os.getenv("AI_STUB", "0") == "1"
    if stub or not which(blender_bin):
        print("using stub build")
        _stub_build(plan, obj_path, glb_path)
        return
    print("running blender", blender_bin)
    # subprocess.run() lit stdout/stderr via communicate() : contrairement à
    # check_call (basé sur wait()), il ne peut pas se bloquer si Blender
    # remplit le buffer du pipe (sortie très verbeuse sur les gros plans).
    try:
        result = subprocess.run(
            [
                blender_bin,
                "--background",
                "--python",
                str(script),
                "--",
                str(plan_path),
                str(obj_path),
                str(glb_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=BLENDER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.output or b"").decode("utf-8", errors="replace")[-4000:]
        raise RuntimeError(f"blender timed out after {BLENDER_TIMEOUT_S}s: {output}") from exc
    if result.returncode != 0:
        output = (result.stdout or b"").decode("utf-8", errors="replace")[-4000:]
        raise RuntimeError(f"blender exited with {result.returncode}: {output}")
    if not obj_path.exists() or not glb_path.exists():
        raise RuntimeError("blender did not produce obj/glb")


def _upload_and_register(
    client: httpx.Client,
    api: str,
    headers: dict[str, str],
    project_id: str,
    job_id: str,
    revision_id: Any,
    obj_path: Path,
    glb_path: Path,
) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:8]
    base = f"projects/{project_id}/models/{suffix}"
    obj_meta = upload_file(obj_path, f"{base}/model.obj", "model/obj")
    glb_meta = upload_file(glb_path, f"{base}/model.glb", "model/gltf-binary")

    out: dict[str, Any] = {}
    for kind, meta, path in (
        ("obj", obj_meta, obj_path),
        ("glb", glb_meta, glb_path),
    ):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        res = client.post(
            f"{api}/internal/projects/{project_id}/artifacts",
            headers=headers,
            json={
                "job_id": job_id,
                "revision_id": revision_id,
                "kind": kind,
                "storage_key": meta["key"],
                "content_type": meta["content_type"],
                "checksum_sha256": checksum,
                "bytes": meta["bytes"],
            },
        )
        res.raise_for_status()
        art = res.json()
        out[kind] = {
            "id": art.get("id"),
            "storage_key": meta["key"],
            "content_url": f"/api/v1/artifacts/{art.get('id')}/content",
        }
    return out


def _fail(api: str, headers: dict[str, str], job_id: str, message: str) -> None:
    print("fail", job_id, message)
    try:
        with httpx.Client(timeout=30.0) as client:
            client.post(
                f"{api}/internal/jobs/{job_id}/complete",
                headers=headers,
                json={"status": "failed", "error": message, "step": "blender"},
            )
    except Exception as exc:  # noqa: BLE001
        # Ne jamais laisser un problème réseau pendant la notification d'échec
        # remonter et interrompre la boucle worker : le job restera visible
        # comme "running" côté API, mais le worker continue de traiter la file.
        print("fail-notify failed", job_id, exc)


def _stub_build(plan: dict[str, Any], obj_path: Path, glb_path: Path) -> None:
    """Deterministic mesh export without Blender binary (dev/CI)."""
    from catalog.primitives import boxes_to_obj, world_boxes

    walls = plan.get("walls") or []
    height = float((plan.get("floor") or {}).get("height_m") or 2.7)
    furniture = plan.get("furniture") or []
    boxes: list[dict[str, Any]] = []
    for wall in walls:
        a, b = wall["a"], wall["b"]
        ax, ay, bx, by = float(a["x"]), float(a["y"]), float(b["x"]), float(b["y"])
        mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
        length = max(0.1, ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5)
        thick = float(wall.get("thickness_m") or 0.15)
        rot = math.atan2(by - ay, bx - ax)
        boxes.append({
            "size": (length, thick, height),
            "location": (mx, my, height / 2.0),
            "rotation_z": rot,
            "color": (0.85, 0.82, 0.76, 1.0),
            "name": wall.get("id") or "wall",
        })
    for item in furniture:
        cid = str(item.get("catalog_id") or "")
        if not cid:
            continue
        pos = item.get("position") or {}
        boxes.extend(
            world_boxes(
                cid,
                float(pos.get("x") or 0),
                float(pos.get("y") or 0),
                float(item.get("rotation_deg") or 0),
                item.get("size_m") if isinstance(item.get("size_m"), dict) else None,
            )
        )
    obj_path.write_text(boxes_to_obj(boxes, comment="A-AI blender stub"), encoding="utf-8")
    gltf = {
        "asset": {"version": "2.0", "generator": "a-ai-blender-stub"},
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "Plan"}],
        "extras": {
            "walls": len(walls),
            "openings": len(plan.get("openings") or []),
            "furniture": len(furniture),
            "catalog_ids": sorted({str(it.get("catalog_id")) for it in furniture if it.get("catalog_id")}),
            "height_m": height,
            "stub": True,
        },
    }
    glb_path.write_bytes(json.dumps(gltf).encode("utf-8"))


if __name__ == "__main__":
    main()
