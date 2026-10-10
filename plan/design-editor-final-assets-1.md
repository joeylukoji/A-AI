---
goal: Finaliser le catalogue réaliste et optimiser les sprites du plan 2D
version: 1.0
date_created: 2026-09-27
last_updated: 2026-09-27
owner: Équipe A-AI
status: 'Completed'
tags: [design, editor, 2d, assets, performance, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Ce sprint remplace les six derniers glyphes vectoriels visibles par des sprites
réalistes cohérents avec les références utilisateur, puis réduit le poids du
catalogue sans modifier les documents, empreintes ou interactions de l’éditeur.
La référence avant modification est `benchmark/runs/editor-technical-assets-v1`.

## 1. Requirements & Constraints

- **REQ-001**: Produire des PNG RGBA réellement transparents pour `nightstand`,
  `wardrobe`, `desk`, `fireplace`, `rug.rect` et `tv.console`, en vue verticale
  orthographique et sans objet supplémentaire.
- **REQ-002**: Respecter les empreintes nominales 0,45 × 0,40 m, 1,20 × 0,60 m,
  1,20 × 0,60 m, 0,70 × 0,55 m, 2,20 × 1,60 m et 1,60 × 0,40 m.
- **REQ-003**: Conserver positions, rotations, clipping, ordre de dessin du tapis,
  sélection, export Canvas, documents d’entrée et fallback vectoriel.
- **REQ-004**: Charger uniquement des chemins locaux déclarés dans la liste fermée
  du chargeur et mettre les images en cache par identifiant de catalogue.
- **REQ-005**: Réduire le poids total du catalogue par redimensionnement et
  réencodage déterministes, avec comparaison visuelle avant/après et conservation
  d’une résolution minimale de 512 px sur chaque axe. Plafonner normalement le
  grand côté à 1280 px ; autoriser 2048 px pour le ratio extrême 4:1 du meuble TV.
- **REQ-006**: Produire un benchmark apparié comprenant catalogue, 38 captures,
  hashes des six documents, métriques de poids et analyse visuelle aux zooms
  50 %, 100 % et 200 %.
- **CON-001**: Ne modifier ni Gemini, ni la pipeline de génération, ni la 3D, ni
  l’agencement logique du mobilier.
- **GUD-001**: Les textures doivent rester sobres, contemporaines et lisibles à
  l’échelle d’un plan complet. Un micro-relief zénithal comparable aux références
  utilisateur est admis, mais il ne doit pas modifier la silhouette ni l’empreinte.
- **PAT-001**: Conserver le pattern Asset Registry + Lazy Loading + Vector Fallback
  de `web/static/js/plan-style-assets.js`.

## 2. Implementation Steps

### Implementation Phase 1 — Baseline et assets

- GOAL-001: Créer les six sprites finaux et établir la mesure de poids initiale.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Mesurer le poids, les dimensions et les alphas des 16 PNG existants ; archiver les métriques comme baseline dans le rapport du sprint. | Oui | 2026-09-27 |
| TASK-002 | Générer séparément les six objets via ImageGen intégré, inspecter chaque sortie, rejeter tout fond, halo, perspective ou accessoire, puis copier les variantes retenues dans `web/static/assets/furniture/`. Dépend de TASK-001. | Oui | 2026-09-27 |

### Implementation Phase 2 — Intégration et optimisation

- GOAL-002: Étendre le registre sans changer son contrat et diminuer le coût des assets.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Ajouter les attentes des six identifiants dans `web/tests/plan-style-assets.test.cjs`, puis leurs fichiers versionnés dans `web/static/js/plan-style-assets.js`; vérifier empreintes, absence de rotation implicite, ordre du tapis, fallback et non-mutation. Dépend de TASK-002. | Oui | 2026-09-27 |
| TASK-004 | Optimiser les 22 PNG dans une copie de travail, comparer taille, alpha et rendu, puis ne remplacer que les fichiers dont la réduction est visuellement équivalente. Dépend de TASK-003. | Oui | 2026-09-27 |

### Implementation Phase 3 — Benchmark, revue et documentation

- GOAL-003: Prouver la stabilité et documenter honnêtement les gains et limites.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Générer la planche catalogue avant/après et les 38 captures dans de nouveaux dossiers ; contrôler les six JSON, les requêtes réseau et les vues représentatives à 50/100/200 %. Dépend de TASK-004. | Oui | 2026-09-27 |
| TASK-006 | Exécuter Node, pytest benchmark, Go HTTP, Ruff et diff-check ; faire les revues Standards/Spec, corriger les défauts, publier le rapport et mettre à jour `docs/`. Dépend de TASK-005. | Oui | 2026-09-27 |

## 3. Alternatives

- **ALT-001**: Conserver les six dessins Canvas : rejeté car leur contraste avec
  les seize sprites est désormais le principal défaut visuel restant.
- **ALT-002**: Fusionner plusieurs meubles en une image de pièce : rejeté car
  cela supprimerait leur édition, rotation et dimensionnement indépendants.
- **ALT-003**: Convertir en WebP : différé afin de conserver le contrat PNG RGBA
  actuel et de séparer changement visuel et changement de format.

## 4. Dependencies

- **DEP-001**: Outil ImageGen intégré pour les nouveaux sprites.
- **DEP-002**: Pillow et Playwright déjà utilisés par le benchmark local.
- **DEP-003**: Baseline `editor-technical-assets-v1` et archive de sources associée.

## 5. Files

- **FILE-001**: `web/static/assets/furniture/*.png` et `README.md`.
- **FILE-002**: `web/static/js/plan-style-assets.js`.
- **FILE-003**: `web/tests/plan-style-assets.test.cjs` et `benchmark/tests/test_editor_assets.py`.
- **FILE-004**: `benchmark/runs/`, `benchmark/comparisons/editor-final-assets/report.md`.
- **FILE-005**: `docs/sprints/design-editor-final-assets-1.md`, `docs/sprints/3c-bilan.md` et `docs/refactor-mvp-2d-1.md`.

## 6. Testing

- **TEST-001**: Chaque PNG est RGBA, possède un alpha 0–255, des coins
  transparents, une bordure sans fuite visible et au moins 512 px par axe.
- **TEST-002**: Les six nouveaux identifiants résolvent un fichier local unique,
  dessiné dans l’empreinte exacte sans rotation interne implicite.
- **TEST-003**: Les 38 captures terminent sans erreur ni requête externe et les
  six documents d’entrée conservent leurs hashes.
- **TEST-004**: Le poids final et le ratio de réduction sont calculés sur les 22
  fichiers ; les captures de contrôle ne montrent pas de dégradation perceptible.
- **TEST-005**: Les suites Node, Python benchmark, Go HTTP, Ruff et diff-check passent.

## 7. Risks & Assumptions

- **RISK-001**: Une texture trop détaillée peut devenir du bruit à 50 % ; valider
  d’abord sur les plans complets, pas uniquement sur la planche catalogue.
- **RISK-002**: Un redimensionnement trop agressif peut flouter à 200 % ; conserver
  les originaux tant que la comparaison n’est pas validée.
- **RISK-003**: Le foyer de cheminée peut sembler oblique ; exiger une silhouette
  strictement vue du dessus et une ombre contenue dans l’empreinte.
- **ASSUMPTION-001**: Les dimensions du catalogue restent la vérité géométrique ;
  les PNG sont exclusivement une couche de présentation.

## 8. Related Specifications / Further Reading

- [Sprint technique précédent](../docs/sprints/design-editor-technical-assets-1.md)
- [Rapport technique précédent](../benchmark/comparisons/editor-technical-assets/report.md)
- [Plan MVP 2D](../docs/refactor-mvp-2d-1.md)
- [Rapport final](../benchmark/comparisons/editor-final-assets/report.md)
