# Vérification du manuscrit « De l’image plausible au plan vérifiable »

Date : 29 septembre 2026. Document contrôlé : [version conservée avant révision](ia-plans-verifiables-avant-revision-20260930.md).

Cette fiche est historique. Pour les nouvelles expériences et le manuscrit du 30 septembre, consulter le [bilan de révision](../sprints/article-evaluation-2.md) et le [suivi des remarques](suivi-revision-20260930.md).

## Périmètre et provenance

L'article est une étude méthodologique avec résultats descriptifs issus des archives du projet. Le système est présenté au présent. Aucune expérience nouvelle avec Gemini, aucun entraînement de modèle, aucune enquête auprès d'architectes et aucune certification constructive ne sont prétendus.

Le checkout comporte des travaux applicatifs préexistants non finalisés. Ils n'ont pas été modifiés pendant cette tâche documentaire et ne sont pas utilisés comme preuves de résultats. Le HEAD observé est `e4bdd740fbd064298c1534b0ee5b888477a50677`, mais les sources archivées avec chaque benchmark, et non ce seul identifiant, définissent les versions étudiées.

## Contrôles des mesures

Les compteurs ont été recalculés à partir des `results.json` des dossiers de référence et candidat indiqués dans les résumés, en excluant les lignes `warmup=true`.

| Archive / état | Mesures | Programmes | Retours | Géométrie valide | Programme mesuré | Programme respecté | Sorties sur parcelle impossible |
|---|---:|---:|---:|---:|---:|---:|---:|
| `3b-parcel`, référence | 100 | 20 | 100 | 84 | 95 | 90 | 15 |
| `3b-parcel`, candidat | 100 | 20 | 85 | 84 | 80 | 75 | 0 |
| `3b-openings`, référence | 100 | 20 | 85 | 84 | 80 | 75 | 0 |
| `3b-openings`, candidat | 100 | 20 | 85 | 85 | 80 | 75 | 0 |
| `3b-polygons-final`, référence | 100 | 20 | 85 | 85 | 80 | 75 | 0 |
| `3b-polygons-final`, candidat | 100 | 20 | 85 | 85 | 80 | 75 | 0 |

- Les trois programmes refusés sont `dev06`, `dev19` et `dev20`, chacun décliné sur cinq graines. Les exceptions sont des `PlanConstraintError` et le motif attendu est `non_positive_usable_envelope`.
- `dev07` échoue au contrôle du programme sur ses cinq graines. `dev17` n'a pas d'annotation exploitable de programme ; ses cinq sorties sont exclues de ce seul dénominateur.
- Les 100 observations mesurées de chaque état ne comportent aucun appel externe. Le manifeste fixe notamment `TOGETHER_NLU=0`, `TOGETHER_PLANNER=0` et `IMAGE_BACKEND=procedural`.
- La correction d'ouverture concerne `dev07/2/0` : déplacement de 0,10 m de la fenêtre, largeur conservée ; 84 autres documents et images identiques.
- Les manifestes de l'éditeur confirment 38 paires, 38 empreintes documentaires identiques et 38 images modifiées. Ces paires représentent six documents, et non 38 programmes indépendants.

## Vérification mathématique

| Équations | Nature et vérification |
|---|---|
| (1) | Contraintes géométriques idéales, unités longueur/aire distinguées, contact de frontière admis. |
| (2) | Formule de l'aire pour polygone simple ; contrôle d'un rectangle 4 × 3 dans les deux sens : 12 m². |
| (3) | Retrait uniforme sur rectangle : 10 × 8 avec retrait 1 donne 8 × 6 ; largeur 2 avec retrait 1 donne zéro. Condition nécessaire, non suffisante pour le programme. |
| (4) | Interpolation affine sur mur orienté ; exemple de mur inversé : (8, 0) et (7,1, 0). |
| (5) | Intersection d'intervalles : 0,10000000000000009 m avant, zéro après (arrondi flottant expliqué par l'arithmétique). |
| (6)–(7) | Définitions d'un cadre idéal de sélection, distinguées explicitement de l'implémentation qui valide le document complet après sélection et adaptation. |
| (8) | Démonstration par inclusion d'événements ; acceptation de probabilité positive et correction du validateur explicitement requises. |
| (9)–(11) | Dénominateurs explicités, variables fixées conventionnellement pour refus, absence d'annotation traitée comme mesure non disponible. Identité risque–couverture vérifiée symboliquement. |
| (12) | Cibles positives et appariement requis. Exemple : (0 + 1/9 + 2/20)/3 = 0,07037037037037037. |
| (13) | IoU définie sur masques comparables d'union non vide ; absence de garantie de segmentation à partir des seuls pixels sombres. |
| (14)–(15) | Moyenne appariée et rééchantillonnage des programmes ; aucune indépendance artificielle entre graines. |
| (16) | Racines du polynôme de score de Wilson vérifiées par SymPy 1.13.1 : deux résidus symboliques nuls. Exemple 15/20 : [0,5312991206 ; 0,8881382993]. |
| (17) | Borne binomiale unilatérale pour zéro erreur, dérivée de (1-p)^n = alpha ; n=20 et alpha=0,05 donnent 0,1391083407. Exemple pédagogique distinct du corpus. |

Contrôles numériques complémentaires : 200 substitutions dans le polynôme de Wilson et 100 vérifications de l'identité de rendement ont réussi avec tolérance absolue de 1e-10. Ils contrôlent les calculs exposés et ne prouvent pas les hypothèses de validité d'une inférence statistique.

Le gain de validité conditionnelle est 100/85 = 1,176470588 point ; le gain de rendement global est 1 point. La variation des sommes médianes de durées de couche vaut 100 × (357,25 / 352,75 - 1) = 1,275690999 %. Elle n'est pas présentée comme un temps par frame ou un effet causal.

## Sources bibliographiques

Les pages primaires des auteurs ou des éditeurs de House-GAN, Graph2Plan, HouseDiffusion, Tell2Design et de la classification sélective ont été consultées. Les métadonnées Efron ont été recoupées avec l'éditeur et le catalogue de Stanford ; la formulation de Wilson a été vérifiée dans le [manuel statistique NIST](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). La documentation Gemini sert uniquement à qualifier ses modalités d'entrée et de sortie.

Les références sont paraphrasées et reliées aux assertions pertinentes. Les résultats du projet possèdent des références distinctes P1 à P6 afin de ne pas attribuer aux publications externes des mesures réalisées localement.

## Revue à deux axes

Le mécanisme du skill [code-review](../../.agents/skills/code-review/SKILL.md) a été adapté à un nouveau document : référence avant ajout = fichier absent ; spécification = [plan du sprint](../../plan/process-article-scientifique-1.md). Il n'y a pas de diff de nouveaux commits à prétendre examiner ni de règles de style applicatif à appliquer artificiellement à la prose.

### Standards scientifiques

Deux constats corrigés : séparation entre formulation idéale et sélection implémentée ; domaine de définition complet du rendement combiné. La relecture de correction confirme **zéro constat non résolu** sur cet axe.

### Spec

Un constat corrigé : la borne nécessaire sur la somme des surfaces autorise l'égalité. Le manuscrit remplace la comparaison stricte par une inégalité large et distingue la réserve éventuelle pour murs et circulation. La relecture de correction confirme **zéro constat non résolu** sur cet axe.

## Forme du document

Le manuscrit comporte 17 équations numérotées consécutivement, 34 délimiteurs de mathématiques affichées, neuf références bibliographiques, six groupes de preuves locales et 14 unités séparées par des sauts de page HTML. Son corps dépasse 7 700 mots hors formules affichées, blocs de code et URL. Les sauts donnent une pagination minimale aux moteurs HTML compatibles ; un lecteur Markdown qui les ignore affiche un document continu. Aucun nombre de pages PDF n'est prétendu, puisqu'aucun PDF n'est demandé ou produit.

Les liens locaux ont été vérifiés. Les preuves sont archivées : cette tâche n'a pas relancé la génération ni modifié les résultats historiques.
