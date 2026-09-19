"""Règles de distribution résidentielle, déclarées une fois, en données.

Avant ce module, les mêmes règles étaient écrites à plusieurs endroits :
`sanitary_violations` (contrôle a posteriori), `_FORBIDDEN_ADJACENCY` et
`_NEEDS_CIRCULATION` (recopiés pour le découpage en colonnes), `HABITABLE`
(deux copies, dans `layout_opt` et `compliance`). Une règle ajoutée à un seul
endroit faisait dériver le générateur de son contrôleur, sans qu'aucun test ne
le voie.

Ce module n'importe rien : ce sont des données. Le contrôleur les interprète
(`layout_opt.sanitary_violations`) et le générateur les lit
(`layout_opt._forbidden_count`, `layout_zones`) — une seule source de vérité.

Les noms des écarts (`wc_kitchen`, …) sont un contrat : `compliance` les teste
par appartenance (`"wc_kitchen" in issues`) et les libellés de l'interface s'y
rattachent.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ForbiddenPair:
    """Un mur commun est interdit entre un type de `left` et un type de `right`.

    `per_room` fixe le comptage, hérité du contrôleur d'origine et conservé à
    l'identique parce que `pack_house` compare `len(issues)` entre deux essais :
      * True  — un écart par pièce de `left` fautive ;
      * False — un seul écart pour l'ensemble du plan.
    """

    name: str
    left: frozenset[str]
    right: frozenset[str]
    per_room: bool


@dataclass(frozen=True)
class NeedsHall:
    """Chaque pièce de ces types doit partager un mur avec un couloir.

    Ne s'applique que si le plan a un couloir : sans couloir, la circulation est
    assurée autrement (`compliance` vérifie l'accessibilité par ailleurs).
    """

    name: str
    types: frozenset[str]


_KITCHEN = frozenset({"kitchen", "dining"})

# L'ORDRE est celui dans lequel le contrôleur d'origine émettait les écarts.
RULES: tuple[ForbiddenPair | NeedsHall, ...] = (
    ForbiddenPair("wc_kitchen", frozenset({"wc"}), _KITCHEN, per_room=True),
    ForbiddenPair("kitchen_bath", frozenset({"bathroom"}), _KITCHEN, per_room=True),
    ForbiddenPair("bedroom_living", frozenset({"bedroom"}), frozenset({"living"}), per_room=True),
    NeedsHall("bedroom_hall", frozenset({"bedroom"})),
    NeedsHall("wc_hall", frozenset({"wc"})),
    ForbiddenPair("wc_bedroom", frozenset({"wc"}), frozenset({"bedroom"}), per_room=False),
)

# Règle « pièces habitables sur façade » (poids 12 dans `compliance`).
HABITABLE_TYPES: frozenset[str] = frozenset({"living", "bedroom", "dining", "office"})

# Pièces d'eau et de service (usage courant ; aucune règle d'adjacence propre).
WET_TYPES: frozenset[str] = frozenset({"bathroom", "wc", "laundry", "storage"})


def forbidden_pairs() -> tuple[tuple[frozenset[str], frozenset[str]], ...]:
    """Les paires (types, types) dont le mur commun est interdit, dans l'ordre des règles."""
    return tuple((r.left, r.right) for r in RULES if isinstance(r, ForbiddenPair))


def types_needing_hall() -> frozenset[str]:
    """Types qui doivent toucher le couloir."""
    out: set[str] = set()
    for rule in RULES:
        if isinstance(rule, NeedsHall):
            out |= rule.types
    return frozenset(out)
