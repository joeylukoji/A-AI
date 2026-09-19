# Variété des plans : les partis

Avant, tous les plans d'un même programme étaient le même pavage. Le module `layout_partis`
énumère les arrangements de zones réalisables (nuit / jour / couloir / garage, placés de
plusieurs façons), `layout_select` en choisit un. Chaque plan reste posé par le packer
déterministe : la variété vient du choix d'un arrangement, jamais de coordonnées libres.

## Interrupteur

`LAYOUT_VARIANTS` (service `ai`) :

| valeur | effet |
|---|---|
| `off` (défaut) | rien ne change, plans identiques à l'ancien moteur |
| `shadow` | on calcule et on journalise (`aai.layout`, événement `layout_shadow`), le plan reste classique |
| `on` | le plan généré porte un parti : `plan_document.layout = {parti, seed, arr}` |

Activer en local : `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.layout.yml up -d ai`.
Retour arrière : relancer sans la surcouche.

## Réglages

- `LAYOUT_TOLERANCE` (défaut `1.0`, plage 0 à 20) : fenêtre de score dans laquelle la graine tire.
  Le score compte pièces sous leur côté minimal, écart d'aire, boyaux, circulation. À 1,0 on ne
  change de maison que si l'alternative est presque aussi bonne. Monter la valeur = plus de
  variété, au prix de pièces plus étroites.
- `LAYOUT_SEED` : force la graine à la génération (reproductions, tests).

## Comportement

- La graine est tirée à la génération seulement. Une adaptation ou une retouche relit celle du
  plan et l'arrangement mémorisé (`arr`) : « ajoute une chambre » ne redessine pas toute la maison.
- Si aucun arrangement n'est réalisable, `adapt` retombe sur le moteur classique.
- Limite mesurée : environ un tiers des programmes n'a qu'un arrangement dont toutes les pièces
  respectent leur côté minimal (grand programme sur parcelle modeste, ou sans garage). Ceux-là ne
  varient pas, tant que `LAYOUT_TOLERANCE` reste bas. Piste suivante : variation à l'intérieur des zones.
