# Sprint — ouvertures et cotations intérieures 2D

Statut : **terminé** — 27 septembre 2026  
Plan exécutable :
[`plan/refactor-editor-openings-dimensions-1.md`](../../plan/refactor-editor-openings-dimensions-1.md)

## Objectif

Extraire les menuiseries hors du renderer de murs, professionnaliser portes et
fenêtres, puis enrichir les labels des pièces rectangulaires avec leurs
dimensions exactes sans réduire la lisibilité ni recouvrir le mobilier.

## Baseline et critères

- Baseline : `benchmark/runs/editor-presentation-v2`.
- 38 vues appariées sur les mêmes six documents gelés.
- Données de plan strictement inchangées et aucune requête réseau.
- Régression médiane de rendu inférieure ou égale à 10 %.
- Tests Node, benchmark, Ruff, Go et diff-check obligatoires.
- Revue Standards et revue Spec obligatoires avant clôture.

## Décisions d’architecture

- `plan-style-walls.js` reste responsable de la seule maçonnerie.
- `plan-style-openings.js` devient responsable des menuiseries.
- `plan-style-annotations.js` conserve les dimensions intérieures car elles font
  partie du label sémantique et réutilisent son placement anti-collision.
- Les tapis sont des revêtements de sol non bloquants ; seuls les objets
  volumétriques déclenchent le déplacement ou le repli du label.
- Le sens de charnière n’est pas inventé : PlanDocument 1.0 ne le décrit pas.

## Résultat

- Portes : réservation, jambages, seuil, battant, articulation et arc.
- Fenêtres : vitrage, deux rails, jambages, appui et meneau adaptatif.
- Dimensions intérieures exactes pour les rectangles orthogonaux hors couloirs.
- Repli anti-collision : dimensions, puis surface, puis nom.
- Ordre des modules vérifié entre navigateur, Node et benchmark.

Le [rapport final](../../benchmark/comparisons/editor-openings-dimensions/report.md)
compare 38 vues : 38/38 documents identiques, 6/6 entrées identiques, zéro
réseau et 564/564 assets chargés. La médiane de rendu passe de 352,75 à
357,25 ms, soit **+1,28 %**.

Validation : **78 tests JavaScript**, **103 tests benchmark**, Go HTTP, Ruff et
diff-check réussis. Les revues Standards et Spec des blocs sont closes sans
finding technique ou fonctionnel.

