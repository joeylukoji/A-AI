from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.diffusion import generate
from app.controlnet_refine import image_to_canny, ink_paper
from app.gan_refine import refine
from app.nlu import parse_brief
from app.plan_render import degrade, layout_to_plan, render_clean_and_mask


def test_refine_stub_keeps_layout(monkeypatch):
    monkeypatch.setenv("AI_STUB", "1")
    spec = parse_brief("Maison 2 chambres", {})
    gen = generate(spec)
    out = refine({"image_png_b64": gen["image_png_b64"], "layout": gen["layout"], "building_spec": spec})
    assert out["method"] == "gan_refine_stub"
    assert out["layout"] is gen["layout"]
    assert out["image_png_b64"]


def test_refine_without_image():
    out = refine({"layout": {"width": 10}})
    assert out["image_png_b64"] == ""
    assert out["layout"]["width"] == 10


def test_render_and_degrade():
    plan = layout_to_plan(
        {
            "width": 10,
            "depth": 8,
            "rooms": [{"type": "living", "polygon": [{"x": 0, "y": 0}, {"x": 5, "y": 0}, {"x": 5, "y": 4}, {"x": 0, "y": 4}]}],
            "walls": [{"id": "w1", "a": {"x": 0, "y": 0}, "b": {"x": 10, "y": 0}, "thickness_m": 0.2}],
        }
    )
    clean, mask = render_clean_and_mask(plan, size=64)
    assert clean.size == (64, 64)
    mask_max = mask.convert("L").getextrema()[1]
    assert isinstance(mask_max, int) and mask_max > 0
    dirty = degrade(clean)
    assert dirty.size == clean.size


def test_canny_keeps_wall_edges():
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (64, 64), "white")
    ImageDraw.Draw(img).rectangle((8, 8, 55, 55), outline="black", width=3)
    edges = image_to_canny(img)
    assert edges.size == (64, 64)
    assert edges.convert("L").getextrema()[1] == 255
    ink = ink_paper(img)
    assert set(ink.convert("L").getdata()) <= {0, 255}  # pyright: ignore[reportArgumentType]  # ImagingCore est bien itérable à l'exécution


def test_controlnet_flag_falls_back_without_weights(monkeypatch):
    monkeypatch.setenv("AI_STUB", "0")
    monkeypatch.setenv("CONTROLNET", "1")
    monkeypatch.setenv("GAN_WEIGHTS", "")
    spec = parse_brief("Maison 2 chambres", {})
    gen = generate(spec)
    out = refine({"image_png_b64": gen["image_png_b64"], "layout": gen["layout"]})
    assert out["layout"] is gen["layout"]
    assert out["method"] in {"controlnet_canny", "gan_refine_stub"}
    assert out["image_png_b64"]


def test_load_checkpoint_prefers_weights_only_true(monkeypatch):
    """`torch.load` doit être tenté d'abord avec `weights_only=True` (mitige la
    désérialisation pickle arbitraire d'un fichier de poids corrompu)."""
    import sys

    from app.gan_refine import _load_checkpoint

    calls: list[bool | None] = []

    class FakeTorch:
        @staticmethod
        def load(path, map_location=None, weights_only=None):
            calls.append(weights_only)
            return {"G": {}, "size": 128, "in_ch": 2}

    monkeypatch.setitem(sys.modules, "torch", FakeTorch())
    out = _load_checkpoint("dummy.pt", "cpu")
    assert out == {"G": {}, "size": 128, "in_ch": 2}
    assert calls == [True]


def test_load_checkpoint_falls_back_when_weights_only_unsupported(monkeypatch):
    """Repli sur `weights_only=False` seulement si la liste blanche refuse le
    format du checkpoint (ex. anciens poids pix2pix) — jamais l'inverse."""
    import sys

    from app.gan_refine import _load_checkpoint

    calls: list[bool | None] = []

    class FakeTorch:
        @staticmethod
        def load(path, map_location=None, weights_only=None):
            calls.append(weights_only)
            if weights_only:
                raise RuntimeError("weights_only load failed: unsupported global")
            return {"G": {}, "size": 128, "in_ch": 2}

    monkeypatch.setitem(sys.modules, "torch", FakeTorch())
    out = _load_checkpoint("dummy.pt", "cpu")
    assert out == {"G": {}, "size": 128, "in_ch": 2}
    assert calls == [True, False]
