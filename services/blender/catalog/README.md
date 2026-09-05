# Catalogue 3D A-AI

Composants **réutilisables** instanciés par Blender à partir du `PlanDocument`.
Pas de Flux, pas de mesh génératif : un ID de catalogue + une pose.

| `catalog_id` | Rôle |
|---|---|
| `wall.exterior` / `wall.interior` | Murs extrudés depuis `walls[]` |
| `chair.dining` | Chaise |
| `bed.single` / `bed.double` | Lit |
| `table.dining` | Table à manger |
| `table.coffee` | Table basse |
| `sofa.2seat` | Canapé |
| `nightstand` / `wardrobe` | Chambre |
| `counter.kitchen` | Plan de travail |

Les recettes par défaut sont paramétriques (boîtes aux dimensions catalogue).
Pour remplacer un composant par un GLB CC0, déposer `glb/<catalog_id>.glb`
(exemple : `glb/chair.dining.glb`). Licences propriétaires interdites.
