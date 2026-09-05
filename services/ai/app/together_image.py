"""Together AI (NLU / pavage) + image Gemini 3 Pro via Eden AI.

Le PlanDocument (pièces / murs / meubles) est calculé localement pour l'éditeur.
L'aperçu PNG : plan vectoriel local, puis `gemini-3-pro-image-preview` (Eden AI)
le redessine. Repli Together FLUX.2-max si la clé Eden manque, sinon rendu local.

Config (voir `deploy/.env.example`) :
  EDENAI_API_KEY          clé Eden AI — image Gemini (prioritaire sur Flux)
  EDENAI_IMAGE_MODEL      défaut image/generation/google/gemini-3-pro-image-preview
  TOGETHER_API_KEY        clé Together — NLU + pavage, et Flux si Eden absent
  IMAGE_BACKEND           "together" (défaut si une clé image est là) ; "procedural" force le local
  TOGETHER_IMAGE_MODEL    défaut "black-forest-labs/FLUX.2-max" (repli)
  TOGETHER_IMAGE_STYLE    "illustration" (défaut) | "cad" | "render3d"
  TOGETHER_IMAGE_LABELS   "none" (défaut) | "model"
  TOGETHER_IMAGE_STEPS    optionnel (entier), défaut 32
  TOGETHER_IMAGE_MAX_PX   optionnel, défaut 1024
  TOGETHER_PLANNER        "1" (défaut) | "0" pour couper l'étape LLM de disposition
  TOGETHER_PLANNER_MODEL  défaut "openai/gpt-oss-120b"
"""
from __future__ import annotations

import base64
import contextlib
import io
import ipaddress
import os
import socket
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:  # pragma: no cover - typage seulement
    from PIL.Image import Image as PILImage

DEFAULT_MODEL = "black-forest-labs/FLUX.2-max"
API_URL = "https://api.together.xyz/v1/images/generations"
CHAT_URL = "https://api.together.xyz/v1/chat/completions"
EDEN_URL = "https://api.edenai.run/v3/universal-ai/"
EDEN_IMAGES_URL = "https://api.edenai.run/v3/images/generations"
EDEN_EDITS_URL = "https://api.edenai.run/v3/images/edits"
DEFAULT_EDEN_MODEL = "image/generation/google/gemini-3-pro-image-preview"
PLANNER_MODEL = "openai/gpt-oss-120b"
METHOD = "flux2-max"

# Bornes de sécurité sur ce qui vient de l'environnement ou d'une réponse
# externe : sans elles une variable mal réglée (ou un fournisseur qui répond
# n'importe quoi) fait exploser le coût de l'appel, la mémoire du process ou
# le temps de blocage d'un worker.
MIN_IMAGE_PX = 512
MAX_IMAGE_PX = 2048
MAX_IMAGE_STEPS = 100
MAX_CHAT_RETRIES = 5
MAX_IMAGE_TIMEOUT_S = 600.0
MAX_REMOTE_IMAGE_BYTES = 24 * 1024 * 1024
MAX_REMOTE_REDIRECTS = 3
# Un base64 pèse ~4/3 des octets encodés : même plafond que le téléchargement,
# appliqué avant le `b64decode` pour qu'une réponse énorme du fournisseur ne
# soit pas d'abord matérialisée en mémoire.
MAX_IMAGE_B64_CHARS = (MAX_REMOTE_IMAGE_BYTES * 4) // 3 + 4
# Un aperçu fait au plus 1536x1536. Pillow n'échoue qu'au-delà de 178 Mpx
# (avant, il se contente d'un warning) : une image de 150 Mpx passait et
# `convert("RGB")` réclamait ~450 Mo au worker.
MAX_IMAGE_PIXELS = 40_000_000

_STYLE_CACHE: str | None = None
_STYLE_LOADED = False


def _api_key() -> str:
    return (os.getenv("TOGETHER_API_KEY") or os.getenv("TOGETHER_AI_API_KEY") or "").strip()


def _eden_key() -> str:
    return (os.getenv("EDENAI_API_KEY") or os.getenv("EDEN_API_KEY") or "").strip()


def eden_model() -> str:
    return (os.getenv("EDENAI_IMAGE_MODEL") or DEFAULT_EDEN_MODEL).strip()


def _eden_llm_model() -> str:
    """`google/gemini-3-pro-image-preview` pour /v3/images/*."""
    model = eden_model()
    parts = [p for p in model.split("/") if p]
    if len(parts) >= 4 and parts[0] == "image":
        return "/".join(parts[2:])
    return model


def method_name() -> str:
    if _eden_key():
        return "gemini-3-pro-image"
    return METHOD


def model_name() -> str:
    return (os.getenv("TOGETHER_IMAGE_MODEL") or DEFAULT_MODEL).strip()


def _backend_allows_api() -> bool:
    backend = (os.getenv("IMAGE_BACKEND") or "together").strip().lower()
    if backend in {"procedural", "local", "off", "0", "false", "no"}:
        return False
    return backend in {
        "", "together", "api", "flux", "flux2", "flux2-dev", "eden", "edenai", "gemini",
    }


def available() -> bool:
    """True si une API image (Eden Gemini ou Together Flux) doit fournir l'aperçu."""
    if not _backend_allows_api():
        return False
    return bool(_eden_key() or _api_key())


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
    # Borné : `TOGETHER_CHAT_RETRIES=1000000` bloquerait le worker sur un
    # endpoint en panne (chaque tentative pouvant durer `timeout`).
    with contextlib.suppress(ValueError):
        attempts = max(1, min(MAX_CHAT_RETRIES, int(os.getenv("TOGETHER_CHAT_RETRIES") or 2)))
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
    """Dimensions image alignées sur l'emprise, multiples de 32, bornées [512, max_px].

    `max_px` est reborné ici : un `TOGETHER_IMAGE_MAX_PX` en dessous de 512
    donnait un côté supérieur à `max_px` (le plancher gagnait sur le plafond),
    et une valeur énorme réclamait au fournisseur une image hors de prix.
    """
    max_px = max(MIN_IMAGE_PX, min(MAX_IMAGE_PX, int(max_px)))
    width_m = max(1.0, float(width_m or 1))
    depth_m = max(1.0, float(depth_m or 1))
    if width_m >= depth_m:
        w, h = float(max_px), max_px * depth_m / width_m
    else:
        w, h = max_px * width_m / depth_m, float(max_px)

    def snap(v: float) -> int:
        return max(MIN_IMAGE_PX, min(max_px, int(round(v / 32.0)) * 32))

    return snap(w), snap(h)


def generate_floorplan_image(
    prompt: str,
    width_m: float = 12.0,
    depth_m: float = 10.0,
    reference_png_b64: str | None = None,
) -> str | None:
    """PNG base64 depuis Gemini (Eden) ou FLUX.2-max, sinon None (repli local).

    `reference_png_b64` : plan vectoriel (géométrie + mobilier déjà au bon endroit).
    """
    if not available():
        return None
    if _eden_key():
        return _via_eden(prompt, width_m, depth_m, reference_png_b64)
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
        # Borné : le nombre d'étapes est facturé, `TOGETHER_IMAGE_STEPS=100000`
        # partait droit vers un appel interminable et hors de prix.
        "steps": min(MAX_IMAGE_STEPS, max(1, int(steps))) if steps.isdigit() else 32,
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


def _eden_size(width_m: float, depth_m: float) -> str:
    """Gemini Image accepte surtout 1024² / 1536×1024 / 1024×1536."""
    width_m = max(1.0, float(width_m or 1))
    depth_m = max(1.0, float(depth_m or 1))
    if width_m >= depth_m * 1.15:
        return "1536x1024"
    if depth_m >= width_m * 1.15:
        return "1024x1536"
    return "1024x1024"


def _via_eden(
    prompt: str,
    width_m: float,
    depth_m: float,
    reference_png_b64: str | None,
) -> str | None:
    key = _eden_key()
    if not key:
        return None
    size = _eden_size(width_m, depth_m)
    data_uri = _as_data_uri(reference_png_b64)
    llm_model = _eden_llm_model()
    if data_uri:
        payload: dict[str, Any] = {
            "model": llm_model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
            "images": [{"image_url": data_uri}],
        }
        url = EDEN_EDITS_URL
        kind = "edit"
    else:
        payload = {
            "model": llm_model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }
        url = EDEN_IMAGES_URL
        kind = "txt"
        print("[together_image] pas de plan de référence — Gemini texte seul", file=sys.stderr)
    print(f"[together_image] Eden {llm_model} {size} via={kind}", file=sys.stderr)
    # Budget global : les trois tentatives enchaînées pouvaient bloquer un
    # worker pendant 3 x `_image_timeout()` (jusqu'à 30 min) sur un
    # fournisseur muet. Chaque repli n'a droit qu'au temps restant.
    deadline = time.monotonic() + _image_timeout()
    data = _eden_post(url, key, payload, _remaining(deadline))
    raw = _eden_image_b64(data) if data else None
    if not raw and data_uri and _remaining(deadline) > 0:
        print("[together_image] Eden edit échec — repli génération texte", file=sys.stderr)
        data = _eden_post(
            EDEN_IMAGES_URL,
            key,
            {
                "model": llm_model,
                "prompt": prompt,
                "size": size,
                "n": 1,
                "response_format": "b64_json",
            },
            _remaining(deadline),
        )
        raw = _eden_image_b64(data) if data else None
    if not raw and _remaining(deadline) > 0:
        print("[together_image] Eden images échec — repli universal-ai", file=sys.stderr)
        data = _eden_post(
            EDEN_URL,
            key,
            {
                "model": eden_model(),
                "input": {"text": prompt, "resolution": size, "num_images": 1},
                "show_original_response": False,
            },
            _remaining(deadline),
        )
        raw = _eden_image_b64(data) if data else None
    if not raw:
        print("[together_image] Eden: pas d'image dans la réponse", file=sys.stderr)
        return None
    return _as_png_b64(raw)


MIN_EDEN_ATTEMPT_S = 5.0


def _remaining(deadline: float) -> float:
    """Temps restant du budget image, 0 s'il est épuisé."""
    left = deadline - time.monotonic()
    return left if left >= MIN_EDEN_ATTEMPT_S else 0.0


def _eden_post(
    url: str, key: str, payload: dict[str, Any], timeout: float | None = None
) -> dict[str, Any] | None:
    try:
        with httpx.Client(timeout=timeout or _image_timeout()) as client:
            r = client.post(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            if r.status_code >= 400:
                print(
                    f"[together_image] Eden {r.status_code} {url}: {(r.text or '')[:400]}",
                    file=sys.stderr,
                )
                return None
            data = r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] Eden échec {url}: {exc}", file=sys.stderr)
        return None
    # Le contrôle `isinstance` était fait *après* `data.get(...)` : un corps
    # JSON qui n'est pas un objet (liste, chaîne, nombre) faisait remonter un
    # AttributeError hors du `try` — 500 côté API, étape image perdue au lieu
    # du repli sur le rendu local.
    if not isinstance(data, dict):
        print(f"[together_image] Eden {url}: réponse JSON inattendue ({type(data).__name__})", file=sys.stderr)
        return None
    status = str(data.get("status") or "").lower()
    if status and status not in {"success", "ok"}:
        err = data.get("error") or data
        print(f"[together_image] Eden status={data.get('status')}: {err}", file=sys.stderr)
        return None
    return data


def _strip_b64(raw: Any) -> str | None:
    """Base64 nu extrait d'un champ de réponse, ou None s'il est inexploitable."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    if len(raw) > MAX_IMAGE_B64_CHARS:
        print(
            f"[together_image] image inline > {MAX_REMOTE_IMAGE_BYTES} o — ignorée",
            file=sys.stderr,
        )
        return None
    text = raw.strip()
    if "base64," in text[:80]:
        text = text.split("base64,", 1)[1]
    return text or None


def _is_public_https_url(url: Any) -> bool:
    """Vrai si l'URL est en HTTPS et ne vise pas une adresse interne.

    Bloque les cibles qu'un fournisseur compromis pourrait nous faire
    interroger depuis l'intérieur du réseau : loopback, lien-local
    (169.254.169.254 = métadonnées cloud), réseaux privés, multicast.
    """
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    try:
        host = httpx.URL(url).host
    except Exception:  # noqa: BLE001 — URL malformée
        return False
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def _fetch_image_url(url: Any) -> str | None:
    """Télécharge une image pointée par une réponse externe, sous contraintes.

    L'URL vient du fournisseur, pas de nous : on exige HTTPS vers une adresse
    publique (pas de `file:`, ni `http://169.254.169.254/...` ou autre cible
    interne) et on plafonne la taille lue, pour qu'une réponse hostile ou
    cassée ne puisse ni sonder le réseau interne ni faire exploser la mémoire.

    Les redirections sont suivies à la main : `follow_redirects=True` laissait
    une réponse hostile rebondir d'une URL HTTPS publique vers une cible
    interne, ce qui annulait le contrôle ci-dessus. Chaque saut est revalidé.

    Limite connue : la validation porte sur la résolution DNS faite ici, donc
    un rebinding DNS entre ce contrôle et la requête reste théoriquement
    possible ; l'empêcher demanderait d'épingler l'IP résolue au transport.
    """
    if not _is_public_https_url(url):
        return None
    current = str(url)
    try:
        with httpx.Client(timeout=60.0, follow_redirects=False) as client:
            for _ in range(MAX_REMOTE_REDIRECTS + 1):
                with client.stream("GET", current) as r:
                    if r.is_redirect:
                        nxt = r.headers.get("location") or ""
                        nxt = str(httpx.URL(current).join(nxt))
                        if not _is_public_https_url(nxt):
                            print(
                                "[together_image] redirection vers une cible non publique — ignorée",
                                file=sys.stderr,
                            )
                            return None
                        current = nxt
                        continue
                    r.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in r.iter_bytes():
                        total += len(chunk)
                        if total > MAX_REMOTE_IMAGE_BYTES:
                            print(
                                f"[together_image] image distante > {MAX_REMOTE_IMAGE_BYTES} o — ignorée",
                                file=sys.stderr,
                            )
                            return None
                        chunks.append(chunk)
                    content = b"".join(chunks)
                    if not content:
                        return None
                    return base64.b64encode(content).decode("ascii")
        print("[together_image] trop de redirections — ignorée", file=sys.stderr)
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] Eden download échec: {exc}", file=sys.stderr)
        return None


def _eden_image_b64(data: dict[str, Any]) -> str | None:
    output = data.get("output")
    for items in (
        data.get("data"),
        output.get("items") if isinstance(output, dict) else None,
    ):
        if not isinstance(items, list) or not items:
            continue
        first = items[0] if isinstance(items[0], dict) else {}
        raw = _strip_b64(
            first.get("b64_json") or first.get("image") or first.get("base64")
        )
        if raw:
            return raw
        fetched = _fetch_image_url(
            first.get("url") or first.get("image_resource_url") or first.get("image_url")
        )
        if fetched:
            return fetched
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
    global _STYLE_CACHE, _STYLE_LOADED

    if _STYLE_LOADED:
        return _STYLE_CACHE
    _STYLE_LOADED = True
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
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] style reference illisible: {exc}", file=sys.stderr)
        _STYLE_CACHE = None
    return _STYLE_CACHE


def _blank_style_labels(img: PILImage) -> PILImage:
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


def _strip_app_chrome(img: PILImage) -> PILImage:
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
    """Normalise la sortie (JPEG/WebP/... selon le modèle) en PNG, contrat `image_png_b64`.

    Renvoie `None` si le contenu renvoyé par le fournisseur n'est pas une image
    décodable : le champ s'appelle `image_png_b64` et est servi tel quel au
    client, on ne laisse donc pas passer un blob arbitraire. L'appelant retombe
    alors sur le rendu vectoriel local.
    """
    if not b64 or len(b64) > MAX_IMAGE_B64_CHARS:
        return None
    try:
        from PIL import Image

        raw = base64.b64decode(b64, validate=True)
        img = Image.open(io.BytesIO(raw))
        pixels = img.width * img.height
        if pixels > MAX_IMAGE_PIXELS:
            print(
                f"[together_image] image {img.width}x{img.height} trop grande — ignorée",
                file=sys.stderr,
            )
            return None
        img.verify()  # rejette un contenu tronqué / non-image
        if img.format == "PNG":
            return b64
        buf = io.BytesIO()
        Image.open(io.BytesIO(raw)).convert("RGB").save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] réponse image invalide, ignorée: {exc}", file=sys.stderr)
        return None


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
    """Timeout HTTP de l'appel image, borné des deux côtés.

    Sans plafond, `TOGETHER_IMAGE_TIMEOUT` mal réglé immobilisait un worker (et
    la requête HTTP qui l'attend) pendant des heures sur un fournisseur muet.
    """
    try:
        return max(30.0, min(MAX_IMAGE_TIMEOUT_S, float(os.getenv("TOGETHER_IMAGE_TIMEOUT") or 240)))
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
            if not isinstance(data, list) or not data:
                return None
            first = data[0] if isinstance(data[0], dict) else {}
            b64 = _strip_b64(first.get("b64_json"))
            if b64:
                return b64
        # Hors du client ci-dessus : `_fetch_image_url` borne HTTPS + taille,
        # au lieu d'aspirer sans limite une URL choisie par le fournisseur.
        return _fetch_image_url(first.get("url"))
    except Exception as exc:  # noqa: BLE001
        print(f"[together_image] REST échec: {exc}", file=sys.stderr)
    return None
