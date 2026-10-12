from __future__ import annotations

import contextlib
import json
import os
import re
import unicodedata
from typing import Any

from app.floorplan_render import (
    _DOOR as _DOOR,
)
from app.floorplan_render import (
    _FLOOR_BATH as _FLOOR_BATH,
)
from app.floorplan_render import (
    _FLOOR_BATH_LINE as _FLOOR_BATH_LINE,
)
from app.floorplan_render import (
    _FLOOR_HARD as _FLOOR_HARD,
)
from app.floorplan_render import (
    _FLOOR_HONEY as _FLOOR_HONEY,
)
from app.floorplan_render import (
    _FLOOR_HONEY_LINE as _FLOOR_HONEY_LINE,
)
from app.floorplan_render import (
    _FLOOR_TILE as _FLOOR_TILE,
)
from app.floorplan_render import (
    _FLOOR_TILE_LINE as _FLOOR_TILE_LINE,
)
from app.floorplan_render import (
    _FLOOR_WOOD as _FLOOR_WOOD,
)
from app.floorplan_render import (
    _FLOOR_WOOD_LINE as _FLOOR_WOOD_LINE,
)
from app.floorplan_render import (
    _FURN as _FURN,
)
from app.floorplan_render import (
    _FURN_FILL as _FURN_FILL,
)
from app.floorplan_render import (
    _FURN_SOFT as _FURN_SOFT,
)
from app.floorplan_render import (
    _GRASS as _GRASS,
)
from app.floorplan_render import (
    _GRASS_DARK as _GRASS_DARK,
)
from app.floorplan_render import (
    _PAGE_BG as _PAGE_BG,
)
from app.floorplan_render import (
    _PLANT as _PLANT,
)
from app.floorplan_render import (
    _PLANT_IN as _PLANT_IN,
)
from app.floorplan_render import (
    _PORCH as _PORCH,
)
from app.floorplan_render import (
    _PORCH_LINE as _PORCH_LINE,
)
from app.floorplan_render import (
    _ROOM_FILL_SOFT as _ROOM_FILL_SOFT,
)
from app.floorplan_render import (
    _RUG as _RUG,
)
from app.floorplan_render import (
    _SHADOW as _SHADOW,
)
from app.floorplan_render import (
    _SS as _SS,
)
from app.floorplan_render import (
    _TEXT as _TEXT,
)
from app.floorplan_render import (
    _TEXT_SOFT as _TEXT_SOFT,
)
from app.floorplan_render import (
    _WALL as _WALL,
)
from app.floorplan_render import (
    _WALL_DARK as _WALL_DARK,
)
from app.floorplan_render import (
    _WALL_LIGHT as _WALL_LIGHT,
)
from app.floorplan_render import (
    ROOM_FILL as ROOM_FILL,
)
from app.floorplan_render import (
    _draw_catalog_item as _draw_catalog_item,
)
from app.floorplan_render import (
    _draw_room_contents as _draw_room_contents,
)
from app.floorplan_render import (
    _edges_m as _edges_m,
)
from app.floorplan_render import (
    _floor_texture as _floor_texture,
)
from app.floorplan_render import (
    _furniture as _furniture,
)
from app.floorplan_render import (
    _overlay_room_labels as _overlay_room_labels,
)
from app.floorplan_render import (
    _poly as _poly,
)
from app.floorplan_render import (
    _render_floorplan as _render_floorplan,
)
from app.floorplan_render import (
    _room_caption as _room_caption,
)
from app.floorplan_render import (
    _room_font as _room_font,
)
from app.floorplan_render import (
    _rr_local as _rr_local,
)
from app.floorplan_render import (
    _rrect as _rrect,
)
from app.floorplan_render import (
    _stamp as _stamp,
)
from app.floorplan_render import (
    _wood_planks as _wood_planks,
)
from app.floorplan_render import (
    _xf as _xf,
)
from app.job_progress import notify_job_step as _notify_job_step
from app.plan_openings import (
    _DOOR_PAIRS as _DOOR_PAIRS,
)
from app.plan_openings import (
    _ENTRANCE_ORDER as _ENTRANCE_ORDER,
)
from app.plan_openings import (
    _FACADE_DOOR_OK as _FACADE_DOOR_OK,
)
from app.plan_openings import (
    _FORBIDDEN_PAIRS as _FORBIDDEN_PAIRS,
)
from app.plan_openings import (
    _GARAGE_DOOR_WIDTH as _GARAGE_DOOR_WIDTH,
)
from app.plan_openings import (
    _MIN_GARAGE_CONTACT as _MIN_GARAGE_CONTACT,
)
from app.plan_openings import (
    _NEIGHBOUR_RANK as _NEIGHBOUR_RANK,
)
from app.plan_openings import (
    _add_missing_room_doors as _add_missing_room_doors,
)
from app.plan_openings import (
    _allow_internal_door as _allow_internal_door,
)
from app.plan_openings import (
    _best_access_wall as _best_access_wall,
)
from app.plan_openings import (
    _centred_offset as _centred_offset,
)
from app.plan_openings import (
    _entrance_offset as _entrance_offset,
)
from app.plan_openings import (
    _garage_door as _garage_door,
)
from app.plan_openings import (
    _last_resort_wall as _last_resort_wall,
)
from app.plan_openings import (
    _rooms_on_wall as _rooms_on_wall,
)
from app.plan_openings import (
    _served_rooms as _served_rooms,
)
from app.plan_openings import (
    _wall_len as _wall_len,
)
from app.plan_openings import (
    _wall_point as _wall_point,
)
from app.plan_openings import (
    _wall_span_for_room as _wall_span_for_room,
)

# Compatibility exports for existing research scripts and callers.
from app.plan_openings import (
    default_openings as default_openings,
)
from app.plan_walls import (
    _edge_key as _edge_key,
)
from app.plan_walls import (
    _hallway_only_edges as _hallway_only_edges,
)
from app.plan_walls import (
    _is_outer_edge as _is_outer_edge,
)
from app.plan_walls import (
    perimeter_and_internal_walls as perimeter_and_internal_walls,
)
from app.room_program import (
    _TYPE_FR as _TYPE_FR,
)
from app.room_program import (
    MAX_ROOM_COUNT as MAX_ROOM_COUNT,
)
from app.room_program import (
    MAX_ROOMS_TOTAL as MAX_ROOMS_TOTAL,
)
from app.room_program import (
    _label as _label,
)
from app.room_program import (
    expand_rooms as expand_rooms,
)


def _flag_on(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _careful_repair_notes(_spec: dict[str, Any] | None = None) -> list[str]:
    """Consignes d'un redo : le dessin précédent avait trop d'erreurs."""
    return [
        "Previous plan had many errors — count rooms exactly and place furniture with extra care",
        "No toilet, bathtub, shower or washbasin in kitchen or dining — bathroom fixtures only in bathroom/WC",
        "Living room must show a sofa, coffee table and TV facing the sofa, not a dining table",
        "Do not draw two dining rooms",
    ]


def render_plan_document(doc: dict[str, Any]) -> str:
    """Rendu PNG vectoriel du PlanDocument (géométrie exacte, sans FLUX)."""
    bounds = (doc.get("floor") or {}).get("bounds") or {}
    width = float(bounds.get("width") or 12)
    depth = float(bounds.get("depth") or 10)
    return _render_floorplan(
        doc.get("rooms") or [],
        doc.get("walls") or [],
        doc.get("openings") or [],
        width,
        depth,
        furniture=doc.get("furniture") or [],
    )


def render_preview(
    doc: dict[str, Any], spec: dict[str, Any] | None = None
) -> tuple[str, str]:
    """Aperçu = plan vectoriel puis Gemini (Eden) le redessine."""
    spec = spec or {}
    brief = str(spec.get("brief") or "")
    constraints = spec.get("constraints") or {}
    b64, method = generate_flux_plan(
        brief,
        constraints,
        spec=spec,
        layout_rooms=doc.get("rooms") or [],
        walls=doc.get("walls") or [],
        openings=doc.get("openings") or [],
        furniture=doc.get("furniture") or [],
    )
    if b64:
        return b64, method
    return render_plan_document(doc), method or "procedural"


def gemini_only() -> bool:
    """`GEMINI_ONLY=1` : aucun aperçu vectoriel local quand Gemini échoue."""
    return (os.getenv("GEMINI_ONLY") or "").strip().lower() in {"1", "true", "yes", "on"}


def preview_from_document(
    brief: str,
    constraints: dict[str, Any] | None,
    *,
    spec: dict[str, Any],
    doc: dict[str, Any],
    job_id: str | None = None,
) -> tuple[str, str]:
    """Gemini redessine la géométrie adaptée ; repli vectoriel si l'API manque."""
    from app.generation_trace import preview_result

    bounds = (doc.get("floor") or {}).get("bounds") or {}
    flux_constraints = dict(constraints or {})
    if bounds.get("width"):
        flux_constraints["parcel_width_m"] = float(bounds["width"])
    if bounds.get("depth"):
        flux_constraints["parcel_depth_m"] = float(bounds["depth"])
    preview_b64, preview_method = generate_flux_plan(
        brief,
        flux_constraints,
        spec=spec,
        job_id=job_id,
        layout_rooms=doc.get("rooms") or [],
        walls=doc.get("walls") or [],
        openings=doc.get("openings") or [],
        furniture=doc.get("furniture") or [],
    )
    if not preview_b64:
        reason = "provider_failed" if preview_method == "flux-failed" else "disabled_or_unconfigured"
        if gemini_only():
            # Pas de dessin local de secours : l'utilisateur ne voit que Gemini.
            preview_result("none", fallback_reason=reason)
            return "", preview_method or "gemini-unavailable"
        preview_b64 = render_plan_document(doc)
        preview_method = preview_method or "procedural"
        preview_result(
            "local",
            fallback_reason="provider_failed"
            if preview_method == "flux-failed"
            else "disabled_or_unconfigured",
        )
    else:
        preview_result("gemini")
    return preview_b64, preview_method


def generate_flux_plan(
    brief: str,
    constraints: dict[str, Any] | None = None,
    spec: dict[str, Any] | None = None,
    job_id: str | None = None,
    layout_rooms: list[dict[str, Any]] | None = None,
    walls: list[dict[str, Any]] | None = None,
    openings: list[dict[str, Any]] | None = None,
    furniture: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Dessin local (pièces + meubles au bon endroit) puis un seul appel Gemini."""
    from . import together_image

    constraints = constraints or {}
    spec = dict(spec or {})
    if brief and not spec.get("brief"):
        spec["brief"] = brief
    width = float(
        constraints.get("parcel_width_m") or constraints.get("max_width_m") or 12
    )
    depth = float(
        constraints.get("parcel_depth_m") or constraints.get("max_depth_m") or 10
    )
    if not _flux_wanted():
        return "", "flux-skipped"
    rooms = _usable_layout_rooms(layout_rooms, spec, width, depth)
    width, depth = _emprise_from_rooms(rooms, width, depth)
    guide = _layout_guide_b64(
        rooms, width, depth, walls=walls, openings=openings, furniture=furniture
    )
    layout_guided = bool(guide)
    ref = guide or together_image.style_reference_b64()
    furniture_plan = _plan_furniture_with_llm(brief, spec)
    careful = _flag_on(constraints.get("careful")) or _flag_on(spec.get("careful"))
    notes = list(_careful_repair_notes(spec) if careful else [])
    _notify_job_step(job_id, "gemini")
    b64 = together_image.generate_floorplan_image(
        _flux_prompt(
            brief=brief,
            spec=spec,
            rooms=rooms,
            width=width,
            depth=depth,
            furniture_plan=furniture_plan,
            repair_notes=notes,
            careful=careful,
            layout_guided=layout_guided,
            walls=walls,
            openings=openings,
        ),
        width,
        depth,
        reference_png_b64=ref,
    )
    if b64:
        return b64, together_image.method_name()
    return "", "flux-failed"


def edit_plan(
    instruction: str,
    brief: str = "",
    constraints: dict[str, Any] | None = None,
    spec: dict[str, Any] | None = None,
    plan_document: dict[str, Any] | None = None,
    image_png_b64: str = "",
    job_id: str | None = None,
) -> dict[str, Any]:
    from app import edit_service
    from app.document_validation import validate_document

    return edit_service.edit_plan(
        instruction,
        brief=brief,
        constraints=constraints,
        spec=spec,
        plan_document=plan_document,
        image_png_b64=image_png_b64,
        job_id=job_id,
        interpret=_interpret_edit,
        rebuild=_adapted_from_spec,
        render_document=render_plan_document,
        notify_step=_notify_job_step,
        validate_document=validate_document,
    )


def _adapted_from_spec(
    spec: dict[str, Any], constraints: dict[str, Any]
) -> dict[str, Any]:
    # Reuse the existing generation builder; edits do not fork a second pipeline.
    from app.pipeline import build_document

    build_constraints = dict(constraints)
    preferred_layout = build_constraints.pop("_aai_source_layout", None)
    return build_document(spec, build_constraints, preferred_layout=preferred_layout)


def _edit_flux_image(
    *,
    brief: str,
    spec: dict[str, Any],
    constraints: dict[str, Any],
    edit_en: str,
    source_png_b64: str,
    job_id: str | None,
) -> tuple[str, str]:
    from . import together_image

    if not _flux_wanted():
        return "", "flux-skipped"
    width = float(
        constraints.get("parcel_width_m") or constraints.get("max_width_m") or 12
    )
    depth = float(
        constraints.get("parcel_depth_m") or constraints.get("max_depth_m") or 10
    )
    src = (
        together_image._png_b64_to_jpeg_uri(source_png_b64, max_side=1024)
        if source_png_b64
        else None
    )
    ref = src or together_image.style_reference_b64()
    _notify_job_step(job_id, "gemini")
    prompt = (
        _flux_edit_prompt(brief=brief, spec=spec, edit_en=edit_en)
        if src
        else _flux_prompt(
            brief=brief, spec=spec, repair_notes=[edit_en], layout_guided=False
        )
    )
    b64 = together_image.generate_floorplan_image(
        prompt, width, depth, reference_png_b64=ref
    )
    if b64:
        return b64, together_image.method_name() + "+edit"
    return "", "flux-failed"


_EDIT_SYSTEM = (
    "Convert the request into a structured floor-plan edit. Return STRICT JSON only with "
    '{"edit_en":"...","reply_fr":"...","rooms":null,"command":null,"clarify":false}. '
    "When adding or removing a room, return the FULL new rooms program in rooms and command=null. "
    "For furniture, openings, or moving one room, return a v1 command and rooms=null. "
    "Use only IDs present in PLAN DOCUMENT. Never invent an object or wall ID. "
    "If target, direction, or measurements cannot be determined safely, set clarify=true, "
    "command=null, rooms=null, and ask one concise question in reply_fr. "
    "Commands: move_furniture(target_id, position{x,y}); add_furniture(target_room_id, "
    "catalog_id, position{x,y}, optional rotation_deg); remove_furniture(target_id); "
    "move_opening(target_id, offset_m); add_opening(target_id=wall ID, opening_type=door|window, "
    "offset_m, width_m); remove_opening(target_id); move_room(target_id, position{dx,dy}); "
    "remove_room(target_id). Room add/remove uses the rooms program, never a fabricated polygon. "
    "Allowed room types: living, kitchen, dining, bedroom, bathroom, wc, hallway, garage, "
    "office, storage, laundry, veranda. reply_fr is a short French sentence."
)


def _interpret_edit(
    instruction: str,
    spec: dict[str, Any] | None,
    plan_document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Translate a user request to a room program or a target-ID command."""
    from . import together_image

    fallback = {
        "edit_en": instruction or "keep the same floor plan",
        "reply_fr": "Je mets à jour le plan.",
        "rooms": None,
        "command": None,
        "clarify": False,
    }
    heur = _heuristic_room_edit(instruction, spec) if instruction else None
    if not instruction:
        return fallback
    if not together_image.planner_enabled():
        return {**fallback, **(heur or {})}

    program = (
        ", ".join(f"{n}x {t}" for t, n in _program_counts(spec).items()) or "unknown"
    )
    try:
        raw = together_image.chat_completion(
            [
                {"role": "system", "content": _EDIT_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"CURRENT ROOM PROGRAM: {program}\n"
                        "PLAN DOCUMENT OBJECTS (IDs and geometry):\n"
                        + json.dumps(
                            {
                                key: (plan_document or {}).get(key, [])
                                for key in ("rooms", "walls", "openings", "furniture")
                            },
                            ensure_ascii=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                        f"USER REQUEST:\n{instruction}\n"
                        "Return the JSON."
                    ),
                },
            ],
            json_mode=True,
            temperature=0.15,
            max_tokens=700,
        )
    except Exception:  # noqa: BLE001
        return {**fallback, **(heur or {})}
    data = _parse_json_obj(raw)
    if not isinstance(data, dict):
        return {**fallback, **(heur or {})}
    edit_en = (
        str(data.get("edit_en") or data.get("edit") or instruction).strip()
        or instruction
    )
    reply_fr = str(
        data.get("reply_fr") or data.get("reply") or fallback["reply_fr"]
    ).strip()
    command = data.get("command")
    clarify = data.get("clarify") is True
    rooms = _sanitize_rooms_program(data.get("rooms"))
    if rooms and _program_counts({"rooms": rooms}) == _program_counts(spec):
        rooms = None
    if heur and heur.get("clarify"):
        return {
            "edit_en": heur.get("edit_en") or edit_en,
            "reply_fr": heur.get("reply_fr") or reply_fr,
            "rooms": None,
            "command": None,
            "clarify": True,
        }
    if heur and heur.get("rooms") and not clarify:
        rooms = heur["rooms"]
        edit_en = heur.get("edit_en") or edit_en
        reply_fr = heur.get("reply_fr") or reply_fr
    if clarify:
        command = None
        rooms = None
    return {
        "edit_en": edit_en,
        "reply_fr": reply_fr or fallback["reply_fr"],
        "rooms": rooms,
        "command": command if isinstance(command, dict) else None,
        "clarify": clarify,
    }


_ROOM_QTY = {"UNE": 1, "UN": 1, "DEUX": 2, "TROIS": 3, "QUATRE": 4}
_REMOVE_VERBS = (
    r"(?:RETIR(?:E|ER)|ENLEV(?:E|ER)|ENLEVE|SUPPRIM(?:E|ER)|OTE(?:R)?|VIRE(?:R)?"
    r"|REMOVE|DELETE|DROP)"
)
_ADD_VERBS = r"(?:AJOUT(?:E|ER)|RAJOUT(?:E|ER)|ADD)"


def _room_name_alt() -> str:
    names = [n for n in _NAME_TO_TYPE if len(n) >= 2]
    names.sort(key=len, reverse=True)
    names.extend(["PIECES", "PIECE"])
    return "|".join(re.escape(n) for n in names)


def _qty_from_token(token: str, *, remove_all: bool, current: int) -> int:
    up = (token or "").strip().upper()
    if remove_all:
        return max(1, current)
    if up.isdigit():
        return max(1, int(up))
    return _ROOM_QTY.get(up, 1)


def _rooms_from_counts(
    counts: dict[str, int], spec: dict[str, Any] | None
) -> list[dict[str, Any]]:
    prev: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for r in (spec or {}).get("rooms") or []:
        typ = str(r.get("type") or "")
        if typ not in _FURN_ROOM_EN:
            continue
        if typ not in prev:
            prev[typ] = r
            order.append(typ)
    for typ in counts:
        if typ not in order:
            order.append(typ)
    out: list[dict[str, Any]] = []
    for typ in order:
        n = int(counts.get(typ) or 0)
        if n < 1:
            continue
        item: dict[str, Any] = {"type": typ, "count": n}
        old = prev.get(typ) or {}
        if old.get("id"):
            item["id"] = old["id"]
        if old.get("area_m2"):
            with contextlib.suppress(TypeError, ValueError):
                item["area_m2"] = float(old["area_m2"])
        out.append(item)
    return out


def _heuristic_room_edit(
    instruction: str, spec: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Détecte ajout/retrait de pièce sans dépendre du LLM (FR/EN)."""
    up = _ascii_upper(instruction)
    if not up:
        return None
    alts = _room_name_alt()
    det = (
        r"(?:MOI\s+)?(?:TOUTES?\s+LES|TOUS\s+LES|CETTE|CET|CE|LA|LE|LES|L['’])?\s*"
        r"(?P<n>UNE|UN|DEUX|TROIS|QUATRE|\d+)?\s*"
    )
    remove_m = re.search(rf"\b{_REMOVE_VERBS}\s+{det}(?P<room>{alts})\b", up)
    add_m = (
        None
        if remove_m
        else re.search(rf"\b{_ADD_VERBS}\s+{det}(?P<room>{alts})\b", up)
    )
    hit = remove_m or add_m
    if not hit:
        return None
    raw_room = hit.group("room")
    if raw_room in {"PIECE", "PIECES"}:
        return {
            "edit_en": "ask which room to change",
            "reply_fr": (
                "Quelle pièce faut-il modifier ? Nommez-la : salon, cuisine, "
                "chambre, salle de bain, garage…"
            ),
            "rooms": None,
            "clarify": True,
        }
    typ = _NAME_TO_TYPE.get(raw_room)
    if not typ:
        return None
    counts = dict(_program_counts(spec))
    current = counts.get(typ, 0)
    remove_all = bool(re.search(r"\bTOUTES?\s+LES\b|\bTOUS\s+LES\b", up))
    qty = _qty_from_token(hit.group("n") or "", remove_all=remove_all, current=current)
    label = _TYPE_FR.get(typ, typ)
    if remove_m:
        if current < 1:
            return {
                "edit_en": f"there is no {typ} to remove",
                "reply_fr": (
                    f"Je ne trouve pas de {label.lower()} sur ce plan. "
                    "Quelle pièce voulez-vous retirer ?"
                ),
                "rooms": None,
                "clarify": True,
            }
        new_n = 0 if remove_all else max(0, current - qty)
        if new_n == current:
            return None
        if new_n:
            counts[typ] = new_n
        else:
            counts.pop(typ, None)
        if sum(counts.values()) < 2:
            return {
                "edit_en": "cannot remove the last rooms",
                "reply_fr": "Il faut garder au moins deux pièces. Laquelle retirer autrement ?",
                "rooms": None,
                "clarify": True,
            }
        rooms = _rooms_from_counts(counts, spec)
        en_name = _FURN_ROOM_EN.get(typ, typ)
        return {
            "edit_en": (
                f"Remove the {en_name} completely. Do not draw that room or its furniture. "
                "Close the remaining walls and redistribute the space."
            ),
            "reply_fr": f"Je retire {label.lower()} et je redessine le plan.",
            "rooms": rooms,
            "clarify": False,
        }
    counts[typ] = current + qty
    rooms = _rooms_from_counts(counts, spec)
    en_name = _FURN_ROOM_EN.get(typ, typ)
    return {
        "edit_en": (
            f"Add {qty} extra enclosed {en_name}. Draw it as its own room with matching furniture."
        ),
        "reply_fr": f"J’ajoute {label.lower()} et je redessine le plan.",
        "rooms": rooms,
        "clarify": False,
    }


def _sanitize_rooms_program(rooms: Any) -> list[dict[str, Any]] | None:
    if not isinstance(rooms, list) or len(rooms) < 2:
        return None
    out: list[dict[str, Any]] = []
    for r in rooms:
        if not isinstance(r, dict):
            continue
        typ = str(r.get("type") or "").strip().lower()
        if typ not in _FURN_ROOM_EN:
            continue
        try:
            n = max(1, int(r.get("count") or 1))
        except (TypeError, ValueError):
            n = 1
        item = {"type": typ, "count": n}
        if r.get("area_m2"):
            with contextlib.suppress(TypeError, ValueError):
                item["area_m2"] = float(r["area_m2"])
        out.append(item)
    return out if len(out) >= 2 else None


def _flux_wanted() -> bool:
    from . import together_image

    if not together_image.available():
        return False
    renderer = (os.getenv("IMAGE_RENDERER") or "gemini").strip().lower()
    return renderer in {
        "flux",
        "flux2",
        "flux2-dev",
        "flux2-max",
        "image",
        "gemini",
        "eden",
        "edenai",
    }


def _flux_or_vector(
    vector_b64: str,
    rooms: list[dict[str, Any]],
    width: float,
    depth: float,
    spec: dict[str, Any],
    *,
    planned: bool,
) -> tuple[str, str]:
    """Gemini redessine le plan vectoriel ; repli local si l'API manque."""
    b64, method = generate_flux_plan(
        str(spec.get("brief") or ""),
        spec.get("constraints") or {},
        spec=spec,
        layout_rooms=rooms,
    )
    if b64:
        return b64, method + ("+plan" if planned else "")
    return vector_b64, method or ("together-layout" if planned else "procedural")


def generate(spec: dict[str, Any], *, image: bool = True) -> dict[str, Any]:
    """Disposition des pièces (LLM ou packer), puis image Gemini si `image`.

    `image=False` : layout seul (le pipeline appelle `render_preview` après adapt,
    pour ne facturer Gemini qu'une fois, sur la géométrie finale).
    """
    from . import together_image

    constraints = spec.get("constraints") or {}
    # Bornée : le rendu vectoriel (textures de sol, mobilier) itère en mètres,
    # une largeur/profondeur absurde venue d'un payload direct sur /v1/generate
    # ferait tourner ces boucles très longtemps (DoS). Mêmes bornes que
    # `nlu._clamp_dim`.
    # `or 12` (et non un défaut de `.get`) : un `{"max_width_m": null}` explicite
    # dans le JSON passait `None` à `float()` → TypeError → 500.
    width = max(2.0, min(200.0, float(constraints.get("max_width_m") or 12)))
    depth = max(2.0, min(200.0, float(constraints.get("max_depth_m") or 10)))
    program = _apply_canonical_names(expand_rooms(spec.get("rooms") or []))

    layout_rooms, veranda_depth, planned = None, 0.0, False
    if together_image.planner_enabled():
        layout_rooms, veranda_depth = _llm_layout(spec, program, width, depth)
        planned = layout_rooms is not None
    if layout_rooms is None:
        layout_rooms = pack_rooms(program, width, depth)
    layout_rooms = _apply_canonical_names(layout_rooms)
    walls = perimeter_and_internal_walls(layout_rooms, width, depth)
    openings = default_openings(walls, width, depth, layout_rooms)

    method = "together-layout" if planned else "procedural"
    b64 = ""
    if image:
        b64, method = _flux_or_vector(
            "", layout_rooms, width, depth, spec, planned=planned
        )
        if not b64:
            b64 = _render_floorplan(
                layout_rooms, walls, openings, width, depth, veranda_depth
            )
            if method in {"", "flux-skipped", "flux-failed"}:
                method = "procedural"

    return {
        "image_png_b64": b64,
        "preview_key": "",
        "method": method,
        "layout": {
            "width": width,
            "depth": depth,
            "height_m": 2.7,
            "rooms": layout_rooms,
            "walls": walls,
            "openings": openings,
        },
    }


def _number_duplicate_names(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Noms canoniques + numérotation (Chambre 1 / Chambre 2). Alias conservé pour les tests."""
    return _apply_canonical_names(rooms)


def _apply_canonical_names(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Libellés uniquement depuis le type : jamais le texte libre du modèle."""
    totals: dict[str, int] = {}
    for r in rooms:
        typ = str(r.get("type") or "other")
        totals[typ] = totals.get(typ, 0) + 1
    seen: dict[str, int] = {}
    for r in rooms:
        typ = str(r.get("type") or "other")
        seen[typ] = seen.get(typ, 0) + 1
        n = seen[typ] if totals.get(typ, 0) > 1 else None
        r["name"] = _label(typ, n)
        r["type"] = typ if typ in _TYPE_FR else (r.get("type") or "other")
    return rooms


_FLUX_STYLE_BODIES = {
    "cad": (
        "A precise black and white architectural CAD floor plan of a single storey house, "
        "drawn in strict top-down orthographic plan view, seen straight from above, flat. Exterior and "
        "load-bearing walls are solid thick black poché, interior partitions are thinner; each "
        "door is a gap in the wall with a quarter-circle swing arc; each window is a thin double "
        "line set into the wall. Exterior dimension lines with measurements and a graphic scale bar. "
        "Pure white background, crisp uniform line weights, perfectly orthogonal geometry on a grid, "
        "drafting-software export look, highly legible."
    ),
    "render3d": (
        "A 3D cutaway dollhouse view of a single storey house with the roof removed, seen from a "
        "high three-quarter angle. Fully furnished rooms with realistic materials and textures, "
        "warm interior lighting, soft global illumination and gentle contact shadows. Clean "
        "architectural visualisation style, neutral studio background, crisp edges, high detail."
    ),
    "illustration": (
        "A simple Sweet Home 3D style 2D floor plan of a single storey house, "
        "drawn as if a person placed furniture in interior-design software, "
        "camera perfectly vertical, looking straight down, flat 2D icons not photoreal. "
        "Thick medium-gray walls with white window recesses, brown door swing arcs. "
        "Simple wood-plank lines in bedrooms and living room, a light tile grid in the "
        "kitchen, pale gray tiles in bathrooms, flat light-gray in the garage. "
        "Simple top-down furniture symbols: beds, an L-shaped sofa, low coffee table, "
        "two armchairs, kitchen counter with a small square sink and hob, "
        "bathtub toilet and sink, a car in the garage. Flat green garden south and east, "
        "small wooden porch at the south entrance. Limited detail, lots of empty floor."
    ),
}


def _label_mode() -> str:
    """TOGETHER_IMAGE_LABELS : "model" | "none". Le chemin produit overlay toujours nos libellés."""
    m = (os.getenv("TOGETHER_IMAGE_LABELS") or "none").strip().lower()
    return m if m in {"model", "none"} else "none"


def _ascii_upper(text: str) -> str:
    """ "Séjour" -> "SEJOUR" : FLUX lettre bien l'ASCII court, mal les accents français."""
    norm = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in norm if not unicodedata.combining(c)).upper().strip()


def _footprint_zone(poly: list[dict[str, Any]], width: float, depth: float) -> str:
    """Situe le centroïde d'une pièce dans l'emprise (front = côté entrée, y=0)."""
    if not poly or width <= 0 or depth <= 0:
        return ""
    cx = sum(float(p["x"]) for p in poly) / len(poly)
    cy = sum(float(p["y"]) for p in poly) / len(poly)
    horiz = (
        "left" if cx / width < 0.34 else ("right" if cx / width > 0.66 else "centre")
    )
    vert = "front" if cy / depth < 0.34 else ("back" if cy / depth > 0.66 else "middle")
    if horiz == "centre" and vert == "middle":
        return "centre"
    if horiz == "centre":
        return vert
    if vert == "middle":
        return horiz
    return f"{vert}-{horiz}"


def _style_body() -> str:
    key = (os.getenv("TOGETHER_IMAGE_STYLE") or "illustration").strip().lower()
    return _FLUX_STYLE_BODIES.get(key, _FLUX_STYLE_BODIES["illustration"])


def _room_labels(rooms: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for r in rooms:
        name = _ascii_upper(str(r.get("name") or r.get("type") or "")) or "ROOM"
        if name not in labels:
            labels.append(name)
    return labels


def _label_clause(labels: list[str]) -> str:
    if _label_mode() != "model":
        return (
            " Keep every room empty with no lettering, numbers or labels of any kind."
        )
    names = ", ".join(labels) if labels else "SEJOUR, CUISINE, CHAMBRE, SDB"
    return (
        " Inside each room write ONLY that room's name, once, in short UPPERCASE sans-serif "
        "capitals, plain unaccented ASCII letters, spelled exactly. No area figures, no numbers, "
        f"no dimensions, no legend, no other words anywhere. The room names, one per room: {names}."
    )


_FURN_ROOM_EN = {
    "living": "living room",
    "kitchen": "kitchen",
    "dining": "dining room",
    "bedroom": "bedroom",
    "bathroom": "bathroom",
    "wc": "WC",
    "hallway": "hallway",
    "garage": "garage",
    "office": "office",
    "storage": "storage",
    "laundry": "laundry",
    "veranda": "porch",
}
_BATH_FIXTURES = (
    "toilet",
    "toilets",
    "wc",
    "loo",
    "bidet",
    "bathtub",
    "bath tub",
    "tub",
    "shower",
    "shower tray",
    "washbasin",
    "wash basin",
    "bathroom sink",
    "lavatory",
)
_FURN_FORBIDDEN = {
    "living": (
        "bed",
        "bathtub",
        "bath tub",
        "tub",
        "shower",
        "toilet",
        "bidet",
        "washbasin",
        "wash basin",
        "stove",
        "hob",
        "cooktop",
        "fridge",
        "car",
        "sink",
        "dining table",
        "dining",
    ),
    "kitchen": (
        "bed",
        "sofa",
        "armchair",
        "bathtub",
        "bath tub",
        "tub",
        "shower",
        "toilet",
        "bidet",
        "car",
        "wardrobe",
        "dining table",
        "dining",
        "cuve",
    ),
    "bedroom": (
        "stove",
        "hob",
        "cooktop",
        "fridge",
        "sofa",
        "armchair",
        "dining table",
        "car",
        "sink",
        *_BATH_FIXTURES,
    ),
    "bathroom": ("bed", "sofa", "fridge", "stove", "hob", "car", "dining", "wardrobe"),
    "garage": ("bed", "sofa", "bathtub", "toilet", "shower", "stove", "wardrobe"),
    "hallway": ("bed", "bathtub", "toilet", "shower", "car", "stove", "fridge"),
    "dining": (
        "bed",
        "bathtub",
        "bath tub",
        "tub",
        "shower",
        "toilet",
        "bidet",
        "washbasin",
        "car",
        "stove",
        "fridge",
    ),
    "office": ("bed", "bathtub", "toilet", "shower", "car", "stove", "fridge", "sink"),
    "wc": ("bed", "sofa", "car", "stove", "fridge", "wardrobe"),
    "laundry": ("bed", "sofa", "car", "toilet", "bathtub"),
    "storage": ("bed", "sofa", "car", "toilet", "bathtub"),
    "veranda": ("bed", "toilet", "bathtub", "shower", "fridge", "car"),
}

_FURNITURE_SYSTEM = (
    "You are an interior designer placing furniture on a 2D Sweet Home 3D floor plan. "
    "Return STRICT JSON only, no markdown: "
    '{"rooms":[{"type":"living","items":["L-shaped sofa against a wall facing the TV"]}]} '
    "type must be one of: living, kitchen, dining, bedroom, bathroom, wc, hallway, garage, "
    "office, storage, laundry, veranda. "
    "Each items entry is a short English placement (object + where it sits). "
    "Rules: only objects that belong in that room; few objects; leave walking space at doors; "
    "do not block windows with tall pieces. Check every room for coherence. "
    "Living: one sofa against a wall, low coffee table in front, TV on the opposite wall, "
    "two armchairs. NO dining table, NO dining chairs, NO bed, NO kitchen appliances, NO bathroom fixtures. "
    "Kitchen: L or U counters on the walls with a small square sink and hob, fridge at the end of the run. "
    "NO dining table, NO chairs around a table, NO sofa, NO bed, NO toilet, NO bathtub, NO tub. "
    "Bedroom: exactly one bed (never two twin beds), headboard against a wall, nightstands, wardrobe. "
    "NO toilet, NO bathtub, NO shower, NO washbasin, NO sink, NO bidet, NO kitchen appliances. "
    "Bathroom: tub or shower, toilet, washbasin — only here. Garage: one car aligned with the door. "
    "Use exactly the room types listed in the program, one entry per room (repeat type for "
    "each extra bedroom/bathroom)."
)


def _norm_item_text(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", (text or "").lower()) + " "


def _item_forbidden(room_type: str, text: str) -> bool:
    blob = _norm_item_text(text)
    for word in _FURN_FORBIDDEN.get(room_type, ()):
        if f" {word} " in blob:
            return True
    if room_type not in {"bathroom", "wc"}:
        for word in _BATH_FIXTURES:
            if f" {word} " in blob:
                return True
    return False


def _coherence_clause(spec: dict[str, Any] | None = None) -> str:
    """Règles d'objets pièce par pièce, injectées dans le prompt FLUX."""
    types = set(_program_types(spec)) or {
        "living",
        "kitchen",
        "bedroom",
        "bathroom",
        "hallway",
        "garage",
    }
    parts = [
        "ROOM COHERENCE (mandatory, inspect every room): "
        "each object belongs to exactly one room type — never copy a bathroom set into a bedroom. "
        "Bathroom fixtures (toilet, bathtub, tub, shower, washbasin, bidet) ONLY in bathroom/WC — "
        "never in kitchen, dining or living. "
    ]
    if "bedroom" in types:
        parts.append(
            "Bedrooms: exactly one bed per room, nightstands and a wardrobe. "
            "Never two beds in the same bedroom. "
            "NO toilet, NO bathtub, NO shower, NO washbasin, NO sink. "
        )
    if "bathroom" in types or "wc" in types:
        parts.append(
            "Bathroom: tub or shower, a clearly visible toilet and a washbasin. "
            "WC (separate toilet room): a clearly visible toilet and a small basin — no bathtub. "
            "NO bed, NO sofa, NO kitchen appliances. "
        )
    if "living" in types:
        parts.append(
            "Living (salon/séjour): sofa, two armchairs, a low coffee table and a TV opposite the sofa. "
            "This is NOT a dining room. NO dining table, NO dining chairs, NO bed, NO bathroom fixtures. "
        )
    if "kitchen" in types:
        parts.append(
            "Kitchen: wall counters, a small square sink on the counter, hob, fridge. "
            "NO dining table, NO chairs, NO sofa, NO bed, NO toilet, NO bathtub, NO tub, NO large basin. "
        )
    if "dining" in types:
        parts.append(
            "Dining: exactly one dining room — one table with chairs. "
            "NO bathroom fixtures. Do not draw a second dining room. "
        )
    else:
        parts.append(
            "No separate dining room. Do not invent a dining room in the living room or kitchen. "
        )
    if "garage" in types:
        parts.append("Garage: one car. NO bed, NO bathroom fixtures. ")
    return "".join(parts)


def _program_types(spec: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    for r in (spec or {}).get("rooms") or []:
        typ = str(r.get("type") or "")
        if typ not in _FURN_ROOM_EN:
            continue
        try:
            n = max(1, int(r.get("count") or 1))
        except (TypeError, ValueError):
            n = 1
        out.extend([typ] * n)
    return out


def _program_counts(spec: dict[str, Any] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for typ in _program_types(spec):
        counts[typ] = counts.get(typ, 0) + 1
    return counts


def _plan_counts(rooms: list[dict[str, Any]] | None) -> dict[str, int]:
    """Pièces du plan FINAL par type. Le couloir compte pour un : `plan_adapt` le découpe en
    segments (« Couloir 1 » … « Couloir 5 ») qui forment un seul couloir continu."""
    counts: dict[str, int] = {}
    for room in rooms or []:
        if not isinstance(room, dict) or len(room.get("polygon") or []) < 3:
            continue
        typ = str(room.get("type") or "room")
        counts[typ] = 1 if typ == "hallway" else counts.get(typ, 0) + 1
    return counts


def _required_rooms_clause(
    spec: dict[str, Any] | None = None, rooms: list[dict[str, Any]] | None = None
) -> str:
    """Liste obligatoire des pièces + murs fermés, pour le prompt FLUX.

    Le décompte vient du plan final quand on l'a : celui du programme initial ne dit plus la même
    chose après adaptation, et un prompt qui annonce « 1 couloir » puis en positionne cinq
    déroute le modèle.
    """
    counts = _plan_counts(rooms) or _program_counts(spec)
    if not counts:
        return "Draw a complete house: every room enclosed by grey walls, continuous outer walls. "
    listed = ", ".join(
        f"{n}x {_FURN_ROOM_EN.get(typ, typ)}" for typ, n in counts.items()
    )
    total = sum(counts.values())
    return (
        f"REQUIRED ROOMS (draw every one, exact counts, each as its own enclosed space): {listed}. "
        f"That is exactly {total} enclosed spaces in total: count them before you finish, none may be missing. "
        "Do not omit a room. Do not add extra rooms. Do not draw two dining rooms. "
        "Do not merge two bedrooms into one. "
        "WALLS: continuous thick grey outer wall around the whole house, and grey walls between "
        "every adjacent rooms. No missing wall, no room open to the garden except a door or window. "
    )


def _usable_layout_rooms(
    rooms: list[dict[str, Any]] | None,
    spec: dict[str, Any],
    width: float,
    depth: float,
) -> list[dict[str, Any]]:
    """Pièces avec polygone, ou pavage déterministe depuis le programme."""
    usable = [
        r
        for r in (rooms or [])
        if isinstance(r, dict) and len(r.get("polygon") or []) >= 3
    ]
    if usable:
        return _apply_canonical_names(usable)
    program = _apply_canonical_names(expand_rooms((spec or {}).get("rooms") or []))
    if not program:
        return []
    return pack_rooms(program, width, depth)


def _emprise_from_rooms(
    rooms: list[dict[str, Any]], width: float, depth: float
) -> tuple[float, float]:
    """Étend largeur/profondeur si les polygones dépassent les contraintes."""
    xs: list[float] = []
    ys: list[float] = []
    for room in rooms:
        for p in room.get("polygon") or []:
            if not isinstance(p, dict):
                continue
            try:
                xs.append(float(p.get("x") or 0))
                ys.append(float(p.get("y") or 0))
            except (TypeError, ValueError):
                continue
    if xs and ys:
        width = max(width, max(xs))
        depth = max(depth, max(ys))
    return width, depth


def _sanitary_layout_clause() -> str:
    """Règles de distribution, toujours dans le prompt FLUX."""
    return (
        "LAYOUT RULES (mandatory): a hallway separates night and day zones; "
        "bedrooms must not share a wall with the living room; "
        "WC and bathroom must not share a wall with kitchen or dining; "
        "each bedroom and the WC open onto the hallway, never onto the kitchen. "
    )


def _shape_clause() -> str:
    """La disposition est juste mais Gemini déforme les pièces : on fixe la forme."""
    return (
        "SHAPES (mandatory): every room is an exact rectangle with straight, axis-aligned walls, "
        "the same size and proportions as in image 1. Do not round, bend, stretch or shrink rooms; "
        "do not add, remove or move any wall or door. "
        "A WC or bathroom has exactly ONE door, never a second one. "
        "WC: a small narrow room; the toilet stands against the wall opposite the door, facing it, "
        "with a small washbasin; the door swing never touches the toilet. "
        "Bathroom: bathtub or shower along one full wall, toilet and washbasin on the other walls, "
        "all clear of the door swing. Toilets are drawn top-down: an oval bowl with a rectangular "
        "tank against the wall. "
    )


def _wet_room_doors_clause(
    rooms: list[dict[str, Any]] | None,
    walls: list[dict[str, Any]] | None,
    openings: list[dict[str, Any]] | None,
) -> str:
    """Porte unique de chaque salle d'eau : côté du mur et pièce desservie."""
    from app.plan_openings import _room_bbox, _served_rooms

    by_id = {str(w.get("id")): w for w in walls or []}
    lines: list[str] = []
    for room in rooms or []:
        typ = str(room.get("type") or "")
        box = _room_bbox(room)
        if typ not in {"wc", "bathroom"} or not box:
            continue
        x0, y0, x1, y1 = box
        for op in openings or []:
            wall = by_id.get(str(op.get("wall_id")))
            if op.get("type") != "door" or wall is None:
                continue
            served = _served_rooms(wall, op, rooms or [])
            if not any(r is room for r in served):
                continue
            ax, ay = float(wall["a"]["x"]), float(wall["a"]["y"])
            bx = float(wall["b"]["x"])
            if abs(ax - bx) <= 0.15:
                side = "west" if abs(ax - x0) <= abs(ax - x1) else "east"
            else:
                side = "north" if abs(ay - y0) <= abs(ay - y1) else "south"
            other = next((r for r in served if r is not room), None)
            onto = _FURN_ROOM_EN.get(str(other.get("type")), "the outside") if other else "the outside"
            name = _FURN_ROOM_EN.get(typ, typ)
            lines.append(
                f"the {name} at x={x0:.1f}-{x1:.1f}m, y={y0:.1f}-{y1:.1f}m has its only door "
                f"on its {side} wall, opening onto the {onto}"
            )
            break
    if not lines:
        return ""
    return "WET ROOM DOORS (copy exactly): " + "; ".join(lines) + ". "


def _topology_clause(
    rooms: list[dict[str, Any]] | None, width: float | None, depth: float | None
) -> str:
    """Positions métriques des pièces pour que FLUX recopie la topologie."""
    if not rooms or not width or not depth:
        return ""
    lines: list[str] = []
    corridor: list[str] = []
    for room in rooms:
        poly = room.get("polygon") or []
        if len(poly) < 3:
            continue
        try:
            xs = [float(p["x"]) for p in poly]
            ys = [float(p["y"]) for p in poly]
        except (KeyError, TypeError, ValueError):
            continue
        typ = str(room.get("type") or "room")
        box = f"x={min(xs):.1f}-{max(xs):.1f}m, y={min(ys):.1f}-{max(ys):.1f}m"
        if typ == "hallway":
            corridor.append(
                box
            )  # les segments d'un même couloir ne sont pas des pièces
            continue
        name = str(room.get("name") or _FURN_ROOM_EN.get(typ, typ))
        lines.append(f"{name} ({typ}): {box}")
        if len(lines) >= 16:
            break
    if corridor:
        lines.append(
            "Hallway (counts as ONE room, drawn as "
            f"{len(corridor)} connected part{'s' if len(corridor) > 1 else ''}; "
            "keep the walls exactly as in the attached plan): " + " | ".join(corridor)
        )
    if not lines:
        return ""
    return (
        "ROOM POSITIONS in metres (origin top-left, x right, y down toward the garden): "
        + "; ".join(lines)
        + ". Keep this topology. Do not swap rooms. "
    )


def _layout_guide_b64(
    rooms: list[dict[str, Any]],
    width: float,
    depth: float,
    walls: list[dict[str, Any]] | None = None,
    openings: list[dict[str, Any]] | None = None,
    furniture: list[dict[str, Any]] | None = None,
) -> str | None:
    """JPEG du plan vectoriel : Flux copie murs + objets déjà placés dans la bonne pièce."""
    if not rooms:
        return None
    from . import together_image

    try:
        wall_list = (
            walls
            if walls is not None
            else perimeter_and_internal_walls(rooms, width, depth)
        )
        open_list = (
            openings
            if openings is not None
            else default_openings(wall_list, width, depth, rooms)
        )
        png = _render_floorplan(
            rooms, wall_list, open_list, width, depth, furniture=furniture
        )
        return together_image._png_b64_to_jpeg_uri(png, max_side=1024)
    except Exception as exc:  # noqa: BLE001
        print(f"[diffusion] layout guide: {exc}", flush=True)
        return None


def _format_furniture_plan(data: dict[str, Any] | None) -> str:
    rooms = (data or {}).get("rooms") if isinstance(data, dict) else None
    if not isinstance(rooms, list):
        return ""
    lines: list[str] = []
    for r in rooms:
        if not isinstance(r, dict):
            continue
        typ = str(r.get("type") or "").strip().lower()
        if typ not in _FURN_ROOM_EN:
            continue
        raw_items = r.get("items") or r.get("objects") or []
        cleaned: list[str] = []
        for it in raw_items:
            if isinstance(it, dict):
                text = str(
                    it.get("item") or it.get("name") or it.get("place") or ""
                ).strip()
            else:
                text = str(it or "").strip()
            if not text or _item_forbidden(typ, text):
                continue
            cleaned.append(text.rstrip("."))
            if len(cleaned) >= 8:
                break
        if not cleaned:
            continue
        lines.append(f"- {_FURN_ROOM_EN[typ]}: " + "; ".join(cleaned))
    if not lines:
        return ""
    return (
        "FURNITURE INVENTORY (draw ONLY these objects, nothing extra, nothing in the wrong room): "
        + " ".join(lines)
        + " Bathroom fixtures stay in the bathroom/WC only. "
    )


def _plan_furniture_with_llm(brief: str, spec: dict[str, Any] | None) -> str:
    """gpt-oss-120b : inventaire d'objets par pièce. Chaîne vide si l'appel échoue."""
    from . import together_image

    if not together_image.planner_enabled():
        return ""
    types = _program_types(spec)
    program = ", ".join(types) if types else "infer rooms from the brief"
    messages = [
        {"role": "system", "content": _FURNITURE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"BRIEF:\n{brief or 'a house'}\n"
                f"ROOM PROGRAM (place furniture in each): {program}\n"
                "Return the JSON inventory."
            ),
        },
    ]
    try:
        raw = together_image.chat_completion(
            messages, json_mode=True, temperature=0.2, max_tokens=900
        )
    except Exception:  # noqa: BLE001
        return ""
    return _format_furniture_plan(_parse_json_obj(raw))


def _default_furniture_block() -> str:
    return (
        "Living room: one dark L-shaped sofa against a long wall, rug, low coffee table in front, "
        "TV on the opposite wall (sofa faces the TV), two armchairs. No dining table, no dining chairs. "
        "Kitchen: simple L-shaped or U-shaped counters on the walls, a small square sink and hob in the run, "
        "fridge at the end. Empty floor in the centre. No dining table, no chairs, no bathtub, no tub. "
        "Bedrooms: exactly one bed per room, headboard on a wall, nightstands, wardrobe. "
        "Never two beds in the same bedroom. "
        "Never a toilet, bathtub, shower or washbasin in a bedroom. "
        "Bathroom: tub, a clearly visible toilet and basin — only in this room. "
        "WC: a clearly visible toilet and a small basin, no bathtub. "
        "Garage: one simple car outline aligned with the door. "
    )


def _flux_prompt(
    spec: dict[str, Any] | None = None,
    rooms: list[dict[str, Any]] | None = None,
    width: float | None = None,
    depth: float | None = None,
    label_mode: str | None = None,
    brief: str | None = None,
    furniture_plan: str | None = None,
    repair_notes: list[str] | None = None,
    careful: bool = False,
    layout_guided: bool = False,
    walls: list[dict[str, Any]] | None = None,
    openings: list[dict[str, Any]] | None = None,
) -> str:
    """Brief + style Sweet Home 3D + (si layout_guided) consigne de suivre le plan attaché."""
    _ = label_mode
    text = (brief or (spec or {}).get("brief") or "").strip()
    if not text:
        text = "a house"
    furn = (furniture_plan or "").strip() or _default_furniture_block()
    notes = [str(x).strip() for x in (repair_notes or []) if str(x).strip()]
    fix = ""
    if notes:
        fix = (
            "Keep those constraints: "
            + "; ".join(notes[:6])
            + ". Put each object only in its matching room. "
            "Especially: no bathroom objects in kitchen, dining or bedrooms. No letters on the drawing. "
        )
    careful_txt = ""
    if careful:
        careful_txt = (
            "Be extra strict. "
            "Kitchen and dining: NO toilet, bathtub, shower or washbasin. "
            "Living: sofa + coffee table + TV — not a dining room. "
            "Exactly the required room counts, never two dining rooms. "
        )
    if layout_guided:
        head = (
            "The attached image (image 1) is the LAYOUT TO FOLLOW. "
            "Keep the SAME walls, the SAME rooms, and the SAME furniture in the SAME rooms. "
            "Do not invent a new plan. Do not move objects to another room. "
            "Bathroom and WC fixtures stay in the bathroom/WC — never copy them into the "
            "kitchen, living room, dining room or bedrooms. "
            "Kitchen: wall counters and a small square sink only — never a bathtub, tub or large basin. "
            "Living room: sofa, two armchairs, low coffee table and TV — not a dining table. "
            "Do not draw two dining rooms. "
            "Each bedroom has exactly one bed — never two twin beds. "
            "If a WC room exists, draw a clearly visible toilet in it. "
            f"{_shape_clause()}"
            f"{_wet_room_doors_clause(rooms, walls, openings)}"
            "Redraw it as a simpler amateur Sweet Home 3D 2D screenshot: grey poche walls, "
            "simple floor fills, simple top-down furniture symbols, faint grid. "
            f"This request: {text}. "
        )
    else:
        head = (
            "The attached image (image 1) is a Sweet Home 3D 2D STYLE SAMPLE. "
            "Keep the SAME IDEA — 2D top-down house plan, grey walls, simple floor fills, "
            "simple furniture symbols seen from above, faint grid — but draw it SIMPLER, "
            "as if a person made it quickly in that software, not as a photoreal render. "
            "Not its room layout and not its labels. "
            "Invent a NEW floor plan for this request: "
            f"{text}. "
        )
    return (
        f"{head}"
        f"{_required_rooms_clause(spec, rooms)}"
        f"{_sanitary_layout_clause()}"
        f"{_topology_clause(rooms, width, depth)}"
        "Look: amateur-friendly interior-design software screenshot, hand-placed furniture, "
        "flat 2D icons, limited detail. NOT photorealistic, NOT a 3D CGI visualization, "
        "NOT Unreal/Twinmotion, NOT a photograph, NOT a dollhouse. "
        "Camera: perfectly vertical orthographic top-down. "
        "Canvas: plain white with a faint light-grey square grid. "
        "Walls: thick filled medium-grey bands (simple poche), tiny drop shadow at most. "
        "Doors: gap plus a thin leaf and a quarter-circle arc. "
        "Windows: simple white cuts in the grey walls. "
        "Floors: simple — a few wood-plank lines in living/bedrooms, a light tile grid "
        "in kitchen/bath, flat grey in the garage, flat green around the house, "
        "a small wood porch at the entrance. No lush grass, no photo textures. "
        "NO TEXT, NO LETTERS, NO WORDS anywhere: no room names, no Bedroom, Kitchen, "
        "Living room, Garage, Garden, Bathroom, no French labels, no numbers, no m², "
        "no legend, no title, no captions. Furniture and walls only, blank floors. "
        "The sample may show names — ignore them, they must not appear in your drawing. "
        f"{careful_txt}"
        f"{fix}"
        f"{_coherence_clause(spec)}"
        "Furniture: simple coloured top-down symbols (rectangles and ovals), little shading. "
        "Nothing overlaps a wall, another object, or a door swing. Walking space at doors. "
        f"{furn}"
        "Few objects, lots of empty floor, muted colours, no people. "
        "Output only the plan — no toolbars, menus, catalog, or window chrome."
    )


def _flux_edit_prompt(
    *,
    brief: str | None = None,
    spec: dict[str, Any] | None = None,
    edit_en: str = "",
    repair_notes: list[str] | None = None,
) -> str:
    """Consigne de retouche : le changement doit être visible, pas une copie du PNG."""
    text = (brief or (spec or {}).get("brief") or "").strip() or "a house"
    notes = [str(x).strip() for x in (repair_notes or []) if str(x).strip()]
    fix = ""
    if notes:
        fix = "Also fix: " + "; ".join(notes[:6]) + ". "
    change = (edit_en or "").strip() or "keep the same furniture and walls"
    return (
        "The attached image is the CURRENT 2D Sweet Home 3D floor plan to EDIT. "
        f"You MUST apply this change so it is obviously visible — do not return a copy: {change}. "
        "Keep the same camera and simple style. Keep outer walls unless the change "
        "adds or removes a room. If a room is removed, delete it and close remaining walls. "
        "If a room is added, insert a new enclosed room. "
        f"Original request was: {text}. "
        "Do not invent extra rooms beyond the required list. "
        f"{_required_rooms_clause(spec)}"
        f"{fix}"
        f"{_coherence_clause(spec)}"
        "NO TEXT, NO LETTERS, NO WORDS, no room names, no numbers, no legend. "
        "Output only the edited plan — no toolbars or window chrome."
    )


_FLUX_FURNITURE = {
    "living": "a sofa with two armchairs around a low coffee table on a rug, a TV console on the wall",
    "dining": "a dining table with six chairs",
    "bedroom": "a double bed with two nightstands and a wardrobe",
    "office": "a desk with an office chair and a bookshelf",
    "kitchen": "an L-shaped kitchen counter with a small square sink, cooktop and fridge",
    "bathroom": "a bathtub, a washbasin and a toilet",
    "wc": "a clearly visible toilet and a small washbasin, no bathtub",
    "laundry": "a washing machine and a laundry sink",
    "hallway": "a slim console table",
    "garage": "a parked car outline",
    "storage": "storage shelves along the wall",
    "veranda": "two outdoor lounge chairs and a small table",
}


def _furniture_clause(rooms: list[dict[str, Any]]) -> str:
    """Décrit le mobilier attendu pièce par pièce (en anglais, sans nom à écrire)."""
    items: list[str] = []
    for r in rooms:
        typ = str(r.get("type") or "")
        furn = _FLUX_FURNITURE.get(typ)
        if not furn:
            continue
        name = _ascii_upper(str(r.get("name") or typ)) or typ.upper()
        items.append(f"the {name} contains {furn}")
    if not items:
        return "Each room has furniture matching its function, drawn as elegant thin-line silhouettes. "
    return (
        "Furniture clearly visible in every room, realistic top-down objects "
        "sitting flat inside each room: " + "; ".join(items) + ". "
    )


_NAME_TO_TYPE = {
    "SEJOUR": "living",
    "SALON": "living",
    "LIVING": "living",
    "SALLE DE SEJOUR": "living",
    "CUISINE": "kitchen",
    "KITCHEN": "kitchen",
    "KITCHENETTE": "kitchen",
    "SALLE A MANGER": "dining",
    "SAM": "dining",
    "DINING": "dining",
    "CHAMBRE": "bedroom",
    "CHAMBRE PARENTALE": "bedroom",
    "SUITE PARENTALE": "bedroom",
    "SUITE": "bedroom",
    "BEDROOM": "bedroom",
    "SDB": "bathroom",
    "SALLE DE BAIN": "bathroom",
    "SALLE D'EAU": "bathroom",
    "SALLE DE BAINS": "bathroom",
    "BATHROOM": "bathroom",
    "BAIN": "bathroom",
    "WC": "wc",
    "TOILETTES": "wc",
    "TOILETTE": "wc",
    "COULOIR": "hallway",
    "DEGAGEMENT": "hallway",
    "HALL": "hallway",
    "ENTREE": "hallway",
    "CIRCULATION": "hallway",
    "COULOIR CENTRAL": "hallway",
    "GARAGE": "garage",
    "CARPORT": "garage",
    "BUREAU": "office",
    "OFFICE": "office",
    "CELLIER": "storage",
    "RANGEMENT": "storage",
    "DEBARRAS": "storage",
    "PLACARD": "storage",
    "BUANDERIE": "laundry",
    "LINGERIE": "laundry",
    "VERANDA": "veranda",
    "TERRASSE": "veranda",
    "VARANGUE": "veranda",
}


def _room_type_from_name(name: str) -> str:
    up = _ascii_upper(name)
    if up in _NAME_TO_TYPE:
        return _NAME_TO_TYPE[up]
    base = re.sub(r"[\s\-]*\d+\s*$", "", up).strip()
    return _NAME_TO_TYPE.get(base, "other")


def _room_display_name(raw: str, typ: str) -> str:
    up = _ascii_upper(raw)
    m = re.search(r"(\d+)\s*$", up)
    n = m.group(1) if m else ""
    if typ in _TYPE_FR:
        return f"{_TYPE_FR[typ]} {n}".strip()
    return raw.strip().title() or "Pièce"


_LAYOUT_SYSTEM = (
    "You are a senior residential architect drawing a Sweet Home 3D style single-storey house. "
    "You SIZE rooms (areas). Geometry is tiled later. Return STRICT JSON only.\n\n"
    "HARD RULES\n"
    "- Use EXACTLY the rooms listed in the program: same names, same count. Do NOT add, "
    "rename, split or drop any room.\n"
    "- Names must be copied character-for-character from the program list.\n"
    "- Origin top-left: x to the east, y to the south. y=0 is NORTH (back of the house, "
    "bedrooms). y=D is SOUTH (garden + main entrance).\n"
    "- Night zone (all CHAMBRE) along the north. A HALLWAY/COULOIR MUST sit between the "
    "night zone and the day zone (SEJOUR, CUISINE). Bedrooms must not share a wall with "
    "the living room: they open onto the corridor only.\n"
    "- WC/toilettes is a GUEST toilet on the corridor (east of the hallway), opening ONLY "
    "onto the hallway. Never place it inside/behind a bedroom or kitchen: guests must reach "
    "it from the circulation without crossing a private room. CUISINE west of the day zone. "
    "Family SDB opens onto the corridor; ensuite may open to the master bedroom only.\n"
    "- GARAGE on the EAST. SEJOUR is the largest day room, entrance on its south wall. "
    "An ensuite exists ONLY for a program room marked (ensuite); every other SDB is shared "
    "and opens onto the corridor. A WC or SDB has exactly ONE door.\n"
    "- Keep proportions habitable: no room thinner than 1.8 m (WC/SDB may be 1.4 m).\n\n"
    "OUTPUT - one JSON object, no markdown:\n"
    '{"veranda_depth": 0, "rooms": [{"name": "SEJOUR", "area": 28, "zone": "front"}]}\n'
    "List every program room once. zone is front|centre|back|left|right. veranda_depth=0."
)


def _layout_user(
    spec: dict[str, Any], program: list[dict[str, Any]], width: float, depth: float
) -> str:
    lines = []
    for r in program:
        name = _ascii_upper(str(r.get("name") or r.get("type") or "room")) or "ROOM"
        try:
            lines.append(
                f"- {name}: current area ~{float(r.get('area_m2') or 12):.0f} m2"
                + (" (ensuite)" if r.get("ensuite") else "")
            )
        except (TypeError, ValueError):
            lines.append(f"- {name}")
    style = str(spec.get("style") or "").strip() or "contemporary"
    return (
        f"FOOTPRINT W={width:.1f} m, D={depth:.1f} m (total {width * depth:.0f} m2). "
        f"Architectural style: {style}. Origin (0,0) = north-west, y increases south toward "
        "the garden and the main entrance.\n"
        "FIXED ROOM PROGRAM — copy these names exactly, one entry each, no extras:\n"
        + "\n".join(lines)
        + "\n\nReturn the JSON tiling."
    )


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


_ZONE_ORDER = {"front": 0, "left": 1, "right": 2, "centre": 3, "back": 4}
_TYPE_MIN_AREA = {
    "living": 18.0,
    "bedroom": 9.0,
    "kitchen": 8.0,
    "dining": 9.0,
    "bathroom": 3.5,
    "wc": 2.4,
    "office": 7.5,
    "hallway": 3.0,
    "garage": 14.0,
    "storage": 2.0,
    "laundry": 3.0,
}


def _merge_llm_program(
    program: list[dict[str, Any]], llm_rooms: Any, width: float, depth: float
) -> list[dict[str, Any]] | None:
    """Surfaces / ordre LLM, programme verrouillé : aucune pièce ajoutée."""
    if not isinstance(llm_rooms, list) or len(llm_rooms) < 2:
        return None
    parsed: list[dict[str, Any]] = []
    for it in llm_rooms:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        if not name:
            continue
        typ = _room_type_from_name(name)
        if typ in {"veranda", "other"}:
            continue
        try:
            area = float(it.get("area") or it.get("area_m2") or 0.0)
        except (TypeError, ValueError):
            area = 0.0
        if area <= 0:
            try:
                area = float(it.get("w") or it.get("width") or 0) * float(
                    it.get("d") or it.get("depth") or 0
                )
            except (TypeError, ValueError):
                area = 0.0
        zone = str(it.get("zone") or "").strip().lower()
        parsed.append({"name": name, "typ": typ, "area": max(area, 0.0), "zone": zone})

    if not (2 <= len(parsed) <= len(program) + 2):
        return None
    types = {p["typ"] for p in parsed}
    if "living" not in types and "bedroom" not in types:
        return None

    foot = max(1.0, width * depth)
    floored = [max(p["area"], _TYPE_MIN_AREA.get(p["typ"], 6.0)) for p in parsed]
    k = (foot * 0.97) / (sum(floored) or 1.0)

    unused = list(range(len(program)))
    out: list[dict[str, Any]] = []
    for i, p in enumerate(parsed):
        src = None
        for j in list(unused):
            if program[j].get("type") == p["typ"]:
                src = program[j]
                unused.remove(j)
                break
        if src is None:
            continue  # pièce hors programme → ignorée
        out.append(
            {
                "id": src.get("id") or f"llm_{i + 1}",
                "type": src.get("type") or p["typ"],
                "name": src.get("name") or _label(p["typ"], None),
                "area_m2": round(max(2.0, floored[i] * k), 1),
                "_zone": _ZONE_ORDER.get(p["zone"], 3),
                **({"ensuite": True} if src.get("ensuite") else {}),
            }
        )
    for j in unused:
        src = program[j]
        out.append(
            {
                "id": src.get("id") or f"r{len(out) + 1}",
                "type": src.get("type"),
                "name": src.get("name") or _label(str(src.get("type") or ""), None),
                "area_m2": float(src.get("area_m2") or 8),
                "_zone": 3,
                **({"ensuite": True} if src.get("ensuite") else {}),
            }
        )
    if len(out) != len(program) or len(out) < 2:
        return None
    out.sort(key=lambda r: r.pop("_zone"))
    return out


def _parse_llm_rect(
    it: dict[str, Any], width: float, depth: float
) -> tuple[float, float, float, float] | None:
    """Rectangle (x0, y0, x1, y1) depuis x/y/w/d, width/depth, ou polygone."""
    poly = it.get("polygon")
    if isinstance(poly, list) and len(poly) >= 3:
        try:
            xs = [float(p["x"]) for p in poly]
            ys = [float(p["y"]) for p in poly]
            return min(xs), min(ys), max(xs), max(ys)
        except (TypeError, ValueError, KeyError):
            pass
    raw_x = it.get("x")
    raw_y = it.get("y")
    try:
        x = float(raw_x if raw_x is not None else it.get("x_m") or 0)
        y = float(raw_y if raw_y is not None else it.get("y_m") or 0)
        w = float(it.get("w") or it.get("width") or it.get("width_m") or 0)
        d = float(
            it.get("d") or it.get("depth") or it.get("depth_m") or it.get("h") or 0
        )
    except (TypeError, ValueError):
        return None
    if w < 1.2 or d < 1.2:
        return None
    x0, y0, x1, y1 = x, y, x + w, y + d
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(width, x1), min(depth, y1)
    if x1 - x0 < 1.2 or y1 - y0 < 1.2:
        return None
    g = 0.1
    x0, y0 = round(x0 / g) * g, round(y0 / g) * g
    x1, y1 = round(x1 / g) * g, round(y1 / g) * g
    x1, y1 = min(width, max(x0 + 1.2, x1)), min(depth, max(y0 + 1.2, y1))
    return round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)


def _rect_overlap(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _normalize_llm_rooms(
    program: list[dict[str, Any]], llm_rooms: Any, width: float, depth: float
) -> list[dict[str, Any]] | None:
    """Accepte un pavage LLM s'il colle au programme, sans chevauchement ni pièce fantôme."""
    if not isinstance(llm_rooms, list) or len(llm_rooms) < 2:
        return None
    parsed: list[dict[str, Any]] = []
    for it in llm_rooms:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        typ = _room_type_from_name(name) if name else str(it.get("type") or "")
        if typ in {"veranda", "other", ""}:
            continue
        rect = _parse_llm_rect(it, width, depth)
        if rect is None:
            return None
        parsed.append({"name": name, "typ": typ, "rect": rect})

    unused = list(range(len(program)))
    placed: list[dict[str, Any]] = []
    for p in parsed:
        src = None
        for j in list(unused):
            if program[j].get("type") == p["typ"]:
                src = program[j]
                unused.remove(j)
                break
        if src is None:
            continue  # extra → drop
        x0, y0, x1, y1 = p["rect"]
        placed.append(
            {
                "id": src.get("id") or f"r{len(placed) + 1}",
                "type": src["type"],
                "name": src.get("name") or _label(src["type"], None),
                "area_m2": round((x1 - x0) * (y1 - y0), 2),
                "polygon": [
                    {"x": x0, "y": y0},
                    {"x": x1, "y": y0},
                    {"x": x1, "y": y1},
                    {"x": x0, "y": y1},
                ],
            }
        )
    if unused or len(placed) != len(program):
        return None

    for i, a in enumerate(placed):
        ra = _edges_m(a["polygon"])
        aa = max(0.01, (ra[2] - ra[0]) * (ra[3] - ra[1]))
        for b in placed[i + 1 :]:
            ov = _rect_overlap(ra, _edges_m(b["polygon"]))
            if ov / aa > 0.12:
                return None
    covered = sum(
        (e[2] - e[0]) * (e[3] - e[1]) for e in (_edges_m(r["polygon"]) for r in placed)
    )
    if covered / max(width * depth, 1.0) < 0.85:
        return None
    return placed


def _house_like(rooms: list[dict[str, Any]], width: float, depth: float) -> bool:
    """True si zones nuit/jour + règles sanitaires (WC/cuisine, chambres/séjour)."""
    from .layout_opt import sanitary_violations

    living = next((r for r in rooms if r.get("type") == "living"), None)
    beds = [r for r in rooms if r.get("type") == "bedroom"]
    if living:
        ys = [float(p["y"]) for p in (living.get("polygon") or [])]
        if ys and (min(ys) + max(ys)) / 2 < depth * 0.35:
            return False
    for bed in beds:
        ys = [float(p["y"]) for p in (bed.get("polygon") or [])]
        if ys and min(ys) > depth * 0.50:
            return False
    if sanitary_violations(rooms):
        return False
    _ = width
    return True


def _llm_layout(
    spec: dict[str, Any], program: list[dict[str, Any]], width: float, depth: float
) -> tuple[list[dict[str, Any]] | None, float]:
    """Together : surfaces / ordre seulement. Le pavage passe toujours par pack_house."""
    from . import together_image
    from .layout_opt import pack_house

    if not together_image.planner_enabled():
        return None, 0.0
    messages = [
        {"role": "system", "content": _LAYOUT_SYSTEM},
        {"role": "user", "content": _layout_user(spec, program, width, depth)},
    ]
    for attempt in range(2):
        try:
            raw = together_image.chat_completion(
                messages,
                json_mode=True,
                temperature=0.15 + 0.2 * attempt,
                max_tokens=1800,
            )
        except Exception:  # noqa: BLE001
            raw = None
        data = _parse_json_obj(raw)
        if not data:
            continue
        merged = _merge_llm_program(program, data.get("rooms"), width, depth) or program
        if merged:
            packed = pack_house(merged, width, depth, grid=0.1, min_side=1.6)
            if packed:
                return packed, 0.0
    return None, 0.0


def _llm_program(
    spec: dict[str, Any], program: list[dict[str, Any]], width: float, depth: float
) -> tuple[list[dict[str, Any]] | None, float]:
    """Compat tests : taille/ordre seulement (sans polygones)."""
    rooms, vd = _llm_layout(spec, program, width, depth)
    if not rooms:
        return None, 0.0
    return [{k: r[k] for k in r if k != "polygon"} for r in rooms], vd


def pack_rooms(
    rooms: list[dict[str, Any]], width: float, depth: float
) -> list[dict[str, Any]]:
    """Pavé maison : nuit au nord, couloir, jour au sud, cuisine à l'ouest, garage à l'est."""
    if not rooms:
        return []
    from .layout_opt import pack_house

    return pack_house(rooms, width, depth, grid=0.1, min_side=1.6)


def _r(v: float) -> float:
    return round(max(0.0, v), 2)


def _bsp_pack(
    rooms: list[dict[str, Any]], x0: float, y0: float, x1: float, y1: float
) -> list[dict[str, Any]]:
    if not rooms:
        # Sans cette garde, `mid = max(1, 0)` renvoyait deux moitiés vides :
        # récursion infinie puis ZeroDivisionError sur `a_l + a_r`.
        return []
    if len(rooms) == 1:
        return [
            {
                **rooms[0],
                "polygon": [
                    {"x": _r(x0), "y": _r(y0)},
                    {"x": _r(x1), "y": _r(y0)},
                    {"x": _r(x1), "y": _r(y1)},
                    {"x": _r(x0), "y": _r(y1)},
                ],
            }
        ]
    mid = max(1, len(rooms) // 2)
    left, right = rooms[:mid], rooms[mid:]
    a_l = sum(max(float(r.get("area_m2") or 12), 6) for r in left)
    a_r = sum(max(float(r.get("area_m2") or 12), 6) for r in right)
    frac = a_l / (a_l + a_r)
    if (x1 - x0) >= (y1 - y0):
        split = _r(x0 + (x1 - x0) * frac)
        split = min(max(split, _r(x0 + 2)), _r(x1 - 2))
        return _bsp_pack(left, x0, y0, split, y1) + _bsp_pack(right, split, y0, x1, y1)
    split = _r(y0 + (y1 - y0) * frac)
    split = min(max(split, _r(y0 + 2)), _r(y1 - 2))
    return _bsp_pack(left, x0, y0, x1, split) + _bsp_pack(right, x0, split, x1, y1)
