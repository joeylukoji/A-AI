from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.housediff import _load_checkpoint  # noqa: E402


def test_load_checkpoint_prefers_weights_only_true(monkeypatch):
    """`torch.load` doit être tenté d'abord avec `weights_only=True` (mitige la
    désérialisation pickle arbitraire d'un checkpoint model250000.pt corrompu)."""
    calls: list[bool | None] = []

    class FakeTorch:
        @staticmethod
        def load(path, map_location=None, weights_only=None):
            calls.append(weights_only)
            return {"layer.weight": "tensor"}

    monkeypatch.setitem(sys.modules, "torch", FakeTorch())
    out = _load_checkpoint("model250000.pt", "cpu")
    assert out == {"layer.weight": "tensor"}
    assert calls == [True]


def test_load_checkpoint_falls_back_when_weights_only_unsupported(monkeypatch):
    """Repli sur `weights_only=False` uniquement si le format n'est pas couvert
    par la liste blanche — jamais utilisé en priorité."""
    calls: list[bool | None] = []

    class FakeTorch:
        @staticmethod
        def load(path, map_location=None, weights_only=None):
            calls.append(weights_only)
            if weights_only:
                raise RuntimeError("weights_only load failed: unsupported global")
            return {"layer.weight": "tensor"}

    monkeypatch.setitem(sys.modules, "torch", FakeTorch())
    out = _load_checkpoint("model250000.pt", "cpu")
    assert out == {"layer.weight": "tensor"}
    assert calls == [True, False]
