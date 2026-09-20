"""Accès à un LLM, sans dépendance : n'importe quel service « chat completions » compatible OpenAI."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable

LLM = Callable[[str, str], str]          # (système, utilisateur) -> texte


def from_env() -> LLM | None:
    """Un client construit depuis l'environnement, ou None (le styliste retombe alors sur ses règles).

    HOMEKIT_LLM_URL, HOMEKIT_LLM_KEY, HOMEKIT_LLM_MODEL ; à défaut TOGETHER_API_KEY (Together AI).
    """
    key = os.environ.get("HOMEKIT_LLM_KEY") or os.environ.get("TOGETHER_API_KEY") or ""
    if not key or os.environ.get("HOMEKIT_LLM", "1").lower() in {"0", "off", "false", "no"}:
        return None
    url = os.environ.get("HOMEKIT_LLM_URL") or "https://api.together.xyz/v1/chat/completions"
    model = os.environ.get("HOMEKIT_LLM_MODEL") or "openai/gpt-oss-120b"
    return chat_client(url, key, model)


def chat_client(url: str, key: str, model: str, *, timeout: float = 12.0, max_tokens: int = 900) -> LLM:
    def call(system: str, user: str) -> str:
        body = json.dumps({"model": model, "max_tokens": max_tokens, "temperature": 0.4,
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                           "response_format": {"type": "json_object"}}).encode()
        req = urllib.request.Request(url, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return (data["choices"][0]["message"].get("content") or "").strip()

    return call
