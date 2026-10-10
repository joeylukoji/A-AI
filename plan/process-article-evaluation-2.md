---
goal: Corriger le manuscrit utilisateur et établir une comparaison vérifiable des générateurs de plans
version: 1.0
date_created: 2026-09-30
last_updated: 2026-09-30
owner: Projet A-AI
status: 'In progress'
tags: [article, evaluation, statistiques, reproducibilite]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In_progress-yellow)

Réviser `docs/articles/ia-plans-verifiables.md` à partir de la version récente du DOCX utilisateur et de sa pré-évaluation. Séparer résultats observés, protocole à exécuter et simulations éventuelles. Ne pas modifier le générateur pour améliorer ses scores après lecture du jeu d'évaluation.

Les six tâches initiales ci-dessous sont réalisées ; un audit complémentaire du schéma est ajouté après le contrôle élargi. La demande globale reste en cours pour la comparaison géométrique spécialisée. Le [bilan](../docs/sprints/article-evaluation-2.md) distingue les résultats acquis, l'échec de fixture préexistant et le sprint suivant.

## 1. Requirements & Constraints

- **REQ-001**: Conserver une seule version, corriger les formules, expliciter la provenance des figures et le rôle réel des modèles.
- **REQ-002**: Exécuter le parcours local de l'application sur le jeu d'évaluation et deux ablations isolées ; archiver entrées, sources, sorties, métriques et erreurs.
- **REQ-003**: Définir une comparaison A-AI, LLM généraliste et modèle spécialisé préentraîné avec entrées comparables et évaluateur commun.
- **REQ-004**: Calculer rendement combiné, diversité géométrique, intervalles par programme et différences appariées à partir des données réelles.
- **CON-001**: Aucune mesure inventée présentée comme observation. Une expérience non exécutée reçoit le statut non mesuré, jamais zéro ni un score simulé.
- **CON-002**: Conserver le DOCX original, les archives et toutes les modifications utilisateur préexistantes ; ne pas publier de dépôt ni engager de dépense indéfinie.
- **CON-003**: Ne pas inférer auteurs, financement, affiliation, validation réglementaire ou preuve de généralisation.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Préparer les sources et figer le protocole avant exécution.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Extraire la version récente du DOCX, lire les remarques et examiner les points d'entrée de l'application, sans changer la pipeline. | Oui | 2026-09-30 |
| TASK-002 | Écrire `benchmark/article-evaluation/protocol.md` : variantes, corpus, métriques, exclusions, statut des modèles externes. | Oui | 2026-09-30 |

### Implementation Phase 2

- **GOAL-002**: Produire des observations auditables après TASK-002.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Ajouter un lanceur et un analyseur dédiés ; figer les sources avant les 10 programmes × 5 graines ; effectuer deux ablations sans retoucher la production. | Oui | 2026-09-30 |
| TASK-004 | Tester les métriques, les dénominateurs et l'archivage ; vérifier l'accès applicatif et déterminer les prérequis manquants des références externes. | Oui ; limites documentées | 2026-09-30 |

### Implementation Phase 3

- **GOAL-003**: Mettre à jour le manuscrit après TASK-003 et TASK-004.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Réviser `docs/articles/ia-plans-verifiables.md`, bibliographie primaire vérifiée, schéma cohérent et tableau de travaux connexes. | Oui | 2026-09-30 |
| TASK-006 | Revues Standards/Spec, contrôle des calculs et liens, bilan `docs/sprints/article-evaluation-2.md` et matrice des remarques traitées. | Oui | 2026-09-30 |
| TASK-007 | Auditer hors réseau les documents archivés contre le schéma JSON gelé avec `benchmark/article_schema_report.py` ; publier séparément ce contrôle post hoc et ses limites dans le manuscrit ; ne réparer ni production ni observations. | Oui ; incohérence publiée | 2026-09-30 |

## 3. Alternatives

- **ALT-001**: Des scores fictifs comparatifs sont exclus ; les tests unitaires peuvent employer des valeurs synthétiques étiquetées sans les intégrer aux résultats empiriques.
- **ALT-002**: Comparer uniquement des images ne permet pas de tester des contraintes métriques sans annotations ou vectorisation validée.

## 4. Dependencies

- **DEP-001**: Python et dépendances existantes, corpus local et sources actuelles de l'application.
- **DEP-002**: Les expériences distantes nécessitent un fournisseur accessible et un budget ; le modèle spécialisé nécessite poids, données autorisées et adaptateur vérifié.

## 5. Files

- **FILE-001**: `benchmark/article-evaluation/`, protocole et rapport.
- **FILE-002**: `benchmark/article_evaluate.py`, `benchmark/article_statistics.py`, `benchmark/tests/test_article_statistics.py`.
- **FILE-003**: `docs/articles/ia-plans-verifiables.md`, figures et suivi des corrections.

## 6. Testing

- **TEST-001**: Tests sur rendements, intervalles, absence de retours, diversité et appariement par programme.
- **TEST-002**: Zéro appel réseau dans le parcours local ; gel SHA-256 et non-écrasement des résultats.
- **TEST-003**: Concordance de chaque chiffre du manuscrit avec les observations, références et liens vérifiés.

## 7. Risks & Assumptions

- **RISK-001**: Le corpus existant est visible dans le dépôt ; parler de séparation développement/évaluation, pas de test aveugle indépendant.
- **RISK-002**: Les annotations de comptage n'évaluent pas la totalité de la sémantique ou de l'usage architectural.
- **ASSUMPTION-001**: La sortie demandée est le Markdown ; le DOCX fourni est une source de fond, pas un fichier à écraser.

## 8. Related Specifications / Further Reading

- [Premier article](process-article-scientifique-1.md)
- [Corpus](../benchmark/cases/corpus.json)
