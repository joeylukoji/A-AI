---
title: "De l’image plausible au plan vérifiable : une IA hybride pour la conception architecturale"
subtitle: "Formalisation géométrique, décision avec rejet et évaluation statistique du système A-AI"
language: fr
date: 2026-09-29
document_type: article scientifique méthodologique avec étude de cas
keywords: [intelligence artificielle hybride, génération sous contraintes, architecture, fiabilité, statistiques appliquées, reproductibilité]
---

# De l’image plausible au plan vérifiable : une IA hybride pour la conception architecturale

## Formalisation géométrique, décision avec rejet et évaluation statistique du système A-AI

**Version du manuscrit :** 29 septembre 2026. **Domaine :** intelligence artificielle et statistiques appliquées à la conception architecturale 2D.

## Résumé

La génération automatique de plans architecturaux confronte l’intelligence artificielle à une difficulté fondamentale : une image convaincante peut représenter une solution géométriquement incorrecte ou contraire au besoin exprimé. Cet article présente A-AI, un système hybride qui articule interprétation du langage naturel, construction de configurations spatiales, validation géométrique et restitution graphique à partir d’un document vectoriel commun. Sa question centrale est simple : comment utiliser la souplesse des modèles génératifs tout en rendant leurs productions mesurables, modifiables et vérifiables ? Nous formalisons la distinction entre validité géométrique, conformité au programme, qualité fonctionnelle et fidélité visuelle. Nous établissons une propriété conditionnelle de non-livraison des documents qui échouent à un contrat géométrique correctement implémenté, puis relions cette propriété à une évaluation conjointe du risque et de la couverture. L’étude de cas exploite des archives reproductibles portant sur vingt programmes synthétiques de développement, exécutés avec cinq graines. Le contrôle de faisabilité supprime la livraison des quinze exécutions associées à trois parcelles impossibles. Une correction de placement d’ouverture porte ensuite le nombre de documents géométriquement valides de 84 à 85 parmi 85 documents retournés. Cependant, le programme demandé n’est respecté que dans 75 des 80 retours disposant d’une annotation de programme exploitable. Ces résultats montrent l’utilité d’une vérification explicite et sa limite : la validité géométrique ne suffit pas à établir la justesse sémantique. L’apport est un cadre d’ingénierie et d’évaluation de l’IA générative sous contraintes, accompagné de résultats locaux auditables ; aucune supériorité générale sur les modèles de recherche ni validation constructive n’est revendiquée.

**Mots-clés :** IA hybride ; plans architecturaux ; génération sous contraintes ; document canonique ; décision avec rejet ; évaluation appariée ; bootstrap par programme.

> **Convention de lecture.** Le système est décrit au présent, comme un ensemble fonctionnel constitué. Les résultats numériques sont exclusivement ceux des expériences archivées. Les évaluations externes définies dans le protocole sont identifiées comme telles. Les formules expriment soit des définitions, soit des propriétés assorties d’hypothèses explicites. Le Markdown comporte des sauts de page HTML pour une composition longue ; la pagination finale dépend du moteur de mise en page.

<div style="page-break-after: always; break-after: page;"></div>

## 1. Introduction

### 1.1. Une image de plan n’est pas encore une solution architecturale

Un plan de logement peut sembler immédiatement crédible : des murs sombres, des pièces nommées, des portes dessinées avec leur arc et un mobilier réaliste suffisent souvent à donner une impression de maîtrise. Pourtant, cette apparence ne permet pas de conclure qu’une chambre est accessible, qu’une fenêtre tient dans son mur ou que la maison respecte les dimensions utiles de la parcelle. L’architecture combine des relations spatiales, des quantités physiques et des usages humains. Ces éléments ne se réduisent pas à la ressemblance avec des images d’entraînement.

L’enjeu est particulièrement sensible lorsqu’un utilisateur formule un besoin en langage naturel. Une demande telle que « une maison de trois chambres sans garage » contient des contraintes positives et négatives. Le système doit comprendre les pièces voulues, préserver l’absence du garage, construire une disposition compatible avec l’emprise, puis restituer cette disposition sans introduire d’éléments contradictoires. Une erreur peut apparaître à chacune de ces étapes. Une amélioration de la qualité graphique peut même rendre cette erreur moins visible, parce qu’une représentation plus soignée inspire davantage confiance.

Les travaux de génération architecturale ont déjà montré l’intérêt des graphes, des représentations vectorielles et du conditionnement linguistique. Ils motivent la construction de systèmes qui relient l’intention aux relations spatiales [R1–R4]. Notre étude porte sur un problème complémentaire : organiser la chaîne complète pour savoir précisément ce qui est généré, ce qui est vérifié et ce qui peut effectivement être affirmé au sujet du résultat.

### 1.2. Question de recherche et idée directrice

La question étudiée est la suivante : **une architecture hybride fondée sur un document géométrique commun permet-elle de réduire les résultats invalides livrés, tout en conservant une mesure honnête du respect du besoin et de la diversité des solutions ?**

L’idée directrice consiste à donner des fonctions distinctes aux composants. Un modèle de langage interprète une demande ou propose un arrangement. Un moteur géométrique matérialise les pièces, les murs et les ouvertures. Un validateur contrôle des propriétés explicites. Un moteur de rendu produit une représentation du document validé. Un générateur d’images, tel que Gemini, intervient comme composant de présentation conditionnée. La décision de considérer un plan comme exploitable ne repose donc pas sur l’impression produite par son image.

Cette organisation ne suppose pas qu’un algorithme symbolique soit toujours supérieur à un réseau neuronal. Elle distingue des tâches qui demandent des garanties différentes. L’interprétation accepte l’ambiguïté du langage ; une distance physique possède une unité ; l’intersection de deux pièces se calcule ; la préférence esthétique relève d’une observation humaine. Mélanger ces niveaux dans un score unique rendrait les erreurs difficiles à localiser et les gains difficiles à attribuer.

### 1.3. Contributions et périmètre

L’article développe quatre contributions liées. La première est une formalisation du plan comme document canonique, partagé entre génération, édition et présentation. La deuxième est une formulation de la validation comme décision d’acceptation ou de rejet, assortie d’une garantie limitée aux propriétés effectivement contrôlées. La troisième est une méthodologie statistique qui prend le programme architectural, et non chaque image ou chaque graine, comme unité principale de comparaison. La quatrième est une étude de cas documentée montrant à la fois la suppression d’erreurs géométriques et la persistance d’une erreur de compréhension du programme.

L’originalité défendue se situe dans l’articulation de ces éléments au sein d’une chaîne traçable. Les notions de validation, de bootstrap et de décision avec rejet sont établies ; nous ne les présentons pas comme des inventions. Leur application fournit ici un cadre pour analyser une application d’IA architecturale sans confondre démonstration logicielle, performance d’un modèle et validité professionnelle.

Le périmètre est la conception préliminaire de plans résidentiels en deux dimensions, principalement orthogonaux. La stabilité structurelle, la simulation énergétique, la conformité à une réglementation locale et les représentations 3D ne font pas partie des résultats étudiés. Cette délimitation permet de traiter rigoureusement un problème précis : produire un objet spatial cohérent et analyser les limites de la confiance qu’on peut lui accorder.

<div style="page-break-after: always; break-after: page;"></div>

## 2. Travaux connexes et positionnement scientifique

### 2.1. Génération architecturale structurée

House-GAN représente les contraintes de nombre, de type et d’adjacence des pièces par un graphe et génère des configurations de pièces avec une architecture adversariale relationnelle. Son intérêt pour notre étude est de rendre les relations spatiales explicites et de distinguer réalisme, diversité et compatibilité au graphe [R1]. Cette séparation rappelle qu’une seule dimension de qualité ne décrit pas complètement un plan. [Article original de Nauata et al.](https://arxiv.org/abs/2003.06988)

Graph2Plan combine un graphe de disposition et une enveloppe de bâtiment pour construire un plan. Le cadre autorise des contraintes fournies par l’utilisateur et relie les représentations de graphe, de raster et de boîtes de pièces [R2]. Il illustre l’importance de l’interface entre intention et géométrie. A-AI retient cette question d’interface, sans prétendre reproduire l’architecture neuronale ni les performances de Graph2Plan. [Article original de Hu et al.](https://arxiv.org/abs/2004.13204)

HouseDiffusion génère directement des plans vectoriels en débruitant les coordonnées des sommets de pièces et de portes. Les objectifs de débruitage continu et discret servent à représenter des relations géométriques telles que l’orthogonalité et le partage de sommets [R3]. Cette approche est distincte de celle d’un modèle d’image qui redessine un guide déjà calculé. La distinction est essentielle pour attribuer correctement une contribution à la génération des coordonnées. [Article original de Shabani et al.](https://arxiv.org/abs/2211.13287)

Tell2Design étudie la génération de plans à partir de descriptions textuelles, avec un jeu de données, une référence séquence à séquence et des évaluations humaines [R4]. Ce travail confirme l’intérêt scientifique de la traduction du langage vers des contraintes de conception. Il situe aussi la compréhension de la demande comme un objet d’évaluation autonome. [Publication ACL de Leng et al.](https://aclanthology.org/2023.acl-long.820/)

Ces travaux ne peuvent pas être comparés numériquement aux résultats d’A-AI en juxtaposant leurs scores publiés. Les données, les entrées, les sorties et les évaluateurs diffèrent. Une comparaison recevable exigerait un protocole commun, des adaptateurs explicités et une analyse des capacités représentatives de chaque méthode. Notre étude est donc positionnée comme une contribution méthodologique et une étude de système, et non comme une compétition de modèles sur un classement commun.

### 2.2. Acceptation sélective et rôle de l’abstention

La classification sélective étudie des systèmes qui peuvent refuser une prédiction afin d’arbitrer entre risque et couverture [R5]. Le principe fournit une analogie utile pour la génération de plans : produire une sortie à toute demande n’est pas toujours souhaitable. Une parcelle de dimensions incompatibles doit pouvoir conduire à un diagnostic explicite. Nous transférons la notion de risque–couverture au niveau de la livraison du document, sans transférer automatiquement les garanties théoriques propres aux classificateurs étudiés par ces auteurs. [El-Yaniv et Wiener, article JMLR](https://jmlr.org/beta/papers/v11/el-yaniv10a.html)

Cette analogie demande une précision. Un refus fondé sur une contrainte géométrique démontrée n’a pas la même signification qu’un refus fondé sur un score de confiance appris. Dans le premier cas, on peut identifier une incompatibilité précise. Dans le second, on estime un risque. A-AI permet de distinguer ces décisions dans les traces d’exécution, afin d’éviter de présenter toute absence de résultat comme une preuve d’impossibilité.

### 2.3. Vérification et mesure de l’incertitude

Le bootstrap fournit un principe de rééchantillonnage pour étudier la variabilité d’un estimateur [R6]. Dans notre contexte, son application doit conserver ensemble les différentes graines d’un même programme. Nous utilisons cette adaptation pour éviter que des variantes très proches soient traitées comme autant de bâtiments indépendants. Les intervalles pour proportions reposent, lorsqu’une hypothèse binomiale est justifiée, sur des méthodes explicites telles que celle de Wilson [R7–R8].

L’apport statistique ne réside donc pas dans l’ajout décoratif d’un intervalle de confiance à un pourcentage. Il consiste à choisir le bon objet aléatoire, à rendre visibles les dénominateurs et à reconnaître les situations où les données ne permettent pas l’inférence souhaitée. Un corpus synthétique de développement renseigne sur des mécanismes d’échec ; il ne représente pas automatiquement la distribution des logements réels.

<div style="page-break-after: always; break-after: page;"></div>

## 3. Architecture du système et chaîne de responsabilité

### 3.1. Du besoin au document géométrique

L’entrée comprend un texte libre, des dimensions de parcelle et des paramètres de conception. Le système construit un programme structuré, nommé `BuildingSpec`, qui explicite les types de pièces, les effectifs et les contraintes numériques disponibles. L’interprétation peut solliciter un modèle de langage ; un mode local procède par règles. Le statut de chaque chemin est enregistré. La validité syntaxique du JSON constitue un contrôle utile, mais ne prouve pas que le sens du texte a été correctement compris.

La construction spatiale transforme ce programme en pièces et relations géométriques. Plusieurs arrangements peuvent être examinés. Un score interne privilégie notamment des surfaces proches des cibles, des proportions moins allongées et une circulation mesurée. L’adaptation à la parcelle peut reconstruire le pavage. Par conséquent, l’objet pertinent pour l’évaluation est le document final après adaptation, pas une proposition intermédiaire qui pourrait être remplacée.

Le document final, nommé `PlanDocument`, contient les coordonnées des pièces, les segments de murs, les ouvertures référencées à ces murs et les instances de mobilier. Les unités sont explicites. Les collections possèdent des identifiants permettant de relier les éléments et de contrôler les références. L’éditeur manipule ce document ; les rendus constituent des vues de ses données. Cette centralisation permet d’étudier séparément une transformation des données et une transformation de leur apparence.

### 3.2. Cartographie de la pipeline

```text
Brief + contraintes de parcelle
             |
             v
Interprétation du programme : BuildingSpec
             |
             v
Construction des dispositions et sélection d’un candidat
             |
             v
Assemblage vectoriel, adaptation à la parcelle, mobilier
             |
             v
Validation finale du PlanDocument ---- échec ---> diagnostic explicite
             |
          succès
             |
       +-----+------------------+
       |                        |
       v                        v
Éditeur / rendu local       Guide graphique local
       |                        |
       v                        v
Révision du document       Illustration Gemini optionnelle
```

**Figure 1.** Chaîne de responsabilité du parcours étudié. L’illustration ne redéfinit pas les coordonnées du document. La trace distingue le moteur configuré, les appels tentés, le moteur effectivement utilisé et les replis.

Cette organisation s’appuie sur un service applicatif commun aux transports HTTP et file de travail. Les modules de géométrie isolent les opérations de domaine. Les adaptateurs d’IA externe gèrent les échanges avec les fournisseurs. Une fonction de progression informe l’interface sans imposer au domaine la connaissance des identifiants de jobs. Ces choix relèvent de la séparation des responsabilités ; leur intérêt scientifique est de permettre une attribution plus précise des effets observés.

### 3.3. Place exacte de Gemini

Gemini reçoit un guide issu du document final et des instructions de présentation. La documentation du fournisseur décrit la génération et l’édition d’images à partir d’entrées textuelles et visuelles [R9]. Dans A-AI, cette capacité sert à produire une illustration conditionnée. Elle ne constitue pas, à elle seule, une preuve d’égalité entre l’image produite et les coordonnées du plan. Cette conclusion découle de la conception de l’intégration, et non d’un jugement général sur toutes les capacités du modèle. [Documentation officielle Gemini](https://ai.google.dev/gemini-api/docs/image-generation)

Une conséquence pratique est de conserver deux statuts : le document contrôlé et l’aperçu illustratif. Une amélioration de l’aperçu doit être évaluée sur la lisibilité, la préférence et la fidélité au document. Elle ne peut recevoir le mérite d’une amélioration géométrique si aucune coordonnée n’a changé. Réciproquement, une amélioration des ouvertures peut être réelle même si la différence visuelle globale paraît minime.

Les noms historiques de modules ne définissent pas les mécanismes actifs. Dans le parcours documenté, le module nommé `diffusion` peut exécuter une construction procédurale, `vectorize` assemble une géométrie déjà disponible et le raffinement GAN est sauté en l’absence d’image intermédiaire. Les résultats présentés ici ne sont donc pas attribués à l’entraînement d’un nouveau réseau de diffusion ou d’un GAN. Cette précision rend l’article conforme au fonctionnement observé du système.

<div style="page-break-after: always; break-after: page;"></div>

## 4. Formalisation du problème architectural

### 4.1. Notations et ensemble des solutions admissibles

On note $b$ le brief, $c$ les contraintes explicites et $z$ une graine locale. Le programme interprété est $S=f_\theta(b,c)$, où $\theta$ désigne le modèle ou les paramètres du parseur. Le document proposé s’écrit $D=G(S,c,z)$. Cette notation n’impose pas que $G$ soit neuronal : il peut combiner heuristiques, énumération de candidats et règles géométriques.

Un document contient un ensemble de pièces $\mathcal R=\{P_1,\ldots,P_m\}$, de murs $\mathcal W$ et d’ouvertures $\mathcal O$. Chaque $P_i$ est un polygone simple, exprimé en mètres. On désigne par $\Omega(c)$ l’enveloppe autorisée et par $A(P)$ l’aire d’un polygone. La mesure $\mu_2$ est une aire, en mètres carrés. Les contraintes strictes idéales comprennent :

$$
P_i\subseteq\Omega(c),\qquad A(P_i)>0,\qquad
\mu_2(P_i\cap P_j)=0\quad(i\ne j).
\tag{1}
$$

La dernière égalité autorise le partage d’une frontière : deux pièces peuvent se toucher sans se recouvrir sur une surface positive. Dans l’implémentation numérique, des tolérances distinctes sont nécessaires pour les longueurs et pour les aires. Le profil étudié utilise des ordres de grandeur de $10^{-6}$ m et de $10^{-6}$ m² selon le contrôle. Ces deux valeurs ne possèdent pas la même unité ; les confondre rendrait la vérification dimensionnellement incorrecte.

Les coordonnées doivent aussi être finies, les identifiants non ambigus et les polygones non auto-intersectants. Une liste de trois points n’est donc pas un critère suffisant de validité. Le système distingue le format du document de sa géométrie. Un format décodable peut représenter un objet spatial invalide.

### 4.2. Surfaces et contraintes de parcelle

Pour un polygone simple de sommets ordonnés $(x_k,y_k)$, $k=1,\ldots,n$, avec $(x_{n+1},y_{n+1})=(x_1,y_1)$, la formule d’aire est :

$$
A(P)=\frac12\left|\sum_{k=1}^{n}
(x_k y_{k+1}-x_{k+1}y_k)\right|.
\tag{2}
$$

La valeur absolue rend le résultat indépendant du sens de parcours. La simplicité du contour est une hypothèse : une somme algébrique non nulle ne rend pas valide un polygone croisé. Un rectangle de 4 m sur 3 m donne 12 m² dans les deux orientations, ce qui fournit un contrôle numérique élémentaire.

Pour une parcelle rectangulaire de largeur $W$ et profondeur $H$, avec un retrait uniforme $r\geq0$, les dimensions utiles sont $W_u=W-2r$ et $H_u=H-2r$. Une condition nécessaire à l’existence d’une emprise rectangulaire positive est :

$$
W-2r>0\quad\text{et}\quad H-2r>0.
\tag{3}
$$

Cette condition est exacte pour le problème défini, mais insuffisante pour assurer que le programme rentre dans la parcelle. Le moteur ne doit pas remplacer une dimension utile négative par un minimum arbitraire : ce remplacement construirait une réponse à un problème différent. Avec $W=10$, $H=8$ et $r=1$, l’emprise utile est de 8 m sur 6 m, soit 48 m². Avec $W=2$ et $r=1$, la largeur utile est nulle ; une maison de largeur strictement positive est impossible dans cette formulation.

### 4.3. Ouvertures définies dans le repère du mur

Soient les extrémités $a,b\in\mathbb R^2$ d’un mur, sa longueur $\ell=\|b-a\|_2>0$, l’offset $o$ d’une ouverture et sa largeur $w>0$. Ses extrémités sont :

$$
p_0=a+\frac{o}{\ell}(b-a),\qquad
p_1=a+\frac{o+w}{\ell}(b-a),\qquad
0\leq o<o+w\leq\ell.
\tag{4}
$$

Cette écriture reste correcte lorsque le mur est vertical ou orienté de droite à gauche. Pour deux ouvertures du même mur, d’intervalles $[o_i,o_i+w_i]$ et $[o_j,o_j+w_j]$, la longueur de recouvrement est :

$$
L_{ij}=\max\{0,\min(o_i+w_i,o_j+w_j)-\max(o_i,o_j)\}.
\tag{5}
$$

Une valeur positive signale un chevauchement ; zéro autorise notamment le contact exact. Ce dernier peut être admis par le contrat géométrique sans être souhaitable constructivement. Un trumeau minimal relève d’une contrainte supplémentaire, qui doit être formulée et évaluée séparément.

<div style="page-break-after: always; break-after: page;"></div>

## 5. Génération hybride et propriété de vérification

### 5.1. Sélection parmi des candidats admissibles

On note $\mathcal C_K(S,c)=\{D_1,\ldots,D_K\}$ l’ensemble fini des candidats examinés avec un budget $K$. Un prédicat $V(D,c)$ vaut 1 lorsque le document satisfait les contrôles du contrat et 0 sinon. L’ensemble vérifié est $\mathcal C_K^V=\{D\in\mathcal C_K:V(D,c)=1\}$.

La sélection peut se formaliser par :

$$
D^*\in\operatorname*{arg\,min}_{D\in\mathcal C_K^V}J(D,S),
\qquad \mathcal C_K^V\ne\varnothing.
\tag{6}
$$

L’équation (6) est une formulation idéale de la recherche sous contraintes, et non la transcription de l’ordre exact des opérations du logiciel. Dans le parcours implémenté, la sélection porte d’abord sur des dispositions de pièces, avec leurs contrôles internes et une préférence éventuelle pour un arrangement mémorisé. Le document complet est ensuite assemblé, adapté, puis soumis au validateur final. Le système ne construit donc pas nécessairement un ensemble de documents finaux tous filtrés avant sélection, et une validation finale échouée ne garantit pas la recherche automatique d’un autre candidat.

Le score $J$ arbitre entre des préférences sur les candidats disponibles. Un score faible n’est ni une probabilité de validité ni une preuve d’optimalité globale. Dans le cadre idéal, un ensemble vérifié vide conduit à un diagnostic de recherche infructueuse, sauf si une impossibilité a été démontrée par ailleurs, comme dans l’équation (3). Dans le système, l’échec du candidat final conserve la même distinction entre rejet du document et preuve d’impossibilité du problème.

Le code de sélection combine plusieurs pénalités et une fenêtre de candidats quasi optimaux. Pour expliciter cette idée indépendamment des coefficients logiciels, on peut définir :

$$
\mathcal C_{K,\tau}^V=
\{D\in\mathcal C_K^V:J(D,S)\leq J_{\min}+\tau\},
\qquad \tau\geq0,
\tag{7}
$$

où $J_{\min}$ est le minimum sur l’ensemble vérifié. Cette écriture prolonge le cadre idéal de l’équation (6) ; dans le code, la fenêtre de sélection s’applique aux dispositions admissibles à cette étape, avant la validation finale du document adapté. Une graine choisit parmi les candidats retenus selon la politique de sélection. Le seuil $\tau$ a la même unité conventionnelle que $J$. Il règle un compromis entre diversité et proximité du meilleur score, sans garantir que des graines différentes produisent des arrangements différents. La diversité doit donc être mesurée, pas déduite de la présence d’un paramètre aléatoire.

### 5.2. Une garantie conditionnelle, précisément délimitée

Définissons $\mathcal F_V(c)$ comme l’ensemble des documents qui satisfont les propriétés mathématiques du contrat. L’acceptation finale est $a(D,c)=\mathbf1\{V(D,c)=1\}$. Les conditions nécessaires à la garantie sont les suivantes : le validateur est correct pour ce contrat, toutes les sorties livrées passent par lui et aucune modification non revalidée n’altère ensuite le document livré.

**Proposition 1 — Validité conditionnelle du document accepté.** Sous ces conditions, si $\Pr(a=1)>0$, alors :

$$
\Pr\bigl(D\notin\mathcal F_V(c)\mid a=1\bigr)=0.
\tag{8}
$$

**Démonstration.** La correction du validateur implique $V(D,c)=1\Rightarrow D\in\mathcal F_V(c)$. L’événement $\{D\notin\mathcal F_V(c),a=1\}$ est donc vide. Sa probabilité est nulle ; la division par $\Pr(a=1)>0$ donne le résultat. La propriété ne dépend pas de la distribution des propositions, mais elle dépend entièrement des hypothèses sur le contrôle et la livraison.

Cette proposition est une conséquence logique du filtrage, pas un nouveau théorème d’apprentissage. Sa valeur est de montrer où se situe la responsabilité de la garantie. Un contrat incomplet peut accepter un plan inutilisable ; une erreur d’implémentation peut violer le contrat ; une modification après validation peut invalider le résultat. Les tests renforcent la confiance dans ces hypothèses sans les transformer en preuve formelle du logiciel complet.

### 5.3. Pourquoi valider la géométrie ne suffit pas

Soit $S^\dagger$ le besoin correctement interprété. Le plan peut vérifier toutes les contraintes géométriques de $S=f_\theta(b,c)$ alors que $S\ne S^\dagger$. Un garage non demandé peut être parfaitement rectangulaire, accessible et contenu dans l’emprise. La preuve précédente n’établit donc pas la vérité de l’interprétation. Elle ne démontre pas non plus l’éclairage naturel, le confort ou la conformité réglementaire.

Cette limite motive une séparation de trois fonctions : le score qui choisit, le validateur qui autorise une livraison et l’évaluateur qui mesure le résultat. L’évaluateur géométrique du benchmark utilise une bibliothèque de géométrie et ne réutilise pas le moteur de placement. Cette indépendance d’implémentation réduit un risque de circularité ; elle ne supprime pas les angles morts conceptuels communs, tels qu’une définition trop pauvre de l’accessibilité.

<div style="page-break-after: always; break-after: page;"></div>

## 6. Mesurer la qualité sans masquer les échecs

### 6.1. Couverture, risque et rendement utile

Considérons $N$ demandes d’évaluation. Pour la demande $i$, $a_i=1$ si un document est retourné, et $a_i=0$ sinon. Parmi les documents retournés, $v_i=1$ indique la validité selon un évaluateur indépendant. Pour les refus, on fixe $v_i=0$ uniquement afin d’écrire des produits ; cela ne signifie pas qu’un document a été observé. La couverture et le risque géométrique conditionnel empirique sont :

$$
\widehat C=\frac1N\sum_{i=1}^{N}a_i,
\qquad
\widehat R_g=
\frac{\sum_{i=1}^{N}a_i(1-v_i)}{\sum_{i=1}^{N}a_i}.
\tag{9}
$$

Le risque n’est défini que si au moins un document est retourné. Le rendement géométriquement valide, calculé sur toutes les demandes, vérifie l’identité :

$$
\widehat Y_g=\frac1N\sum_{i=1}^{N}a_i v_i
=\widehat C(1-\widehat R_g).
\tag{10}
$$

Cette identité empêche un raisonnement trompeur : un système qui refuse presque tout peut présenter un risque conditionnel très faible. Il faut publier la couverture et le rendement en même temps. Inversement, sur une entrée mathématiquement impossible, le rejet est le comportement attendu ; la baisse du taux brut de retour peut traduire une amélioration. Le rapport distingue donc refus justifiés, erreurs techniques et absence de candidat trouvé.

### 6.2. Conformité au programme et surfaces

Soit $\mathcal I_P$ l’ensemble des demandes dont le programme est annoté. Pour une sortie existante, $p_i=1$ si les effectifs par type de pièce correspondent à l’annotation, et 0 sinon. Pour un refus, on fixe conventionnellement $p_i=0$, sans lui attribuer de document observé. La conformité conditionnelle utilise le dénominateur $\sum_{i\in\mathcal I_P}a_i$ et n’est définie que si ce dénominateur est positif. Lorsque $|\mathcal I_P|>0$, le rendement combiné sur toutes les demandes annotées est :

$$
\widehat Y_{g,p}=
\frac{1}{|\mathcal I_P|}\sum_{i\in\mathcal I_P}a_i v_i p_i.
\tag{11}
$$

Sans demande annotée, le rendement combiné est non disponible. Il serait incorrect de l’obtenir en multipliant deux taux calculés sur des ensembles différents ou en supposant l’indépendance de la géométrie et de la sémantique. Un plan qui respecte le nombre de pièces mais ignore une négation reste incorrect du point de vue du besoin.

Lorsque des surfaces cibles strictement positives $t_j$ sont explicitement annotées et appariées aux pièces, l’erreur relative moyenne est :

$$
E_A=\frac1q\sum_{j=1}^{q}\frac{|A(P_j)-t_j|}{t_j},
\qquad q\geq1.
\tag{12}
$$

Cette quantité est sans unité. Si aucune cible n’est annotée, elle est non mesurée, et non égale à zéro. Pour des pièces de même type, l’appariement doit être fixé avant la comparaison ; le tri par surface employé par un évaluateur ne vérifie pas l’identité fonctionnelle de chaque chambre. L’erreur maximale peut compléter la moyenne afin de rendre visible une pièce particulièrement défavorisée.

### 6.3. Usage et fidélité visuelle

Pour évaluer l’accessibilité, un graphe de circulation relie deux pièces lorsqu’un passage effectif les connecte. Avec une entrée $e$, l’indicateur proposé est la proportion de pièces habitables atteignables depuis $e$. Un simple contact de murs ne suffit pas à créer une arête. Cet indicateur appartient au protocole d’évaluation fonctionnelle ; il n’est pas renseigné dans les résultats géométriques archivés présentés ici.

La fidélité d’un rendu exige aussi une définition précise. Pour deux masques de murs $M_D$ et $M_I$, recalés dans un même repère et dont l’union est non vide, l’intersection sur union vaut :

$$
\operatorname{IoU}(M_D,M_I)=
\frac{|M_D\cap M_I|}{|M_D\cup M_I|}.
\tag{13}
$$

Seuiller tous les pixels sombres d’une image meublée ne fournit pas nécessairement un masque de murs : texte, mobilier et ombres contaminent la mesure. Une annotation sémantique ou une méthode de segmentation validée est nécessaire. Enfin, l’identité du document avant et après un changement de style prouve la préservation des données contrôlées, mais ne prouve pas que chaque primitive a été correctement dessinée. Les deux contrôles sont complémentaires.

<div style="page-break-after: always; break-after: page;"></div>

## 7. Protocole statistique et conditions d’inférence

### 7.1. Unité d’analyse et comparaisons appariées

Un programme architectural est l’unité principale. Ses cinq graines sont des variantes corrélées, et certaines graines ne changent effectivement pas le résultat. Les dix-huit ou trente images d’un même logement ne constituent pas davantage autant de logements indépendants. Le corpus de développement comprend vingt programmes ; dix autres programmes sont réservés par le protocole à une évaluation finale et ne sont pas utilisés dans les résultats rapportés.

Pour une métrique $y$, notons $y_{u,s}^{A}$ et $y_{u,s}^{B}$ les résultats des versions $A$ et $B$ sur le programme $u$ et la graine $s$. Sur un ensemble de graines comparables $\mathcal S_u$, le contraste moyen par programme et le contraste global sont :

$$
\Delta_u=\frac{1}{|\mathcal S_u|}
\sum_{s\in\mathcal S_u}(y_{u,s}^{B}-y_{u,s}^{A}),
\qquad
\widehat\Delta=\frac1U\sum_{u=1}^{U}\Delta_u.
\tag{14}
$$

Chaque programme a ainsi le même poids. Pour une métrique définie uniquement sur des documents retournés, les paires manquantes ne sont pas silencieusement retirées : on publie leur nombre et on complète l’analyse par couverture, rendement ou coût incluant l’échec. Les effets conditionnels et globaux répondent à des questions différentes.

L’archivage apparié conserve le brief, les contraintes, les graines, les versions, les paramètres et les échecs. Le comparateur vérifie la compatibilité des configurations. Il ne compare pas seulement l’intersection des expériences qui ont réussi. Cette règle évite qu’une version paraisse meilleure parce que ses cas difficiles ont disparu du tableau.

### 7.2. Bootstrap par programme

L’intervalle descriptif utilise un rééchantillonnage des $U$ programmes avec remise. Pour la réplication $b$, on tire $U$ indices $u_1^{(b)},\ldots,u_U^{(b)}$ et calcule :

$$
\widehat\Delta^{*(b)}=
\frac1U\sum_{j=1}^{U}\Delta_{u_j^{(b)}}.
\tag{15}
$$

Les quantiles empiriques à 2,5 % et 97,5 % des 2 000 réplications forment l’intervalle percentile. Le principe de rééchantillonnage vient du bootstrap [R6] ; le regroupement par programme correspond à la structure de nos données. Une approximation de couverture fréquentiste demande notamment une population cible pertinente et des unités de programme raisonnablement indépendantes.

Dans un petit corpus synthétique choisi pour révéler des erreurs, cet intervalle décrit surtout la stabilité du contraste face à la composition des cas observés. Il ne corrige ni la sélection du corpus ni un changement de machine entre deux mesures. S’il n’existe qu’un programme corrigé, un intervalle et une valeur moyenne doivent être accompagnés du cas individuel ; ils ne transforment pas une réparation ciblée en preuve de supériorité générale.

### 7.3. Proportions et absence d’erreurs observées

Pour $n$ observations de Bernoulli indépendantes de même probabilité $p$, $\widehat p=k/n$ et $z=z_{1-\alpha/2}$, l’intervalle de Wilson est :

$$
\left[
\frac{\widehat p+z^2/(2n)-z\sqrt{\widehat p(1-\widehat p)/n+z^2/(4n^2)}}{1+z^2/n},
\frac{\widehat p+z^2/(2n)+z\sqrt{\widehat p(1-\widehat p)/n+z^2/(4n^2)}}{1+z^2/n}
\right].
\tag{16}
$$

Il résulte de l’inversion de l’inégalité du test de score $|\widehat p-p|\leq z\sqrt{p(1-p)/n}$ [R7–R8]. Les hypothèses d’indépendance ne sont pas satisfaites par le simple comptage des cinq graines d’un programme ; nous n’appliquons donc pas cet intervalle aux 85 plans archivés comme s’ils étaient indépendants.

Lorsque zéro erreur est observée dans un véritable échantillon binomial de taille $n$, une borne supérieure unilatérale exacte au niveau $1-\alpha$ est :

$$
p_U=1-\alpha^{1/n}.
\tag{17}
$$

La dérivation utilise $\Pr(K=0\mid p)=(1-p)^n=\alpha$. Pour $n=20$ et $\alpha=0{,}05$, on obtient environ 13,91 %. Il s’agit d’un exemple pédagogique, non d’une borne calculée pour notre corpus. Même vingt succès indépendants seraient donc insuffisants pour conclure à un risque presque nul avec une forte confiance.

<div style="page-break-after: always; break-after: page;"></div>

## 8. Résultats empiriques de l’étude de cas

### 8.1. Sources, configuration et dénominateurs

Les résultats proviennent des archives locales de comparaison `3b-parcel`, `3b-openings` et `3b-polygons-final` [P1–P3]. Chaque comparaison comprend vingt programmes de développement et cinq graines, soit cent observations mesurées après échauffement. Le nombre de répétitions chronométrées par couple programme–graine est un. Les appels externes sont désactivés : l’interprétation textuelle utilise le mode local, le placement est local et les images sont produites localement. Ces résultats n’estiment donc pas la performance d’un LLM externe ni celle de Gemini.

Trois programmes ont une emprise utile non positive selon les contraintes du corpus. Ils produisent quinze observations de refus attendus dans les versions corrigées. Dix-sept programmes donnent 85 documents. Parmi ces documents, 80 disposent d’une annotation exploitable du programme de pièces ; les cinq autres correspondent au même programme non annoté pour cette mesure. Les valeurs manquantes demeurent explicitement absentes.

| Étape comparée | Demandes | Documents retournés | Documents géométriquement valides | Documents livrés malgré une parcelle impossible |
|---|---:|---:|---:|---:|
| Référence avant contrôle de parcelle | 100 | 100 | 84 | 15 |
| Après contrôle de parcelle | 100 | 85 | 84 | 0 |
| Après correction des ouvertures | 100 | 85 | 85 | 0 |
| Après consolidation du contrôle polygonal | 100 | 85 | 85 | 0 |

**Tableau 1.** Résultats descriptifs des étapes archivées. Les lignes représentent des états successifs documentés et non quatre groupes randomisés. La validité concerne l’évaluateur géométrique déclaré, pas l’ensemble des propriétés architecturales.

### 8.2. Effet du contrôle de faisabilité

Le contrôle de parcelle fait passer la couverture brute de 100 % à 85 %. Le nombre de documents valides reste égal à 84. Cette baisse de couverture retire quinze sorties qui ne pouvaient respecter une emprise utile positive. Le risque géométrique parmi les documents retournés passe de $16/100=16\%$ à $1/85\approx1{,}18\%$. Le rendement global valide reste $84/100=84\%$.

La lecture conjointe des trois quantités explique le résultat : cette étape améliore la qualité des documents livrés en empêchant des livraisons invalides, sans créer un nouveau plan valide. Présenter uniquement le taux de réussite du service conduirait à qualifier cette correction de dégradation. Présenter uniquement le taux conditionnel de validité ferait oublier que le système a changé de comportement d’acceptation. La décomposition de l’équation (10) rend les deux aspects visibles.

Les quinze refus correspondent à trois programmes, et non à quinze parcelles indépendantes. Ils portent sur le motif précis d’emprise utile non positive. L’expérience ne démontre pas que le moteur reconnaît toutes les impossibilités architecturales ni qu’il trouve toujours une solution lorsqu’elle existe.

### 8.3. Correction localisée d’une ouverture

La comparaison des ouvertures identifie un seul document modifié, `dev07/2/0`. Une fenêtre de 1,40 m de large est déplacée de l’offset 2,50 m à 2,40 m, tandis qu’une porte de garage reste à l’offset 3,80 m avec une largeur de 2,40 m. Avant correction, les intervalles $[2{,}50;3{,}90]$ et $[3{,}80;6{,}20]$ se recouvrent sur 0,10 m. Après correction, $[2{,}40;3{,}80]$ et $[3{,}80;6{,}20]$ sont tangents. L’équation (5) donne respectivement 0,10 m et 0 m.

Le nombre de documents valides passe de 84 à 85 sur 85 retours, soit une amélioration de $1/85\times100\approx1{,}18$ point de pourcentage de validité conditionnelle. Le rendement global augmente d’un point, de 84 % à 85 %. Les 84 autres documents et leurs PNG locaux sont identiques. L’inspection documentée du cas confirme le déplacement ciblé. Il ne s’agit pas d’un gain esthétique démontré ni d’une validation constructive d’un contact sans trumeau.

### 8.4. Une erreur sémantique subsiste

Sur les 80 retours dont le programme est mesurable, 75 respectent les effectifs attendus, soit 93,75 %. Les cinq échecs appartiennent au programme `dev07` : la demande contenant « sans garage » produit encore un garage dans le mode local étudié. Cette observation fournit un contre-exemple concret à l’idée qu’un document géométriquement valide répond nécessairement au besoin.

Les résultats soutiennent ainsi deux conclusions de portée différente. La correction d’ouverture élimine l’anomalie mesurée dans le cas observé. La chaîne conserve une faiblesse sémantique que le validateur géométrique ne détecte pas par définition. Ce contre-exemple délimite la propriété effectivement acquise et fournit une cible précise pour l’évaluation des composants d’interprétation.

<div style="page-break-after: always; break-after: page;"></div>

## 9. Rendu, reproductibilité et expérience de présentation

### 9.1. Une modification graphique à données constantes

Une expérience complémentaire concerne le dessin du plan dans l’éditeur 2D [P4]. Elle compare deux versions de rendu sur six documents gelés, avec trois zooms — 50 %, 100 % et 200 % — et deux densités de pixels. Les 36 vues ordinaires sont complétées par deux captures d’interaction, sélection et glissement, soit 38 paires de captures.

| Contrôle | Résultat archivé |
|---|---:|
| Captures avant/après | 38 paires |
| Images modifiées par la refonte | 38 sur 38 |
| Empreintes des documents préservées | 38 sur 38 |
| Fichiers JSON d’entrée identiques octet par octet | 6 sur 6 |
| Chargements d’éléments graphiques réussis | 564 sur 564 |
| Tentatives d’accès réseau | 0 |

**Tableau 2.** Contrôles d’intégrité du benchmark d’éditeur. Les 38 captures sont des mesures de six documents, pas 38 projets architecturaux indépendants. Les 564 chargements ne sont pas non plus 564 éléments graphiques distincts.

La refonte hiérarchise les murs, les ouvertures, les annotations et le mobilier. Les portes et fenêtres sont dessinées à partir des ouvertures enregistrées ; les dimensions intérieures sont affichées lorsque la géométrie autorise une interprétation exacte. Ces changements relèvent du moteur graphique de l’éditeur, qui constitue une chaîne distincte de l’illustration Gemini.

Cette expérience répond à une question circonscrite : peut-on faire évoluer la présentation en conservant les données du projet ? Les contrôles archivés soutiennent une réponse positive pour les six documents testés. Ils ne démontrent pas une préférence esthétique des utilisateurs, une meilleure vitesse de compréhension ou une réduction des erreurs d’édition. Ces propriétés demandent d’autres observations.

### 9.2. Interprétation des temps de rendu

Le rapport contient une médiane de somme de durées de couche de 352,75 ms avant modification et de 357,25 ms après modification, soit environ +1,28 %. Ces valeurs agrègent des appels instrumentés pendant le chargement et les redessins de chaque vue. Elles ne représentent pas automatiquement le temps d’une image interactive stabilisée, ni la latence perçue lors d’un déplacement.

La comparaison demeure descriptive. Le protocole ne fournit pas ici une expérience randomisée de performance à répétitions nombreuses sur une machine isolée. Une différence inférieure à quelques pour cent peut être sensible au chargement, à l’ordonnancement et au cache. Nous ne convertissons donc pas ce chiffre en garantie de fluidité ni en preuve d’une optimisation algorithmique. Pour mesurer la réactivité, il faudrait définir un geste, une fenêtre de mesure, un échauffement et des quantiles de durée par image.

La même prudence s’applique aux latences de génération des archives. Un changement de validateur peut coïncider avec une baisse chronométrique sans en être la cause. La conservation des sources, du matériel et des paramètres rend la question analysable ; elle ne remplace pas l’organisation expérimentale requise pour une attribution causale.

### 9.3. Reproductibilité et provenance

Chaque exécution conserve les entrées, le document produit, le rendu local, les mesures, les erreurs et un manifeste. Les archives contiennent les sources nécessaires à la reproduction, y compris celles qui ne sont pas encore intégrées dans un commit. Une empreinte SHA-256 vérifie l’intégrité du contenu ; elle ne prouve ni la correction du code ni l’authenticité d’un résultat au-delà de la chaîne d’archivage maîtrisée.

Les appels externes demandent une provenance plus fine : modèle demandé, modèle configuré, modèle éventuellement déclaré par le fournisseur, nombre de tentatives et motif de repli. Un nom de modèle dans la configuration ne prouve pas que ce modèle a effectivement rendu l’image. Une graine locale ne garantit pas non plus la répétabilité d’un service distant. La disponibilité de ces informations protège contre une attribution erronée d’un rendu local à Gemini.

Enfin, l’indépendance de l’évaluateur mérite d’être vérifiée dans le code. Les diagnostics de géométrie utilisent une implémentation séparée du moteur de placement. Ils signalent explicitement les dimensions non mesurées : accessibilité, dégagement du mobilier et fidélité Gemini. Cette déclaration constitue une information scientifique, car elle empêche un lecteur d’étendre involontairement la portée d’un score.

<div style="page-break-after: always; break-after: page;"></div>

## 10. Discussion : portée pour l’IA et les statistiques appliquées

### 10.1. Une architecture de confiance par responsabilités

La portée principale de cette étude est de déplacer l’objet de la confiance. Au lieu de demander si un modèle « sait dessiner une maison », on demande quelles propriétés du résultat sont contrôlables, par quel composant et à quel moment. Cette reformulation convient à de nombreuses tâches où l’IA produit un objet structuré : configuration industrielle, agencement intérieur, dessin technique ou préparation d’un document réglementé.

Le document canonique rend ces responsabilités inspectables. Une erreur de compréhension appartient à la relation entre brief et programme. Un recouvrement appartient au calcul géométrique. Une porte dessinée au mauvais endroit appartient à la projection graphique. Une image embellie qui invente une ouverture appartient à la fidélité de l’illustration. L’existence d’un objet commun permet de comparer ces niveaux au lieu de les agréger sous une étiquette vague de qualité.

Cette structure offre également un moyen de construire des interventions. On peut améliorer le contrôle des ouvertures en conservant le reste du document, puis mesurer le changement exact. On peut modifier le style du rendu sur des entrées gelées, puis vérifier la préservation des données. Une telle modularité facilite des ablations interprétables. Elle ne garantit toutefois pas une indépendance causale complète : une adaptation qui repave le logement peut modifier l’effet d’une proposition antérieure.

### 10.2. Ce que les résultats permettent réellement de soutenir

Les données soutiennent la valeur de contrôles explicites sur deux familles d’erreurs : les emprises impossibles détectables par les dimensions utiles et un chevauchement d’ouverture identifié. Elles montrent aussi que l’ingénierie graphique peut évoluer avec des documents inchangés. Ces observations sont reproductibles dans le périmètre des archives.

Elles ne permettent pas d’affirmer que l’ensemble des logements produits serait constructible, qu’un réseau particulier surpasserait les approches publiées ou que Gemini améliorerait la précision géométrique. Le parcours testé utilise des composants locaux. Une expérience différente est nécessaire pour évaluer les modèles externes. Le résultat sémantique négatif constitue un point de départ utile pour cette comparaison : il identifie une tâche observable, la préservation d’une négation du brief.

Le contraste entre 100 % de validité géométrique conditionnelle et 93,75 % de conformité au programme sur les retours annotés illustre l’intérêt d’une analyse multidimensionnelle. Un seul score aurait pu masquer cette différence. Pour une application réelle, le tableau de bord devrait donc afficher des diagnostics localisés et une liste des contrôles exécutés, plutôt qu’un pourcentage de confiance dont la signification resterait floue.

### 10.3. Évaluer les composants appris sans confusion d’attribution

Le protocole d’extension distingue trois expériences. La première compare l’interprétation locale et l’interprétation par modèle de langage, à brief et règles aval identiques. La deuxième compare l’ajout d’une proposition spatiale du modèle, à programme structuré fixé et budget de recherche comparable. La troisième compare le rendu local et l’illustration Gemini à document strictement fixé.

Cette séparation permet de poser une question à chaque étape. L’interprétation préserve-t-elle mieux les contraintes négatives ? La proposition spatiale survit-elle à l’adaptation et améliore-t-elle le document final ? L’illustration améliore-t-elle la lisibilité sans altérer les relations perceptibles ? Ces questions sont testables. Elles évitent une ablation nominale où un composant désactivé ou écrasé par l’étape suivante recevrait néanmoins une part du gain.

Pour l’évaluation humaine du rendu, les observateurs examinent des paires avec un ordre de présentation randomisé et des versions masquées. La préférence, la fidélité et la détection d’erreurs sont recueillies séparément. Les jugements provenant d’un même évaluateur et les variantes d’un même programme sont dépendants. Le protocole doit les traiter comme mesures répétées ; un grand nombre de clics ne compense pas un petit nombre d’architectes ou de programmes.

### 10.4. Limites scientifiques

Le corpus est synthétique et a servi au développement. Ses programmes sont choisis pour couvrir des situations, non tirés au hasard d’une population de projets réels. Les résultats peuvent donc surestimer les performances sur des briefs inattendus, des parcelles irrégulières ou des habitudes d’habitation absentes du corpus. Les paramètres de sélection comportent également des préférences de conception ; une pièce allongée ou une circulation importante n’est pas intrinsèquement mauvaise dans tout contexte.

La géométrie validée est une représentation de conception préliminaire. L’aire du polygone d’une pièce ne doit pas être assimilée sans convention à une surface habitable réglementaire, notamment lorsque l’épaisseur des murs intervient. L’absence de collisions entre pièces ne prouve pas la possibilité d’ouvrir tous les battants avec le mobilier. Un graphe connexe ne prouve pas l’accessibilité universelle. Chaque élargissement de la notion de validité demande de nouvelles données, de nouvelles règles et une compétence architecturale adaptée.

La fiabilité finale dépend donc autant de l’explicitation de ces frontières que de la sophistication du modèle génératif. C’est sur cette articulation, mesurable et critiquable, que se situe la portée doctorale du travail.

<div style="page-break-after: always; break-after: page;"></div>

## 11. Conclusion

Cet article présente une approche de génération architecturale dans laquelle le document vectoriel constitue l’objet central du raisonnement et de la vérification. L’interprétation du besoin, la construction des dispositions, le contrôle géométrique et la présentation possèdent des responsabilités distinctes. Cette organisation permet de relier chaque résultat à un mécanisme identifiable et de définir les limites des garanties fournies.

L’analyse formelle établit une propriété conditionnelle simple : un filtre correct, appliqué à toutes les sorties et suivi d’aucune modification non vérifiée, ne livre pas de document contraire au contrat qu’il contrôle. La valeur pratique de cette propriété dépend du contenu du contrat et de la qualité de son implémentation. Elle ne transforme pas une vérification de polygones en compréhension du besoin ni en certification architecturale.

Les archives montrent la suppression des livraisons associées à quinze exécutions de parcelles impossibles, puis la correction d’un chevauchement de fenêtre dans un document. Elles montrent simultanément qu’un programme peut rester mal compris malgré une géométrie valide. L’analyse du risque, de la couverture et des dénominateurs rend ces conclusions compatibles et évite une présentation artificiellement optimiste du système.

Pour la recherche en IA, l’apport est un cadre d’évaluation de systèmes génératifs hybrides où les propriétés déterministes et les capacités apprises peuvent être examinées séparément. Pour les statistiques appliquées, il souligne que l’unité d’analyse est le programme architectural et que les graines, les captures et les tentatives ne créent pas automatiquement de nouvelles observations indépendantes. Pour l’architecture, il fournit une base de travail éditable dont les contrôles et les inconnues sont explicites.

Une contribution scientifique solide ne repose donc pas seulement sur des plans plus séduisants. Elle repose sur la capacité à expliquer pourquoi un résultat est accepté, ce qui a été effectivement mesuré et quelles affirmations demeurent à vérifier. A-AI matérialise cette démarche dans une chaîne où l’image sert à communiquer un projet, tandis que sa cohérence est étudiée sur une représentation contrôlable.

## Déclarations de transparence

**Nature de l’étude.** Article méthodologique avec analyse descriptive d’archives d’un système logiciel. Les démonstrations sont conditionnelles ; les résultats empiriques ne constituent pas une évaluation représentative de la profession architecturale.

**Expériences externes.** Aucun résultat de génération Gemini, aucune comparaison chronométrée d’API, aucune préférence d’expert ni étude utilisateur n’est inventé ou présenté comme mesuré. Les expériences décrites en section 10.3 définissent un protocole complémentaire.

**Sources et disponibilité.** Les preuves sont conservées dans le dépôt A-AI selon les références P1 à P6. Leur présence locale n’équivaut pas à un dépôt public pérenne. Une soumission académique doit être accompagnée d’une version archivée, identifiée et accessible aux évaluateurs dans le respect des droits associés aux données et dépendances.

**Périmètre de version.** Les résultats publiés portent sur les versions archivées identifiées dans les références du projet. Les fonctionnalités qui ne figurent pas dans ces archives, notamment les extensions de sémantique de charnière et de débattement, n’entrent pas dans les résultats.

**Auteurs et affiliation.** Ce manuscrit n’attribue aucune signature, institution, financement ou approbation éthique non fournis. Ces informations relèvent des auteurs responsables de la soumission.

<div style="page-break-after: always; break-after: page;"></div>

## Références bibliographiques

**[R1]** Nauata, N., Chang, K.-H., Cheng, C.-Y., Mori, G. et Furukawa, Y. (2020). *House-GAN: Relational Generative Adversarial Networks for Graph-constrained House Layout Generation*. ECCV. [Manuscrit des auteurs](https://arxiv.org/abs/2003.06988).

**[R2]** Hu, R., Huang, Z., Tang, Y., van Kaick, O., Zhang, H. et Huang, H. (2020). *Graph2Plan: Learning Floorplan Generation from Layout Graphs*. ACM Transactions on Graphics. DOI : 10.1145/3386569.3392391. [Manuscrit des auteurs](https://arxiv.org/abs/2004.13204).

**[R3]** Shabani, M. A., Hosseini, S. et Furukawa, Y. (2023). *HouseDiffusion: Vector Floorplan Generation via a Diffusion Model with Discrete and Continuous Denoising*. CVPR, 5466–5475. [Actes officiels](https://openaccess.thecvf.com/content/CVPR2023/html/Shabani_HouseDiffusion_Vector_Floorplan_Generation_via_a_Diffusion_Model_With_Discrete_CVPR_2023_paper.html) ; [prépublication des auteurs](https://arxiv.org/abs/2211.13287).

**[R4]** Leng, S., Zhou, Y., Dupty, M. H., Lee, W. S., Joyce, S. et Lu, W. (2023). *Tell2Design: A Dataset for Language-Guided Floor Plan Generation*. ACL, 14680–14697. DOI : 10.18653/v1/2023.acl-long.820. [Publication officielle](https://aclanthology.org/2023.acl-long.820/).

**[R5]** El-Yaniv, R. et Wiener, Y. (2010). *On the Foundations of Noise-free Selective Classification*. Journal of Machine Learning Research, 11, 1605–1641. [Publication officielle](https://jmlr.org/beta/papers/v11/el-yaniv10a.html).

**[R6]** Efron, B. (1979). *Bootstrap Methods: Another Look at the Jackknife*. The Annals of Statistics, 7(1), 1–26. DOI : 10.1214/aos/1176344552. [Publication de l’Institute of Mathematical Statistics](https://projecteuclid.org/journals/annals-of-statistics/volume-7/issue-1/Bootstrap-Methods-Another-Look-at-the-Jackknife/10.1214/aos/1176344552.full).

**[R7]** Wilson, E. B. (1927). *Probable Inference, the Law of Succession, and Statistical Inference*. Journal of the American Statistical Association, 22(158), 209–212. DOI : 10.1080/01621459.1927.10502953. [Article original](https://doi.org/10.1080/01621459.1927.10502953).

**[R8]** NIST/SEMATECH. *e-Handbook of Statistical Methods*, section 7.2.4.1, « Confidence intervals ». Formulation de l’intervalle de score de Wilson. [Documentation statistique officielle](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). Consultée le 29 septembre 2026.

**[R9]** Google. *Gemini API — Image generation*. Documentation des entrées textuelles et visuelles et de l’édition d’images. [Documentation du fournisseur](https://ai.google.dev/gemini-api/docs/image-generation). Consultée le 29 septembre 2026 ; les capacités documentées ne sont pas assimilées à des résultats expérimentaux du présent article.

## Références des preuves du projet

**[P1]** A-AI. Comparaison du contrôle de parcelle : [résumé numérique](../../benchmark/comparisons/3b-parcel/summary.json) et [rapport](../../benchmark/comparisons/3b-parcel/report.md).

**[P2]** A-AI. Comparaison du placement des ouvertures : [résumé numérique](../../benchmark/comparisons/3b-openings/summary.json) et [analyse du cas `dev07/2/0`](../../benchmark/comparisons/3b-openings/report.md).

**[P3]** A-AI. Consolidation de validation polygonale : [résumé numérique](../../benchmark/comparisons/3b-polygons-final/summary.json), [observations brutes](../../benchmark/runs/3b-polygons-final/results.json) et [manifeste](../../benchmark/runs/3b-polygons-final/manifest.json).

**[P4]** A-AI. Refonte des ouvertures et cotations dans l’éditeur : [rapport comparatif](../../benchmark/comparisons/editor-openings-dimensions/report.md), [manifeste avant](../../benchmark/runs/editor-presentation-v2/manifest.json) et [manifeste après](../../benchmark/runs/editor-openings-dimensions-v1/manifest.json).

**[P5]** A-AI. [Protocole de benchmark](../../benchmark/README.md), [corpus](../../benchmark/cases/corpus.json) et [évaluateur géométrique indépendant](../../research/metrics/geometry.py).

**[P6]** A-AI. [Service de pipeline](../../services/ai/app/pipeline.py), [sélection des dispositions](../../services/ai/app/layout_select.py), [traces de génération](../../services/ai/app/generation_trace.py) et [audit scientifique](../pipeline-scientific-audit.md).

<div style="page-break-after: always; break-after: page;"></div>

## Annexe A. Exemple guidé et vérification des raisonnements

### A.1. Du besoin à une vérification interprétable

Considérons, à titre d’exemple explicatif et non d’expérience supplémentaire, une parcelle de 10 m sur 8 m avec un retrait uniforme de 1 m. L’équation (3) donne une emprise utile positive de 8 m sur 6 m. Si le programme demande une chambre de 12 m², une cuisine de 9 m² et un séjour de 20 m², la somme des surfaces cibles est 41 m². Cette somme ne dépasse pas 48 m² et satisfait donc la condition nécessaire $\sum_j t_j\leq A(\Omega)$ pour placer ces seules surfaces sans recouvrement dans l’emprise. L’égalité est admissible dans ce problème simplifié ; circulation et murs peuvent exiger une réserve supplémentaire. Le respect de cette borne ne garantit pas une disposition satisfaisante avec dimensions minimales et ouvertures.

Supposons qu’un candidat fournisse des surfaces appariées de 12, 8 et 22 m². L’équation (12) donne $(0+1/9+2/20)/3\approx0{,}07037$, soit une erreur relative moyenne de 7,04 %. Cette valeur décrit seulement la proximité aux surfaces cibles. Elle ne dit pas si la cuisine est accessible, si le séjour possède une fenêtre ou si l’utilisateur avait demandé une cuisine ouverte. Le calcul est utile parce que sa signification reste étroite et explicite.

Considérons ensuite un mur allant de $a=(10,0)$ à $b=(0,0)$, une ouverture d’offset 2 m et de largeur 0,9 m. L’équation (4) donne $p_0=(8,0)$ et $p_1=(7{,}1,0)$. L’offset est mesuré depuis la première extrémité du mur, et non depuis l’origine globale. Une implémentation qui utilise directement l’offset comme abscisse déplacerait la porte vers le mauvais côté de la façade. Cette erreur montre pourquoi les conventions de repère ont une portée scientifique autant que logicielle : elles définissent l’objet effectivement évalué.

### A.2. Lecture de la décomposition risque–couverture

Prenons les valeurs archivées après contrôle de parcelle : 85 retours sur 100 demandes, dont 84 géométriquement valides. La couverture est $0{,}85$, le risque conditionnel est $1/85$ et le produit de l’équation (10) vaut $0{,}85\times84/85=0{,}84$. Après correction de la fenêtre, le risque conditionnel observé devient nul, la couverture reste $0{,}85$ et le rendement vaut $0{,}85$.

Le premier contrôle et la seconde correction n’ont donc pas le même effet. Le contrôle de parcelle supprime des livraisons invalides ; la correction de fenêtre transforme une sortie invalide en sortie valide. Cette différence serait invisible si l’on publiait uniquement un pourcentage final. Elle est importante pour décider entre investir dans un meilleur mécanisme de refus et améliorer effectivement la génération.

### A.3. Vérification de l’intervalle de Wilson

Pour vérifier l’équation (16), on élève au carré l’inégalité du score puis multiplie par $n$ : $n(\widehat p-p)^2\leq z^2p(1-p)$. Après développement, on obtient $(n+z^2)p^2-(2n\widehat p+z^2)p+n\widehat p^2\leq0$. Les deux racines de ce polynôme de degré deux sont exactement les bornes écrites dans l’équation (16). Le coefficient du terme quadratique est positif, donc l’ensemble des solutions est l’intervalle compris entre les racines.

À titre de contrôle numérique indépendant des données du projet, pour $k=15$, $n=20$ et $z=1{,}959964$, les bornes sont approximativement 0,5313 et 0,8881. Le point estimé est 0,75, mais l’incertitude reste importante. Cet exemple n’est pas une analyse des vingt programmes du corpus : il sert à contrôler l’algèbre et à rappeler que les conditions probabilistes précèdent l’usage d’une formule.

### A.4. Portée d’une preuve négative

Une erreur observée suffit à réfuter une affirmation universelle de correction. Le cas « sans garage » réfute ainsi l’affirmation selon laquelle toutes les sorties mesurées respectent le programme. À l’inverse, l’absence d’erreur sur un corpus fini ne démontre pas une correction universelle. Le rôle du benchmark est de rendre des mécanismes observables, de tester des hypothèses et d’accumuler des preuves, pas de transformer un ensemble limité de cas en certitude générale.

Cette asymétrie justifie une pratique centrale du projet : conserver les erreurs et les cas difficiles dans les archives. Ils ne sont pas des éléments à retirer pour améliorer le taux affiché ; ils décrivent la frontière de validité de la méthode. Une architecture d’IA fiable est aussi une architecture qui permet de voir cette frontière.
