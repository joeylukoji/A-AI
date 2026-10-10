"""Characterize the shared use case and the transport boundaries."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import httpx
import pytest
from app import diffusion, pipeline, worker
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def stages(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Distinct intermediate/final documents expose accidental stale references."""
    state: dict[str, Any] = {"calls": [], "preview_calls": []}
    state["spec"] = {"rooms": [], "constraints": {"max_width_m": 12, "max_depth_m": 10}}
    state["adapted"] = {
        "plan_document": {
            "version": "1.0",
            "units": "m",
            "floor": {"bounds": {"width": 6, "depth": 4}},
            "walls": [
                {"id": "w1", "a": {"x": 0, "y": 0}, "b": {"x": 6, "y": 0}},
                {"id": "w2", "a": {"x": 6, "y": 0}, "b": {"x": 6, "y": 4}},
                {"id": "w3", "a": {"x": 6, "y": 4}, "b": {"x": 0, "y": 4}},
                {"id": "w4", "a": {"x": 0, "y": 4}, "b": {"x": 0, "y": 0}},
            ],
            "rooms": [
                {
                    "id": "final",
                    "polygon": [{"x": 0, "y": 0}, {"x": 6, "y": 0}, {"x": 6, "y": 4}],
                }
            ],
            "layout": {"parti": "zoned", "seed": 42},
        },
        "compliance": {"score": 88},
        "dimensions": [{"id": "final", "width_m": 6}],
        "parcel": {"width_m": 14},
        "rules": {"grid_m": 0.1},
    }

    def parse(brief: str, constraints: dict[str, Any]) -> dict[str, Any]:
        state["calls"].append(("nlu", brief, deepcopy(constraints)))
        return state["spec"]

    def generate(spec: dict[str, Any], *, image: bool) -> dict[str, Any]:
        assert spec == state["spec"]
        assert image is False
        return {
            "layout": {"rooms": ["initial"]},
            "method": "procedural",
            "preview_key": "key",
        }

    def refine(payload: dict[str, Any]) -> dict[str, Any]:
        assert payload["layout"] == {"rooms": ["initial"]}
        return {"layout": {"rooms": ["refined"]}}

    def vectorize(payload: dict[str, Any]) -> dict[str, Any]:
        assert payload["layout"] == {"rooms": ["refined"]}
        state["vectorize_input"] = deepcopy(payload)
        return {"plan_document": {"rooms": ["intermediate"]}}

    def adapt(payload: dict[str, Any]) -> dict[str, Any]:
        assert payload["plan_document"] == {"rooms": ["intermediate"]}
        state["adapt_input"] = deepcopy(payload)
        return deepcopy(state["adapted"])

    def preview(
        brief: str, constraints: dict[str, Any], **kwargs: Any
    ) -> tuple[str, str]:
        assert kwargs["doc"] == state["adapted"]["plan_document"]
        assert kwargs["spec"] == state["spec"]
        assert "job_id" not in kwargs  # transport callback stays outside the use case
        state["preview_calls"].append(deepcopy(kwargs["doc"]))
        return "final-png", "procedural"

    monkeypatch.setattr(pipeline.nlu, "parse_brief", parse)
    monkeypatch.setattr(pipeline.diffusion, "generate", generate)
    monkeypatch.setattr(pipeline.gan_refine, "refine", refine)
    monkeypatch.setattr(pipeline.vectorize, "vectorize", vectorize)
    monkeypatch.setattr(pipeline.plan_adapt, "adapt", adapt)
    monkeypatch.setattr(pipeline.diffusion, "preview_from_document", preview)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    return state


def test_final_document_and_preview_follow_one_ordered_pipeline(
    stages: dict[str, Any],
) -> None:
    progress: list[str] = []
    constraints = {"parcel_width_m": 14, "setback_m": 1, "rules": {"grid_m": 0.2}}
    before = deepcopy(constraints)
    result = pipeline.generate_plan("Maison", constraints, progress=progress.append)
    assert progress == ["nlu", "diffusion", "refine", "vectorize", "adapt", "gemini"]
    assert result["plan_document"] == stages["adapted"]["plan_document"]
    assert result["compliance"] == stages["adapted"]["compliance"]
    assert result["image_png_b64"] == "final-png"
    assert result["preview_key"] == "key"
    assert result["method"] == "procedural+adapt"
    assert len(stages["preview_calls"]) == 1
    assert stages["adapt_input"]["parcel"] == {
        "width_m": 14,
        "depth_m": 10,
        "setback_m": 1,
    }
    assert stages["adapt_input"]["rules"] == constraints["rules"]
    assert constraints == before


def test_edit_rebuild_reuses_vector_stages_without_rendering(
    stages: dict[str, Any],
) -> None:
    result = diffusion._adapted_from_spec(stages["spec"], {})
    assert result["plan_document"] == stages["adapted"]["plan_document"]
    assert not stages["preview_calls"]
    assert not stages["calls"]  # the existing program does not go through NLU again


def test_edit_rebuild_threads_source_layout_without_leaking_internal_constraint(
    stages: dict[str, Any],
) -> None:
    source_layout = {"parti": "zoned", "seed": 31, "arr": "L2|R1|B2"}

    diffusion._adapted_from_spec(
        stages["spec"], {"parcel_width_m": 14, "_aai_source_layout": source_layout}
    )

    assert stages["vectorize_input"]["preferred_layout"] == source_layout
    assert stages["adapt_input"]["parcel"]["width_m"] == 14
    assert "_aai_source_layout" not in stages["adapt_input"]["parcel"]


def test_invalid_stage_output_cannot_reach_preview(stages):
    from app.plan_contracts import GeneratedDocumentError

    stages["adapted"]["plan_document"]["walls"][0]["a"]["x"] = None
    with pytest.raises(GeneratedDocumentError, match="invalid_number"):
        pipeline.generate_plan("Maison", {})
    assert not stages["preview_calls"]


def _capture_worker(
    monkeypatch: pytest.MonkeyPatch, status: int = 200
) -> list[tuple[str, dict[str, Any]]]:
    import json

    calls: list[tuple[str, dict[str, Any]]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Internal-Token"] == "worker-token"
        payload = json.loads(request.content)
        calls.append((request.url.path, payload))
        if request.url.path.endswith("/revisions"):
            return httpx.Response(status, json={"id": "revision", "version": 3})
        return httpx.Response(200, json={})

    client_class = httpx.Client
    monkeypatch.setattr(
        worker.httpx,
        "Client",
        lambda **kw: client_class(transport=httpx.MockTransport(handle), **kw),
    )
    return calls


def test_http_and_worker_persist_the_same_pipeline_result(
    stages: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = pipeline.generate_plan("Maison", {})
    with TestClient(app) as client:
        response = client.post(
            "/v1/pipeline", json={"brief": "Maison", "constraints": None}
        )
    assert response.status_code == 200
    assert response.json() == expected
    calls = _capture_worker(monkeypatch)
    worker._process(
        {"job_id": "job", "project_id": "project", "input": {"brief": "Maison"}},
        "http://api",
        "worker-token",
    )
    saved = next(payload for path, payload in calls if path.endswith("/revisions"))
    for key in (
        "building_spec",
        "plan_document",
        "compliance",
        "preview_key",
        "image_png_b64",
    ):
        assert saved[key] == expected[key]
    completed = calls[-1][1]
    assert completed["status"] == "succeeded"
    assert completed["output"] == {
        "revision_id": "revision",
        "version": 3,
        "method": expected["method"],
    }


def test_worker_reports_failure_without_persisting_partial_plan(
    stages: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise ValueError("invalid layout")

    monkeypatch.setattr(pipeline.diffusion, "generate", fail)
    calls = _capture_worker(monkeypatch)
    with pytest.raises(ValueError, match="invalid layout"):
        worker._process(
            {"job_id": "job", "project_id": "project"}, "http://api", "worker-token"
        )
    assert calls[-1][1]["status"] == "failed"
    assert all(not path.endswith("/revisions") for path, _ in calls)
    assert not stages["preview_calls"]


def test_worker_does_not_announce_success_if_revision_is_rejected(
    stages: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _capture_worker(monkeypatch, status=503)
    with pytest.raises(httpx.HTTPStatusError):
        worker._process(
            {"job_id": "job", "project_id": "project"}, "http://api", "worker-token"
        )
    assert calls[-1][1]["status"] == "failed"
    assert sum(path.endswith("/revisions") for path, _ in calls) == 1
    assert not any(payload.get("status") == "succeeded" for _, payload in calls)
