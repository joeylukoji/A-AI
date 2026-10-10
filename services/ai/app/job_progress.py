"""Adaptateur de progression des jobs vers l'API Go."""

from __future__ import annotations

import os

import httpx


def notify_job_step(job_id: str | None, step: str) -> None:
    """Pousse le pas courant (SSE) vers l'API Go si un job_id est fourni."""
    from uuid import UUID

    jid = (job_id or "").strip()
    api = (os.getenv("API_CALLBACK_BASE") or "").strip()
    if not jid or not api:
        return
    try:
        UUID(jid)
    except ValueError:
        return
    token = os.getenv("INTERNAL_TOKEN", "dev-internal-token")
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{api}/internal/jobs/{jid}/running",
                headers={"X-Internal-Token": token, "Content-Type": "application/json"},
                json={"step": step},
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[diffusion] notify {step}: {exc}", flush=True)
