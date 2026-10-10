---
goal: Isoler les annotations du plan 2D et éviter les libellés débordants à faible zoom
version: 1.0
date_created: 2026-09-24
last_updated: 2026-09-24
owner: Équipe A-AI
status: Completed
tags: [refactor, design, editor, 2d, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Ce sous-sprint 3C couvre les noms/surfaces des pièces et les cotes extérieures
de `PlanStyle`, pas les coordonnées du plan, le mobilier, Gemini, Pillow ou 3D.
La référence est `benchmark/runs/3c-walls-no-inferred-porch` (36 vues au repos,
sélection et glissement). Le défaut prioritaire est le texte de pièce plus
large que sa cellule sur les plans étroits à 50 % ; la légende HTML garde les
noms complets lorsque le canvas doit omettre un libellé.

## 1. Requirements & Constraints

- **REQ-001**: Extraire `fmtM`, `drawDimensions`, `polyArea`, `sharedEdge`, `hallGroups`, `drawRoomLabels` de `web/static/js/plan-style.js` dans `web/static/js/plan-style-annotations.js`, en injectant `{box, m2px, label, ink, paper}`. `PlanStyle` conserve les quatre exports publics `drawDimensions`, `drawRoomLabels`, `hallGroups`, `polyArea`.
- **REQ-002**: Pendant l'extraction neutre, produire 38/38 PNG et six JSON identiques à la référence, sans modifier ordre de couches, police ou API.
- **REQ-003**: Ensuite, dans l'éditeur à faible zoom, ne peindre un nom de pièce que si sa largeur mesurée et sa hauteur tiennent dans la boîte projetée de la pièce avec une marge de 4 px. Essayer les tailles de police de la taille actuelle jusqu'à 8 px ; si aucune ne tient, omettre le nom dans le canvas, sans tronquer ni inventer d'abréviation.
- **REQ-004**: Peindre la surface sur une deuxième ligne seulement si le nom est affiché, si la largeur mesurée de la surface et la hauteur des deux lignes tiennent ; sinon garder seulement le nom. Préserver le regroupement d'un couloir continu et l'option `noArea`.
- **CON-001**: Conserver `PlanDocument` et la légende HTML inchangés ; la surface demeure disponible dans le document même si elle n'est pas dessinée au zoom minuscule.
- **CON-002**: Aucun label ne doit être déplacé pour éviter le mobilier dans ce bloc : `drawRoomLabels` ne reçoit pas les meubles, et une nouvelle stratégie d'ancrage requiert un plan/test distinct. Les pièces concaves demandent aussi un contrôle ultérieur de l'ancre intérieure.
- **CON-003**: Charger le nouveau module avant `plan-style.js` dans trois templates, tests Node, smoke Chromium et le harnais. Comparer six documents, zooms 50/100/200 %, DPR 1/2 et états interactifs.
- **GUD-001**: Tests avant code, revues Standards/Spec immédiatement après chaque bloc, documentation dans `docs/sprints/3c-bilan.md` et images comparées dans `benchmark/comparisons/`.
- **PAT-001**: Module de rendu pur ; `box`, `m2px`, couleurs et résolveur de libellé sont des dépendances injectées, sans état d'édition ni accès réseau.

## 2. Implementation Steps

### Implementation Phase 1 — Caractérisation et extraction neutre

- **GOAL-001**: Séparer les annotations sans changer un pixel ni les documents.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Ajouter `web/tests/plan-style-annotations.test.cjs` sur cotes 12,0 × 9,0 m, nom/surface, `noArea`, couloirs adjacents, pièce sans polygone, `save/restore`, non-mutation et nom débordant à 50 % ; exécuter sur l'ancien module. | Oui | 2026-09-24 |
| TASK-002 | Extraire mécaniquement les six fonctions indiquées en REQ-001 ; conserver `box`/`m2px` dans `plan-style.js`, injecter les dépendances et réexporter l'API. Mettre à jour les trois templates, le harnais et les tests navigateur/Node. | Oui | 2026-09-24 |
| TASK-003 | Revue Standards/Spec, tests JS/navigateur/Go/Python ciblés, capture `benchmark/runs/3c-annotations-extracted`, comparaison SHA-256 appariée des 38 PNG et six JSON à `3c-walls-no-inferred-porch`. | Oui | 2026-09-24 |

### Implementation Phase 2 — Texte adapté à la cellule projetée

- **GOAL-002**: Supprimer les débordements évidents du texte à faible zoom sans cacher les noms qui tiennent.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Remplacer le test de caractérisation débordant par un test en échec qui mesure une petite pièce, une grande pièce et `noArea` à plusieurs échelles : nom/surface peints seulement lorsqu'ils tiennent ; ne jamais modifier room/PlanDocument. | Oui | 2026-09-24 |
| TASK-005 | Dans `drawRoomLabels`, mesurer `ctx.measureText` après avoir fixé la police, réduire la taille jusqu'à 8 px, limiter la largeur disponible à la boîte projetée autour de l'ancre avec marge de 4 px, vérifier hauteur d'une ou deux lignes puis peindre. Ne pas changer `drawDimensions`, `hallGroups`, `polyArea` ni la légende. | Oui | 2026-09-24 |
| TASK-006 | Revue Standards/Spec, 38 captures finales `benchmark/runs/3c-annotations-fit-v2`, six JSON identiques et inspection 50/100/200 % + sélection/glissement. Publier `benchmark/comparisons/3c-annotations-fit-v2/report.md` avec cas où le texte est omis, limites de l'ancre et du mobilier, tests et durée descriptive sans causalité. | Oui | 2026-09-24 |

## 3. Alternatives

- **ALT-001**: Dessiner des noms tronqués ou abrégés automatiquement : rejeté dans ce bloc car les abréviations peuvent devenir ambiguës et demanderaient une règle métier/une légende correspondante.
- **ALT-002**: Réduire la police sous 8 px : rejeté, car un texte présent mais illisible n'améliore pas la lecture.
- **ALT-003**: Déplacer les étiquettes hors des pièces avec flèches : rejeté, car cela requiert un algorithme de placement global, non testé ici.

## 4. Dependencies

- **DEP-001**: `PlanStylePalette`, `PlanStyleFloors`, `PlanStyleFurniture`, `PlanStyleWalls` et la façade `PlanStyle` actuelle.
- **DEP-002**: Node, Chromium Playwright et Go pour les vérifications et captures.

## 5. Files

- **FILE-001**: `web/static/js/plan-style.js`, nouveau `web/static/js/plan-style-annotations.js`.
- **FILE-002**: Trois templates du plan, `benchmark/editor_capture.py`, chargeurs Node et `benchmark/tests/test_editor_palette_integration.py`.
- **FILE-003**: `web/tests/plan-style-annotations.test.cjs`, `docs/sprints/3c-bilan.md`, `docs/refactor-mvp-2d-1.md` et deux rapports `benchmark/comparisons/`.

## 6. Testing

- **TEST-001**: Mock canvas avec `measureText`, `fillText/strokeText`, ordre et limites des boîtes, `save/restore`, nom/surface et non-mutation.
- **TEST-002**: SHA-256 des 38 captures et six JSON après extraction, puis comparaison d'images appariées à 50/100/200 % et DPR 1/2 après la variation.
- **TEST-003**: `node --test` des suites éditeur, `pytest benchmark/tests`, `go test ./internal/httpapi`, Ruff et `git diff --check`.

## 7. Risks & Assumptions

- **RISK-001**: `ctx.measureText` dépend de la police réellement chargée ; tests Node caractérisent la logique, captures Chromium vérifient le rendu avec les polices locales du harnais. La page produit authentifiée reste un contrôle distinct.
- **RISK-002**: Une pièce concave peut avoir une ancre moyenne hors du polygone même si le texte tient dans sa boîte ; ce sprint ne prouve pas la containment polygonale.
- **RISK-003**: Omettre un label au zoom très faible peut réduire l'information sur le canvas ; la légende complète est conservée et le zoom reste disponible.
- **ASSUMPTION-001**: La marge de 4 px inclut le halo de 3 px et évite le contact avec le mur sur les pièces rectangulaires de la matrice.

## 8. Related Specifications / Further Reading

- [Plan MVP 2D](../refactor-mvp-2d-1.md)
- [Bilan sprint 3C](3c-bilan.md)
- [Référence canvas](../../benchmark/runs/3c-walls-no-inferred-porch/manifest.json)
