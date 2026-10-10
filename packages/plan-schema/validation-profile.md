# Profil de validation 2D — géométrie du document, v1.2

Ce profil exécuté par Python et Go complète, mais ne remplace pas, le JSON Schema.
Les deux contrôles ont des périmètres distincts : le profil d'exécution valide la
géométrie et ignore les métadonnées inconnues; le schéma JSON est un contrat
déclaratif plus strict pour les consommateurs qui choisissent de l'appliquer.
Un document accepté par le profil géométrique n'est donc pas nécessairement
valide selon le schéma. Ce profil ne certifie ni conformité réglementaire ni
faisabilité constructive.

## Contrat

- Objet JSON, `version: "1.0"`, `units: "m"` ; `floor.bounds.width/depth`
  sont des nombres finis strictement positifs. Aucune coercition booléen/chaîne/null.
- `walls` et `rooms` sont des tableaux obligatoires. `openings` est facultatif
  (absence = tableau vide), mais null n'est pas un tableau.
- Au moins quatre murs. Chaque mur a un ID chaîne non vide unique, deux points
  numériques finis, une longueur > 1e-6 m, et est orthogonal à 1e-6 m près.
  Ses points restent dans l'emprise, à 1e-6 m près.
- Les quatre côtés du rectangle d'emprise sont couverts par les murs, sans
  trou > 1e-6 m (tolérance par trou, pas cumulée). Les deux extrémités d'un mur
  doivent être à <= 1e-6 m du côté. Murs fractionnés, inversés ou aux IDs
  arbitraires admis. Les ouvertures ne retirent pas le mur porteur du contour.
- Chaque pièce a un ID chaîne non vide unique et au moins trois sommets finis,
  dans l'emprise. Aire algébrique absolue > 1e-6 m², calculée par triangulation
  autour du premier sommet pour limiter la cancellation. Les triangles et les
  deux orientations sont acceptés ; une liste de pièces vide reste autorisée
  pour compatibilité avec les documents en cours d'édition.
- Le contour d'une pièce doit être simple : arêtes non nulles, aucun sommet
  répété sauf le sommet final identique au premier, aucun retour collinéaire
  ni intersection/contact d'arêtes non adjacentes. Les sommets collinéaires
  parcourus dans le même sens restent permis.
- Deux pièces peuvent partager un bord ou un point ; leur intersection
  intérieure a une aire <= 1e-6 m². L'aire est intégrée par bandes horizontales
  découpées aux sommets et aux intersections des arêtes, après validation des
  contours. Chaque bande additionne la largeur des intervalles communs.
- Le coût du contrôle est borné par profil : au plus 64 pièces, 64 sommets par
  pièce et 256 sommets au total. Dépassement : `geometry_complexity_limit`.
  Ce plafond décrit la capacité du MVP ; ce n'est pas une norme architecturale.
- Chaque ouverture a un ID chaîne non vide unique, une référence de mur connue,
  un type `door` ou `window`, un offset fini, une largeur finie > 0, et une
  extrémité calculée finie. Intervalle dans le mur à 1e-6 m près. Intersection
  intérieure entre ouvertures d'un même mur <= 1e-6 m. Contact exact admis.
- Une porte peut omettre ensemble `hinge` et `swing` (compatibilité historique),
  ou déclarer la paire complète. `hinge` vaut `start|end`; `swing` vaut
  `positive|negative`, où `positive` désigne la normale gauche du mur orienté
  de `a` vers `b`. Une paire partielle et ces propriétés sur une fenêtre sont
  interdites.
- L'unicité est propre à chaque collection. Aucune réparation ni mutation.
- Les métadonnées inconnues sont ignorées par le contrôle géométrique, pas
  supprimées du document. `layout`, `program` et les nouveaux types de mobilier
  restent compatibles avec ce contrôle; ils peuvent nécessiter une mise à jour
  du JSON Schema avant de satisfaire son contrat déclaratif.

## Erreurs et frontières

Codes stables du contrat : `invalid_structure`, `invalid_header`, `invalid_number`,
`invalid_bounds`, `insufficient_walls`, `invalid_wall_id`, `invalid_wall_point`,
`invalid_wall_segment`, `point_out_of_bounds`, `invalid_room_id`,
`invalid_room_polygon`, `invalid_opening_id`, `unknown_wall`,
`invalid_opening_type`, `invalid_opening_width`, `opening_out_of_bounds`,
`overlapping_openings`, `invalid_door_semantics`,
`invalid_door_semantic_value`, `incomplete_perimeter`, `overlapping_rooms`.
Le dépassement de capacité utilise `geometry_complexity_limit`.
Les fixtures comparent les codes, pas les messages.

Go conserve l'enveloppe HTTP existante 400/`invalid_plan`; son erreur métier
expose `ValidationError.Code`. Python expose `PlanDocumentError.code` et traduit
une **sortie générée** invalide en erreur interne 500, pas en erreur utilisateur 422.
Un JSON Go non décodable produit `invalid_json` avant le contrôle du document.
Python reçoit un objet déjà décodé par son adaptateur.

## Limites à lever dans le bloc suivant

La correspondance pièces/murs et la validité du mobilier ne sont pas
encore contrôlés ici. Le contrôle de simplicité détecte aussi les contours
croisés dont l'aire algébrique reste non nulle. Un succès de ce profil ne suffit
donc pas à déclarer le plan conforme ou constructible.
Le benchmark indépendant conserve ses contrôles supplémentaires. La validation
géométrique ne démontre ni accessibilité, ni ventilation, ni épaisseurs ou
conformité aux réglementations de construction.
La couverture contrôlée est celle du rectangle `floor.bounds`, pas d'une
enveloppe libre concave. Elle ne vérifie ni épaisseurs ni assemblages constructifs.

## Fixtures partagées

`validation-cases.json` contient un document de base et des mutations `set`/`remove`
avec chemin JSON sous forme de liste. Chaque test clone la base. Un chemin vide
remplace la racine. `code: null` indique une acceptation attendue. Les erreurs
multiples n'ont pas de priorité publique garantie.
