from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import httpx
import redis

from app import pipeline

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
    """Run the shared use case, then persist its exact document and preview."""
    job_id = job["job_id"]
    inp = job.get("input") or {}
    headers = {"X-Internal-Token": token, "Content-Type": "application/json"}
    with httpx.Client(timeout=420.0) as client:

        def post(path: str, payload: dict[str, Any]) -> httpx.Response:
            response = client.post(f"{api}{path}", headers=headers, json=payload)
            response.raise_for_status()
            return response

        def progress(step: str) -> None:
            post(f"/internal/jobs/{job_id}/running", {"step": step})

        try:
            result = pipeline.generate_plan(inp.get("brief") or "", inp.get("constraints") or {}, progress=progress)
            revision = post(
                f"/internal/projects/{job.get('project_id')}/revisions",
                {
                    "user_id": inp.get("user_id"),
                    "source": "ai",
                    "plan_document": result["plan_document"],
                    "building_spec": result["building_spec"],
                    "compliance": result["compliance"],
                    "preview_key": result["preview_key"],
                    "image_png_b64": result["image_png_b64"],
                },
            ).json()
        except Exception:
            # No retry here: revision creation is not yet idempotent. The queue
            # recovery / acknowledgement policy belongs to the reliability sprint.
            post(
                f"/internal/jobs/{job_id}/complete",
                {
                    "status": "failed",
                    "error": "2D generation or revision persistence failed",
                },
            )
            raise

        post(
            f"/internal/jobs/{job_id}/complete",
            {
                "status": "succeeded",
                "step": "vectorize",
                "output": {
                    "revision_id": revision.get("ID") or revision.get("id"),
                    "version": revision.get("Version") or revision.get("version"),
                    "method": result["method"],
                },
            },
        )
