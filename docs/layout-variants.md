# Variété des plans : les partis

Avant, tous les plans d'un même programme étaient le même pavage. Le module `layout_partis`
énumère les arrangements de zones réalisables (nuit / jour / couloir / garage, placés de
plusieurs façons), `layout_select` en choisit un. Chaque plan reste posé par le packer
déterministe : la variété vient du choix d'un arrangement, jamais de coordonnées libres.

## Interrupteur

`LAYOUT_VARIANTS` (service `ai`) :

| valeur | effet |
|---|---|
| `on` (défaut) | le plan généré porte un parti : `plan_document.layout = {parti, seed, arr}` ; le moteur classique ne sert que si aucun parti n'est réalisable |
| `shadow` | on calcule et on journalise (`aai.layout`, événement `layout_shadow`), le plan reste celui du classique |
| `off` | retour arrière : moteur classique seul |

Une valeur inconnue (faute de frappe) donne `off`.

Pourquoi `on` par défaut : sur 200 programmes, le classique laisse le couloir à 24 % de la maison (partis :
11 %), rate la surface du garage de 80 % (partis : 9 %) et produit des chambres sous le minimum ; les
partis sont meilleurs sur chacun de ces points.

## Réglages

- `LAYOUT_TOLERANCE` (défaut `2.0`, plage 0 à 20) : fenêtre de score dans laquelle la graine tire. Le score
  compte les pièces sous leur côté minimal, l'écart de surface moyen et celui de la pire pièce, les boyaux,
  la circulation. Un parti dont une pièce d'habitation ou la cuisine a un rapport d'aspect supérieur à 3 n'est
  tiré que si tous les autres le dépassent aussi. Monter la valeur = plus de variété, au prix de pièces plus
  étroites.
- `LAYOUT_SEED` : force la graine à la génération (reproductions, tests).

## Surfaces demandées

Le plan embarque `program` : les pièces demandées, une entrée par pièce. L'adaptation (`plan_adapt`) vise ces
surfaces. Avant, elle n'avait que les polygones du premier tracé, donc reproduisait ses déformations (un couloir
de 31 m² en cinq « pièces »). Un plan modifié à la main dont les types de pièces ont changé n'utilise pas le
programme ; les segments de couloir y sont alors fusionnés en un seul, plafonné à 10 % de la maison.

## Comportement

- La graine est tirée à la génération seulement. Une adaptation ou une retouche relit celle du
  plan et l'arrangement mémorisé (`arr`) : « ajoute une chambre » ne redessine pas toute la maison.
- Si aucun arrangement n'est réalisable, `adapt` retombe sur le moteur classique.
- Limite mesurée : environ un tiers des programmes n'a qu'un arrangement dont toutes les pièces
  respectent leur côté minimal (grand programme sur parcelle modeste, ou sans garage). Ceux-là ne
  varient pas, tant que `LAYOUT_TOLERANCE` reste bas. Piste suivante : variation à l'intérieur des zones.
