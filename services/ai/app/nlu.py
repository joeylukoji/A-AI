from __future__ import annotations

import os
import re
from typing import Any

_ALLOWED_TYPES = {
    "living", "kitchen", "bedroom", "bathroom", "wc", "hallway",
    "garage", "dining", "office", "storage", "laundry",
}

_NLU_SYSTEM = (
    "You extract a residential room program from a French or English brief. "
    "Return STRICT JSON only.\n"
    "RULES\n"
    "- Include only rooms the user asked for, plus the dwelling core: living, kitchen, "
    "bathroom, and bedrooms when a house/apartment is implied.\n"
    "- Do NOT invent garage, office, dining, laundry, storage, or a second bathroom "
    "unless the brief mentions them.\n"
    "- Add hallway only if there are 2 or more bedrooms (circulation).\n"
    "- Add wc only if the brief mentions WC / toilettes as a separate room.\n"
    "- type must be one of: living, kitchen, bedroom, bathroom, wc, hallway, garage, "
    "dining, office, storage, laundry.\n"
    "- Bedroom count must match the brief (T3/F3 => 2 bedrooms). Studio/T1 => 0 bedrooms.\n"
    "OUTPUT: {\"style\": \"contemporary\", \"floors\": 1, \"rooms\": "
    "[{\"type\": \"living\", \"area_m2\": 28, \"count\": 1}]}"
)


def parse_brief(brief: str, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    """BuildingSpec : LLM Together si dispo, sinon heuristique. Jamais de pièce inventée hors brief."""
    constraints = constraints or {}
    heuristic = _heuristic_parse(brief, constraints)
    llm = _llm_parse(brief, constraints, heuristic)
    return llm or heuristic


def _heuristic_parse(brief: str, constraints: dict[str, Any]) -> dict[str, Any]:
    text = brief.lower()
    rooms: list[dict[str, Any]] = []
    rid = 1

    bedroom_count, is_studio = _bedroom_count(text)

    def add(room_type: str, area: float, count: int = 1, **extra: Any) -> None:
        nonlocal rid
        rooms.append({"id": f"r{rid}", "type": room_type, "area_m2": area, "count": count, **extra})
        rid += 1

    add("living", float(constraints.get("living_area_m2", 22 if is_studio else 30)))
    open_to = ["r1"] if "ouverte" in text else []
    add("kitchen", 8 if is_studio else 12, open_to=open_to, adjacent_to=["r1"])
    if bedroom_count:
        add("bedroom", 12, count=bedroom_count, adjacent_to=["r1"])
    add("bathroom", 5 if is_studio else 6)
    if bedroom_count >= 3 or re.search(r"(deux|2)\s+salles?\s+de\s+bain", text):
        add("bathroom", 5)
    if bedroom_count >= 2:
        add("hallway", 8, adjacent_to=["r1"])
    if "garage" in text:
        add("garage", 18)
    if "bureau" in text or "office" in text:
        add("office", 10)
    if "salle à manger" in text or "salle a manger" in text or "dining" in text:
        add("dining", 14, adjacent_to=["r1"])
    if "wc" in text or "toilette" in text:
        add("wc", 2)
    if "buanderie" in text or "laundry" in text:
        add("laundry", 4)
    if "cellier" in text or "rangement" in text or "débarras" in text or "debarra" in text:
        add("storage", 3)

    return _finalize_spec(brief, rooms, constraints)


def _llm_parse(
    brief: str, constraints: dict[str, Any], heuristic: dict[str, Any]
) -> dict[str, Any] | None:
    from . import together_image

    if not together_image.planner_enabled():
        return None
    flag = (os.getenv("TOGETHER_NLU") or "1").strip().lower()
    if flag in {"0", "off", "false", "no"}:
        return None
    draft = ", ".join(
        f"{r.get('count', 1)}x {r.get('type')}" for r in (heuristic.get("rooms") or [])
    )
    messages = [
        {"role": "system", "content": _NLU_SYSTEM},
        {
            "role": "user",
            "content": (
                f"BRIEF:\n{brief}\n\nHeuristic draft (correct if the brief disagrees): {draft}\n"
                "Return the JSON program."
            ),
        },
    ]
    try:
        raw = together_image.chat_completion(messages, json_mode=True, temperature=0.1, max_tokens=900)
    except Exception:  # noqa: BLE001
        return None

    data = _parse_json_obj(raw)
    if not data or not isinstance(data.get("rooms"), list):
        return None
    rooms: list[dict[str, Any]] = []
    rid = 1
    for item in data["rooms"]:
        if not isinstance(item, dict):
            continue
        typ = str(item.get("type") or "").strip().lower()
        if typ not in _ALLOWED_TYPES:
            continue
        try:
            area = float(item.get("area_m2") or item.get("area") or 10)
            count = max(1, int(item.get("count") or 1))
        except (TypeError, ValueError):
            continue
        if count > 8 or area <= 0 or area > 200:
            continue
        rooms.append({"id": f"r{rid}", "type": typ, "area_m2": area, "count": count})
        rid += 1
    rooms = _filter_invented_rooms(brief, rooms)
    if not any(r["type"] == "living" for r in rooms) and not any(r["type"] == "kitchen" for r in rooms):
        return None
    if len(rooms) < 2:
        return None
    spec = _finalize_spec(brief, rooms, constraints)
    style = str(data.get("style") or "").strip().lower()
    if style in {"contemporary", "traditional", "minimal", "mediterranean", "other"}:
        spec["style"] = style
    try:
        floors = int(data.get("floors") or spec["floors"])
        if 1 <= floors <= 5:
            spec["floors"] = floors
    except (TypeError, ValueError):
        pass
    return spec


def _filter_invented_rooms(brief: str, rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Garde le noyau + les pièces explicitement demandées. Pas de garage fantôme."""
    text = brief.lower()
    mentioned = {
        "garage": "garage" in text or "carport" in text,
        "office": "bureau" in text or "office" in text,
        "dining": "salle à manger" in text or "salle a manger" in text or "dining" in text,
        "laundry": "buanderie" in text or "laundry" in text,
        "storage": "cellier" in text or "rangement" in text or "débarras" in text or "debarra" in text,
        "wc": "wc" in text or "toilette" in text,
    }
    bedroom_n = sum(int(r.get("count") or 1) for r in rooms if r.get("type") == "bedroom")
    out: list[dict[str, Any]] = []
    for room in rooms:
        typ = str(room.get("type") or "")
        if typ in {"living", "kitchen", "bedroom", "bathroom"}:
            out.append(room)
        elif typ == "hallway" and bedroom_n >= 2:
            out.append(room)
        elif mentioned.get(typ):
            out.append(room)
    return out


def _finalize_spec(brief: str, rooms: list[dict[str, Any]], constraints: dict[str, Any]) -> dict[str, Any]:
    total = float(
        constraints.get("total_area_m2")
        or sum(float(r.get("area_m2") or 10) * int(r.get("count") or 1) for r in rooms) * 1.15
    )
    width = float(
        constraints.get("parcel_width_m")
        or constraints.get("max_width_m")
        or max(10.0, round(total**0.5 * 1.15, 1))
    )
    depth = float(
        constraints.get("parcel_depth_m")
        or constraints.get("max_depth_m")
        or max(8.0, round(total / max(width, 1), 1))
    )
    return {
        "version": "1.0",
        "brief": brief,
        "total_area_m2": total,
        "floors": int(constraints.get("floors", 1)),
        "style": constraints.get("style", "contemporary"),
        "rooms": rooms,
        "constraints": {
            "orthogonal": True,
            "max_width_m": width,
            "max_depth_m": depth,
        },
    }


def _parse_json_obj(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    import json

    s = re.sub(r"<think>.*?</think>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"```[a-zA-Z]*", " ", s).replace("```", " ")
    i, j = s.find("{"), s.rfind("}")
    if i == -1 or j <= i:
        return None
    body = s[i : j + 1]
    for candidate in (body, re.sub(r",\s*([}\]])", r"\1", body)):
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except ValueError:
            continue
    return None


def _bedroom_count(text: str) -> tuple[int, bool]:
    """Nombre de chambres + flag studio. Défaut maison : 2 chambres."""
    if re.search(r"\bstudio\b|\bt1\b|\bf1\b", text):
        return 0, True
    m = re.search(r"(\d+)\s*chambres?", text)
    if m:
        return max(0, int(m.group(1))), False
    m = re.search(r"(\d+)\s*bedrooms?", text)
    if m:
        return max(0, int(m.group(1))), False
    if "chambre" in text or "bedroom" in text:
        return 1, False
    m = re.search(r"\b(?:t|f)(\d)\b", text)
    if m:
        n = int(m.group(1))
        return max(0, n - 1), n <= 1
    m = re.search(r"(\d+)\s*pi[eè]ces?", text)
    if m:
        n = int(m.group(1))
        return max(0, n - 1), n <= 1
    return 2, False
