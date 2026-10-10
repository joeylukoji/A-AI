---
goal: Définir le contrat des retouches vectorielles avant extraction du service
version: 1.0
date_created: 2026-10-02
last_updated: 2026-10-02
owner: Projet A-AI
status: 'In progress'
tags: [architecture, edition, plan-document, 2d]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In_progress-yellow)

Ce contrat borne le premier bloc du sprint 4. Une demande d'édition doit produire soit une
question sans mutation, soit une commande déterministe appliquée au `PlanDocument`; l'image est
ensuite rendue depuis le document résultant. Le parcours HTTP, le modèle de job et le format
historique des révisions restent compatibles.

## 1. Requirements & Constraints

- **REQ-001**: Le `PlanDocument` est la source de vérité pour les retouches structurelles et d'équipement.
- **REQ-002**: Les commandes portent des IDs stables d'objets existants ou une description explicite d'objet à créer.
- **REQ-003**: Une interprétation ambiguë, une cible absente, une commande inconnue ou un document invalide renvoie un diagnostic sans mutation ni nouvelle révision.
- **REQ-004**: L'application d'une commande est déterministe et s'effectue sur une copie ; le document d'entrée ne doit jamais être muté.
- **REQ-005**: Après application, validation du document complet avant persistance ; l'aperçu local est produit depuis le document validé.
- **REQ-006**: Une image générative peut illustrer la version validée, mais ne peut remplacer ni modifier sa géométrie.
- **REQ-007**: Les retouches de programme qui nécessitent un nouveau pavage indiquent explicitement les IDs, ouvertures ou meubles qui ne peuvent pas être préservés.
- **CON-001**: Conserver routes, auth, quotas, événements et réponse de job existants.
- **CON-002**: Ne pas changer le schéma public `PlanDocument` au cours de cette extraction ; étendre le contrat interne de commandes seulement.
- **CON-003**: Ne jamais confondre absence de résultat d'un modèle d'image avec une commande appliquée.
- **GUD-001**: Distinguer les phases `interpret`, `apply`, `validate`, `render` et `persist`; chacune a un résultat testable.
- **PAT-001**: Utiliser des commandes de domaine immuables, un interpréteur remplaçable et un service applicatif qui reçoit le validateur, le renderer et le générateur d'IDs comme dépendances; le service n'accède pas directement à HTTP, à la base ou aux fournisseurs.

### Contrat interne `EditCommand` v1

```json
{
  "version": 1,
  "action": "move_furniture | add_furniture | remove_furniture | move_opening | add_opening | remove_opening | move_room | remove_room | replace_program",
  "target_id": "stable object ID; source wall ID for add_opening",
  "target_room_id": "stable containing room ID for new furniture",
  "position": {"x": 0.0, "y": 0.0},
  "offset_m": 0.0,
  "width_m": 0.9,
  "rotation_deg": 0.0,
  "catalog_id": "catalog entry for add_furniture",
  "opening_type": "door | window",
  "room_type": "living | kitchen | dining | bedroom | bathroom | wc | hallway | garage | office | storage | laundry | veranda",
  "program": [{"type": "bedroom", "count": 1, "area_m2": 12.0}],
  "reply_fr": "confirmation or clarification question",
}
```

Les champs non pertinents pour une action sont omis; champs obligatoires : `move_furniture`
(`target_id`, `position`), `add_furniture` (`target_room_id`, `catalog_id`, `position`),
`remove_furniture` (`target_id`), `move_opening` (`target_id`, `offset_m`), `add_opening`
(`target_id` du mur, `opening_type`, `offset_m`, `width_m`), `remove_opening` (`target_id`),
`move_room` (`target_id`, `position` delta métrique), `remove_room` (`target_id`) et
`replace_program` (`program`). `rotation_deg` est facultatif pour `add_furniture` et vaut zéro
par défaut. `position` exprime toujours une coordonnée absolue du meuble,
sauf pour `move_room` où elle exprime `(dx, dy)`. Le service crée tous les IDs. Les types
d'ouverture autorisés sont strictement `door|window`, avec offset non négatif; les IDs de catalogue sont vérifiés dans
le catalogue applicatif courant avant application.

`replace_program` reste le nom explicite du chemin de reconstruction complet utilisé pour les
changements de programme; il ne constitue pas `add_room` avec géométrie dessinée à la main.
L'entrée suit le langage du `BuildingSpec` (`type`, `count` obligatoires et `area_m2` facultatif par type).
Un `id` est facultatif et n'est admis que depuis un programme assaini qui reprend explicitement
un ID déjà présent dans le plan; les IDs arbitraires fournis par le modèle sont retirés avant
`parse_edit_command`.
Après
reconstruction, `PlanDocument.program` est recalculé depuis les pièces finales, avec un ID par
pièce, son type, son nom et son aire polygonale. L'opération annonce dans `reply_fr` que la
géométrie est repavée et ne promet la conservation d'aucun identifiant de pièce, mur ou ouverture
qui ne peut être apparié sans ambiguïté. Le déplacement géométrique local de pièce demeure
distinct via `move_room`.

### Contrat de résultat

| Résultat | État document | Aperçu | Persistance |
|---|---|---|---|
| `clarification_required` | Identique à l'entrée | Réutiliser l'aperçu courant | L'interpréteur retourne `clarify=true` avant l'analyse d'une commande; job `succeeded` historique; aucune nouvelle révision |
| `rejected` | Identique à l'entrée | Réutiliser l'aperçu courant | Job `failed` avec code métier; aucune nouvelle révision; statut projet restauré depuis la révision source |
| `applied` | Document copié, muté et validé | Rendu local de ce document | Une révision source→cible |

Les erreurs stables du service v1 sont `unknown_action`, `target_not_found`, `invalid_payload`,
`constraint_violation`, `invalid_result` et `revision_conflict`. Les détails d'erreur internes
peuvent évoluer; les codes restent stables. `/v1/edit` conserve les clés `plan_document`,
`building_spec`, `compliance`, `dimensions`, `parcel`, `rules`, `preview_key`, `image_png_b64`,
`reply_fr`, `edit_en`, `method`, `clarify` et `steps`; les nouveaux champs internes sont additifs.
Go mappe `clarification_required` aux clés historiques et termine le job comme aujourd'hui.
`rejected` termine en échec avec le code stable et sans sauvegarde de révision. Le commit
`SaveRevision` reçoit l'ID de la révision source en `baseRevisionID`; un changement concurrent
retourne `revision_conflict`, n'ajoute aucune révision et préserve la version courante.
Une commande partiellement appliquée n'est jamais retournée ni persistée.

## 2. Implementation Steps

### Implementation Phase 1 — caractérisation et revue du contrat

- GOAL-001: Établir le comportement actuel des routes et figer les contrats internes avant extraction.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Tracer `handlers_api.go:handleEditPlan/processEditPlan`, `jobs.Service.RunInlineEdit`, `/v1/edit` et `diffusion.edit_plan`; relever les champs révision et transport conservés. | Oui | 2026-10-02 |
| TASK-002 | Faire revoir ce contrat contre le code observé et le plan MVP 2D avant de créer les modules de service. | Oui — corrections appliquées | 2026-10-02 |

### Implementation Phase 2 — implémentation du cas d'usage

- GOAL-002: Appliquer les commandes au document vectoriel puis dériver l'aperçu du résultat validé.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Créer `services/ai/app/edit_commands.py` avec validation stricte et types de commandes v1, sans dépendance FastAPI ou fournisseur. | Oui | 2026-10-02 |
| TASK-004 | Créer `services/ai/app/edit_service.py` pour interpréter, appliquer sur copie, valider et rendre ; garder `diffusion.edit_plan` comme façade de compatibilité. | Oui — service applicatif et façade préservés; 35 tests dédiés couvrent actions, rejets géométriques et reconstruction | 2026-10-02 |
| TASK-005 | Brancher `/v1/edit` sur le service, garder les clés de réponse historiques et ne persister que `applied`; une clarification conserve l'état `ready`. | En cours — CAS de révision source et restauration du statut en cas d'échec branchés | 2026-10-02 |

### Implementation Phase 3 — vérification et bilan

- GOAL-003: Démontrer absence de mutation partielle et cohérence document/aperçu/persistance.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Ajouter tests unitaires par action, cible absente, commande ambiguë, document invalide, erreur du rendu et copie profonde de l'entrée. | Oui — actions locales, reconstruction, calcul d'aires dérivées, clarification et absence de mutation couverts | 2026-10-02 |
| TASK-007 | Tester le parcours API/job/revision, conflits de révision, identifiants conservés et aperçu recalculé depuis le document cible; vérifier la concordance des exports SVG/DXF. | En cours — forwarding IA et exports prouvés; CAS HTTP/job PostgreSQL non exécuté faute de base | 2026-10-02 |
| TASK-008 | Exécuter lint et suites ciblées IA/Go/JS ; publier captures et rapport apparié sur les cas 2D concernés, avec Gemini marqué comme illustration seulement ou non exécuté. | Oui — suites IA/Go/JS et benchmark apparié vérifiés; Gemini reste non exécuté dans cette comparaison | 2026-10-02 |

### Implementation Phase 4 — couverture des mutations locales (reprise)

- GOAL-004: Démontrer par une matrice d'actions que chaque retouche locale est déterministe, ciblée et rejetée sans mutation lorsqu'elle invalide la géométrie.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Dans `services/ai/tests/test_edit_service.py`, couvrir le succès et la cible absente pour déplacement/suppression de meuble et d'ouverture, et ajouter meuble/ouverture; vérifier IDs stables et document source inchangé. | Oui — tests de mutation et cible manquante | 2026-10-02 |
| TASK-010 | Couvrir `move_room` avec déplacement intérieur valide, limites du plan, chevauchement, ouvertures attachées et murs; corriger seulement les défauts démontrés par `validate_document`. | Oui — translation collective des meubles, murs et ouvertures; limites/chevauchements rejetés | 2026-10-02 |
| TASK-011 | Ajouter des tests de service où la validation ou le rendu échoue; établir que l'entrée reste inchangée et qu'aucun résultat `applied` n'est produit. | Oui — validation/rendu en échec sans sortie partiellement appliquée | 2026-10-02 |
| TASK-012 | Relancer suite IA complète, tests Go CAS, Ruff et `git diff --check`; mettre à jour les résultats et les tâches restantes, sans fermer les tests API/export ni le benchmark. | Oui — vérifications complètes post-changement consignées ci-dessous | 2026-10-02 |

### Implementation Phase 5 — intégration du contrat d'édition et sorties

- GOAL-005: Fournir des preuves reproductibles que l'API IA transmet le résultat édité sans altération et que les exports 2D utilisent les mêmes géométries du document canonique.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Ajouter un test `services/ai/tests/test_pipeline.py` de `POST /v1/edit` avec `app.api.diffusion.edit_plan` simulé; vérifier instruction normalisée, transfert des champs document/spec/image/job, réponse JSON appliquée inchangée et absence d'appel à un fournisseur externe. | Oui — test ciblé API réussi | 2026-10-02 |
| TASK-014 | Ajouter dans `internal/export/service_test.go` un test sur un document modifié représentant une révision éditée; exporter SVG et DXF et vérifier les mêmes sommets ordonnés (attribut `points` SVG transformé par l'échelle connue, entités `VERTEX` DXF filtrées sur `ROOMS`) et le même libellé de pièce; valider dynamiquement le nombre d'entrées xref PDF et leurs offsets d'objets. | Oui — parité géométrique SVG/DXF et intégrité dynamique de la table xref PDF | 2026-10-02 |
| TASK-015 | Exécuter les tests Go et Python concernés; vérifier le statut de la base locale. Si `DATABASE_URL` n'est pas disponible, consigner explicitement que la preuve de concurrence CAS HTTP/job reste conditionnelle et ne pas prétendre l'avoir exécutée. | Partiel — suites locales réussies; `DATABASE_URL` absent et moteur Docker indisponible, tests PostgreSQL/CAS ignorés explicitement | 2026-10-02 |

### Implementation Phase 6 — benchmark apparié du générateur 2D

- GOAL-006: Mesurer l'état actuel du générateur local sur exactement les mêmes entrées que la référence conservée, avec un protocole contrôlé, des artefacts intacts et une interprétation descriptive.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-016 | Valider `benchmark/runs/3b-contract-profile-reviewed/manifest.json` : 20 programmes development, graines 0–4, 1 répétition, même Python/OS/dépendances/police/configuration et hashes runner/évaluateur. Détecter la dérive de `corpus.json`, récupérer le corpus autoritatif du `source/source.zip`, exiger son hash canonique égal au manifeste, et vérifier l'intégrité locale des 100 paires avec `paired_rows(ref, ref)`. | Oui — copie externe du corpus divergente détectée; source archivée autoritative et 100 samples cohérents validés | 2026-10-02 |
| TASK-017 | Extraire le corpus vérifié de `source/source.zip` dans un répertoire temporaire dédié puis lancer `python -m benchmark.run --out benchmark/runs/4a-current-20261002 --corpus <corpus-temporaire-vérifié> --seeds 0 1 2 3 4` avec la configuration locale intégrée (AI stub, backend procédural, réseau bloqué); conserver snapshot/hash et chaque erreur; ne jamais inclure le split evaluation. | Oui — 100 observations mesurées, 15 erreurs `PlanConstraintError` préservées, aucune requête réseau | 2026-10-02 |
| TASK-018 | Comparer la référence `3b-contract-profile-reviewed` et le run courant avec `benchmark.compare`, sortie neuve `benchmark/comparisons/4a-vs-3b-current`; vérifier 100 paires, inspecter `summary.json`, rapport et planche, distinguer hashes d'image et différence perceptuelle, signaler les graines dont l'effectivité n'est pas confirmée dans le document, consigner écarts et limites sans attribuer causalement le résultat à une modification isolée. | Oui — métriques stables, signal de latence descriptif, planche et analyse visuelle illustrative publiées avec limites explicites | 2026-10-02 |

### Implementation Phase 7 — fermeture des vérifications locales

- GOAL-007: Fermer les vérifications locales reproductibles du sprint sans maquiller les tests PostgreSQL ignorés ni inclure l'ensemble d'évaluation réservé.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-019 | Depuis la racine du dépôt, lancer `node --test web/tests` avec Node 24; conserver le nombre de fichiers/tests passés/échoués et le code de sortie. Si Node refuse un répertoire comme cible, relancer avec les neuf chemins `web/tests/*.test.cjs` résolus depuis PowerShell. | Oui — Node 24 refuse le dossier comme cible; les neuf fichiers explicites passent, 82/82 | 2026-10-02 |
| TASK-020 | Revalider sans mutation les 100 paires de référence/candidat via `benchmark.compare.paired_rows`; vérifier que `summary.json`, la planche et les deux manifestes sont présents et correspondent à 20 IDs de développement × 5 graines × 1 répétition. | Oui — 100 paires intègres; artefacts présents; split evaluation exclu | 2026-10-02 |
| TASK-021 | Mettre à jour TASK-008 comme terminée uniquement si les tests Node/Python/Go et la comparaison sont confirmés; laisser TASK-007 ouverte tant que PostgreSQL/CAS et intégration HTTP/job ne sont pas exécutés avec une base disponible. | Oui — TASK-008 clôturée; TASK-007 reste ouverte faute de PostgreSQL/Docker | 2026-10-02 |

### Implementation Phase 8 — correction du test de porte inversée

- GOAL-008: Corriger l'attendu du test de rendu selon le contrat `hinge=start` mesuré depuis le point A du mur, sans modifier un calcul de rendu déjà conforme.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-022 | Vérifier le contrat dans `docs/sprints/feature-editor-door-semantics-1.md` et la transformation de `openingGeometry`/`drawDoor` dans `web/static/js/plan-style-openings.js`; calculer le point de départ du battant pour les cas vertical et inversé du test. | Oui — sur le mur inversé, offset 1 m depuis x=4 m donne charnière x=3 m / 60 px; normale positive donne y=−20 px | 2026-10-02 |
| TASK-023 | Dans `web/tests/plan-style-openings.test.cjs`, remplacer seulement la coordonnée attendue du mur inversé par `[60, -20]` et vérifier aussi que `moveTo` de la feuille est la charnière attendue; ne modifier ni renderer ni contrat. | Oui — attendu corrigé et charnière explicite vérifiée; renderer inchangé | 2026-10-02 |
| TASK-024 | Relancer les neuf tests Node, les tests Python de sémantique de porte, `git diff --check` et faire revoir le changement Standards/Spec; garder TASK-008 en cours jusqu'à réussite complète. | Oui — 82 tests Node, 56 tests Python, vérification whitespace et revues Standards/Spec sans finding | 2026-10-02 |

### Implementation Phase 9 — preuve intégrée du conflit CAS HTTP/job

- GOAL-009: Démontrer, sur PostgreSQL réel et sans fournisseur externe, qu'une édition IA basée sur une révision devenue obsolète échoue proprement et préserve la sauvegarde concurrente la plus récente.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-025 | Créer `plan/feature-postgres-cas-http-job-1.md` avec critères d'acceptation explicites pour le test authentifié HTTP → job inline → PostgreSQL CAS, une IA simulée déterministe, des barrières de synchronisation, des tests et risques. | Oui — sprint formalisé avant implémentation | 2026-10-02 |
| TASK-026 | Ajouter à `internal/httpapi/handlers_api_test.go` un test d'intégration utilisant une IA locale bloquée, un save éditeur concurrent, puis des assertions HTTP/job/DB sur `revision_conflict` et la révision courante inchangée. | Oui — test déterministe implémenté avec canaux, aucune IA distante | 2026-10-02 |
| TASK-027 | Ajouter dans `.github/workflows/test.yml` un service PostgreSQL 16 isolé, appliquer les migrations avec `go run ./cmd/api -migrate-only`, puis exécuter les suites API/job/projet avec `DATABASE_URL`. | Oui — un job CI distinct assure l'exécution DB au lieu d'un skip | 2026-10-02 |
| TASK-028 | Exécuter le test localement contre PostgreSQL, les suites Go ciblées, les revues Standards/Spec, puis clore TASK-007 uniquement si la preuve DB réelle réussit. | En cours — intégration sautée faute de `DATABASE_URL` et Docker Engine; CI PostgreSQL ajouté mais pas encore exécuté | 2026-10-02 |
| TASK-033 | Rendre la preuve PostgreSQL du job CI non contournable : un DB test ne doit pas être ignoré si la base manque, est inaccessible ou n'est pas migrée dans le job d'intégration; préserver les skips locaux hors mode strict. | Oui — garde-fou strict ajouté, tests subprocess skip/échec réussis, mode local conservé | 2026-10-02 |
| TASK-034 | Établir une baseline `--cov-branch` sur `services/ai/tests/test_edit_commands.py`, puis ajouter uniquement des tests de frontière pour les branches non exercées du parseur v1; vérifier codes et champs d'erreur sans modifier le comportement. | Oui — 32→49 tests; couverture ciblée 89%→100% statements/branches, suite IA 915 tests; revues Standards/Spec sans finding | 2026-10-02 |
| TASK-035 | Cartographier le flux `edit_service → build_document → vectorize → plan_adapt`, puis figer six cas/5 seeds et exécuter la référence avant tout changement runtime pour la conservation des IDs/parti. | En cours — architecture auditée; plan et baseline runner définis, run référence à produire | 2026-10-02 |

### Vérification Phase 9 — 2026-10-02

- `go test -count=1 ./...` : tous les packages passent localement. Les tests nécessitant une base,
  dont le nouveau scénario, gardent leur skip conventionnel en l'absence de `DATABASE_URL`.
- `go test -v -run TestEditJobRejectsStaleRevisionAfterConcurrentEditorSave ./internal/httpapi` :
  compile/passe avec skip explicite `DATABASE_URL not set`; ce résultat n'est pas une preuve CAS.
- `go vet ./internal/httpapi ./internal/jobs ./internal/project` : réussi.
- Le job `.github/workflows/test.yml:postgres-integration` démarre PostgreSQL 16, applique le schéma,
  puis lance les packages API/jobs/projet sous `-race`. Le YAML est syntaxiquement valide.
- `git diff --check` : aucune erreur d'espacement. Le `-race` ne peut pas être exécuté sur cet hôte
  Windows car `CGO_ENABLED=0` (`go test -race` exige CGO).
- Revues Standards et Spec : les demandes de délai/cleanup ont été adressées; aucun finding résiduel
  confirmé sur la dernière version du changement.

TASK-007 reste ouverte jusqu'à un run CI réussi (ou une exécution locale) démontrant le test avec
PostgreSQL réel; la configuration du job CI ne suffit pas à elle seule à prouver le comportement.

### Durcissement du garde-fou PostgreSQL CI — 2026-10-02

- `REQUIRE_DATABASE_TESTS=1` est limité au job `postgres-integration` : les helpers des tests
  `internal/httpapi` et `internal/project` échouent si l'URL, la connexion ou le schéma manque;
  hors de ce mode, les suites locales conservent leurs skips habituels.
- `go test -count=1 ./internal/httpapi ./internal/project` : réussi.
- `go test -v -count=1 -run 'TestEditJobRejectsStaleRevisionAfterConcurrentEditorSave|TestSaveRevisionDetectsConflict' ./internal/httpapi ./internal/project` : les scénarios DB affichent le skip attendu sans `DATABASE_URL`.
- Les tests `TestDatabaseUnavailableOutcomes` lancent le helper dans un sous-processus et
  confirment l'issue réelle : skip local, échec strict avec diagnostic lorsque la DB manque.
- Avec `REQUIRE_DATABASE_TESTS=1` sans URL, les deux tests DB principaux ont également été
  exécutés directement et ont échoué avec le message `PostgreSQL integration tests are required but unavailable`.
- `go vet ./internal/httpapi ./internal/project` et `git diff --check` : réussis.
- La base locale et un remote Git configuré sont absents; aucun run CI n'a donc été exécuté sur
  cet arbre non poussé. La preuve PostgreSQL réelle reste la condition de clôture de TASK-007.

### Matrice de validation des commandes d'édition 2D — 2026-10-02

- Baseline `python -m pytest tests/test_edit_commands.py --cov=app.edit_commands --cov-branch
  --cov-report=term-missing -q` depuis `services/ai/` : 32 tests, 89%, 10 statements manquants.
- Après ajout de cas nommés : 49 tests ciblés réussis, 114/114 statements et 48/48 branches
  couvertes. Les erreurs de champs absents (`fields`) restent distinctes des valeurs invalides
  explicitement nulles (`catalog_id`, `opening_type`); les IDs optionnels et messages sont normalisés.
- `python -m pytest tests -q` depuis `services/ai/` : 915 passed en 226,50 s. Avertissements tiers
  inchangés : collision PyFPDF/fpdf2 et dépréciation Pillow `Image.getdata`.
- Ruff check/format et `git diff --check` réussis; aucun module de production ni artefact de
  benchmark n'a changé. Couverture = exécution des branches, pas preuve de meilleure qualité des plans.
- Revues finales Standards et Spec : aucun finding. La tâche de fond TASK-015 reste partielle;
  cette matrice sécurise seulement le contrat de parsing des commandes.

### Implementation Phase 10 — couverture des actions d'édition 2D

- GOAL-010: Fermer les écarts ciblés de tests de `edit_service.py` sans modifier l'algorithme, les sorties de plans ni les artefacts benchmark.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-029 | Établir une baseline de couverture branches sur `services/ai/tests/test_edit_service.py` avant le changement et relever les branches métier non exercées. | Oui — 29 tests, 85% statement coverage; rapports et zones manquantes listés dans le plan de sprint | 2026-10-02 |
| TASK-030 | Tester suppression de pièce vers cible absente/moins de deux pièces restantes, agrégation de types, conservation d'aire demandée et aire polygonale moyenne de repli. | Oui — rejets sans mutation; deux bureaux adjacents 4/6 m² donnent count=2 et area=5 m²; Bedroom explicite conservé | 2026-10-02 |
| TASK-031 | Tester chevauchement tapis/meubles dans les deux ordres d'insertion et génération d'identifiant sans collision tous calques confondus. | Oui — les deux insertions rug/canapé autorisées; ID `edit_f1` présent sur un mur entraîne `edit_f2` | 2026-10-02 |
| TASK-032 | Exécuter suite IA, Ruff, couverture après changement et revues Standards/Spec; confirmer que les modules de production et artefacts de benchmark sont inchangés. | Oui — 898 tests, Ruff check/format et revues réussis; seule la couverture ciblée edit_service varie de 85% à 87%, aucun code production ou benchmark édité | 2026-10-02 |

### Vérification Phase 10 — 2026-10-02

- `python -m pytest tests/test_edit_service.py -q` : 35 passed.
- `python -m pytest tests/test_edit_service.py --cov=app.edit_service --cov-branch --cov-report=term-missing -q` :
  35 passed; couverture combinée ciblée 87% contre 85% sur les 29 tests initiaux; lignes manquantes
  27 contre 30 et branches partielles 16 contre 19.
- `python -m pytest tests -q` depuis `services/ai/` : 898 passed, deux avertissements tiers connus
  (double installation PyFPDF/fpdf2 et dépréciation Pillow `Image.getdata`).
- `python -m ruff check tests/test_edit_service.py` et `python -m ruff format --check
  tests/test_edit_service.py` : réussis.
- Revues ciblées Standards/Spec pour chaque bloc : aucun finding final; les revues ont conduit à
  renforcer le calcul de moyenne sur deux pièces distinctes et la cohérence géométrique du fixture.
- Aucune logique de production ni artefact `benchmark/` n'a été modifié; il n'y a donc pas de
  comparaison de génération avant/après à prétendre dans ce sprint test-only.

## 3. Alternatives

- **ALT-001**: Laisser le modèle d'image appliquer seul toute modification ; rejeté car son raster ne met pas à jour la géométrie exportable.
- **ALT-002**: Remplacer immédiatement tout le plan après une demande partielle ; rejeté car cela déplace des éléments hors cible sans preuve de nécessité.
- **ALT-003**: Réécrire les endpoints et le format de job ; rejeté car l'extraction doit préserver les consommateurs existants.

## 4. Dependencies

- **DEP-001**: `services/ai/app/plan_contracts.py` et `document_validation.py` pour les frontières et erreurs de validation.
- **DEP-002**: `services/ai/app/plan_drawing.py` ou `floorplan_render.py` pour produire un aperçu local exact.
- **DEP-003**: `services/ai/app/together_image.py` reste un service facultatif d'illustration après application.
- **DEP-004**: `internal/jobs/service.go` et `internal/httpapi/handlers_api.go` gardent le contrat job/révision public.

## 5. Files

- **FILE-001**: `docs/sprints/4-command-contracts.md` — contrat et progression de la tâche 14.
- **FILE-002**: `services/ai/app/edit_commands.py` — actions et payloads validés.
- **FILE-003**: `services/ai/app/edit_service.py` — application, validation et rendu du cas d'usage.
- **FILE-004**: `services/ai/app/diffusion.py`, `services/ai/app/api.py` — façades d'intégration compatibles.
- **FILE-005**: `services/ai/tests/`, `internal/httpapi/`, `web/tests/` — tests de domaine et d'intégration.
- **FILE-006**: `docs/sprints/4-bilan.md`, `benchmark/` — preuves et rapport final.

## 6. Testing

- **TEST-001**: Chaque action valide transforme seulement sa cible et préserve les IDs non concernés.
- **TEST-002**: Toute erreur ou clarification conserve une égalité profonde du document avant/après et n'ajoute aucune révision.
- **TEST-003**: Toute sortie appliquée passe le validateur partagé avant aperçu et persistance.
- **TEST-004**: L'aperçu local, la révision finale et les exports SVG/DXF représentent le même état; la réponse API existante reste compatible.
- **TEST-005**: Les archives du benchmark initial restent lisibles et non modifiées.

## 7. Risks & Assumptions

- **RISK-001**: Une demande en langage naturel ne spécifie souvent ni cible unique ni coordonnées; l'interpréteur doit demander clarification plutôt que deviner.
- **RISK-002**: Des opérations topologiques comme ajouter une pièce nécessitent un pavage explicite et peuvent invalider ouvertures ou meubles voisins.
- **RISK-003**: Le parcours HTTP courant exécute les jobs inline; ce sprint ne change pas le modèle de durabilité des jobs.
- **ASSUMPTION-001**: Le dessin local du `PlanDocument` est le rendu canonique; un raster génératif est seulement une couche illustrative.

## 8. Related Specifications / Further Reading

- [Plan détaillé MVP 2D](../refactor-mvp-2d-1.md), Sprint 4, tâches 14–17.
- [Audit architecture 2D](../architecture-2d-audit.md), défauts de `edit_plan`.
- [Contrat PlanDocument](../../packages/plan-schema/plan-document.schema.json).
- [Contrats et erreurs de validation](../../services/ai/app/plan_contracts.py).

## Revue du contrat — 2026-10-02

La revue Spec a relevé le périmètre plus large que TASK-015, le CAS de révision manquant,
les états de job non mappés et l'absence de vérification SVG/DXF. Le contrat a été précisé :
`replace_program` signifie reconstruction complète, `PlanDocument.program` est dérivé du
document final, les champs/cibles sont définis par action, la sauvegarde compare l'ID de
révision source et les tests couvrent les exports. La revue Standards a demandé ces mêmes
précisions, ajoutées avant le début du code.

La revue de l'implémentation a ensuite exigé deux correctifs : nommer les IDs non préservés
après reconstruction et remettre le projet en `ready` lorsqu'une édition échoue sans invalider
la révision source. Ces correctifs sont inclus; les tests d'intégration Go dédiés au job/API
restent à faire avant de fermer le sprint.

### Vérification — 2026-10-02

- `python -m pytest services/ai/tests -q` : 871 passed; deux avertissements d'environnement tiers
  (double installation PyFPDF/fpdf2 et dépréciation Pillow `Image.getdata`).
- `go test ./internal/httpapi ./internal/project` : réussi.
- `python -m ruff check` sur les modules et tests concernés : réussi.
- `python -m ruff format --check` sur les nouveaux modules et tests du service : réussi.
- `gofmt -d internal/httpapi/handlers_api.go` et `git diff --check` : aucune différence/action détectée.

La suite complète n'exerce pas encore le flux d'édition avec une révision concurrente au niveau
HTTP/job; cet élément, plus les mesures appariées de benchmark, reste une condition de clôture.

### Reprise — couverture des mutations locales

`edit_service.py` vérifie maintenant l'empreinte rectangulaire réelle des meubles ajoutés/déplacés
(dimensions du catalogue ou de l'instance et rotation) : toute partie hors pièce ou tout
chevauchement avec un autre meuble géométriquement placé est rejeté, même si son `room_id` manque.
Les tapis peuvent chevaucher les
autres meubles, comme dans le moteur de placement initial. `move_room` a une preuve de déplacement
validé avec meuble et ouverture attachée; les meubles associés sont translatés ensemble avant
vérification des collisions, et les cas hors limites/chevauchements sont refusés avant rendu.
`test_edit_service.py` couvre 29 cas paramétrés/unitaires; la suite IA complète de reprise est
réussie et revue sur les deux axes (Spec et Standards).

### Vérification reprise — 2026-10-02

- `python -m pytest services/ai/tests -q` : 891 passed; deux avertissements tiers connus
  (co-installation PyFPDF/fpdf2 et API Pillow `Image.getdata` dépréciée).
- `python -m pytest services/ai/tests/test_edit_service.py -q` : 29 passed.
- `go test ./internal/httpapi ./internal/project` : réussi.
- Ruff check/format sur les modules et tests de cette reprise : réussi.
- `gofmt -d` et `git diff --check` sur les fichiers suivis concernés : aucun écart.

À ce stade, TASK-007 reste ouverte pour le CAS HTTP/job sur vraie persistance; les tâches
TASK-016–TASK-018 apportent la comparaison du générateur local mais ne valident pas le flux API/job.

### Vérification finale de reprise — 2026-10-02

- `node --test web/tests` n'accepte pas le dossier comme cible dans la version de Node installée;
  le repli explicite sur les neuf fichiers `web/tests/*.test.cjs` a réussi : 82 passed, 0 failed.
- `python -m pytest services/ai/tests/test_furnish_layout.py -q` : 56 passed.
- Le test de porte inversée vérifie désormais indépendamment la charnière `[60, 0]` et le bout
  du battant `[60, -20]`; aucun code de rendu n'a été modifié.
- `benchmark.compare.paired_rows` a revalidé les 100 paires. Les manifestes, `summary.json` et la
  planche de contact sont présents; seuls 20 programmes du split development, 5 graines et 1
  répétition sont utilisés.
- `git diff --check` n'a signalé aucune erreur d'espacement sur les fichiers suivis concernés.
- Revues ciblées Standards et Spec : aucun finding sur le test/doc de cette reprise.

TASK-008 est clôturée pour les vérifications locales et artefacts décrits ci-dessus. TASK-007 reste
ouverte : le scénario CAS HTTP/job avec PostgreSQL réel requiert une base de test, indisponible dans
l'environnement de cette reprise.

### Vérification intégration API/export — 2026-10-02

- `python -m pytest services/ai/tests/test_pipeline.py -q -k 'edit_endpoint_preserves_applied_service_result or edit_keeps_plan_without_together_key'` : 2 passed.
- `go test ./internal/export ./internal/httpapi ./internal/project` : réussi.
- `go test ./internal/export -run 'TestPDFXrefEntriesAre20Bytes|TestEditedRevisionGeometryMatchesSVGAndDXFExports'` : tests ciblés réussis, incluant ordre des sommets et offsets PDF vérifiés contre les en-têtes d'objets.
- `go test -v ./internal/project` : CAS PostgreSQL (`TestSaveRevisionDetectsConflict`) ignoré car `DATABASE_URL` absent; les tests non DB passent.
- Vérification d'environnement : aucune `DATABASE_URL`; moteur Docker Desktop indisponible (pipe Linux absent), aucun conteneur PostgreSQL local détectable.
- Le test d'export compare l'ordre complet des sommets après conversion SVG (40 px/m + origine 20 px) avec les paires X/Y ordonnées du calque `ROOMS` en DXF, à partir du même document et libellé de pièce.

La preuve du transport `/v1/edit` et de la concordance de géométrie aux exporteurs est maintenant automatisée. Le parcours HTTP/job avec vraie persistance et conflit concurrent reste non démontré localement sans PostgreSQL; ne pas confondre les tests de contrat isolés avec un test système complet.

### Reprise — identité géométrique des pièces reconstruites — 2026-10-04

Le flux `replace_program`/`remove_room` retire désormais les IDs des entrées du générateur,
puis restaure les IDs après adaptation uniquement lorsque la pièce source et la pièce reconstruite
ont le même type et une correspondance polygonale mutuelle non ambiguë (IoU ≥ 0,25 et marge
≥ 0,10 sur le second choix). Ces seuils sont des heuristiques prudentes non calibrées, pas une
mesure de continuité sémantique validée; une correspondance incertaine reçoit un nouvel ID.
Les IDs générés en double sont rejetés et les références mobilier/programme/dimensions sont
remappées ensemble.

Le benchmark 2D local ajoute un diagnostic IoU par ID sur toutes les pièces source (pièces sans
ID correspondant ou géométrie valide comptées à zéro), en complément du taux d'intersection des
IDs; le comparateur rapporte les moyennes et le delta appariés. Le dernier candidat a livré 30/30
plans valides. L'IoU géométrique même-ID moyen est passé de 0 à 0,9817, la rétention des IDs de 0
à 1, et l'erreur relative moyenne de surface cible de 30,58 % à 29,68 % (Δ apparié −0,90 point).
La référence est explicitement rebasée depuis les sorties historiques en ne changeant que les IDs
source/références; il ne s'agit pas d'une réexécution historique exacte.

Visuellement, 26/30 images sont identiques. Les quatre différences sont `dev02`, graines 1–4;
elles correspondent à la conservation du descripteur d'implantation source. Les six planches de
contact ont été parcourues. C'est une preuve de continuité/régression sur un corpus synthétique,
pas une démonstration de préférence architecturale. Les seuils IoU 0,25 et marge 0,10 restent des
heuristiques non calibrées.

Résultats finaux: `python -m pytest services/ai/tests -q` : 925 passed; tests ciblés du service et
du comparateur : 54 passed, et tests benchmark edit/comparateur : 12 passed. Ruff check/format et
`git diff --check` passent sur les fichiers concernés. Lors d'une exécution plus large de
`benchmark/tests`, un échec distinct demeure dans `test_plan_schema.py::test_door_semantics_cases_are_enforced_by_the_draft_2020_schema` (`door-semantics-valid` rejeté); il n'est pas causé par le code de ce sprint et reste à examiner séparément.
