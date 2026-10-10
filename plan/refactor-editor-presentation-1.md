---
goal: Séparer et professionnaliser la présentation extérieure du plan 2D
version: 1.0
date_created: 2026-09-27
last_updated: 2026-09-27
owner: Équipe A-AI
status: 'Completed'
tags: [refactor, frontend, editor, 2d, presentation, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Ce sprint extrait la présentation extérieure hors du module de placement des
libellés, puis améliore le fond, la profondeur visuelle de l’emprise, les cotes
globales et l’échelle graphique. La baseline appariée est
`benchmark/runs/editor-final-assets-v2`.

## 1. Requirements & Constraints

- **REQ-001**: Créer `web/static/js/plan-style-presentation.js` comme unique
  propriétaire du fond Canvas, de l’ombre de l’emprise, des deux cotes globales
  et de l’échelle graphique.
- **REQ-002**: Retirer `drawDimensions` et ses helpers exclusifs de
  `plan-style-annotations.js`; conserver dans ce module le placement des noms,
  surfaces, groupes de couloirs et évitement du mobilier.
- **REQ-003**: Dessiner un fond gris ivoire sobre et une feuille/emprise blanche
  avec ombre diffuse contenue, sans modifier les sols, murs, pièces ou données.
- **REQ-004**: Ajouter une échelle graphique exacte de 2 m, segmentée 0–1–2 m,
  positionnée au-dessus de l’emprise et omise uniquement si ses coordonnées ou
  l’échelle écran sont invalides.
- **REQ-005**: Conserver les cotes largeur sous le bâtiment et profondeur à
  gauche, leurs valeurs métriques françaises, leurs traits d’attache et leur
  lisibilité aux zooms 50 %, 100 % et 200 %.
- **REQ-006**: Conserver le contrat public `PlanStyle.drawSite` et
  `PlanStyle.drawDimensions` afin de ne pas coupler `editor.js` au refactor.
- **REQ-007**: Mettre à jour tous les points de chargement et le harnais offline,
  puis produire 38 captures appariées avec les six documents inchangés.
- **CON-001**: Ne pas inventer terrasse, végétation, orientation nord, limites de
  parcelle ou cartouche, car ces données ne sont pas présentes dans PlanDocument.
- **CON-002**: Ne modifier ni le mobilier, ni Gemini, ni la 3D, ni les interactions.
- **GUD-001**: Le fond et l’ombre doivent rester plus discrets que les murs, les
  ouvertures, le mobilier et les textes.
- **PAT-001**: Utiliser un module de présentation injecté par la façade
  `plan-style.js`, sans état global mutable ni dépendance vers `editor.js`.

## 2. Implementation Steps

### Implementation Phase 1 — Stabilize

- GOAL-001: Verrouiller le contrat visuel et fonctionnel avant extraction.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Ajouter `web/tests/plan-style-presentation.test.cjs` avec un contexte Canvas enregistrant les appels ; tester fond, emprise, ombre, cotes, format français, échelle 0–1–2 m, coordonnées invalides et équilibre save/restore. | Oui | 2026-09-27 |

### Implementation Phase 2 — Extract

- GOAL-002: Séparer présentation extérieure et annotations de pièces.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-002 | Après TASK-001, créer `plan-style-presentation.js`, y déplacer `fmtM` et `drawDimensions`, puis ajouter `drawSite` et `drawScaleBar`; supprimer ces responsabilités de `plan-style-annotations.js`. | Oui | 2026-09-27 |
| TASK-003 | Après TASK-002, injecter le nouveau module dans `plan-style.js`, charger le fichier avant la façade dans `web/templates/editor.html`, l’ajouter à `benchmark/editor_capture.py` et aux loaders de tests concernés. | Oui | 2026-09-27 |

### Implementation Phase 3 — Polish and validate

- GOAL-003: Vérifier la hiérarchie visuelle et l’absence de régression.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Après TASK-003, exécuter les tests ciblés puis Node complet ; inspecter la baseline et ajuster uniquement palette, ombre, offsets et typographie de la couche présentation. | Oui | 2026-09-27 |
| TASK-005 | Générer 38 captures finales sous `benchmark/runs/editor-presentation-v2`, comparer hashes image/document, réseau, temps de couche et vues 50/100/200 %, puis rédiger `benchmark/comparisons/editor-presentation/report.md`. | Oui | 2026-09-27 |
| TASK-006 | Exécuter pytest benchmark, Ruff, Go HTTP et diff-check ; faire les revues Standards/Spec, corriger les findings et mettre à jour `docs/`. | Oui | 2026-09-27 |

## 3. Alternatives

- **ALT-001**: Ajouter terrasse, arbres et limites de terrain comme les références :
  rejeté car PlanDocument ne fournit aucune géométrie fiable pour ces éléments.
- **ALT-002**: Conserver toutes les fonctions dans `annotations` : rejeté car le
  module cumule déjà géométrie des labels, groupes de couloirs et présentation.
- **ALT-003**: Modifier directement `editor.js` : rejeté pour préserver la façade
  stable et isoler la politique visuelle du moteur d’interaction.

## 4. Dependencies

- **DEP-001**: Contrat Canvas existant de `PlanStyle` et ordre d’appel dans
  `web/static/js/editor.js`.
- **DEP-002**: Harnais Playwright et baseline `editor-final-assets-v2`.

## 5. Files

- **FILE-001**: `web/static/js/plan-style-presentation.js` et
  `web/tests/plan-style-presentation.test.cjs`.
- **FILE-002**: `web/static/js/plan-style-annotations.js` et tests existants.
- **FILE-003**: `web/static/js/plan-style.js`, `web/templates/editor.html` et
  `benchmark/editor_capture.py`.
- **FILE-004**: `benchmark/runs/editor-presentation-v1`, rapport et documentation.

## 6. Testing

- **TEST-001**: Le module de présentation équilibre chaque save/restore et ne
  produit aucune coordonnée non finie sur entrées valides ou invalides.
- **TEST-002**: L’échelle graphique représente exactement deux segments d’un
  mètre à la valeur retournée par `m2px(toScreen)`.
- **TEST-003**: Les cotes affichent largeur et profondeur à une décimale avec
  virgule, sans changer le contrat de `PlanStyle`.
- **TEST-004**: Les 38 captures réussissent sans réseau ni erreur JavaScript et
  les six hashes documentaires restent identiques à la baseline.
- **TEST-005**: La médiane du temps de couche ne régresse pas de plus de 10 % ;
  Node, pytest, Ruff, Go et diff-check passent.

## 7. Risks & Assumptions

- **RISK-001**: Une ombre trop forte peut être interprétée comme une géométrie ;
  limiter l’opacité et inspecter les zooms extrêmes.
- **RISK-002**: L’échelle peut entrer en collision avec le bord du Canvas à 200 % ;
  elle reste ancrée au plan et peut naturellement sortir du viewport après zoom.
- **RISK-003**: Les tests existants chargent une liste explicite de modules ; tous
  les loaders doivent être recensés par recherche globale.
- **ASSUMPTION-001**: `toScreen` conserve une échelle uniforme en x et y, comme
  l’exige déjà le renderer actuel.

## 8. Related Specifications / Further Reading

- [Sprint final des assets](design-editor-final-assets-1.md)
- [Plan annotations précédent](../docs/sprints/3c-annotations-plan.md)
- [Rapport assets final](../benchmark/comparisons/editor-final-assets/report.md)
- [Rapport présentation](../benchmark/comparisons/editor-presentation/report.md)
