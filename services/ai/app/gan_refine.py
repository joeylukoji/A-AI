from __future__ import annotations

import base64
import io
import os
from typing import Any

from PIL import Image, ImageFilter, ImageOps

from . import plan_render


def refine(payload: dict[str, Any]) -> dict[str, Any]:
    """Layout-aware refine: real weights if GAN_WEIGHTS + AI_STUB!=1, else PIL stub."""
    layout = payload.get("layout")
    b64 = payload.get("image_png_b64")
    method = str(payload.get("method") or "")
    if not b64:
        return {"layout": layout, "preview_key": "", "image_png_b64": "", "method": "gan_refine_skip"}

    # Image Together / rendu vectoriel : pas de GAN ni ControlNet (ils dégraderaient le plan).
    if method.startswith(("flux", "together", "gemini", "eden", "vector-plan")):
        return {"layout": layout, "image_png_b64": b64, "preview_key": "", "method": "together_passthrough"}

    if os.getenv("AI_STUB", "1") != "1":
        cn = _try_controlnet(b64)
        if cn is not None:
            return {"layout": layout, "image_png_b64": cn, "preview_key": "", "method": "controlnet_canny"}
        out = _try_gan(b64, layout)
        if out is not None:
            return {"layout": layout, "image_png_b64": out, "preview_key": "", "method": "gan_refine_v1"}

    return {**_stub_filter(b64), "layout": layout, "preview_key": "", "method": "gan_refine_stub"}


def _try_controlnet(b64: str) -> str | None:
    if os.getenv("CONTROLNET", "").strip() not in {"1", "canny", "true"}:
        return None
    from .controlnet_refine import try_controlnet

    raw = base64.b64decode(b64)
    src = Image.open(io.BytesIO(raw)).convert("RGB")
    out = try_controlnet(src)
    if out is None:
        return None
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _posterize(p: int) -> int:
    return 255 if p > 180 else (0 if p < 80 else p)


def _stub_filter(b64: str) -> dict[str, str]:
    raw = base64.b64decode(b64)
    img = Image.open(io.BytesIO(raw)).convert("L")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = img.point(_posterize)
    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return {"image_png_b64": base64.b64encode(buf.getvalue()).decode("ascii")}


def _load_checkpoint(weights_path: str, map_location: str) -> dict[str, Any]:
    """Charge un checkpoint `.pt` en essayant `weights_only=True` d'abord.

    `weights_only=True` (PyTorch >= 2.0) refuse la désérialisation d'objets
    Python arbitraires et évite ainsi une exécution de code si le fichier de
    poids est corrompu ou malveillant. On retombe sur `weights_only=False`
    seulement si le format du checkpoint n'est pas couvert par la liste
    blanche (ex. objets numpy anciens dans un state_dict pix2pix) : le risque
    résiduel est accepté ici car `GAN_WEIGHTS` pointe toujours vers un fichier
    local choisi par l'opérateur, jamais un contenu envoyé par un client.
    """
    import torch

    try:
        return torch.load(weights_path, map_location=map_location, weights_only=True)
    except Exception:
        return torch.load(weights_path, map_location=map_location, weights_only=False)


def _try_gan(b64: str, layout: dict[str, Any] | None) -> str | None:
    weights = os.getenv("GAN_WEIGHTS", "").strip()
    if not weights or not os.path.isfile(weights):
        return None
    try:
        import torch
        from torchvision import transforms
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return None

    raw = base64.b64decode(b64)
    src = Image.open(io.BytesIO(raw)).convert("L")
    orig = src.size
    resampling: Any = getattr(Image, "Resampling", Image)  # Pillow >= 10
    ckpt = _load_checkpoint(weights, "cuda")
    size = int(ckpt.get("size") or 128)
    in_ch = int(ckpt.get("in_ch") or 2)

    plan = layout if layout and layout.get("rooms") is not None else None
    if plan and not plan.get("floor"):
        plan = plan_render.layout_to_plan(layout)
    if plan:
        _, mask = plan_render.render_clean_and_mask(plan, size=size)
    else:
        mask = Image.new("L", (size, size), 0)

    tfm = transforms.Compose(
        [transforms.Resize((size, size)), transforms.ToTensor(), transforms.Normalize((0.5,), (0.5,))]
    )
    coarse = tfm(src.resize((size, size), resampling.BILINEAR))
    mask_t = tfm(mask)
    if not (isinstance(coarse, torch.Tensor) and isinstance(mask_t, torch.Tensor)):
        return None
    x = torch.cat([coarse, mask_t], dim=0).unsqueeze(0).cuda()
    if x.size(1) != in_ch:
        return None

    from .gan_unet import UNet

    G = UNet(in_ch, 1).cuda()
    G.load_state_dict(ckpt["G"])
    G.eval()
    with torch.no_grad():
        y = G(x)[0, 0].clamp(-1, 1)
    pix = ((y.cpu() + 1) * 127.5).byte().numpy()
    out = Image.fromarray(pix, mode="L").resize(orig, resampling.NEAREST).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
