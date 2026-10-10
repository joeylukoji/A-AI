---
goal: Rendre le glyphe voiture 2D lisible et contenu dans son empreinte
version: 1.0
date_created: 2026-09-24
last_updated: 2026-09-24
owner: Équipe A-AI
status: Completed
tags: [design, editor, 2d, furniture, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Ce sous-sprint de TASK-012 améliore uniquement le glyphe `car.sedan` dans le
canvas de l'éditeur. Référence appariée : `benchmark/runs/3c-openings-fidelity-v2`
(six documents, 38 PNG). Aucun changement du PlanDocument, de la génération
Gemini/Pillow ou de la 3D.

## 1. Requirements & Constraints

- **REQ-001**: Tous les composants du symbole (carrosserie, vitrage, roues,
  phares et feux) restent dans le rectangle local `[-w/2,w/2] × [-d/2,d/2]`
  pour la taille cataloguée `4,2 × 1,8 m` et les tailles plus petites valides.
- **REQ-002**: Garder un véhicule reconnaissable en vue de dessus avec
  carrosserie claire, cabine vitrée bleue, quatre roues, deux phares et deux
  feux. La longueur du véhicule suit l'axe local X ; la rotation du document
  reste appliquée exclusivement par `beginItem`.
- **REQ-003**: Conserver le style sobre des plans : traits fins, pas d'ombre
  ni reflet, sans déformer le rendu des autres glyphes de mobilier.
- **CON-001**: Modifier uniquement `drawCar` dans
  `web/static/js/plan-style-furniture.js`, ses tests, les documents de sprint
  et les fichiers benchmark ; ne pas changer le catalogue, le générateur ni
  la position du véhicule.
- **CON-002**: Écrire des tests rouges avant production, revoir Standards et
  Spec après chaque bloc, exécuter les suites complètes et comparer les 38
  PNG et six JSON appariés.
- **PAT-001**: Toutes les dimensions internes de la voiture dérivent de `w`
  et `d` (ou sont bornées par ces deux valeurs) ; ne pas ajouter de taille fixe
  qui puisse déborder pour une taille valide.

## 2. Implementation Steps

### Implementation Phase 1 — Contrat géométrique

- **GOAL-001**: Prouver le débordement existant, puis le supprimer sans changer
  la source de vérité du mobilier.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Dans `web/tests/plan-style-furniture.test.cjs`, ajouter un test rouge de `car.sedan` aux tailles 4,2 × 1,8 et 2,1 × 0,9 m et rotations 0/90/270°, inspectant les rectangles/ellipses et les coordonnées des commandes de chemin en repère local ; vérifier non-mutation et `save/restore`. | Oui | 2026-09-24 |
| TASK-002 | Recalculer les roues et les feux dans `drawCar` à partir des bords locaux, sans dépasser l'empreinte ; conserver quatre roues et quatre feux. | Oui | 2026-09-24 |
| TASK-003 | Revue Standards/Spec et tests Node ciblés ; documenter le résultat géométrique. | Oui | 2026-09-24 |

### Implementation Phase 2 — Lecture du symbole et benchmark

- **GOAL-002**: Rendre la cabine et la silhouette plus faciles à reconnaître
  aux zooms 50/100/200 %, sans changer le modèle de données.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Ajouter des assertions rouges sur les éléments de cabine : vitrage avant et arrière distincts, axe X du véhicule inchangé, et état canvas équilibré. | Oui | 2026-09-24 |
| TASK-005 | Ajuster `drawCar` dans le style existant avec deux zones vitrées et des séparations fines, bornées par `w` et `d`, sans inventer d'autres objets. | Oui | 2026-09-24 |
| TASK-006 | Revue Standards/Spec, tests Node/benchmark/Go/Ruff, capture dans `benchmark/runs/3d-car-glyph-v2`, rapport `benchmark/comparisons/3d-car-glyph/report.md`, bilan et statut TASK-012. | Oui | 2026-09-24 |

## 3. Alternatives

- **ALT-001**: Utiliser une image photographique de voiture : rejeté, car le
  symbole doit rester vectoriel et net aux trois zooms.
- **ALT-002**: Déplacer la voiture ou le libellé GARAGE : rejeté, car cela
  change une responsabilité distincte de la géométrie du glyphe.

## 4. Dependencies

- **DEP-001**: `PlanStyleFurniture.drawFurniture` et `beginItem` appliquent
  déjà translation, rotation et échelle du document.
- **DEP-002**: `benchmark/editor_capture.py` fournit les 38 vues de référence.

## 5. Files

- **FILE-001**: `web/static/js/plan-style-furniture.js`.
- **FILE-002**: `web/tests/plan-style-furniture.test.cjs`.
- **FILE-003**: `docs/sprints/3c-bilan.md`, ce plan,
  `docs/refactor-mvp-2d-1.md` et le rapport benchmark.

## 6. Testing

- **TEST-001**: Mock canvas vérifiant points et rectangles dans l'empreinte
  locale, quatre roues/feux, vitrage avant/arrière, rotations et non-mutation.
- **TEST-002**: Comparer par SHA-256 les 38 PNG et six JSON d'entrée ; inspecter
  les vues de garage `dev02` et `dev13` à 50/100/200 %.
- **TEST-003**: `node --test "web/tests/*.test.cjs"`,
  `python -m pytest benchmark/tests -q`, `go test ./internal/httpapi`,
  Ruff ciblé et `git diff --check`.

## 7. Risks & Assumptions

- **RISK-001**: Les vues à 50 % peuvent masquer les détails de cabine ; ne
  conclure à un gain perceptif que par inspection, pas par seul nombre de
  pixels modifiés.
- **RISK-002**: Les commandes Bezier de la carrosserie exigent de contrôler
  les points de contrôle et les extrémités, pas seulement les rectangles.
- **ASSUMPTION-001**: Toute taille strictement positive est valide pour le
  renderer ; les détails deviennent proportionnels à cette taille.

## 8. Related Specifications / Further Reading

- [Plan MVP 2D](../refactor-mvp-2d-1.md)
- [Bilan sprint 3C](3c-bilan.md)
- [Référence visuelle](../../benchmark/runs/3c-openings-fidelity-v2/manifest.json)
