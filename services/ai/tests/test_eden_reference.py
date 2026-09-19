"""Aperçu Gemini : l'appel Eden ne perd pas le plan de référence.

Aucun appel réseau : `_eden_post` est remplacé.
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from app import together_image  # noqa: E402


def _png_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 200, 200)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


REF = base64.b64encode(b"ref").decode("ascii")


@pytest.fixture
def eden(monkeypatch):
    """Simule Eden : `script` donne la réponse de chaque appel, `urls` garde l'historique."""
    monkeypatch.setenv("EDENAI_API_KEY", "dummy")
    monkeypatch.setenv("IMAGE_BACKEND", "gemini")
    monkeypatch.delenv("GEMINI_TEXT_FALLBACK", raising=False)
    monkeypatch.setattr(together_image, "_as_data_uri", lambda b64: "data:image/png;base64," + b64 if b64 else None)
    state = {"script": [], "urls": []}

    def post(url, key, payload, timeout=None):
        state["urls"].append(url)
        step = state["script"].pop(0) if state["script"] else None
        return {"data": [{"b64_json": _png_b64()}]} if step == "ok" else None

    monkeypatch.setattr(together_image, "_eden_post", post)
    return state


def test_a_failed_edit_is_retried_with_the_reference_plan(eden):
    eden["script"] = [None, "ok"]
    assert together_image.generate_floorplan_image("plan", 12, 10, reference_png_b64=REF)
    assert eden["urls"] == [together_image.EDEN_EDITS_URL] * 2


def test_without_success_the_reference_plan_is_never_dropped(eden):
    """Sinon Gemini invente un plan : on rend None et le pipeline garde le rendu vectoriel exact."""
    eden["script"] = [None, None, "ok", "ok"]           # les repli « texte seul » auraient réussi
    assert together_image.generate_floorplan_image("plan", 12, 10, reference_png_b64=REF) is None
    assert eden["urls"] == [together_image.EDEN_EDITS_URL] * 2


def test_the_blind_fallback_can_be_switched_back_on(eden, monkeypatch):
    monkeypatch.setenv("GEMINI_TEXT_FALLBACK", "1")
    eden["script"] = [None, None, "ok"]
    assert together_image.generate_floorplan_image("plan", 12, 10, reference_png_b64=REF)
    assert eden["urls"] == [together_image.EDEN_EDITS_URL] * 2 + [together_image.EDEN_IMAGES_URL]


def test_without_a_reference_the_text_paths_still_work(eden):
    eden["script"] = [None, "ok"]
    assert together_image.generate_floorplan_image("plan", 12, 10)
    assert eden["urls"] == [together_image.EDEN_IMAGES_URL, together_image.EDEN_URL]


def test_a_first_success_costs_a_single_call(eden):
    eden["script"] = ["ok"]
    assert together_image.generate_floorplan_image("plan", 12, 10, reference_png_b64=REF)
    assert len(eden["urls"]) == 1


@pytest.mark.parametrize("value,expected", [("1", True), ("true", True), ("ON", True), ("", False), ("0", False)])
def test_text_fallback_flag(monkeypatch, value, expected):
    monkeypatch.setenv("GEMINI_TEXT_FALLBACK", value)
    assert together_image._text_fallback_allowed() is expected
