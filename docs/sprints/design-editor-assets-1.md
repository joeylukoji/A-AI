---
goal: Remplacer le mobilier schématique principal par des sprites réalistes de dessus
version: 1.0
date_created: 2026-09-25
last_updated: 2026-09-26
owner: Équipe A-AI
status: Completed
tags: [design, editor, 2d, assets, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Le rendu vectoriel du sprint précédent est fonctionnel mais rejeté visuellement
par l'utilisateur. Changer la représentation du mobilier principal, pas la
géométrie ni le moteur Gemini. Référence avant : `editor-modern-v2`.

## 1. Requirements & Constraints

- **REQ-001**: Produire des assets orthographiques de dessus, détourés avec alpha,
  pour les lits, canapés, voiture et plante. Matières textiles et feuillage réels,
  proportions lisibles et palette coordonnée ; aucun texte ou sol dans les assets.
- **REQ-002**: Intégrer les sprites au vrai Canvas de l'éditeur, avec chargement
  local, rendu vectoriel de secours en cas d'échec et rafraîchissement automatique.
- **REQ-003**: Préserver positions, dimensions, rotations, clipping, ordre des
  tapis, sélection, export Canvas et documents JSON ; aucun objet supplémentaire.
- **REQ-004**: Comparer les 38 vues et le catalogue avec la version rejetée ;
  archiver sources et assets. Inspecter le résultat à 100 %, pas seulement les assets.
- **CON-001**: Uniquement éditeur 2D ; pas de génération Gemini ni de 3D.
- **PAT-001**: Isoler le chargement d'assets du dessin vectoriel et de l'éditeur.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Valider une direction matérielle réellement différente.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Générer et inspecter séparément les sprites avec imagegen ; copier les sorties retenues dans `web/static/assets/furniture/`, documenter prompts et provenance. | Oui | 2026-09-25 |

### Implementation Phase 2

- **GOAL-002**: Intégrer le rendu sans fragiliser les interactions.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-002 | Après TASK-001, tester puis ajouter le chargeur `plan-style-assets.js`, son contrat prepare/draw et le fallback ; brancher `plan-style-furniture.js`, `plan-style.js`, `editor.js` et le template. Revue Standards/Spec. | Oui | 2026-09-26 |
| TASK-003 | Adapter les harnais `benchmark/editor_capture.py` et `catalogue_capture.py` au chargement strictement local des assets, attendre prepare et archiver leurs hashes. Revue Standards/Spec. | Oui | 2026-09-26 |

### Implementation Phase 3

- **GOAL-003**: Livrer des images vérifiables du vrai éditeur.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Après TASK-002 et TASK-003, exécuter les tests Node, benchmark et Go, capturer avant/après, inspecter plans/catalogue puis rédiger `benchmark/comparisons/editor-assets/report.md` et mettre à jour le bilan. | Oui | 2026-09-26 |

## 3. Alternatives

- **ALT-001**: Nouvelle retouche vectorielle seule : rejetée après le retour utilisateur.
- **ALT-002**: Image décorative de plan complet : rejetée car non éditable.

## 4. Dependencies

- **DEP-001**: Outil imagegen intégré ; aucune API externe au chargement de l'éditeur.
- **DEP-002**: Canvas 2D et harnais Chromium existants.

## 5. Files

- **FILE-001**: `web/static/assets/furniture/`, `web/static/js/plan-style-assets.js` et modules d'intégration cités dans TASK-002.
- **FILE-002**: `web/tests/plan-style-assets.test.cjs` et harnais cités dans TASK-003.
- **FILE-003**: Ce sprint, rapport benchmark et `docs/sprints/3c-bilan.md`.

## 6. Testing

- **TEST-001**: Succès, erreur de chargement, déduplication, sprite inconnu, transformations et non-mutation.
- **TEST-002**: 38 captures, six JSON inchangés, absence de dépendance réseau externe, PNG exportable sans Canvas contaminé.
- **TEST-003**: Tests Node, pytest benchmark, Go HTTP, Ruff pour Python et `git diff --check`.

## 7. Risks & Assumptions

- **RISK-001**: Transparence ou projection imparfaite : inspecter avant intégration, ne pas masquer le défaut par un fond blanc.
- **RISK-002**: Poids mémoire et chargement : mutualiser les images et conserver un fallback utilisable.
- **ASSUMPTION-001**: Les principaux meubles réalistes peuvent cohabiter avec les petits symboles techniques vectoriels ; vérifier la cohérence sur plan complet.

## 8. Related Specifications / Further Reading

- [Sprint précédent](design-editor-modern-1.md)
- [Plan MVP](../refactor-mvp-2d-1.md)
- [Résultat, mesures et limites](../../benchmark/comparisons/editor-assets/report.md)
