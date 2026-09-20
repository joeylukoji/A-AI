# homekit3d

Composants 3D **réutilisables** pour construire des maisons : murs avec de vraies ouvertures, sols, portes, fenêtres,
un catalogue de 214 meubles et objets sous licence CC0, l'ameublement automatique d'un plan vierge, et un styliste
assisté par un LLM. Une maison de 12 pièces se construit en **moins de 5 secondes** (Blender compris) et pèse
environ 0,5 Mo en GLB.

C'est un projet à part : il ne dépend d'aucun code d'A-AI. A-AI l'utilise (voir plus bas), mais on peut le copier
dans n'importe quel autre projet, avec ou sans lui fournir un plan A-AI.

```
libs/homekit3d/
  homekit3d/            le paquet Python
    assets/             342 modèles GLB (4 packs CC0) + leurs licences
    catalog/manifest.json   rôle, dimensions réelles, échelle, licence de chaque modèle (généré)
    plan.py             modèle de plan + outils pour le construire
    geometry.py         murs, ouvertures, sols (Python pur, testable sans Blender)
    assemble.py         du plan aux objets à poser (choix du modèle, échelle, cuisine en file)
    layout.py, furnish.py   placement et ameublement automatique
    stylist.py, llm.py  style et décor : un LLM propose, un solveur dispose
    blender_scene.py    scène Blender + export GLB / OBJ
    cli.py              python -m homekit3d build plan.json maison.glb
  tools/                génération du manifeste, planche-contact, rendu de contrôle
  examples/villa.py     une maison construite avec les seuls outils de la bibliothèque
  tests/                des tests unitaires par module et l'intégration avec un vrai Blender
```

## Démarrage

Il faut Python 3.10+ et Blender 4.2+ (testé avec 4.2.5 et 5.1.1).

```python
from homekit3d import Catalog, Plan
from homekit3d.stylist import Stylist

plan = Plan(width=12.0, depth=9.0, seed=7)               # mètres ; x à droite, y vers le bas comme un plan
plan.rect_room("living", 0, 0, 6, 5, name="Séjour")
plan.rect_room("bedroom", 0, 5, 4.5, 9, name="Chambre")
plan.outline()                                            # murs extérieurs
plan.walls_from_rooms()                                   # une cloison par arête commune
plan.door(plan.wall_at(2.0, 5.0), 1.2)                    # porte sur le mur qui passe par ce point
plan.window(plan.wall_at(3.0, 0.0), 1.5, width=1.4)
plan.place("sofa", x=3.0, y=4.2, rot=180, room="r1")     # ou laissez le styliste meubler
Stylist(Catalog.load()).style(plan)                       # style, ameublement des pièces vides, décor
```

```
python -m homekit3d build plan.json maison.glb --stats stats.json          # Blender est retrouvé tout seul
python -m homekit3d build plan.json maison.glb --obj maison.obj --no-ai    # OBJ en plus, sans appel LLM
python -m homekit3d catalog --role sofa                                    # explorer le catalogue
```

`build` accepte un plan de la bibliothèque (`Plan.to_dict()`) **ou** un `PlanDocument` d'A-AI (murs, pièces,
ouvertures, mobilier déjà posé). Blender est cherché dans `--blender`, `BLENDER_BIN`, le `PATH` puis les
dossiers usuels.

## Comment ça marche

1. **Coque** (`geometry.py`). Chaque mur est découpé en boîtes autour de ses ouvertures : plein, allège sous une
   fenêtre, linteau au-dessus. Pas d'opération booléenne (lente et fragile) : le volume est exact et testé. Les
   chambranles, vantaux, poignées, vitrages (translucides) et sols (un matériau par type de pièce) suivent. La face
   intérieure et la face extérieure d'un mur reçoivent chacune leur peinture, quel que soit le sens de tracé.
2. **Catalogue** (`catalog.py`, `tools/build_manifest.py`). Chaque modèle a un *rôle* (`bed.double`, `sofa`,
   `kitchen.stove`…). Les packs n'ont pas la même échelle : un canapé Kenney fait 0,98 m, celui de KayKit 3,0 m. Le
   manifeste ramène chaque rôle à une **taille réelle** (`ROLE_FIT`), après application de la hiérarchie de nœuds du
   GLB (les modèles exportés d'Unity portent des rotations et des échelles sur leurs nœuds : les ignorer donnait des
   toilettes tournées et réduites de moitié).
3. **Assemblage** (`assemble.py`). Pour chaque objet : le modèle du rôle dont l'emprise réelle ressemble le plus à
   celle demandée (tirage déterministe par graine), un facteur d'échelle borné (jamais un meuble déformé), la pose
   contre les murs. Un plan de travail de cuisine devient une **file d'éléments** qui remplit exactement sa longueur,
   avec un évier, en laissant la place de la cuisinière et du frigo. Voiture et cheminée, absentes des packs, sont
   construites par code (`procedural.py`).
4. **Ameublement** (`furnish.py`). Pour un plan vierge : dispositions courantes par type de pièce (lit tête au mur et
   chevets, canapé face au meuble télé, cuisine en file le long du plus long mur, salle à manger…), posées
   seulement là où il y a de la place et hors du battant des portes.
5. **Styliste** (`stylist.py`). Le principe est celui de [Holodeck](https://arxiv.org/abs/2312.09067) : le LLM
   apporte le bon sens (quel style, quel décor pour quelle pièce) mais **ne place jamais rien** ; sa réponse est
   validée (styles, rôles et pièces connus, quatre objets de décor par pièce au plus), puis un solveur déterministe
   cherche la place. Sans LLM, avec une réponse invalide ou trop lente (12 s), les mêmes choix sont faits par des
   règles à graine : **le résultat est identique d'un lancement à l'autre**, et un LLM en panne ne bloque rien.
6. **Blender** (`blender_scene.py`). Chaque modèle est importé **une seule fois** ; les meubles sont des objets qui
   partagent ses maillages (instances liées), et l'exportateur glTF n'écrit qu'un maillage. C'est ce qui tient le
   temps : dix chaises coûtent un import.

Le LLM est configuré par `HOMEKIT_LLM_URL`, `HOMEKIT_LLM_KEY`, `HOMEKIT_LLM_MODEL` (tout service « chat
completions » compatible OpenAI), à défaut `TOGETHER_API_KEY`. `HOMEKIT_LLM=0` le coupe. La clé n'est jamais mise
dans un prompt.

## Performances (mesurées)

Plan A-AI de 14 pièces, 26 instances, 19 modèles distincts, Blender 5.1 sur un poste de bureau :

| étape | temps |
|---|---|
| coque (Python + Blender) | 0,1 à 0,5 s |
| import des modèles (une fois chacun) | 0,3 à 0,7 s |
| pose des instances | < 0,05 s |
| export GLB | 0,8 à 1,3 s |
| **total, démarrage de Blender compris** | **4 à 5 s** (budget : 30 s) |

Un test d'intégration (`tests/test_blender.py`) échoue au-delà de 30 s.

## Ajouter des modèles

1. Déposer les GLB dans `homekit3d/assets/<pack>/` avec leur fichier de licence, déclarer le pack dans
   `PACKS` de `tools/build_manifest.py` (auteur, licence, source, style).
2. Ajouter des règles `RULES` (nom → rôle, pièces, étiquettes) et, pour un nouveau rôle, sa taille réelle dans
   `ROLE_FIT`.
3. `python tools/build_manifest.py`, puis `blender -b --python tools/contact_sheet.py -- planche.png <rôles>` pour
   vérifier à l'œil l'échelle et l'orientation (la face d'un meuble regarde vers +Z glTF).

`tools/fetch_polyhaven.py` télécharge des modèles depuis Poly Haven (CC0) pour compléter le catalogue avec des
pièces plus détaillées ; ils sont plus lourds que les packs low-poly, à réserver aux pièces maîtresses.

## Licences et crédits

Le code de `homekit3d/` est sous licence MIT (`LICENSE`). Les modèles sont sous **CC0** : aucun crédit n'est exigé,
mais [ATTRIBUTION.md](ATTRIBUTION.md) les cite. `Catalog.attributions(used)` liste les packs réellement utilisés par
une maison.

## Ce que cette version ne fait pas

* Des murs droits (les plans testés sont orthogonaux) ; pas de murs courbes, d'étages ni de toits.
* L'ameublement automatique suppose des pièces rectangulaires (leur boîte englobante) ; une pièce en L est meublée
  dans sa boîte, hors des zones qui n'appartiennent pas à la pièce elle-même.
* Les packs de base sont *low-poly* et cohérents entre eux ; seules les pièces Poly Haven du style `premium` (cinq
  aujourd'hui : deux fauteuils, une chaise, une table basse, un buffet) sont détaillées et texturées.
* Les portes sont dessinées fermées ; un utilisateur ne peut pas encore choisir un modèle de porte du catalogue.
