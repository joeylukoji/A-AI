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


# --- Conventions de façade du dessin -----------------------------------------
# `diffusion.default_openings` pose l'entrée et la porte de garage à des endroits
# FIXES, qu'aucun plan ne peut ignorer sans que la porte ouvre sur la mauvaise
# pièce : l'entrée sur le mur sud, la porte de garage sur le mur est. Un plan qui
# met des chambres au sud aurait son porche devant elles ; un garage à l'ouest
# aurait sa porte de garage devant le séjour.
#
# On les déclare ici plutôt que de généraliser `default_openings` : les partis
# s'y conforment. Des tests comparent ces déclarations au comportement réel de
# `default_openings` et échoueront le jour où il sera généralisé, signe qu'il
# faut alors assouplir ces règles.

# Pièces devant lesquelles l'entrée peut s'ouvrir. Tête de `diffusion._ENTRANCE_ORDER`
# (couloir, séjour, salle à manger) : cuisine, bureau et garage y figurent aussi
# comme dernier recours, mais aucun plan ne veut d'une entrée par la cuisine.
ENTRANCE_TYPES: tuple[str, ...] = ("hallway", "living", "dining")
# Longueur minimale de mur sud devant une de ces pièces (`_entrance_offset`).
MIN_ENTRANCE_SPAN = 1.1


def garage_door_span(depth: float) -> tuple[float, float]:
    """Intervalle des ordonnées de la porte de garage sur le mur est.

    Même formule que `diffusion.default_openings`, qui ne pose cette porte que
    si le mur est fait au moins 2,4 m ; en dessous, aucune porte n'est posée et
    l'intervalle est vide.
    """
    if depth < 2.4:
        return (0.0, 0.0)
    offset = max(0.4, min(depth - 2.6, depth * 0.55))
    return (offset, offset + min(2.4, depth * 0.45))


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
