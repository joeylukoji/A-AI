"""Expansion et libellés du programme de pièces demandé."""

from __future__ import annotations

from typing import Any

_TYPE_FR = {
    "living": "Séjour",
    "kitchen": "Cuisine",
    "dining": "Salle à manger",
    "bedroom": "Chambre",
    "bathroom": "SDB",
    "wc": "WC",
    "hallway": "Couloir",
    "garage": "Garage",
    "office": "Bureau",
    "storage": "Rangement",
    "laundry": "Buanderie",
    "veranda": "Véranda",
}


MAX_ROOM_COUNT = 20
MAX_ROOMS_TOTAL = 60


def expand_rooms(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand bounded room counts while preserving requested areas and stable IDs."""
    out: list[dict[str, Any]] = []
    for idx, r in enumerate(rooms):
        if not isinstance(r, dict):
            continue
        try:
            count = int(r.get("count") or 1)
        except (TypeError, ValueError):
            count = 1
        count = max(1, min(MAX_ROOM_COUNT, count))
        rid = str(r.get("id") or f"r{idx + 1}")
        typ = str(r.get("type") or "other")
        try:
            area = float(r.get("area_m2") or 12)
        except (TypeError, ValueError):
            area = 12.0
        for i in range(count):
            if len(out) >= MAX_ROOMS_TOTAL:
                return out
            out.append(
                {
                    "id": f"{rid}_{i + 1}" if count > 1 else rid,
                    "type": typ,
                    "name": _label(typ, i + 1 if count > 1 else None),
                    "area_m2": area,
                    **({"ensuite": True} if r.get("ensuite") else {}),
                }
            )
    return out


def _label(room_type: str, n: int | None) -> str:
    labels = {
        "living": "Séjour",
        "kitchen": "Cuisine",
        "bedroom": "Chambre",
        "bathroom": "SDB",
        "wc": "WC",
        "garage": "Garage",
        "office": "Bureau",
        "hallway": "Couloir",
        "dining": "Salle à manger",
        "storage": "Rangement",
        "laundry": "Buanderie",
    }
    base = labels.get(room_type, _TYPE_FR.get(room_type, "Pièce"))
    return f"{base} {n}" if n else base
