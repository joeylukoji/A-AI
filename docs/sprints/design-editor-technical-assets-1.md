---
goal: Harmoniser les zones cuisine, repas et sanitaires du plan 2D
version: 1.0
date_created: 2026-09-27
last_updated: 2026-09-27
owner: Équipe A-AI
status: Completed
tags: [design, editor, 2d, assets, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Le sprint précédent a amélioré les gros meubles mais laisse un contraste visible
avec les objets techniques encore vectoriels. Ce sprint remplace les neuf types
les plus visibles des zones repas, cuisine et sanitaires. Référence mesurée :
`benchmark/runs/editor-assets-v2`.

## 1. Requirements & Constraints

- **REQ-001**: Créer neuf sprites RGBA en projection verticale de dessus et sans décor pour
  `table.dining`, `chair.dining`, `table.coffee`, `counter.kitchen`, `stove`,
  `fridge`, `bathtub`, `toilet` et `sink.basin`, dans la palette chêne clair,
  pierre blanche, métal anthracite et céramique blanche du rendu existant. Un
  micro-relief par éclairage est admis comme dans les références utilisateur,
  sans perspective oblique modifiant la silhouette ou l'empreinte.
- **REQ-002**: Conserver exactement les empreintes nominales, positions,
  rotations, clipping, documents et ordre de dessin. Garder le fallback vectoriel.
- **REQ-003**: Étendre la liste locale fermée du chargeur sans dupliquer sa
  logique ni créer d’URL depuis les données du plan.
- **REQ-004**: Inspecter chaque alpha et le catalogue complet, puis comparer les
  mêmes 38 captures avec `editor-assets-v2`, en distinguant vues modifiées et
  vues sans objet concerné.
- **REQ-005**: Documenter prompts, provenance, poids, revue Standards/Spec et
  limites ; ne pas prétendre qu’un test fonctionnel prouve la qualité esthétique.
- **CON-001**: Uniquement le Canvas 2D de l’éditeur ; ni Gemini, ni 3D, ni
  modification d’agencement.
- **PAT-001**: Un asset versionné par type ; chargement à la demande et cache
  partagé déjà fourni par `plan-style-assets.js`.

## 2. Implementation Steps

### Implementation Phase 1 — Assets

- **GOAL-001**: Produire un ensemble cohérent, proprement détouré et orienté.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Générer séparément les neuf objets avec imagegen, inspecter cadrage et transparence, rejeter les damiers/halos opaques, copier les variantes retenues dans `web/static/assets/furniture/` et ajouter leurs prompts au README. | Oui | 2026-09-27 |

### Implementation Phase 2 — Intégration

- **GOAL-002**: Étendre le renderer sans changer son contrat.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-002 | Après TASK-001, ajouter d’abord les attentes aux tests, puis déclarer les neuf fichiers dans `plan-style-assets.js`; vérifier orientation, empreinte, déduplication, fallback et export Canvas. Exécuter une revue Standards/Spec. | Oui | 2026-09-27 |

### Implementation Phase 3 — Validation

- **GOAL-003**: Prouver la stabilité fonctionnelle et rendre le résultat inspectable.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Après TASK-002, capturer le catalogue et les 38 vues dans de nouveaux dossiers, comparer hashes image/JSON et inspecter cuisine, repas, salle de bains aux zooms 50/100/200 %. | Oui | 2026-09-27 |
| TASK-004 | Exécuter Node, pytest benchmark, Go HTTP, Ruff et diff-check ; publier le rapport avant/après et mettre à jour `3c-bilan.md` et le plan MVP. | Oui | 2026-09-27 |

## 3. Alternatives

- **ALT-001**: Refaire ces objets en Canvas : rejeté car le contraste vectoriel
  est précisément le défaut encore visible.
- **ALT-002**: Générer une cuisine ou salle de bains complète en une image :
  rejeté car cela détruirait les instances, dimensions et rotations éditables.

## 4. Dependencies

- **DEP-001**: Outil imagegen intégré et stockage local des PNG.
- **DEP-002**: Chargeur, fallback et harnais offline livrés au sprint précédent.

## 5. Files

- **FILE-001**: `web/static/assets/furniture/*.png` et son `README.md`.
- **FILE-002**: `web/static/js/plan-style-assets.js` et tests associés.
- **FILE-003**: `benchmark/runs/`, nouveau rapport, ce plan et bilans 2D.

## 6. Testing

- **TEST-001**: PNG RGBA avec alpha 0–255, coin transparent et résolution minimale.
- **TEST-002**: Routage des neuf IDs, transformations locales, clipping,
  chargement unique, fallback et non-mutation.
- **TEST-003**: 38 captures, six documents inchangés, requêtes externes nulles,
  catalogue complet et suites Node/Python/Go au vert.

## 7. Risks & Assumptions

- **RISK-001**: Un détail trop fin disparaît à 50 % ; juger aussi le plan complet,
  pas seulement la planche catalogue agrandie.
- **RISK-002**: Les PNG augmentent le poids ; seuls les types présents chargent,
  mais une optimisation d’encodage restera à planifier séparément.
- **ASSUMPTION-001**: Les dimensions du catalogue constituent la vérité
  géométrique ; les pixels servent uniquement à la présentation.

## 8. Related Specifications / Further Reading

- [Sprint mobilier principal](design-editor-assets-1.md)
- [Rapport mobilier principal](../../benchmark/comparisons/editor-assets/report.md)
- [Plan MVP 2D](../refactor-mvp-2d-1.md)
- [Rapport du sprint](../../benchmark/comparisons/editor-technical-assets/report.md)
