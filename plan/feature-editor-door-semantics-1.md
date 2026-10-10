---
goal: Rendre le sens des portes explicite et éditable dans le plan 2D
version: 1.0
date_created: 2026-09-28
last_updated: 2026-09-28
owner: Équipe A-AI
status: 'In progress'
tags: [feature, contract, frontend, editor, 2d, generation, benchmark]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In_progress-yellow)

Ce sprint remplace la convention implicite `start/positive` par deux propriétés
optionnelles et validées dans PlanDocument : `hinge` (`start|end`) et `swing`
(`positive|negative`). Les anciens documents restent valides ; la baseline
visuelle est `benchmark/runs/editor-openings-dimensions-v1`.

## 1. Requirements & Constraints

- **REQ-001**: Ajouter aux portes les propriétés optionnelles `hinge` et `swing`
  dans `packages/plan-schema/plan-document.schema.json`; les accepter ensemble
  ou les omettre ensemble et les interdire sur les fenêtres.
- **REQ-002**: Valider les mêmes règles et codes stables dans
  `services/ai/app/opening_intervals.py` et `internal/plan/validation_openings.go`.
- **REQ-003**: Ajouter dans `services/ai/app/plan_openings.py` une attribution
  déterministe : ouverture extérieure vers la pièce desservie, ouverture depuis
  un couloir vers l’autre pièce, puis choix stable documenté pour les autres cas.
- **REQ-004**: Choisir la charnière au bord de l’ouverture le plus proche d’une
  extrémité du contact avec la pièce cible, afin de ranger le battant contre un
  bord plutôt qu’au milieu du mur.
- **REQ-005**: Faire utiliser exactement les mêmes valeurs par
  `plan-style-openings.js` et `services/ai/app/furnish.py`; le battant dessiné,
  la zone de débattement et le passage opposé doivent coïncider.
- **REQ-006**: Conserver le fallback `hinge=start`, `swing=positive` pour tout
  ancien document sans propriétés, sans mutation automatique à l’ouverture.
- **REQ-007**: Ajouter `PlanEdit.cycleDoorSwing` et un outil éditeur « Sens
  porte » qui parcourt les quatre couples valides, avec checkpoint, undo,
  sauvegarde différée et annonce accessible.
- **REQ-008**: Une porte nouvellement ajoutée dans l’éditeur doit stocker
  explicitement `hinge=start` et `swing=positive`; une fenêtre ne doit stocker
  aucune propriété de porte.
- **CON-001**: Ne modifier ni la 3D, ni les exports, ni Gemini, ni la géométrie
  des murs et ouvertures dans ce sprint.
- **CON-002**: Ne pas modifier les anciens documents gelés utilisés par la
  baseline ; mesurer séparément compatibilité historique et nouvelles variantes.
- **GUD-001**: Définir `positive` comme la normale gauche du mur orienté de `a`
  vers `b`, soit `(-uy, ux)`, et `negative` comme son opposée.
- **PAT-001**: Centraliser la normalisation des valeurs dans de petites fonctions
  pures par environnement et éviter toute dépendance du renderer vers l’éditeur.

## 2. Implementation Steps

### Implementation Phase 1 — Stabilize the contract

- GOAL-001: Définir et verrouiller la sémantique rétrocompatible.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Ajouter aux fixtures partagées les cas valide complet, paire partielle, enum invalide et propriétés sur fenêtre ; étendre les tests Python/Go du contrat avant l’implémentation. |  |  |
| TASK-002 | Ajouter les tests JS des quatre combinaisons de charnière/débattement et les tests Python des zones de mobilier correspondantes. |  |  |

### Implementation Phase 2 — Implement semantics

- GOAL-002: Propager une seule sémantique du générateur jusqu’au Canvas.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Après TASK-001, mettre à jour le schéma JSON et les validateurs Python/Go avec les mêmes règles et codes `invalid_door_semantics` et `invalid_door_semantic_value`. |  |  |
| TASK-004 | Après TASK-002, implémenter l’attribution dans `plan_openings.py`, puis adapter `furnish.py` et `plan-style-openings.js` aux quatre configurations sans mutation d’entrée. |  |  |
| TASK-005 | Ajouter `cycleDoorSwing` dans `plan-edit.js`, l’outil dans `editor.html` et son branchement dans `editor.js`; couvrir ajout, cycle, undo et sauvegarde par tests Node/Playwright. |  |  |

### Implementation Phase 3 — Benchmark and validate

- GOAL-003: Démontrer compatibilité, cohérence géométrique et coût maîtrisé.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Exécuter les tests ciblés puis complets ; générer quatre variantes Canvas et vérifier par pixels/hashes que les battants occupent quatre quadrants distincts. |  |  |
| TASK-007 | Rejouer les 38 captures historiques et vérifier leur identité visuelle/documentaire avec la baseline, puis mesurer le coût de rendu. |  |  |
| TASK-008 | Exécuter Ruff, tests Go et diff-check ; mener les revues Standards/Spec, corriger leurs findings et publier le rapport sous `benchmark/comparisons/editor-door-semantics/`. |  |  |

## 3. Alternatives

- **ALT-001**: Continuer à inférer le sens uniquement dans le renderer : rejeté
  car le mobilier, l’éditeur et les exports pourraient interpréter différemment
  la même porte.
- **ALT-002**: Utiliser `left|right` sans référentiel : rejeté car ces mots sont
  ambigus lorsque l’ordre des sommets du mur est inversé.
- **ALT-003**: Rendre les champs obligatoires et migrer tous les documents :
  rejeté pour préserver les projets existants et les preuves gelées.

## 4. Dependencies

- **DEP-001**: PlanDocument 1.0 et les validateurs partagés Python/Go.
- **DEP-002**: Placement des portes de `plan_openings.py` et géométrie des zones
  de `furnish.py`.
- **DEP-003**: Façade `PlanStyle`, module pur `PlanEdit` et harnais Playwright.
- **DEP-004**: Baseline `benchmark/runs/editor-openings-dimensions-v1`.

## 5. Files

- **FILE-001**: Schéma, fixtures et profil sous `packages/plan-schema/`.
- **FILE-002**: Validateurs `opening_intervals.py` et `validation_openings.go`.
- **FILE-003**: Génération `plan_openings.py`, mobilier `furnish.py` et tests.
- **FILE-004**: Renderer `plan-style-openings.js` et tests Canvas.
- **FILE-005**: `plan-edit.js`, `editor.js`, `editor.html` et tests d’interaction.
- **FILE-006**: Runs, rapport et documentation du sprint.

## 6. Testing

- **TEST-001**: Python et Go acceptent absence ou paire valide et rejettent paire
  partielle, enum invalide et sémantique appliquée à une fenêtre avec le même code.
- **TEST-002**: Les quatre couples produisent quatre battants distincts, bornés,
  avec état Canvas équilibré et entrées non mutées.
- **TEST-003**: Les zones de mobilier utilisent le même point de charnière et la
  même normale signée que le renderer, y compris sur mur inversé et vertical.
- **TEST-004**: L’éditeur cycle quatre états, annule correctement et ne place pas
  de champs de porte sur une fenêtre.
- **TEST-005**: Les 38 captures historiques restent identiques et la médiane de
  rendu ne régresse pas de plus de 10 %.

## 7. Risks & Assumptions

- **RISK-001**: Le sens dépend de l’orientation `a→b`; toute inversion future du
  mur devra transformer les champs ou conserver l’orientation du mur.
- **RISK-002**: Le choix automatique peut être valide géométriquement sans être
  optimal fonctionnellement ; l’outil éditeur permet donc de le corriger.
- **RISK-003**: Une divergence Python/Go/JS rendrait les preuves incohérentes ;
  les mêmes quatre cas doivent être testés dans chaque environnement.
- **ASSUMPTION-001**: Le moteur actuel produit des pièces orthogonales et
  `_served_rooms` identifie correctement les pièces au droit de l’ouverture.

## 8. Related Specifications / Further Reading

- [Sprint menuiseries précédent](refactor-editor-openings-dimensions-1.md)
- [Profil de validation](../packages/plan-schema/validation-profile.md)
- [Rapport menuiseries](../benchmark/comparisons/editor-openings-dimensions/report.md)

