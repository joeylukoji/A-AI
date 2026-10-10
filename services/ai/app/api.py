"""Adaptateur HTTP des cas d'usage 2D et des étapes de recherche."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app import devis, diffusion, gan_refine, nlu, pipeline, plan_adapt, vectorize
from app.api_models import AdaptRequest, DevisRequest, EditRequest, PipelineRequest
from app.api_security import require_internal_token
from app.job_progress import notify_job_step
from app.opening_intervals import OpeningGeometryError
from app.plan_contracts import GeneratedDocumentError, PlanConstraintError

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal_token)])
public_router = APIRouter(prefix="/v1")


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
    except GeneratedDocumentError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": exc.code, "path": exc.path, "message": "generated document is invalid"},
        ) from exc
    except OpeningGeometryError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": exc.code, "opening_id": exc.opening_id, "message": "generated opening geometry is invalid"},
        ) from exc
    except PlanConstraintError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "fields": list(exc.fields), "message": str(exc)},
        ) from exc
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail=f"payload invalide: {exc}") from exc


@router.post("/nlu")
def api_nlu(req: PipelineRequest) -> dict[str, Any]:
    return _run_stage(lambda: nlu.parse_brief(req.brief, req.constraints))


@router.post("/generate")
def api_generate(spec: dict[str, Any]) -> dict[str, Any]:
    return _run_stage(lambda: diffusion.generate(spec))


@router.post("/refine")
def api_refine(payload: dict[str, Any]) -> dict[str, Any]:
    return _run_stage(lambda: gan_refine.refine(payload))


@router.post("/vectorize")
def api_vectorize(payload: dict[str, Any]) -> dict[str, Any]:
    return _run_stage(lambda: vectorize.vectorize(payload))


@router.post("/devis")
def api_devis(req: DevisRequest) -> dict[str, Any]:
    """Devis descriptif + cahier des charges + cahier technique (PDF) via gpt-oss-120b."""
    return _run_stage(lambda: devis.generate_devis(req.brief, req.building_spec, req.plan_document, req.constraints))


# Volontairement hors du routeur interne : ne renvoie que les règles par défaut
# statiques (aucun coût, aucune donnée utilisateur) — cf.
# tests/test_internal_auth.py::test_adapt_rules_stays_public_read_only_endpoint.
@public_router.get("/adapt/rules")
def api_adapt_rules() -> dict[str, Any]:
    return {"rules": plan_adapt.default_rules()}


@router.post("/adapt")
def api_adapt(req: AdaptRequest) -> dict[str, Any]:
    return _run_stage(
        lambda: plan_adapt.adapt(
            {
                "plan_document": req.plan_document,
                "parcel": req.parcel,
                "rules": req.rules,
            }
        )
    )


@router.post("/pipeline")
def api_pipeline(req: PipelineRequest) -> dict[str, Any]:
    return _run_stage(lambda: _pipeline(req))


def _pipeline(req: PipelineRequest) -> dict[str, Any]:
    return pipeline.generate_plan(req.brief, req.constraints, progress=partial(notify_job_step, req.job_id))


@router.post("/edit")
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
