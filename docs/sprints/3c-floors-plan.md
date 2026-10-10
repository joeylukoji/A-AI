---
goal: Séparer puis améliorer les sols du canvas éditeur 2D sans altérer le PlanDocument
version: 1.0
date_created: 2026-09-23
last_updated: 2026-09-24
owner: Équipe A-AI
status: Complete
tags: [design, architecture, editor, 2d, benchmark]
---

# Introduction

![Status: Complete](https://img.shields.io/badge/status-Complete-green)

Ce sous-plan du sprint 3C couvre exclusivement les sols du canvas HTML dans
`web/static/js/plan-style.js`. La référence figée est
`benchmark/runs/3c-palette-extract` (36 repos + 2 interactions). Aucun rendu
Gemini, PNG Pillow ou fichier 3D n'est modifié.

## 1. Requirements & Constraints

- **REQ-001**: Garder les polygones, coordonnées, types de pièces et identifiants du `PlanDocument` inchangés ; ne dessiner aucun équipement absent.
- **REQ-002**: Préserver le découpage des sols par `ctx.clip()` sur chaque polygone, y compris les pièces concaves et adjacentes.
- **REQ-003**: Le premier bloc d'extraction doit produire les mêmes 38 PNG octet par octet que la référence, avec le même navigateur, zoom et DPR.
- **REQ-004**: Le second bloc doit rendre les sols plus sobres et lisibles, selon les deux références utilisateur, uniquement dans l'éditeur et les aperçus qui réutilisent `PlanStyle`.
- **CON-001**: Conserver l'API publique `PlanStyle.drawFloor/drawFixtures/fill` et l'ordre existant de superposition sols → mobilier → murs → libellés → ouvertures. Toute réorganisation serait un changement visuel distinct.
- **CON-002**: Conserver les trois templates consommateurs (`editor.html`, `project.html`, `admin_plan.html`) et le harnais en ordre de chargement valide.
- **CON-003**: Le harnais sans CSS global ni police CDN sert aux comparaisons appariées ; la vérification de la page produit reste distincte.
- **GUD-001**: Faire revue Standards/Spec et tests immédiatement après chaque bloc ; tenir `docs/sprints/3c-bilan.md` et `benchmark/comparisons/` à jour.
- **PAT-001**: Isoler une responsabilité de rendu dans `plan-style-floors.js` ; le module reçoit ses dépendances explicitement et n'accède ni au réseau ni à l'état de l'éditeur.

## 2. Implementation Steps

### Implementation Phase 1 — Extraction sans variation de pixels

- **GOAL-001**: Déplacer le dessin des sols dans un module dédié tout en conservant exactement le canvas existant.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Ajouter `web/tests/plan-style-floor.test.cjs` sur un polygone concave et les types chambre/cuisine/séjour/SDB/garage : un clip par pièce, `save/restore` équilibrés, aucun changement du JSON. Exécuter ces tests avant extraction. | Oui | 2026-09-23 |
| TASK-002 | Déplacer `woodPlanks`, `tileGrid`, `drawFloor` de `plan-style.js` dans `plan-style-floors.js`, en injectant `box`, `m2px` et `fill` lors de la construction ; `PlanStyle` réexporte `drawFloor` et `drawFixtures` avec les signatures actuelles. Charger le nouveau fichier dans les trois templates, le test et `benchmark/editor_capture.py`. | Oui | 2026-09-24 |
| TASK-003 | Revue Standards/Spec, tests JS et aperçu navigateur, capture `benchmark/runs/3c-floors-extracted`, comparaison SHA-256 des 38 PNG et six documents à `3c-palette-extract`. Si une image diffère, corriger avant Phase 2. | Oui | 2026-09-24 |

### Implementation Phase 2 — Première variation graphique des sols

- **GOAL-002**: Produire un premier nouveau rendu éditeur plus proche des références, sans changement structurel.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Définir les aplats de base dans `plan-style-palette.js` (valeurs figées ci-dessous), faire utiliser `fill(room)` par `plan-style-floors.js` et y réduire le contraste des motifs. Garder des textures visibles à 100 % sans saturer noms ou mobilier ; vérifier la concordance avec la légende. | Oui | 2026-09-24 |
| TASK-005 | Capturer `benchmark/runs/3c-floors-design-v1` sur les six mêmes documents, zooms et DPR ; comparer géométrie/JSON, inspecter images studio/garage/couloir/étroit et états sélection/glissement. Publier liens avant/après et analyse qualitative dans `benchmark/comparisons/3c-floors-design-v1/report.md`. | Oui | 2026-09-24 |
| TASK-006 | Revue Standards/Spec et tests JS/Go/Python ciblés ; rejeter toute dérive de murs, ouvertures, mobilier ou document. Documenter la performance descriptive des couches, sans revendiquer de gain causal sur un run. | Oui | 2026-09-24 |

## 3. Alternatives

- **ALT-001**: Modifier immédiatement tout `plan-style.js` : rejeté, car empêcherait d'attribuer une différence visuelle à une responsabilité précise.
- **ALT-002**: Générer une texture bitmap : rejeté pour ce bloc, car la qualité à plusieurs zooms et DPR serait plus difficile à contrôler que les traits vectoriels du canvas.

## 4. Dependencies

- **DEP-001**: Scripts `PlanStylePalette`, `PlanStyle` et `benchmark/editor_capture.py` de la baseline 3C.
- **DEP-002**: Node pour les tests JS, Chromium Playwright et Shapely pour le harnais optionnel.

## 5. Files

- **FILE-001**: `web/static/js/plan-style.js` et nouveau `plan-style-floors.js`.
- **FILE-004**: `web/static/js/plan-style-palette.js` pour les aplats communs à la légende et aux sols pendant la Phase 2.
- **FILE-002**: `web/templates/editor.html`, `project.html`, `admin_plan.html` et `benchmark/editor_capture.py`.
- **FILE-003**: `web/tests/plan-style-floor.test.cjs`, `docs/sprints/3c-bilan.md`, `benchmark/comparisons/3c-floors-design-v1/report.md`.

## 6. Testing

- **TEST-001**: Tests JS ciblés avant/après extraction, puis `node --test web/tests/*.test.cjs` avec énumération explicite sous PowerShell.
- **TEST-002**: Comparaison appariée SHA-256 des 38 PNG et des six JSON après extraction, puis examen visuel avant/après style à 50/100/200 % et DPR 1/2.
- **TEST-003**: Smoke Chromium du composant `plan-thumb.js` et tests `go test ./internal/httpapi` pour l'intégration des templates.

## 7. Risks & Assumptions

- **RISK-001**: Une dépendance de script oubliée casse les pages projet/admin ; le test d'ordre des trois templates et le smoke navigateur sont des gardes.
- **RISK-002**: Un motif du sol déborde un polygone ou cache un libellé ; tests de clipping et inspection des PNG couvrent le risque connu, sans démontrer toutes les géométries possibles.
- **ASSUMPTION-001**: Les deux images fournies sont une direction graphique, pas une source de géométrie ou de programme de pièces.

Palette de la Phase 2, arrêtée avant le changement de code : séjour/salle à
manger `rgb(248,247,243)`, cuisine `rgb(249,248,244)`, chambre/bureau
`rgb(247,244,235)`, couloir `rgb(247,246,242)`, sanitaires
`rgb(241,246,247)`, garage `rgb(239,240,237)`, rangement
`rgb(244,242,238)`. Le type inconnu conserve son fallback existant.
Texture : lames des chambres 0,22 × 1,1 m avec nuances proches et joints
à 0,45 px / opacité 0,06 ; séjour/salle à manger hachures croisées diagonales
espacées de 0,5 m à 0,45 px / opacité 0,04 ; couloir mêmes hachures de 0,65 m
à opacité 0,03 ; cuisine carreaux de 0,6 m à 0,55 px / opacité 0,06 ; sanitaires
carreaux de 0,3 m à opacité 0,07. Garage et rangement restent en aplat uni.

## 8. Related Specifications / Further Reading

- [Plan MVP 2D](../refactor-mvp-2d-1.md)
- [Journal du sprint 3C](3c-bilan.md)
- [Baseline canvas](../../benchmark/runs/3c-palette-extract/manifest.json)
