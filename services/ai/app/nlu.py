from __future__ import annotations

import os
import re
from typing import Any

_MIN_DIM_M = 2.0
_MAX_DIM_M = 200.0  # borne haute anti-DoS : au-delà, le rendu (textures de sol) devient trop lent


def _clamp_dim(value: float) -> float:
    """Borne une dimension bâtiment (m) : évite qu'une valeur de `constraints`
    absurde (ex. `max_width_m: 1e9`) ne fasse boucler très longtemps les
    fonctions de rendu du plan (elles itèrent en unités mètres, pas pixels)."""
    return max(_MIN_DIM_M, min(_MAX_DIM_M, value))


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
    "- Add hallway if there is at least one bedroom (night/day corridor), or a separate WC. "
    "Always add it for 2+ bedrooms.\n"
    "- Add a separate type wc if the brief mentions WC, toilettes, toilet, or w.c. "
    "as its own room — do not fold it into bathroom.\n"
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
    if re.search(r"(deux|2)\s+salles?\s+de\s+bain", text):
        add("bathroom", 5)
    if bedroom_count >= 1:
        add("hallway", 8, adjacent_to=["r1"])
    if "garage" in text:
        add("garage", 18)
    if "bureau" in text or "office" in text:
        add("office", 10)
    if "salle à manger" in text or "salle a manger" in text or "dining" in text:
        add("dining", 14, adjacent_to=["r1"])
    if _mentions_wc(text):
        add("wc", 3.5)
        if not any(r["type"] == "hallway" for r in rooms):
            add("hallway", 6)
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
        "wc": _mentions_wc(text),
    }
    bedroom_n = sum(int(r.get("count") or 1) for r in rooms if r.get("type") == "bedroom")
    has_wc = any(r.get("type") == "wc" for r in rooms) or mentioned.get("wc")
    out: list[dict[str, Any]] = []
    for room in rooms:
        typ = str(room.get("type") or "")
        keep = (
            typ in {"living", "kitchen", "bedroom", "bathroom"}  # noyau du logement
            or (typ == "hallway" and (bedroom_n >= 1 or has_wc))
            or bool(mentioned.get(typ))                          # demandée au brief
        )
        if keep:
            out.append(room)
    return out


def _mentions_wc(text: str) -> bool:
    """WC / toilettes demandés comme pièce séparée (pas seulement « salle de bain »)."""
    return bool(re.search(
        r"\bwc\b|w\.\s*c\.?|toilettes?|toilets?|\btoilet\b|cabinet de toilette",
        (text or "").lower(),
    ))


# Salle d'eau privée seulement si le brief la demande. « ensuite » seul est exclu :
# en français c'est « puis ».
_ENSUITE_RE = re.compile(
    r"suite\s+parentale|\ben-suite\b|\bensuite\s+bath|master\s+bath"
    r"|(salles?\s+de\s+bains?|salles?\s+d'eau|sdb|douches?|toilettes?|wc)\s+"
    r"(privatives?|attenantes?|int[ée]gr[ée]es?|dans\s+(la|sa|chaque|les)\s+chambres?)"
    # « avec SA salle de bain » : sans possessif, « 3 chambres avec toilettes » décrit la maison.
    r"|chambres?(\s+[a-zé]+)?\s+(avec|et)\s+(sa|son|leurs?)\s+(propres?\s+)?(salles?\s+de\s+bains?|salles?\s+d'eau|sdb|douches?|toilettes?|wc)"
)


def _wants_ensuite(text: str) -> bool:
    return bool(_ENSUITE_RE.search((text or "").lower()))


def _mark_ensuite(brief: str, rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Une salle de bain `ensuite` si demandée ; sinon toutes les salles d'eau sont communes.

    La salle de bain commune reste : les autres chambres et les invités en ont besoin.
    """
    if not _wants_ensuite(brief) or not any(r.get("type") == "bedroom" for r in rooms):
        return rooms
    out = [dict(r) for r in rooms]
    baths = [r for r in out if r.get("type") == "bathroom"]
    n_baths = sum(int(r.get("count") or 1) for r in baths)
    if n_baths >= 2:
        last = baths[-1]
        if int(last.get("count") or 1) > 1:
            last["count"] = int(last["count"]) - 1
        else:
            out.remove(last)
        area = float(last.get("area_m2") or 5)
    else:
        area = 5.0
    used = {str(r.get("id")) for r in out}
    rid = next(f"r{i}" for i in range(len(out) + 1, len(out) + 100) if f"r{i}" not in used)
    out.append({"id": rid, "type": "bathroom", "area_m2": area, "count": 1, "ensuite": True})
    return out


def _finalize_spec(brief: str, rooms: list[dict[str, Any]], constraints: dict[str, Any]) -> dict[str, Any]:
    rooms = _mark_ensuite(brief, rooms)
    rooms = _ensure_hallway_in_program(rooms)
    total = float(
        constraints.get("total_area_m2")
        or sum(float(r.get("area_m2") or 10) * int(r.get("count") or 1) for r in rooms) * 1.15
    )
    width = _clamp_dim(float(
        constraints.get("parcel_width_m")
        or constraints.get("max_width_m")
        or max(10.0, round(total**0.5 * 1.15, 1))
    ))
    depth = _clamp_dim(float(
        constraints.get("parcel_depth_m")
        or constraints.get("max_depth_m")
        or max(8.0, round(total / max(width, 1), 1))
    ))
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


def _ensure_hallway_in_program(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Couloir dès qu'il y a des chambres ou un WC séparé (circulation jour/nuit)."""
    types = {str(r.get("type") or "") for r in rooms}
    need = "bedroom" in types or "wc" in types
    if not need or "hallway" in types:
        return rooms
    out = list(rooms)
    out.append({"id": "r_hall", "type": "hallway", "area_m2": 8, "count": 1})
    return out


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
