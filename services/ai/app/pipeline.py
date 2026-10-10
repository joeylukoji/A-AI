"""Cas d'usage 2D commun aux adaptateurs HTTP, Redis et aux retouches."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app import diffusion, gan_refine, generation_trace, nlu, plan_adapt, vectorize
from app.document_validation import validate_generated_document
from app.parcel_constraints import validate_request_dimensions

Progress = Callable[[str], None]


def _report(progress: Progress | None, step: str) -> None:
    if progress is not None:
        progress(step)


def _requested_dimension(
    constraints: dict[str, Any], primary: str, alias: str, fallback: Any
) -> Any:
    for key in (primary, alias):
        if constraints.get(key) is not None:
            return constraints[key]
    return fallback


def build_document(
    spec: dict[str, Any],
    constraints: dict[str, Any],
    *,
    progress: Progress | None = None,
    preferred_layout: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and adapt the vector document before any paid preview rendering.

    Transport adapters supply progress reporting. This function neither reads
    job identifiers nor writes revisions or sends HTTP callbacks.
    """
    _report(progress, "diffusion")
    generated = diffusion.generate(spec, image=False)
    _report(progress, "refine")
    refined = gan_refine.refine(
        {
            "image_png_b64": generated.get("image_png_b64"),
            "layout": generated.get("layout"),
            "building_spec": spec,
            "method": generated.get("method"),
        }
    )
    generation_trace.refinement(refined.get("method") or "unknown")
    _report(progress, "vectorize")
    vector = vectorize.vectorize(
        {
            "layout": refined.get("layout") or generated.get("layout"),
            "preferred_layout": preferred_layout,
            "building_spec": spec,
        }
    )
    spec_constraints = spec.get("constraints") or {}
    _report(progress, "adapt")
    adapted = plan_adapt.adapt(
        {
            "plan_document": vector["plan_document"],
            "parcel": {
                "width_m": _requested_dimension(
                    constraints,
                    "parcel_width_m",
                    "max_width_m",
                    spec_constraints.get("max_width_m"),
                ),
                "depth_m": _requested_dimension(
                    constraints,
                    "parcel_depth_m",
                    "max_depth_m",
                    spec_constraints.get("max_depth_m"),
                ),
                "setback_m": constraints.get("setback_m", 0),
            },
            "rules": constraints.get("rules") or {},
        }
    )
    validate_generated_document(adapted["plan_document"])
    return {
        **adapted,
        "preview_key": refined.get("preview_key") or generated.get("preview_key") or "",
    }


def generate_plan(
    brief: str,
    constraints: dict[str, Any] | None = None,
    *,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Generate a final plan and its preview through one transport-independent path."""
    with generation_trace.capture() as provenance:
        result = _generate_plan(brief, constraints, progress=progress)
        return {**result, "provenance": provenance}


def _generate_plan(
    brief: str,
    constraints: dict[str, Any] | None,
    *,
    progress: Progress | None,
) -> dict[str, Any]:
    constraints = dict(constraints or {})
    validate_request_dimensions(constraints)
    _report(progress, "nlu")
    spec = nlu.parse_brief(brief, constraints)
    adapted = build_document(spec, constraints, progress=progress)
    _report(progress, "gemini")
    image, method = diffusion.preview_from_document(
        brief, constraints, spec=spec, doc=adapted["plan_document"]
    )
    return {
        "building_spec": spec,
        "plan_document": adapted["plan_document"],
        "compliance": adapted["compliance"],
        "dimensions": adapted["dimensions"],
        "parcel": adapted["parcel"],
        "rules": adapted["rules"],
        "preview_key": adapted["preview_key"],
        "image_png_b64": image,
        "steps": ["nlu", "diffusion", "gan_refine", "vectorize", "adapt", "gemini"],
        "method": (method or "procedural") + "+adapt",
    }
