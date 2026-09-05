from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import compliance, devis, diffusion, gan_refine, nlu, plan_adapt, vectorize
from .worker import start_worker_thread


class PipelineRequest(BaseModel):
    brief: str
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
        f"[ai] flux={together_image.available()} "
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
        "style_ref": "1" if together_image._style_image_path() else "0",
    }


@app.post("/v1/nlu")
def api_nlu(req: PipelineRequest) -> dict[str, Any]:
    return nlu.parse_brief(req.brief, req.constraints)


@app.post("/v1/generate")
def api_generate(spec: dict[str, Any]) -> dict[str, Any]:
    return diffusion.generate(spec)


@app.post("/v1/refine")
def api_refine(payload: dict[str, Any]) -> dict[str, Any]:
    return gan_refine.refine(payload)


@app.post("/v1/vectorize")
def api_vectorize(payload: dict[str, Any]) -> dict[str, Any]:
    return vectorize.vectorize(payload)


class AdaptRequest(BaseModel):
    plan_document: dict[str, Any]
    parcel: dict[str, Any] = Field(default_factory=dict)
    rules: dict[str, Any] = Field(default_factory=dict)


class DevisRequest(BaseModel):
    brief: str = ""
    building_spec: dict[str, Any] = Field(default_factory=dict)
    plan_document: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)

    @field_validator("building_spec", "plan_document", "constraints", mode="before")
    @classmethod
    def _none_as_empty(cls, value: Any) -> Any:
        return {} if value is None else value


@app.post("/v1/devis")
def api_devis(req: DevisRequest) -> dict[str, Any]:
    """Devis descriptif + cahier des charges + cahier technique (PDF) via gpt-oss-120b."""
    return devis.generate_devis(req.brief, req.building_spec, req.plan_document, req.constraints)


@app.get("/v1/adapt/rules")
def api_adapt_rules() -> dict[str, Any]:
    return {"rules": plan_adapt.default_rules()}


@app.post("/v1/adapt")
def api_adapt(req: AdaptRequest) -> dict[str, Any]:
    return plan_adapt.adapt({
        "plan_document": req.plan_document,
        "parcel": req.parcel,
        "rules": req.rules,
    })


@app.post("/v1/pipeline")
def api_pipeline(req: PipelineRequest) -> dict[str, Any]:
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
        "method": preview_method + "+adapt",
    }


class EditRequest(BaseModel):
    instruction: str
    brief: str = ""
    constraints: dict[str, Any] = Field(default_factory=dict)
    building_spec: dict[str, Any] = Field(default_factory=dict)
    plan_document: dict[str, Any] = Field(default_factory=dict)
    image_png_b64: str = ""
    job_id: str | None = None

    @field_validator("constraints", "building_spec", "plan_document", mode="before")
    @classmethod
    def _edit_none_as_empty(cls, value: Any) -> Any:
        return {} if value is None else value


@app.post("/v1/edit")
def api_edit(req: EditRequest) -> dict[str, Any]:
    """Retouche d'un plan existant à partir d'une consigne (chat)."""
    if not (req.instruction or "").strip():
        raise HTTPException(status_code=400, detail="instruction required")
    return diffusion.edit_plan(
        req.instruction.strip(),
        brief=req.brief,
        constraints=req.constraints,
        spec=req.building_spec,
        plan_document=req.plan_document,
        image_png_b64=req.image_png_b64,
        job_id=req.job_id,
    )
