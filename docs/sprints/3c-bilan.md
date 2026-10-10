# Sprint 3C — rendu architectural de l'éditeur 2D

État au 2026-09-24 : TASK-010, TASK-011 et TASK-013 livrées ; TASK-012 partielle.
Palette, sols, mobilier, murs/ouvertures et annotations sont
isolés ; sols, canapé en L, seuil inféré et annotations à faible zoom ont été
améliorés. La refonte concerne
exclusivement `web/static/js/editor.js`
et son rendu `PlanStyle`, **pas** les images Gemini ni le PNG Pillow.

## Plan avant code

1. **Stabiliser (TASK-010).** Figer six `PlanDocument` du run
   `benchmark/runs/3b-polygons-final`, graines 0 : `dev01` compact, `dev02`
   garage, `dev03` étroit, `dev04` couloir segmenté, `dev05` mobilier et
   `dev13` maison large. Capturer le vrai canvas avec les scripts de l'éditeur,
   à 50/100/200 % du zoom ajusté et DPR 1/2. Ajouter des captures de sélection
   et de glissement avant dépôt sur un cas représentatif. Archiver version du
   navigateur, dimensions CSS/backing, polices, JSON, sources JS et mesure de
   temps de dessin. Bloquer les requêtes réseau dans le harnais ; ne pas lancer
   de sauvegarde pendant la capture. Le PNG Pillow n'est pas une référence canvas.
2. **Extraire (TASK-011).** Caractériser l'ordre des couches, les transformations
   monde/écran et `ctx.save/restore`, puis isoler en petites étapes les styles,
   sols, symboles, murs/ouvertures et annotations. Préserver l'API
   `window.PlanStyle` appelée par `editor.js` et tester chaque extraction avant
   tout changement esthétique. `editor.js` garde état, caméra, interactions,
   rendu des surcouches d'édition et cycle réseau ; `plan-edit.js` garde les
   commandes géométriques. Aucun accès réseau depuis le rendu.
3. **Corriger la fidélité puis polir (TASK-012).** Appliquer aux seuls éléments
   présents dans le document une palette sobre proche des deux références :
   murs sombres et hiérarchisés, fenêtres fines, battants/arches conventionnels,
   sols discrets découpés aux pièces, mobilier vu de dessus dans son empreinte
   orientée, noms et surfaces lisibles. Tester le canapé en L tourné, les murs
   inversés, fenêtres et couloirs. Éliminer ou qualifier clairement les éléments
   inventés par le style (marche d'entrée déduite d'un ID, murs masqués).
4. **Simplifier et mesurer (TASK-013).** Comparer les mêmes JSON/caméras/polices
   avant/après, captures côte à côte et latence de dessin par cas. Contrôler
   sélection, glissement, permutation, zoom, annulation, sauvegarde et
   rechargement ; identité du JSON pour les changements de style. Vérifier
   focus, nom accessible du canvas, outils et messages d'erreur. Toute régression
   structurelle visuelle ou tout refus serveur après édition est un échec,
   indépendamment d'un jugement esthétique favorable.

## Cartographie des responsabilités et risques avant extraction

| Zone | Responsabilité actuelle | Risque / contrat à figer |
|---|---|---|
| `editor.js::draw` (≈ 170 lignes) | Compose sols, mobilier, murs, ouvertures, sélection, légende DOM et conformité | Couplage rendu/DOM/état ; préserver l'ordre et la distinction `draw(full)` |
| `plan-style.js` (882 lignes) | Palette, ~20 symboles, sols, murs, ouvertures, labels et cotes | Extraction par famille sans changement de pixels initial ; préserver `PlanStyle` |
| `plan-edit.js` | Déplacements, collisions, couloirs et commandes | Boîtes englobantes et tolérance de recouvrement différentes du contrat serveur polygonal |
| `editor.html` | Canvas, toolbar, scripts et données JSON | Contrôle zoom et raccourcis ; capture après chargement des polices/animations |

La revue Spec signale le canapé en L dépassant l'empreinte déclarée d'environ
0,72 m, les ouvertures tronquées visuellement alors que l'arc conserve la largeur
brute, les murs de couloir masqués et une marche dessinée depuis l'ID
`w_outer_3`. Le sens de battant n'est pas stocké : toute représentation est une
convention graphique, non une déduction du modèle. `plan-edit.js` autorise des
manipulations via boîtes englobantes et tolérance de 0,05 m² alors que le serveur
valide désormais des polygones ; couvrir le refus de sauvegarde et son message
sans assimiler cette correction métier à une refonte esthétique.

La revue Standards confirme que `requestAnimationFrame` évite déjà certains
redessins multiples, mais qu'un survol repeint textures et mobilier et que les
ouvertures cherchent leur mur linéairement. Optimiser seulement après mesure.
Le canvas n'a pas de nom accessible ni de focus ; la sélection initiale est à
la souris. Ces lacunes entrent dans la recette interactive.

## Garde-fous et critères de fin

- Source de vérité : coordonnées, IDs, murs, ouvertures, mobilier et superficies
  du `PlanDocument`; pas de décoration structurelle non représentée par lui.
- Deux étapes de comparaison distinctes : extraction sans différence de pixels,
  puis style avec revue visuelle et géométrique. Mesurer six documents et les
  trois zooms / deux DPR prévus ; documenter navigateur, polices et dimensions.
- Tests JS d'état et de rendu ajoutés avant extraction,
  `node --test web/tests/plan-edit.test.cjs` puis nouveaux tests de rendu,
  et contrôles E2E d'édition au vert après chaque bloc ; suites Python/Go
  pertinentes sur toute modification du contrat.
- La référence stylistique ne démontre ni conformité constructive ni qualité
  universelle. Les défauts de conception spatiale relèvent du sprint 5.

Skills appliqués : `create-implementation-plan` pour le découpage,
`frontend-refactor-planner` (stabiliser → extraire → simplifier → polir),
`review-and-refactor` pour les responsabilités, et revues Standards/Spec du
`code-review`. La consigne du skill de garder les fichiers intacts cède à la
demande explicite de l'utilisateur de séparer les responsabilités.

## TASK-010 — première capture et correction planifiée

Le harnais initial exécute réellement `plan-style.js`, `plan-edit.js` et
`editor.js` dans Chromium ; la capture pilote le zoom de l'éditeur et extrait
les pixels du canvas. Smoke `dev01`, zoom 100 %, DPR 1 réussi et inspecté.
Ce premier passage n'est pas encore une baseline figée.

Revues Standards/Spec immédiates : archiver aussi les six JSON et la dépendance
Playwright ; valider les IDs/zooms/DPR uniques ; vérifier le zoom observé et
l'identité du document détenu par l'éditeur ; journaliser toute requête réseau
et faire échouer une sauvegarde ; enregistrer deux états interactifs avant
dépôt. Remplacer la temporisation fixe par la fin des frames et décrire
explicitement le harnais HTML minimal. Il n'embarque ni CSS global ni police
Google DM Sans : la typographie est un fallback local, à distinguer de la
capture produit avec police chargée. Les temps instrumentés couvrent les
couches `drawSite` → `drawDimensions`, pas le dessin complet.

Après correction, relancer smoke, revue, tests JS et la matrice complète avant
de déclarer TASK-010 terminée. Aucune extraction ni retouche visuelle d'ici là.

Le premier smoke du harnais renforcé a révélé que `editor.js` dessine avant
`resize()` pendant son initialisation : le premier `scale` observé n'est pas
le zoom ajusté. Le harnais prend désormais l'échelle après deux frames comme
référence 100 %, puis vérifie les zooms demandés. Aucun fichier du rendu produit
n'a été modifié pour ce test.

Dernière micro-étape avant gel : partager la collecte des `pageerror` avec la
capture interactive pour refuser aussi les exceptions survenues pendant le
glissement ; déclarer Shapely dans la dépendance optionnelle du harnais et
consigner les versions/empreintes des polices système candidates. La famille
réellement choisie par le fallback navigateur reste une limite : la comparaison
pixel-à-pixel ne vaut que dans un environnement navigateur/OS/polices identique.

## Résultat TASK-010 : baseline figée

Run final : [manifest des captures](../../benchmark/runs/3c-editor-baseline-reviewed/manifest.json)
et [archive source](../../benchmark/runs/3c-editor-baseline-reviewed/source.zip),
SHA-256 de l'archive
`4EDF1CCAD729CB31BA944AB3CFCCC3A4D6262A4CDF9B637299F2C27D2A4B6779`.
Les six JSON sont archivés aussi dans `inputs/`. Chromium 151.0.7922.34,
Playwright 1.62.0, Shapely 2.1.2 ; plateforme et empreintes de polices système
candidates dans le manifeste.

La matrice contient **36 PNG de repos** (6 cas × 3 zooms × 2 DPR) et deux PNG
interactifs `dev05` (sélection et glissement avant dépôt). Les zooms réellement
observés valent 50/100/200 % ; au DPR 2 le canvas de 960 × 594 CSS possède
1920 × 1188 pixels de backing. Zéro tentative réseau, zéro erreur JavaScript
et aucune mutation du document interne dans ces captures. Le glissement est
annulé avant sauvegarde. Les 18 tests JS existants et Ruff sur le harnais passent ;
les deux dernières revues Standards/Spec ne relèvent aucun blocage.

Inspection visuelle des PNG `dev01` compact, `dev02` garage, `dev03` étroit,
`dev05` sélection/glissement : murs et ouvertures lisibles au cadrage, mais le
zoom 50 % sur la parcelle étroite comprime fortement noms et surfaces. Le
glissement invalide affiche clairement son fantôme rouge « Chevauchement ».
Cela caractérise le comportement courant, sans démontrer une amélioration.
Durée des couches `drawSite` → `drawDimensions` sur les 36 captures : médiane
2,2 ms, min 0,7 ms, max 5,9 ms, **non** une mesure complète du cycle de dessin
et non une comparaison de performance isolée.

Limite de portée : le harnais monte les scripts de production dans une page HTML
minimale. Il n'inclut ni le CSS global ni la police DM Sans chargée depuis un
CDN par l'application. Une comparaison pixel-à-pixel devra reprendre le même
environnement et la même page minimale ; la recette visuelle finale nécessitera
en plus une capture de l'interface réelle. Le prochain bloc doit d'abord
caractériser puis extraire les responsabilités sans changer ces pixels.

## TASK-011 — micro-bloc 1, plan avant code

1. Figer `3c-editor-baseline-reviewed` comme référence pour ce bloc, sans
   écraser les captures. Ajouter tests Node de la résolution nom/couleur.
2. Extraire uniquement les données et fonctions de palette/libellé de
   `plan-style.js` dans `plan-style-palette.js`. Garder l'API `PlanStyle` inchangée ;
   charger le nouveau script avant `plan-style.js` dans le template et le
   harnais. Aucune logique géométrique ni esthétique ne change ici.
3. Revue immédiate Standards/Spec ; exécuter tests JS, Ruff du harnais et la
   matrice des 36 PNG. Comparer **octet par octet** chaque image de repos et les
   deux états interactifs ; comparer les empreintes des JSON d'entrée et relever
   toute différence. Si un pixel diverge, ne pas prétendre à une extraction
   neutre ; analyser puis corriger avant le bloc suivant.
4. Documenter résultat et limites. Les autres extractions (sols, mobilier,
   murs/ouvertures, annotations) suivent en blocs séparés, chacun avec revue,
   tests et comparaison.

Les deux tests de caractérisation `plan-style-palette.test.cjs` passent sur le
code **avant** extraction : nom explicite, repli du nom générique, couleur
connue/inconnue et absence de mutation du paramètre. Ils ne couvrent pas à eux
seuls le rendu visuel, d'où la comparaison intégrale de la matrice ensuite.

Revue immédiate du premier essai d'extraction : `project.html` et
`admin_plan.html` chargent aussi `plan-style.js` et perdraient la palette.
Avant le benchmark candidat, ajouter la dépendance dans ces deux templates,
vérifier tous les consommateurs par recherche globale et tester leurs aperçus.

## Résultat TASK-011, micro-bloc 1

`plan-style-palette.js` porte désormais exclusivement les couleurs, libellés
et leurs deux résolveurs. `PlanStyle` conserve son API publique. Les trois
templates consommateurs chargent la palette avant le rendu ; le harnais suit
le même ordre. Le test d'ordre protège `editor.html`, `project.html` et
`admin_plan.html`. Tests : **21 JS** et `go test ./internal/httpapi` réussis ;
Ruff du harnais réussi. Revues Standards/Spec : blocage des deux autres pages
détecté puis corrigé, aucun blocage restant.

Comparaison : [rapport détaillé et liens vers les images](../../benchmark/comparisons/3c-palette-extract/report.md).
Les **38 PNG** (36 repos, sélection, glissement) et les six JSON appariés sont
identiques avant/après. Les images `dev01`, `dev02`, `dev03` et `dev05` ont été
inspectées. Aucune amélioration esthétique revendiquée. Les captures de la
page projet/admin réelle et les prochains modules de rendu restent à faire ;
TASK-011 n'est donc pas encore terminée.

### Vérification complémentaire des aperçus avant la prochaine extraction

Avant de poursuivre : ajouter un test navigateur optionnel qui monte les trois
scripts palette → style → `plan-thumb.js` avec un document de fixture existant,
puis vérifie l'absence d'erreur JS, la légende et des pixels non vides. Garder
le test statique d'ordre des trois templates. Ce smoke vérifie l'intégration
du composant d'aperçu, sans se faire passer pour une capture de la page projet
authentifiée ou pour une comparaison esthétique complète.

La revue du smoke a signalé que la seule taille du PNG ne prouve pas que le
plan est dessiné. Remplacer cette assertion par des pixels d'un mur connu et
du fond sur la fixture, puis rejouer le test navigateur avant validation.

Le test navigateur passe avec un pixel de mur sombre et un pixel de feuille
clair attendus, en plus de la légende et de l'absence d'erreur JavaScript.
Il dépend de Chromium Playwright optionnel : si le navigateur manque sur une
autre machine, le test est **skipped**, pas réputé réussi. Ici il a bien été
exécuté. Cela vérifie le composant d'aperçu, pas l'interface authentifiée.

Vérification finale de ce micro-bloc : **30 tests `benchmark/tests`**, **21 tests
JS**, tests `internal/httpapi` et Ruff ciblé réussis ; `git diff --check`
sans erreur d'espacement (avertissements CRLF du checkout). Les empreintes des
**38/38 PNG** de la comparaison restent identiques. La prochaine étape est
l'extraction des sols, après un plan et des tests de caractérisation propres à
ce rendu ; puis viendront mobilier, murs/ouvertures et annotations.

## TASK-011 — micro-bloc 2 : sols

Le [plan détaillé des sols](3c-floors-plan.md) a été écrit avant le code. Les
**10 tests Node de caractérisation** passent sur le renderer actuel : huit types
de pièces dont chambre, cuisine, séjour, SDB et garage, polygone concave,
triangle, absence de contour, équilibre `save/restore`, découpage et absence de
mutation. Le premier essai de test comptait aussi les lignes du carrelage après
le clip ; l'assertion limite désormais le compte au seul contour avant `clip`.
L'extraction peut commencer après la revue de ce bloc de tests.

La revue a renforcé les tests avant extraction : ils comparent désormais les
coordonnées exactes du chemin avant `clip`, interdisent toute peinture avant
celui-ci et vérifient l'imbrication complète des `save/restore`. Le plan a aussi
rectifié l'ordre effectif : les libellés sont dessinés avant les ouvertures.
Les dix tests repassent ; la revue finale de ce correctif n'a pas trouvé de
blocage restant.

Extraction neutre achevée : `plan-style-floors.js` reçoit `box`, `m2px` et
`fill` explicitement ; `PlanStyle.drawFloor/drawFixtures` et les trois pages
consommatrices restent compatibles. **31 tests JS**, smoke Chromium de la
miniature, `go test ./internal/httpapi` et Ruff ciblé réussis. Les revues
Standards/Spec n'ont trouvé aucun blocage ; la duplication historique des
couleurs entre sols et palette sera traitée lors de la variation esthétique.
Les [38 captures avant/après](../../benchmark/comparisons/3c-floors-extracted/report.md)
et les six JSON sont identiques octet par octet. La phase design peut partir de
`3c-floors-extracted`, sans attribuer de gain visuel à cette extraction.

Avant la variation de style, un onzième test vérifie sur douze types que le
premier aplat du sol et la couleur publique `PlanStyle.fill`/légende coïncident
après normalisation hexadécimal/RGB. Il passe sur la référence extraite et
servira de garde-fou quand les couleurs seront éclaircies.

La revue du test a relevé une contradiction du plan : changer l'aplat dans le
module sols seul laisserait la légende avec l'ancienne couleur. Le plan Phase 2
autorise désormais la modification de `plan-style-palette.js` comme source
unique des aplats ; le module sols utilisera `fill(room)`. Les valeurs et les
motifs visés sont figés dans le plan avant cette retouche.

Variation graphique des sols terminée : palette commune à la légende et au
canvas, aplats clairs, lames pâles dans les chambres, trames discrètes du
séjour/couloir et carrelage des pièces humides. Les **38 captures** du candidat
`3c-floors-design-v1` diffèrent de la référence extraite ; les **six JSON**
des plans, les dimensions, zooms, DPR et navigateur sont inchangés. La
[comparaison illustrée](../../benchmark/comparisons/3c-floors-design-v1/report.md)
documente les cas studio, garage, couloir, parcelle étroite et interactions.
Les revues Standards/Spec n'ont trouvé aucun défaut bloquant. La densité des
annotations à 50 % et le mobilier qui traverse des murs sur une fixture
restent à corriger dans des blocs distincts ; ce sprint de sols ne termine
donc ni TASK-011 ni TASK-012 du plan 2D global.

Vérification finale ciblée : **32 tests JS**, smoke Chromium de la miniature,
`go test ./internal/httpapi` et Ruff passent. `git diff --check` réussit,
avec seulement les avertissements CRLF du checkout. Un seul passage du
benchmark ne permet pas de conclure à un effet de performance ; le rapport
donne les durées descriptives et les limites du harnais.

## TASK-011 — micro-bloc 3 : mobilier

Le [plan du sous-sprint mobilier](3c-furniture-plan.md) précède tout changement
du renderer. Sur le code précédent, deux tests de caractérisation passent :
signatures de commandes des 23 identifiants de catalogue/fallback, position,
rotation, échelle, tri du tapis, équilibre `save/restore` et non-mutation. La
revue Standards/Spec a demandé de rendre les signatures distinctives et de
contrôler l'angle réel ; ces assertions ont été ajoutées. Les couleurs ne
sont pas captées par ce mock : l'extraction devra aussi comparer les 38 PNG.

Le diagnostic du canapé en L est précis : `drawSofa` ajoute 0,72 m à la
profondeur enregistrée dans `size_m`, alors que le placement du mobilier et le
rendu Pillow utilisent déjà celle-ci comme empreinte totale. Le correctif
prévu concerne uniquement le dessin 2D, sans déplacer les meubles du document.

Extraction neutre effectuée : le rendu du mobilier a été déplacé dans
`plan-style-furniture.js`, chargé par les trois templates et le harnais. Une
erreur initiale d'indice dans le chargement du harnais a été détectée par la
revue, puis corrigée avant la capture complète. Les [38 images et six JSON
appariés](../../benchmark/comparisons/3c-furniture-extracted/report.md) ont
les mêmes SHA-256 que la référence `3c-floors-design-v1`. **34 tests JS**,
smoke Chromium et Ruff ciblé passent ; les deux axes de revue n'ont plus de
blocage. Aucune amélioration visuelle n'est attribuée à l'extraction.

Correction du canapé en L : le nouveau test échouait sur l'ancien symbole
(`+1,52 m` dessiné contre `+0,80 m` autorisé), puis passe à 0/90/270° pour
quatre tailles positives et pour le canapé deux places. La revue a fait
borner les détails fixes pour les petites tailles permises par le schéma ; le
dessin nominal du deux places garde sa signature. La [comparaison illustrée](../../benchmark/comparisons/3c-furniture-footprint-v1/report.md)
montre **26/38 images modifiées**, **12/38 inchangées** et les six JSON
inchangés. Dans `dev13`, le canapé ne franchit plus le mur sud. Les autres
types de mobilier, annotations et pages authentifiées complètes restent hors
de cette correction.

Vérification finale du sous-sprint mobilier : **35 tests JS**, **30 tests
`benchmark/tests`** dont le smoke Chromium de miniature,
`go test ./internal/httpapi`, Ruff ciblé et `git diff --check`
réussissent. Le contrôle `git` n'émet que des avertissements CRLF du checkout.
La dernière revue Standards/Spec ne signale plus de blocage. Le sous-plan
mobilier est terminé ; la tâche d'extraction et de design 2D globale reste
partielle jusqu'aux murs/ouvertures et annotations.

## TASK-011 — micro-bloc 4 : murs et ouvertures

Le [plan du sous-sprint](3c-walls-openings-plan.md) a précédé l'extraction.
Trois tests Node caractérisent les quatre directions/jonctions de murs, une
porte et une fenêtre sur mur inversé, ainsi que le seuil actuellement inféré.
La revue a renforcé les assertions des quatre chemins et limité la tolérance
du chargement optionnel au seul futur module de murs.

Extraction neutre achevée dans `plan-style-walls.js` : murs, ouvertures et
seuil forment maintenant un module sans état éditeur. L'ordre de chargement
est vérifié dans trois templates et le harnais n'utilise plus d'indices
positionnels pour insérer l'instrumentation. Les [38 PNG et six JSON](../../benchmark/comparisons/3c-walls-extracted/report.md)
sont identiques avant/après. **38 tests JS**, smoke Chromium, tests Go et
Ruff ciblé passent ; les deux revues n'ont trouvé aucun défaut bloquant.
La prochaine variation supprimera uniquement le seuil/flèche non fondés.

Variation terminée : le test échouait d'abord sur les dix opérations canvas
qui dessinaient une marche et une flèche à partir du seul identifiant
`w_outer_3`. `drawPorch` reste exporté pour compatibilité, mais ne peint plus.
La porte, son arc et sa position sont contrôlés séparément. La [comparaison
illustrée](../../benchmark/comparisons/3c-walls-no-inferred-porch/report.md)
montre **26/38 PNG modifiés**, les **12 vues à 200 % inchangées car le seuil
est hors champ**, et les six JSON inchangés. Les pixels modifiés inspectés à
100 % se situent sous la porte sud. **38 tests JS**, **30 tests benchmark**,
tests Go, Ruff et `git diff --check` passent. Revues Standards/Spec sans
blocage ; la fonction de compatibilité vide et ses deux callsites seront à
supprimer ensemble dans un nettoyage ultérieur. Le sens du battant reste une
convention en l'absence de champ explicite. Les annotations sont la prochaine
responsabilité à isoler et à améliorer.

## TASK-011 — micro-bloc 5 : annotations

Le [plan du sous-sprint annotations](3c-annotations-plan.md) a été écrit avant
le code. Trois tests de caractérisation passent sur le renderer actuel :
format des cotes, nom et surface, regroupement des couloirs, `noArea`,
non-mutation et débordement d'un nom dans une cellule projetée à 50 %.
La revue a fait aligner l'échelle du dernier test sur 50 % du repère de base.
Le chargement optionnel du nouveau module ne sera autorisé que pendant cette
phase préalable ; après extraction, son absence devra faire échouer les tests.

Extraction neutre des annotations achevée dans `plan-style-annotations.js` :
la façade conserve `drawDimensions`, `drawRoomLabels`, `hallGroups` et
`polyArea`. Le script est chargé dans les trois templates, les tests et le
harnais. Les [38 PNG et six JSON](../../benchmark/comparisons/3c-annotations-extracted/report.md)
sont identiques avant/après ; **41 tests JS**, smoke Chromium, tests Go et
Ruff ciblé passent. La revue n'a trouvé aucun blocage ; un `Map` inutilisé
hérité reste volontairement jusqu'à une variation mesurée. Cette extraction
ne corrige pas encore les textes débordants à faible zoom.

Variation des annotations achevée : le test rouge initial prouvait le
débordement d'un nom et d'une surface dans une cellule de 1,5 × 1,5 m. Le
renderer mesure maintenant chaque texte autour de son ancre, réduit le nom
jusqu'à 8 px, réserve 4 px aux bords et omet le nom ou la surface seulement
si nécessaire. Deux régressions supplémentaires ont été corrigées : choisir
un segment de couloir qui accueille réellement le nom, et ignorer un segment
physiquement trop étroit même s'il est large en pixels à fort zoom. Les
[38 captures comparées](../../benchmark/comparisons/3c-annotations-fit-v2/report.md)
comptent **8 PNG modifiés et 30 inchangés** ; les six JSON restent identiques.
Les surfaces `SDB`/`WC` qui débordaient à 50 % sont omises, avec les noms
conservés. **44 tests JS**, dont six annotations, les **30 tests benchmark**,
le smoke Chromium, les tests Go, Ruff et `git diff --check` passent. Les revues
Standards/Spec sont sans point actionnable. Le placement hors mobilier et la garantie d'une ancre dans
une pièce concave restent des travaux distincts.

## TASK-013 — interactions, clavier et sauvegarde

Le [plan du sous-sprint](3c-interactions-plan.md) a précédé le code. Les tests
navigateur ont d'abord reproduit les flèches actives hors du canvas, l'absence
de cible clavier et deux courses de sauvegarde. Le canvas a désormais un nom,
une description et un focus ; Entrée/Maj+Entrée parcourent les pièces, les
flèches exigent le focus du canvas et Ctrl+Z laisse les champs éditables gérer
leur propre historique. Les outils annoncent leur état et les statuts sont
accessibles ; le template a une instruction spécifique en lecture seule.

La sauvegarde réémet un PUT pour une édition faite pendant un PUT en cours,
avec le nouveau `base_revision_id`, et une sauvegarde manuelle consomme le
minuteur d'autosauvegarde restant. Les tests couvrent aussi refus HTTP, panne
réseau, topologie invalide, réessai, double clic pendant le PUT et rechargement
d'une révision figée. Le [rapport apparié](../../benchmark/comparisons/3c-interactions/report.md)
montre **38/38 PNG et 6/6 JSON identiques** au sprint annotations, malgré les
nouveaux comportements d'édition. Le harnais ne représente pas une session
authentifiée complète ni un lecteur d'écran ; ses mesures de latence sont
descriptives et insuffisantes pour conclure à un effet de performance.
Validation finale : **48 tests benchmark**, **44 tests JS**, tests Go de
`internal/httpapi`, Ruff ciblé et `git diff --check` passent ; les revues
Standards/Spec n'ont plus de point actionnable.

## TASK-012 — micro-bloc menuiseries 2D

Le [plan du sous-sprint](3c-openings-fidelity-plan.md) précède les
modifications. Première phase : les baies sont désormais intersectées avec
leur mur réel. Un arc de porte partiellement hors mur suit la seule portion
visible ; une ouverture sans portion visible ou aux données invalides ne
génère plus de symbole. Les tests rouges ont reproduit ces défauts avant le
correctif. La [comparaison appariée](../../benchmark/comparisons/3c-openings-bounds-v1/report.md)
est **38/38 PNG et 6/6 JSON identique** : le corpus gelé n'avait pas ces cas
invalides. Revues Standards/Spec sans blocage. Le traitement visuel des
fenêtres suit dans la phase 2.

Seconde phase : les fenêtres ont un vitrage bleu pâle centré et des jambages
aux extrémités. Les mêmes extrémités écrêtées commandent trou, rails, vitrage
et jambages ; sous 6 px projetés, les jambages sont omis. Le
[rapport apparié](../../benchmark/comparisons/3c-openings-fidelity/report.md)
compte **28/38 PNG modifiés**, **6/6 JSON d'entrée inchangés**. L'inspection
des vues à 50, 100 et 200 % montre une meilleure délimitation des fenêtres,
mais le gain perceptif reste à valider par des utilisateurs. Les tests rouges
ont précédé le code, puis **49 tests JS**, **48 tests benchmark**, les tests Go
`internal/httpapi`, Ruff et `git diff --check` passent. Revues Standards/Spec
sans blocage. Le sens du battant reste conventionnel ; les autres glyphes
de mobilier restent hors de ce sous-sprint.

## TASK-012 — micro-bloc véhicule 2D

Le [plan du sous-sprint véhicule](3d-car-glyph-plan.md) a précédé le code.
Un test rouge a mesuré les roues débordant de 0,04 m hors de l'empreinte
cataloguée. La carrosserie, la cabine, les quatre roues et les quatre feux
sont désormais proportionnés à `size_m` ; les tests contrôlent leurs bornes
aux tailles 4,2 × 1,8 et 2,1 × 0,9 m et aux rotations 0/90/270°. Un second
test rouge a précédé la séparation du vitrage avant/arrière. Le reflet
superflu a été retiré. La revue a identifié que l'épaisseur du trait pouvait
encore dépasser le chemin borné ; un troisième test rouge a précédé le
clipping local à l'empreinte, maintenant protégé par `save/restore` de l'item.
Le [benchmark apparié](../../benchmark/comparisons/3d-car-glyph/report.md)
compte **12/38 PNG modifiés** (les seules vues des deux plans avec voiture),
**6/6 JSON identiques**. Aux zooms 50/100/200 %, la cabine reste sobre ; le
chevauchement du libellé GARAGE est un défaut distinct d'annotation. **51
tests JS**, **48 tests benchmark**, les tests Go `internal/httpapi`, Ruff et
`git diff --check` passent. Les revues Standards/Spec sont sans blocage.

## Refonte visuelle globale — 25 septembre 2026

Le [sprint de design contemporain](design-editor-modern-1.md) remplace les
corrections isolées par une direction graphique commune : papier blanc,
murs anthracite, chêne clair, dalles minérales et catalogue contemporain.
Les 22 types du catalogue partagent désormais des primitives de dessin
proportionnelles et un clipping local ; le blanchiment global des couleurs
et les helpers décoratifs vides ont été supprimés. Les tests couvrent aussi
les tailles compactes, les entrées invalides et le routage de chaque glyphe.

Les libellés de l'éditeur cherchent une zone libre de mobilier, y compris
pour les objets tournés et les pièces concaves. Le repli essaie nom/surface,
nom seul, puis omission. Deux défauts trouvés en revue ont été reproduits
par des tests rouges et corrigés : le préfiltrage trop strict autour de
l'ancre initiale et le choix d'un segment de couloir occupé malgré un
segment libre. Les revues des blocs de base et d'annotations sont closes.

Après inspection de la première capture et retour utilisateur, une seconde
passe rapproche le catalogue des références : matières nuancées, coutures,
plis du linge, veinage du bois, détails botaniques et carrosserie profilée.
La [comparaison finale](../../benchmark/comparisons/editor-modern/report.md)
montre **38/38 captures modifiées**, avec **6/6 documents JSON identiques**.
Les [22 objets du catalogue](../../benchmark/runs/editor-modern-catalogue-v2/after.png)
ont été rendus avant/après. Validation : **59 tests JS**, **48 tests benchmark**,
tests Go HTTP, Ruff et contrôle du diff réussis ; revues Standards et Spec
sans blocage. Le rendu reste schématique et les conflits physiques déjà dans
les documents ne sont pas résolus par ce sprint graphique. À 50 %, certains
petits espaces meublés omettent leur libellé faute de place. Le rapport détaille
ces limites et distingue comparaison visuelle et évaluation utilisateur.

## Mobilier réaliste intégré — 26 septembre 2026

Après rejet du rendu encore schématique, le [sprint assets](design-editor-assets-1.md)
remplace sept types par des images RGBA de dessus : lits simple/double, canapés
deux places/en L, fauteuil, plante et voiture. Les assets imagegen et leurs prompts
sont enregistrés dans `web/static/assets/furniture/`. Le chargeur indépendant ne
charge que les types présents et les met en cache ; les symboles vectoriels restent
disponibles en secours. Les positions, tailles, rotations et données ne changent pas.

Le [rapport apparié](../../benchmark/comparisons/editor-assets/report.md) compare
**38/38 vues modifiées**, **6/6 JSON identiques**, plus le catalogue complet.
**65 tests JS**, **59 tests benchmark**, tests Go HTTP et Ruff réussis ; revues
Standards et Spec sans défaut bloquant. Une régression du lancement direct du
harnais a été reproduite par un test rouge et corrigée. Les captures finales
`editor-assets-v2` archivent ce correctif sans différence de pixels avec v1.

Le sprint est terminé, pas la refonte esthétique complète : quinze types restent
vectoriels, comme les miniatures projet/admin. Les sept PNG totalisent 15,56 Mo
avant optimisation. La validation porte sur le Canvas réel dans un hôte minimal,
pas sur une page authentifiée complète ni les exports serveur. L'agencement et
les arcs de portes préexistants ne sont pas modifiés.

## Cuisine, repas et sanitaires réalistes — 27 septembre 2026

Le [sprint technique](design-editor-technical-assets-1.md) étend le rendu réaliste
à neuf types supplémentaires : table/chaise de repas, table basse, plan de travail,
plaque, réfrigérateur, baignoire, WC et lavabo. Les faux damiers et un WC avec halo
ont été rejetés avant intégration. Les 16 assets retenus sont maintenant contrôlés
sur leur canal alpha et leur bord de canevas ; les neuf nouveaux types possèdent
aussi un test explicite de fichier, dimensions et orientation.

Le [rapport](../../benchmark/comparisons/editor-technical-assets/report.md) établit
**38/38 captures modifiées**, **6/6 JSON identiques**, zéro requête externe et
zéro chargement en échec dans les vues normales. Validation finale : **67 tests
JavaScript**, **84 tests benchmark**, Go HTTP, Ruff et diff-check. Les revues
Standards et Spec sont closes sans défaut bloquant après correction d’une liste
de test dupliquée et renforcement du contrôle alpha.

Le catalogue n’est pas encore entièrement homogène : table de nuit, armoire,
bureau, cheminée, tapis et meuble TV restent vectoriels. Les neuf PNG ajoutent
12,11 Mio et les 16 assets totalisent 26,95 Mio ; le chargement à la demande limite
le coût par page, mais une optimisation reste nécessaire avant une cible mobile.

## Finalisation du catalogue réaliste — 27 septembre 2026

Les six derniers glyphes (`nightstand`, `wardrobe`, `desk`, `fireplace`,
`rug.rect`, `tv.console`) ont été remplacés par des sprites ImageGen en vue
zénithale. Le catalogue atteint ainsi **22 types réalistes sur 22**, sans changer
les documents ni les empreintes. Les URL optimisées sont versionnées `-opt1` et
le fallback Canvas reste disponible.

L’optimisation déterministe réduit les 22 PNG de 39 291 254 à 27 734 479 octets
(**−29,41 %**), soit un catalogue final encore 1,86 % plus léger que les seize
assets du sprint précédent. Le chevet et le meuble TV utilisent un canevas au
ratio exact de leur empreinte, contrôlé automatiquement.

La preuve finale comprend **38 captures**, six JSON identiques, zéro requête
réseau, zéro asset échoué, une planche catalogue avant/après, **67 tests
JavaScript**, **102 tests benchmark**, Go HTTP, Ruff et diff-check. Les revues
Standards et Spec se terminent toutes deux sans défaut. Rapport :
`benchmark/comparisons/editor-final-assets/report.md`.

## Présentation extérieure et cotations — 27 septembre 2026

Le fond, l’ombre de l’emprise, les cotes globales et l’échelle 0–1–2 m sont
désormais regroupés dans `plan-style-presentation.js`. Le placement des noms,
surfaces et couloirs reste dans `plan-style-annotations.js`. Le contrat public
de `PlanStyle` et le moteur d’interaction ne changent pas.

Les scripts partagés par les trois templates sont centralisés dans le partial
`plan_style_scripts`, et les cinq suites JavaScript réutilisent un loader unique.
La couche refuse aussi les transformations nulles au lieu de dessiner une fausse
échelle à partir du fallback historique.

Le run `benchmark/runs/editor-presentation-v2` contient **38 captures**, six JSON
identiques, zéro réseau et **564/564 assets chargés**. La médiane de rendu par vue
augmente de 3,54 %, sous la limite de 10 %. Validation : **70 tests JavaScript**,
**102 tests benchmark**, Go HTTP, Ruff et diff-check. Les revues Standards et
Spec se terminent sans finding. Rapport :
`benchmark/comparisons/editor-presentation/report.md`.

## Menuiseries et dimensions intérieures — 27 septembre 2026

Le rendu des ouvertures est extrait de `plan-style-walls.js` vers
`plan-style-openings.js`. Les portes disposent maintenant d’une réservation,
de jambages, d’un seuil, d’un battant et de son articulation ; les fenêtres
affichent vitrage, dormant, jambages, appui et meneau adaptatif. Le contrat public
de `PlanStyle` reste stable.

Les pièces rectangulaires exactes affichent dans l’éditeur une dimension
`largeur × profondeur` sous leur surface. Les couloirs et formes irrégulières
sont exclus ; en cas de conflit avec un meuble volumique, le label retire d’abord
la dimension, puis la surface, avant d’omettre éventuellement le nom.

Le run `benchmark/runs/editor-openings-dimensions-v1` contient **38 captures**,
38 documents et six entrées identiques à la baseline, zéro réseau et **564/564
assets chargés**. Le temps médian passe de 352,75 à 357,25 ms (**+1,28 %**).
Validation : **78 tests JavaScript**, **103 tests benchmark**, Go HTTP, Ruff et
diff-check. Rapport :
`benchmark/comparisons/editor-openings-dimensions/report.md`.
