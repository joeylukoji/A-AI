# Suivi de révision de l'article — 30 septembre 2026

Sources : version récente du DOCX fourni par l'utilisateur et pré-évaluation jointe. Le DOCX original n'est pas modifié. [Ancien Markdown conservé](ia-plans-verifiables-avant-revision-20260930.md) ; [manuscrit révisé](ia-plans-verifiables.md). La sortie demandée est un Markdown, pas une nouvelle composition Word/PDF.

## Corrections appliquées et réserves

| Remarque | Traitement | Preuve ou limite |
|---|---|---|
| Deux articles empilés, phrases de conversation et dates divergentes | Une version, un résumé, onze sections, une bibliographie ; retrait des messages de conversation | Manuscrit daté du 30 septembre 2026 |
| Figures remplacées par du texte | Schéma SVG original et image historique G004 avec demande et provenance | Figure 1 inspectée après rendu ; figure 2 hors scores |
| Formules brutes ou tronquées | Équations Markdown/LaTeX réécrites et calculs vérifiés | 17 équations numérotées ; conversion Word/PDF non livrée |
| Pas de composant appris mesuré | 60 tentatives LLM réelles, 59 réponses ; comparaison locale/direct/intégré | Compréhension uniquement, pas géométrie bout en bout |
| Jeu d'évaluation non exécuté | 10 programmes × 5 graines × 3 variantes = 150 observations | Pas de réglage du générateur après lecture de ces résultats ; corpus déjà visible |
| Absence d'ablations | Retrait des deux validations finales et désactivation des variantes | Aucune amélioration de rendement constatée ; ne pas prétendre équivalence générale |
| Ablation de faisabilité demandée | Analyse de l'archive avant/après existante | Pas une nouvelle ablation randomisée ; on ne réimplémente pas approximativement un ancien moteur |
| Paradoxe « sans garage » | Explication explicite de dev07, échec local aussi sur eval07 | Géométrie valide ≠ besoin respecté |
| Rendement combiné absent | 75/95 historique ; 40/50 évaluation ; refus conservés | Ne pas confondre avec 75/80 et 40/45 conditionnels |
| Statistiques décoratives | Wilson au niveau programme et bootstrap apparié exécutés | Corpus petit, choisi par les auteurs ; interprétation descriptive |
| Diversité non mesurée | Signature des contours typés, au centimètre ; 13 contre 9 dispositions distinctes comptées par programme | Ni diversité fonctionnelle ni mesure esthétique |
| Mini-benchmark sémantique trop ambitieux | Décomposition présentée comme protocole | Effectifs exacts mesurés ; relations et minimums non évalués |
| Proposition triviale | Propriété conditionnelle raccourcie | Pas de théorème original d'apprentissage revendiqué |
| Boucle éditeur sans validation | Flèche de sauvegarde vers validateur Go et correction | Ne pas affirmer que chaque geste local est validé instantanément |
| Emprise placée trop tôt dans le schéma | Contrôle représenté dans l'adaptation, après document initial | Représentation fidèle au logiciel, pas copie de l'ordre suggéré par le relecteur |
| Provenance et échelle des images | Remplacement de G004 par G005, G007, G010, G013 et G015 avec leurs prompts exacts | Pas de barre d'échelle inventée sur des illustrations non recalées ; sélection illustrative, hors métriques |
| Originalité exagérée | Tableau des mécanismes de huit systèmes et discussion des proximités | Pas de supériorité revendiquée sans expérience commune |
| Mesure de temps fragile | Texte ramené à deux phrases | Écart de 1,28 % non interprété comme gain |
| Noms « diffusion » et « GAN » trompeurs | Tableau nom logiciel / mécanisme actif | Modules de production non renommés pendant l'expérience |
| Bibliographie incohérente | Liste unique de 18 références ciblées et sources primaires | Références redondantes/non mobilisées retirées ; aucune conservation mécanique des 29 notices |
| Données et code non publics | Chemins locaux précis, sources archivées et empreintes | Publication, tag et DOI restent à faire avec autorisation ; un HEAD seul ne décrit pas les modifications locales |
| Auteurs/affiliation absents | Déclaration d'assistance IA explicite | Identité, contributions, financement et conflits à confirmer par les auteurs ; pas d'inférence depuis les métadonnées Word |
| Modèle spécialisé demandé | HouseDiffusion retenu et protocole de comparaison géométrique établi | Comparaison statistique non exécutée : graphe commun, données autorisées et évaluateur partagé restent à fixer |
| Smoke test HouseDiffusion | Poids `model250000.pt` chargés ; trois sorties locales générées et inspectées | Fonctionnement démontré ; ce smoke test ne remplace pas la comparaison équitable |
| Écart découvert pendant les contrôles | Audit post hoc du schéma publié, séparé des scores géométriques | 0/135 documents conformes à cause du catalogue mobilier ; données conservées, constat publié en section 8.6 |

## Bibliographie

Les notices prioritaires ont été rapprochées des pages des auteurs, actes, arXiv versionné ou sites des éditeurs. La référence SPRING pointe vers l'article complet d'Artificial Intelligence ; FlairGPT vers sa publication ; Design-MLLM vers la version 3 consultée. La référence Transformer est celle de Vaswani et al. (2017). Le NIST est cité comme auteur institutionnel avec une date de consultation, pas avec une date de publication arbitraire. Les références classiques Wilson/Efron sont conservées ; la formule de Wilson est également vérifiée dans le manuel NIST. L'accès à un DOI ne garantit pas que toutes ses pages seront accessibles au lecteur sans abonnement.

## Avant soumission

La correction du Markdown n'est pas une validation éditoriale d'un PDF. Il reste à renseigner les auteurs, composer et inspecter le fichier de soumission, publier les artefacts autorisés et exécuter la comparaison géométrique spécialisée. Il faut garder les expériences non exécutées comme telles, même dans une présentation du projet abouti.
