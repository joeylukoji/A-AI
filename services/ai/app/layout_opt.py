"""Packer résidentiel : topologie type Sweet Home 3D (pas un BSP naïf).

Convention du dessin (origine en haut à gauche, y vers le sud) :
  y = 0     → nord / fond de parcelle (chambres)
  y = depth → sud / jardin + entrée
  x = 0     → ouest (cuisine, SDB)
  x = width → est (chambre parentale, garage)
"""
from __future__ import annotations

from typing import Any


GRID = 0.5
MIN_SIDE = 2.0
HABITABLE = {"living", "bedroom", "dining", "office"}
WET = {"bathroom", "wc", "laundry", "storage"}


def _snap(v: float, grid: float = GRID) -> float:
    g = grid if grid > 0 else GRID
    return round(max(0.0, v) / g) * g


def _box(x0: float, y0: float, x1: float, y1: float) -> list[dict[str, float]]:
    return [
        {"x": x0, "y": y0},
        {"x": x1, "y": y0},
        {"x": x1, "y": y1},
        {"x": x0, "y": y1},
    ]


def _min_side(typ: str, default: float) -> float:
    return {
        "wc": min(1.2, default),
        "bathroom": min(1.5, default) if default < 1.6 else 1.5,
        "laundry": 1.5,
        "storage": 1.4,
        "hallway": 1.1,
        "kitchen": 2.2,
        "garage": 3.0,
        "bedroom": 2.6,
        "living": 3.0,
        "dining": 2.2,
        "office": 2.2,
    }.get(typ, default)


def _place(room: dict[str, Any], x0: float, y0: float, x1: float, y1: float, grid: float) -> dict[str, Any]:
    x0, y0 = _snap(x0, grid), _snap(y0, grid)
    x1, y1 = _snap(x1, grid), _snap(y1, grid)
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    x1 = max(x1, x0 + grid)
    y1 = max(y1, y0 + grid)
    w, h = x1 - x0, y1 - y0
    out = dict(room)
    out["polygon"] = _box(round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))
    out["area_m2"] = round(w * h, 2)
    return out


def _weights(items: list[dict[str, Any]]) -> list[float]:
    return [max(float(it.get("area") or it.get("area_m2") or 8), 2.0) for it in items]


def _splits(span: float, weights: list[float], mins: list[float], grid: float) -> list[float]:
    """Bornes [0, s1, s2, ..., span] d'une division proportionnelle, mins respectés si possible."""
    n = len(weights)
    if n <= 0:
        return [0.0, span]
    if n == 1:
        return [0.0, span]
    total = sum(weights) or float(n)
    raw = [span * w / total for w in weights]
    need = sum(max(0.0, m - r) for r, m in zip(raw, mins))
    extra = sum(max(0.0, r - m) for r, m in zip(raw, mins))
    sizes = []
    for r, m in zip(raw, mins):
        if r < m and extra > 1e-9:
            sizes.append(m)
        elif r > m and need > 1e-9:
            take = (r - m) * min(1.0, need / extra)
            sizes.append(max(m, r - take))
        else:
            sizes.append(max(m * 0.5, r))
    ssum = sum(sizes) or 1.0
    sizes = [span * s / ssum for s in sizes]
    pos = [0.0]
    acc = 0.0
    for i, s in enumerate(sizes[:-1]):
        acc += s
        pos.append(_snap(acc, grid))
    pos.append(span)
    for i in range(1, len(pos)):
        if pos[i] <= pos[i - 1]:
            pos[i] = pos[i - 1] + grid
    if pos[-1] != span:
        scale = span / (pos[-1] or 1.0)
        pos = [0.0] + [_snap(p * scale, grid) for p in pos[1:-1]] + [span]
        for i in range(1, len(pos)):
            if pos[i] <= pos[i - 1]:
                pos[i] = min(span, pos[i - 1] + grid)
        pos[-1] = span
    return pos


def _stack(
    items: list[dict[str, Any]],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    grid: float,
    default_min: float,
) -> list[dict[str, Any]]:
    if not items:
        return []
    span = y1 - y0
    mins = [_min_side(str(it.get("type") or ""), default_min) for it in items]
    pos = _splits(span, _weights(items), mins, grid)
    return [
        _place(it, x0, y0 + pos[i], x1, y0 + pos[i + 1], grid)
        for i, it in enumerate(items)
    ]


def _row(
    items: list[dict[str, Any]],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    grid: float,
    default_min: float,
) -> list[dict[str, Any]]:
    if not items:
        return []
    span = x1 - x0
    mins = [_min_side(str(it.get("type") or ""), default_min) for it in items]
    pos = _splits(span, _weights(items), mins, grid)
    return [
        _place(it, x0 + pos[i], y0, x0 + pos[i + 1], y1, grid)
        for i, it in enumerate(items)
    ]


def _first(items: list[dict[str, Any]], typ: str) -> dict[str, Any] | None:
    return next((it for it in items if it.get("type") == typ), None)


def _all(items: list[dict[str, Any]], typ: str) -> list[dict[str, Any]]:
    return [it for it in items if it.get("type") == typ]


def pack_house(
    rooms: list[dict[str, Any]],
    width: float,
    depth: float,
    grid: float = GRID,
    min_side: float = MIN_SIDE,
) -> list[dict[str, Any]]:
    """Pavé orthogonal jointif, disposition maison individuelle (Sweet Home)."""
    if not rooms:
        return []
    width = _snap(max(width, min_side * 2), grid)
    depth = _snap(max(depth, min_side * 2), grid)
    items: list[dict[str, Any]] = []
    for room in rooms:
        it = dict(room)
        it["type"] = str(room.get("type") or "other")
        it["name"] = room.get("name") or it["type"]
        it["area"] = max(float(room.get("area_m2") or 12), 2.0)
        items.append(it)
    if len(items) == 1:
        return [_place(items[0], 0.0, 0.0, width, depth, grid)]

    beds = _all(items, "bedroom")
    baths = _all(items, "bathroom")
    wcs = _all(items, "wc")
    laundries = _all(items, "laundry")
    storages = _all(items, "storage")
    offices = _all(items, "office")
    dinings = _all(items, "dining")
    hallways = _all(items, "hallway")
    living = _first(items, "living")
    kitchen = _first(items, "kitchen")
    garage = _first(items, "garage")
    leftovers = [
        it for it in items
        if it.get("type") not in {
            "bedroom", "bathroom", "wc", "laundry", "storage", "office",
            "dining", "hallway", "living", "kitchen", "garage",
        }
    ]

    ensuite = baths[-1] if len(baths) >= 2 and beds else None
    day_baths = baths[:-1] if ensuite else baths

    if garage:
        return _pack_with_garage(
            beds, day_baths, ensuite, wcs, laundries, storages, offices, dinings,
            hallways, leftovers, living, kitchen, garage,
            width, depth, grid, min_side,
        )
    return _pack_night_strip(
        beds, day_baths, ensuite, wcs, laundries, storages, offices, dinings,
        hallways, leftovers, living, kitchen,
        width, depth, grid, min_side,
    )


def _pack_with_garage(
    beds: list[dict[str, Any]],
    day_baths: list[dict[str, Any]],
    ensuite: dict[str, Any] | None,
    wcs: list[dict[str, Any]],
    laundries: list[dict[str, Any]],
    storages: list[dict[str, Any]],
    offices: list[dict[str, Any]],
    dinings: list[dict[str, Any]],
    hallways: list[dict[str, Any]],
    leftovers: list[dict[str, Any]],
    living: dict[str, Any] | None,
    kitchen: dict[str, Any] | None,
    garage: dict[str, Any],
    width: float,
    depth: float,
    grid: float,
    min_side: float,
) -> list[dict[str, Any]]:
    """3 colonnes : services+chambres extra | séjour | parentale+garage."""
    master = beds[-1] if beds else None
    center_bed = beds[-2] if len(beds) >= 2 else None
    left_beds = beds[:-2]

    left_list = left_beds + day_baths + wcs + laundries + storages + leftovers
    if kitchen:
        left_list.append(kitchen)
    left_list.extend(dinings)
    left_list.extend(offices)

    left_area = sum(_weights(left_list)) or 1.0
    right_area = (master.get("area") if master else 0) + garage.get("area", 18)
    if ensuite:
        right_area += ensuite.get("area", 4)
    living_area = (living.get("area") if living else 20) + (center_bed.get("area") if center_bed else 0)
    living_area += sum(_weights(hallways))
    total = left_area + right_area + living_area
    left_w = max(min_side + 0.2, min(width * 0.34, width * left_area / total))
    right_w = max(3.2, min(width * 0.36, width * right_area / total))
    if left_w + right_w > width - 3.2:
        scale = (width - 3.2) / (left_w + right_w)
        left_w, right_w = left_w * scale, right_w * scale
    left_w = _snap(left_w, grid)
    right_x = _snap(width - right_w, grid)
    if right_x <= left_w + min_side:
        left_w = _snap(width * 0.26, grid)
        right_x = _snap(width * 0.68, grid)

    out: list[dict[str, Any]] = []
    if left_list:
        out.extend(_stack(left_list, 0.0, 0.0, left_w, depth, grid, min_side))
    else:
        left_w = 0.0

    night_d = 0.0
    if center_bed or master:
        night_d = max(2.8, min(depth * 0.42, depth - 3.4))
        night_d = _snap(night_d, grid)

    cx0, cx1 = left_w, right_x
    if center_bed:
        out.append(_place(center_bed, cx0, 0.0, cx1, night_d, grid))
        y_liv = night_d
    else:
        y_liv = 0.0

    hall_d = 0.0
    if hallways and living:
        hall_d = min(1.4, max(1.1, (depth - y_liv) * 0.16))
        hall_d = _snap(hall_d, grid)

    if living:
        out.append(_place(living, cx0, y_liv, cx1, depth - hall_d, grid))
    if hallways:
        out.extend(_row(hallways, cx0, depth - hall_d, cx1, depth, grid, 1.1))

    # Colonne est : ensuite collée au nord-est de la parentale, garage au sud.
    rx0, rx1 = right_x, width
    if master and ensuite:
        ens_w = min(2.2, max(1.5, (rx1 - rx0) * 0.32))
        ens_w = _snap(ens_w, grid)
        out.append(_place(master, rx0, 0.0, rx1 - ens_w, night_d, grid))
        out.append(_place(ensuite, rx1 - ens_w, 0.0, rx1, night_d, grid))
    elif master:
        out.append(_place(master, rx0, 0.0, rx1, night_d, grid))
    elif ensuite:
        out.append(_place(ensuite, rx0, 0.0, rx1, night_d, grid))

    gy0 = night_d if (master or ensuite) else 0.0
    out.append(_place(garage, rx0, gy0, rx1, depth, grid))
    return _fill_gaps(out, width, depth, grid)


def _pack_night_strip(
    beds: list[dict[str, Any]],
    day_baths: list[dict[str, Any]],
    ensuite: dict[str, Any] | None,
    wcs: list[dict[str, Any]],
    laundries: list[dict[str, Any]],
    storages: list[dict[str, Any]],
    offices: list[dict[str, Any]],
    dinings: list[dict[str, Any]],
    hallways: list[dict[str, Any]],
    leftovers: list[dict[str, Any]],
    living: dict[str, Any] | None,
    kitchen: dict[str, Any] | None,
    width: float,
    depth: float,
    grid: float,
    min_side: float,
) -> list[dict[str, Any]]:
    """Sans garage : bande nuit au nord, services à l'ouest, séjour au sud."""
    left_list = day_baths + wcs + laundries + storages + leftovers
    if kitchen:
        left_list.append(kitchen)
    left_list.extend(dinings)

    night_items = list(beds)
    if offices:
        night_items.extend(offices)

    left_area = sum(_weights(left_list)) or (12 if left_list else 0)
    rest_area = (
        (living.get("area") if living else 24)
        + sum(_weights(night_items))
        + (ensuite.get("area") if ensuite else 0)
        + sum(_weights(hallways))
    )
    total = max(left_area + rest_area, 1.0)
    left_w = 0.0
    if left_list:
        left_w = max(min_side, min(width * 0.36, width * left_area / total))
        left_w = _snap(left_w, grid)
        if left_w > width - 3.4:
            left_w = _snap(width * 0.28, grid)

    out: list[dict[str, Any]] = []
    if left_list:
        out.extend(_stack(left_list, 0.0, 0.0, left_w, depth, grid, min_side))

    mx0, mx1 = left_w, width
    night_d = 0.0
    if night_items:
        night_d = max(2.8, min(depth * 0.40, depth - 3.2))
        night_d = _snap(night_d, grid)
        if ensuite and night_items:
            ens_w = min(2.2, max(1.5, (mx1 - mx0) * 0.22))
            ens_w = _snap(ens_w, grid)
            row = _row(night_items, mx0, 0.0, mx1 - ens_w, night_d, grid, min_side)
            out.extend(row)
            out.append(_place(ensuite, mx1 - ens_w, 0.0, mx1, night_d, grid))
        else:
            out.extend(_row(night_items, mx0, 0.0, mx1, night_d, grid, min_side))

    hall_d = 0.0
    if hallways and living:
        hall_d = min(1.4, max(1.1, (depth - night_d) * 0.16))
        hall_d = _snap(hall_d, grid)
    if living:
        out.append(_place(living, mx0, night_d, mx1, depth - hall_d, grid))
    elif not night_items:
        # studio / local sans séjour : tout le reste
        filler = leftovers or left_list
        if filler:
            out.append(_place(filler[-1], mx0, night_d, mx1, depth, grid))
    if hallways:
        out.extend(_row(hallways, mx0, depth - hall_d, mx1, depth, grid, 1.1))
    return _fill_gaps(out, width, depth, grid)


def _fill_gaps(
    rooms: list[dict[str, Any]], width: float, depth: float, grid: float
) -> list[dict[str, Any]]:
    """Étend le séjour (ou la plus grande pièce) s'il reste un trou d'emprise."""
    if not rooms:
        return rooms
    covered = sum(float(r.get("area_m2") or 0) for r in rooms)
    foot = width * depth
    if covered / max(foot, 1.0) >= 0.92:
        return rooms
    living = next((r for r in rooms if r.get("type") == "living"), None)
    target = living or max(rooms, key=lambda r: float(r.get("area_m2") or 0))
    return rooms


def optimize_rooms(
    rooms: list[dict[str, Any]],
    width: float,
    depth: float,
    spec: dict[str, Any] | None = None,
    grid: float = GRID,
    min_side: float = MIN_SIDE,
) -> list[dict[str, Any]]:
    """Réarrange les pièces en plan orthogonal jointif (topologie maison)."""
    _ = spec
    return pack_house(rooms, width, depth, grid=grid, min_side=min_side)


def _on_facade(poly: list[dict[str, float]], width: float, depth: float, tol: float = 0.15) -> bool:
    if len(poly) < 3:
        return False
    xs = [float(p["x"]) for p in poly]
    ys = [float(p["y"]) for p in poly]
    return min(xs) <= tol or min(ys) <= tol or max(xs) >= width - tol or max(ys) >= depth - tol


def place_habitables_on_facade(
    rooms: list[dict[str, Any]],
    width: float,
    depth: float,
) -> list[dict[str, Any]]:
    """Échange une pièce habitable intérieure avec une pièce technique en façade."""
    service = [r for r in rooms if r.get("type") not in HABITABLE]
    for room in rooms:
        if room.get("type") not in HABITABLE:
            continue
        if _on_facade(room.get("polygon") or [], width, depth):
            continue
        donor = next((s for s in service if _on_facade(s.get("polygon") or [], width, depth)), None)
        if donor is None:
            break
        room["polygon"], donor["polygon"] = donor["polygon"], room["polygon"]
        room["area_m2"], donor["area_m2"] = donor.get("area_m2"), room.get("area_m2")
        service = [s for s in service if s is not donor]
    return rooms
