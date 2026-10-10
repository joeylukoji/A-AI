"""Request-scoped provenance, separate from legacy progress notifications."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_CURRENT: ContextVar[dict[str, Any] | None] = ContextVar("generation_trace", default=None)


@contextmanager
def capture() -> Iterator[dict[str, Any]]:
    """Collect a trace isolated from concurrent requests and nested generations."""
    trace: dict[str, Any] = {
        "version": 1,
        "refinement": "unknown",
        "preview": {
            "backend": "unknown",
            "model_requested": None,
            "model_configured": None,
            "model_reported": None,
            "provider_invocations": 0,
            "generation_http_attempts": 0,
            "attempt_models": [],
            "download_http_attempts": None,
            "fallback_reason": None,
        },
    }
    token = _CURRENT.set(trace)
    try:
        yield trace
    finally:
        _CURRENT.reset(token)


def refinement(method: str) -> None:
    """Record the refinement that actually ran, including explicit skips."""
    if trace := _CURRENT.get():
        trace["refinement"] = method


def preview_result(backend: str, *, fallback_reason: str | None = None) -> None:
    """Record the effective renderer without changing compatibility method names."""
    if trace := _CURRENT.get():
        trace["preview"].update(backend=backend, fallback_reason=fallback_reason)


def provider_invocation(model: str, *, configured_model: str) -> None:
    """Count a logical image-provider invocation; retries are HTTP attempts."""
    if trace := _CURRENT.get():
        trace["preview"]["provider_invocations"] += 1
        trace["preview"]["model_requested"] = model
        trace["preview"]["model_configured"] = configured_model


def http_attempt(model: str | None = None) -> None:
    """Count generation POST attempts, not subsequent image downloads."""
    if trace := _CURRENT.get():
        trace["preview"]["generation_http_attempts"] += 1
        trace["preview"]["attempt_models"].append(model)
