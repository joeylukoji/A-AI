from __future__ import annotations

import hmac
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import devis, diffusion, gan_refine, nlu, plan_adapt, vectorize
from .worker import start_worker_thread


_BRIEF_MAX_LEN = 4000
# Un PNG base64 de plan fait ~1 Mo ; 16 Mo laisse largement la place à une
# capture haute résolution tout en refusant un corps de requête sans limite
# (Pydantic ne borne pas les `str` par défaut, et le champ finit en mémoire
# puis ré-encodé en JPEG avant l'appel image).
_IMAGE_B64_MAX_LEN = 16 * 1024 * 1024


def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
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


_INTERNAL_ONLY = [Depends(require_internal_token)]


def _run_stage(stage: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Exécute une étape du pipeline en traduisant un payload aberrant en 422.

    Les endpoints `/v1/generate`, `/v1/refine`, `/v1/vectorize` et `/v1/devis`
    acceptent des documents libres (`dict[str, Any]`) : un mur sans `a`/`b`, un
    polygone sans `x`, une surface non numérique remontaient en 500 avec une
    trace serveur. Ce sont des erreurs d'entrée, pas des pannes du service.

    `AttributeError` compte aussi : c'est ce que lève un sous-objet du mauvais
    type (`{"layout": "x"}` puis `layout.get(...)`), et c'était le dernier
    payload aberrant à passer encore en 500.
    """
    try:
        return stage()
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail=f"payload invalide: {exc}") from exc


class PipelineRequest(BaseModel):
    brief: str = Field(max_length=_BRIEF_MAX_LEN)
    constraints: dict[str, Any] = Field(default_factory=dict)
    job_id: str | None = None

    @field_validator("constraints", mode="before")
    @classmethod
    def _constraints_none_as_empty(cls, value: Any) -> Any:
        return {} if value is None else value


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    from . import together_image

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


app = FastAPI(title="A-AI Inference", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    from . import together_image

    return {
        "status": "ok",
        "stub": os.getenv("AI_STUB", "1"),
        "flux": "1" if together_image.available() else "0",
        "eden": "1" if together_image._eden_key() else "0",
        "image_method": together_image.method_name() if together_image.available() else "none",
        "style_ref": "1" if together_image._style_image_path() else "0",
    }


@app.post("/v1/nlu", dependencies=_INTERNAL_ONLY)
def api_nlu(req: PipelineRequest) -> dict[str, Any]:
    return _run_stage(lambda: nlu.parse_brief(req.brief, req.constraints))


@app.post("/v1/generate", dependencies=_INTERNAL_ONLY)
def api_generate(spec: dict[str, Any]) -> dict[str, Any]:
    return _run_stage(lambda: diffusion.generate(spec))


@app.post("/v1/refine", dependencies=_INTERNAL_ONLY)
def api_refine(payload: dict[str, Any]) -> dict[str, Any]:
    return _run_stage(lambda: gan_refine.refine(payload))


@app.post("/v1/vectorize", dependencies=_INTERNAL_ONLY)
def api_vectorize(payload: dict[str, Any]) -> dict[str, Any]:
    return _run_stage(lambda: vectorize.vectorize(payload))


class AdaptRequest(BaseModel):
    plan_document: dict[str, Any]
    parcel: dict[str, Any] = Field(default_factory=dict)
    rules: dict[str, Any] = Field(default_factory=dict)


class DevisRequest(BaseModel):
    brief: str = Field(default="", max_length=_BRIEF_MAX_LEN)
    building_spec: dict[str, Any] = Field(default_factory=dict)
    plan_document: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)

    @field_validator("building_spec", "plan_document", "constraints", mode="before")
    @classmethod
    def _none_as_empty(cls, value: Any) -> Any:
        return {} if value is None else value


@app.post("/v1/devis", dependencies=_INTERNAL_ONLY)
def api_devis(req: DevisRequest) -> dict[str, Any]:
    """Devis descriptif + cahier des charges + cahier technique (PDF) via gpt-oss-120b."""
    return _run_stage(
        lambda: devis.generate_devis(
            req.brief, req.building_spec, req.plan_document, req.constraints
        )
    )


# Volontairement sans `_INTERNAL_ONLY` : ne renvoie que les règles par défaut
# statiques (aucun coût, aucune donnée utilisateur) — cf.
# tests/test_internal_auth.py::test_adapt_rules_stays_public_read_only_endpoint.
@app.get("/v1/adapt/rules")
def api_adapt_rules() -> dict[str, Any]:
    return {"rules": plan_adapt.default_rules()}


@app.post("/v1/adapt", dependencies=_INTERNAL_ONLY)
def api_adapt(req: AdaptRequest) -> dict[str, Any]:
    return _run_stage(
        lambda: plan_adapt.adapt({
            "plan_document": req.plan_document,
            "parcel": req.parcel,
            "rules": req.rules,
        })
    )


@app.post("/v1/pipeline", dependencies=_INTERNAL_ONLY)
def api_pipeline(req: PipelineRequest) -> dict[str, Any]:
    return _run_stage(lambda: _pipeline(req))


def _pipeline(req: PipelineRequest) -> dict[str, Any]:
    spec = nlu.parse_brief(req.brief, req.constraints)
    preview_b64, preview_method = diffusion.generate_flux_plan(
        req.brief, req.constraints, spec=spec, job_id=req.job_id
    )
    gen = diffusion.generate(spec, image=False)
    refined = gan_refine.refine({"image_png_b64": gen.get("image_png_b64"), "layout": gen.get("layout"), "building_spec": spec, "method": gen.get("method")})
    plan = vectorize.vectorize({"layout": refined.get("layout") or gen.get("layout"), "building_spec": spec})
    c = spec.get("constraints") or {}
    adapted = plan_adapt.adapt({
        "plan_document": plan["plan_document"],
        "parcel": {
            "width_m": req.constraints.get("parcel_width_m") or c.get("max_width_m"),
            "depth_m": req.constraints.get("parcel_depth_m") or c.get("max_depth_m"),
            "setback_m": req.constraints.get("setback_m") or 0,
        },
        "rules": req.constraints.get("rules") or {},
    })
    doc = adapted["plan_document"]
    if not preview_b64:
        preview_b64 = diffusion.render_plan_document(doc)
        preview_method = preview_method or "procedural"
    return {
        "building_spec": spec,
        "plan_document": doc,
        "compliance": adapted["compliance"],
        "dimensions": adapted["dimensions"],
        "parcel": adapted["parcel"],
        "rules": adapted["rules"],
        "preview_key": refined.get("preview_key") or gen.get("preview_key") or "",
        "image_png_b64": preview_b64,
        "steps": ["nlu", "diffusion", "gan_refine", "vectorize", "adapt", "flux"],
        # `generate_flux_plan` peut rendre une méthode vide : sans ce repli le
        # champ valait "+adapt", illisible côté client.
        "method": (preview_method or "procedural") + "+adapt",
    }


class EditRequest(BaseModel):
    instruction: str = Field(max_length=_BRIEF_MAX_LEN)
    brief: str = Field(default="", max_length=_BRIEF_MAX_LEN)
    constraints: dict[str, Any] = Field(default_factory=dict)
    building_spec: dict[str, Any] = Field(default_factory=dict)
    plan_document: dict[str, Any] = Field(default_factory=dict)
    image_png_b64: str = Field(default="", max_length=_IMAGE_B64_MAX_LEN)
    job_id: str | None = None

    @field_validator("constraints", "building_spec", "plan_document", mode="before")
    @classmethod
    def _edit_none_as_empty(cls, value: Any) -> Any:
        return {} if value is None else value


@app.post("/v1/edit", dependencies=_INTERNAL_ONLY)
def api_edit(req: EditRequest) -> dict[str, Any]:
    """Retouche d'un plan existant à partir d'une consigne (chat)."""
    if not (req.instruction or "").strip():
        raise HTTPException(status_code=400, detail="instruction required")
    return _run_stage(
        lambda: diffusion.edit_plan(
            req.instruction.strip(),
            brief=req.brief,
            constraints=req.constraints,
            spec=req.building_spec,
            plan_document=req.plan_document,
            image_png_b64=req.image_png_b64,
            job_id=req.job_id,
        )
    )
