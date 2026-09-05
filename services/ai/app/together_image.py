"""Together AI — disposition LLM (gpt-oss-120b) + image FLUX.2-max.

Le PlanDocument (pièces / murs / meubles) est calculé localement pour l'éditeur.
L'aperçu PNG : plan vectoriel local (pièces + mobilier au bon endroit), puis
`black-forest-labs/FLUX.2-max` le redessine (style Sweet Home 3D).
Repli local si la clé manque.

Config (voir `deploy/.env.example`) :
  TOGETHER_API_KEY        clé API Together — active ce backend si présente
  IMAGE_BACKEND           "together" (défaut si clé présente) ; "procedural" force le rendu local
  TOGETHER_IMAGE_MODEL    défaut "black-forest-labs/FLUX.2-max"
  TOGETHER_IMAGE_STYLE    "illustration" (défaut) | "cad" | "render3d" (cf. diffusion._flux_prompt)
  TOGETHER_IMAGE_LABELS   "none" (défaut, overlay local) | "model" (FLUX lettre, déconseillé)
  TOGETHER_IMAGE_STEPS    optionnel (entier), défaut 32
  TOGETHER_IMAGE_MAX_PX   optionnel, défaut 1024
  TOGETHER_PLANNER        "1" (défaut) | "0" pour couper l'étape LLM de disposition
  TOGETHER_PLANNER_MODEL  défaut "openai/gpt-oss-120b"

Équivalent SDK :

    from together import Together
    client = Together()
    response = client.images.generate(
        prompt="...",
        model="black-forest-labs/FLUX.2-max",
    )
"""
from __future__ import annotations

import base64
import io
import os
import sys
from pathlib import Path
from typing import Any

import httpx

DEFAULT_MODEL = "black-forest-labs/FLUX.2-max"
API_URL = "https://api.together.xyz/v1/images/generations"
CHAT_URL = "https://api.together.xyz/v1/chat/completions"
PLANNER_MODEL = "openai/gpt-oss-120b"
METHOD = "flux2-max"
_STYLE_CACHE: str | None | bool = False  # False = pas encore lu


def _api_key() -> str:
    return (os.getenv("TOGETHER_API_KEY") or os.getenv("TOGETHER_AI_API_KEY") or "").strip()


def model_name() -> str:
    return (os.getenv("TOGETHER_IMAGE_MODEL") or DEFAULT_MODEL).strip()


def available() -> bool:
    """True si l'API Together doit fournir l'image (clé présente + backend non désactivé)."""
    if not _api_key():
        return False
    backend = (os.getenv("IMAGE_BACKEND") or "together").strip().lower()
    return backend in {"", "together", "api", "flux", "flux2", "flux2-dev"}


def planner_model() -> str:
    return (os.getenv("TOGETHER_PLANNER_MODEL") or PLANNER_MODEL).strip()


def planner_enabled() -> bool:
    """True si l'étape LLM de disposition (gpt-oss-120b) doit tourner avant l'image."""
    if not _api_key():
        return False
    flag = (os.getenv("TOGETHER_PLANNER") or "1").strip().lower()
    return flag not in {"0", "off", "false", "no"}


def chat_completion(
    messages: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 1400,
    temperature: float = 0.35,
    timeout: float = 90.0,
    json_mode: bool = False,
) -> str | None:
    """Appel chat Together (SDK si dispo, sinon REST). Retourne le texte de la réponse ou None."""
    key = _api_key()
    if not key:
        return None
    payload: dict[str, Any] = {
        "model": model or planner_model(),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    effort = (os.getenv("TOGETHER_PLANNER_EFFORT") or "low").strip().lower()
    if effort in {"low", "medium", "high"}:
        payload["reasoning_effort"] = effort  # gpt-oss : limite les tokens de raisonnement
    attempts = 2
    try:
        attempts = max(1, int(os.getenv("TOGETHER_CHAT_RETRIES") or 2))
    except ValueError:
        pass
    text: str | None = None
    for _ in range(attempts):  # l'endpoint chat renvoie parfois des 503 transitoires
        text = _chat_via_sdk(payload, timeout) or _chat_via_rest(key, payload, timeout)
        if text:
            break
    text = (text or "").strip()
    return text or None


def _png_b64_to_jpeg_uri(png_b64: str, max_side: int = 768) -> str | None:
    try:
        raw = base64.b64decode(png_b64)
        from PIL import Image

        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=86 if max_side >= 1024 else 72)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] jpeg ref: {exc}", file=sys.stderr)
        return None


def _chat_via_sdk(payload: dict[str, Any], timeout: float = 90.0) -> str | None:
    try:
        from together import Together
    except Exception:
        return None
    try:
        client = Together(api_key=_api_key(), timeout=timeout, max_retries=0)
    except TypeError:
        client = Together(api_key=_api_key())
    lean = {k: v for k, v in payload.items() if k not in ("reasoning_effort", "response_format")}
    for kwargs in (payload, lean):
        try:
            resp = client.chat.completions.create(**kwargs)
            choice = (getattr(resp, "choices", None) or [None])[0]
            msg = getattr(choice, "message", None)
            if msg is None:
                return None
            return getattr(msg, "content", None) or getattr(msg, "reasoning", None)
        except TypeError:
            continue  # SDK plus ancien : réessaie sans reasoning_effort / response_format
        except Exception as exc:  # noqa: BLE001
            print(f"[together_image] chat SDK échec: {exc}", file=sys.stderr)
            return None
    return None


def _chat_via_rest(key: str, payload: dict[str, Any], timeout: float) -> str | None:
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                CHAT_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            choices = (r.json() or {}).get("choices") or []
            if not choices:
                return None
            msg = (choices[0] or {}).get("message") or {}
            return msg.get("content") or msg.get("reasoning")
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] chat REST échec: {exc}", file=sys.stderr)
    return None


def _dims(width_m: float, depth_m: float, max_px: int) -> tuple[int, int]:
    """Dimensions image alignées sur l'emprise, multiples de 32, bornées [512, max_px]."""
    width_m = max(1.0, float(width_m or 1))
    depth_m = max(1.0, float(depth_m or 1))
    if width_m >= depth_m:
        w, h = max_px, max_px * depth_m / width_m
    else:
        w, h = max_px * width_m / depth_m, max_px

    def snap(v: float) -> int:
        return max(512, min(max_px, int(round(v / 32.0)) * 32))

    return snap(w), snap(h)


def generate_floorplan_image(
    prompt: str,
    width_m: float = 12.0,
    depth_m: float = 10.0,
    reference_png_b64: str | None = None,
) -> str | None:
    """PNG base64 depuis FLUX.2-max, ou None si l'appel échoue (fallback rendu local).

    `reference_png_b64` : plan vectoriel (géométrie + mobilier déjà au bon endroit).
    """
    key = _api_key()
    if not key:
        return None
    try:
        max_px = int(os.getenv("TOGETHER_IMAGE_MAX_PX", "1024"))
    except ValueError:
        max_px = 1024
    w, h = _dims(width_m, depth_m, max_px)
    steps = os.getenv("TOGETHER_IMAGE_STEPS", "").strip()
    base: dict[str, Any] = {
        "model": model_name(),
        "prompt": prompt,
        "width": w,
        "height": h,
        "n": 1,
        "response_format": "b64_json",
        "steps": int(steps) if steps.isdigit() else 32,
    }
    data_uri = _as_data_uri(reference_png_b64)
    payload = dict(base)
    if data_uri:
        payload["image_url"] = data_uri
    else:
        print("[together_image] pas de plan de référence — FLUX texte seul", file=sys.stderr)
    kind = "url" if data_uri else "txt"
    print(f"[together_image] FLUX {base['model']} {w}x{h} via={kind}", file=sys.stderr)
    raw_b64 = _via_sdk(payload) or _via_rest(key, payload)
    if raw_b64:
        return _as_png_b64(raw_b64)
    return None


def _as_data_uri(raw_b64: str | None) -> str | None:
    text = (raw_b64 or "").strip()
    if not text:
        return None
    if text.startswith("data:"):
        return text
    return f"data:image/jpeg;base64,{text}"


def style_reference_b64() -> str | None:
    """Capture Sweet Home 3D (image.png) encodée JPEG, pour guider le style FLUX."""
    global _STYLE_CACHE
    if _STYLE_CACHE is not False:
        return _STYLE_CACHE  # type: ignore[return-value]
    path = _style_image_path()
    if not path:
        _STYLE_CACHE = None
        return None
    try:
        from PIL import Image

        img = _strip_app_chrome(Image.open(path).convert("RGB"))
        img = _blank_style_labels(_blank_style_labels(img))
        img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=86)
        _STYLE_CACHE = base64.b64encode(buf.getvalue()).decode("ascii")
        return _STYLE_CACHE
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] style reference illisible: {exc}", file=sys.stderr)
        _STYLE_CACHE = None
        return None


def _blank_style_labels(img):
    """Efface le texte noir des libellés Sweet Home, sans toucher murs gris ni arcs de porte."""
    from PIL import Image, ImageFilter

    orig = img.convert("RGB")
    med = orig.filter(ImageFilter.MedianFilter(size=7))
    src = orig.tobytes()
    fill = med.tobytes()
    out = bytearray(src)
    i, n = 0, len(src)
    while i < n:
        r, g, b = out[i], out[i + 1], out[i + 2]
        luma = (77 * r + 150 * g + 29 * b) >> 8
        chroma = abs(r - g) + abs(g - b) + abs(r - b)
        if luma < 100 and chroma < 45:
            mr, mg, mb = fill[i], fill[i + 1], fill[i + 2]
            if ((77 * mr + 150 * mg + 29 * mb) >> 8) > 115:
                out[i], out[i + 1], out[i + 2] = mr, mg, mb
        i += 3
    return Image.frombytes("RGB", orig.size, bytes(out))


def _strip_app_chrome(img):
    """Retire catalogue / barres d'outils si la source est la capture Sweet Home 3D 1600×946."""
    if img.size == (1600, 946):
        return img.crop((292, 86, 1600, 922))
    return img


def _style_image_path() -> Path | None:
    env = (os.getenv("TOGETHER_STYLE_IMAGE") or "").strip()
    here = Path(__file__).resolve().parent
    candidates: list[Path | None] = [
        Path(env) if env else None,
        here / "assets" / "sweet_home_style.png",
    ]
    for i in (2, 3, 4):
        try:
            candidates.append(here.parents[i] / "image.png")
        except IndexError:
            break
    for p in candidates:
        if p and p.is_file():
            return p
    print("[together_image] capture Sweet Home introuvable (app/assets/sweet_home_style.png)", file=sys.stderr)
    return None


def _as_png_b64(b64: str | None) -> str | None:
    """Normalise la sortie (JPEG/WebP/... selon le modèle) en PNG, contrat `image_png_b64`."""
    if not b64:
        return None
    try:
        import io

        from PIL import Image

        raw = base64.b64decode(b64)
        img = Image.open(io.BytesIO(raw))
        if img.format == "PNG":
            return b64
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] conversion PNG échouée: {exc}", file=sys.stderr)
        return b64


def _via_sdk(payload: dict[str, Any]) -> str | None:
    try:
        from together import Together
    except Exception:
        return None
    try:
        client = Together(api_key=_api_key(), timeout=_image_timeout(), max_retries=0)
        kwargs = dict(payload)
        rf = kwargs.get("response_format")
        if rf == "b64_json":
            kwargs["response_format"] = "base64"
        resp = None
        try:
            resp = client.images.generate(**kwargs)
        except TypeError:
            kwargs.pop("response_format", None)
            resp = client.images.generate(**kwargs)
        data = getattr(resp, "data", None) or []
        if not data:
            return None
        item = data[0]
        b64 = (
            getattr(item, "b64_json", None)
            or getattr(item, "b64", None)
            or (item.get("b64_json") if isinstance(item, dict) else None)
        )
        return b64
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] SDK échec: {exc}", file=sys.stderr)
        return None


def _image_timeout() -> float:
    try:
        return max(30.0, float(os.getenv("TOGETHER_IMAGE_TIMEOUT") or 240))
    except ValueError:
        return 240.0


def _via_rest(key: str, payload: dict[str, Any]) -> str | None:
    try:
        with httpx.Client(timeout=_image_timeout()) as client:
            r = client.post(
                API_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            if r.status_code >= 400:
                print(
                    f"[together_image] REST {r.status_code}: {(r.text or '')[:400]}",
                    file=sys.stderr,
                )
                return None
            data = (r.json() or {}).get("data") or []
            if not data:
                return None
            first = data[0]
            b64 = first.get("b64_json")
            if b64:
                return b64
            url = first.get("url")
            if url:
                img = client.get(url)
                img.raise_for_status()
                return base64.b64encode(img.content).decode("ascii")
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] REST échec: {exc}", file=sys.stderr)
    return None
