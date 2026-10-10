---
goal: Rendre les portes et fenêtres 2D fidèles à leur segment de mur et plus lisibles
version: 1.0
date_created: 2026-09-24
last_updated: 2026-09-24
owner: Équipe A-AI
status: Completed
tags: [design, editor, 2d, openings, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Ce sous-sprint termine une partie de `TASK-012` dans l'éditeur 2D : géométrie
des baies, lecture des fenêtres et dessin des battants. Référence appariée :
`benchmark/runs/3c-interactions-v1` (six documents, 38 captures). Les images
Gemini, le PNG Pillow et la 3D restent hors périmètre.

## 1. Requirements & Constraints

- **REQ-001**: Dans `web/static/js/plan-style-walls.js:drawOpenings`, borner
  `offset_m` et `width_m` à la longueur réelle du mur ; si la portion visible
  est nulle ou les nombres sont invalides, ne dessiner aucune baie. Le rayon
  d'arc d'une porte doit égaler la largeur effectivement visible, pas la
  largeur demandée hors du mur.
- **REQ-002**: Garder la porte comme trou dans le mur, battant et arc fin à
  90° selon la convention existante. Aucun sens d'ouverture n'est stocké dans
  `PlanDocument` : ne pas inventer charnière gauche/droite ni rôle d'entrée.
- **REQ-003**: Dessiner une fenêtre comme une baie claire avec vitrage bleu
  pâle centré dans l'épaisseur du mur, deux rails fins et deux jambages aux
  extrémités, y compris sur un mur inversé ou vertical. Tous les détails
  doivent suivre le vecteur tangent/normal de la baie. Pour ce sprint, fixer
  la teinte du vitrage à `#dcebf2`, sa demi-largeur projetée à
  `min(0,22 × épaisseur du mur, 2,5 px)`, les rails aux faces du mur et
  les jambages seulement si la baie projetée atteint 6 px. La séquence
  enregistrée comprend alors le trou, les deux rails, le trait central bleu
  et les deux jambages (six traits) ; sans jambages, quatre traits.
- **REQ-004**: Seuls les types `door` et `window` du schéma sont rendus ; ne
  jamais traiter un type inconnu comme une porte. `PlanDocument`, offsets,
  largeurs, murs et ordre des couches restent inchangés.
- **CON-001**: Le changement reste dans le module pur `PlanStyleWalls` ; la
  façade, l'éditeur, l'API et le schéma ne changent pas.
- **CON-002**: Tests rouges avant chaque bloc, revue Standards/Spec après
  chaque bloc, puis comparaison des 38 PNG et six JSON sur la même matrice.
- **PAT-001**: Une seule résolution géométrique des bornes `start/end` alimente
  le trou, les rails, jambages et l'arc ; éviter des largeurs contradictoires.

## 2. Implementation Steps

### Implementation Phase 1 — Bornes et validation des baies

- **GOAL-001**: Supprimer les symboles de portes/fenêtres hors du segment
  stocké sans toucher aux données.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Ajouter des tests Node rouges dans `web/tests/plan-style-walls.test.cjs` : porte dont la largeur dépasse le bout du mur, ouverture totalement hors mur, largeur invalide/zéro, type inconnu et mur inversé. Vérifier coordonnées du trou, rayon de l'arc, absence de commande et non-mutation. | Oui | 2026-09-24 |
| TASK-002 | Implémenter une résolution bornée dans `drawOpenings` ; utiliser la longueur projetée réelle pour l'arc ; garder le rendu nominal des baies valides et `drawWalls` inchangés. | Oui | 2026-09-24 |
| TASK-003 | Revue Standards/Spec, suites Node ciblées, capture `benchmark/runs/3c-openings-bounds-v1`, comparaison appariée des 38 PNG et six JSON à `3c-interactions-v1`, analyse des cas effectivement modifiés. | Oui | 2026-09-24 |

### Implementation Phase 2 — Vitrage lisible et jambages

- **GOAL-002**: Approcher le langage graphique des références sans ajouter
  d'élément architectural absent du document.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Ajouter un test Node rouge sur fenêtre horizontale/verticale/inversée : bande de vitrage centrée, deux rails et deux jambages entièrement compris dans la portion visible. Tester les très petites ouvertures sans détail illisible. | Oui | 2026-09-24 |
| TASK-005 | Dessiner le vitrage bleu pâle et les jambages dans `drawOpenings` avec les tangentes/normales calculées ; conserver la continuité des murs et l'ordre des couches. | Oui | 2026-09-24 |
| TASK-006 | Revue Standards/Spec, tests Node/navigateur/Go/Ruff, capture `benchmark/runs/3c-openings-fidelity-v2`, rapport d'images appariées dans `benchmark/comparisons/3c-openings-fidelity/report.md`, mise à jour de `docs/sprints/3c-bilan.md` et de TASK-012. | Oui | 2026-09-24 |

## 3. Alternatives

- **ALT-001**: Inférer le sens des battants depuis les pièces voisines :
  rejeté, car le schéma ne stocke pas ce sens et l'inférence peut être fausse.
- **ALT-002**: Changer simultanément le PNG Pillow ou le pipeline Gemini :
  rejeté, car le besoin porte sur le canvas de l'éditeur.
- **ALT-003**: Remplacer les fenêtres par une image bitmap : rejeté, car les
  mêmes ouvertures doivent rester nettes aux zooms 50/100/200 % et DPR 1/2.

## 4. Dependencies

- **DEP-001**: `web/static/js/plan-style-walls.js` et ses appels existants par
  `PlanStyle.drawOpenings`.
- **DEP-002**: `benchmark/editor_capture.py`, Chromium Playwright, Node, Go.

## 5. Files

- **FILE-001**: `web/static/js/plan-style-walls.js`.
- **FILE-002**: `web/tests/plan-style-walls.test.cjs`.
- **FILE-003**: `docs/sprints/3c-bilan.md`, ce plan,
  `docs/refactor-mvp-2d-1.md`, le rapport `benchmark/comparisons/`.

## 6. Testing

- **TEST-001**: Mock canvas vérifiant les chemins exacts, `save/restore`,
  absence de mutation et non-rendu hors segment.
- **TEST-002**: 38 captures appariées + six JSON par SHA-256, à 50/100/200 %,
  DPR 1/2 et états sélection/glissement ; inspection visuelle ciblée.
- **TEST-003**: `node --test "web/tests/*.test.cjs"`, `pytest benchmark/tests`,
  `go test ./internal/httpapi`, Ruff ciblé et `git diff --check`.

## 7. Risks & Assumptions

- **RISK-001**: La convention du battant à 90° ne représente pas un vrai sens
  de porte ; elle reste annoncée jusqu'à l'ajout d'une donnée explicite.
- **RISK-002**: Les fenêtres minuscules peuvent devenir brouillées à 50 % ;
  supprimer les jambages sous un seuil de 6 px projetés sans cacher la baie.
- **ASSUMPTION-001**: La portion visible d'une ouverture est l'intersection
  de `[offset_m, offset_m + width_m]` avec `[0, longueur_du_mur]`.

## 8. Related Specifications / Further Reading

- [Plan MVP 2D](../refactor-mvp-2d-1.md)
- [Bilan sprint 3C](3c-bilan.md)
- [Schéma PlanDocument](../../packages/plan-schema/plan-document.schema.json)
- [Référence canvas](../../benchmark/runs/3c-interactions-v1/manifest.json)
