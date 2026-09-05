from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import httpx
import redis

from . import compliance, diffusion, gan_refine, nlu, plan_adapt, vectorize

QUEUE = "queue:generate_2d"


def start_worker_thread() -> None:
    t = threading.Thread(target=_loop, name="ai-worker", daemon=True)
    t.start()


def _loop() -> None:
    url = os.getenv("REDIS_URL")
    if not url:
        return
    r = redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_timeout=None,
        socket_connect_timeout=5,
        health_check_interval=30,
    )
    api = os.getenv("API_CALLBACK_BASE", "http://api:8080")
    token = os.getenv("INTERNAL_TOKEN", "dev-internal-token")
    while True:
        try:
            item = r.brpop(QUEUE, timeout=5)
            if not item:
                continue
            _, raw = item
            job = json.loads(raw)
            _process(job, api, token)
        except redis.TimeoutError:
            continue
        except Exception as exc:  # noqa: BLE001
            print("worker error", exc)
            time.sleep(1)


def _process(job: dict[str, Any], api: str, token: str) -> None:
    job_id = job["job_id"]
    inp = job.get("input") or {}
    brief = inp.get("brief") or ""
    constraints = inp.get("constraints") or {}
    headers = {"X-Internal-Token": token, "Content-Type": "application/json"}
    with httpx.Client(timeout=420.0) as client:
        client.post(f"{api}/internal/jobs/{job_id}/running", headers=headers, json={"step": "nlu"})
        spec = nlu.parse_brief(brief, constraints)
        client.post(f"{api}/internal/jobs/{job_id}/running", headers=headers, json={"step": "flux"})
        preview_b64, preview_method = diffusion.generate_flux_plan(
            brief, constraints, spec=spec, job_id=job_id
        )
        client.post(f"{api}/internal/jobs/{job_id}/running", headers=headers, json={"step": "diffusion"})
        gen = diffusion.generate(spec, image=False)
        client.post(f"{api}/internal/jobs/{job_id}/running", headers=headers, json={"step": "refine"})
        refined = gan_refine.refine({"image_png_b64": gen.get("image_png_b64"), "layout": gen.get("layout"), "building_spec": spec, "method": gen.get("method")})
        client.post(f"{api}/internal/jobs/{job_id}/running", headers=headers, json={"step": "vectorize"})
        plan = vectorize.vectorize({"layout": refined.get("layout") or gen.get("layout"), "building_spec": spec})
        c = spec.get("constraints") or {}
        adapted = plan_adapt.adapt({
            "plan_document": plan["plan_document"],
            "parcel": {
                "width_m": (constraints.get("parcel_width_m") if isinstance(constraints, dict) else None) or c.get("max_width_m"),
                "depth_m": (constraints.get("parcel_depth_m") if isinstance(constraints, dict) else None) or c.get("max_depth_m"),
                "setback_m": (constraints.get("setback_m") if isinstance(constraints, dict) else 0) or 0,
            },
            "rules": (constraints.get("rules") if isinstance(constraints, dict) else None) or {},
        })
        doc = adapted["plan_document"]
        if not preview_b64:
            preview_b64 = diffusion.render_plan_document(doc)
            preview_method = preview_method or "procedural"
        user_id = inp.get("user_id")
        project_id = job.get("project_id")
        rev = client.post(
            f"{api}/internal/projects/{project_id}/revisions",
            headers=headers,
            json={
                "user_id": user_id,
                "source": "ai",
                "plan_document": doc,
                "building_spec": spec,
                "compliance": compliance.evaluate(doc),
                "preview_key": refined.get("preview_key") or "",
                "image_png_b64": preview_b64,
            },
        )
        rev.raise_for_status()
        revision = rev.json()
        client.post(
            f"{api}/internal/jobs/{job_id}/complete",
            headers=headers,
            json={
                "status": "succeeded",
                "step": "vectorize",
                "output": {
                    "revision_id": revision.get("ID") or revision.get("id"),
                    "version": revision.get("Version") or revision.get("version"),
                    "method": preview_method,
                },
            },
        )
