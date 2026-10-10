# Sprint 3B — contrats et faisabilité

État final : TASK-006 à 009 livrées dans le périmètre du profil 2D v1.2.
Ce journal conserve les bilans intermédiaires dans leur ordre chronologique ;
la conclusion et les limites actuelles figurent en fin de fichier.

## Plan du bloc parcelle

1. Figer la référence `benchmark/runs/3a-provenance-final`.
2. Introduire `PlanConstraintError` et un résultat immutable `BuildableParcel`
   dans `services/ai/app/plan_contracts.py` / `parcel_constraints.py`.
3. Calculer l'emprise utile avant le pavage ; distinguer zéro, valeur absente et
   valeur non finie. Les limites du moteur ne sont pas des lois architecturales.
4. Conserver le bornage supérieur historique de 200 m ; refuser les valeurs
   non positives et les retraits négatifs. Arrondir vers l'intérieur quand le
   snap au plus proche dépasse la parcelle ; vérifier de nouveau le minimum
   requis par le moteur après snap pour éviter son agrandissement implicite.
   Le moteur sérialise au centimètre : accepter seulement les grilles multiples
   de 0,01 m, faute de quoi le polygone final pourrait dépasser l'emprise.
5. Brancher à `plan_adapt.adapt` et préserver les zéros explicites dans
   `pipeline.build_document`. Tester aussi `/v1/pipeline` et `/v1/adapt`.
6. Exécuter tests et benchmark apparié : les trois programmes impossibles doivent
   être refusés ; tous les documents/images des autres programmes doivent rester
   identiques. Ne pas masquer un rejet inattendu sous un gain de validité.

Revue préalable Spec : le `or` de résolution des dimensions cachait zéro ; le
packer pouvait réagrandir une dimension arrondie trop petite. Ces deux chemins
sont inclus dans les tests d'acceptation du bloc.

## Implémentation et revue

`BuildableParcel` est immutable et ne dépend pas de FastAPI. Les erreurs
`PlanConstraintError` exposent code et champs ; l'API les traduit en HTTP 422
structuré. La limite historique de travail de 200 m est conservée.

La revue Spec a reproduit et fait corriger deux autres chemins de dépassement :
grille sous la précision centimétrique du moteur, et alias `max_width_m` normalisé
par le NLU. Les dimensions brutes sont maintenant vérifiées avant NLU et
conservées avec priorité `parcel_*` → `max_*` → spec. Le cas largeur 1 m avec
minimum configurable conserve effectivement la largeur et les sommets dans 1 m.
Les erreurs relatives au minimum du moteur ne prétendent pas démontrer une
impossibilité architecturale universelle.

Revues finales Standards et Spec : aucun défaut bloquant restant dans le bloc
examiné. La validation complète du document est explicitement hors de ce bloc.

## Comparaison reproductible

Référence : `benchmark/runs/3a-provenance-final`.
Candidat final revu : `benchmark/runs/3b-parcel-reviewed`.
Commande :

```powershell
python -m benchmark.compare benchmark/runs/3a-provenance-final benchmark/runs/3b-parcel-reviewed --out benchmark/comparisons/3b-parcel
```

| Mesure sur les mêmes 100 observations | Avant | Après |
|---|---|---|
| Document produit | 100 | 85 |
| Document produit malgré une parcelle impossible | 15 | 0 |
| Refus métier attendus | 0 | 15 |
| Erreurs inattendues | 0 | 0 |
| Plans passant les contrôles géométriques disponibles | 84 | 84 |

Les 15 refus portent sur trois programmes, chacun avec cinq graines. Ils
correspondent tous à `PlanConstraintError/non_positive_usable_envelope` et sont
conservés dans le rapport comme erreurs de traitement, puis qualifiés ici comme
refus attendus ; aucune exception quelconque n'est déclarée succès automatiquement.
**Les 85 documents encore produits et leurs 85 PNG sont strictement identiques**.
Zéro tentative réseau bloquée sur les observations mesurées.

L'amélioration démontrée est le refus des emprises impossibles, pas une hausse
du nombre de plans géométriquement valides ni une amélioration esthétique.
Le défaut « sans garage » et le chevauchement d'ouvertures `dev07/2/0` restent
visibles. Aucun ajustement n'a utilisé les dix cas d'évaluation réservés.

Rapport et planches : [comparaison parcelle](../../benchmark/comparisons/3b-parcel/report.md).
Les latences restent descriptives : ces runs ne constituent pas une campagne
de performances isolée à cinq répétitions.

## Tests et limites

- Suite élargie `services/ai/tests research/metrics benchmark/tests` :
  **718 passed**, 10 warnings, 156,99 s avant l'ultime correction d'alias positif.
- Après les dernières corrections, **26 tests parcelle réussis**, dont alias
  invalides avant NLU, alias positif, grille fine, snap intérieur et HTTP 422.
- Trois tests supplémentaires du runner : restauration de l'environnement,
  connexion bloquée même si avalée, distinction erreur d'évaluateur/génération.
- Ruff et formatage sur les modules nouveaux/réécrits : réussis ; diff sans
  erreur d'espacement. Avertissements environnementaux de dépendances Python
  et dépréciations présents, pas traités par ce bloc.
- Source baseline extraite dans `.cache/3a-baseline-replay` : import depuis
  l'archive et génération d'un studio 7 × 6 m réussis.

À ce stade du journal restaient TASK-006 (contrats complets), TASK-008
(validation finale des ouvertures) et TASK-009 (parité Go/Python).

## Bloc suivant — 23 septembre : document géométrique et ouvertures

Plan avant implémentation :

1. Référence : `benchmark/runs/3b-parcel-reviewed`, complétée par copie locale
   des fichiers Go de validation. Ne pas modifier l'évaluateur du benchmark.
2. Contrat géométrique commun Python/Go : nombres JSON finis sans coercition,
   IDs uniques par collection, murs orthogonaux non dégénérés, points dans
   l'emprise, polygones simples d'aire positive, pas d'intersection intérieure
   des pièces, ouvertures contenues sans chevauchement. Tolérance linéaire
   1e-6 m et aire 1e-6 m². Pièces triangulaires admises, contacts de frontières admis.
3. Figer fixtures JSON communes avec cas valides et invalides et codes d'erreur.
   Les métadonnées `program`/`layout` restent compatibles ; ne pas imposer
   l'ancien enum mobilier devenu obsolète comme condition de validité géométrique.
4. Valider dans `plan_adapt.adapt` et à la frontière `pipeline.build_document`,
   avant aperçu. Distinguer erreur de contrainte utilisateur et sortie invalide
   produite par le moteur. Vérifier les ouvertures avant de placer le mobilier.
5. Pour les fenêtres générées en conflit, conserver le même mur et la même
   pièce et choisir l'intervalle libre le plus proche ; ne déplacer aucune porte.
   Si les minima imposés ne tiennent pas, retourner un diagnostic explicite.
   Ne jamais appliquer cette réparation à un document soumis à la sauvegarde Go.
6. Revues Standards/Spec, fixtures Python/Go, tests de génération/adaptation,
   puis corpus de développement et planches avant/après. Rapporter toute baisse
   de taux de succès ; ne pas assimiler un refus supplémentaire à un meilleur plan.

### Livraison intermédiaire : intervalles des ouvertures

Le bloc est volontairement limité à TASK-008. Les contrats globaux de document
et la parité Go/Python (TASK-006/009) restent ouverts, sans revendication de
validation complète. Aucun changement du canvas, de Gemini ou de la 3D.

- `opening_intervals.py` sépare les vérifications numériques/géométriques des
  heuristiques de placement : références, IDs, nombres finis stricts (y compris
  les résultats calculés), murs orthogonaux non nuls, intervalles contenus et
  absence de chevauchement avec tolérance de 1e-6 m. Le contact exact est admis ;
  cela ne constitue pas une validation constructive des distances entre baies.
- `fit_generated_windows` s'exécute après les minima et avant le mobilier.
  Il conserve les portes, les IDs, les largeurs et le mur ; les fenêtres en
  conflit sont projetées sur l'intervalle libre le plus proche dans la pièce
  d'origine. Une égalité est départagée par l'offset inférieur. Cette stratégie
  gloutonne déterministe ne prétend pas résoudre un placement global optimal.
- La pièce de référence est calculée depuis l'ouverture **avant** élargissement.
  Les spans s'appuient sur les rectangles du moteur actuel ; ils ne sont pas
  un algorithme de desserte pour des pièces concaves arbitraires.
- Les erreurs du générateur sont des `OpeningGeometryError` (RuntimeError),
  traduites en HTTP 500 structuré, pas en contrainte utilisateur 422.
  Une absence de place n'entraîne ni réduction silencieuse ni déplacement de porte.
- Le test de parcelle 1 × 10 m révèle une porte hors mur : ce plan précédemment
  retourné est maintenant refusé. Le test conserve un contrôle de l'emprise
  réellement transmise au placement (1 m) et ne masque pas le nouveau refus.

#### Standards

Deux constats corrigés : association à la pièce après élargissement et place
exacte refusée par arrondi flottant. Revue finale : aucun défaut bloquant relevé.

#### Spec

Deux constats corrigés : changement de pièce et dépassement vers l'infini des
valeurs calculées. Revue finale : aucun écart bloquant supplémentaire relevé.
Le périmètre non livré (contrats globaux/Go) reste explicitement au prochain bloc.

#### Benchmark final du bloc

[Rapport et planches avant/après](../../benchmark/comparisons/3b-openings/report.md).
Run final `3b-openings-reviewed` contre `3b-parcel-reviewed`, évaluateur et
protocole inchangés : 100 observations, 85 retours avant/après, 15 refus de
parcelles impossibles avant/après, validité géométrique **84 → 85**.
84 documents/PNG identiques ; seul `dev07/2/0` déplace la fenêtre de 10 cm,
sans déplacer ni réduire la porte du garage. Aucun gain esthétique revendiqué.

Le premier passage de la suite complète donne 740 réussites et trois échecs
dans des tests de métadonnées d'arrangement. Les fixtures réelles RICH/DIVERSE
contiennent des fenêtres impossibles à déplacer dans leur pièce d'origine.
Les trois tests ciblés sont isolés avec un placement de portes uniquement,
sans désactiver le validateur ; un test réel RICH protège le refus explicite.
Ces tests isolés ne constituent plus une preuve de réussite de bout en bout
sur ces fixtures. Les refus hors corpus restent une limitation documentée,
pas un gain de génération. Aucun choix alternatif de parti n'est implémenté ici.

Couverture complémentaire réelle : RICH sans garage conserve pièces, fenêtres
et arrangement après changement de graine 4 → 9 ; DIVERSE est testé sur douze
graines sans substitution. Onze produisent des ouvertures valides, la graine 7
est explicitement refusée (`window_no_free_span: o4`). Revue Spec finale de ces
ajouts : aucun écart bloquant. Les tests n'utilisent pas les cas réservés.

#### Validation finale

- Suite complète Python/recherche/benchmark : **744 réussites**, 10 warnings,
  168,06 s, avant ajout des treize derniers tests d'intégration.
- Les **13 tests supplémentaires réussissent**, 16,82 s. Ils complètent la suite
  précédente ; aucun changement de code de production entre ces deux passages.
- Ruff sur les modules et tests ciblés : réussi. `git diff --check` : réussi
  (avertissements LF/CRLF sur des fichiers déjà modifiés, sans erreur de diff).
- Les warnings de dépendances/dépréciation existants ne sont pas corrigés ici.
- TASK-008 terminé. TASK-006/009 restent à traiter : contrat complet, frontière
  `pipeline.build_document`, validation Go et fixtures communes. Le sprint 3B
  n'est donc pas terminé ; le design des plans canvas reste au sprint 3C.

## Bloc contrats — plan d'exécution avant code

Référence Python figée : `benchmark/runs/3b-openings-reviewed/source/source.zip`.
Référence Go : `.cache/3b-contracts-before/validate.go` (aucune modification
depuis sa copie), complétée par Git HEAD pour les tests existants.

1. Livrer un profil **structure et intervalles**, première partie de TASK-006/009 :
   en-tête 1.0/m, emprise positive finie, au moins quatre murs orthogonaux non
   nuls, coordonnées dans l'emprise, IDs uniques par collection, pièces avec
   au moins trois points finis et aire non nulle, ouvertures avec contrat TASK-008.
   Métadonnées inconnues conservées ; ouvertures absentes admises, null refusé.
2. Documenter le profil dans `packages/plan-schema/validation-profile.md` et
   ajouter des fixtures JSON communes (document de base + mutations explicites),
   avec code d'erreur attendu pour Python et Go. Ne pas activer l'ancien enum mobilier.
3. Introduire un validateur Python sans dépendance à l'évaluateur de recherche,
   et renforcer `internal/plan/Validate` sans réparation des documents sauvegardés.
   Les erreurs du contrat portent un code stable ; l'adaptateur HTTP Go conserve
   son enveloppe existante `invalid_plan` pour compatibilité.
4. Valider les sorties d'adaptation et de `pipeline.build_document` avant aperçu.
   Une sortie générée invalide est une erreur interne structurée, jamais un 422.
   Mettre les fixtures de tests de pipeline en conformité, sans court-circuiter
   le validateur ; ajouter un test qui interdit l'appel de l'aperçu si invalide.
5. Exécuter fixtures communes, suites Python/Go, revues Standards et Spec,
   puis benchmark comparatif sans modifier l'évaluateur ni les cas réservés.

Ce découpage ne clôt pas le contrat géométrique global : simplicité des polygones,
chevauchement des pièces et fermeture réelle du périmètre restent au bloc suivant.
Un succès du profil n'est donc pas une certification architecturale complète.

### Livraison du profil structure/intervalles

- Contrat explicite : [profil partagé](../../packages/plan-schema/validation-profile.md).
  **51 fixtures communes** contrôlent notamment absence/null, booléens, nombres
  sous forme de chaînes, débordements calculés, IDs dupliqués, triangles inversés,
  limites de murs, contacts entre ouvertures et métadonnées futures.
- Python : `document_validation.py` sépare contrôle de document et placement.
  `PlanDocumentError` expose code/chemin ; `GeneratedDocumentError` distingue
  les erreurs internes de génération des contraintes utilisateur. Les sorties
  de `adapt` et `build_document` sont contrôlées avant aperçu.
- Go : lecture JSON avec `UseNumber`, puis fonctions séparées pour champs,
  structure et ouvertures ; les coordonnées absentes ne deviennent plus zéro.
  L'API existante conserve son enveloppe 400/`invalid_plan` à la sauvegarde.
- Les fixtures de pipeline ont maintenant une géométrie réelle, au lieu de
  documents minimaux invalides. Un test garantit qu'un document final invalide
  ne déclenche aucun aperçu. Pas de validation désactivée pour faire passer les tests.
- Aucun changement de design de Gemini, du canvas ni de la 3D.

#### Standards

La revue indépendante a pu reprendre après une limite d'usage temporaire.
Aucune violation documentée ni heuristique nécessitant correction immédiate
relevée dans le bloc de production. Les contrôles répétés protègent deux frontières
distinctes ; ils ne sont pas assimilés à une duplication inutile.

#### Spec

Aucun écart bloquant relevé pour le profil partiel annoncé. La revue a vérifié
les types stricts, la classification HTTP et l'absence de mutation. Les garanties
géométriques non implémentées restent explicitement hors de ce bloc.

#### Tests et preuves

- Suite complète `services/ai/tests research/metrics benchmark/tests` :
  **806 passed**, 10 warnings, avant ajout des huit derniers cas JSON partagés.
  Durée affichée par pytest : 2443,91 s ; ce temps n'est pas une mesure de performance.
- Après les huit ajouts : **56 tests Python du contrat réussis** et tests Go
  des **51 fixtures** réussis. Aucun code de production modifié entre les passages.
- `go test ./...` : réussi. Test Go optionnel sur le run final : **170 documents
  générés acceptés**, échauffements compris. Activation via `PLAN_BENCHMARK_RUN`
  pointant sur un dossier de run, puis `go test ./internal/plan -run TestGeneratedBenchmarkDocuments -v`.
- Fuzzing Go, 5 s, deux workers : **108 305 exécutions**, aucun panic.
- `go test -race ./internal/plan` **non exécutable ici** : CGO désactivé et aucun
  compilateur C détecté. Ne pas présenter le contrôle de courses comme réussi.
- Ruff ciblé, gofmt et contrôle d'espacement : réussis. Warnings préexistants
  de dépendances Python et fins de ligne Windows non corrigés par ce bloc.
- [Comparaison et analyse des images](../../benchmark/comparisons/3b-contract-profile/report.md) :
  85 retours/15 refus inchangés ; **85 documents et PNG identiques**. Aucune
  tentative réseau. Sources Go supplémentaires archivées dans le run final.

TASK-006 et TASK-009 restent **partiels** : les bases du contrat et la parité
structure/intervalles sont livrées, mais le prochain bloc doit ajouter la
simplicité des polygones, leur disjonction et la couverture du périmètre.
Ne pas cocher ces tâches comme entièrement terminées avant ces contrôles.

Revue finale des ajouts de tests : aucun blocage sur les axes Standards et Spec.
Le test Go optionnel vérifie les fichiers présents, pas la complétude du run ;
cette dernière est contrôlée par la comparaison du benchmark. Les 170 fichiers
incluent les échauffements et ne sont pas 170 observations indépendantes.

## Bloc géométrie — première étape : couverture du périmètre

Plan avant code, en complément de TASK-006/009 :

1. Référence figée : `3b-contract-profile-reviewed` (sources Python et archive Go).
2. Ajouter un contrôle autonome de couverture des quatre côtés du rectangle
   `floor.bounds`, en Python et Go. Utiliser les coordonnées, jamais les IDs.
   Admettre murs inversés, côtés fractionnés et jonctions à 1e-6 m près.
   Fusionner les intervalles triés et refuser tout trou > 1e-6 m, y compris
   aux extrémités. Les portes/fenêtres n'enlèvent pas le segment porteur du mur.
3. Retourner `incomplete_perimeter` sans réparer ni changer le document. Ne pas
   confondre quatre murs quelconques avec un contour fermé. Le contrôle porte
   sur le rectangle d'emprise du format actuel, pas une enveloppe polygonale libre.
4. Étendre les fixtures JSON communes : quatre murs intérieurs, trou central,
   trou de coin, couverture fractionnée/inversée, IDs arbitraires et tolérance.
5. Revues Standards/Spec, suites Python/Go et benchmark 100 observations contre
   la référence. Vérifier l'identité des documents/PNG encore acceptés.

La simplicité des polygones et les intersections de pièces suivront dans une
étape distincte ; ce premier contrôle ne clôt pas TASK-006/009 ni le sprint 3B.

### Implémentation du contrôle de périmètre

- `perimeter_validation.py` et `validation_perimeter.go` projettent les murs
  prévalidés sur les quatre côtés, trient les intervalles et conservent la
  couverture maximale. Ils refusent `incomplete_perimeter` dès qu'un côté a
  un trou supérieur à 1e-6 m. Coût O(n log n), sans modification du document.
- Le contrôle utilise les deux extrémités et ne dépend ni des IDs ni du sens
  des murs. Les portes/fenêtres restent portées par leurs segments de mur.
- Le profil passe à v1.1. Les **63 fixtures communes** incluent douze nouveaux
  cas de périmètre ; sept cas unitaires supplémentaires dans chaque langage
  testent directement la couverture d'intervalles, notamment les trous multiples.
- Premier passage ciblé : **75 tests Python réussis**, tests Go `internal/plan`
  réussis. Les suites complètes et le benchmark sont contrôlés séparément.

#### Standards

Aucun défaut concret ni violation de standard relevé. Le tri Go porte sur
des projections locales ; un intervalle imbriqué ne réduit pas la couverture.

#### Spec

Aucun écart bloquant relevé pour le contrôle de périmètre. Les extrémités,
fractionnements, orientations et tolérances correspondent au profil annoncé.
Les polygones simples et la disjonction des pièces restent au bloc suivant.

## Bloc géométrie — deuxième étape : polygones et pièces

Plan avant code, après le contrôle de périmètre :

1. Référence : `benchmark/runs/3b-perimeter` et archive Go associée ; conserver
   l'évaluateur Shapely indépendant du moteur. Ne pas modifier les dix cas réservés.
2. Ajouter en Python et Go une validation des polygones de pièces : fermer
   implicitement le contour, admettre un dernier point identique au premier,
   refuser arêtes nulles, sommet répété ailleurs, retour collinéaire et
   intersection de deux arêtes non adjacentes (contact inclus). Triangles,
   orientations horaires/antihoraires et sommets collinéaires sans retour admis.
   Tolérance linéaire 1e-6 m, aire 1e-6 m².
3. Calculer l'aire d'intersection de chaque paire de pièces simples par bandes
   horizontales, découpées aux ordonnées des sommets et des intersections
   d'arêtes. Dans chaque bande, la largeur d'intersection est linéaire ;
   l'intégrale midpoint × hauteur donne l'aire. Refuser si aire > 1e-6 m² ;
   contact de frontières et partage d'un mur restent permis.
4. Ajouter `overlapping_rooms` et les cas communs de polygone croisé, concave,
   pièce contenue, pièces identiques, contact seul et chevauchement étroit.
   Comparer les décisions sur exemples aléatoires à l'évaluateur Shapely du
   benchmark, sans l'importer dans l'application.
5. Revue Standards/Spec, tests des deux langages, run des 100 observations,
   inspection des planches et rapport des refus nouveaux. Un document refusé
   n'est jamais compté comme amélioration esthétique ou plan réussi.

### Implémentation des polygones et de la disjonction

- `polygon_validation.py` et `validation_polygons.go` vérifient les arêtes,
  les sommets répétés, les retours collinéaires et les croisements de chaque
  contour. La fermeture du contour est implicite ; un dernier sommet répété
  pour marquer la fermeture est accepté sans modifier le document reçu.
- L'aire d'intersection de deux pièces simples est intégrée sur des bandes
  horizontales découpées aux sommets et aux croisements d'arêtes. Les bords
  communs sont admis ; une aire intérieure > 1e-6 m² est refusée avec
  `overlapping_rooms`. Les 150 comparaisons différentielles GEOS comprennent
  rectangles, pièces en L et triangles obliques.
- Un cas de revue révélait que deux arêtes d'environ 1 mm croisées passaient
  sous le seuil d'aire. La correction teste le signe strict d'un croisement
  propre et réserve la tolérance linéaire aux contacts quasi collinéaires.
  Le cas est désormais dans les fixtures JSON communes.
- Le contrôle sur un document soumis est limité à **64 pièces**, **64 sommets
  par pièce** et **256 sommets au total**, avec erreur
  `geometry_complexity_limit`. Ce plafond borne le coût du calcul ; il décrit
  une capacité du MVP et non une contrainte architecturale.
- Le profil passe à v1.2. **233 tests ciblés Python** (contrat et comparaison
  GEOS) et `go test ./internal/plan` réussis après les corrections. Les suites
  complètes et le benchmark avant/après tournent séparément.

#### Standards

La revue a identifié une complexité non bornée malgré la limite HTTP de 4 Mio.
Les plafonds communs ci-dessus corrigent ce risque avant le calcul des
intersections. Aucun autre constat de style bloquant dans le premier passage.

#### Spec

La revue a fourni le contre-exemple des arêtes courtes croisées. Les deux
implémentations et la fixture partagée ont été corrigées. La revue ultérieure
a aussi trouvé un angle obtus court valide faussement rejeté ; voir ci-dessous.

#### Micro-étape de revue : angle court valide

Avant la correction : ajouter au contrat partagé un contour valide avec un
angle obtus de 0,1 mm, puis remplacer le seuil d'aire absolu du test de retour
collinéaire par une distance normalisée sur les longueurs adjacentes, dans les
deux langages. Vérifier le cas de retour exact, le nouveau cas valide, les
suites complètes et la comparaison du benchmark sur la version corrigée.

Le seuil est maintenant `1e-6 m × max(longueurs des deux arêtes)` au lieu de
`1e-6 m²` : l'angle obtus valide de la revue et le retour collinéaire sont
respectivement acceptés/refusés par les deux implémentations. La fixture commune
fait partie des **234 tests ciblés Python réussis** ; `go test ./internal/plan`
réussit également. Les suites et la comparaison finales suivent ci-dessous.

## Recette finale du sprint 3B

- Le contrat commun contient **76 fixtures** : Python et Go comparent les mêmes
  décisions et codes. Le profil v1.2 contrôle structure, limites, périmètre,
  ouvertures, polygones simples et disjonction des intérieurs. Les revues
  Standards/Spec après le dernier correctif n'ont relevé aucun blocage.
- Tests sur la version finale : **970** tests `services/ai/tests research/metrics`,
  **29** tests `benchmark/tests` (soit 999), et `go test ./...` réussis. Ruff
  ciblé et `git diff --check` réussis. Les 150 cas différentiels GEOS incluent
  rectangles, L concaves et triangles obliques. Les 10 avertissements Python
  concernent dépendances/dépréciations déjà présentes, pas des échecs.
- Benchmark final archivé : `benchmark/runs/3b-polygons-final` (source Python,
  patch local, manifeste et archive Go `go-validation-source.zip`, SHA-256 de
  cette dernière `F58DA88E083FB88943D6BC022CE4D00E8AC9170A11FDC8E714D276A65DEA5A50`).
  Le validateur Go a accepté les **170 documents générés**, échauffements
  compris. Les 100 observations mesurées donnent **85 plans valides / 15 refus
  attendus**, exactement comme la référence `3b-perimeter` ; les **85 JSON et
  PNG acceptés sont identiques**, aucun nouveau refus. La planche et les PNG
  `dev01/0/0`, `dev14/0/0` ont été inspectés. Voir
  [rapport apparié](../../benchmark/comparisons/3b-polygons-final/report.md).
- La latence de ce run à une répétition n'est pas une preuve d'accélération :
  d'autres tests locaux tournaient simultanément. Aucun gain esthétique
  attribué à cette validation ; le canvas et Gemini ne sont pas mesurés ici.

Le sprint 3B satisfait ses contrats définis ; il ne certifie pas la
constructibilité. Restent hors profil : relation exacte murs/pièces, validité
du mobilier, circulation et réglementation. Le sprint 3C doit reprendre
séparément la fidélité graphique et interactive de l'éditeur, pas le rendu Gemini.
