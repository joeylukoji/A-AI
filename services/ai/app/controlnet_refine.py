"""Sharpen a floor-plan raster with ControlNet Canny (OpenRAIL). Layout unchanged."""
from __future__ import annotations

import os
from typing import Any

import numpy as np
from PIL import Image, ImageOps

CONTROLNET_ID = "lllyasviel/sd-controlnet-canny"
SD_ID = "runwayml/stable-diffusion-v1-5"
PROMPT = (
    "architectural floor plan, black ink CAD drawing on white paper, "
    "sharp straight walls, doors and windows, high contrast technical blueprint"
)
NEGATIVE = (
    "blurry, photo, 3d render, colorful, furniture clutter, watermark, "
    "gradient, gray mush, noisy, distorted, sketchy"
)

_PIPE: Any = None


def image_to_canny(img: Image.Image, low: int = 80, high: int = 160) -> Image.Image:
    """White edges on black, 3-channel, as required by sd-controlnet-canny."""
    gray = np.asarray(img.convert("L"), dtype=np.uint8)
    try:
        import cv2

        edges = cv2.Canny(gray, low, high)
        if float(edges.mean()) < 2.0:
            edges = cv2.Canny(255 - gray, low, high)
    except ImportError:
        edges = _sobel_edges(gray, low)
    return Image.fromarray(np.stack([edges, edges, edges], axis=-1))


def ink_paper(img: Image.Image) -> Image.Image:
    g = ImageOps.autocontrast(img.convert("L"))
    return g.point(lambda p: 0 if p < 140 else 255).convert("RGB")


def _sobel_edges(gray: np.ndarray, low: int) -> np.ndarray:
    g = gray.astype(np.int16)
    dx = np.zeros_like(g)
    dy = np.zeros_like(g)
    dx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    dy[1:-1, :] = g[2:, :] - g[:-2, :]
    mag = np.clip(np.abs(dx) + np.abs(dy), 0, 255).astype(np.uint8)
    return np.where(mag >= max(30, low // 2), 255, 0).astype(np.uint8)


def try_controlnet(src: Image.Image) -> Image.Image | None:
    """Run pretrained Canny ControlNet. None if packages/GPU missing."""
    if os.getenv("CONTROLNET", "").strip() not in {"1", "canny", "true"}:
        return None
    try:
        import torch
        from diffusers import ControlNetModel, StableDiffusionControlNetPipeline, UniPCMultistepScheduler
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return None

    global _PIPE
    if _PIPE is None:
        dtype = torch.float16
        controlnet = ControlNetModel.from_pretrained(CONTROLNET_ID, torch_dtype=dtype)
        pipe = StableDiffusionControlNetPipeline.from_pretrained(
            SD_ID,
            controlnet=controlnet,
            safety_checker=None,
            torch_dtype=dtype,
        )
        pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
        pipe.enable_model_cpu_offload()
        _PIPE = pipe

    control = image_to_canny(src).resize((512, 512), Image.NEAREST)
    out = _PIPE(
        PROMPT,
        image=control,
        negative_prompt=NEGATIVE,
        num_inference_steps=int(os.getenv("CONTROLNET_STEPS", "20")),
        guidance_scale=7.5,
        controlnet_conditioning_scale=float(os.getenv("CONTROLNET_SCALE", "1.1")),
        generator=torch.Generator(device="cuda").manual_seed(int(os.getenv("CONTROLNET_SEED", "42"))),
    ).images[0]
    out = out.resize(src.size, Image.LANCZOS)
    if os.getenv("CONTROLNET_INK", "1") != "0":
        out = ink_paper(out)
    return out
