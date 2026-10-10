---
goal: Comparer A-AI et HouseDiffusion sur le corpus d'évaluation 2D commun
version: 1.0
date_created: 2026-10-01
last_updated: 2026-10-01
owner: Projet A-AI
status: 'Completed'
tags: [evaluation, housediffusion, 2d, reproducibilite]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Ce sprint exécute une comparaison géométrique locale entre les sorties A-AI archivées et la sortie intégrée `house_diffusion+opt` sur les dix programmes d'évaluation. Le même évaluateur indépendant et les mêmes graines contrôlées sont utilisés. Les attributs non pris en charge par HouseDiffusion restent des erreurs observées ; ils ne sont pas réparés silencieusement. La campagne finale est archivée dans `benchmark/runs/house-diffusion-comparison-20261001-controlled`; l'archive homonyme sans contrôle de graine est conservée comme essai préliminaire et n'est pas utilisée pour les chiffres finaux.

## 1. Requirements & Constraints

- **REQ-001**: Utiliser les dix cas `split=evaluation` de `benchmark/cases/corpus.json` et les graines 0–4.
- **REQ-002**: Réutiliser les documents A-AI archivés et ne jamais les régénérer dans ce sprint.
- **REQ-003**: Convertir chaque programme en entrée structurée HouseDiffusion et conserver la conversion exacte.
- **REQ-004**: Appeler `research.metrics.geometry.evaluate` sur A-AI et HouseDiffusion avec le même cas original.
- **REQ-005**: Archiver les JSON, PNG, erreurs, configuration, hash du checkpoint et commentaires par programme.
- **CON-001**: HouseDiffusion est exécuté avec `HOUSEDIFFUSION_STEPS=20` pour cette première comparaison ; cette valeur doit apparaître dans tous les rapports.
- **CON-002**: Les cas à emprise non positive sont enregistrés comme refus communs ; aucune sortie artificielle ne leur est attribuée.
- **CON-003**: Les types absents ou fusionnés par le mapping HouseDiffusion sont comptés comme non-conformités du programme, pas corrigés.
- **GUD-001**: Distinguer validité géométrique, rendement combiné et conformité au schéma JSON.
- **PAT-001**: Utiliser un évaluateur indépendant de la génération et une analyse appariée par `case_id/seed`.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Figer les entrées communes et vérifier les prérequis locaux.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Vérifier corpus, archives A-AI, `model250000.pt`, code vendorisé et `available()`. | Oui | 2026-10-01 |
| TASK-002 | Écrire le lanceur sans réseau externe, avec mapping structuré et refus d'emprise partagé. | Oui | 2026-10-01 |

### Implementation Phase 2

- **GOAL-002**: Générer et mesurer les sorties HouseDiffusion.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Générer 10 cas × 5 graines à 20 pas ; archiver les sorties et erreurs sans écraser d'archive. | Oui | 2026-10-01 |
| TASK-004 | Mesurer chaque sortie avec `evaluate` et calculer couverture, géométrie, programme et rendement combiné. | Oui | 2026-10-01 |

### Implementation Phase 3

- **GOAL-003**: Comparer, documenter et revoir les résultats.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Calculer les contrastes appariés A-AI/HouseDiffusion, intervalles descriptifs et analyse des types non supportés. | Oui | 2026-10-01 |
| TASK-006 | Produire le rapport Markdown, mettre à jour l'article et effectuer tests/lint/code-review. | Oui | 2026-10-01 |

## 3. Alternatives

- **ALT-001**: Réduire à un seul échantillon par programme ; rejeté car les archives A-AI contiennent cinq graines et permettent un appariement direct.
- **ALT-002**: Remapper `garage`, `wc` ou `laundry` vers une autre fonction ; rejeté car cela cacherait une limite réelle du modèle.
- **ALT-003**: Utiliser l'image PNG comme vérité ; rejeté car les métriques doivent porter sur les documents vectoriels.

## 4. Dependencies

- **DEP-001**: `model250000.pt` et `vendor/house_diffusion` présents localement.
- **DEP-002**: PyTorch, NumPy, Pillow, Shapely et les modules A-AI importables.
- **DEP-003**: Archive `benchmark/runs/article-evaluation-20260930` intacte.

## 5. Files

- **FILE-001**: `benchmark/house_diffusion_compare.py`.
- **FILE-002**: `benchmark/runs/house-diffusion-comparison-20261001-controlled/`.
- **FILE-003**: `benchmark/article-evaluation/house-diffusion-results.md`.
- **FILE-004**: `docs/articles/ia-plans-verifiables.md` et `docs/sprints/article-evaluation-2.md`.

## 6. Testing

- **TEST-001**: Vérifier dix cas, cinq graines, clés uniques et refus attendus.
- **TEST-002**: Vérifier que chaque sortie mesurée passe par la même fonction `evaluate` et le même cas original.
- **TEST-003**: Vérifier hash du checkpoint, absence de réseau et non-écrasement des archives.
- **TEST-004**: Comparer les dénominateurs A-AI/HouseDiffusion et publier les non-retours séparément.

## 7. Risks & Assumptions

- **RISK-001**: Le mapping RPLAN ne représente pas tous les types du corpus ; cette limite peut dominer le score sémantique.
- **RISK-002**: Vingt pas accélèrent l'essai mais ne constituent pas le réglage original du checkpoint.
- **RISK-003**: Le corpus d'évaluation est public et synthétique ; les intervalles restent descriptifs.
- **ASSUMPTION-001**: L'évaluation commune mesure le document vectoriel produit par `house_diffusion+opt`, pas les contours natifs isolés, l'esthétique ou la conformité réglementaire.

## 8. Related Specifications / Further Reading

- [Protocole article](../benchmark/article-evaluation/protocol.md)
- [Évaluateur géométrique](../research/metrics/geometry.py)
- [HouseDiffusion](https://github.com/aminshabani/house_diffusion)
