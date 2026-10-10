# Sprint — sens explicite des portes 2D

Statut : **en cours** — 28 septembre 2026  
Plan exécutable :
[`plan/feature-editor-door-semantics-1.md`](../../plan/feature-editor-door-semantics-1.md)

## Objectif

Remplacer la convention implicite du battant par deux propriétés optionnelles,
validées, générées et éditables : point de charnière et côté de débattement.

## Référentiel

- `hinge=start|end` désigne une extrémité de l’intervalle d’ouverture mesuré
  depuis le point `a` du mur.
- `swing=positive` utilise la normale gauche `(-uy, ux)` du mur `a→b` ;
  `negative` utilise la normale opposée.
- Les anciens documents sans ces champs restent valides et utilisent
  `start/positive` uniquement au rendu.

## Critères

- Contrat Python/Go/JSON Schema cohérent.
- Génération déterministe fondée sur la pièce desservie.
- Renderer et zones de mobilier géométriquement identiques.
- Cycle des quatre configurations avec undo dans l’éditeur.
- Baseline historique inchangée, benchmark spécifique des quatre variantes.

