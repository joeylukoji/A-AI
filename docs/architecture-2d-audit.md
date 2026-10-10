# Architecture 2D — audit et sprints

Date : 22 septembre 2026. Périmètre : génération, adaptation, édition, rendu et export 2D.
Le worker Blender et la bibliothèque 3D sont hors de ce chantier.

État : audit et sprints 1–2 livrés. Le sprint 3A est maintenant livré pour la
caractérisation locale ; le bloc parcelle du sprint 3B est implémenté. Le reste
des sprints demeure au backlog. Voir [bilan 3A](sprints/3a-bilan.md) et
[bilan 3B](sprints/3b-bilan.md).
Le sprint 3 inclut désormais la refonte visuelle du plan de l'éditeur demandée le 22 septembre 2026,
à partir des deux références fournies par l'utilisateur.

Mise à jour de planification : le [plan détaillé MVP 2D](refactor-mvp-2d-1.md)
fait autorité pour l'ordre des tâches restantes : sprint 3 subdivisé en baseline
(3A), contrats (3B), design (3C), puis sprints 4–7 et recette 8. Le backlog
ci-dessous reste le contexte d'origine. Voir aussi la [cartographie scientifique
Gemini](pipeline-scientific-audit.md) et le [protocole benchmark](../benchmark/README.md).

## Méthode

Chaque sprint suit : diagnostic → critères d'acceptation → tests de caractérisation/régression →
implémentation → tests ciblés → bilan. Les modifications locales préexistantes sont conservées.
Skills du dépôt : `review-and-refactor`, `python-code-style`, `fastapi`,
`frontend-refactor-planner` ; `golang-design-patterns` pour l'audit de l'orchestration Go.
La demande explicite de découpage prime sur la règle de conservation des fichiers de `review-and-refactor`.
Les recommandations sont tirées du code actuel, pas d'une mesure de qualité des modèles externes.

## Sprint 0 — diagnostic

### Parcours réellement exécuté

```text
Navigateur / HTMX / éditeur
  → handlers Go : session, organisation, quotas, job, révision, artefacts
  → jobs.Service : HTTP interne /v1/pipeline (SkipQueue=true pour le parcours web)
  → NLU : brief → BuildingSpec
  → diffusion.generate(image=False) : programme → pavage initial, murs, ouvertures
  → GAN : étape conservée ; ne change pas le layout
  → vectorize : assemblage du PlanDocument, mobilier, programme cible, variante
  → plan_adapt : nouveau pavage selon parcelle et variante, nouvelles ouvertures et mobilier
  → aperçu : dessin local du document final → redessin optionnel par un service image
  → Go : persistance d'une révision, PNG et événements SSE
```

Le worker Redis constitue un second point d'entrée, distinct du parcours web actuel.
`vectorize` assemble surtout des données déjà vectorielles : ce n'est pas une reconstruction
de géométrie à partir du raster. L'adaptation repave toutes les pièces ; elle peut donc effacer
les positions proposées par le LLM. Investir dans un meilleur prompt de placement sans traiter
ce second pavage peut ne pas améliorer le résultat final.

### Responsabilités et dépendances observées avant refactoring

| Zone | Responsabilité légitime | Problème constaté |
|---|---|---|
| `internal/httpapi/handlers_api.go` | Adaptation HTTP, auth et validation d'entrée | Orchestre aussi jobs, appels IA, images et sauvegarde ; extraction future des cas d'usage |
| `internal/jobs/service.go` | Cycle de vie et transport des jobs | SQL, Redis, hub SSE et clients IA dans une même structure ; enqueue Redis échoué seulement journalisé |
| `services/ai/app/main.py` | Composition FastAPI et lifecycle | Mélange modèles, auth interne, routes et pipeline |
| `services/ai/app/worker.py` | Consommation Redis et callbacks | Copie du pipeline HTTP ; erreur de traitement sans callback terminal d'échec |
| `diffusion.py` | Compatibilité de génération et coordination provisoire | Plus de 3 000 lignes physiques : prompts, retouches, rendu Pillow, géométrie, programme, HTTP |
| `layout_opt`, `layout_zones`, `layout_partis`, `layout_select` | Construction, énumération, sélection des pavages | Bonne séparation déjà amorcée ; validation des partis dépend de `diffusion` pour les ouvertures |
| `plan_adapt.py` | Adaptation à la parcelle et aux règles | Reconstruit tout ; règles d'ouverture appliquées après placement, sans revalidation des positions |
| `compliance.py` / `internal/plan/compliance.go` | Évaluation indicative | Deux implémentations à comparer ; connexité Python basée sur contacts des pièces, pas les portes |
| `internal/plan/validate.go` | Validation du document | Vérifie quelques invariants, mais pas doublons d'ID, recouvrements ni offsets d'ouverture |
| `web/static/js/editor.js` | Interaction et état de l'éditeur | État, rendu, réseau et commandes encore couplés ; `plan-edit.js` offre déjà un noyau testable |

### Défauts de fidélité et limites métier

1. `_render_floorplan` reçoit murs et ouvertures, mais redessine les cloisons depuis les rectangles,
   puis invente portes et fenêtres. Des couloirs volontairement ouverts peuvent être refermés à l'image.
   La porte sud interprète son offset comme une abscisse alors que son mur est orienté de droite à gauche.
2. `apply_opening_rules` réduit toutes les portes extérieures à la largeur d'entrée, y compris
   la porte de garage de 2,40 m. Élargir une fenêtre ne vérifie pas son dépassement du mur.
3. `edit_plan` modifie seulement le raster pour les consignes sans changement de programme.
   Une fenêtre ou un meuble peut donc changer à l'image sans changer dans le document exporté.
4. Les retouches de programme régénèrent un document sans reprendre explicitement `layout.arr` et
   `layout.seed` de la révision ; la stabilité annoncée n'est pas garantie sur ce chemin.
5. Le score de sélection optimise surface, proportion, côté minimal et circulation.
   `layout_partis.door_issues` contrôle déjà accès par portes, traversées de chambres et porte de garage
   pour les candidats : réutiliser ce contrôle sur le document final après adaptation/édition.
   Le score public de conformité, lui, utilise encore les contacts entre pièces et ne mesure pas
   l'éclairement par fenêtres ni les dégagements de portes.
6. `plan_adapt` impose une emprise minimale même si parcelle moins retraits est trop petite :
   une contrainte impossible doit être signalée, pas masquée par une maison dépassant l'emprise utile.
7. Les JSON libres et les captures générales de `TypeError`/`AttributeError` en 422 peuvent cacher
   une erreur de programmation. Introduire progressivement des contrats et erreurs métier explicites.

### Décisions d'architecture

- Conserver le monolithe modulaire Go et les processus IA actuels.
- Un seul cas d'usage Python de génération, appelé par HTTP et Redis ; progression injectée.
- Extraire des modules concrets : programme, murs/ouvertures, rendu raster. Le domaine géométrique
  ne doit importer ni FastAPI, ni Redis, ni client image, ni le module d'orchestration `diffusion`.
- Conserver temporairement les imports historiques de `diffusion` pour ne pas casser les tests,
  les scripts de recherche et les consommateurs existants. Ne pas créer une seconde implémentation.
- Le rendu local lit le PlanDocument ; le moteur de placement est le seul à créer la géométrie.
- Ne pas changer l'algorithme de sélection des partis en même temps que son découpage.
- Les redessins génératifs restent des illustrations : le guidage ne prouve pas une égalité géométrique.

## Sprint 1 — séparation des responsabilités

Statut : terminé.

1. Établir une baseline des tests 2D en mode local sans appels facturés.
2. Extraire le programme de pièces et la topologie (murs/ouvertures) hors de `diffusion`.
3. Extraire le rendu Pillow dans un module de présentation.
4. Unifier l'orchestration HTTP, Redis et reconstruction après retouche dans un service applicatif.
5. Séparer modèles HTTP, routes et démarrage FastAPI ; garder les contrats d'API.
6. Tester la parité des chemins, les callbacks d'échec et les invariants/imports du domaine.

Acceptation : tests de référence inchangés, pas de dépendance transport dans la topologie,
une seule séquence génération/adaptation, document final transmis à l'aperçu et à la sauvegarde.

Livré :

- `api_models.py`, `api_security.py`, `api.py` : contrats, authentification et routes ; `main.py`
  compose les routeurs et garde le lifecycle. Même interface HTTP, même endpoint public de règles.
- `pipeline.py` : `generate_plan` et `build_document`, partagés par HTTP, Redis et reconstruction
  de programme. La progression est une fonction injectée, les callbacks sont dans `job_progress.py`.
- `worker.py` : transport et sauvegarde uniquement ; un échec de génération ou de sauvegarde est
  signalé au job ; aucune tentative automatique de création de révision en double.
- `room_program.py`, `plan_geometry.py`, `plan_walls.py`, `plan_openings.py` : domaine sans imports
  FastAPI, Redis, Pillow, HTTPX ou `diffusion` (vérifié dans un processus Python isolé).
- `floorplan_render.py` : rendu Pillow extrait. Les imports historiques de `diffusion` nécessaires
  aux appelants existants restent disponibles via réexport, sans duplication de logique.
- `plan_adapt`, `vectorize` et la validation des partis utilisent directement les modules de domaine.

La taille de `diffusion.py` passe d'environ 2 934 à 1 548 lignes non vides avant le dernier nettoyage
d'imports. Il contient encore les prompts, les adaptateurs image et les retouches : ce n'est pas
encore une simple façade. Leur séparation complète reste à faire avec le sprint des retouches.

## Sprint 2 — fidélité locale et ouvertures

Statut : terminé.

1. Reproduire le défaut murs/portes/fenêtres dessinés sans correspondance au document.
2. Dessiner les segments de murs et les ouvertures stockés, dans leur orientation réelle.
3. Préserver la largeur des portes de garage pendant l'adaptation.
4. Tester visuellement/pixellement les cas simples : mur absent, couloir ouvert, porte sud inversée,
   fenêtre explicite et ouverture de garage ; vérifier les tests de disposition existants.

Acceptation : le rendu local n'invente pas de cloison/ouverture ; la porte de garage conserve sa largeur.
La qualité esthétique d'un service d'image externe n'est pas mesurée dans ce sprint.

Livré :

- `plan_drawing.py` dessine les murs stockés et découpe les ouvertures stockées. Il ne reconstruit
  plus de cloisons depuis les pièces et ne crée plus de portes/fenêtres implicites.
- `plan_geometry.opening_segment` projette l'offset depuis `wall.a` vers `wall.b` ; une ouverture
  invalide n'est pas déplacée pour la faire apparaître. La validation explicite reste au sprint 3.
- Le guide d'image distingue une liste absente d'une liste explicitement vide, mobilier compris.
- Les règles de largeur des portes sont des minima ; la porte de garage conserve ses 2,40 m.
- La vérification visuelle a révélé un symbole de canapé en L dépassant `size_m.d` : sa méridienne
  est désormais contenue dans l'empreinte annoncée, avec régression testée à 0°, 90°, 180° et 270°.

### Vérifications et limites

- Baseline : 628 tests réussis et 2 échecs dus au réglage global `TOGETHER_PLANNER=0` de la commande
  de test. Les deux tests attendent un LLM simulé ; ils passent une fois cette surcharge retirée.
- Après sprints : **657 tests** IA 2D + métriques + dataset réussis en 198,66 s.
- Après l'ultime correction visuelle du canapé : **91 tests ciblés** rendu + intégration image
  réussis, dont les quatre nouvelles orientations (ajoutées après la collecte de la suite complète).
- **81 tests ciblés** de pipeline, API, variantes et transports réussis pendant le sprint 1.
- **18 tests JavaScript** de l'éditeur réussis ; `go test ./...` réussi.
- Ruff : règles `E4,E7,E9,F,I,B,UP` et formatage 120 colonnes vérifiés sur les 16 fichiers nouveaux
  ou réécrits ; les avertissements de l'environnement Python global restent préexistants.
- Plan local 14 × 12 m, trois chambres et garage : rendu et inspection visuelle réalisés. Ce cas
  ne remplace pas une validation du corpus ni une mesure des modèles d'image externes.

Les jeux golden de pavage et d'ouvertures restent inchangés. Aucun appel de génération externe réel,
aucun déploiement ni test navigateur E2E de la stack complète n'a été réalisé pour ces sprints.
La reprise durable des jobs, les retouches uniquement raster, les contraintes impossibles et les
évaluateurs Go/Python séparés restent ouverts. Les arcs de porte sont une convention de présentation :
le schéma actuel ne décrit pas le sens d'ouverture ni le côté des paumelles.

## Backlog des sprints suivants

| Sprint | Livrable | Validation attendue |
|---|---|---|
| 3 — Contrats, faisabilité et design de l'éditeur | Types de domaine, validation géométrique, contraintes impossibles explicites ; rendu architectural 2D inspiré des références utilisateur, détaillé ci-dessous | Corpus valide/invalide, parité Go/Python ; comparaison visuelle, fidélité au document et non-régression des interactions |
| 4 — Retouches vectorielles | Commandes explicites ajout/retrait/déplacement ; préservation des variantes ; distinction rendu esthétique et modification géométrique | Même modification dans éditeur, aperçu et export ; aucune modification sur clarification |
| 5 — Qualité spatiale | Graphe de circulation par portes, fenêtres des pièces habitables, dégagements ; sélection multi-candidats avec diagnostics | Corpus fixe + graines, taux de pièces accessibles, erreur de surfaces, ratios, collisions, diversité, durée p50/p95 |
| 6 — Cas d'usage Go et éditeur | Services génération/adaptation/export, état et commandes de l'éditeur séparés du DOM et du réseau | Tests de commandes, E2E brief → édition → export, conflits de révision |
| 7 — Fiabilité des jobs | Reprise après crash, ack/retry/idempotence, limites de concurrence, métriques | Tests panne Redis/HTTP/processus et absence de double révision |

### Sprint 3 — ajout : rendu architectural du plan dans l'éditeur

Statut : **planifié, non implémenté**. Demande : rapprocher le dessin interactif des deux images
jointes par l'utilisateur, en complément du chantier contrats/faisabilité déjà prévu.
L'objectif porte sur le plan affiché dans le canvas de l'éditeur 2D.

Références visuelles de la tâche du 22 septembre 2026 :

- `codex-clipboard-3d33c43e-53e0-4c69-ae7d-0f3a0049e791.png` : plan résidentiel meublé,
  murs noirs, sols clairs par pièce, noms et surfaces discrets, terrasse et végétation légères.
- `codex-clipboard-f626ac93-e766-4d96-912d-b48fe3fdaf68.png` : dessin architectural plus technique,
  murs anthracite pochés, menuiseries fines, arcs de portes, mobilier détaillé en vue de dessus,
  hachures/texture de sol sobres et touches de couleur sur les objets.

Ces images définissent une direction graphique ; leur disposition, leurs pièces et leurs équipements
ne constituent pas le programme à générer. Le contenu affiché provient toujours du `PlanDocument`.

**Direction graphique retenue**

- Fond de feuille blanc ou blanc cassé, palette peu saturée, priorité visuelle aux murs et à la lecture des pièces.
- Murs extérieurs sombres, cloisons hiérarchisées selon leur épaisseur, raccords propres et ouvertures nettes.
- Portes avec battants/arcs fins et fenêtres avec cadres/vitrages lisibles, aux positions et dimensions stockées.
- Sols discrets : carrelage fin, parquet doux, béton du garage ; textures découpées dans les polygones des pièces.
- Mobilier architectural vu du dessus : lits, canapés, tables/chaises, cuisine, sanitaires et véhicule,
  avec contours fins, détails sobres et ombres légères, dans l'empreinte et la rotation déclarées.
- Libellés homogènes, noms puis surfaces en m², sans texte débordant ni masquant les ouvertures ; cotes et échelle lisibles.
- Sélection et poignées d'édition visibles au-dessus du dessin, avec un état de repos sobre.
- Terrasse et végétation seulement lorsque les données du plan les décrivent ; aucun équipement ajouté par le style.

**Étapes et responsabilités**

1. Stabiliser : capturer le rendu actuel sur un corpus fixe (petit appartement, maison avec garage,
   petites pièces et couloir segmenté), relever les temps de rendu et inventorier les interactions.
2. Définir les règles visuelles : palette, épaisseurs, typographie, textures et symboles ; comparer
   un même document aux références avant de généraliser les changements.
3. Découper : isoler dans des modules de rendu les styles partagés, sols, symboles de mobilier,
   murs/ouvertures et annotations. `editor.js` garde état, caméra, sélection et commandes ;
   `plan-edit.js` garde les transformations géométriques. Le rendu reste indépendant du réseau.
4. Implémenter par couches : sols → mobilier → murs/ouvertures → annotations → sélection/poignées.
   Réutiliser les mécanismes de `plan-style.js` qui conviennent ; préserver les interfaces de l'éditeur.
5. Simplifier et optimiser : mutualiser les calculs de projection et mettre en cache motifs/symboles
   si les mesures le justifient ; prendre en compte le zoom et la densité de pixels de l'écran.
6. Vérifier : tests unitaires du rendu et des projections, captures comparatives dans le navigateur,
   parcours de déplacement/permutation/sauvegarde et bilan documenté avec exemples avant/après.

Skills : `frontend-refactor-planner` pour les phases et critères de validation ; `review-and-refactor`
pour les responsabilités et conventions. Appliquer `python-code-style` si une harmonisation du rendu
local Python devient nécessaire. Le découpage explicitement demandé reste prioritaire sur la consigne
de conservation des fichiers du skill de refactoring.

**Critères d'acceptation et tests**

- Un même plan conserve ses coordonnées, identifiants, ouvertures et mobilier après changement de style.
- Les murs/portes/fenêtres affichés correspondent au document ; aucun mur ajouté entre segments de couloir.
- Textures contenues dans les pièces et symboles dans leurs dimensions déclarées, y compris canapé en L
  et éléments tournés ; intégrer au canvas les régressions déjà corrigées dans le rendu Python au sprint 2.
- Lecture vérifiée à 50 %, 100 % et 200 % de zoom, avec tailles de canvas et densités d'écran différentes.
- Sélection, déplacement, permutation, zoom/panoramique, annulation/rétablissement si disponibles et
  sauvegarde/rechargement fonctionnent ; repères de focus et commandes existantes restent utilisables.
- Comparaisons visuelles sur le corpus fixe, tests JavaScript existants au vert et absence de régression
  mesurée sur les temps de rendu et la réactivité des interactions.
- Le changement de style n'altère pas le document utilisé par les exports ; les captures avant/après
  et les éventuelles différences résiduelles avec le rendu Python sont consignées dans le bilan.

Les repères techniques absents du schéma (sens réel des battants, par exemple) restent des conventions
graphiques explicites tant que les contrats ne les décrivent pas. Ce sprint conserve le périmètre 2D.

### Comment mesurer de meilleurs plans

Conserver un corpus reproductible : petites/grandes parcelles, programmes denses, plusieurs SDB,
garage aux différentes façades, programmes sans couloir, surfaces demandées et contraintes impossibles.
Comparer à programme et graine identiques avant/après. Mesurer séparément :

- validité : géométrie finie, pièces conservées, absence de superposition, ouvertures référencées et contenues ;
- usage : accès depuis l'entrée par des portes, intimité nuit/jour, ouverture sur façade, dégagement mobilier ;
- respect du brief : nombre/type/surface, adjacences demandées, contraintes de parcelle ;
- diversité : arrangements distincts à qualité comparable ;
- fidélité : document, PNG local, éditeur et export décrivent la même structure ;
- coût : appels externes, latence, taille du résultat.

Ne pas confondre un meilleur score interne avec une validation architecturale indépendante.
Les corpus golden et tests d'invariants actuels constituent la base de cette comparaison.
