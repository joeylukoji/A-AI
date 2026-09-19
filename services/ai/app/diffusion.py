from __future__ import annotations

import base64
import contextlib
import io
import os
import re
import unicodedata
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont

# `ImageFont.truetype` rend une `FreeTypeFont`, `load_default()` l'une ou
# l'autre selon la build Pillow : les deux exposent l'API utilisée ici.
_Font = ImageFont.ImageFont | ImageFont.FreeTypeFont


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


def render_preview(doc: dict[str, Any], spec: dict[str, Any] | None = None) -> tuple[str, str]:
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
    """Dessin local (pièces + meubles au bon endroit) puis un seul appel image (Gemini / Flux)."""
    from . import together_image

    constraints = constraints or {}
    spec = dict(spec or {})
    if brief and not spec.get("brief"):
        spec["brief"] = brief
    width = float(constraints.get("parcel_width_m") or constraints.get("max_width_m") or 12)
    depth = float(constraints.get("parcel_depth_m") or constraints.get("max_depth_m") or 10)
    if not _flux_wanted():
        return "", "flux-skipped"
    rooms = _usable_layout_rooms(layout_rooms, spec, width, depth)
    guide = _layout_guide_b64(
        rooms, width, depth, walls=walls, openings=openings, furniture=furniture
    )
    layout_guided = bool(guide)
    ref = guide or together_image.style_reference_b64()
    furniture_plan = _plan_furniture_with_llm(brief, spec)
    careful = _flag_on(constraints.get("careful")) or _flag_on(spec.get("careful"))
    notes = list(_careful_repair_notes(spec) if careful else [])
    _notify_job_step(job_id, "flux")
    b64 = together_image.generate_floorplan_image(
        _flux_prompt(
            brief=brief,
            spec=spec,
            furniture_plan=furniture_plan,
            repair_notes=notes,
            careful=careful,
            layout_guided=layout_guided,
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
    instruction = (instruction or "").strip()
    constraints = dict(constraints or {})
    spec = dict(spec or {})
    if brief and not spec.get("brief"):
        spec["brief"] = brief
    plan_document = dict(plan_document or {})
    parsed = _interpret_edit(instruction, spec)
    edit_en = parsed["edit_en"]
    reply_fr = parsed["reply_fr"]
    new_rooms = parsed.get("rooms")
    clarify = bool(parsed.get("clarify"))
    rebuilt = False
    adapted: dict[str, Any] = {}
    if new_rooms:
        spec["rooms"] = new_rooms
        adapted = _adapted_from_spec(spec, constraints)
        plan_document = adapted.get("plan_document") or plan_document
        rebuilt = True
    _notify_job_step(job_id, "edit")
    brief_txt = brief or str(spec.get("brief") or "")
    if clarify:
        preview = (image_png_b64 or "").strip()
        method = "edit-clarify"
    elif rebuilt:
        preview, method = generate_flux_plan(
            brief_txt,
            constraints,
            spec=spec,
            job_id=job_id,
            layout_rooms=(plan_document or {}).get("rooms"),
            walls=(plan_document or {}).get("walls"),
            openings=(plan_document or {}).get("openings"),
            furniture=(plan_document or {}).get("furniture"),
        )
        if preview:
            method = (method or "flux") + "+edit"
        else:
            preview = render_plan_document(plan_document) if plan_document else ""
            method = method or "procedural+edit"
    else:
        preview, method = _edit_flux_image(
            brief=brief_txt,
            spec=spec,
            constraints=constraints,
            edit_en=edit_en,
            source_png_b64=image_png_b64,
            job_id=job_id,
        )
        if not preview:
            preview = (image_png_b64 or "").strip()
            method = method or "edit-kept"
    if not adapted and plan_document:
        adapted = {
            "plan_document": plan_document,
            "compliance": {},
            "dimensions": [],
            "parcel": {},
            "rules": {},
        }
    return {
        "building_spec": spec,
        "plan_document": plan_document,
        "compliance": adapted.get("compliance") or {},
        "dimensions": adapted.get("dimensions") or [],
        "parcel": adapted.get("parcel") or {},
        "rules": adapted.get("rules") or {},
        "preview_key": "",
        "image_png_b64": preview,
        "reply_fr": reply_fr,
        "edit_en": edit_en,
        "method": method,
        "clarify": clarify,
        "steps": ["edit", "flux"],
    }


def _adapted_from_spec(spec: dict[str, Any], constraints: dict[str, Any]) -> dict[str, Any]:
    from . import gan_refine, plan_adapt, vectorize

    gen = generate(spec, image=False)
    refined = gan_refine.refine({
        "image_png_b64": gen.get("image_png_b64"),
        "layout": gen.get("layout"),
        "building_spec": spec,
        "method": gen.get("method"),
    })
    plan = vectorize.vectorize({
        "layout": refined.get("layout") or gen.get("layout"),
        "building_spec": spec,
    })
    c = spec.get("constraints") or {}
    return plan_adapt.adapt({
        "plan_document": plan["plan_document"],
        "parcel": {
            "width_m": constraints.get("parcel_width_m") or c.get("max_width_m"),
            "depth_m": constraints.get("parcel_depth_m") or c.get("max_depth_m"),
            "setback_m": constraints.get("setback_m") or 0,
        },
        "rules": constraints.get("rules") or {},
    })


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
    width = float(constraints.get("parcel_width_m") or constraints.get("max_width_m") or 12)
    depth = float(constraints.get("parcel_depth_m") or constraints.get("max_depth_m") or 10)
    src = together_image._png_b64_to_jpeg_uri(source_png_b64, max_side=1024) if source_png_b64 else None
    ref = src or together_image.style_reference_b64()
    _notify_job_step(job_id, "flux")
    prompt = (
        _flux_edit_prompt(brief=brief, spec=spec, edit_en=edit_en)
        if src
        else _flux_prompt(brief=brief, spec=spec, repair_notes=[edit_en], layout_guided=False)
    )
    b64 = together_image.generate_floorplan_image(prompt, width, depth, reference_png_b64=ref)
    if b64:
        return b64, together_image.method_name() + "+edit"
    return "", "flux-failed"


_EDIT_SYSTEM = (
    "You convert a floor-plan change request into JSON. Return STRICT JSON only: "
    "{\"edit_en\":\"...\",\"reply_fr\":\"...\",\"rooms\":null} "
    "edit_en: 1-2 English sentences telling an image model how to edit the EXISTING plan. "
    "If a room is removed, say so clearly (delete that room, close remaining walls). "
    "reply_fr: one short French sentence confirming the change, no markdown. "
    "rooms: null for furniture/window-only edits. If the user ADDS or REMOVES rooms, "
    "rooms MUST be the FULL new program "
    "[{\"type\":\"living\",\"count\":1},{\"type\":\"kitchen\",\"count\":1},...], "
    "without the deleted room. Never keep a room they asked to delete. "
    "If they say 'this room' / 'cette pièce' without naming it, set rooms to null "
    "and ask in reply_fr which room (salon, chambre, garage…). "
    "Allowed types: living, kitchen, dining, bedroom, bathroom, wc, hallway, garage, "
    "office, storage, laundry."
)


def _interpret_edit(instruction: str, spec: dict[str, Any] | None) -> dict[str, Any]:
    """gpt-oss + heuristique : consigne FR/EN → notes FLUX + programme de pièces."""
    from . import together_image

    fallback = {
        "edit_en": instruction or "keep the same floor plan",
        "reply_fr": "Je mets à jour le plan.",
        "rooms": None,
        "clarify": False,
    }
    heur = _heuristic_room_edit(instruction, spec) if instruction else None
    if not instruction:
        return fallback
    if not together_image.planner_enabled():
        return {**fallback, **(heur or {})}

    program = ", ".join(
        f"{n}x {t}" for t, n in _program_counts(spec).items()
    ) or "unknown"
    try:
        raw = together_image.chat_completion(
            [
                {"role": "system", "content": _EDIT_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"CURRENT ROOM PROGRAM: {program}\n"
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
    edit_en = str(data.get("edit_en") or data.get("edit") or instruction).strip() or instruction
    reply_fr = str(data.get("reply_fr") or data.get("reply") or fallback["reply_fr"]).strip()
    rooms = _sanitize_rooms_program(data.get("rooms"))
    if rooms and _program_counts({"rooms": rooms}) == _program_counts(spec):
        rooms = None
    if heur and heur.get("clarify"):
        return {
            "edit_en": heur.get("edit_en") or edit_en,
            "reply_fr": heur.get("reply_fr") or reply_fr,
            "rooms": None,
            "clarify": True,
        }
    if heur and heur.get("rooms"):
        rooms = heur["rooms"]
        edit_en = heur.get("edit_en") or edit_en
        reply_fr = heur.get("reply_fr") or reply_fr
    return {
        "edit_en": edit_en,
        "reply_fr": reply_fr or fallback["reply_fr"],
        "rooms": rooms,
        "clarify": False,
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
    add_m = None if remove_m else re.search(rf"\b{_ADD_VERBS}\s+{det}(?P<room>{alts})\b", up)
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


def _notify_job_step(job_id: str | None, step: str) -> None:
    """Pousse le pas courant (SSE) vers l'API Go si un job_id est fourni."""
    from uuid import UUID

    jid = (job_id or "").strip()
    api = (os.getenv("API_CALLBACK_BASE") or "").strip()
    if not jid or not api:
        return
    try:
        UUID(jid)
    except ValueError:
        return
    token = os.getenv("INTERNAL_TOKEN", "dev-internal-token")
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{api}/internal/jobs/{jid}/running",
                headers={"X-Internal-Token": token, "Content-Type": "application/json"},
                json={"step": step},
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[diffusion] notify {step}: {exc}", flush=True)


def _flux_wanted() -> bool:
    from . import together_image

    if not together_image.available():
        return False
    renderer = (os.getenv("IMAGE_RENDERER") or "flux").strip().lower()
    return renderer in {
        "flux", "flux2", "flux2-dev", "flux2-max", "image", "gemini", "eden", "edenai",
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
    """FLUX.2-max redessine le plan vectoriel ; repli local si l'API manque."""
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
    """Disposition des pièces (LLM ou packer), puis image FLUX.2-max si `image`.

    `image=False` : layout seul (le pipeline appelle `render_preview` après adapt,
    pour ne facturer FLUX qu'une fois, sur la géométrie finale).
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
        b64, method = _flux_or_vector("", layout_rooms, width, depth, spec, planned=planned)
        if not b64:
            b64 = _render_floorplan(layout_rooms, walls, openings, width, depth, veranda_depth)
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


_ROOM_FILL_SOFT: dict[str, tuple[int, int, int]] = {
    "living": (196, 148, 72), "kitchen": (248, 248, 246), "dining": (210, 170, 110),
    "bedroom": (232, 214, 176), "bathroom": (210, 214, 216), "wc": (210, 214, 216),
    "hallway": (220, 196, 150), "garage": (210, 210, 208), "office": (232, 214, 176),
    "storage": (210, 210, 208), "laundry": (210, 214, 216),
}
_FLOOR_WOOD = (232, 214, 176)
_FLOOR_WOOD_LINE = (210, 188, 148)
_FLOOR_HONEY = (196, 148, 72)
_FLOOR_HONEY_LINE = (176, 128, 58)
_FLOOR_TILE = (248, 248, 246)
_FLOOR_TILE_LINE = (214, 214, 212)
_FLOOR_BATH = (210, 214, 216)
_FLOOR_BATH_LINE = (186, 192, 196)
_FLOOR_HARD = (210, 210, 208)
_RUG = (90, 78, 68)
_PLANT = (86, 130, 64)
_PLANT_IN = (58, 96, 42)
_WALL = (138, 138, 136)
_WALL_DARK = (88, 88, 86)
_WALL_LIGHT = (168, 168, 166)
_FURN = (72, 68, 64)
_FURN_FILL = (248, 248, 246)
_FURN_SOFT = (236, 236, 234)
_SHADOW = (30, 28, 24, 42)
_TEXT = (36, 36, 34)
_TEXT_SOFT = (92, 92, 88)
_PAGE_BG = (232, 232, 230)
_GRASS = (118, 154, 74)
_GRASS_DARK = (96, 132, 58)
_PORCH = (176, 138, 86)
_PORCH_LINE = (148, 112, 64)
_DOOR = (168, 122, 72)
_SS = 3  # supersampling : dessin à 3x puis réduction LANCZOS -> traits et texte nets


def _rrect(d: ImageDraw.ImageDraw, box: Any, r: float, **kw: Any) -> None:
    try:
        d.rounded_rectangle(box, radius=max(1, r), **kw)
    except (AttributeError, TypeError):
        d.rectangle(box, **{k: v for k, v in kw.items() if k != "radius"})


def _wood_planks(
    d: ImageDraw.ImageDraw, P: Any, x0: float, y0: float, x1: float, y1: float,
    tones: list[tuple[int, int, int]], sc: float, ph: float = 0.135, pw: float = 0.88,
) -> None:
    """Parquet à lames décalées, couleur un peu variable."""
    tw = max(1, int(0.008 * sc))
    row, yy = 0, y0
    while yy < y1 - 1e-6:
        yb = min(y1, yy + ph)
        off = (row % 2) * (pw * 0.38)
        xx, col = x0 - off, 0
        while xx < x1:
            xb = min(x1, xx + pw)
            xa = max(x0, xx)
            if xb > xa + 0.02:
                tone = tones[(row * 3 + col) % len(tones)]
                d.rectangle([P(xa, yy), P(xb, yb)], fill=tone)
                seam = (max(40, tone[0] - 28), max(28, tone[1] - 28), max(16, tone[2] - 18))
                d.line([P(xa, yy), P(xb, yy)], fill=seam, width=tw)
            xx += pw
            col += 1
        yy += ph
        row += 1


def _floor_texture(d: ImageDraw.ImageDraw, typ: str, bm: tuple[float, float, float, float],
                   P: Any, sc: float) -> None:
    """Sol de la pièce : parquet à lames, carrelage damier, dalle."""
    x0, y0, x1, y1 = bm
    tw = max(1, int(0.01 * sc))
    if typ in ("living", "dining", "hallway"):
        d.rectangle([P(x0, y0), P(x1, y1)], fill=_FLOOR_HONEY)
        _wood_planks(d, P, x0, y0, x1, y1, [
            (196, 148, 72), (180, 130, 56), (208, 164, 86), (168, 120, 48), (200, 154, 80),
        ], sc)
    elif typ in ("bedroom", "office"):
        d.rectangle([P(x0, y0), P(x1, y1)], fill=_FLOOR_WOOD)
        _wood_planks(d, P, x0, y0, x1, y1, [
            (232, 212, 176), (222, 202, 164), (240, 224, 192), (212, 190, 152), (234, 216, 180),
        ], sc)
    elif typ == "kitchen":
        d.rectangle([P(x0, y0), P(x1, y1)], fill=(216, 212, 204))
        tile, g = 0.38, 0.018
        xx, col = x0, 0
        while xx < x1:
            yy, row = y0, 0
            while yy < y1:
                xa, ya = xx + g, yy + g
                xb, yb = min(x1, xx + tile - g), min(y1, yy + tile - g)
                if xb > xa and yb > ya:
                    fill = (246, 244, 238) if (row + col) % 2 == 0 else (232, 228, 220)
                    d.rectangle([P(xa, ya), P(xb, yb)], fill=fill)
                yy += tile
                row += 1
            xx += tile
            col += 1
    elif typ in ("bathroom", "wc", "laundry"):
        d.rectangle([P(x0, y0), P(x1, y1)], fill=(200, 206, 210))
        tile, g = 0.22, 0.012
        xx, col = x0, 0
        while xx < x1:
            yy, row = y0, 0
            while yy < y1:
                xa, ya = xx + g, yy + g
                xb, yb = min(x1, xx + tile - g), min(y1, yy + tile - g)
                if xb > xa and yb > ya:
                    fill = (228, 234, 238) if (row + col) % 2 == 0 else (208, 216, 220)
                    d.rectangle([P(xa, ya), P(xb, yb)], fill=fill)
                yy += tile
                row += 1
            xx += tile
            col += 1
    elif typ in ("garage", "storage"):
        d.rectangle([P(x0, y0), P(x1, y1)], fill=_FLOOR_HARD)
        step = 1.4
        xx = x0 + step
        while xx < x1:
            d.line([P(xx, y0), P(xx, y1)], fill=(160, 160, 156), width=tw)
            xx += step
        yy = y0 + step
        while yy < y1:
            d.line([P(x0, yy), P(x1, yy)], fill=(160, 160, 156), width=tw)
            yy += step
    else:
        d.rectangle([P(x0, y0), P(x1, y1)], fill=_ROOM_FILL_SOFT.get(typ, (238, 239, 241)))


def _xf(P: Any, px: float, py: float, rot: float) -> Any:
    import math
    rad = math.radians(rot)
    c, s = math.cos(rad), math.sin(rad)

    def T(lx: float, ly: float) -> tuple[float, float]:
        return P(px + lx * c - ly * s, py + lx * s + ly * c)

    return T


def _poly(d: ImageDraw.ImageDraw, pts: list[tuple[float, float]], fill: Any, outline: Any, lw: int) -> None:
    d.polygon(pts, fill=fill, outline=outline)
    if lw > 1:
        d.line(pts + [pts[0]], fill=outline, width=lw)


def _rr_local(
    d: ImageDraw.ImageDraw, T: Any, a: float, b: float, c: float, e: float,
    fill: Any, outline: Any, lw: int,
) -> None:
    _poly(d, [T(a, b), T(c, b), T(c, e), T(a, e)], fill, outline, lw)


def _stamp(
    img: Image.Image, P: Any, px: float, py: float, rot: float,
    wm: float, dm: float, sc: float, paint: Any,
) -> None:
    """Dessine un meuble en local (non tourné) puis le colle avec rotation."""
    pad = max(10, int(0.28 * sc))
    W = max(16, int(wm * sc) + pad * 2)
    H = max(16, int(dm * sc) + pad * 2)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer, "RGBA")
    ox, oy = W / 2, H / 2
    lw = max(1, int(0.016 * sc))

    def L(lx: float, ly: float) -> tuple[float, float]:
        return ox + lx * sc, oy + ly * sc

    def box(x0: float, y0: float, x1: float, y1: float) -> list[float]:
        a, b = L(x0, y0), L(x1, y1)
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]

    def rr(x0: float, y0: float, x1: float, y1: float, rad: float, fill: Any, outline: Any = None) -> None:
        _rrect(dr, box(x0, y0, x1, y1), max(1, rad * sc), fill=fill, outline=outline, width=lw)

    def ell(x: float, y: float, rx: float, ry: float, fill: Any, outline: Any = None) -> None:
        dr.ellipse(box(x - rx, y - ry, x + rx, y + ry), fill=fill, outline=outline, width=lw)

    ell(0.05, 0.06, wm * 0.5, dm * 0.46, (24, 18, 12, 55))
    paint(dr, L, rr, ell, lw)
    if abs(rot) > 0.4:
        layer = layer.rotate(-rot, expand=True, resample=Image.Resampling.BICUBIC)
    wx, wy = P(px, py)
    img.paste(layer, (int(round(wx - layer.width / 2)), int(round(wy - layer.height / 2))), layer)


def _draw_catalog_item(img: Image.Image, d: ImageDraw.ImageDraw, item: dict[str, Any], P: Any, sc: float) -> None:
    """Glyphe 2D réaliste (vue du dessus) pour une instance catalogue."""
    _ = d
    cid = str(item.get("catalog_id") or "")
    pos = item.get("position") or {}
    try:
        px, py = float(pos["x"]), float(pos["y"])
        w = float((item.get("size_m") or {}).get("w") or 0.5)
        dd = float((item.get("size_m") or {}).get("d") or 0.5)
        rot = float(item.get("rotation_deg") or 0)
    except (TypeError, ValueError, KeyError):
        return
    hx, hy = w / 2, dd / 2

    def bed(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        dark = cid.endswith("double") and w >= 1.4
        frame = (61, 46, 36) if dark else (196, 168, 130)
        linen = (62, 66, 72) if dark else (244, 239, 230)
        rr(-hx, -hy, hx, hy, 0.08, frame, (42, 30, 24) if dark else (138, 106, 72))
        rr(-hx + 0.04, -hy + 0.16, hx - 0.04, hy - 0.06, 0.07, linen, (42, 46, 50) if dark else (208, 198, 180))
        rr(-hx, -hy, hx, -hy + 0.16, 0.03, (36, 28, 24) if dark else (184, 154, 120), (42, 30, 24))
        pw, ph = w * 0.26, 0.26
        for sx in (-w * 0.22, w * 0.22):
            ell(sx, -hy + 0.38, pw, ph, (251, 248, 242), (212, 207, 196))
            ell(sx - 0.05, -hy + 0.34, pw * 0.4, ph * 0.35, (255, 255, 255, 90))
        rr(-hx + 0.08, hy - 0.46, hx - 0.08, hy - 0.14, 0.05,
           (74, 68, 64) if dark else (228, 212, 184), (46, 42, 40) if dark else (196, 176, 144))

    def sofa(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        fabric, dark, seat = (90, 94, 102), (58, 62, 68), (106, 110, 118)
        extra = 0.72 if cid == "sofa.lshape" else 0.0
        rr(-hx, -hy, hx, hy + extra, 0.12, fabric, (42, 46, 52))
        rr(-hx, -hy, hx, -hy + 0.2, 0.07, dark, (36, 40, 44))
        rr(-hx, -hy, -hx + 0.18, hy, 0.07, dark, (36, 40, 44))
        rr(hx - 0.18, -hy, hx, hy + extra, 0.07, dark, (36, 40, 44))
        seats = 3 if cid == "sofa.lshape" else 2
        inner = w - 0.4
        for i in range(seats):
            x0 = -hx + 0.22 + i * (inner / seats)
            rr(x0, -hy + 0.24, x0 + inner / seats - 0.04, hy - 0.08, 0.08, seat, (62, 66, 72))
        if cid == "sofa.lshape":
            rr(hx - 1.02, -hy, hx, hy + extra, 0.12, fabric, (42, 46, 52))
            rr(hx - 0.92, hy - 0.06, hx - 0.22, hy + extra - 0.08, 0.08, seat, (62, 66, 72))

    def armchair(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.14, (110, 74, 48), (58, 36, 20))
        rr(-hx, -hy, hx, -hy + 0.16, 0.06, (84, 54, 28), (58, 36, 20))
        rr(-hx, -hy, -hx + 0.12, hy, 0.05, (84, 54, 28), (58, 36, 20))
        rr(hx - 0.12, -hy, hx, hy, 0.05, (84, 54, 28), (58, 36, 20))
        ell(0, 0.06, w * 0.3, dd * 0.24, (138, 96, 64), (74, 48, 28))

    def table_dining(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        ell(0, 0, hx, hy, (138, 88, 40), (90, 52, 20))
        ell(0, 0, hx - 0.06, hy - 0.06, (196, 138, 72), (138, 90, 40))
        for k in (0.22, 0.42, 0.62):
            ell(0, 0, hx * k, hy * k, None, (90, 50, 18, 70))
        ell(-w * 0.14, -dd * 0.12, w * 0.18, dd * 0.08, (255, 230, 180, 50))

    def chair(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        ell(0, 0.06, w * 0.44, dd * 0.36, (236, 196, 74), (176, 138, 24))
        rr(-w * 0.36, -hy, w * 0.36, -hy + 0.11, 0.04, (212, 168, 46), (138, 106, 20))
        ell(-0.05, 0.0, w * 0.16, dd * 0.1, (255, 255, 220, 90))

    def coffee(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.08, (232, 228, 218), (184, 180, 170))
        rr(-hx + 0.05, -hy + 0.05, hx - 0.05, hy - 0.05, 0.05, (250, 248, 244), (212, 207, 198))
        ell(-w * 0.18, 0, 0.06, 0.06, (180, 80, 50, 90))
        ell(w * 0.12, 0.04, 0.045, 0.045, (40, 90, 140, 70))

    def counter(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.03, (236, 232, 224), (184, 180, 172))
        n = max(2, int(round(w / 0.55)))
        for i in range(1, n):
            x = -hx + (w * i) / n
            dr.line([L(x, -hy + 0.1), L(x, hy - 0.04)], fill=(160, 156, 148, 140), width=lw)
        # Petit évier encastré (carré), pas une cuve / baignoire.
        sw, sd = 0.32, min(0.28, max(0.18, dd * 0.42))
        sx = -w * 0.12
        rr(sx - sw / 2, -sd / 2, sx + sw / 2, sd / 2, 0.03, (214, 216, 218), (120, 124, 128))
        rr(sx - sw / 2 + 0.04, -sd / 2 + 0.04, sx + sw / 2 - 0.04, sd / 2 - 0.04, 0.02, (198, 202, 206), (140, 144, 148))
        ell(sx, -hy + 0.07, 0.028, 0.028, (138, 144, 150), (74, 80, 86))

    def stove(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.04, (42, 42, 44), (16, 16, 18))
        for ix, iy, r in ((-0.15, -0.13, 0.11), (0.15, -0.13, 0.09), (-0.15, 0.13, 0.09), (0.15, 0.13, 0.11)):
            ell(ix, iy, r, r, (22, 22, 24), (106, 106, 112))
            ell(ix, iy, r * 0.35, r * 0.35, (58, 58, 62), (138, 138, 144))

    def night(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.04, (122, 82, 48), (62, 42, 24))
        ell(0, -0.02, 0.075, 0.075, (240, 220, 156), (196, 160, 96))
        ell(0, -0.02, 0.035, 0.035, (255, 248, 210, 180))

    def wardrobe(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.03, (110, 78, 50), (58, 40, 24))
        dr.line([L(0, -hy + 0.04), L(0, hy - 0.04)], fill=(58, 40, 24), width=lw)
        ell(-0.09, 0, 0.028, 0.028, (208, 204, 196), (138, 134, 128))
        ell(0.09, 0, 0.028, 0.028, (208, 204, 196), (138, 134, 128))

    def desk(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.04, (62, 62, 66), (28, 28, 32))
        rr(w * 0.08, -dd * 0.16, w * 0.08 + 0.32, -dd * 0.16 + 0.22, 0.02, (22, 22, 26), (8, 8, 12))
        rr(w * 0.12, -dd * 0.12, w * 0.12 + 0.24, -dd * 0.12 + 0.14, 0.01, (30, 58, 82), (12, 28, 40))

    def fireplace(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.04, (74, 70, 68), (28, 26, 24))
        rr(-hx + 0.08, -hy + 0.1, hx - 0.08, hy - 0.1, 0.03, (42, 34, 32), (12, 8, 8))
        ell(0, hy - 0.22, 0.14, 0.09, (196, 74, 34))
        ell(0, hy - 0.26, 0.07, 0.06, (240, 192, 64))

    def bathtub(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rad = min(w, dd) * 0.32
        rr(-hx, -hy, hx, hy, rad, (246, 246, 244), (176, 176, 180))
        rr(-hx + 0.1, -hy + 0.1, hx - 0.1, hy - 0.1, rad * 0.8, (200, 221, 230), (138, 168, 180))
        ell(hx - 0.22, 0, 0.04, 0.04, (138, 142, 146), (90, 94, 98))

    def toilet(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, -hy + 0.2, 0.03, (242, 242, 240), (184, 184, 188))
        ell(0, 0.1, w * 0.44, dd * 0.38, (248, 248, 246), (184, 184, 188))
        ell(0, 0.12, w * 0.24, dd * 0.2, (220, 230, 234), (160, 168, 172))

    def sink(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        ell(0, 0.05, w * 0.44, dd * 0.4, (246, 246, 244), (184, 184, 188))
        ell(0, 0.07, w * 0.28, dd * 0.24, (208, 224, 230), (144, 164, 172))
        rr(-0.04, -hy, 0.04, -hy + 0.14, 0.02, (200, 204, 208), (138, 142, 146))

    def car(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx + 0.08, -hy, hx - 0.12, hy, 0.28, (236, 236, 234), (154, 154, 160))
        rr(-w * 0.16, -hy + 0.14, -w * 0.16 + w * 0.4, hy - 0.14, 0.14, (122, 160, 180), (74, 112, 132))
        for wx_, wy_ in ((-hx + 0.38, -hy - 0.04), (hx - 0.72, -hy - 0.04),
                         (-hx + 0.38, hy - 0.08), (hx - 0.72, hy - 0.08)):
            rr(wx_, wy_, wx_ + 0.38, wy_ + 0.12, 0.04, (28, 28, 30), (8, 8, 10))
        ell(-hx + 0.1, -dd * 0.22, 0.07, 0.05, (244, 232, 144))
        ell(-hx + 0.1, dd * 0.22, 0.07, 0.05, (244, 232, 144))
        ell(hx - 0.12, -dd * 0.2, 0.05, 0.04, (224, 112, 96))
        ell(hx - 0.12, dd * 0.2, 0.05, 0.04, (224, 112, 96))

    def rug(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.06, (196, 90, 58), (138, 56, 32))
        rr(-hx + 0.08, -hy + 0.08, hx - 0.08, hy - 0.08, 0.04, (212, 120, 76), (160, 72, 40))
        rr(-hx + 0.16, -hy + 0.16, hx - 0.16, hy - 0.16, 0.03, (255, 220, 180, 40))

    def plant(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        ell(0, 0.08, w * 0.28, dd * 0.22, (138, 90, 50), (90, 56, 24))
        for x, y, r, col in (
            (-0.08, -0.1, 0.16, (74, 138, 44)), (0.1, -0.12, 0.18, (46, 106, 28)),
            (0.0, -0.18, 0.14, (90, 154, 52)), (-0.12, 0.0, 0.12, (46, 106, 28)),
            (0.12, 0.02, 0.13, (74, 138, 44)),
        ):
            ell(x, y, r, r * 0.85, col, (30, 74, 16))

    def fridge(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.04, (232, 236, 238), (168, 176, 180))
        dr.line([L(-hx + 0.04, 0.02), L(hx - 0.04, 0.02)], fill=(176, 184, 188), width=lw)
        rr(hx - 0.1, -hy + 0.12, hx - 0.05, -hy + 0.3, 0.015, (200, 206, 210), (138, 144, 148))

    def tv(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.03, (58, 50, 44), (28, 24, 20))
        rr(-hx + 0.12, -hy + 0.04, hx - 0.12, -hy + 0.14, 0.015, (18, 20, 22), (8, 8, 10))

    def generic(dr: Any, L: Any, rr: Any, ell: Any, lw: int) -> None:
        rr(-hx, -hy, hx, hy, 0.06, (200, 184, 164), (106, 90, 72))

    painters = {
        "sofa.2seat": sofa, "sofa.lshape": sofa, "armchair": armchair,
        "table.dining": table_dining, "chair.dining": chair, "table.coffee": coffee,
        "counter.kitchen": counter, "stove": stove, "nightstand": night,
        "wardrobe": wardrobe, "desk": desk, "fireplace": fireplace,
        "bathtub": bathtub, "toilet": toilet, "sink.basin": sink, "sink": sink,
        "car.sedan": car, "rug.rect": rug, "plant.pot": plant, "fridge": fridge,
        "tv.console": tv,
    }
    painter = painters.get(cid, generic)
    if cid.startswith("bed."):
        painter = bed
    extra_d = dd + (0.75 if cid == "sofa.lshape" else 0.18)
    extra_w = w + (0.2 if cid == "car.sedan" else 0.14)
    _stamp(img, P, px, py, rot, extra_w, extra_d + 0.12, sc, painter)


def _furniture(d: ImageDraw.ImageDraw, typ: str, bx: tuple[float, float, float, float],
               P: Any, sc: float) -> None:
    """Mobilier de repli (sans catalogue) : mêmes couleurs que Sweet Home 3D."""
    m = 0.25
    x0, y0, x1, y1 = bx[0] + m, bx[1] + m, bx[2] - m, bx[3] - m
    w, h = x1 - x0, y1 - y0
    if w < 0.8 or h < 0.8:
        return
    lw = max(1, int(0.02 * sc))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def sh(a: float, b: float, c: float, e: float, rad: float = 0.12) -> None:
        _rrect(d, [P(a + 0.05, b + 0.07), P(c + 0.05, e + 0.07)], rad * sc, fill=_SHADOW)

    def rect(a: float, b: float, c: float, e: float, fill: Any = _FURN_FILL) -> None:
        d.rectangle([P(a, b), P(c, e)], fill=fill, outline=_FURN, width=lw)

    def rr(a: float, b: float, c: float, e: float, rad: float = 0.12, fill: Any = _FURN_FILL) -> None:
        _rrect(d, [P(a, b), P(c, e)], rad * sc, fill=fill, outline=_FURN, width=lw)

    def circ(a: float, b: float, rad: float, fill: Any = _FURN_FILL) -> None:
        d.ellipse([P(a - rad, b - rad), P(a + rad, b + rad)], fill=fill, outline=_FURN, width=lw)

    def line(a: float, b: float, c: float, e: float, fill: Any = _FURN) -> None:
        d.line([P(a, b), P(c, e)], fill=fill, width=lw)

    if typ == "bedroom":
        bw, bh = min(1.8, w - 0.7), min(2.05, h - 0.9)
        if bw < 1.2 or bh < 1.6:
            return
        xb0, xb1 = cx - bw / 2, cx + bw / 2
        if h - bh > 1.1:  # tapis au pied du lit
            rr(max(x0, xb0 - 0.45), y0 + bh - 0.5, min(x1, xb1 + 0.45),
               min(y1 - 0.1, y0 + bh + 0.7), 0.08, fill=_RUG)
        sh(xb0, y0, xb1, y0 + bh, 0.1)
        rr(xb0, y0, xb1, y0 + bh, 0.1)                        # lit
        rect(xb0, y0, xb1, y0 + 0.14, fill=(232, 233, 238))   # tête de lit
        pw = bw / 2 - 0.28
        rr(xb0 + 0.14, y0 + 0.2, xb0 + 0.14 + pw, y0 + 0.52, 0.06)   # oreillers
        rr(xb1 - 0.14 - pw, y0 + 0.2, xb1 - 0.14, y0 + 0.52, 0.06)
        line(xb0 + 0.08, y0 + bh * 0.58, xb1 - 0.08, y0 + bh * 0.58)  # pli de couette
        rect(xb0 + 0.06, y0 + bh - 0.48, xb1 - 0.06, y0 + bh - 0.08, fill=(238, 231, 219))  # jeté
        for s in (-1, 1):  # tables de nuit + lampes
            nx0 = xb0 - 0.62 if s < 0 else xb1 + 0.12
            if nx0 >= x0 - 0.01 and nx0 + 0.5 <= x1 + 0.26:
                rect(nx0, y0, nx0 + 0.5, y0 + 0.42)
                circ(nx0 + 0.25, y0 + 0.21, 0.09)
        if h - bh > 1.0:  # penderie sur le mur du fond
            wr = min(w, 2.4)
            rect(x0, y1 - 0.62, x0 + wr, y1, fill=_FURN_SOFT)
            xx = x0 + 0.6
            while xx < x0 + wr - 0.15:
                line(xx, y1 - 0.62, xx, y1)
                circ(xx - 0.11, y1 - 0.31, 0.035, fill=_FURN)
                xx += 0.6
    elif typ == "living":
        if w >= h:  # canapé contre le mur du fond, TV sur le mur d'en face
            sw = min(2.4, w - 0.9)
            if sw < 1.2:
                return
            sx0, sx1 = x0 + 0.35, x0 + 0.35 + sw
            sy0, sy1 = y1 - 0.98, y1 - 0.03
            rr(sx0, max(y0 + 0.55, sy0 - 1.35), sx1 + 0.2, sy0 - 0.25, 0.1, fill=_RUG)
            rect(x0 + 0.4, y0, x0 + 2.0, y0 + 0.38, fill=_FURN_SOFT)   # meuble TV
            rect(x0 + 0.58, y0 + 0.04, x0 + 1.82, y0 + 0.22, fill=(58, 61, 68))
            sh(sx0, sy0, sx1, sy1, 0.16)
            rr(sx0, sy0, sx1, sy1, 0.16, fill=(72, 74, 78))                    # canapé
            rect(sx0, sy0, sx0 + 0.24, sy1, fill=(88, 90, 94))  # accoudoirs
            rect(sx1 - 0.24, sy0, sx1, sy1, fill=(88, 90, 94))
            line(sx0 + 0.24, sy0 + 0.3, sx1 - 0.24, sy0 + 0.3)  # dossier
            n = max(2, int(sw // 0.8))
            for i in range(1, n):                            # coussins
                xx = sx0 + 0.24 + (sw - 0.48) * i / n
                line(xx, sy0 + 0.3, xx, sy1)
            sh(cx - 0.42, cy - 0.62, cx + 0.42, cy - 0.28, 0.06)
            rr(cx - 0.42, cy - 0.62, cx + 0.42, cy - 0.28, 0.06, fill=(248, 248, 246))  # table basse
            rect(cx - 0.32, cy + 0.15, cx + 0.32, cy + 0.85, fill=(28, 28, 30))  # cheminée
            # deux fauteuils, jamais une table à manger
            rr(cx - 1.45, cy - 0.55, cx - 0.62, cy + 0.22, 0.14, fill=(92, 62, 42))
            line(cx - 1.32, cy - 0.55, cx - 1.32, cy + 0.22)
            rr(cx + 0.62, cy - 0.55, cx + 1.45, cy + 0.22, 0.14, fill=(92, 62, 42))
            line(cx + 1.32, cy - 0.55, cx + 1.32, cy + 0.22)
            circ(x1 - 0.38, y0 + 0.75, 0.3, fill=_PLANT)    # plante
            circ(x1 - 0.38, y0 + 0.75, 0.16, fill=_PLANT_IN)
        else:  # pièce en hauteur : canapé contre le mur gauche
            sd = min(2.4, h - 0.9)
            if sd < 1.2:
                return
            sy0, sy1 = y0 + 0.35, y0 + 0.35 + sd
            sx0, sx1 = x0 + 0.03, x0 + 0.98
            rr(sx1 + 0.25, sy0, min(x1, sx1 + 1.6), sy1, 0.1, fill=_RUG)
            rect(x1 - 0.38, y0 + 0.4, x1, y0 + 2.0, fill=_FURN_SOFT)
            rect(x1 - 0.22, y0 + 0.58, x1 - 0.04, y0 + 1.82, fill=(58, 61, 68))
            sh(sx0, sy0, sx1, sy1, 0.16)
            rr(sx0, sy0, sx1, sy1, 0.16, fill=(72, 74, 78))
            rect(sx0, sy0, sx1, sy0 + 0.24, fill=(88, 90, 94))
            rect(sx0, sy1 - 0.24, sx1, sy1, fill=(88, 90, 94))
            line(sx0 + 0.3, sy0 + 0.24, sx0 + 0.3, sy1 - 0.24)
            n = max(2, int(sd // 0.8))
            for i in range(1, n):
                yy = sy0 + 0.24 + (sd - 0.48) * i / n
                line(sx0 + 0.3, yy, sx1, yy)
            rr(cx + 0.08, cy - 0.38, cx + 0.52, cy + 0.38, 0.06, fill=(248, 248, 246))  # table basse
            rr(cx - 0.95, cy - 0.95, cx - 0.18, cy - 0.18, 0.14, fill=(92, 62, 42))
            line(cx - 0.82, cy - 0.95, cx - 0.18, cy - 0.95)
            rr(cx - 0.95, cy + 0.18, cx - 0.18, cy + 0.95, 0.14, fill=(92, 62, 42))
            line(cx - 0.82, cy + 0.18, cx - 0.18, cy + 0.18)
            circ(x1 - 0.42, y1 - 0.55, 0.3, fill=_PLANT)
            circ(x1 - 0.42, y1 - 0.55, 0.16, fill=_PLANT_IN)
    elif typ == "kitchen":
        rect(x0, y0, x1, y0 + 0.62)                          # plan de travail
        line(x0, y0 + 0.62, x1, y0 + 0.62)
        if h > 2.4:                                          # retour en L
            rect(x0, y0, x0 + 0.62, y0 + min(h - 0.6, 3.4))
            line(x0 + 0.62, y0, x0 + 0.62, y0 + min(h - 0.6, 3.4))
        rect(x1 - 0.68, y0 + 0.03, x1 - 0.04, y0 + 0.59, fill=_FURN_SOFT)  # frigo
        line(x1 - 0.68, y0 + 0.31, x1 - 0.04, y0 + 0.31)
        ex = x0 + 0.85                                        # petit évier encastré, pas une cuve
        if ex + 0.55 < x1 - 0.75:
            rect(ex, y0 + 0.14, ex + 0.38, y0 + 0.46, fill=(214, 216, 218))
            rect(ex + 0.05, y0 + 0.18, ex + 0.33, y0 + 0.42, fill=(198, 202, 206))
            circ(ex + 0.19, y0 + 0.10, 0.035, fill=_FURN)
        px = min(x0 + max(2.1, w * 0.45), x1 - 1.75)         # plaques 4 foyers
        if px > x0 and px + 0.75 < x1 - 0.75:
            for i in range(2):
                for j in range(2):
                    circ(px + 0.2 + i * 0.32, y0 + 0.17 + j * 0.28, 0.085 if (i + j) % 2 else 0.115)
    elif typ == "dining":
        tw, th = min(1.9, w - 1.7), min(1.05, h - 1.7)
        if tw < 1.0 or th < 0.75:
            return
        tx0, ty0, tx1, ty1 = cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2
        sh(tx0, ty0, tx1, ty1, 0.06)
        rr(tx0, ty0, tx1, ty1, 0.06, fill=(168, 118, 64))                         # table
        rect(tx0 + 0.12, ty0 + 0.12, tx1 - 0.12, ty1 - 0.12, fill=(184, 132, 74))
        yellow = (232, 196, 64)
        for fx in (-tw / 4, tw / 4):                         # 6 chaises
            rr(cx + fx - 0.21, ty0 - 0.6, cx + fx + 0.21, ty0 - 0.16, 0.08, fill=yellow)
            rr(cx + fx - 0.21, ty1 + 0.16, cx + fx + 0.21, ty1 + 0.6, 0.08, fill=yellow)
        rr(tx0 - 0.6, cy - 0.21, tx0 - 0.16, cy + 0.21, 0.08, fill=yellow)
        rr(tx1 + 0.16, cy - 0.21, tx1 + 0.6, cy + 0.21, 0.08, fill=yellow)
        if h - th > 2.0:                                     # buffet
            rect(x0, y1 - 0.48, x0 + min(1.9, w * 0.45), y1, fill=_FURN_SOFT)
    elif typ in ("bathroom", "wc"):
        txx = x0 + 0.08                                       # WC : réservoir + cuvette bien lisible
        tw = min(0.55, max(0.42, w * 0.35))
        rect(txx, y0 + 0.04, txx + tw, y0 + 0.28, fill=(248, 248, 246))
        d.ellipse(
            [P(txx - 0.04, y0 + 0.22), P(txx + tw + 0.04, y0 + 0.95)],
            fill=_FURN_FILL, outline=_FURN, width=max(lw, 2),
        )
        d.ellipse(
            [P(txx + 0.08, y0 + 0.36), P(txx + tw - 0.08, y0 + 0.82)],
            outline=_FURN, width=max(lw, 2),
        )
        if typ == "wc":
            circ(x1 - min(0.32, w * 0.22), y0 + 0.32, min(0.2, w * 0.14))
            return
        bw_ = min(1.75, w - 0.85)
        if bw_ >= 1.2 and h >= 1.9:                          # baignoire
            bx0 = x0 + 0.72
            sh(bx0, y1 - 0.85, bx0 + bw_, y1 - 0.05, 0.2)
            rr(bx0, y1 - 0.85, bx0 + bw_, y1 - 0.05, 0.2)
            rr(bx0 + 0.15, y1 - 0.7, bx0 + bw_ - 0.15, y1 - 0.2, 0.13, fill=_FURN_SOFT)
            circ(bx0 + bw_ - 0.22, y1 - 0.45, 0.05, fill=_FURN)   # bonde
            circ(bx0 + 0.14, y1 - 0.45, 0.045, fill=_FURN)        # robinet
        if w >= 1.9:                                         # meuble vasque
            rect(x1 - 0.58, y0 + 0.02, x1 - 0.02, y0 + 0.62)
            circ(x1 - 0.3, y0 + 0.32, 0.16)
    elif typ == "office":
        dw_ = min(1.7, w - 0.5)
        sh(x0, y0, x0 + dw_, y0 + 0.7, 0.04)
        rect(x0, y0, x0 + dw_, y0 + 0.7)                     # bureau
        line(x0 + 0.15, y0 + 0.35, x0 + dw_ - 0.15, y0 + 0.35)
        ax_ = x0 + min(0.9, dw_ / 2)
        circ(ax_, y0 + 1.14, 0.26)                           # fauteuil
        line(ax_ - 0.19, y0 + 0.94, ax_ + 0.19, y0 + 0.94)
        if w >= 2.3:                                         # bibliothèque
            hh = min(1.8, h - 0.8)
            rect(x1 - 0.38, y0, x1, y0 + hh, fill=_FURN_SOFT)
            yy = y0 + 0.45
            while yy < y0 + hh - 0.15:
                line(x1 - 0.38, yy, x1, yy)
                yy += 0.45
        if h > 2.2:
            circ(x1 - 0.45, y1 - 0.5, 0.28, fill=_PLANT)
    elif typ == "garage":
        cw_, ch_ = min(4.6, w - 0.6), min(1.95, h - 0.7)
        if cw_ < 3.0 or ch_ < 1.35:
            return
        gx0, gy0, gx1, gy1 = cx - cw_ / 2, cy - ch_ / 2, cx + cw_ / 2, cy + ch_ / 2
        sh(gx0, gy0, gx1, gy1, 0.42)
        rr(gx0, gy0, gx1, gy1, 0.42)                         # voiture
        rr(gx0 + cw_ * 0.3, gy0 + 0.12, gx0 + cw_ * 0.64, gy1 - 0.12, 0.18)  # pavillon
        line(gx0 + cw_ * 0.3, gy0 + 0.12, gx0 + cw_ * 0.22, gy0 + 0.02)      # pare-brise
        line(gx0 + cw_ * 0.3, gy1 - 0.12, gx0 + cw_ * 0.22, gy1 - 0.02)
        line(gx0 + cw_ * 0.64, gy0 + 0.12, gx0 + cw_ * 0.72, gy0 + 0.02)     # lunette arrière
        line(gx0 + cw_ * 0.64, gy1 - 0.12, gx0 + cw_ * 0.72, gy1 - 0.02)
        for wx_ in (gx0 + cw_ * 0.15, gx0 + cw_ * 0.73):     # roues
            d.rectangle([P(wx_, gy0 - 0.1), P(wx_ + 0.32, gy0 + 0.07)], fill=(70, 72, 78))
            d.rectangle([P(wx_, gy1 - 0.07), P(wx_ + 0.32, gy1 + 0.1)], fill=(70, 72, 78))
    elif typ == "laundry":
        for i in range(2):                                   # machines hublot
            mx = x0 + i * 0.72
            if mx + 0.66 > x1:
                break
            rect(mx, y0, mx + 0.66, y0 + 0.68)
            circ(mx + 0.33, y0 + 0.4, 0.2)
            rect(mx + 0.1, y0 + 0.05, mx + 0.34, y0 + 0.12, fill=_FURN_SOFT)
    elif typ == "storage":
        sw_ = min(w, 2.2)
        rect(x0, y0, x0 + sw_, y0 + 0.42, fill=_FURN_SOFT)   # étagères
        xx = x0 + 0.55
        while xx < x0 + sw_ - 0.1:
            line(xx, y0, xx, y0 + 0.42)
            xx += 0.55
        if w > 1.6 and h > 1.4:                              # cartons
            rr(x1 - 0.75, y1 - 0.75, x1 - 0.25, y1 - 0.25, 0.05)
            rr(x1 - 1.25, y1 - 0.6, x1 - 0.85, y1 - 0.2, 0.05)
    elif typ == "hallway":
        if w > 2.4:
            rr(x0 + 0.3, cy - 0.38, x1 - 0.3, cy + 0.38, 0.1, fill=_RUG)  # tapis de couloir
        if w >= 2.2:
            rect(x0, y0, x0 + min(1.2, w * 0.4), y0 + 0.34, fill=_FURN_SOFT)  # console


def _room_caption(d: ImageDraw.ImageDraw, box: tuple[float, float, float, float], name: str, area: Any, sc: float) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    avail = (x1 - x0) - 10 * _SS
    disp = name
    fs = int(min(max(11 * _SS, (x1 - x0) * 0.22), 30 * _SS))
    while fs > 9 * _SS:
        f = _room_font(fs)
        if d.textlength(disp, font=f) <= avail:
            break
        fs -= _SS
    f = _room_font(fs)
    sub = f"{float(area):.0f} m²" if area else ""
    fsub = _room_font(max(8 * _SS, int(fs * 0.62)))
    oy = -fs * 0.42 if sub else 0
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):  # halo blanc pour lisibilité
        d.text((cx + dx, cy + oy + dy), disp, font=f, fill=(255, 255, 255, 235), anchor="mm")
    d.text((cx, cy + oy), disp, font=f, fill=(38, 38, 42), anchor="mm")
    if sub:
        d.text((cx, cy + oy + fs * 0.92), sub, font=fsub, fill=(122, 122, 128), anchor="mm")


def _edges_m(poly: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    xs = [p["x"] for p in poly]
    ys = [p["y"] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _shared_seg(a: tuple, b: tuple) -> tuple[str, float, float, float] | None:
    """Segment de mur commun entre deux rectangles (métres) : ('v'|'h', coord, lo, hi)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    e = 0.08
    if abs(ax1 - bx0) < e or abs(bx1 - ax0) < e:
        lo, hi = max(ay0, by0), min(ay1, by1)
        if hi - lo > 0.8:
            return "v", (ax1 if abs(ax1 - bx0) < e else ax0), lo, hi
    if abs(ay1 - by0) < e or abs(by1 - ay0) < e:
        lo, hi = max(ax0, bx0), min(ax1, bx1)
        if hi - lo > 0.8:
            return "h", (ay1 if abs(ay1 - by0) < e else ay0), lo, hi
    return None


def _door(d: ImageDraw.ImageDraw, seg: tuple[str, float, float, float], P: Any, sc: float) -> None:
    orient, coord, lo, hi = seg
    dw = min(0.9, (hi - lo) - 0.3)
    if dw < 0.6:
        return
    s = (lo + hi) / 2 - dw / 2
    gap = max(3, int(0.2 * sc))
    lw = max(1, int(0.022 * sc))
    leaf = max(2, int(0.045 * sc))
    hinge_r = max(1, int(0.03 * sc))
    if orient == "v":
        hx, hy = P(coord, s)
        d.line([P(coord, s), P(coord, s + dw)], fill=(255, 255, 255), width=gap)
        d.line([P(coord, s), P(coord + dw, s)], fill=_WALL_LIGHT, width=leaf)
        d.arc([P(coord - dw, s - dw), P(coord + dw, s + dw)], 0, 90, fill=(158, 162, 170), width=lw)
        d.ellipse([hx - hinge_r, hy - hinge_r, hx + hinge_r, hy + hinge_r], fill=_WALL_LIGHT)
    else:
        hx, hy = P(s, coord)
        d.line([P(s, coord), P(s + dw, coord)], fill=(255, 255, 255), width=gap)
        d.line([P(s, coord), P(s, coord + dw)], fill=_WALL_LIGHT, width=leaf)
        d.arc([P(s - dw, coord - dw), P(s + dw, coord + dw)], 0, 90, fill=(158, 162, 170), width=lw)
        d.ellipse([hx - hinge_r, hy - hinge_r, hx + hinge_r, hy + hinge_r], fill=_WALL_LIGHT)


def _windows(d: ImageDraw.ImageDraw, box: tuple, typ: str, width: float, depth: float, P: Any, sc: float) -> None:
    x0, y0, x1, y1 = box
    e = 0.12
    edges = []
    if x0 <= e:
        edges.append(("v", 0.0, y0, y1))
    if x1 >= width - e:
        edges.append(("v", width, y0, y1))
    if y0 <= e:
        edges.append(("h", 0.0, x0, x1))
    if y1 >= depth - e:
        edges.append(("h", depth, x0, x1))
    for orient, coord, lo, hi in edges:
        span = hi - lo
        if span < 1.3:
            continue
        ww = 2.4 if typ == "garage" else (0.7 if typ in ("bathroom", "wc", "storage", "laundry") else 1.3)
        ww = min(ww, span - 0.6)
        c = (lo + hi) / 2
        a, b = c - ww / 2, c + ww / 2
        th = max(3, int(0.2 * sc))
        off = 0.055
        lw = max(1, int(0.018 * sc))
        if orient == "v":
            d.line([P(coord, a), P(coord, b)], fill=(255, 255, 255), width=th)
            for oc in (coord - off, coord + off):
                d.line([P(oc, a), P(oc, b)], fill=(110, 114, 122), width=lw)
            d.line([P(coord, a), P(coord, b)], fill=(168, 196, 218), width=lw)
        else:
            d.line([P(a, coord), P(b, coord)], fill=(255, 255, 255), width=th)
            for oc in (coord - off, coord + off):
                d.line([P(a, oc), P(b, oc)], fill=(110, 114, 122), width=lw)
            d.line([P(a, coord), P(b, coord)], fill=(168, 196, 218), width=lw)


def _render_floorplan(
    rooms: list[dict[str, Any]], walls: list[dict[str, Any]], openings: list[dict[str, Any]],
    width: float, depth: float, veranda_depth: float = 0.0, annotate: bool = False,
    furniture: list[dict[str, Any]] | None = None,
) -> str:
    """Rendu vectoriel style Sweet Home 3D : sols, mobilier texturé, jardin, porche sud."""
    width = max(1.0, float(width))
    depth = max(1.0, float(depth))
    base_scale = max(24.0, min(900.0 / width, 600.0 / depth))
    sc = base_scale * _SS
    pad_l, pad_r, pad_t0, pad_b = 88 * _SS, 110 * _SS, 48 * _SS, 150 * _SS
    vpx = int(round(veranda_depth * sc)) if veranda_depth and veranda_depth > 0 else 0
    pad_t = pad_t0 + vpx
    ox, oy = pad_l, pad_t
    cw = int(width * sc) + pad_l + pad_r
    ch = int(depth * sc) + pad_t + pad_b

    img = Image.new("RGB", (cw, ch), _PAGE_BG)
    d = ImageDraw.Draw(img, "RGBA")

    def P(mx: float, my: float) -> tuple[float, float]:
        return ox + mx * sc, oy + my * sc

    def X(mx: float) -> float:
        return ox + mx * sc

    def Y(my: float) -> float:
        return oy + my * sc

    hx0, hy0, hx1, hy1 = X(0), Y(0), X(width), Y(depth)
    ew = max(7, int(0.32 * sc))   # mur extérieur
    iw = max(5, int(0.18 * sc))   # cloison

    # Jardin L (sud + est) façon Sweet Home 3D
    d.rectangle([0, 0, cw, ch], fill=_GRASS)
    for i in range(280):
        gx = int((i * 73 + 19) % max(1, cw))
        gy = int((i * 47 + 31) % max(1, ch))
        rx = max(3, int(0.12 * sc + (i % 5)))
        col = _GRASS_DARK if i % 2 else (148, 186, 78)
        d.ellipse([gx - rx, gy - int(rx * 0.7), gx + rx, gy + int(rx * 0.7)], fill=(*col, 90))

    def _tree(mx: float, my: float, r: float) -> None:
        cx_, cy_ = P(mx, my)
        rr = r * sc
        d.ellipse([cx_ - rr + 3, cy_ - rr + 4, cx_ + rr + 3, cy_ + rr + 4], fill=(30, 50, 16, 50))
        d.ellipse([cx_ - rr, cy_ - rr, cx_ + rr, cy_ + rr], fill=(58, 106, 34))
        d.ellipse([cx_ - rr * 0.45, cy_ - rr * 0.55, cx_ + rr * 0.35, cy_ + rr * 0.15], fill=(90, 148, 52))
        d.ellipse([cx_ - rr * 0.18, cy_ - rr * 0.18, cx_ + rr * 0.18, cy_ + rr * 0.18], fill=(106, 74, 40))

    _tree(width + 0.85, depth * 0.28, 0.55)
    _tree(width + 1.15, depth * 0.62, 0.7)
    _tree(width * 0.22, depth + 1.05, 0.5)
    _tree(width * 0.55, depth + 1.2, 0.65)
    _tree(width * 0.85, depth + 0.95, 0.45)
    hedge = max(4, int(0.12 * sc))
    d.line([P(width + 0.25, 0.15), P(width + 0.25, depth + 0.2)], fill=(70, 110, 40), width=hedge)
    d.line([P(0.1, depth + 0.25), P(width + 0.25, depth + 0.25)], fill=(70, 110, 40), width=hedge)
    if annotate:
        d.text((hx1 + (cw - hx1) / 2, (hy0 + hy1) / 2), "Jardin", fill=(62, 92, 40),
               font=_room_font(13 * _SS), anchor="mm")
        d.text(((hx0 + hx1) / 2, hy1 + 52 * _SS), "Jardin", fill=(62, 92, 40),
               font=_room_font(13 * _SS), anchor="mm")

    if vpx:
        d.rectangle([hx0 - ew // 2, hy0 - vpx, hx1 + ew // 2, hy0], fill=(216, 199, 172), outline=(122, 108, 84), width=max(2, _SS))
        for gx in range(int(hx0), int(hx1), int(0.5 * sc) or 12):
            d.line([(gx, hy0 - vpx + 5), (gx, hy0 - 5)], fill=(150, 133, 107, 130), width=max(1, _SS))

    d.rectangle([hx0, hy0, hx1, hy1], fill=(255, 255, 255))

    boxes = []
    for room in rooms:
        poly = room.get("polygon") or []
        if len(poly) < 3:
            continue
        bm = _edges_m(poly)
        boxes.append((room, bm))
        _floor_texture(d, str(room.get("type") or ""), bm, P, sc)

    items = furniture or []
    if items:
        ordered = sorted(items, key=lambda it: 0 if str(it.get("catalog_id") or "").startswith("rug") else 1)
        for it in ordered:
            _draw_catalog_item(img, d, it, P, sc)
    else:
        for room, bm in boxes:
            _furniture(d, str(room.get("type") or ""), bm, P, sc)

    # cloisons : arêtes internes des pièces
    seen: set = set()
    for _, bm in boxes:
        x0, y0, x1, y1 = bm
        for seg in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            (a, b) = seg
            if abs(a[0] - b[0]) < 0.02 and (a[0] <= 0.05 or a[0] >= width - 0.05):
                continue
            if abs(a[1] - b[1]) < 0.02 and (a[1] <= 0.05 or a[1] >= depth - 0.05):
                continue
            key = tuple(sorted([(round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2))]))
            if key in seen:
                continue
            seen.add(key)
            d.line([P(*a), P(*b)], fill=_WALL_DARK, width=iw)
            d.line([P(*a), P(*b)], fill=(154, 154, 148), width=max(2, iw - 3))

    # portes : une par pièce, vers un couloir sinon vers la plus grande voisine
    halls = [(r, bm) for r, bm in boxes if str(r.get("type")) == "hallway"]
    for room, bm in boxes:
        if str(room.get("type")) == "hallway":
            continue
        target = None
        for _, hbm in halls:
            target = _shared_seg(bm, hbm)
            if target:
                break
        if not target:
            best = 0.0
            for other, obm in boxes:
                if other is room:
                    continue
                s = _shared_seg(bm, obm)
                if s and (s[3] - s[2]) > best:
                    best, target = s[3] - s[2], s
        if target:
            _door(d, target, P, sc)
    for _hall, bm in halls:  # relie le couloir à la façade sud (entrée)
        if bm[3] >= depth - 0.15:
            _door(d, ("h", depth, bm[0], bm[2]), P, sc)

    for room, bm in boxes:
        _windows(d, bm, str(room.get("type") or ""), width, depth, P, sc)

    # mur extérieur (poché gris épais)
    d.rectangle([hx0, hy0, hx1, hy1], outline=_WALL_DARK, width=ew)

    # porte d'entrée SUD + porche bois
    lw2 = max(1, int(0.022 * sc))
    entry_x = None
    entry_w = 0.9
    for op in openings or []:
        if op.get("type") == "door" and str(op.get("wall_id")) in {"w_outer_3", "w_outer_1"}:
            try:
                off = float(op.get("offset_m") or width * 0.42)
                dw_ = float(op.get("width_m") or 0.9)
            except (TypeError, ValueError):
                continue
            a = max(0.1, min(width - dw_ - 0.1, off))
            ydoor = depth if str(op.get("wall_id")) == "w_outer_3" else 0.0
            d.line([P(a, ydoor), P(a + dw_, ydoor)], fill=(255, 255, 255), width=ew + 2)
            leaf = 1.0 if ydoor > 0 else -1.0
            d.line([P(a, ydoor), P(a, ydoor - leaf * dw_)], fill=_DOOR, width=max(2, int(0.045 * sc)))
            if ydoor > 0:
                d.arc([P(a - dw_, ydoor - dw_), P(a + dw_, ydoor + dw_)], 180, 270, fill=_DOOR, width=lw2)
                entry_x, entry_w = a, dw_
            else:
                d.arc([P(a - dw_, -dw_), P(a + dw_, dw_)], 0, 90, fill=_DOOR, width=lw2)
            break
    if entry_x is not None:
        px0, px1 = entry_x - 0.35, entry_x + entry_w + 0.35
        d.rectangle([P(px0, depth), P(px1, depth + 1.15)], fill=_PORCH, outline=_PORCH_LINE, width=max(1, _SS))
        step = 0.18
        yy = depth
        while yy < depth + 1.15:
            d.line([P(px0, yy), P(px1, yy)], fill=_PORCH_LINE, width=max(1, _SS))
            yy += step
        if annotate:
            ax_, ay_ = X(entry_x + entry_w / 2), Y(depth) + 28 * _SS
            d.text((ax_, ay_), "Entrée", fill=_TEXT_SOFT, font=_room_font(10 * _SS), anchor="mm")

    if annotate:
        for room, bm in boxes:
            area = float(room.get("area_m2") or 0)
            if area <= 0:
                area = max(0.0, (bm[2] - bm[0]) * (bm[3] - bm[1]))
            _room_caption(d, (X(bm[0]), Y(bm[1]), X(bm[2]), Y(bm[3])), str(room.get("name") or ""), area, sc)

    # cotes avec lignes d'attache et ticks à 45°
    if annotate:
        dimf = _room_font(12 * _SS)
        dg = (150, 150, 154)
        yy = hy0 - vpx - 34 * _SS
        for xx in (hx0, hx1):
            d.line([(xx, hy0 - vpx - 8 * _SS), (xx, yy + 5 * _SS)], fill=dg, width=max(1, _SS))
            d.line([(xx - 4 * _SS, yy + 4 * _SS), (xx + 4 * _SS, yy - 4 * _SS)], fill=dg, width=max(1, _SS))
        d.line([(hx0, yy), (hx1, yy)], fill=dg, width=max(1, _SS))
        d.text(((hx0 + hx1) / 2, yy - 11 * _SS), f"{width:.1f} m", fill=(104, 104, 108), font=dimf, anchor="mm")
        xx = hx0 - 26 * _SS
        for yv in (hy0, hy1):
            d.line([(hx0 - 8 * _SS, yv), (xx + 5 * _SS, yv)], fill=dg, width=max(1, _SS))
            d.line([(xx - 4 * _SS, yv - 4 * _SS), (xx + 4 * _SS, yv + 4 * _SS)], fill=dg, width=max(1, _SS))
        d.line([(xx, hy0), (xx, hy1)], fill=dg, width=max(1, _SS))
        d.text((xx - 9 * _SS, (hy0 + hy1) / 2), f"{depth:.1f} m", fill=(104, 104, 108), font=dimf, anchor="rm")

    # cartouche : titre, surface, échelle, boussole (sous le jardin sud)
    fb = hy1 + 78 * _SS
    if annotate:
        d.line([(hx0, fb), (hx1, fb)], fill=(208, 203, 193), width=max(1, _SS))
        area = 0.0
        for r, bm in boxes:
            if str(r.get("type") or "") in {"garage", "storage"}:
                continue
            a = float(r.get("area_m2") or 0)
            if a <= 0:
                a = max(0.0, (bm[2] - bm[0]) * (bm[3] - bm[1]))
            area += a
        d.text((hx0, fb + 16 * _SS), "PLAN DU REZ-DE-CHAUSSÉE", fill=_TEXT, font=_room_font(15 * _SS), anchor="lm")
        d.text((hx0, fb + 36 * _SS), f"{width:.1f} × {depth:.1f} m  —  Surface habitable ≈ {area:.0f} m²",
               fill=_TEXT_SOFT, font=_room_font(11 * _SS), anchor="lm")
        sbx0, sbx1 = hx1 - sc - 34 * _SS, hx1 - 34 * _SS
        sby = fb + 26 * _SS
        d.line([(sbx0, sby), (sbx1, sby)], fill=_TEXT_SOFT, width=max(2, _SS))
        for t in (sbx0, sbx1):
            d.line([(t, sby - 4 * _SS), (t, sby + 4 * _SS)], fill=_TEXT_SOFT, width=max(1, _SS))
        d.text(((sbx0 + sbx1) / 2, sby - 9 * _SS), "1 m", fill=_TEXT_SOFT, font=_room_font(10 * _SS), anchor="mm")
        nx, ny = hx1 - 12 * _SS, fb + 26 * _SS
        d.ellipse([nx - 10 * _SS, ny - 10 * _SS, nx + 10 * _SS, ny + 10 * _SS], outline=_TEXT_SOFT, width=max(1, _SS))
        d.polygon([(nx - 3.5 * _SS, ny + 4 * _SS), (nx + 3.5 * _SS, ny + 4 * _SS), (nx, ny - 6 * _SS)], fill=_TEXT)
        d.text((nx, ny - 15 * _SS), "N", fill=_TEXT_SOFT, font=_room_font(10 * _SS), anchor="mm")

    out = img.resize((cw // _SS, ch // _SS), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _overlay_room_labels(
    png_b64: str, rooms: list[dict[str, Any]], width: float, depth: float
) -> str:
    """Pose les libellés canoniques sur une image (FLUX) pour éviter les fautes du modèle."""
    try:
        raw = base64.b64decode(png_b64)
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:  # noqa: BLE001
        return png_b64
    d = ImageDraw.Draw(img, "RGBA")
    iw, ih = img.size
    mx, my = max(width, 0.1), max(depth, 0.1)
    pad = min(iw, ih) * 0.06

    def P(mx0: float, my0: float) -> tuple[float, float]:
        return pad + mx0 / mx * (iw - 2 * pad), pad + my0 / my * (ih - 2 * pad)

    for room in rooms:
        poly = room.get("polygon") or []
        if len(poly) < 3:
            continue
        x0, y0, x1, y1 = _edges_m(poly)
        name = str(room.get("name") or "")
        if not name:
            continue
        bx = (P(x0, y0)[0], P(x0, y0)[1], P(x1, y1)[0], P(x1, y1)[1])
        _room_caption(d, bx, name, None, max(1.0, (iw / 900) * 2))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


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
    """"Séjour" -> "SEJOUR" : FLUX lettre bien l'ASCII court, mal les accents français."""
    norm = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in norm if not unicodedata.combining(c)).upper().strip()


def _footprint_zone(poly: list[dict[str, Any]], width: float, depth: float) -> str:
    """Situe le centroïde d'une pièce dans l'emprise (front = côté entrée, y=0)."""
    if not poly or width <= 0 or depth <= 0:
        return ""
    cx = sum(float(p["x"]) for p in poly) / len(poly)
    cy = sum(float(p["y"]) for p in poly) / len(poly)
    horiz = "left" if cx / width < 0.34 else ("right" if cx / width > 0.66 else "centre")
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
        return " Keep every room empty with no lettering, numbers or labels of any kind."
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
    "toilet", "toilets", "wc", "loo", "bidet",
    "bathtub", "bath tub", "tub", "shower", "shower tray",
    "washbasin", "wash basin", "bathroom sink", "lavatory",
)
_FURN_FORBIDDEN = {
    "living": (
        "bed", "bathtub", "bath tub", "tub", "shower", "toilet", "bidet",
        "washbasin", "wash basin", "stove", "hob", "cooktop", "fridge", "car", "sink",
        "dining table", "dining",
    ),
    "kitchen": (
        "bed", "sofa", "armchair", "bathtub", "bath tub", "tub", "shower", "toilet",
        "bidet", "car", "wardrobe", "dining table", "dining", "cuve",
    ),
    "bedroom": (
        "stove", "hob", "cooktop", "fridge", "sofa", "armchair", "dining table",
        "car", "sink", *_BATH_FIXTURES,
    ),
    "bathroom": ("bed", "sofa", "fridge", "stove", "hob", "car", "dining", "wardrobe"),
    "garage": ("bed", "sofa", "bathtub", "toilet", "shower", "stove", "wardrobe"),
    "hallway": ("bed", "bathtub", "toilet", "shower", "car", "stove", "fridge"),
    "dining": ("bed", "bathtub", "bath tub", "tub", "shower", "toilet", "bidet", "washbasin", "car", "stove", "fridge"),
    "office": ("bed", "bathtub", "toilet", "shower", "car", "stove", "fridge", "sink"),
    "wc": ("bed", "sofa", "car", "stove", "fridge", "wardrobe"),
    "laundry": ("bed", "sofa", "car", "toilet", "bathtub"),
    "storage": ("bed", "sofa", "car", "toilet", "bathtub"),
    "veranda": ("bed", "toilet", "bathtub", "shower", "fridge", "car"),
}

_FURNITURE_SYSTEM = (
    "You are an interior designer placing furniture on a 2D Sweet Home 3D floor plan. "
    "Return STRICT JSON only, no markdown: "
    "{\"rooms\":[{\"type\":\"living\",\"items\":[\"L-shaped sofa against a wall facing the TV\"]}]} "
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
        "living", "kitchen", "bedroom", "bathroom", "hallway", "garage",
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


def _required_rooms_clause(spec: dict[str, Any] | None = None) -> str:
    """Liste obligatoire des pièces + murs fermés, pour le prompt FLUX."""
    counts = _program_counts(spec)
    if not counts:
        return (
            "Draw a complete house: every room enclosed by grey walls, continuous outer walls. "
        )
    listed = ", ".join(f"{n}x {_FURN_ROOM_EN.get(typ, typ)}" for typ, n in counts.items())
    return (
        f"REQUIRED ROOMS (draw every one, exact counts, each as its own enclosed space): {listed}. "
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
        r for r in (rooms or [])
        if isinstance(r, dict) and len(r.get("polygon") or []) >= 3
    ]
    if usable:
        return _apply_canonical_names(usable)
    program = _apply_canonical_names(expand_rooms((spec or {}).get("rooms") or []))
    if not program:
        return []
    return pack_rooms(program, width, depth)


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
        wall_list = walls if walls else perimeter_and_internal_walls(rooms, width, depth)
        open_list = openings if openings else default_openings(wall_list, width, depth, rooms)
        png = _render_floorplan(
            rooms, wall_list, open_list, width, depth, furniture=furniture or None
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
                text = str(it.get("item") or it.get("name") or it.get("place") or "").strip()
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
) -> str:
    """Brief + style Sweet Home 3D + (si layout_guided) consigne de suivre le plan attaché."""
    _ = (rooms, width, depth, label_mode)
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
        f"{_required_rooms_clause(spec)}"
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
    "SEJOUR": "living", "SALON": "living", "LIVING": "living", "SALLE DE SEJOUR": "living",
    "CUISINE": "kitchen", "KITCHEN": "kitchen", "KITCHENETTE": "kitchen",
    "SALLE A MANGER": "dining", "SAM": "dining", "DINING": "dining",
    "CHAMBRE": "bedroom", "CHAMBRE PARENTALE": "bedroom", "SUITE PARENTALE": "bedroom",
    "SUITE": "bedroom", "BEDROOM": "bedroom",
    "SDB": "bathroom", "SALLE DE BAIN": "bathroom", "SALLE D'EAU": "bathroom",
    "SALLE DE BAINS": "bathroom", "BATHROOM": "bathroom", "BAIN": "bathroom",
    "WC": "wc", "TOILETTES": "wc", "TOILETTE": "wc",
    "COULOIR": "hallway", "DEGAGEMENT": "hallway", "HALL": "hallway", "ENTREE": "hallway",
    "CIRCULATION": "hallway", "COULOIR CENTRAL": "hallway",
    "GARAGE": "garage", "CARPORT": "garage",
    "BUREAU": "office", "OFFICE": "office",
    "CELLIER": "storage", "RANGEMENT": "storage", "DEBARRAS": "storage", "PLACARD": "storage",
    "BUANDERIE": "laundry", "LINGERIE": "laundry",
    "VERANDA": "veranda", "TERRASSE": "veranda", "VARANGUE": "veranda",
}
_TYPE_FR = {
    "living": "Séjour", "kitchen": "Cuisine", "dining": "Salle à manger", "bedroom": "Chambre",
    "bathroom": "SDB", "wc": "WC", "hallway": "Couloir", "garage": "Garage", "office": "Bureau",
    "storage": "Rangement", "laundry": "Buanderie", "veranda": "Véranda",
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
    "If two SDB, one is an ensuite east of the master bedroom.\n"
    "- Keep proportions habitable: no room thinner than 1.8 m (WC/SDB may be 1.4 m).\n\n"
    "OUTPUT - one JSON object, no markdown:\n"
    "{\"veranda_depth\": 0, \"rooms\": [{\"name\": \"SEJOUR\", \"area\": 28, \"zone\": \"front\"}]}\n"
    "List every program room once. zone is front|centre|back|left|right. veranda_depth=0."
)


def _layout_user(
    spec: dict[str, Any], program: list[dict[str, Any]], width: float, depth: float
) -> str:
    lines = []
    for r in program:
        name = _ascii_upper(str(r.get("name") or r.get("type") or "room")) or "ROOM"
        try:
            lines.append(f"- {name}: current area ~{float(r.get('area_m2') or 12):.0f} m2")
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
    "living": 18.0, "bedroom": 9.0, "kitchen": 8.0, "dining": 9.0, "bathroom": 3.5,
    "wc": 2.4, "office": 7.5, "hallway": 3.0, "garage": 14.0, "storage": 2.0, "laundry": 3.0,
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
                area = float(it.get("w") or it.get("width") or 0) * float(it.get("d") or it.get("depth") or 0)
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
        out.append({
            "id": src.get("id") or f"llm_{i + 1}",
            "type": src.get("type") or p["typ"],
            "name": src.get("name") or _label(p["typ"], None),
            "area_m2": round(max(2.0, floored[i] * k), 1),
            "_zone": _ZONE_ORDER.get(p["zone"], 3),
        })
    for j in unused:
        src = program[j]
        out.append({
            "id": src.get("id") or f"r{len(out) + 1}",
            "type": src.get("type"),
            "name": src.get("name") or _label(str(src.get("type") or ""), None),
            "area_m2": float(src.get("area_m2") or 8),
            "_zone": 3,
        })
    if len(out) != len(program) or len(out) < 2:
        return None
    out.sort(key=lambda r: r.pop("_zone"))
    return out


def _parse_llm_rect(it: dict[str, Any], width: float, depth: float) -> tuple[float, float, float, float] | None:
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
        d = float(it.get("d") or it.get("depth") or it.get("depth_m") or it.get("h") or 0)
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


def _rect_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
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
        placed.append({
            "id": src.get("id") or f"r{len(placed) + 1}",
            "type": src["type"],
            "name": src.get("name") or _label(src["type"], None),
            "area_m2": round((x1 - x0) * (y1 - y0), 2),
            "polygon": [
                {"x": x0, "y": y0}, {"x": x1, "y": y0},
                {"x": x1, "y": y1}, {"x": x0, "y": y1},
            ],
        })
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
    """Together : tailles LLM + packer maison. Un pavage n'est gardé que s'il est « house-like »."""
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
                messages, json_mode=True, temperature=0.15 + 0.2 * attempt, max_tokens=1800
            )
        except Exception:  # noqa: BLE001
            raw = None
        data = _parse_json_obj(raw)
        if not data:
            continue
        tiled = _normalize_llm_rooms(program, data.get("rooms"), width, depth)
        if tiled and _house_like(tiled, width, depth):
            return tiled, 0.0
        merged = _merge_llm_program(program, data.get("rooms"), width, depth)
        if merged:
            return pack_house(merged, width, depth, grid=0.1, min_side=1.6), 0.0
    return None, 0.0


def _llm_program(
    spec: dict[str, Any], program: list[dict[str, Any]], width: float, depth: float
) -> tuple[list[dict[str, Any]] | None, float]:
    """Compat tests : taille/ordre seulement (sans polygones)."""
    rooms, vd = _llm_layout(spec, program, width, depth)
    if not rooms:
        return None, 0.0
    return [{k: r[k] for k in r if k != "polygon"} for r in rooms], vd


def default_openings(
    walls: list[dict[str, Any]],
    width: float,
    depth: float,
    rooms: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Porte d'entrée sud + porte de garage + fenêtres façades + portes internes autorisées.

    La porte de garage s'ouvre sur le mur extérieur où le garage se trouve (`_garage_door`).
    """
    openings: list[dict[str, Any]] = []
    oid = 1
    internals = [w for w in walls if not str(w.get("id", "")).startswith("w_outer")]
    by_id = {str(w.get("id")): w for w in walls}
    south = by_id.get("w_outer_3")
    east = by_id.get("w_outer_2")
    north = by_id.get("w_outer_1")
    west = by_id.get("w_outer_4")
    room_list = [r for r in (rooms or []) if len(r.get("polygon") or []) >= 3]
    has_garage = any(r.get("type") == "garage" for r in room_list)

    if south:
        flen = _wall_len(south)
        openings.append({
            "id": f"o{oid}",
            "wall_id": south["id"],
            "type": "door",
            # 42 % de la façade tombait au hasard : l'entrée pouvait déboucher
            # dans la salle de bain. On la cale sur l'entrée / le séjour dès
            # qu'on connaît les pièces.
            "offset_m": _entrance_offset(south, flen, room_list),
            "width_m": 0.9,
        })
        oid += 1
    if has_garage:
        entrance = next((o for o in openings if south and o.get("wall_id") == south["id"]), None)
        garage_door = _garage_door(
            (east, west, north, south), room_list,
            (float(entrance["offset_m"]), float(entrance["width_m"])) if entrance else None,
        )
        if garage_door:
            wall, offset, width_m = garage_door
            openings.append({
                "id": f"o{oid}",
                "wall_id": wall["id"],
                "type": "door",
                "offset_m": offset,
                "width_m": width_m,
            })
            oid += 1
    for wall in (north, west):
        if not wall:
            continue
        wl = _wall_len(wall)
        if wl < 1.6:
            continue
        openings.append({
            "id": f"o{oid}",
            "wall_id": wall["id"],
            "type": "window",
            "offset_m": max(0.3, wl * 0.25),
            "width_m": min(1.4, wl * 0.35),
        })
        oid += 1

    for wall in internals:
        wl = _wall_len(wall)
        if wl < 1.05:
            continue
        if room_list and not _allow_internal_door(wall, room_list):
            continue
        if not room_list and wl < 1.2:
            continue
        openings.append({
            "id": f"o{oid}",
            "wall_id": wall["id"],
            "type": "door",
            "offset_m": max(0.2, min(wl - 1.0, wl * 0.4)),
            "width_m": 0.8,
        })
        oid += 1
    if room_list:
        _add_missing_room_doors(openings, walls, internals, room_list, oid)
    _ = (width, depth)
    return openings


# Voisinages qu'on refuse même en dernier recours : ouvrir une de ces portes
# vaut un écart sanitaire signalé par `compliance.evaluate`.
_FORBIDDEN_PAIRS = {
    frozenset({"wc", "kitchen"}),
    frozenset({"wc", "dining"}),
    frozenset({"wc", "bedroom"}),
    frozenset({"bedroom", "living"}),
    frozenset({"kitchen", "bathroom"}),
}
# Pièces auxquelles une porte de façade convient si aucune porte intérieure
# n'est acceptable (un WC ou une chambre ne s'ouvre pas sur le jardin).
_FACADE_DOOR_OK = {"garage", "living", "kitchen", "dining", "hallway", "office", "storage", "laundry"}
_NEIGHBOUR_RANK = {"hallway": 4, "living": 3, "dining": 3, "kitchen": 2, "office": 2, "garage": 2}


def _wall_span_for_room(
    wall: dict[str, Any], room: dict[str, Any]
) -> tuple[float, float] | None:
    """Portion du mur en vis-à-vis de `room`, en mètres depuis l'extrémité `a`.

    Un mur de façade court le long de toute la maison : centrer une ouverture
    sur le mur la posait devant une autre pièce (porte d'entrée débouchant
    dans la salle de bain, porte de secours percée chez le voisin).
    """
    from .layout_opt import _room_bbox

    a, b = _wall_point(wall.get("a")), _wall_point(wall.get("b"))
    box = _room_bbox(room)
    if a is None or b is None or box is None:
        return None
    x0, y0, x1, y1 = box
    if abs(a[0] - b[0]) <= 0.15:  # mur vertical
        if abs(x0 - a[0]) > 0.15 and abs(x1 - a[0]) > 0.15:
            return None
        lo, hi = max(min(a[1], b[1]), y0), min(max(a[1], b[1]), y1)
        if hi - lo <= 0.05:
            return None
        return (lo - a[1], hi - a[1]) if b[1] >= a[1] else (a[1] - hi, a[1] - lo)
    if abs(a[1] - b[1]) > 0.15:  # mur oblique : pas de découpe fiable
        return None
    if abs(y0 - a[1]) > 0.15 and abs(y1 - a[1]) > 0.15:
        return None
    lo, hi = max(min(a[0], b[0]), x0), min(max(a[0], b[0]), x1)
    if hi - lo <= 0.05:
        return None
    return (lo - a[0], hi - a[0]) if b[0] >= a[0] else (a[0] - hi, a[0] - lo)


def _centred_offset(span: tuple[float, float], width_m: float, wall_len: float) -> float:
    lo, hi = span
    off = lo + max(0.0, (hi - lo - width_m) / 2)
    return round(max(0.0, min(off, max(0.0, wall_len - width_m))), 3)


def _served_rooms(
    wall: dict[str, Any], opening: dict[str, Any], rooms: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Pièces réellement desservies par une ouverture (au droit de sa position)."""
    from .layout_opt import _room_bbox

    a, b = _wall_point(wall.get("a")), _wall_point(wall.get("b"))
    if a is None or b is None:
        return []
    length = _wall_len(wall)
    try:
        mid = float(opening.get("offset_m") or 0) + float(opening.get("width_m") or 0) / 2
    except (TypeError, ValueError):
        return []
    t = min(1.0, max(0.0, mid / length)) if length > 0 else 0.5
    px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
    out: list[dict[str, Any]] = []
    for room in rooms:
        box = _room_bbox(room)
        if not box:
            continue
        x0, y0, x1, y1 = box
        on_v = (abs(x0 - px) <= 0.15 or abs(x1 - px) <= 0.15) and y0 - 0.15 <= py <= y1 + 0.15
        on_h = (abs(y0 - py) <= 0.15 or abs(y1 - py) <= 0.15) and x0 - 0.15 <= px <= x1 + 0.15
        if on_v or on_h:
            out.append(room)
    return out


def _add_missing_room_doors(
    openings: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    internals: list[dict[str, Any]],
    rooms: list[dict[str, Any]],
    oid: int,
) -> None:
    """Donne une porte à toute pièce qui n'en a aucune.

    La liste blanche `_DOOR_PAIRS` sait dire quelles portes sont *souhaitables*,
    mais rien ne garantissait qu'il en reste au moins une par pièce : un bureau
    coincé entre cuisine et salle à manger, ou un WC qui ne touche pas le
    couloir, se retrouvait muré — une pièce inaccessible, donc un plan faux.
    """
    by_id = {str(w.get("id")): w for w in walls}
    served: set[int] = set()
    for op in openings:
        if op.get("type") != "door":
            continue
        wall = by_id.get(str(op.get("wall_id")))
        if wall is None:
            continue
        for room in _served_rooms(wall, op, rooms):
            served.add(id(room))
    for room in rooms:
        if id(room) in served:
            continue
        wall = _best_access_wall(room, internals, walls, rooms)
        if wall is None:
            continue
        wl = _wall_len(wall)
        span = _wall_span_for_room(wall, room) or (0.0, wl)
        usable = span[1] - span[0]
        width_m = 0.8 if usable >= 0.85 else max(0.6, usable - 0.05)
        openings.append({
            "id": f"o{oid}",
            "wall_id": wall["id"],
            "type": "door",
            "offset_m": _centred_offset(span, width_m, wl),
            "width_m": round(width_m, 2),
        })
        oid += 1
        served.add(id(room))


def _best_access_wall(
    room: dict[str, Any],
    internals: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    rooms: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Meilleur mur pour percer la porte manquante d'une pièce enclavée."""
    typ = str(room.get("type") or "")
    best: tuple[tuple[float, float, float], dict[str, Any]] | None = None
    for wall in internals:
        pair = _rooms_on_wall(wall, rooms)
        if len(pair) != 2 or all(r is not room for r in pair):
            continue
        other = next(r for r in pair if r is not room)
        other_t = str(other.get("type") or "")
        if frozenset({typ, other_t}) in _FORBIDDEN_PAIRS:
            continue
        span = _wall_span_for_room(wall, room)
        usable = (span[1] - span[0]) if span else _wall_len(wall)
        if usable < 0.7:
            continue
        # Un mur assez large pour une porte réglementaire (0,80 m) passe avant
        # un voisinage mieux classé mais trop étroit.
        rank = (1.0 if usable >= 0.85 else 0.0, float(_NEIGHBOUR_RANK.get(other_t, 1)), usable)
        if best is None or rank > best[0]:
            best = (rank, wall)
    if best is not None:
        return best[1]
    facade: list[tuple[float, dict[str, Any]]] = []
    if typ in _FACADE_DOOR_OK:
        for w in walls:
            if not str(w.get("id", "")).startswith("w_outer"):
                continue
            span = _wall_span_for_room(w, room)
            if span and span[1] - span[0] >= 1.0:
                facade.append((span[1] - span[0], w))
    if facade:
        return max(facade, key=lambda it: it[0])[1]
    return _last_resort_wall(room, internals, rooms)


def _last_resort_wall(
    room: dict[str, Any], internals: list[dict[str, Any]], rooms: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Mur le plus large, voisinage déconseillé compris.

    Une pièce murée est pire qu'un écart sanitaire : celui-ci est au moins
    signalé par `compliance.evaluate`, l'autre rend le plan inutilisable.
    """
    best: tuple[float, dict[str, Any]] | None = None
    for wall in internals:
        pair = _rooms_on_wall(wall, rooms)
        if len(pair) != 2 or all(r is not room for r in pair):
            continue
        span = _wall_span_for_room(wall, room)
        usable = (span[1] - span[0]) if span else _wall_len(wall)
        if usable >= 0.7 and (best is None or usable > best[0]):
            best = (usable, wall)
    return best[1] if best else None


# Pièces qui peuvent recevoir la porte d'entrée, de la meilleure à la pire.
_ENTRANCE_ORDER = ("hallway", "living", "dining", "kitchen", "office", "garage")

# Porte de garage : 2,4 m, avec 0,2 m de part et d'autre dans la façade du garage.
_GARAGE_DOOR_WIDTH = 2.4
_MIN_GARAGE_CONTACT = _GARAGE_DOOR_WIDTH + 0.4


def _garage_door(
    walls: tuple[dict[str, Any] | None, ...],
    rooms: list[dict[str, Any]],
    entrance: tuple[float, float] | None,
) -> tuple[dict[str, Any], float, float] | None:
    """Mur, position et largeur de la porte de garage, ou None s'il n'y a pas de façade pour l'ouvrir.

    La porte était toujours posée sur le mur est, à 55 % de sa longueur, où que soit le
    garage : un garage à l'ouest ou au nord avait sa porte devant une autre pièce. Elle
    s'ouvre désormais sur le mur extérieur où un garage se trouve.

    1. L'emplacement historique (mur est) est conservé tel quel dès qu'un garage l'occupe :
       les plans dont le garage tient toute la façade est ne changent pas d'un millimètre.
    2. Sinon, le mur où un garage a le plus long contact (au moins `_MIN_GARAGE_CONTACT`),
       préférence est, ouest, nord, sud à contact égal, la porte centrée sur ce contact. Sur
       le mur sud, elle évite la porte d'entrée (`entrance` : position et largeur).
    """
    east, west, north, south = walls
    garages = [r for r in rooms if r.get("type") == "garage"]
    if east and _wall_len(east) >= 2.4:
        wl = _wall_len(east)
        offset, width_m = max(0.4, min(wl - 2.6, wl * 0.55)), min(2.4, wl * 0.45)
        for garage in garages:
            span = _wall_span_for_room(east, garage)
            if span and span[0] <= offset + 0.05 and span[1] >= offset + width_m - 0.05:
                return east, offset, width_m
    best: tuple[tuple[float, int], dict[str, Any], float] | None = None
    for rank, wall in enumerate(walls):
        if wall is None:
            continue
        for garage in garages:
            span = _wall_span_for_room(wall, garage)
            if not span or span[1] - span[0] < _MIN_GARAGE_CONTACT:
                continue
            offset = _centred_offset(span, _GARAGE_DOOR_WIDTH, _wall_len(wall))
            if wall is south and entrance and offset < entrance[0] + entrance[1] and entrance[0] < offset + _GARAGE_DOOR_WIDTH:
                continue
            key = (-round(span[1] - span[0], 3), rank)
            if best is None or key < best[0]:
                best = (key, wall, offset)
    return (best[1], best[2], _GARAGE_DOOR_WIDTH) if best else None


def _entrance_offset(
    south: dict[str, Any], flen: float, rooms: list[dict[str, Any]]
) -> float:
    """Position de la porte d'entrée sur la façade sud, devant une pièce d'accueil."""
    default = max(0.4, min(flen - 1.2, flen * 0.42))
    if not rooms:
        return default
    best: tuple[int, float, tuple[float, float]] | None = None
    for room in rooms:
        span = _wall_span_for_room(south, room)
        if not span or span[1] - span[0] < 1.1:
            continue
        typ = str(room.get("type") or "")
        rank = _ENTRANCE_ORDER.index(typ) if typ in _ENTRANCE_ORDER else len(_ENTRANCE_ORDER)
        key = (rank, -(span[1] - span[0]), span)
        if best is None or key[:2] < best[:2]:
            best = key
    if best is None:
        return default
    return _centred_offset(best[2], 0.9, flen)


_DOOR_PAIRS = {
    frozenset({"bedroom", "hallway"}),
    frozenset({"bathroom", "hallway"}),
    frozenset({"wc", "hallway"}),
    frozenset({"laundry", "hallway"}),
    frozenset({"storage", "hallway"}),
    frozenset({"office", "hallway"}),
    frozenset({"kitchen", "living"}),
    frozenset({"kitchen", "dining"}),
    frozenset({"kitchen", "hallway"}),
    frozenset({"living", "hallway"}),
    frozenset({"living", "dining"}),
    frozenset({"living", "office"}),
    frozenset({"dining", "hallway"}),
    frozenset({"garage", "hallway"}),
    frozenset({"garage", "living"}),
}


def _rooms_on_wall(wall: dict[str, Any], rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from .layout_opt import _room_bbox

    a = _wall_point(wall.get("a"))
    b = _wall_point(wall.get("b"))
    if a is None or b is None:
        return []
    ax, ay = a
    bx, by = b
    vertical = abs(ax - bx) <= 0.15
    hits: list[dict[str, Any]] = []
    for room in rooms:
        box = _room_bbox(room)
        if not box:
            continue
        x0, y0, x1, y1 = box
        if vertical:
            x = (ax + bx) / 2
            ylo, yhi = min(ay, by), max(ay, by)
            if abs(x0 - x) > 0.15 and abs(x1 - x) > 0.15:
                continue
            if min(y1, yhi) - max(y0, ylo) >= 0.5:
                hits.append(room)
        else:
            y = (ay + by) / 2
            xlo, xhi = min(ax, bx), max(ax, bx)
            if abs(y0 - y) > 0.15 and abs(y1 - y) > 0.15:
                continue
            if min(x1, xhi) - max(x0, xlo) >= 0.5:
                hits.append(room)
    return hits


def _allow_internal_door(wall: dict[str, Any], rooms: list[dict[str, Any]]) -> bool:
    pair = _rooms_on_wall(wall, rooms)
    if len(pair) != 2:
        return False
    types = [str(r.get("type") or "") for r in pair]
    key = frozenset(types)
    if key == {"bedroom", "bathroom"}:
        return any(bool(r.get("ensuite")) for r in pair if r.get("type") == "bathroom")
    if key == {"bathroom", "hallway"}:
        bath = next(r for r in pair if r.get("type") == "bathroom")
        return not bath.get("ensuite")
    return key in _DOOR_PAIRS


def _wall_point(node: Any) -> tuple[float, float] | None:
    """(x, y) d'une extrémité de mur, ou None si le mur est malformé.

    Les murs peuvent venir d'un `layout` libre (/v1/vectorize) : un `{}` ou un
    `{"a": 3}` faisait remonter KeyError/TypeError en 500.
    """
    if not isinstance(node, dict):
        return None
    try:
        return float(node["x"]), float(node["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _wall_len(wall: dict[str, Any]) -> float:
    a = _wall_point(wall.get("a")) if isinstance(wall, dict) else None
    b = _wall_point(wall.get("b")) if isinstance(wall, dict) else None
    if a is None or b is None:
        return 0.0
    return max(0.1, ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5)


# Bornes du programme de pièces. `/v1/generate` accepte un `building_spec`
# libre : sans plafond, `{"rooms": [{"count": 1_000_000_000}]}` faisait
# exploser la mémoire et le temps de pavage (DoS). Sans `.get()` tolérant, une
# pièce sans `id`/`type` remontait en KeyError → 500.
MAX_ROOM_COUNT = 20
MAX_ROOMS_TOTAL = 60


def expand_rooms(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            out.append({
                "id": f"{rid}_{i + 1}" if count > 1 else rid,
                "type": typ,
                "name": _label(typ, i + 1 if count > 1 else None),
                "area_m2": area,
            })
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


def pack_rooms(rooms: list[dict[str, Any]], width: float, depth: float) -> list[dict[str, Any]]:
    """Pavé maison : nuit au nord, couloir, jour au sud, cuisine à l'ouest, garage à l'est."""
    if not rooms:
        return []
    from .layout_opt import pack_house

    return pack_house(rooms, width, depth, grid=0.1, min_side=1.6)


def _r(v: float) -> float:
    return round(max(0.0, v), 2)


def _bsp_pack(rooms: list[dict[str, Any]], x0: float, y0: float, x1: float, y1: float) -> list[dict[str, Any]]:
    if not rooms:
        # Sans cette garde, `mid = max(1, 0)` renvoyait deux moitiés vides :
        # récursion infinie puis ZeroDivisionError sur `a_l + a_r`.
        return []
    if len(rooms) == 1:
        return [{
            **rooms[0],
            "polygon": [
                {"x": _r(x0), "y": _r(y0)},
                {"x": _r(x1), "y": _r(y0)},
                {"x": _r(x1), "y": _r(y1)},
                {"x": _r(x0), "y": _r(y1)},
            ],
        }]
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


def perimeter_and_internal_walls(rooms: list[dict[str, Any]], width: float, depth: float) -> list[dict[str, Any]]:
    walls = [
        {"id": "w_outer_1", "a": {"x": 0, "y": 0}, "b": {"x": width, "y": 0}, "thickness_m": 0.2},
        {"id": "w_outer_2", "a": {"x": width, "y": 0}, "b": {"x": width, "y": depth}, "thickness_m": 0.2},
        {"id": "w_outer_3", "a": {"x": width, "y": depth}, "b": {"x": 0, "y": depth}, "thickness_m": 0.2},
        {"id": "w_outer_4", "a": {"x": 0, "y": depth}, "b": {"x": 0, "y": 0}, "thickness_m": 0.2},
    ]
    seen: set[tuple[float, float, float, float]] = set()
    wid = 1
    for room in rooms:
        poly = room.get("polygon") or [] if isinstance(room, dict) else []
        if len(poly) < 3:
            continue
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            if _is_outer_edge(a, b, width, depth):
                continue
            key = _edge_key(a, b)
            if key in seen:
                continue
            seen.add(key)
            walls.append({
                "id": f"w_i{wid}",
                "a": {"x": key[0], "y": key[1]},
                "b": {"x": key[2], "y": key[3]},
                "thickness_m": 0.15,
            })
            wid += 1
    return walls


def _edge_key(a: dict[str, float], b: dict[str, float]) -> tuple[float, float, float, float]:
    ax, ay, bx, by = round(a["x"], 3), round(a["y"], 3), round(b["x"], 3), round(b["y"], 3)
    if (ax, ay) <= (bx, by):
        return ax, ay, bx, by
    return bx, by, ax, ay


def _is_outer_edge(a: dict[str, float], b: dict[str, float], width: float, depth: float) -> bool:
    xs = {a["x"], b["x"]}
    ys = {a["y"], b["y"]}
    on_left = xs == {0.0} or (min(xs) <= 0 and max(xs) <= 0)
    on_right = min(xs) >= width and max(xs) >= width
    on_top = ys == {0.0} or (min(ys) <= 0 and max(ys) <= 0)
    on_bottom = min(ys) >= depth and max(ys) >= depth
    return on_left or on_right or on_top or on_bottom


ROOM_FILL: dict[str, tuple[int, int, int]] = {
    "living": (236, 214, 176),
    "kitchen": (232, 168, 120),
    "bedroom": (176, 198, 222),
    "bathroom": (152, 196, 196),
    "hallway": (228, 222, 214),
    "garage": (196, 196, 190),
    "office": (196, 184, 214),
    "dining": (222, 190, 168),
    "storage": (210, 206, 196),
}


def _room_font(size: int) -> _Font:
    for path in ("arial.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _draw_room_contents(draw: ImageDraw.ImageDraw, room: dict[str, Any], sx: float, sy: float, font: _Font) -> None:
    poly = room.get("polygon") or []
    if len(poly) < 3:
        return
    xs = [float(p["x"]) for p in poly]
    ys = [float(p["y"]) for p in poly]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    rw, rd = x1 - x0, y1 - y0
    typ = str(room.get("type") or "")

    def box(mx0: float, my0: float, mx1: float, my1: float, fill: tuple[int, int, int]) -> None:
        draw.rectangle([mx0 * sx, my0 * sy, mx1 * sx, my1 * sy], fill=fill, outline=(50, 50, 50))

    if typ == "kitchen":
        t = min(0.6, rd * 0.28)
        box(x0, y0, x1, y0 + t, (196, 160, 112))
        sink_x = x0 + rw * 0.2
        box(sink_x, y0 + 0.08, sink_x + 0.5, y0 + t - 0.08, (197, 216, 224))
        stove = x0 + rw * 0.55
        box(stove, y0 + 0.1, stove + 0.55, y0 + t - 0.1, (63, 63, 63))
    elif typ == "bathroom":
        box(x1 - min(1.7, rw - 0.3), y0 + 0.2, x1 - 0.2, y0 + 0.9, (184, 205, 212))
        cx, cy = x0 + 0.45, y1 - 0.45
        draw.ellipse([(cx - 0.2) * sx, (cy - 0.22) * sy, (cx + 0.2) * sx, (cy + 0.22) * sy], fill=(236, 236, 236), outline=(50, 50, 50))
    elif typ == "bedroom":
        box(x0 + 0.25, y0 + 0.25, x0 + min(2.0, rw - 0.35), y0 + min(1.5, rd - 0.35), (154, 168, 188))
    elif typ == "living":
        box(x0 + 0.25, y1 - 0.85, x0 + min(2.4, rw - 0.35), y1 - 0.25, (138, 115, 88))

    name = str(room.get("name") or _label(typ, None))
    cx = (x0 + x1) / 2 * sx
    cy = (y0 + y1) / 2 * sy
    try:
        draw.text((cx, cy), name, fill=(28, 25, 23), font=font, anchor="mm")
    except TypeError:
        bbox = draw.textbbox((0, 0), name, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - tw / 2, cy - th / 2), name, fill=(28, 25, 23), font=font)
