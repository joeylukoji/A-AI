---
goal: Réconcilier l'énumération du mobilier et les fixtures du contrat PlanDocument
version: 1.0
date_created: 2026-10-04
last_updated: 2026-10-04
owner: Projet A-AI
status: 'Completed'
tags: [refactor, schema, catalogue, benchmark, 2d, reproducibilite]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Corriger les désaccords vérifiés entre l'énumération `catalog_id` du schéma JSON,
le catalogue de placement 2D et les fixtures partagées, puis réauditer les documents
archivés sous le schéma corrigé sans modifier la campagne ni écraser son audit historique.
Ce sprint ne modifie ni la géométrie produite, ni les dimensions de mobilier, ni la 3D.

## 1. Requirements & Constraints

- **REQ-001**: `packages/plan-schema/plan-document.schema.json` doit accepter exactement les IDs mobiliers de `services/ai/app/furnish.py:CATALOG`, sans inclure `wall.exterior` ni `wall.interior` dans `furniture.catalog_id`.
- **REQ-002**: Le document de base de `packages/plan-schema/validation-cases.json` doit satisfaire les champs exigés par le schéma, notamment `thickness_m` strictement positif pour ses quatre murs.
- **REQ-003**: Un test de contrat doit détecter toute dérive future entre les IDs du schéma, `furnish.CATALOG` et les IDs mobiliers du catalogue Blender, sans assimiler les deux types de murs à du mobilier.
- **REQ-004**: L'audit du schéma doit pouvoir utiliser un schéma explicitement fourni et enregistrer son empreinte ainsi que le fait qu'il diffère du schéma gelé; le mode par défaut conserve son refus si l'empreinte ne correspond plus.
- **REQ-005**: Documenter la frontière entre le profil d'exécution Python/Go (qui ignore les métadonnées inconnues) et le schéma JSON publié (contrat déclaratif fermé et plus strict); ne pas présenter leur acceptation comme équivalente.
- **REQ-006**: Réauditer les 135 documents archivés avec le nouveau schéma dans un artefact inédit; conserver intacts P9, son rapport, les documents, les PNG et les manifestes de l'expérience.
- **REQ-007**: Mettre à jour l'article et les bilans pour distinguer le résultat historique sous l'ancien schéma du nouvel audit post hoc, sans modifier les scores de génération.
- **CON-001**: Rester dans le périmètre 2D/contrat; aucun changement de placement, de rendu, de dimensions de mobilier, de sortie générée ou de code 3D.
- **CON-002**: Ne pas écraser une archive, un rapport, une sortie d'audit, un document de l'étude ou le DOCX utilisateur.
- **CON-003**: L'énumération physique `table.dining` diffère actuellement entre `furnish.CATALOG` (1,80 × 1,00 m) et le catalogue Blender (1,60 × 0,90 m); la documenter comme limite non résolue et ne pas choisir silencieusement une dimension dans ce sprint.
- **GUD-001**: Archiver un rapport d'audit révisé dans un nouveau chemin et préciser que l'application d'un schéma courant à des documents historiques est une analyse post hoc, non le critère préenregistré de l'expérience.
- **PAT-001**: Garder le schéma JSON comme artefact déclaratif; dériver son test de conformité des IDs de `CATALOG` au lieu de créer un second catalogue applicatif.

## 2. Implementation Steps

### Implementation Phase 1 — diagnostic et référence documentaire

- **GOAL-001**: Formaliser les écarts avant toute modification.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Comparer `services/ai/app/furnish.py:CATALOG`, `services/blender/catalog/catalog.json`, `plan-document.schema.json` et `validation-cases.json`; consigner les 22 IDs de mobilier, les 2 IDs de murs, les 13 IDs absents du schéma, les quatre épaisseurs absentes de la fixture et la divergence de dimensions `table.dining`. | ✅ | 2026-10-04 |

### Implementation Phase 2 — schéma, fixture et garde de dérive

- **GOAL-002**: Rendre l'énumération JSON cohérente avec le mobilier 2D et rendre la fixture commune valide selon son schéma.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-002 | Mettre à jour uniquement `$defs.furniture_instance.properties.catalog_id.enum` avec les 22 clés triées de `furnish.CATALOG`; ne pas inclure les IDs `wall.*` du catalogue Blender et ne modifier aucune taille ou géométrie. | ✅ | 2026-10-04 |
| TASK-003 | Ajouter `thickness_m: 0.2` aux quatre murs de `validation-cases.json.base`; conserver inchangés les cas de mutation et l'acceptation du profil Python/Go existant. | ✅ | 2026-10-04 |
| TASK-004 | Ajouter `test_schema_furniture_catalog_ids_match_runtime_catalog` dans `benchmark/tests/test_plan_schema.py`; vérifier égalité exacte schéma/runtime et égalité catalogue Blender moins `wall.exterior`/`wall.interior` avec `CATALOG`. | ✅ | 2026-10-04 |

### Implementation Phase 3 — audit révisé, tests et clôture

- **GOAL-003**: Reproduire l'audit sous le nouveau schéma sans contaminer les résultats historiques.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Étendre `benchmark/article_schema_report.py:report` avec un argument `--schema` facultatif; garder le mode par défaut et son contrôle d'empreinte strict, et écrire `schema_selection`, `frozen_schema_sha256` et `matches_frozen_schema` dans tout nouvel audit. Tester le chemin explicite et le refus d'écrasement. | ✅ | 2026-10-04 |
| TASK-006 | Exécuter l'audit courant vers `benchmark/article-evaluation/schema-audit-current-20261004.json`; confirmer les 135 retours, l'empreinte explicite et la distribution des erreurs sans toucher `schema-audit.json`. Comparer aussi le schéma d'archive au schéma courant pour identifier les différences responsables de la requalification. | ✅ — 135/135 valides, zéro erreur; P9 intact; diff sémantique du schéma limité à l'enum mobilier (9 → 22 IDs) | 2026-10-04 |
| TASK-007 | Exécuter les tests schema Python, contrat Python partagé et tests Go `./internal/plan`; exécuter Ruff, `git diff --check`, revue Standards/Spec et mettre à jour l'article, le bilan `docs/sprints/article-evaluation-2.md` et ce plan. | ✅ — benchmark 132; validation IA 89; Go OK; Ruff OK; revues OK | 2026-10-04 |

## 3. Alternatives

- **ALT-001**: Ajouter les 13 IDs manquants uniquement dans la fixture; rejeté car les sorties réelles resteraient interdites par le contrat publié.
- **ALT-002**: Supprimer l'énumération du schéma au profit d'un texte libre; rejeté car la liste est vérifiable et les IDs inconnus doivent rester détectables.
- **ALT-003**: Réécrire P9 pour afficher le nouveau résultat; rejeté car cela effacerait l'observation produite sous le schéma gelé.
- **ALT-004**: Modifier les dimensions d'une chaise/table pour faire coïncider 2D et 3D; différé car c'est un changement de génération qui exige un benchmark distinct et une décision sur la dimension canonique.
- **DEC-001**: Conserver l'enum du schéma et ses propriétés fermées. La revue a confirmé que le profil géométrique runtime et le schéma déclaratif ont des périmètres différents; expliciter cette limite dans le profil et tester séparément les deux comportements, plutôt que d'effacer la détection des IDs inconnus.

## 4. Dependencies

- **DEP-001**: `services/ai/app/furnish.py:CATALOG` comme liste opérationnelle des types de mobilier de la pipeline 2D.
- **DEP-002**: `services/blender/catalog/catalog.json` pour détecter la présence des mêmes IDs côté catalogue d'assets, sans traiter les murs comme meubles.
- **DEP-003**: Sources/manifestes archivés de `benchmark/runs/article-evaluation-20260930/` et évaluateur `jsonschema` Draft 2020-12.

## 5. Files

- **FILE-001**: `packages/plan-schema/plan-document.schema.json` — enum mobilier publiée.
- **FILE-002**: `packages/plan-schema/validation-cases.json` — base de fixture complète.
- **FILE-003**: `benchmark/tests/test_plan_schema.py` — assertions de cohérence inter-catalogues.
- **FILE-004**: `benchmark/article_schema_report.py` et `benchmark/tests/test_article_schema_report.py` — provenance explicite des audits.
- **FILE-005**: `benchmark/article-evaluation/schema-audit-current-20261004.json` — nouvelle preuve post hoc, jamais écrasée.
- **FILE-006**: `docs/articles/ia-plans-verifiables.md`, `docs/sprints/article-evaluation-2.md` et ce plan — distinction historique/courante et limites.

## 6. Testing

- **TEST-001**: `python -m pytest benchmark/tests/test_plan_schema.py -q` accepte la porte valide, rejette ses variantes invalides et vérifie les IDs de catalogue.
- **TEST-002**: `python -m pytest services/ai/tests/test_document_validation.py -q` confirme l'absence de régression des fixtures Python partagées.
- **TEST-003**: `go test ./internal/plan` confirme la même fixture partagée côté Go.
- **TEST-004**: Les tests `benchmark/tests/test_article_schema_report.py` couvrent mode gelé, refus avec empreinte divergente, mode schema explicite différent, provenance, comptage et sortie en écriture exclusive.
- **TEST-005**: Le nouvel audit porte sur exactement 135 documents; chaque observation conserve son SHA-256 et le rapport historique reste byte-for-byte intact.
- **TEST-006**: Ruff, format et `git diff --check` passent sur les fichiers concernés; les revues Standards/Spec ne trouvent pas d'écart bloquant.

## 7. Risks & Assumptions

- **RISK-001**: Un réaudit avec un schéma plus récent change la qualification post hoc sans changer les documents; présenter les deux empreintes et ne pas remplacer le résultat gelé.
- **RISK-002**: Le contrôle JSON Schema accepte la syntaxe/énumération mais ne prouve pas une faisabilité constructive ou architecturale.
- **RISK-003**: L'écart de dimensions `table.dining` peut décaler la représentation 3D par rapport au placement 2D; il reste ouvert à un sprint de mobilier mesuré.
- **ASSUMPTION-001**: Les 22 clés de `furnish.CATALOG` sont les seuls identifiants autorisés dans le champ de mobilier 2D; `wall.exterior` et `wall.interior` ne sont pas des `catalog_id` de meubles.
- **ASSUMPTION-002**: Les 135 résultats archivés et leur ordre de statuts sont immuables; seule l'interprétation selon une empreinte de schéma distincte sera ajoutée.

## 8. Related Specifications / Further Reading

- `docs/sprints/article-evaluation-2.md` — comparaison géométrique commune proposée; prérequis de catalogue désormais satisfaits.
- `packages/plan-schema/validation-profile.md` — limites du contrôle géométrique Python/Go.
- `benchmark/article_schema_report.py` — protocole d'audit post hoc préexistant.
