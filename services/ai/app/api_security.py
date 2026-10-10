"""Authentification des appels HTTP internes."""

from __future__ import annotations

import hmac
import os
from typing import Annotated

from fastapi import Header, HTTPException


def require_internal_token(
    x_internal_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    """Guard for every /v1/* endpoint: only the Go API (and the internal
    worker) should be able to reach this service. Without this check, anyone
    who can reach this container's port (e.g. the host port published by the
    default docker-compose for local dev) could trigger paid Together API
    calls / GPU inference directly, bypassing the Go API's session auth,
    billing quotas, and rate limiting entirely.

    INTERNAL_TOKEN unset/empty => no-op, so local `uvicorn`/pytest runs that
    never configured the shared secret keep working unauthenticated (matches
    prior behavior). Set INTERNAL_TOKEN (same value as the Go API's) to turn
    this on — already the case in deploy/docker-compose.yml. In production,
    internal/config.Config.Validate() on the Go side additionally refuses to
    boot with a default/empty INTERNAL_TOKEN, so setting a real shared secret
    there implicitly requires setting one here too.
    """
    expected = (os.getenv("INTERNAL_TOKEN") or "").strip()
    if not expected:
        return
    got = (x_internal_token or "").strip()
    if not got or not hmac.compare_digest(got, expected):
        raise HTTPException(status_code=401, detail="invalid internal token")
