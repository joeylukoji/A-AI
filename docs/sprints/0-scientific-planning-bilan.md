# Bilan — analyse scientifique et planification 2D

Date : 2026-09-22. Périmètre livré : skills, analyse, documentation et protocole.
Aucun code applicatif changé. Les sprints fonctionnels restent planifiés.

## Installation et méthode

Commande demandée exécutée avec succès :
`npx skills add https://github.com/github/awesome-copilot --skill create-implementation-plan`.
Skill lu dans `.agents/skills/create-implementation-plan/SKILL.md`, provenance
consignée par l'installateur dans `skills-lock.json`. Les copies destinées aux
autres agents créées par cet installateur sont conservées.

Skills appliqués : `create-implementation-plan`, `code-review` et
`frontend-refactor-planner`. Le plan est enregistré dans `docs/` conformément
à la demande utilisateur. Le mécanisme de revue Standards/Spec a été exécuté
par deux agents séparés sur l'analyse puis sur les nouveaux documents.

Le skill de revue prévoit un diff entre commits. Ici le dépôt est déjà modifié
et plusieurs modules sont non suivis : la revue du code a utilisé HEAD
`e4bdd740fbd064298c1534b0ee5b888477a50677` comme contexte, complété par lecture
des fichiers locaux. La revue de cette livraison porte sur les documents ajoutés
et leurs modifications, sans attribuer les changements existants à ce bloc.
Le suivi d'issues `docs/agents/issue-tracker.md` est absent ; la demande utilisateur
sert de spécification. L'installation `/setup-matt-pocock-skills` recommandée
par le skill n'est pas nécessaire à la revue locale de cette demande.

## Standards

Audit du code : zéro violation architecturale bloquante démontrée dans les
extractions examinées, trois améliorations de conception : provenance ambiguë
`flux`/Gemini/local, contrats dictionnaires implicites, responsabilités résiduelles
du module diffusion et de l'adaptateur Together/Eden. Elles sont planifiées.

Revue des documents : deux constats, corrigés. Les tâches éloignées qui ne
permettaient pas encore de fixer les signatures ou budgets exigent maintenant
un contrat de conception revu avant implémentation. Le corpus de développement
est explicitement séparé du groupe final.

## Spec

Audit du code : quatre limites principales, intégrées à l'audit scientifique :
documentation historique non conforme au parcours actuel, benchmark ancien
sans adaptation finale ni artefacts appariés, attribution GAN inadéquate et
métriques insuffisantes pour établir une validité architecturale.

Revue des documents : deux constats, corrigés. Les 20 programmes de développement
sont seuls rejoués pendant les améliorations ; les 10 finaux attendent le gel.
Le budget de sélection est un plafond commun de huit candidats, avec nombre
effectif enregistré, et non « exactement huit au maximum ».

## Vérifications réalisées

Commande de caractérisation existante, sans appels image réels :

```powershell
$env:AI_STUB='1'
$env:IMAGE_BACKEND='procedural'
$env:TOGETHER_NLU='0'
$env:TOGETHER_API_KEY=''
$env:TOGETHER_AI_API_KEY=''
$env:EDENAI_API_KEY=''
$env:EDEN_API_KEY=''
$env:PYTHONPATH='services/ai'
python -m pytest services/ai/tests/test_pipeline_service.py services/ai/tests/test_architecture_2d.py services/ai/tests/test_floorplan_render.py -q
```

Résultat : **31 passed in 5.82s**. Avertissements de dépendances Python et de
configuration pytest présents ; aucun échec sur ce sous-ensemble.
Ce résultat ne valide ni les services externes ni un parcours navigateur complet.

Contrôle des 69 déclarations d'identifiants du plan : aucune duplication.
`git diff --check` réussi ; avertissements LF/CRLF seulement.

## État et prochaine étape

Cartographie et plan disponibles dans `docs/pipeline-scientific-audit.md` et
`docs/refactor-mvp-2d-1.md`. `benchmark/README.md` et `report-template.md`
définissent les preuves à produire. Aucun runner ni résultat avant/après n'est
présenté comme livré. La prochaine étape est TASK-001 du sprint 3A : figer
la source et le corpus avant toute amélioration fonctionnelle.
