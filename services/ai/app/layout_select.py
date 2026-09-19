"""Politique de sélection des partis, et interrupteur de leur branchement.

`layout_partis` sait produire des plans valides ; ce module CHOISIT entre eux, et
décide si le pipeline s'en sert.

**Choisir.** Chaque parti réalisable reçoit un score (plus petit = meilleur) qui
mesure ce que le contrôle exact ne dit pas : pièces sous leur côté minimal, écart
aux aires demandées, boyaux (pièces d'habitation très allongées), part de
circulation. La conformité n'y entre PAS : elle est déjà garantie par le contrôle
exact (aucune régression face au classique), et la mettre aussi dans l'objectif
ferait de tout chiffre de conformité rapporté un chiffre sans valeur.

Le meilleur plan serait toujours le même pour un même programme : c'est
précisément le défaut à corriger. On tire donc, à graine fixée, parmi les ARRANGEMENTS
« quasi-meilleurs » (dans une fenêtre `tolerance()` du meilleur score) : la qualité reste
bornée, et deux graines donnent deux maisons différentes quand il en existe.

Il n'en existe pas toujours. Mesuré sur 57 programmes et 12 graines, un tiers n'a qu'un
seul arrangement dont les pièces respectent leur côté minimal : la variété est forte pour
les maisons petites ou moyennes, faible pour un grand programme sur une parcelle modeste.
Le curseur `LAYOUT_TOLERANCE` arbitre entre qualité et variété.

**Retoucher.** Le plan mémorise la graine et l'arrangement retenu
(`layout = {"parti", "seed", "arr"}`). Une retouche (« ajoute une chambre ») refait le
pavage : sans `arr`, la graine seule tirerait un autre arrangement et redessinerait
toute la maison. On préfère donc l'arrangement mémorisé s'il existe encore, tant qu'il
reste à une distance raisonnable du meilleur score.

**Brancher.** `LAYOUT_VARIANTS` vaut `off` (défaut : rien ne change), `shadow` (on calcule
et on journalise, le plan reste celui d'avant) ou `on` (le plan généré porte un parti).
La graine est choisie à la GÉNÉRATION seulement : une adaptation ou une retouche relit celle
du plan, elle n'en tire jamais une nouvelle.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any

from . import layout_opt as lo
from . import layout_partis as lp
from .layout_opt import PartiUnavailable, register_parti

LOG = logging.getLogger("aai.layout")

# Poids du score.
W_THIN = 1.0            # par pièce sous son côté minimal
W_MAE = 0.25            # par m² d'écart moyen aux aires demandées
W_ASPECT = 0.6          # par unité d'allongement au-delà de ASPECT_OK
W_CIRCULATION = 2.0     # par tranche de 5 points de circulation au-delà de CIRCULATION_OK
STRICT_BONUS = 0.25     # un arrangement strict évite les contacts délicats par construction
ASPECT_OK = 2.5         # rapport grand côté / petit côté toléré pour une pièce d'habitation
CIRCULATION_OK = 0.12   # part du plan occupée par le couloir : 8 à 12 % dans un plan courant
TOLERANCE = 1.0         # fenêtre des « quasi-meilleurs » dans laquelle la graine tire (LAYOUT_TOLERANCE)
MAX_TOLERANCE = 20.0
PREFER_TOLERANCE = 2.0  # l'arrangement mémorisé est repris s'il est à moins de 2 points du meilleur
MAX_CLASSES = 48        # borne sur le travail d'un programme riche (un nombre, pas un délai)

# Pièces où un long boyau est un défaut. Le garage et les pièces d'eau peuvent être allongés.
_ASPECT_TYPES = {"living", "bedroom", "dining", "office", "kitchen"}


# --- Score -------------------------------------------------------------------

def _dims(room: dict[str, Any]) -> tuple[float, float]:
    x0, y0, x1, y1 = lp._bbox(room)
    return x1 - x0, y1 - y0


def aspect_penalty(rooms: list[dict[str, Any]]) -> float:
    """Somme, sur les pièces d'habitation, de l'allongement au-delà de `ASPECT_OK`."""
    total = 0.0
    for room in rooms:
        if room["type"] not in _ASPECT_TYPES:
            continue
        w, h = _dims(room)
        short = min(w, h)
        if short > 1e-9:
            total += max(0.0, max(w, h) / short - ASPECT_OK)
    return total


def circulation_penalty(rooms: list[dict[str, Any]]) -> float:
    """Tranches de 5 points de couloir au-delà de `CIRCULATION_OK`."""
    total = hall = 0.0
    for room in rooms:
        w, h = _dims(room)
        total += w * h
        if room["type"] == "hallway":
            hall += w * h
    return max(0.0, hall / total - CIRCULATION_OK) / 0.05 if total > 0 else 0.0


def area_error(rooms: list[dict[str, Any]], targets: dict[Any, float]) -> float:
    """Écart moyen (m²) aux aires demandées, sur les pièces qui en ont une."""
    errs = [abs(w * h - targets[r.get("id")]) for r in rooms if r.get("id") in targets for w, h in [_dims(r)]]
    return sum(errs) / len(errs) if errs else 0.0


def score(real: lp.Realization, targets: dict[Any, float]) -> float:
    """Plus petit est meilleur. Ne contient aucun terme de conformité (cf. docstring du module)."""
    return (
        W_THIN * real.thin
        + W_MAE * area_error(real.rooms, targets)
        + W_ASPECT * aspect_penalty(real.rooms)
        + W_CIRCULATION * circulation_penalty(real.rooms)
        - (STRICT_BONUS if real.strict else 0.0)
    )


# --- Sélection ------------------------------------------------------------------

def tolerance() -> float:
    """Fenêtre des quasi-meilleurs : `LAYOUT_TOLERANCE` si elle est valide, sinon `TOLERANCE`.

    C'est le curseur entre qualité et variété. À 1,0 (défaut) une maison régénérée ne change que
    si une alternative est presque aussi bonne : pour un programme qui n'a qu'un arrangement
    respectant les côtés minimaux, elle reste la même. Monter la valeur accepte des alternatives
    plus étroites (à 5, des pièces sous leur minimum) pour plus de variété.
    """
    try:
        value = float(os.getenv("LAYOUT_TOLERANCE", ""))
    except ValueError:
        return TOLERANCE
    return value if 0.0 <= value <= MAX_TOLERANCE else TOLERANCE


def pool(rooms: list[dict[str, Any]], width: float, depth: float, *,
         grid: float = 0.1, min_side: float = 1.6) -> list[lp.Realization]:
    """Partis réalisables d'un programme (un par classe, borné par `MAX_CLASSES`)."""
    return lp.realizations(rooms, width, depth, grid=grid, min_side=min_side, max_classes=MAX_CLASSES)


def pick(candidates: list[lp.Realization], targets: dict[Any, float], *, seed: int,
         prefer: str | None = None) -> lp.Realization | None:
    """Choisit un parti : l'arrangement mémorisé s'il tient encore, sinon un quasi-meilleur tiré."""
    if not candidates:
        return None
    scored = sorted(((score(r, targets), i, r) for i, r in enumerate(candidates)), key=lambda t: (t[0], t[1]))
    best = scored[0][0]
    if prefer:
        for s, _, r in scored:
            if r.raw_code == prefer and s <= best + PREFER_TOLERANCE:
                return r
    # On tire parmi les ARRANGEMENTS distincts de la fenêtre, pas parmi les plans : un même
    # arrangement fournit souvent plusieurs plans (adjacences mineures différentes), qui
    # seraient sinon tirés plus souvent et se ressembleraient d'une graine à l'autre.
    groups: dict[str, list[lp.Realization]] = {}
    window = best + tolerance()
    for s, _, r in scored:
        if s <= window:
            groups.setdefault(r.code, []).append(r)      # déjà triés du meilleur au moins bon
    codes = sorted(groups)
    return groups[codes[random.Random(seed).randrange(len(codes))]][0]


def select(rooms: list[dict[str, Any]], width: float, depth: float, *, seed: int,
           prefer: str | None = None, grid: float = 0.1, min_side: float = 1.6) -> lp.Realization | None:
    """Le parti retenu pour ce programme et cette graine, ou None si aucun n'est réalisable."""
    return pick(pool(rooms, width, depth, grid=grid, min_side=min_side), lp._targets(rooms), seed=seed, prefer=prefer)


@register_parti("zoned")
def _zoned(rooms: list[dict[str, Any]], width: float, depth: float, grid: float, min_side: float,
           variant: dict[str, Any]) -> list[dict[str, Any]]:
    """Parti « zones » : signature attendue par `layout_opt.pack_house`."""
    chosen = select(rooms, width, depth, seed=variant["seed"], prefer=variant.get("arr"),
                    grid=grid, min_side=min_side)
    if chosen is None:
        raise PartiUnavailable("aucun arrangement de zones valide pour ce plan")
    out = [dict(r) for r in chosen.rooms]           # copies : on annote sans toucher la réalisation
    for room in out:
        room["_arr"] = chosen.raw_code              # lu (et retiré) par `plan_adapt.adapt`
    return out


# --- Interrupteur -----------------------------------------------------------------

def mode() -> str:
    """`off` (défaut), `shadow` ou `on`, lu dans `LAYOUT_VARIANTS`. Toute autre valeur : `off`."""
    value = (os.getenv("LAYOUT_VARIANTS") or "off").strip().lower()
    if value in {"on", "1", "true", "yes"}:
        return "on"
    return "shadow" if value == "shadow" else "off"


def choose_variant(constraints: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Descripteur du parti d'une génération, ou None (drapeau éteint : le plan reste classique).

    La graine est tirée ici, à la génération, dans cet ordre : `constraints["layout_seed"]`,
    la variable d'environnement `LAYOUT_SEED` (le pipeline ne transmet pas les contraintes
    inconnues jusqu'ici ; c'est le canal des tests et des reproductions), sinon le hasard.
    Une adaptation ou une retouche relit celle du plan, elle n'appelle jamais cette fonction.
    """
    if mode() != "on":
        return None
    seed = (constraints or {}).get("layout_seed")
    if _valid_seed(seed):
        return {"parti": "zoned", "seed": seed}
    try:
        env_seed = int(os.getenv("LAYOUT_SEED", ""))
    except ValueError:
        env_seed = None
    if _valid_seed(env_seed):
        return {"parti": "zoned", "seed": env_seed}
    return {"parti": "zoned", "seed": random.SystemRandom().randrange(lo._MAX_SEED + 1)}


def _valid_seed(seed: Any) -> bool:
    return isinstance(seed, int) and not isinstance(seed, bool) and 0 <= seed <= lo._MAX_SEED


def shadow(layout: dict[str, Any], spec: dict[str, Any]) -> None:
    """Mode ombre : calcule le parti qu'on aurait choisi et le journalise. Ne change RIEN au plan.

    Ne lève jamais : un défaut du calcul d'ombre ne doit pas faire échouer une génération.
    """
    if mode() != "shadow":
        return
    try:
        program = [
            {"id": r.get("id"), "type": r.get("type"), "name": r.get("name"),
             "area_m2": r.get("area") or r.get("area_m2")}
            for r in (layout.get("rooms") or []) if isinstance(r, dict)
        ]
        width, depth = float(layout.get("width") or 0), float(layout.get("depth") or 0)
        started = time.perf_counter()
        candidates = pool(program, width, depth)
        chosen = pick(candidates, lp._targets(program), seed=0)
        LOG.info(json.dumps({
            "event": "layout_shadow",
            "classes": len(candidates),
            "distinct_arrangements": len({c.code for c in candidates}),
            "picked": chosen.raw_code if chosen else None,
            "thin_classic": lp.thin_count([r for r in layout.get("rooms") or [] if isinstance(r, dict) and r.get("polygon")], 1.6),
            "thin_zoned": chosen.thin if chosen else None,
            "ms": round(1000 * (time.perf_counter() - started)),
        }))
    except Exception as exc:  # noqa: BLE001 - l'ombre ne doit jamais casser la génération
        LOG.warning("layout_shadow failed: %r", exc)
