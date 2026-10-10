"""Actual provenance is independent of legacy stage labels and concurrent requests."""

import asyncio
import base64
import io

import httpx
import pytest
from app import diffusion, generation_trace, pipeline, together_image
from PIL import Image


def test_capture_restores_nested_context():
    with generation_trace.capture() as outer:
        generation_trace.preview_result("local")
        with generation_trace.capture() as inner:
            generation_trace.preview_result("gemini")
        generation_trace.http_attempt()
    assert outer["preview"]["backend"] == "local"
    assert outer["preview"]["generation_http_attempts"] == 1
    assert inner["preview"]["generation_http_attempts"] == 0
    generation_trace.http_attempt()
    assert outer["preview"]["generation_http_attempts"] == 1


def test_concurrent_capture_is_isolated():
    async def collect(backend):
        with generation_trace.capture() as trace:
            generation_trace.preview_result(backend)
            await asyncio.sleep(0)
            return trace["preview"]["backend"]

    async def scenario():
        return await asyncio.gather(collect("local"), collect("gemini"))

    assert asyncio.run(scenario()) == ["local", "gemini"]


@pytest.mark.parametrize(
    "method,reason",
    [
        ("flux-skipped", "disabled_or_unconfigured"),
        ("flux-failed", "provider_failed"),
    ],
)
def test_preview_fallback_is_local_even_with_legacy_method(monkeypatch, method, reason):
    monkeypatch.setattr(diffusion, "generate_flux_plan", lambda *a, **kw: ("", method))
    monkeypatch.setattr(diffusion, "render_plan_document", lambda doc: "local-png")
    with generation_trace.capture() as trace:
        assert diffusion.preview_from_document("brief", {}, spec={}, doc={}) == ("local-png", method)
    assert trace["preview"]["backend"] == "local"
    assert trace["preview"]["fallback_reason"] == reason
    assert trace["preview"]["generation_http_attempts"] == 0


@pytest.mark.parametrize("failures", [0, 1, 2])
def test_provider_invocation_and_http_retries_are_distinct(monkeypatch, failures):
    monkeypatch.setenv("EDENAI_API_KEY", "test-only")
    monkeypatch.setenv("IMAGE_BACKEND", "gemini")
    monkeypatch.delenv("GEMINI_TEXT_FALLBACK", raising=False)
    buf = io.BytesIO()
    Image.new("RGB", (32, 32)).save(buf, format="PNG")
    png = base64.b64encode(buf.getvalue()).decode("ascii")
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) <= failures:
            return httpx.Response(503, json={"error": "test"})
        return httpx.Response(200, json={"data": [{"b64_json": png}]})

    client = httpx.Client
    monkeypatch.setattr(
        together_image.httpx, "Client", lambda **kw: client(transport=httpx.MockTransport(respond), **kw)
    )
    with generation_trace.capture() as trace:
        result = together_image.generate_floorplan_image("plan", reference_png_b64=png)
    assert bool(result) == (failures < 2)
    assert trace["preview"]["provider_invocations"] == 1
    assert trace["preview"]["generation_http_attempts"] == min(failures + 1, 2)
    assert trace["preview"]["model_requested"] == together_image._eden_llm_model()
    assert trace["preview"]["model_configured"] == together_image.eden_model()
    assert trace["preview"]["attempt_models"] == [together_image._eden_llm_model()] * len(calls)
    assert trace["preview"]["model_reported"] is None


def test_pipeline_records_renderer_and_skip(monkeypatch):
    monkeypatch.setattr(pipeline.nlu, "parse_brief", lambda *a: {})
    monkeypatch.setattr(
        pipeline,
        "build_document",
        lambda *a, **kw: {
            "plan_document": {},
            "compliance": {},
            "dimensions": [],
            "parcel": {},
            "rules": {},
            "preview_key": "",
        },
    )
    monkeypatch.setattr(diffusion, "generate_flux_plan", lambda *a, **kw: ("api-png", "gemini-3-pro-image"))
    result = pipeline.generate_plan("brief")
    assert result["provenance"]["preview"]["backend"] == "gemini"
    assert result["provenance"]["refinement"] == "unknown"  # stage replaced by test double
