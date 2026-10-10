"""HouseDiffusion inference: model250000.pt → pièces vectorielles."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "vendor" / "house_diffusion"
DEFAULT_WEIGHTS = ROOT / "model250000.pt"

TYPE_TO_RPLAN = {
    "living": 1,
    "kitchen": 2,
    "bedroom": 3,
    "bathroom": 4,
    "hallway": 6,
    "dining": 7,
    "office": 8,
    "storage": 10,
    "garage": 10,
}
RPLAN_TO_TYPE = {v: k for k, v in TYPE_TO_RPLAN.items()}
RPLAN_TO_NAME = {
    1: "Séjour",
    2: "Cuisine",
    3: "Chambre",
    4: "SDB",
    6: "Entrée",
    7: "Salle à manger",
    8: "Bureau",
    10: "Rangement",
}

MAX_POINTS = 100
CORNERS = 4


def weights_path() -> Path:
    raw = os.getenv("HOUSEDIFFUSION_WEIGHTS", "").strip()
    return Path(raw) if raw else DEFAULT_WEIGHTS


def available() -> bool:
    """Vrai seulement si l'inférence HouseDiffusion peut réellement tourner.

    Il ne suffit pas que les poids existent : le paquet vendored
    `vendor/house_diffusion` est importé par `_load()` et n'est pas versionné.
    Sans cette vérification, `available()` annonçait un backend utilisable puis
    `generate()` levait ModuleNotFoundError.
    """
    if os.getenv("AI_STUB", "1") == "1":
        return False
    if not (VENDOR / "house_diffusion" / "script_util.py").is_file():
        return False
    return weights_path().is_file()


def _one_hot(idx: int, size: int) -> np.ndarray:
    v = np.zeros(size, dtype=np.float32)
    if 0 <= idx < size:
        v[idx] = 1.0
    return v


def rooms_from_spec(spec: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for room in spec.get("rooms") or []:
        typ = str(room.get("type") or "living")
        count = int(room.get("count") or 1)
        rplan = TYPE_TO_RPLAN.get(typ)
        if rplan is None:
            continue
        out.extend([typ] * max(1, count))
    if not out:
        out = ["living", "kitchen", "bedroom", "bathroom"]
    return out[:12]


def build_syn_kwargs(
    room_types: list[str], device: Any
) -> tuple[tuple[int, int, int], dict[str, Any]]:
    import torch

    n_rooms = len(room_types)
    rplan_ids = [TYPE_TO_RPLAN[t] for t in room_types]
    living = next((i for i, t in enumerate(room_types) if t == "living"), 0)

    rows: list[np.ndarray] = []
    bounds: list[tuple[int, int]] = []
    offset = 0
    for ri, rid in enumerate(rplan_ids):
        n = CORNERS
        bounds.append((offset, offset + n))
        for c in range(n):
            coords = np.zeros(2, dtype=np.float32)
            rtype = _one_hot(rid, 25)
            corner = _one_hot(c, 32)
            room_i = _one_hot(ri + 1, 32)
            pad = np.array([1.0], dtype=np.float32)
            conn = np.array([offset + c, offset + (c + 1) % n], dtype=np.float32)
            rows.append(np.concatenate([coords, rtype, corner, room_i, pad, conn]))
        offset += n

    house = np.stack(rows, 0)
    if house.shape[0] > MAX_POINTS:
        raise ValueError("trop de coins pour HouseDiffusion")
    pad_n = MAX_POINTS - house.shape[0]
    if pad_n:
        house = np.concatenate([house, np.zeros((pad_n, 94), dtype=np.float32)], 0)

    door = np.ones((MAX_POINTS, MAX_POINTS), dtype=np.float32)
    self_m = np.ones((MAX_POINTS, MAX_POINTS), dtype=np.float32)
    gen = np.ones((MAX_POINTS, MAX_POINTS), dtype=np.float32)
    gen[:offset, :offset] = 0
    for i, (a0, a1) in enumerate(bounds):
        self_m[a0:a1, a0:a1] = 0
        for j, (b0, b1) in enumerate(bounds):
            if i == j:
                continue
            if i == living or j == living:
                door[a0:a1, b0:b1] = 0

    graph = np.zeros((200, 3), dtype=np.float32)
    ge = 0
    for j in range(n_rooms):
        if j == living:
            continue
        graph[ge] = [living, 1, j]
        ge += 1

    def t(x: np.ndarray) -> Any:
        return torch.from_numpy(x).unsqueeze(0).to(device)

    kw = {
        "syn_door_mask": t(door),
        "syn_self_mask": t(self_m),
        "syn_gen_mask": t(gen),
        "syn_room_types": t(house[:, 2:27]),
        "syn_corner_indices": t(house[:, 27:59]),
        "syn_room_indices": t(house[:, 59:91]),
        "syn_src_key_padding_mask": t(1.0 - house[:, 91]),
        "syn_connections": t(house[:, 92:94]),
        "syn_graph": t(graph),
        "door_mask": t(door),
        "self_mask": t(self_m),
        "gen_mask": t(gen),
        "room_types": t(house[:, 2:27]),
        "corner_indices": t(house[:, 27:59]),
        "room_indices": t(house[:, 59:91]),
        "src_key_padding_mask": t(1.0 - house[:, 91]),
        "connections": t(house[:, 92:94]),
        "graph": t(graph),
    }
    return (1, 2, MAX_POINTS), kw


_MODEL = None
_DIFF = None


def _load_checkpoint(weights_path: str | Path, map_location: str) -> Any:
    """Charge le state_dict HouseDiffusion en essayant `weights_only=True` d'abord.

    Voir `gan_refine._load_checkpoint` pour le rationnel : ceci mitige la
    désérialisation pickle arbitraire tout en tolérant les checkpoints plus
    anciens qui ne passent pas la liste blanche `weights_only`. Le fichier
    (`HOUSEDIFFUSION_WEIGHTS` / `model250000.pt`) est toujours un chemin local
    choisi par l'opérateur, jamais un contenu fourni par un client HTTP.
    """
    import torch

    try:
        return torch.load(weights_path, map_location=map_location, weights_only=True)
    except Exception:
        return torch.load(weights_path, map_location=map_location, weights_only=False)


def _load(device: Any, steps: int) -> tuple[Any, Any]:
    global _MODEL, _DIFF
    if _MODEL is not None and _DIFF is not None:
        return _MODEL, _DIFF
    if str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))
    from house_diffusion.script_util import (
        create_model_and_diffusion,
        update_arg_parser,
    )

    class A:
        analog_bit = False
        dataset = "rplan"
        learn_sigma = False
        diffusion_steps = 1000
        noise_schedule = "cosine"
        timestep_respacing = str(max(20, min(steps, 1000)))
        use_kl = False
        predict_xstart = False
        rescale_timesteps = False
        rescale_learned_sigmas = False
        target_set = -1
        set_name = ""
        use_checkpoint = False
        input_channels = 0
        condition_channels = 0
        out_channels = 0
        use_unet = False
        num_channels = 512

    args = A()
    update_arg_parser(args)
    model, diffusion = create_model_and_diffusion(
        input_channels=args.input_channels,
        condition_channels=args.condition_channels,
        num_channels=args.num_channels,
        out_channels=args.out_channels,
        dataset=args.dataset,
        use_checkpoint=args.use_checkpoint,
        use_unet=args.use_unet,
        learn_sigma=args.learn_sigma,
        diffusion_steps=args.diffusion_steps,
        noise_schedule=args.noise_schedule,
        timestep_respacing=args.timestep_respacing,
        use_kl=args.use_kl,
        predict_xstart=args.predict_xstart,
        rescale_timesteps=args.rescale_timesteps,
        rescale_learned_sigmas=args.rescale_learned_sigmas,
        analog_bit=args.analog_bit,
        target_set=args.target_set,
        set_name=args.set_name,
    )
    state = _load_checkpoint(weights_path(), "cpu")
    model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()
    _MODEL, _DIFF = model, diffusion
    return model, diffusion


def _decode_rooms(
    coords: np.ndarray, kw: dict[str, Any], width: float, depth: float
) -> list[dict[str, Any]]:
    mask = kw["syn_src_key_padding_mask"][0].cpu().numpy()
    types = kw["syn_room_types"][0].cpu().numpy()
    ridx = kw["syn_room_indices"][0].cpu().numpy()
    rooms: list[dict[str, Any]] = []
    poly: list[dict[str, float]] = []
    cur_type = 0
    cur_ri = None
    bed_n = 0
    for j in range(coords.shape[0]):
        if mask[j] >= 0.5:
            continue
        pt = coords[j]
        x = float((pt[0] / 2 + 0.5) * width)
        y = float((pt[1] / 2 + 0.5) * depth)
        ri = int(np.argmax(ridx[j]))
        if cur_ri is not None and ri != cur_ri and poly:
            rooms.append(_room_dict(cur_type, poly, bed_n))
            if cur_type == 3:
                bed_n += 1
            poly = []
        cur_ri = ri
        cur_type = int(np.argmax(types[j]))
        poly.append({"x": round(max(0.0, x), 2), "y": round(max(0.0, y), 2)})
    if poly:
        rooms.append(_room_dict(cur_type, poly, bed_n))
    return [r for r in rooms if len(r["polygon"]) >= 3]


def _room_dict(rplan: int, poly: list[dict[str, float]], bed_n: int) -> dict[str, Any]:
    typ = RPLAN_TO_TYPE.get(rplan, "other")
    name = RPLAN_TO_NAME.get(rplan, typ)
    if typ == "bedroom" and bed_n:
        name = f"Chambre {bed_n + 1}"
    elif typ == "bedroom":
        name = "Chambre"
    return {
        "id": f"hd_{len(poly)}_{rplan}",
        "type": typ,
        "name": name,
        "area_m2": _poly_area(poly),
        "polygon": poly,
    }


def _poly_area(poly: list[dict[str, float]]) -> float:
    if len(poly) < 3:
        return 0.0
    acc = 0.0
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        acc += p["x"] * q["y"] - q["x"] * p["y"]
    return round(abs(acc) / 2, 2)


def generate(spec: dict[str, Any]) -> dict[str, Any]:
    import torch

    from . import diffusion as proc

    # Make benchmark seeds effective while leaving normal application calls
    # untouched when the variable is absent.
    seed_text = os.getenv("HOUSEDIFFUSION_SEED", "").strip()
    if seed_text:
        try:
            seed = int(seed_text)
        except ValueError as exc:
            raise ValueError("HOUSEDIFFUSION_SEED must be an integer") from exc
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        np.random.seed(seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    steps = int(os.getenv("HOUSEDIFFUSION_STEPS", "100"))
    model, diff = _load(device, steps)
    room_types = rooms_from_spec(spec)
    shape, kw = build_syn_kwargs(room_types, device)
    last = None
    for out in diff.p_sample_loop_progressive(
        model,
        shape,
        clip_denoised=True,
        model_kwargs=kw,
        analog_bit=False,
        progress=False,
    ):
        last = out["sample"]
    if last is None:
        raise RuntimeError("HouseDiffusion: aucun sample")
    coords = last[0].permute(1, 0).detach().cpu().numpy()
    constraints = spec.get("constraints") or {}
    width = float(constraints.get("max_width_m") or 12)
    depth = float(constraints.get("max_depth_m") or 10)
    raw_rooms = _decode_rooms(coords, kw, width, depth)
    if len(raw_rooms) < 2:
        raise RuntimeError("HouseDiffusion: moins de 2 pièces décodées")
    for i, room in enumerate(raw_rooms):
        room["id"] = f"hd_r{i + 1}"
    from .layout_opt import optimize_rooms

    layout_rooms = optimize_rooms(raw_rooms, width, depth, spec)
    walls = proc.perimeter_and_internal_walls(layout_rooms, width, depth)
    openings = proc.default_openings(walls, width, depth, layout_rooms)
    from .diffusion import ROOM_FILL, _draw_room_contents, _room_font
    from PIL import Image, ImageDraw
    import base64
    import io

    canvas = Image.new("RGB", (512, 512), (245, 240, 232))
    draw = ImageDraw.Draw(canvas)
    sx, sy = 512 / max(width, 1), 512 / max(depth, 1)
    font = _room_font(16)
    for room in layout_rooms:
        poly = [(p["x"] * sx, p["y"] * sy) for p in room["polygon"]]
        if len(poly) >= 3:
            draw.polygon(
                poly,
                fill=ROOM_FILL.get(room.get("type") or "", (220, 230, 240)),
                outline=(40, 40, 40),
            )
            _draw_room_contents(draw, room, sx, sy, font)
    for wall in walls:
        draw.line(
            [
                (wall["a"]["x"] * sx, wall["a"]["y"] * sy),
                (wall["b"]["x"] * sx, wall["b"]["y"] * sy),
            ],
            fill=(20, 20, 20),
            width=3,
        )
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return {
        "image_png_b64": b64,
        "preview_key": "",
        "method": "house_diffusion+opt",
        "layout": {
            "width": width,
            "depth": depth,
            "height_m": 2.7,
            "rooms": layout_rooms,
            "walls": walls,
            "openings": openings,
        },
    }
