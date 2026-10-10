---
goal: Comparer trois systèmes 2D sous un programme et un évaluateur géométrique communs
version: 1.0
date_created: 2026-10-04
last_updated: 2026-10-04
owner: Projet A-AI
status: 'In progress'
tags: [feature, benchmark, 2d, evaluation, reproducibility]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In_progress-yellow)

Construire une expérience 2D séparée de la campagne article existante pour comparer le cœur géométrique A-AI, un LLM généraliste produisant directement un `PlanDocument`, et le système spécialisé `house_diffusion+opt`. Chaque système recevra le même programme structuré, les mêmes contraintes de parcelle, les mêmes objectifs de surface et le même graphe d'adjacence. Les sources et observations déjà archivées ne seront pas réécrites. Les sorties et échecs seront évalués par le même code indépendant; aucun plan invalide ne sera réparé pour le score.

## 1. Requirements & Constraints

- **REQ-001**: Créer un corpus d'évaluation commun inédit de 10 programmes synthétiques non ambigus, dont les types de pièces appartiennent à l'intersection réellement prise en charge par les trois systèmes; exclure les types perdus ou aliasés par HouseDiffusion (`wc`, `laundry`, `garage`, `storage`). Les cas synthétiques ne seront pas présentés comme validés par des architectes.
- **REQ-002**: Définir avant toute observation un graphe explicite par programme, avec nœuds individuels (y compris les occurrences des pièces répétées), arêtes d'adjacence, contraintes de parcelle et objectifs de surface. Transmettre le même objet JSON aux adaptateurs des trois systèmes.
- **REQ-003**: A-AI doit utiliser le cœur structuré de production (`pipeline.build_document`) sans reparsing du texte, appel Gemini de présentation ni appel réseau; les limites de cette condition doivent être inscrites au manifeste.
- **REQ-004**: HouseDiffusion doit utiliser les poids locaux archivés, les répétitions 0–4 transmises à `HOUSEDIFFUSION_SEED`, 20 pas et l'adaptateur/post-traitement `house_diffusion+opt`; le résultat doit être nommé comme système intégré, et non comme sortie native du réseau.
- **REQ-005**: Le LLM généraliste `openai/gpt-oss-120b` doit recevoir uniquement le programme structuré, les contraintes et le graphe, puis retourner directement un objet `PlanDocument` en unités métriques. Une sortie incomplète, invalide, tronquée ou non décodable est un résultat invalide/erreur, jamais une géométrie réparée.
- **REQ-006**: Conserver le statut de chaque tentative (retour, refus attendu, sortie invalide, erreur transport/technique), l'entrée, le prompt exact, la réponse brute, le modèle signalé, les usages, les versions, les graines ou index de répétition et les SHA-256 dans une archive en écriture exclusive.
- **REQ-007**: Calculer sur toutes les tentatives et sans filtre opportuniste le retour, la validité géométrique, l'égalité du programme, le F1 des arêtes d'adjacence, les erreurs relatives de surface et le rendement combiné. Rendement combiné = tentatives valides géométriquement ET programme exact ET ensemble d'arêtes attendu égal à l'ensemble observé / 50 demandes; refus, invalides, erreurs et F1 incomplet valent zéro. L'aire cible reste une mesure continue séparée, sans seuil arbitraire caché. Rapporter les dénominateurs, les refus et erreurs séparément; ne pas inférer accessibilité, réglementation, constructibilité ni préférence esthétique.
- **REQ-008**: Limiter la campagne distante à 50 appels, température 0,1, sortie maximale 4 096 jetons, sans nouvelle tentative automatique et à une réservation maximale stricte de 0,50 USD. Arrêter avant tout appel si le plafond serait dépassé. Les requêtes ne contiennent que des données synthétiques.
- **REQ-009**: Avant toute exécution sur le jeu d'évaluation, valider les trois adaptateurs et le sérialiseur sur des fixtures de développement; figer ensuite corpus, code, modèle, poids, métriques et configuration dans un manifeste. Si un prérequis bloque, produire uniquement `preflight.json` avec `status: not_measured`, le motif et zéro tentative; ne produire ni score ni planche.
- **REQ-010**: Préserver les archives `article-evaluation-20260930`, `house-diffusion-comparison-20261001-controlled`, P9/P11 et les plans déjà présents; publier les nouveaux résultats dans un dossier daté qui n'existe pas.
- **CON-001**: Périmètre 2D uniquement; pas de modification du générateur de production, de l'éditeur, du rendu Gemini, de Blender ou des dimensions catalogue.
- **CON-002**: La répétition LLM est indexée, pas déterministe : ne pas prétendre qu'une graine fournisseur contrôlée a été appliquée si l'API ne la confirme pas.
- **CON-003**: Une comparaison sur 10 programmes synthétiques visibles n'est pas un essai aveugle, une validation d'architectes ou une preuve de généralisation.
- **CON-004**: Le schéma d'entrée commun ne garantit pas que chaque système interprète les arêtes de graphe de façon identique; une métrique d'adjacence explicite est donc requise et le mécanisme d'injection du graphe de chaque système doit être publié.
- **GUD-001**: Déclarer la sélection des types selon la prise en charge vérifiée, sans relabelliser un type manquant vers un autre.
- **GUD-002**: Les critères d'arrêt du réseau, de coût, de poids manquants, de dérive d'entrée ou d'adaptateur non validé prévalent sur l'exécution complète.
- **PAT-001**: Utiliser des adaptateurs de benchmark distincts et un évaluateur indépendant; aucune logique de comparaison ne doit être ajoutée aux modules de production.

## 2. Implementation Steps

### Implementation Phase 1 — corpus commun et protocole préenregistré

- **GOAL-001**: Définir un corpus et des critères évaluables avant de lire toute sortie de cette expérience.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Inspecter les contrats `pipeline.build_document`, `housediff.generate`, `PlanDocument` et `research.metrics.geometry.evaluate`; figer les champs exacts d'entrée/sortie, les types communs sans aliases et les limites de chaque backend dans ce plan. | ✅ — inspection de faisabilité réalisée | 2026-10-04 |
| TASK-002 | Créer `benchmark/common-geometry-20261004/corpus.json` avec 10 programmes structurés et graphes d'adjacence, plus un split `development` séparé; définir les aires cibles et les emprises valides sans prétention architecturale. Aucun résultat ni géométrie générée ne doit être intégré au corpus. | ✅ — 12 cas validés structurellement (10 évaluation, 2 développement), aucun type hors intersection ni arête orpheline | 2026-10-04 |
| TASK-003 | Écrire `benchmark/common-geometry-20261004/protocol.md` avant tout résultat. Adjacence si frontière commune ≥ 0,10−1e-6 m; un contact ponctuel ne l'est pas. Fixer l'appariement d'occurrences conformément à TASK-006. Les aires cibles sont identiques entre occurrences d'un même type; apparier selon le rang lexical d'ID cible après tri stable des sorties. Sur paires d'occurrences présentes, calculer `mean(|A−T|/T)`; signaler séparément cibles sans pièce appariée, pièces excédentaires et `null` si aucune paire valide. Si les arêtes attendues sont vides, précision/rappel/F1 sont `null`; sinon F1=2PR/(P+R), zéro si TP=0. Géométries de pièces invalides ou chevauchantes => métriques d'adjacence `null`. Rendement combiné suit REQ-007. Verrouiller le protocole avant tout score d'évaluation. | ✅ — protocole préenregistré, clarifié par revue avant tout score | 2026-10-04 |
| TASK-004 | Vérifier poids, hash du checkpoint, révision du dépôt vendor, disponibilité CPU/GPU, présence de la clé fournisseur sans afficher sa valeur et contrôle d'écriture exclusive; quotas locaux = 50 A-AI + 50 HouseDiffusion sans réseau, distant = 50 LLM maximum. Répétitions 0–4 transmises à `LAYOUT_SEED` et `HOUSEDIFFUSION_SEED`; aucune graine prétendue côté LLM. Si prérequis manquant, écrire uniquement le statut `not_measured` défini par REQ-009. | | |

### Implementation Phase 2 — adaptateurs et test hors évaluation

- **GOAL-002**: Tester que les trois conditions consomment le même programme et produisent des observations comparables sans réparation cachée.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Créer `benchmark/common_geometry_adapters.py` avec normalisation structurelle commune, adaptateur A-AI direct vers `pipeline.build_document`, adaptateur HouseDiffusion vers `housediff.generate`, conversion du résultat intégré au `PlanDocument` et construction de requête LLM stricte; le parseur reste dans `benchmark/common_geometry.py`. Seuls les champs transport nécessaires peuvent être adaptés, jamais la géométrie invalide. | ✅ — trois conditions définies, requête LLM sérialisée, réseau bloqué pour les moteurs locaux, conversion HouseDiffusion sans défauts implicites; tests et smoke development réussis | 2026-10-04 |
| TASK-006 | Écrire une fonction indépendante d'adjacence, sans changer les métriques historiques. Pour chaque type, trier toutes les pièces de sortie valides par centroïde `(y,x)` croissant, aire croissante, WKB hexadécimal croissant; apparier le rang i au rang i des IDs attendus de ce type triés lexicalement jusqu'au minimum des deux cardinalités. IDs de sortie générés ne participent pas au tri. Vérifier sur bedroom/bathroom répétés. Mesurer l'arête si frontière commune ≥ 0,10−1e-6 m; produire TP/FP/FN, P/R/F1. Graphe attendu vide => P/R/F1 `null`; polygones non mesurables ou chevauchants => métriques graphe `null`; graphe attendu non vide avec TP=0 => F1=0. | ✅ — appariement géométrique déterministe et métriques indépendantes implémentés | 2026-10-04 |
| TASK-007 | Ajouter `benchmark/tests/test_common_geometry.py` avec fixtures déterministes pour mêmes entrées, compteurs de répétitions, adaptateurs, parsing strict JSON, seuil/tolérance d'adjacence, cas de centroïdes ex aequo, surfaces manquantes/en trop, documents valides/invalides, absence de réparation, quotas et arrêt budget; aucun réseau réel ni poids dans les tests. | 🟡 — 15 tests offline couvrent corpus, parsing, requête structurée, conversion sans réparation, réseau et métriques; tests runner/quota et certains cas géométriques restent à ajouter | 2026-10-04 |
| TASK-008 | Exécuter uniquement sur le split development (max 10 A-AI et 10 HouseDiffusion; LLM mocké sans réseau), inspecter, corriger le harness sans ajuster les paramètres des modèles; consigner tout changement protocolaire avant d'ouvrir evaluation. | 🟡 — smoke dev01 seed 0 réussi pour A-AI et HouseDiffusion+opt; campagne development complète et archivage encore à faire | 2026-10-04 |

### Implementation Phase 3 — gel, exécution contrôlée et résultats

- **GOAL-003**: Produire des observations reproductibles sous budget, ou enregistrer explicitement pourquoi l'expérience est non mesurée.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Créer le lanceur `benchmark/common_geometry_run.py`; écrire d'abord un manifeste exclusif avec SHA-256 des sources/corpus/poids, prix officiel daté, split, 5 répétitions, 20 pas HouseDiffusion, température, plafond et paramètres. Refuser toute sortie cible existante. | | |
| TASK-010 | Exécuter 10 programmes × 5 répétitions/backend : 50 inférences locales A-AI et 50 HouseDiffusion hors réseau, et au plus 50 appels LLM distants. Bloquer chaque appel avant envoi sur la réservation cumulée de 0,50 USD; sauvegarder prompt/réponse/usage/status sans retry ni overwrite. | | |
| TASK-011 | Résumer hors génération dans `benchmark/common_geometry_report.py`; par système/cas, rendement de cas = succès combinés parmi les 5 tentatives / 5; rendement macro = moyenne non pondérée des 10 rendements de cas. Bootstrap percentile bilatéral 95 % du macro (10 cas resélectionnés avec remise, 2 000 tirages, seed 20261004); contraste = différences des proportions au niveau cas, puis bootstrap des mêmes cas. Ne jamais apparier les répétitions. Vérifier 3 × 50 observations uniques. | | |
| TASK-012 | Si et seulement si des résultats d'évaluation existent, produire le rapport et les planches non retouchées dans le nouveau dossier; analyser les échecs sans assimiler réussite géométrique à qualité architecturale. Un run `not_measured` ne produit aucune planche. | | |

### Implementation Phase 4 — documentation, revue et clôture

- **GOAL-004**: Publier les preuves et les limites sans modifier l'article scientifique avant vérification indépendante.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Mettre à jour `docs/sprints/article-evaluation-2.md`, le protocole et `docs/articles/ia-plans-verifiables.md` uniquement depuis le rapport réauditable; différencier explicitement cette nouvelle expérience des résultats antérieurs. | | |
| TASK-014 | Lancer tests, Ruff, format, `git diff --check` et revue Standards/Spec sur le diff de ce plan; vérifier les liens, hashes, tableaux, dénominateurs, cas manquants et intégrité de toutes les archives préexistantes. | | |

## 3. Alternatives

- **ALT-001**: Réutiliser les 10 programmes de l'article tels quels; rejeté pour la condition commune car seuls quelques programmes évitent `wc`, `laundry`, `garage/storage` incompatibles ou aliasés dans RPLAN.
- **ALT-002**: Comparer seulement A-AI/HouseDiffusion déjà archivés; insuffisant pour la demande d'une comparaison à trois systèmes et pour distinguer le générateur de la compréhension du langage.
- **ALT-003**: Faire générer des images par le LLM puis les vectoriser; rejeté comme condition principale, car l'erreur d'image et l'erreur de vectorisation seraient confondues avec la capacité de produire directement des coordonnées.
- **ALT-004**: Remapper `wc`, buanderie, garage ou cellier vers des catégories supportées; rejeté car il masquerait le déficit d'expressivité et rendrait le graphe/type non comparable.

## 4. Dependencies

- **DEP-001**: `services/ai/app/pipeline.py:build_document` et `services/ai/app/housediff.py:generate` pour les deux moteurs locaux.
- **DEP-002**: `model250000.pt` et `vendor/house_diffusion`; checkpoint déjà présent avec SHA-256 observé `7b22c916ec8d5fce087ce9bfe277817a93d60ca2eed9f8bbcf4b8eefec43797a`, à revalider au gel.
- **DEP-003**: `research.metrics.geometry.evaluate` et le paquet Shapely comme métriques géométriques communes.
- **DEP-004**: API Together et `openai/gpt-oss-120b`; prix serverless affiché à 0,15 USD / million tokens d'entrée et 0,60 USD / million tokens de sortie sur la page officielle au 2026-10-04; le coût observé reste basé sur usage API et budget réservé, pas sur une facture supposée.
- **DEP-005**: Corpus synthetic/non expert; autorisation antérieure utilisateur plafonnée à 5 €; plafond incrémental choisi pour cette expérience : 0,50 USD réservés.

## 5. Files

- **FILE-001**: `benchmark/common-geometry-20261004/corpus.json` et `protocol.md` — entrées et règles préenregistrées.
- **FILE-002**: `benchmark/common_geometry.py`, `benchmark/common_geometry_adapters.py`, `benchmark/common_geometry_run.py` — évaluateur/adaptateurs et collecte exclusivement benchmark.
- **FILE-003**: `research/metrics/geometry.py` et `benchmark/tests/test_common_geometry.py` — mesure d'adjacence et test offline.
- **FILE-004**: `benchmark/common_geometry_report.py` — agrégation et appariement sans modèles.
- **FILE-005**: `benchmark/runs/common-geometry-20261004/` — manifestes, données brutes et résultats écrits exclusivement.
- **FILE-006**: `docs/sprints/article-evaluation-2.md`, `docs/articles/ia-plans-verifiables.md`, ce plan — conclusions et limites publiées.

## 6. Testing

- **TEST-001**: Fixture identique et validée par les trois adaptateurs; aucune entrée ne perd ou ne renomme de type.
- **TEST-002**: Evaluateur d'adjacence teste deux pièces partageant une limite, un simple contact ponctuel, un vide, un overlap, arêtes extra/manquantes et cas sans arête demandée.
- **TEST-003**: Parseur du LLM rejette réponse markdown, JSON tronqué, données non finies, valeurs booléennes en coordonnée, unités autres que m et plan hors emprise sans correction automatique.
- **TEST-004**: Runner de test utilise réponses mockées, compte strictement les appels, réserve le coût avant d'appeler, s'arrête au plafond et conserve les erreurs ; aucun réseau réel pendant les tests.
- **TEST-005**: Test d'intégrité vérifie 10 cases × 5 repeats × 3 méthodes, unicité des clés, provenance SHA-256 et égalité de l'entrée structurée.
- **TEST-006**: Avant clôture : `python -m pytest benchmark/tests/test_common_geometry.py -q`, suites benchmark et IA concernées, `go test ./internal/plan` si le document contractuel Go est touché, Ruff/format et `git diff --check`.

## 7. Risks & Assumptions

- **RISK-001**: HouseDiffusion ne représente qu'un sous-ensemble des types et son système de reconstruction/projection affecte l'output; résultats à nommer `house_diffusion+opt`.
- **RISK-002**: Échec d'adaptateur LLM ou timeout peut introduire un manque non aléatoire; conserver tous les appels et afficher coverage par cas.
- **RISK-003**: Graphe étoile autour du séjour reflète la configuration admise par le code HouseDiffusion existant, sans valider son réalisme architectural; les conclusions ne se généralisent pas à d'autres graphes.
- **RISK-004**: LLM ne garantit pas l'aléa reproductible côté fournisseur; son index de répétition n'est pas un bloc d'appariement statistique avec les autres méthodes.
- **RISK-005**: L'aire cible, la géométrie, le rendu et la conformité des types sont des dimensions distinctes; le rendement combiné ne comprend pas l'erreur de surface, qui demeure rapportée en mesure séparée avec sa couverture.
- **ASSUMPTION-001**: Le graphe standard est une étoile avec le séjour comme nœud central; les types HouseDiffusion non aliasés admissibles sont `living`, `kitchen`, `bedroom`, `bathroom`, `hallway`, `dining`, `office`.
- **ASSUMPTION-002**: Le modèle local et les dépendances peuvent toujours charger sur l'environnement présent; le gel du sprint doit arrêter si ce n'est plus vrai.
- **ASSUMPTION-003**: Le plafond de réservation de 0,50 USD est suffisant pour 50 réponses courtes JSON sous un maximum de 4 096 jetons; chaque réservation réelle est calculée avant envoi avec la tarification datée et l'appel n'est jamais envoyé si le budget global serait dépassé.

## 8. Related Specifications / Further Reading

- `docs/sprints/article-evaluation-2.md` — exigences de la comparaison géométrique commune.
- `benchmark/article-evaluation/protocol.md` — campagne antérieure et séparation NLU/géométrie.
- `benchmark/article-evaluation/house-diffusion-results.md` — mesures système antérieures, non équivalentes au protocole prévu ici.
- `research/metrics/geometry.py` — évaluateur indépendant.
- [Tarifs Together AI](https://www.together.ai/pricing) — page officielle, consultée le 2026-10-04.
