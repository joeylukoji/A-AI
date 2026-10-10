---
goal: Présenter les générations Docker et leurs briefs pour choisir cinq figures d'article
version: 1.0
date_created: 2026-09-29
last_updated: 2026-09-29
owner: Projet A-AI
status: 'Completed'
tags: [documentation, figures, provenance]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Constituer une galerie locale des aperçus de génération, sans captures de l'éditeur et sans appels de génération. Les résultats de modèles doivent être distingués des replis locaux.

## 1. Requirements & Constraints

- **REQ-001**: Lire PostgreSQL et MinIO locaux, relier chaque résultat à son job et à son brief historique.
- **REQ-002**: Placer le brief à côté de l'image, numéroter les candidats et permettre la sélection de cinq images.
- **CON-001**: Aucune mutation de base, de bucket, ni génération externe ; ne pas exposer d'identifiants utilisateurs ou de secrets.
- **CON-002**: Ne pas prétendre disposer du prompt technique complet ou d'une preuve de modèle quand ils ne sont pas archivés.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Retrouver les preuves et exporter les originaux.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Inspecter les métadonnées jobs/révisions, les clés de stockage et les journaux disponibles. | ✅ | 2026-09-29 |
| TASK-002 | Exporter les aperçus et briefs historiques dans `docs/articles/selection-generations/`, avec hashes et provenance. | ✅ | 2026-09-29 |

### Implementation Phase 2

- **GOAL-002**: Livrer une galerie utilisable et fidèle aux archives.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Inspecter les images, isoler les replis locaux, produire `index.html` avec prompts juxtaposés et sélection de cinq éléments. | ✅ | 2026-09-29 |
| TASK-004 | Vérifier associations, chargement des images, sélection, et effectuer les revues Standards/Spec ; documenter dans `docs/sprints/galerie-generations-1.md`. | ✅ | 2026-09-29 |

## 3. Alternatives

- **ALT-001**: Captures de l'éditeur exclues par la demande utilisateur.
- **ALT-002**: Nouvelles images générées exclues : la demande porte sur l'historique existant.

## 4. Dependencies

- **DEP-001**: Conteneurs PostgreSQL et MinIO du projet existants, démarrés pour consultation.
- **DEP-002**: Python, boto3 et Pillow locaux pour exporter et inspecter les artefacts.

## 5. Files

- **FILE-001**: `research/export_article_gallery.py`, utilitaire local d'export en lecture seule.
- **FILE-002**: `docs/articles/selection-generations/`, galerie, originaux et manifeste.
- **FILE-003**: `docs/sprints/galerie-generations-1.md`, bilan et limites de provenance.

## 6. Testing

- **TEST-001**: Vérifier hashes, dimensions et association exacte job → révision → clé image.
- **TEST-002**: Vérifier galerie sans ressource distante, prompts échappés et sélection limitée à cinq.

## 7. Risks & Assumptions

- **RISK-001**: Le champ source=ai ne prouve pas l'usage d'un modèle d'image ; les journaux révèlent des replis locaux pour quota insuffisant.
- **ASSUMPTION-001**: Le brief utilisateur est le texte demandé pour la galerie ; le prompt technique envoyé au fournisseur est indiqué indisponible s'il n'est pas stocké.

## 8. Related Specifications / Further Reading

- [Article](../docs/articles/ia-plans-verifiables.md)
