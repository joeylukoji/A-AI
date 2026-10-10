# Sprint Article / Évaluation 2 — bilan du 30 septembre 2026

[Plan d'exécution](../../plan/process-article-evaluation-2.md) · [Manuscrit](../articles/ia-plans-verifiables.md) · [Matrice des corrections](../articles/suivi-revision-20260930.md)

## Périmètre et état

Révision Markdown et campagnes locale/linguistique réalisées. **La comparaison géométrique A-AI/HouseDiffusion sur les dix programmes est maintenant exécutée.** La comparaison à trois systèmes avec un LLM produisant directement des coordonnées reste à faire. Aucune modification du moteur de production ni de l'éditeur n'a été faite dans ce sprint pour améliorer les scores.

Les skills `create-implementation-plan`, `python-code-style` et `code-review` ont guidé le plan, les garde-fous et la double revue. Le skill documents a servi à lire le DOCX comme source, sans l'écraser. Revue adaptée aux fichiers WIP et nouveaux fichiers, avec HEAD e4bdd740fbd064298c1534b0ee5b888477a50677 comme référence documentaire, pas comme description suffisante de l'état expérimental. Les instantanés de sources font foi pour les exécutions.

## Étapes réalisées

1. Lecture du DOCX et des remarques ; sauvegarde de l'ancien Markdown ; protocole écrit avant les exécutions.
2. Gel du corpus et des sources ; 150 générations locales, toutes archivées individuellement.
3. Deux ablations : validations finales neutralisées ; variantes désactivées. Résultats identiques en rendement, diversité réduite sans variantes.
4. Appel réel du NLU généraliste et de l'intégration A-AI, plafonné à 60 tentatives et un sous-budget réservé de 0,50 USD, sous l'autorisation utilisateur de 5 €.
5. Réécriture du manuscrit : dénominateurs, statistiques, travaux connexes, schéma, illustration et limites.
6. Recalcul hors réseau, tests de non-régression de l'analyse et revues séparées Standards/Spec.
7. Audit post hoc du schéma JSON publié sur les documents archivés ; publication séparée des défauts, sans réparation des observations.
8. Comparaison HouseDiffusion : 10 programmes × 5 graines, évaluateur commun, rapport chiffré et revue des écarts de mapping.

## Résultats et preuves

- [Campagne locale consolidée](../../benchmark/runs/article-evaluation-20260930/analysis-summary.json) : 45 retours / 50, 40 succès combinés / 50 pour chaque variante ; 5 refus, 0 erreur technique de génération.
- [Comparaison linguistique](../../benchmark/article-evaluation/llm-results.md) : évaluation locale 9/10, LLM direct 9/10, intégré 10/10. Le dernier résultat comprend le post-traitement applicatif.
- [Synthèse linguistique JSON](../../benchmark/article-evaluation/llm-summary.json) : 60 tentatives, 59 réponses ; 0,01249815 USD estimé pour les jetons reçus ; coût facturé inconnu, appel interrompu exclu de cette estimation.
- [Test HTTP séparé](../../benchmark/runs/article-evaluation-20260930/http-smoke-separate.json) : statut 200 et document. Docker n'était pas disponible ; test en mémoire du point d'entrée applicatif, pas de test de déploiement ni d'écriture en base.
- [Audit du schéma publié](../../benchmark/article-evaluation/schema-audit.json) : 0 document conforme sur 135 retours ; 1 785 erreurs exclusivement sur l'énumération du catalogue mobilier. Ce contrôle post hoc distingue la validité géométrique mesurée de la conformité complète au format.
- [Nouvel audit post hoc au schéma courant](../../benchmark/article-evaluation/schema-audit-current-20261004.json) : 135/135 documents reconnus valides après synchronisation des 22 IDs du catalogue 2D. L'audit P9 historique est conservé ; empreinte courante `4532347c…` contre empreinte gelée `455a566d…`.
- [Comparaison HouseDiffusion](../../benchmark/article-evaluation/house-diffusion-results.md) : campagne finale contrôlée dans `house-diffusion-comparison-20261001-controlled`, A-AI 40/50 et HouseDiffusion intégré `house_diffusion+opt` 15/50 en rendement combiné ; 45/45 géométriquement valides parmi les retours dans les deux systèmes. L'archive sans contrôle de graine est conservée comme préliminaire et exclue des chiffres finaux.

## Incidents conservés

L'interdiction réseau du premier dispositif bloquait la connexion locale `socketpair` de TestClient sous Windows après les 150 générations. Les fichiers individuels existaient déjà ; l'agrégation a été faite sans régénérer. Un test HTTP séparé a confirmé le parcours applicatif. Les empreintes de diversité ont été corrigées pour neutraliser les représentations numériques entières/flottantes et le zéro signé, puis recalculées depuis les documents conservés.

Le premier lot LLM a rencontré une erreur `ReadError` sur `dev13` direct. Le cas reste un échec technique ; la continuation ne l'a pas rejoué. La revue a ensuite détecté qu'une reprise de continuation pouvait perdre l'historique du budget. Le script refuse désormais ce cas ; un test hors réseau le vérifie. Aucun de ces correctifs n'a nécessité un appel payant supplémentaire.

## Vérifications

```powershell
python -m unittest benchmark.tests.test_article_statistics benchmark.tests.test_article_llm_report benchmark.tests.test_article_schema_report -v
python -m ruff check benchmark/article_evaluate.py benchmark/article_statistics.py benchmark/article_report.py benchmark/article_llm.py benchmark/article_llm_report.py benchmark/article_schema_report.py benchmark/tests/test_article_statistics.py benchmark/tests/test_article_llm_report.py benchmark/tests/test_article_schema_report.py
```

Douze tests ciblés réussis ; lint et format vérifiés. La figure SVG a été rendue et inspectée : textes lisibles, flèches raccordées, retour de sauvegarde explicite. Le recalcul linguistique n'a effectué aucun appel réseau. Les archives d'observation sont en écriture exclusive ; une nouvelle analyse exige une nouvelle destination. Les sources des analyseurs sont conservées dans [analysis-source](../../benchmark/article-evaluation/analysis-source/source-manifest.json) et [analysis-source-final](../../benchmark/article-evaluation/analysis-source-final/source-manifest.json), distinctes des sources gelées avant les expériences.

État de vérification **antérieur au sprint de réconciliation du schéma/catalogue** : le contrôle élargi (statistiques, rapports, lanceur, expériences, géométrie et schéma) avait donné **41 tests réussis et 1 échec**. `test_door_semantics_cases_are_enforced_by_the_draft_2020_schema` échouait parce que la fixture commune omettait `thickness_m` sur ses quatre murs alors que le schéma l'exigeait. À cette date, le schéma et les fixtures n'avaient pas été modifiés dans le sprint d'évaluation. Ce résultat est conservé comme historique et n'est pas l'état courant : après correction, `benchmark/tests` passe 132 tests, les tests de validation IA en passent 89 et `go test ./internal/plan` réussit (voir `plan/refactor-plan-schema-catalog-1.md`, TASK-007). Les avertissements requests/pytest-asyncio restent des avertissements d'environnement.

L'audit historique a révélé une incohérence entre le catalogue généré et l'énumération publiée. Celle-ci est maintenant corrigée dans le schéma et protégée par un test qui compare le schéma, le catalogue 2D et les assets Blender. Le réaudit des mêmes observations est séparé de P9 : aucun plan ni score expérimental n'a été modifié. L'écart de dimensions de `table.dining` entre les catalogues 2D et Blender demeure ouvert et demande un sprint mesuré distinct.

## Standards

Revue du sprint d'évaluation : aucun défaut actionnable restant dans ses artefacts. Défaut de reprise transitive corrigé par refus explicite ; autres corrections validées (programmes mal structurés, annotations absentes, groupes de cinq graines, doublons). L'agrégateur a été rejoué indépendamment en mémoire avec égalité exacte des résultats. L'échec historique de la fixture est résolu dans le sprint de réconciliation ci-dessus.

## Spec

La revue complémentaire de l'audit a demandé de remplacer « contrôle complet » par « contrôle géométrique » dans le schéma. Libellés et légende corrigés pour ne pas suggérer une conformité JSON intégrale.

Revue finale du manuscrit et des artefacts : aucun défaut actionnable sur chiffres, formules, liens et portée des allégations. La sélection illustrative finale utilise désormais G005, G007, G010, G013 et G015, avec prompts archivés. Exigence globale partielle : la comparaison de géométries produites directement par un LLM, la validation du mapping HouseDiffusion sur un graphe commun plus riche et la publication des données restent à réaliser. Le fichier de soumission Word/PDF n'est pas livré par cette révision Markdown. Le fichier compte plus de 7 000 mots ; le nombre de pages dépendra de la composition finale.

## Sprint suivant proposé : comparaison géométrique commune

Le prérequis de réconciliation du catalogue, du schéma et des fixtures est maintenant satisfait dans `plan/refactor-plan-schema-catalog-1.md`, sans modification des archives de l'étude. Toute nouvelle campagne doit identifier cette évolution explicitement. La comparaison publiée ici reste une mesure système de `house_diffusion+opt`; une séparation native/post-traitement devra être planifiée si l'effet du réseau seul est requis.

1. Obtenir et vérifier licence, checkpoint HouseDiffusion et hash ; résoudre les droits des données nécessaires. Ne pas substituer une image générique à un plan vectoriel.
2. Fixer l'intersection des types et des contraintes pris en charge ; annoter le même programme/graphe pour les trois méthodes, avant toute lecture de scores.
3. Implémenter des adaptateurs séparés ; tester unités, contours, portes et refus. Aucune réparation cachée propre à un concurrent.
4. Geler protocole, corpus, versions, paramètres et budget restant avant exécution. Tester les cas limites de l'évaluateur commun.
5. Exécuter A-AI, LLM à coordonnées et HouseDiffusion ; archiver erreurs et résultats bruts ; calculer différences appariées par programme.
6. Comparer les figures non retouchées à partir d'un échantillonnage annoncé ; mise à jour du manuscrit seulement après mesure et double revue.

## État du sprint géométrique commun — 4 octobre 2026

Le sprint détaillé est suivi dans [le plan d'implémentation](../../plan/feature-common-geometry-evaluation-1.md). Le corpus inédit est défini dans [corpus.json](../../benchmark/common-geometry-20261004/corpus.json) (10 programmes evaluation et 2 development) et son [protocole préenregistré](../../benchmark/common-geometry-20261004/protocol.md) fixe maintenant les métriques avant toute génération. Les cas ne sont pas validés par des architectes et restent visibles/non aveugles.

Le premier bloc du harness indépendant est en place dans `benchmark/common_geometry.py` : parseur strict au schéma PlanDocument 1.0 sans réparation, appariement d'occurrences par géométrie, calcul d'adjacence et erreur relative de surface. Les adaptateurs distincts sont dans `benchmark/common_geometry_adapters.py` : entrée A-AI locale directe, conversion HouseDiffusion+opt sans champs générés manquants inventés, et construction de requête LLM JSON avec le même programme/parcelle/graphe et schéma explicite. Les moteurs locaux bloquent les chemins courants TCP, UDP et DNS; les secrets, la configuration et le chemin d'import temporaire sont restaurés après exécution. Les métriques historiques n'ont pas été modifiées. Quinze tests hors ligne passent. Deux smoke tests locaux sur `dev01`, seed 0, ont produit des `PlanDocument` valides (5 pièces chacun); ils ne sont pas des scores et ne couvrent pas les deux cas development ni les 5 répétitions. Aucun appel LLM n'a été effectué. Les revues finales Standards/Spec n'ont plus trouvé de défaut P1/P2 sur ce bloc.

La suite reste bloquante avant les scores : terminer et revoir les tests runner/quota, les contrôles development complets, le lanceur à écriture exclusive, le préflight des poids et des secrets et l'agrégation statistique. Aucune exécution evaluation n'est autorisée par ce jalon intermédiaire, et aucun chiffre comparatif nouveau n'est revendiqué.
