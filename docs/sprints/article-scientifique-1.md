# Sprint documentaire — article scientifique A-AI

Date : 29 septembre 2026.

Statut : terminé. Revues finales Standards / Spec : 0 / 0 constat non résolu.

## Objectif

Produire un article français long, accessible et de niveau doctoral sur l'IA et les statistiques appliquées aux plans architecturaux. Sujet retenu : **De l'image plausible au plan vérifiable : une IA hybride pour la conception architecturale**.

## Livrables

- [Manuscrit](../articles/ia-plans-verifiables.md) : structure académique, 17 équations, cadre de validation, protocole statistique, résultats documentés, discussion et références.
- [Note de vérification](../articles/verification-ia-plans-verifiables.md) : recalcul des mesures, contrôles mathématiques et revues.
- [Plan exécuté](../../plan/process-article-scientifique-1.md).

## Étapes réalisées

1. Analyse de la pipeline actuelle et sélection des archives de benchmark utilisables.
2. Vérification des références scientifiques originales et de la documentation statistique.
3. Rédaction au présent du système, avec séparation des résultats mesurés et du protocole complémentaire.
4. Contrôle des dénominateurs et recalcul des compteurs sur les observations hors échauffement.
5. Vérification symbolique et numérique des formules ; contrôle des unités et conditions de définition.
6. Double relecture indépendante selon le mécanisme `code-review`, corrections et contrôle de longueur/liens.

## Choix scientifiques

La contribution porte sur la fiabilité d'une chaîne hybride et la qualité de son évaluation. Les contrôles du dépôt ne démontrent pas une supériorité de Gemini ou d'un GAN : le manuscrit ne leur attribue pas de résultats inexistants. Le système est présenté comme constitué, avec ses limites de domaine et ses propriétés vérifiées.

Les résultats sont fondés sur vingt programmes de développement, cinq graines et les archives existantes. Les variantes ne sont pas traitées comme des programmes indépendants. Le volume dépasse la demande de huit pages ; le fichier Markdown conserve une pagination HTML explicite pour les outils qui la prennent en charge.

Le sprint logiciel de sémantique des portes reste distinct de ce sprint documentaire. Ses modifications ont été conservées sans reprise de l'implémentation pendant la rédaction.
