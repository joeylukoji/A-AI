---
goal: Isoler le mobilier de l'éditeur 2D et contenir le canapé en L dans son empreinte
version: 1.0
date_created: 2026-09-24
last_updated: 2026-09-24
owner: Équipe A-AI
status: Completed
tags: [refactor, design, editor, 2d, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Ce sous-sprint 3C concerne seulement les symboles de mobilier du canvas
`PlanStyle`. La référence figée est `benchmark/runs/3c-floors-design-v1`
(36 repos + sélection + glissement). Le générateur de documents, Gemini,
le rendu Pillow et la 3D ne sont pas modifiés.

## 1. Requirements & Constraints

- **REQ-001**: Déplacer les glyphes, la palette de mobilier et `drawFurniture` de `web/static/js/plan-style.js` vers `web/static/js/plan-style-furniture.js` sans variation visuelle de l'extraction.
- **REQ-002**: Corriger `sofa.lshape` : tous les aplats du canapé doivent rester dans `[-w/2,w/2] × [-d/2,d/2]` avant rotation. `size_m.d` inclut déjà la méridienne, conformément à `services/ai/app/floorplan_render.py`.
- **REQ-003**: Ne modifier aucun `PlanDocument`, position, rotation, collision de placement ou autre symbole dans cette variation. Conserver l'API publique `PlanStyle.drawFurniture(ctx, items, toScreen)`.
- **CON-001**: Préserver le tri tapis-avant-meubles, les `save/restore` par instance, les dimensions monde/écran et l'ordre sols → mobilier → murs.
- **CON-002**: Charger le nouveau module avant `plan-style.js` dans `editor.html`, `project.html`, `admin_plan.html`, le harnais et les tests navigateur/Node.
- **CON-003**: Les 38 PNG de l'extraction neutre doivent être identiques à la référence, puis la variation doit être comparée séparément sur les mêmes JSON, caméras, DPR et Chromium.
- **GUD-001**: Après chaque bloc, lancer tests ciblés et revues Standards/Spec ; mettre à jour `docs/sprints/3c-bilan.md` et `benchmark/comparisons/`.
- **PAT-001**: Module de rendu pur avec injection explicite de `m2px`, sans accès à l'état d'édition ni au réseau.

## 2. Implementation Steps

### Implementation Phase 1 — Caractérisation et extraction neutre

- **GOAL-001**: Isoler le mobilier sans changement de pixels ni de données.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Ajouter `web/tests/plan-style-furniture.test.cjs` : un rendu de chaque type de meuble existant, canapé en L tourné, tri tapis, `save/restore`, API et non-mutation ; exécuter sur l'ancien code. | Oui | 2026-09-24 |
| TASK-002 | Déplacer le bloc `roundRect` → `drawFurniture` dans `plan-style-furniture.js` via extraction mécanique ; exposer une fabrique `window.PlanStyleFurniture({m2px})` et déléguer depuis `plan-style.js`. Mettre à jour trois templates, `benchmark/editor_capture.py`, les tests Node et le smoke miniature. | Oui | 2026-09-24 |
| TASK-003 | Revue Standards/Spec, tests JS/navigateur/Go, capture `benchmark/runs/3c-furniture-extracted` et comparaison SHA-256 appariée des 38 PNG et six JSON à `3c-floors-design-v1`. Rejeter l'extraction si une image diffère. | Oui | 2026-09-24 |

### Implementation Phase 2 — Empreinte du canapé en L

- **GOAL-002**: Retirer le débordement interne du symbole sans déplacer le meuble ni changer la structure du plan.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Ajouter d'abord un test en échec de l'enveloppe dessinée de `sofa.lshape` à rotation 0/90/270 ; vérifier qu'un deux-places garde son empreinte. | Oui | 2026-09-24 |
| TASK-005 | Dans `drawSofa` du nouveau module, prendre `d` comme profondeur totale et réserver au corps une profondeur `d - min(0.72, d × 0.45)` ; dessiner la méridienne jusqu'à `+d/2`, sans extension. | Oui | 2026-09-24 |
| TASK-006 | Revue Standards/Spec et tests ciblés ; capturer `benchmark/runs/3c-furniture-footprint-v1`, vérifier JSON identiques et comparer visuellement les six plans, à 50/100/200 % et DPR 1/2, dans `benchmark/comparisons/3c-furniture-footprint-v1/report.md`. Documenter les débordements restants dus aux autres symboles ou aux données sans les masquer. | Oui | 2026-09-24 |

## 3. Alternatives

- **ALT-001**: Rogner tout mobilier au polygone de pièce : rejeté, car cacherait une mauvaise position dans les données et couperait les traits des symboles.
- **ALT-002**: Déplacer automatiquement les meubles dans l'éditeur : rejeté pour ce bloc, car cela changerait le `PlanDocument` et possiblement la synchronisation 3D.

## 4. Dependencies

- **DEP-001**: `PlanStylePalette`, `PlanStyleFloors` et le harnais `benchmark/editor_capture.py` du sous-sprint des sols.
- **DEP-002**: Node, Chromium Playwright et Go pour les vérifications ciblées.

## 5. Files

- **FILE-001**: `web/static/js/plan-style.js` et nouveau `web/static/js/plan-style-furniture.js`.
- **FILE-002**: `web/templates/editor.html`, `project.html`, `admin_plan.html`, `benchmark/editor_capture.py`.
- **FILE-003**: `web/tests/plan-style-furniture.test.cjs`, tests de chargement et `benchmark/tests/test_editor_palette_integration.py`.
- **FILE-004**: `docs/sprints/3c-bilan.md` et `benchmark/comparisons/3c-furniture-footprint-v1/report.md`.

## 6. Testing

- **TEST-001**: Tests Node sur commandes canvas et enveloppe du canapé, puis `node --test` sur les suites de l'éditeur.
- **TEST-002**: 38 captures appariées, SHA-256 identiques après extraction, six JSON identiques et examen visuel après correction.
- **TEST-003**: Smoke navigateur de la miniature, `go test ./internal/httpapi`, Ruff du harnais et `git diff --check`.

## 7. Risks & Assumptions

- **RISK-001**: Un oubli de script casse les miniatures sur pages projet/admin ; ordre vérifié dans chaque template et smoke navigateur.
- **RISK-002**: Des petits traits décoratifs d'autres glyphes dépassent leur rectangle ; le test du canapé porte sur ce symbole seulement. Aucun masquage global n'est autorisé.
- **ASSUMPTION-001**: `size_m` représente l'enveloppe du symbole centré, comme dans la génération et le rendu Pillow ; une donnée invalide reste une responsabilité distincte du renderer.

## 8. Related Specifications / Further Reading

- [Plan MVP 2D](../refactor-mvp-2d-1.md)
- [Bilan sprint 3C](3c-bilan.md)
- [Référence avant mobilier](../../benchmark/runs/3c-floors-design-v1/manifest.json)
