---
goal: Isoler murs et ouvertures du canvas 2D puis supprimer le seuil d'entrée inféré
version: 1.0
date_created: 2026-09-24
last_updated: 2026-09-24
owner: Équipe A-AI
status: Completed
tags: [refactor, design, editor, 2d, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Ce sous-sprint 3C porte sur `PlanStyle.drawWalls`, `drawOpenings` et
`drawPorch`, appelés par `web/static/js/editor.js`. La référence appariée est
`benchmark/runs/3c-furniture-footprint-v1` : 36 vues au repos et deux états
interactifs. Aucun changement de `PlanDocument`, Gemini, Pillow ou 3D.

## 1. Requirements & Constraints

- **REQ-001**: Extraire les tracés de murs, ouvertures et seuil dans `web/static/js/plan-style-walls.js`, avec une fabrique `window.PlanStyleWalls({ink})` ; `ink` est la couleur partagée avec les libellés. Conserver l'API `PlanStyle.drawWalls/drawOpenings/drawPorch` et les 38 PNG pixel-identiques à cette étape.
- **REQ-002**: Après l'extraction neutre seulement, arrêter de dessiner le seuil et la flèche inférés par `wall_id === 'w_outer_3'` ; le schéma ne possède pas de rôle « porte d'entrée », donc la seule présence d'une porte sud ne prouve pas une entrée architecturale.
- **REQ-003**: Préserver la géométrie des murs et des baies, y compris fenêtres et battants conventionnels ; ne jamais changer offsets, largeurs, ordre des murs ni sens de stockage.
- **CON-001**: Charger le nouveau module avant `plan-style.js` dans trois templates, tests Node, smoke miniature et `benchmark/editor_capture.py`, sans casser la pile palette → sols → mobilier → murs/ouvertures → façade `PlanStyle`.
- **CON-002**: Garder la convention de battant à 90° faute de champ de sens d'ouverture. Toute amélioration de cette convention serait un sous-sprint distinct, avec données explicites ou convention documentée.
- **CON-003**: Comparer les mêmes six JSON, caméra, DPR, navigateur et interactions avant/après chaque étape. L'extraction exige 38/38 PNG identiques ; la suppression du seuil peut changer certaines images, sans altérer les documents.
- **GUD-001**: Écrire les tests avant le code, conduire les revues Standards/Spec immédiatement après les blocs et actualiser `docs/sprints/3c-bilan.md` et les rapports `benchmark/comparisons/`.
- **PAT-001**: Module de rendu pur sans accès à l'état de l'éditeur ni au réseau ; la décision d'omettre une décoration sans preuve appartient au rendu, pas à la géométrie du plan.

## 2. Implementation Steps

### Implementation Phase 1 — Caractérisation et extraction neutre

- **GOAL-001**: Déplacer le renderer murs/ouvertures sans changement visuel.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Ajouter `web/tests/plan-style-walls.test.cjs` avant extraction : murs horizontal/vertical/inversé et T, fenêtre/porte sur mur inversé, ouverture sans mur, sauvegarde/restauration canvas, non-mutation et absence d'entrée pour `drawPorch` sans `w_outer_3`. | Oui | 2026-09-24 |
| TASK-002 | Extraire `drawWalls`, `drawPorch`, `drawOpenings`, `GAP` et `WALL` dans `plan-style-walls.js` ; injecter `INK` depuis `plan-style.js` sous la clé `ink` parce que les libellés l'utilisent encore. `plan-style.js` délègue sans changer les signatures. Mettre à jour les trois templates, le harnais, les tests Node et le smoke navigateur. | Oui | 2026-09-24 |
| TASK-003 | Revue Standards/Spec, tests JS/Go/Python ciblés, capture `benchmark/runs/3c-walls-extracted` et comparaison SHA-256 des 38 PNG et six JSON à `3c-furniture-footprint-v1`. Corriger toute dérive avant Phase 2. | Oui | 2026-09-24 |

### Implementation Phase 2 — Supprimer le seuil non fondé

- **GOAL-002**: Ne plus présenter une porte sud comme entrée sans donnée sémantique.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Ajouter d'abord un test en échec : une porte sur `w_outer_3` ne génère ni marche ni flèche par `drawPorch`, tout en conservant `drawOpenings` et le document. | Oui | 2026-09-24 |
| TASK-005 | Rendre `drawPorch` compatible mais sans peinture ni géométrie inférée ; garder son export pendant la migration de l'éditeur. Ne pas modifier le dessin des murs, fenêtres ou portes. | Oui | 2026-09-24 |
| TASK-006 | Revue Standards/Spec et tests ; capturer `benchmark/runs/3c-walls-no-inferred-porch`, comparer les 38 images et six JSON, inspecter les six plans et les interactions. Documenter les avant/après dans `benchmark/comparisons/3c-walls-no-inferred-porch/report.md` et les limites du battant conventionnel. | Oui | 2026-09-24 |

## 3. Alternatives

- **ALT-001**: Garder la marche sur toute porte sud : rejeté, car l'identifiant du mur ne porte pas le rôle d'entrée.
- **ALT-002**: Déduire l'entrée par la pièce voisine : rejeté pour ce bloc, car cela reste une inférence non garantie et nécessiterait un contrat de données/test métier.
- **ALT-003**: Changer simultanément épaisseur, angles, arc et vitrage : rejeté, car la comparaison ne pourrait plus attribuer l'effet visuel à une décision unique.

## 4. Dependencies

- **DEP-001**: `PlanStylePalette`, `PlanStyleFloors`, `PlanStyleFurniture` et le harnais canvas figé.
- **DEP-002**: Node, Chromium Playwright et Go disponibles pour les tests ciblés.

## 5. Files

- **FILE-001**: `web/static/js/plan-style.js` et nouveau `web/static/js/plan-style-walls.js`.
- **FILE-002**: `web/templates/editor.html`, `project.html`, `admin_plan.html` ; `benchmark/editor_capture.py`.
- **FILE-003**: `web/tests/plan-style-walls.test.cjs`, trois tests de chargement Node et `benchmark/tests/test_editor_palette_integration.py`.
- **FILE-004**: `docs/sprints/3c-bilan.md`, `docs/refactor-mvp-2d-1.md`, deux rapports `benchmark/comparisons/`.

## 6. Testing

- **TEST-001**: Mock canvas avec coordonnées exactes, ordre de peinture, `save/restore`, absence de mutation ; signature de commande stable après extraction.
- **TEST-002**: Capture 38 PNG et six JSON à chaque phase ; SHA-256 pixel-identiques seulement pour l'extraction, puis analyse qualitative appariée du seuil supprimé.
- **TEST-003**: `node --test` des suites éditeur, `pytest benchmark/tests`, `go test ./internal/httpapi`, Ruff du harnais et `git diff --check`.

## 7. Risks & Assumptions

- **RISK-001**: Script non chargé dans une miniature projet/admin ; tests d'ordre des trois templates et smoke Chromium.
- **RISK-002**: Le harnais comporte des indices de chargement positionnels ; mettre les six scripts de rendu/édition avant instrumentation dans l'ordre, puis vérifier 38 captures, pas seulement un test Node.
- **ASSUMPTION-001**: Une marche/flèche absente de `PlanDocument` est une décoration inventée ; sa suppression ne retire aucune donnée architecturale stockée.

## 8. Related Specifications / Further Reading

- [Plan MVP 2D](../refactor-mvp-2d-1.md)
- [Bilan sprint 3C](3c-bilan.md)
- [Référence canvas](../../benchmark/runs/3c-furniture-footprint-v1/manifest.json)
