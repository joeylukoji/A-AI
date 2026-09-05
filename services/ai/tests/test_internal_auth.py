from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

client = TestClient(app)


def test_v1_endpoints_open_when_internal_token_unset(monkeypatch):
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    res = client.get("/v1/adapt/rules")
    assert res.status_code == 200


def test_v1_endpoint_rejects_missing_token_when_configured(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "shared-secret")
    res = client.post("/v1/generate", json={})
    assert res.status_code == 401


def test_v1_endpoint_rejects_wrong_token_when_configured(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "shared-secret")
    res = client.post(
        "/v1/generate", json={}, headers={"X-Internal-Token": "wrong"}
    )
    assert res.status_code == 401


def test_v1_endpoint_accepts_correct_token_when_configured(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "shared-secret")
    res = client.post(
        "/v1/pipeline",
        json={"brief": "Maison 3 chambres avec garage", "constraints": None},
        headers={"X-Internal-Token": "shared-secret"},
    )
    assert res.status_code == 200, res.text


def test_healthz_never_requires_token(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "shared-secret")
    res = client.get("/healthz")
    assert res.status_code == 200


def test_adapt_rules_stays_public_read_only_endpoint(monkeypatch):
    # /v1/adapt/rules only returns static default rules (no cost, no user
    # data) — deliberately left open even when INTERNAL_TOKEN is configured.
    monkeypatch.setenv("INTERNAL_TOKEN", "shared-secret")
    res = client.get("/v1/adapt/rules")
    assert res.status_code == 200
