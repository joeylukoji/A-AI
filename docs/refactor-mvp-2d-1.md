---
goal: Finaliser le parcours MVP 2D avec preuves de fidélité et comparaisons reproductibles
version: 1.0
date_created: 2026-09-22
last_updated: 2026-09-23
owner: Équipe A-AI
status: In progress
tags: [architecture, refactor, benchmark, mvp, 2d]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In_progress-yellow)

Plan d'exécution après les sprints 1 et 2. Sprint 3A livré pour la caractérisation
locale ; sprint 3B en cours, blocs parcelle et ouvertures livrés, profil de validation
structure/intervalles et géométrie du profil 2D v1.2 communes Python/Go livrés.
Le sprint 3B est clos dans ce périmètre, sans prétention de constructibilité.
Voir les bilans dans `docs/sprints/`.
Le sprint 3 est scindé en 3A/3B/3C pour isoler mesures,
validité et design. L'ordre est 3A → 3B → 3C → 4 → 5 → 6 → 7 → 8.
Le format suit `create-implementation-plan`; le stockage dans `docs/` suit la
demande utilisateur et prime sur le répertoire `/plan/` proposé par le skill.

## 1. Requirements & Constraints

- **REQ-001**: Limiter les changements au parcours 2D : génération, Gemini image, adaptation, édition, sauvegarde et exports.
- **REQ-002**: PlanDocument reste la référence géométrique ; toute retouche structurelle modifie ce document avant les rendus.
- **REQ-003**: Appliquer `create-implementation-plan` et une revue Standards/Spec à chaque bloc logique, y compris analyse ; consigner les constats avant de poursuivre.
- **REQ-004**: Toute amélioration de génération ou de rendu produit une comparaison appariée avant/après dans `benchmark/`, avec images et courte analyse.
- **REQ-005**: Mettre à jour documentation, résultats, limites et statut à la fin de chaque tâche ; ne cocher terminé qu'après vérification.
- **REQ-006**: Reprendre les deux références utilisateur uniquement pour le dessin du plan dans le canvas de l'éditeur : murs sombres, menuiseries fines, sols discrets, mobilier en vue de dessus, noms/surfaces lisibles. Ne pas appliquer cette refonte au design Gemini.
- **SEC-001**: Archiver configuration et requêtes sans clés, jetons, données personnelles ni briefs réels non anonymisés.
- **CON-001**: Préserver les modifications locales existantes ; ne pas utiliser HEAD seul comme baseline expérimentale d'un checkout modifié.
- **CON-002**: Ne pas annoncer un gain scientifique sur le seul score interne ni assimiler une image esthétique à un plan constructible.
- **GUD-001**: Un bloc suit plan → référence figée → analyse → revue → modification → revue immédiate → tests → comparaison → bilan docs ; les corrections suivent le même cycle.
- **PAT-001**: Conserver cas d'usage commun, adaptateurs de transport, noyau géométrique et rendus séparés ; introduire seulement les abstractions nécessaires.

## 2. Implementation Steps

Chaque table est séquentielle de haut en bas, sauf mention contraire. Les fichiers
nouveaux indiqués sont des cibles proposées, pas des fichiers déjà livrés.
Après chaque tâche, déposer le bilan dans `docs/sprints/<sprint>-bilan.md` et les
revues dans ce bilan, avec diff exact, tests et statut. La référence de revue
par défaut est l'état local du bloc avant modification ; HEAD sert au contexte
historique. Aucun changement antérieur n'est attribué au bloc courant.

### Implementation Phase 1 — Sprint 3A : preuve et baseline

- **GOAL-001**: Obtenir une baseline reproductible de la pipeline finale et des évaluateurs capables de rejeter des contre-exemples.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Créer `benchmark/cases/corpus.json` : 30 programmes, répartition 20 développement/10 évaluation, seeds 0–4, types/contraintes et surfaces explicitement demandées annotés ; appliquer les strates de `benchmark/README.md`. Archiver la source locale exécutable et les hashes avant toute modification applicative. | Oui | 2026-09-22 |
| TASK-002 | Créer `benchmark/run.py` appelant `pipeline.generate_plan` avec mode local explicite, puis `benchmark/compare.py` pour appariement strict case/seed/repeat. Conserver document, PNG, erreurs, configuration expurgée, versions, latences et provenance. Réutiliser les utilitaires existants seulement après validation. Rejeter corpus ou configurations incompatibles. | Oui | 2026-09-22 |
| TASK-003 | Ajouter dans `research/metrics/` les validations indépendantes : polygones simples et positifs, recouvrements, enveloppe, IDs, ouvertures et comptes par type. Tester segments disjoints, polygones dégénérés, NaN, pièces absentes, couloirs segmentés. Ne pas réutiliser le score de sélection comme oracle. | Oui | 2026-09-22 |
| TASK-004 | Dans `pipeline.generate_plan`, `diffusion.preview_from_document` et l'adaptateur Eden, ajouter provenance réelle et motif de repli sans casser les champs historiques ; tests local, succès API simulé, échec, reprise. Distinguer invocation du fournisseur et POST de génération ; téléchargements non mesurés explicites. | Oui | 2026-09-22 |
| TASK-005 | Exécuter la baseline locale figée sur les 20 programmes de développement uniquement, puis vérifier une comparaison identité/identité et un contre-exemple modifié. Produire planches et `benchmark/comparisons/3a-provenance-final/report.md`. Signaler métriques encore indisponibles ; exiger zéro fausse amélioration sur identité. | Oui | 2026-09-22 |

Sortie : corpus versionné, référence archivée, runner vérifié, six cas rapides
et 20 programmes locaux de développement exécutés ; les dix cas finaux restent
inexécutés jusqu'au gel. Aucune valeur manquante n'est convertie en succès.

### Implementation Phase 2 — Sprint 3B : contrats et faisabilité

- **GOAL-002**: Aucun document invalide livré silencieusement ; les contraintes impossibles produisent un diagnostic métier testable. Dépend de GOAL-001.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Définir contrats de résultat et erreurs métier dans `services/ai/app/plan_contracts.py`, alignés sur `packages/plan-schema/`; valider aux frontières de `pipeline.build_document`, sans transformer toute exception de programmation en 422. Profil document 2D v1.2 livré ; limites scientifiques documentées. | Oui | 2026-09-23 |
| TASK-007 | Corriger `plan_adapt.adapt` : calculer emprise utile avant les minima, refuser dimensions non finies et retraits impossibles ; conserver règles métier configurables et retourner les contraintes en conflit. | Oui | 2026-09-22 |
| TASK-008 | Valider après `apply_opening_rules` : mur existant, largeur positive, offset et extrémité dans le mur, pas de chevauchement ; préserver garage large. Rejouer les orientations inversées et fenêtres élargies. | Oui | 2026-09-23 |
| TASK-009 | Aligner `internal/plan/validate.go` et la frontière Python avec fixtures JSON communes ; comparer acceptation/refus et codes d'erreur, documenter tout écart volontaire. 76 fixtures partagées, périmètre et polygones inclus ; 170 documents du run final admis par Go. | Oui | 2026-09-23 |

Sortie : toutes les fixtures invalides refusées explicitement, zéro nouvelle
violation sur plans acceptés, cas existants valides préservés ou migration documentée.

### Implementation Phase 3 — Sprint 3C : design architectural de l'éditeur

- **GOAL-003**: Rapprocher le canvas des références sans modifier la géométrie. Dépend de GOAL-002 ; détails visuels dans `architecture-2d-audit.md`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Capturer six documents figés avec les vrais scripts `editor.js`/`plan-style.js` : 36 repos + sélection et glissement, zoom 50/100/200 %, DPR 1/2. Mesurer les couches de rendu avant changement ; limites de page minimale/police dans le bilan. | Oui | 2026-09-23 |
| TASK-011 | Extraire de `plan-style.js` les styles, sols, symboles, murs/ouvertures et annotations en modules de rendu explicites ; conserver signatures appelées par `editor.js`, sans accès réseau depuis les rendus. Les cinq extractions sont achevées, chacune validée par 38 PNG et six JSON identiques à sa référence. | Oui | 2026-09-24 |
| TASK-012 | Appliquer palette sobre, raccords de murs, fenêtres fines, sols découpés aux pièces, mobilier contenu dans son empreinte orientée, libellés nom/surface et échelle. Les 22 types du catalogue utilisent des sprites réalistes locaux avec fallback vectoriel, optimisés à 27,73 Mio. La présentation extérieure est séparée des annotations : fond ivoire, feuille ombrée, cotes globales et échelle 0–1–2 m. Les menuiseries ont leur propre renderer : portes avec jambages/seuil/battant et fenêtres avec dormant/vitrage/appui ; les rectangles exacts affichent des dimensions intérieures adaptatives. Le dernier run conserve 38 documents identiques, zéro réseau et 564/564 assets chargés ; 78 tests JS, 103 tests benchmark, Go, Ruff et revues au vert. Le sens réel des battants reste une convention faute de donnée et l'adéquation esthétique reste à évaluer avec les utilisateurs. | Partiel | 2026-09-27 |
| TASK-013 | Vérifier sélection, déplacement, permutation, caméra, sauvegarde/rechargement et annulation si existante ; documenter navigation clavier/focus. Comparer captures et identité JSON, puis publier rapport esthétique et latence. Vérifié sur page Chromium minimale avec requêtes interceptées ; 38 PNG et six JSON identiques au repos. Page authentifiée/lecteur d'écran hors de cette preuve. | Oui | 2026-09-24 |

Sortie : document inchangé à style seul, zéro élément structurel inventé,
images contrôlées aux zooms/DPR prévus, tests éditeur au vert et alerte performance traitée.

### Implementation Phase 4 — Sprint 4 : retouches cohérentes

- **GOAL-004**: Une demande structurelle a le même effet dans document, éditeur, aperçu et export. Dépend de GOAL-003.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Caractériser `diffusion.edit_plan`. Avant extraction, rédiger `docs/sprints/4-command-contracts.md` : signatures, schémas de commandes/erreurs, correspondance routes existantes et nouveaux modules `services/ai/app/edit_commands.py` et `edit_service.py`. Faire revoir ce contrat ; puis extraire interprétation, application et aperçu en conservant les contrats clients. | Oui — contrat revu et façades/service applicatif extraits | 2026-10-02 |
| TASK-015 | Dans `services/ai/app/edit_commands.py` et `edit_service.py`, implémenter les signatures approuvées de TASK-014 pour ajout/retrait/déplacement de pièces, ouvertures et mobilier ; appliquer validation avant sauvegarde. Une demande ambiguë ou invalide retourne diagnostic sans mutation. | En cours — première tranche meubles/ouvertures/pièces; matrice de tests et contrôles géométriques à terminer | 2026-10-02 |
| TASK-016 | Préserver identifiants et `layout.seed/arr` lorsque compatibles ; expliciter toute régénération globale et conserver révision source. Tester répétition de commande, conflit de révision et absence de changement sur refus. | Non | — |
| TASK-017 | Benchmark retouches sur six plans figés : documents avant/après, image locale, Gemini si exécuté et export SVG/DXF. Vérifier que chaque modification structurelle figure dans tous les formats. | Non | — |

Sortie : aucune retouche structurelle limitée au PNG ; changements non demandés
détectés, diagnostics sans sauvegarde partielle et rapport de régression publié.

### Implementation Phase 5 — Sprint 5 : qualité spatiale et Gemini

- **GOAL-005**: Démontrer les gains spatiaux et mesurer la fidélité de Gemini séparément. Dépend de GOAL-004.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | Dans `layout_partis`, `layout_select` et `compliance`, calculer graphe de circulation via portes, exposition par fenêtres et collisions de mobilier ; évaluer le document final après adaptation. Garder évaluateur benchmark indépendant. | Non | — |
| TASK-019 | Comparer proposition Together et placement local à BuildingSpec fixé ; sauvegarder dispositions avant/après `plan_adapt`. Choisir conservation, suppression ou reformulation de la proposition selon gain observé, coût et taux de rejet ; documenter la décision avant modification correspondante. | Non | — |
| TASK-020 | Comparer sélection actuelle et sélection contrainte avec le même plafond de 8 candidats et seeds identiques ; enregistrer les nombres réellement générés et évalués. Classer d'abord les contraintes dures puis les préférences, publier diversité et taux de succès sans masquer les refus. | Non | — |
| TASK-021 | Séparer dialogue Together et rendu Eden/Gemini derrière adaptateurs concrets ; comparer guide seul et guide avec consignes de mobilier à document fixé. Conserver tous prompts/résultats expurgés, trois répétitions par cas du sous-ensemble image. | Non | — |
| TASK-022 | Établir contrôle de fidélité avec annotations indépendantes de murs/ouvertures ; toute anomalie structurelle critique rend le rendu non validé et garde le local comme représentation exacte. Ne pas automatiser l'acceptation par simple seuillage. Publier évaluation aveugle et limites du contrôle. | Non | — |

Sortie : rapport apparié complet, hypothèses acceptées/rejetées/inconclusives,
aucune affirmation d'amélioration Gemini sans images réelles et mesures.

### Implementation Phase 6 — Sprint 6 : cas d'usage et parcours éditeur

- **GOAL-006**: Parcours brief → édition → sauvegarde → export testable de bout en bout. Dépend de GOAL-005.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-023 | Inventorier dans `internal/httpapi/handlers_api.go` les fonctions de génération, adaptation et export et rédiger `docs/sprints/6-use-cases.md` avec symboles source/cible, signatures et dépendances. Revoir cette table avant extraction vers `internal/planning/service.go` ; handlers limités à auth, validation et traduction HTTP, interfaces limitées aux dépendances externes testées. | Non | — |
| TASK-024 | Séparer état/caméra/commandes/réseau dans `editor.js` en réutilisant `plan-edit.js`; tests déterministes des commandes et conflits, restitution d'erreur visible et conservation des modifications non sauvegardées. | Non | — |
| TASK-025 | Ajouter E2E sur stack locale : brief, résultat, édition d'une ouverture, sauvegarde, rechargement, SVG/DXF/PDF ; contrôler coordonnées et isolation entre projets. Archiver captures et compte rendu. | Non | — |

Sortie : E2E et tests Go/JS ciblés réussis, exports cohérents et erreurs récupérables.

### Implementation Phase 7 — Sprint 7 : jobs durables

- **GOAL-007**: Reprendre un traitement interrompu sans double révision. Dépend de GOAL-006.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-026 | Dans `internal/jobs/service.go` et `services/ai/app/worker.py`, formaliser états, propriétaire de traitement, clé d'idempotence et acquittement après persistance ; documenter migration du chemin HTTP vers exécution durable avant activation. | Non | — |
| TASK-027 | Avant changement, rédiger `docs/sprints/7-job-policy.md` depuis les latences mesurées : nombre de tentatives, délai global, backoff, durée de bail, heartbeat et concurrence avec valeurs numériques et justification. Revoir cette politique et tester sa cohérence bail/délai ; puis l'implémenter dans `internal/jobs/service.go` et `services/ai/app/worker.py`. Distinguer panne transitoire/erreur métier, callbacks terminaux et reprise des abandons. | Non | — |
| TASK-028 | Injecter crash avant/après sauvegarde, indisponibilité Redis/HTTP et réponse perdue ; vérifier une seule révision, terminaison des jobs et absence de concurrence double. Comparer temps et appels avant/après. | Non | — |

Sortie : scénarios de panne reproductibles, pas de double écriture, logs et métriques
permettant de retracer un job et son fournisseur réel.

### Implementation Phase 8 — Sprint 8 : recette MVP 2D

- **GOAL-008**: Produire une recette traçable du MVP 2D et de ses limites. Dépend de GOAL-007.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-029 | Geler configuration puis exécuter corpus tenu à l'écart, suite complète locale et E2E ; classer tous échecs et ne plus ajuster les paramètres sur ce corpus sans créer une nouvelle évaluation indépendante. | Non | — |
| TASK-030 | Produire `docs/mvp-2d-acceptance.md` : exigences, preuves, tests, planches, avis architecture, latences, coûts, limites et procédures de reprise ; refaire les revues Standards/Spec des diffs finaux. | Non | — |

Sortie : aucun défaut bloquant connu du parcours 2D, preuves accessibles et limites
explicites. Cette recette ne vaut ni finalisation de la 3D ni validation scientifique
générale ni mise en production commerciale automatique.

## 3. Alternatives

- **ALT-001**: Gemini comme source unique de géométrie : écarté pour le MVP car aucune reconstruction/validation vectorielle fiable n'est démontrée.
- **ALT-002**: Optimiser immédiatement le GAN : différé car il n'agit pas sur le parcours principal.
- **ALT-003**: Réécrire toute l'application en architecture complexe : écarté ; extractions progressives et contrats suffisent au chantier identifié.

## 4. Dependencies

- **DEP-001**: Python et dépendances existantes, Node pour tests canvas, Go et stack locale pour E2E ; relever leurs versions dans les runs.
- **DEP-002**: Accès fonctionnel Eden/Gemini et Together pour expériences externes ; si indisponible, marquer le sous-ensemble non exécuté et ne pas conclure sur le modèle.
- **DEP-003**: Évaluateurs humains et corpus annoté nécessaires à la validation architecturale externe ; les tests locaux restent exécutables sans eux.

## 5. Files

- **FILE-001**: `services/ai/app/{pipeline,diffusion,plan_adapt,vectorize,together_image,compliance}.py` : orchestration, contrats et rendu externe.
- **FILE-002**: `services/ai/app/{layout_partis,layout_select,plan_openings,plan_geometry}.py` : contraintes et qualité spatiale.
- **FILE-003**: `web/static/js/{editor,plan-style,plan-edit}.js`, `web/tests/` : rendu et commandes.
- **FILE-004**: `internal/httpapi/handlers_api.go`, `internal/jobs/service.go`, `internal/plan/validate.go`, `services/ai/app/worker.py` : parcours et fiabilité.
- **FILE-005**: `benchmark/`, `research/metrics/`, `docs/sprints/`, `docs/architecture-2d-audit.md` : preuves et suivi continu.

## 6. Testing

- **TEST-001**: Caractérisation locale sans API facturée : tests pipeline, architecture, rendu et intégration image simulée ; paramètres explicites dans chaque rapport.
- **TEST-002**: Contrats partagés Go/Python : validité/refus, dimensions finies, conflits d'identifiants et ouvertures hors mur.
- **TEST-003**: `node --test web/tests/*.test.cjs` et captures navigateur sur documents figés ; tester comportements plutôt que détails d'implémentation.
- **TEST-004**: Comparaisons appariées suivant `benchmark/README.md`, planches et rapport utilisant `benchmark/report-template.md`.
- **TEST-005**: Tests de panne et E2E du parcours complet ; revue Standards et Spec distinctes, corrections vérifiées avant passage au bloc suivant.

## 7. Risks & Assumptions

- **RISK-001**: Une API peut changer de modèle effectif et de latence ; archiver dates et provenance, ne pas assimiler seed locale et déterminisme réseau.
- **RISK-002**: Refuser les plans invalides peut réduire le taux de succès ; publier les deux métriques ensemble.
- **RISK-003**: Améliorer le style peut dégrader lisibilité, fidélité ou vitesse ; critères séparés et retour à la couche précédente si régression.
- **ASSUMPTION-001**: Le MVP prioritaire est le parcours 2D existant ; 3D, facturation et extensions commerciales ne sont pas incluses dans ces critères de fin.

## 8. Related Specifications / Further Reading

- [Audit scientifique et cartographie](pipeline-scientific-audit.md)
- [Audit et sprints précédents, références visuelles](architecture-2d-audit.md)
- [Protocole benchmark](../benchmark/README.md)
- [Skill de planification](../.agents/skills/create-implementation-plan/SKILL.md)
- [Skill de revue](../.agents/skills/code-review/SKILL.md)
