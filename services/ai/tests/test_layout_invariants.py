"""Étape 0 du chantier de dualisation : caractériser le pavage actuel.

Ce module ne teste pas un comportement voulu, il **fige le comportement
observé** de `pack_house` sur un corpus de programmes résidentiels tirés sous
graine. Il sert deux fins :

  1. un filet de régression — tout nouveau moteur d'implantation devra égaler
     ou battre ces chiffres, sinon la promesse « aussi précis qu'avant » n'est
     pas vérifiable ;
  2. le tableau de référence de l'article.

Le corpus est déterministe (`random.Random(seed)`, bibliothèque standard) :
aucune dépendance ajoutée, et deux exécutions donnent les mêmes programmes.

Pour afficher le tableau :
    python -m services.ai.tests.test_layout_invariants
ou, depuis services/ai :
    python tests/test_layout_invariants.py
"""
from __future__ import annotations

import random
from typing import Any

from app.layout_opt import _min_side, optimize_rooms, pack_house, sanitary_violations
from app.sizing import resize_layout, slicing_tree


# Taille du corpus. 200 programmes suffisent à stabiliser les moyennes au
# centième tout en gardant la suite sous la seconde.
CORPUS_SIZE = 200

# Aires plausibles par type (m²), volontairement large : le corpus doit
# couvrir les briefs maladroits autant que les briefs raisonnables.
_AREA_RANGE = {
    "living": (16.0, 38.0),
    "kitchen": (6.0, 16.0),
    "bedroom": (9.0, 18.0),
    "bathroom": (3.5, 9.0),
    "wc": (1.2, 3.0),
    "hallway": (4.0, 12.0),
    "garage": (12.0, 24.0),
    "dining": (8.0, 18.0),
    "office": (7.0, 14.0),
    "storage": (2.0, 6.0),
    "laundry": (3.0, 7.0),
}


def _program(rng: random.Random) -> dict[str, Any]:
    """Un programme résidentiel déplié : une entrée par pièce, comme `expand_rooms`."""
    rooms: list[dict[str, Any]] = []

    def add(typ: str) -> None:
        lo, hi = _AREA_RANGE[typ]
        rooms.append({
            "id": f"r{len(rooms) + 1}",
            "type": typ,
            "name": typ,
            "area_m2": round(rng.uniform(lo, hi), 1),
        })

    # Noyau : un séjour et une cuisine, comme la garde de cohérence du NLU.
    add("living")
    add("kitchen")
    for _ in range(rng.randint(0, 4)):
        add("bedroom")
    for _ in range(rng.randint(1, 2)):
        add("bathroom")
    for typ in ("wc", "hallway", "garage", "dining", "office", "storage", "laundry"):
        if rng.random() < 0.35:
            add(typ)
    rng.shuffle(rooms)
    return rooms


def _fitted(rng: random.Random) -> dict[str, Any]:
    """Programme dont la parcelle est dimensionnée pour lui.

    Tirer les aires et la parcelle indépendamment produit surtout des
    programmes mal posés : sur un corpus ainsi tiré le ratio médian
    demande/parcelle valait 0,71, et « l'écart aux aires » y mesurait moins la
    qualité de la cotation que le fait de devoir remplir une parcelle trop
    grande — la couverture étant exactement 1,0 par construction. On dimensionne
    donc la parcelle d'après le programme, avec un jeu réaliste de ±15 %.
    """
    rooms = _program(rng)
    demand = sum(float(r["area_m2"]) for r in rooms)
    area = demand / rng.uniform(0.85, 1.15)
    ratio = rng.uniform(0.7, 1.45)  # allongement de la parcelle
    width = (area * ratio) ** 0.5
    return {
        "rooms": rooms,
        "width": round(max(4.0, min(20.0, width)), 1),
        "depth": round(max(4.0, min(20.0, area / max(width, 1e-6))), 1),
    }


def _unfitted(rng: random.Random) -> dict[str, Any]:
    """Programme et parcelle tirés indépendamment : beaucoup de briefs mal posés.

    Gardé pour éprouver les invariants durs, jamais pour mesurer la précision.
    """
    rooms = _program(rng)
    return {
        "rooms": rooms,
        "width": round(rng.uniform(6.0, 18.0), 1),
        "depth": round(rng.uniform(6.0, 18.0), 1),
    }


# Corpus de précision : parcelle ajustée au programme. C'est lui qui porte les
# chiffres de l'article.
CORPUS = [_fitted(random.Random(seed)) for seed in range(CORPUS_SIZE)]

# Corpus de robustesse : programmes mal posés inclus. Seuls les invariants durs
# y sont exigés — un plan reste valide même quand le brief est absurde.
CORPUS_STRESS = [_unfitted(random.Random(10_000 + seed)) for seed in range(CORPUS_SIZE)]


def _bbox(room: dict[str, Any]) -> tuple[float, float, float, float] | None:
    poly = room.get("polygon") or []
    if len(poly) < 3:
        return None
    xs = [float(p["x"]) for p in poly]
    ys = [float(p["y"]) for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _is_rect(room: dict[str, Any]) -> bool:
    poly = room.get("polygon") or []
    if len(poly) != 4:
        return False
    xs = {round(float(p["x"]), 4) for p in poly}
    ys = {round(float(p["y"]), 4) for p in poly}
    return len(xs) == 2 and len(ys) == 2


def measure(
    program: dict[str, Any], *, grid: float, min_side: float,
    via_optimize: bool = False, resize: bool = False, guard: bool = True,
) -> dict[str, Any]:
    """Pave un programme et renvoie ses métriques d'invariants et de précision.

    `via_optimize` emprunte `optimize_rooms`, l'entrée réellement appelée par
    l'étage d'adaptation. Elle ne fait aujourd'hui que déléguer à `pack_house` ;
    passer par elle garantit que le test le détecte si ça change.
    """
    width, depth = program["width"], program["depth"]
    rooms = [dict(r) for r in program["rooms"]]
    targets = {r["id"]: float(r["area_m2"]) for r in rooms}
    if via_optimize:
        packed = optimize_rooms(rooms, width, depth, None, grid=grid, min_side=min_side)
    else:
        packed = pack_house(rooms, width, depth, grid=grid, min_side=min_side)
    if resize:
        resize_layout(
            packed, width, depth, targets=targets, grid=grid, min_side=min_side,
            only_if_better=guard,
        )

    boxes = [(r, _bbox(r)) for r in packed]
    boxes = [(r, b) for r, b in boxes if b is not None]

    overlap = 0.0
    for i, (_, a) in enumerate(boxes):
        for _, b in boxes[i + 1 :]:
            ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
            iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
            overlap += ix * iy

    oob = 0.0
    for _, (x0, y0, x1, y1) in boxes:
        inx = max(0.0, min(x1, width) - max(x0, 0.0))
        iny = max(0.0, min(y1, depth) - max(y0, 0.0))
        oob += max(0.0, (x1 - x0) * (y1 - y0) - inx * iny)

    covered = sum((b[2] - b[0]) * (b[3] - b[1]) for _, b in boxes)

    thin = 0
    for room, (x0, y0, x1, y1) in boxes:
        want = _min_side(str(room.get("type") or ""), min_side)
        if min(x1 - x0, y1 - y0) + 1e-6 < want:
            thin += 1

    # Écart aux aires demandées, sur les seules pièces du programme d'entrée :
    # `pack_house` peut ajouter un couloir (`_ensure_hallway`), qui n'a pas de
    # cible à respecter.
    errs = []
    for room, (x0, y0, x1, y1) in boxes:
        target = targets.get(room.get("id"))
        if target:
            errs.append(abs((x1 - x0) * (y1 - y0) - target))

    placed = {r.get("id") for r, _ in boxes}
    missing = [rid for rid in targets if rid not in placed]

    return {
        "overlap_m2": overlap,
        "oob_m2": oob,
        "coverage": covered / max(width * depth, 1e-9),
        "non_rect": sum(1 for r in packed if not _is_rect(r)),
        "thin_rooms": thin,
        "area_mae": (sum(errs) / len(errs)) if errs else 0.0,
        "missing_rooms": len(missing),
        "sanitary": len(sanitary_violations(packed)),
        "rooms_in": len(targets),
        "rooms_out": len(boxes),
    }


def _aggregate(**cfg: Any) -> dict[str, float]:
    rows = [measure(p, **cfg) for p in CORPUS]
    n = float(len(rows))
    return {
        "overlap_max": max(r["overlap_m2"] for r in rows),
        "overlap_mean": sum(r["overlap_m2"] for r in rows) / n,
        "oob_max": max(r["oob_m2"] for r in rows),
        "coverage_mean": sum(r["coverage"] for r in rows) / n,
        "coverage_min": min(r["coverage"] for r in rows),
        "non_rect_total": sum(r["non_rect"] for r in rows),
        "thin_mean": sum(r["thin_rooms"] for r in rows) / n,
        "thin_max": max(r["thin_rooms"] for r in rows),
        "area_mae_mean": sum(r["area_mae"] for r in rows) / n,
        "area_mae_max": max(r["area_mae"] for r in rows),
        "missing_total": sum(r["missing_rooms"] for r in rows),
        "sanitary_mean": sum(r["sanitary"] for r in rows) / n,
        "sanitary_clean": sum(1 for r in rows if r["sanitary"] == 0) / n,
    }


# Les deux réglages réellement en production : l'étage d'implantation appelle
# `pack_house` avec min_side=1.6, l'étage d'adaptation passe par
# `optimize_rooms` avec min_side=2.0.
GENERATE = {"grid": 0.1, "min_side": 1.6}
ADAPT = {"grid": 0.1, "min_side": 2.0, "via_optimize": True}
SIZED = {"grid": 0.1, "min_side": 1.6, "resize": True}
# Cotation sans garde d'acceptation : sert à vérifier que le chemin brut est
# géométriquement sain. Sans ce réglage, la garde masquerait un bug de coupe.
SIZED_RAW = {"grid": 0.1, "min_side": 1.6, "resize": True, "guard": False}


# --- Invariants durs -------------------------------------------------------
# Ce sont les garanties « par construction » revendiquées par l'article. Elles
# ne tolèrent aucun écart : une seule violation est un bug, pas une dérive.

def test_no_overlap_on_corpus():
    for program in CORPUS:
        m = measure(program, **GENERATE)
        assert m["overlap_m2"] < 1e-9, (
            f"chevauchement {m['overlap_m2']:.3f} m² sur "
            f"{program['width']}x{program['depth']} ({m['rooms_in']} pièces)"
        )


def test_stays_within_envelope_on_corpus():
    for program in CORPUS:
        m = measure(program, **GENERATE)
        assert m["oob_m2"] < 1e-6, f"{m['oob_m2']:.4f} m² hors emprise"


def test_all_rooms_are_axis_aligned_rectangles():
    for program in CORPUS:
        m = measure(program, **GENERATE)
        assert m["non_rect"] == 0


def test_no_room_is_silently_dropped():
    for program in CORPUS:
        m = measure(program, **GENERATE)
        assert m["missing_rooms"] == 0, (
            f"{m['missing_rooms']} pièce(s) perdue(s) sur {m['rooms_in']}"
        )


def test_adapt_settings_hold_the_same_invariants():
    for program in CORPUS:
        m = measure(program, **ADAPT)
        assert m["overlap_m2"] < 1e-9
        assert m["oob_m2"] < 1e-6
        assert m["missing_rooms"] == 0


def test_invariants_survive_ill_posed_briefs():
    """Un brief absurde doit produire un plan laid, jamais un plan invalide."""
    for program in CORPUS_STRESS:
        m = measure(program, **GENERATE)
        assert m["overlap_m2"] < 1e-9
        assert m["oob_m2"] < 1e-6
        assert m["non_rect"] == 0
        assert m["missing_rooms"] == 0


def test_packer_is_deterministic():
    """Aucun aléa aujourd'hui : deux appels identiques donnent le même pavage.

    Ce test échouera dès l'introduction d'une graine — c'est voulu : il faudra
    alors le reformuler en « déterministe à graine fixée », ce qui est la
    propriété que l'article revendique.
    """
    program = CORPUS[0]
    first = measure(program, **GENERATE)
    second = measure(program, **GENERATE)
    assert first == second


def test_corpus_is_reproducible():
    """Les corpus eux-mêmes ne doivent pas bouger d'une exécution à l'autre."""
    assert [_fitted(random.Random(s)) for s in range(CORPUS_SIZE)] == CORPUS
    assert [_unfitted(random.Random(10_000 + s)) for s in range(CORPUS_SIZE)] == CORPUS_STRESS


# --- Garde-fous de référence ----------------------------------------------
# Bornes calées juste au-delà des valeurs mesurées sur le moteur actuel. Elles
# n'expriment pas un objectif mais un seuil de non-régression : si un chiffre
# les franchit, c'est que le comportement a changé.

def test_baseline_coverage_does_not_regress():
    agg = _aggregate(**GENERATE)
    assert agg["coverage_mean"] >= 0.999, agg["coverage_mean"]


def test_baseline_area_error_does_not_regress():
    agg = _aggregate(**GENERATE)
    assert agg["area_mae_mean"] <= 4.5, agg["area_mae_mean"]


def test_baseline_sanitary_does_not_regress():
    agg = _aggregate(**GENERATE)
    assert agg["sanitary_clean"] >= 0.96, agg["sanitary_clean"]


def test_baseline_thin_rooms_does_not_regress():
    agg = _aggregate(**GENERATE)
    assert agg["thin_mean"] <= 3.8, agg["thin_mean"]


# --- Étape 4 : la cotation ------------------------------------------------

def test_every_layout_is_sliceable():
    """La reconnaissance de l'arbre doit couvrir tout ce que le pavage produit.

    Si ce test tombe, c'est qu'une configuration non sliçable est apparue : la
    cotation la laisse alors intacte (aucune perte), mais l'étape 3b devient
    nécessaire pour la couvrir.
    """
    for program in CORPUS:
        rooms = [dict(r) for r in program["rooms"]]
        packed = pack_house(rooms, program["width"], program["depth"], grid=0.1, min_side=1.6)
        assert slicing_tree(packed, program["width"], program["depth"]) is not None


def test_sizing_preserves_hard_invariants():
    """La cotation ne déplace que des coupes : la partition reste exacte."""
    for program in CORPUS:
        m = measure(program, **SIZED)
        assert m["overlap_m2"] < 1e-9, m["overlap_m2"]
        assert m["oob_m2"] < 1e-6, m["oob_m2"]
        assert m["non_rect"] == 0
        assert m["missing_rooms"] == 0
        assert m["coverage"] > 0.999, m["coverage"]


def test_sizing_preserves_invariants_on_ill_posed_briefs():
    for program in CORPUS_STRESS:
        m = measure(program, **SIZED)
        assert m["overlap_m2"] < 1e-9
        assert m["oob_m2"] < 1e-6
        assert m["missing_rooms"] == 0


def test_raw_sizing_is_geometrically_sound():
    """Sans la garde d'acceptation, la cotation doit rester une partition exacte."""
    for program in CORPUS:
        m = measure(program, **SIZED_RAW)
        assert m["overlap_m2"] < 1e-9, m["overlap_m2"]
        assert m["oob_m2"] < 1e-6, m["oob_m2"]
        assert m["non_rect"] == 0
        assert m["coverage"] > 0.999, m["coverage"]


def test_sizing_never_regresses():
    """La garde d'acceptation interdit toute dégradation, sur les deux critères."""
    base = _aggregate(**GENERATE)
    sized = _aggregate(**SIZED)
    assert sized["area_mae_mean"] <= base["area_mae_mean"]
    assert sized["thin_mean"] <= base["thin_mean"]
    assert sized["thin_max"] <= base["thin_max"]


def test_sizing_reduces_area_error():
    """Gain livré, garde active : ~11 % sur l'écart moyen aux aires."""
    before = _aggregate(**GENERATE)["area_mae_mean"]
    after = _aggregate(**SIZED)["area_mae_mean"]
    assert after < before * 0.92, f"{before:.3f} -> {after:.3f}"


def test_sizing_never_adds_a_sanitary_violation():
    """La garde d'acceptation compte les adjacences interdites en premier."""
    base = _aggregate(**GENERATE)
    sized = _aggregate(**SIZED)
    assert sized["sanitary_mean"] <= base["sanitary_mean"]
    assert sized["sanitary_clean"] >= base["sanitary_clean"]


def test_sizing_potential_once_topology_improves():
    """Gain accessible sans la garde : ~34 %.

    L'écart entre ce chiffre et celui du test précédent mesure ce que la
    topologie actuelle coûte — elle bloque la cotation sur 54 % des plans, en
    empilant trop de pièces côte à côte pour que les côtés minimaux tiennent.
    C'est l'argument chiffré des étapes 3a / 3b du chantier.
    """
    before = _aggregate(**GENERATE)["area_mae_mean"]
    raw = _aggregate(**SIZED_RAW)["area_mae_mean"]
    assert raw < before * 0.70, f"{before:.3f} -> {raw:.3f}"


def _report() -> str:
    lines = ["", f"Corpus : {CORPUS_SIZE} programmes, graines 0..{CORPUS_SIZE - 1}", ""]
    for label, cfg in (
        ("implantation", GENERATE),
        ("implantation + cotation", SIZED),
        ("cotation sans garde", SIZED_RAW),
        ("adaptation", ADAPT),
    ):
        agg = _aggregate(**cfg)
        lines.append(f"--- {label}")
        for key in sorted(agg):
            lines.append(f"  {key:<20} {agg[key]:.4f}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(_report())
