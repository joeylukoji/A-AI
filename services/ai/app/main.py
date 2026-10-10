"""Composition de l'application FastAPI et cycle de vie du worker."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app import together_image
from app.api import _pipeline as _pipeline
from app.api import api_pipeline as api_pipeline
from app.api import public_router, router
from app.api_models import PipelineRequest as PipelineRequest
from app.worker import start_worker_thread


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    path = together_image._style_image_path()
    print(
        f"[ai] image={together_image.available()} "
        f"eden={'1' if together_image._eden_key() else '0'} "
        f"style={path.name if path else 'MISSING'}",
        flush=True,
    )
    if os.getenv("REDIS_URL"):
        start_worker_thread()
    yield


app = FastAPI(title="Congo Architecture IA", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "stub": os.getenv("AI_STUB", "1"),
        "image": "1" if together_image.available() else "0",
    }


app.include_router(public_router)
app.include_router(router)
