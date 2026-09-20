# Crédits des modèles 3D

Les modèles de `homekit3d/assets/` sont sous licence **CC0 1.0** (domaine public : aucun crédit n'est exigé, ils sont
cités par courtoisie), **sauf** :

* `sh3d-c` et `sh3d-luca` : **Free Art License 1.3** (http://artlibre.org/licence/lal/en/), de type copyleft : citer les
  auteurs et laisser sous la même licence les œuvres dérivées ;
* `sh3d-scopia`, `sh3d-kator`, `sh3d-bby` : **CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/) : **citer l'auteur** ;
* `vehicles` (Ferrari 458 Italia de *vicent091036*, tirée des exemples de three.js) : publiée sur Sketchfab, sous une licence
  CC BY d'après nos souvenirs — **non revérifiée** : la page d'origine n'est plus accessible. À contrôler avant tout usage
  autre que privé.

`Catalog.attributions(used)` donne la licence des packs réellement utilisés par une maison. Pour un usage strictement
CC0, il suffit d'écarter les modèles dont `license != "CC0-1.0"`.

| Pack | Auteur | Contenu | Source |
|---|---|---|---|
| `kenney-furniture` | Kenney (www.kenney.nl) | Furniture Kit 2.0 : lits, canapés, tables, cuisine, salle de bain, luminaires | https://kenney.nl/assets/furniture-kit |
| `kaykit-furniture` | Kay Lousberg (www.kaylousberg.com) | Furniture Bits 1.0 : canapés, lits, étagères, cadres, tapis, plantes | https://kaylousberg.itch.io/furniture-bits |
| `kaykit-restaurant` | Kay Lousberg (www.kaylousberg.com) | Restaurant Bits : éléments de cuisine, tables, chaises | https://kaylousberg.itch.io/restaurant-bits |
| `polyhaven` | Contributeurs de Poly Haven (polyhaven.com) | Scans détaillés à textures 1k : `ArmChair_01` (Kirill Sannikov), `Chandelier_01` (Kirill Sannikov), `ClassicNightstand_01` (Kirill Sannikov), `GreenChair_01` (Kirill Sannikov), `Ottoman_01` (Caspian Fortune), `Sofa_01` (Kirill Sannikov), `ceramic_vase_01` (James Ray Cock), `coffee_table_round_01` (Ulan Cabanilla), `desk_lamp_arm_01` (Kuutti Siitonen, Yann Kervran), `dining_chair_02` (James Ray Cock), `fancy_picture_frame_01` (Rico Cilliers, Rob Tuytel), `fancy_picture_frame_02` (Rico Cilliers, Rob Tuytel), `hanging_picture_frame_02` (James Ray Cock), `metal_office_desk` (Ulan Cabanilla), `mid_century_lounge_chair` (Kuutti Siitonen), `modern_arm_chair_01` (Vibrant Nordic), `modern_ceiling_lamp_01` (James Ray Cock), `modern_coffee_table_01` (Amin), `modern_wooden_cabinet` (Patrik Pangerl), `ornate_mirror_01` (James Ray Cock), `painted_wooden_chair_01` (Kuutti Siitonen), `painted_wooden_nightstand` (Kirill Sannikov), `potted_plant_01` (Rico Cilliers), `potted_plant_02` (Rico Cilliers), `potted_plant_04` (James Ray Cock), `side_table_01` (James Ray Cock), `sofa_02` (Kirill Sannikov), `sofa_03` (Fran Calvente), `throw_pillows_01` (Serhii Khromov), `wall_clock` (PierreB3D), `wooden_table_02` (Serhii Khromov) | https://polyhaven.com/models |
| `sh3d-b` | Contributeurs de Blend Swap, via le catalogue de Sweet Home 3D | 48 modèles réalistes (lits, canapés, cuisine, sanitaires, plantes…), CC0 | https://github.com/YoannDev90/SweetHome3D-Packs |
| `sh3d-c` | Contributeurs du catalogue « Contributions » de Sweet Home 3D 1.9.3 | 46 modèles (chambre, séjour, cuisine en bois, bains…), **Free Art License 1.3** | https://www.sweethome3d.com/freeModels.jsp |
| `sh3d-luca` | Luca Presidente (catalogue Sweet Home 3D 1.9.3) | Table, chaise, buffet et commode assortis (4 modèles), **Free Art License 1.3** | https://www.sweethome3d.com/freeModels.jsp |
| `sh3d-scopia` | Scopia (catalogue Sweet Home 3D 1.9.3) | Chaises, table ronde, lustre, canapés, fauteuils, lits, armoire, coupé sport noir (17 modèles), **CC BY 4.0** | https://www.sweethome3d.com/freeModels.jsp |
| `sh3d-kator` | Kator Legaz (catalogue Sweet Home 3D 1.9.3) | Table en verre, chaise, canapés et fauteuil « mid-century » (5 modèles), **CC BY 4.0** | https://www.sweethome3d.com/freeModels.jsp |
| `sh3d-bby` | Contributeurs de Blend Swap (jeu CC BY) | Table, chaises, commode-buffet, canapé (5 modèles), **CC BY 4.0** | https://github.com/YoannDev90/SweetHome3D-Packs |
| `vehicles` | vicent091036 | Ferrari 458 Italia (GLB Draco des exemples de three.js, décompressé par `tools/gltf_to_glb.py` et tourné vers +Z), licence à revérifier | https://github.com/mrdoob/three.js/tree/dev/examples/models/gltf |

**Textures des murs et des sols** (`assets/textures/`, Poly Haven, CC0) : `beige_wall_001` (Dimitrios Savva, Rico Cilliers), `garage_floor` (Jenelle van Heerden), `interior_tiles` (Charlotte Baglioni), `oak_wood_planks` (Dimitrios Savva), `old_wood_floor` (Guillaume Monsergent), `white_stucco` (Amal Kumar).

Les modèles `sh3d-*` sont des OBJ convertis en GLB par `tools/import_sh3d.py` ; `assets/sh3d-*/SOURCES.json` garde pour chacun
son nom d'origine et sa catégorie, et `LICENSE.txt` la licence du pack. Les fichiers de licence d'origine des packs Kenney et KayKit sont conservés à côté des modèles
(`homekit3d/assets/*/LICENSE.txt`). Poly Haven publie l'ensemble de ses modèles en CC0
(https://polyhaven.com/license) ; chaque modèle a un `<id>.license.json` avec son auteur et sa source.

## Ce dont la bibliothèque s'inspire

* **Holodeck** (Yang et al., CVPR 2024, https://arxiv.org/abs/2312.09067) : un LLM propose, un solveur place.
* **OpenHome3D** (MIT, https://github.com/Cherbooo/OpenHome3D) : source pratique des packs Kenney et KayKit rangés
  en GLB, et référence pour le catalogue de meubles CC0 d'un concepteur de maison dans le navigateur.
