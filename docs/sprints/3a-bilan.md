# Sprint 3A — construction de la référence expérimentale

État : livré pour le protocole local de caractérisation. Périmètre : TASK-001 à TASK-005 du plan MVP 2D.
Précision utilisateur : la refonte de design vise uniquement le plan du canvas
éditeur ; la branche Gemini est évaluée pour sa fidélité.

## Blocs et critères de fin

1. Corpus et archive : 20 cas développement, 10 réservés, quatre impossibles,
   programme attendu annoté séparément du parseur ; archive des sources utiles
   avec SHA-256 avant modification applicative.
2. Exécution et métriques : modules `benchmark/artifacts.py`, `benchmark/run.py`,
   `research/metrics/geometry.py`; local strict, seeds 0–4, erreurs conservées,
   évaluateur indépendant du placement. Géométrie via Shapely, dépendance benchmark
   seulement, sans ajout au serveur produit.
3. Comparaison : `benchmark/compare.py`, appariement case/seed/repeat et contrôle
   des hashes d'entrée/configuration/corpus/évaluateur, planches PNG et rapport.
4. Provenance : mesurer backend réellement exécuté, repli et tentatives, sans
   casser les retours publics existants ; tests simulés des chemins externes.
5. Vérification : fixtures invalides, identité/identité, mismatch explicite,
   baseline de développement, inspection images et bilan des limites.

Chaque bloc est revu sur les axes Standards/Spec avant passage au suivant.
La référence de revue est l'état local au début du bloc, et non tous les changements
antérieurs du checkout. Aucun cas réservé n'est exécuté pendant ce sprint.

## Livré et exécuté

- Corpus synthétique de 30 programmes, dont 20 de développement et 10 réservés.
  Les attentes sont distinctes du parseur ; le cas ambigu reste sans score de programme.
- `benchmark/run.py` fige la source Python locale, bloque les connexions réseau,
  enregistre les erreurs et capture la pipeline finale avec une graine effective vérifiée.
- `research/metrics/geometry.py` utilise Shapely comme évaluateur indépendant :
  polygones, emprise, chevauchements, murs, ouvertures et programme par type.
- `benchmark/compare.py` refuse les entrées incompatibles ou artefacts altérés,
  conserve tous les cas, affiche toute paire modifiée et produit rapport/planche.
- Provenance ajoutée sans modifier les champs historiques : moteur de rendu réel,
  raffinement réellement exécuté, modèle configuré/demandé, modèles par tentative,
  invocation et POST de génération. Le modèle réellement servi et les téléchargements
  HTTP restent non mesurés (`null`), sans valeur inventée.

## Résultats

Exécutions : `benchmark/runs/3a-baseline` et `3a-provenance-final`, chacune avec
20 programmes × 5 graines × 1 répétition mesurée, plus un échauffement par paire.
Le hash du corpus, de l'évaluateur et du runner est identique entre les bras.

- **100/100 documents identiques et 100/100 PNG identiques** après ajout de provenance.
- Comparaison identité/identité : aucun delta qualitatif ; les tests détectent
  aussi un document modifié, une image altérée et un échantillon manquant.
- Baseline : 84/100 documents passent les contrôles géométriques implémentés.
  Quinze sorties correspondent aux trois parcelles impossibles ; une sortie
  (`dev07/2/0`) contient un chevauchement d'ouvertures.
- Programme : 90 correspondances sur 95 observations annotées ; le programme
  « sans garage » échoue pour les cinq graines. Cinq observations du brief ambigu
  ne sont pas notées.

Ces proportions concernent 20 programmes corrélés par graines, pas 100 programmes
indépendants. Elles ne constituent pas une estimation de performance générale.
Les temps de cette campagne ne démontrent aucun gain : une répétition mesurée et
des tests exécutés en parallèle ne permettent pas d'isoler un effet de latence.

## Inspection des images

Inspection assistée de `dev02/0/0` et `dev06/0/0` et vérification d'identité
des PNG de toutes les paires. Le plan avec garage conserve pièces et mobilier.
Le plan impossible montre des espaces fortement comprimés : l'image ne suffit
pas à rendre cette sortie acceptable. Les images sont celles du rendu Pillow,
pas des captures du canvas ; aucune refonte graphique n'a été réalisée ici.

Rapports : [provenance](../../benchmark/comparisons/3a-provenance-final/report.md)
et [contrôle identité](../../benchmark/comparisons/3a-identity/report.md).

## Revues et vérifications

Standards : corrections du comptage réseau, de la reproduction sans Git et de
la distinction erreur de génération/évaluation. Spec : contrôle des hashes réels,
couverture des variantes modifiées dans les planches et précision des compteurs
de génération distincts des téléchargements. Les tests de restauration de
l'environnement et de tentative réseau avalée passent.

Tests du benchmark : 26 réussis, puis 3 tests supplémentaires d'isolation réussis.
Intégration pipeline/Together/Eden/provenance : 89 réussis avant les deux précisions
de métadonnées ; 8 tests provenance rejoués après celles-ci réussissent.
Les vérifications élargies communes avec le sprint 3B sont consignées dans son bilan.

## Limites conservées

Le corpus attend une validation architecturale externe. Les surfaces uniquement
implicites ne sont pas inventées comme vérités terrain. Pas de capture navigateur,
d'évaluation Gemini réelle ni de score d'accessibilité/mobilier dans ce bloc.
Le manifeste ne redistribue pas les polices système. Les scripts historiques
d'ablation GAN ne sont pas remplacés ni présentés comme validation du produit.
