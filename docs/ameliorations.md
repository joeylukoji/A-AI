# Améliorations A-AI

Liste unique de ce qui est fait, de ce qui manque, et de l’ordre pour y arriver.

Dernière mise à jour : 23 août 2026 (parcours produit complété : éditeur, ouvertures, preview, QCAD, healthchecks).

Trois livrables distincts (ne pas les confondre) :

1. **Plan éditable** — un `PlanDocument` géométriquement vrai
2. **GAN layout-aware** — angle papier (image + masques → image propre)
3. **API réelle** — brancher les poids dans `gan_refine.py` (aujourd’hui un stub)

Le DCGAN bruit→image a été retiré du dépôt : il ne produisait aucun de ces trois.

---

## Déjà en place

| Zone | État |
|------|------|
| Produit MVP stub | Auth, orgs/RBAC, projets, révisions, jobs, exports PDF/SVG/DXF QCAD/OBJ/glTF |
| UI | HTMX + éditeur Canvas + viewer 3D |
| Pipeline FastAPI | NLU heuristique → diffusion procédurale → `gan_refine` stub → vectorize stub |
| 3D | Blender 4.2.5 headless, GLB/OBJ → MinIO |
| Infra | Postgres, Redis, Stripe stub, compte `demo@a-ai.local` |
| Corpus | Non versionné (re-téléchargeable via `download.py` si besoin) |
| Train GPU | Refine pix2pix : `train_gan_refine.py` → `gan_refine/last.pt` |

Bugs déjà corrigés : pipeline `422` si `constraints: null` ; timeouts Redis Blender.

---

## 1. Plan éditable

La source de vérité est le **`PlanDocument`** (`packages/plan-schema/plan-document.schema.json`) : murs, polygones de pièces, ouvertures. L’éditeur et Blender ne lisent que ça.

### Pourquoi ce n’est pas encore « un vrai plan appris »

- FloorPlanCAD = bbox meubles / portes, **pas** de polygones de pièces
- `floorplancad_convert.py` **invente** des pièces autour des meubles
- `vectorize.py` recopie le `layout` procédural, il ne lit pas le raster
- L’éditeur ne permet pas encore d’ajouter pièces / ouvertures proprement

### Améliorations

| # | Action | Priorité |
|---|--------|----------|
| P1 | Garder le layout procédural comme plan éditable produit (déjà là) | — |
| P2 | ~~Éditeur : ajouter / supprimer pièces, portes, fenêtres ; snap orthogonal~~ | Fait |
| P3 | Vectorisation réelle du raster (squelette, composantes connexes, snap) | Haute (si on veut un plan issu de l’image) |
| P4 | Corpus vecteur (ResPlan pickle Zenodo, ou CubiCasa SVG) pour vérité terrain | Haute (recherche + qualité) |
| P5 | ~~Valider topologie à chaque save~~ (orthogonal, ouvertures accrochées, 4 murs) | Fait |
| P6 | ~~Découpe portes / fenêtres dans Blender~~ (booléen sur les cutters) | Fait |
| P7 | Multi-étages dans schéma + éditeur | Moyenne |

Sans P3 ou P4, le GAN restera une **image**, jamais un plan qu’on déplace dans le Canvas.

---

## 2. Raffinement layout-aware (angle papier)

Pas « bruit → image ». Objectif :

> Raster (et masques de pièces / `BuildingSpec`) → **même layout**, traits nets, orthogonal, éventuellement super-résolution.

Architecture cible : **pix2pix / SPADE / RefineGAN**, pas le DCGAN actuel.

### Données à construire

FloorPlanCAD tout seul ne fournit **pas** de paires `(plan sale, plan propre)`.

| # | Action | Priorité |
|---|--------|----------|
| R1 | ~~Paires PlanDocument~~ `make_refine_pairs.py` (clean + dégradé + masque) | Fait |
| R2 | ~~Conditionnement masque pièces + image grossière~~ (2 canaux) | Fait |
| R3 | ~~`train_gan_refine.py` pix2pix GPU~~ | Fait (à lancer) |
| R4 | Ablations : diffusion seule vs diffusion+GAN ; avec / sans masques ; avec / sans adjacences `BuildingSpec` | Haute (papier) |
| R5 | Métriques : FID/KID **et** IoU par pièce, murs fermés, orthogonalité, conformité brief | Haute |
| R6 | Run DCGAN 80 epochs / `--limit 0` = **smoke test GPU + data**, pas le modèle papier | Basse |
| R7 | Étude architectes N≥10 (préférence / éditabilité) | Moyenne (R3 recherche) |
| R8 | Dataset enrichi ~6k synthèses contrôlées (`synthesize.py`) | Moyenne |

Licence : poids issus de FloorPlanCAD = **mémoire / preprint seulement**. Pour un modèle « produit », réentraîner sur synthèse A-AI + corpus CC-BY (ResPlan).

### Ce que le DCGAN actuel n’est pas

- Pas conditionné par le layout
- 64×64, trop petit pour du CAD 640×640
- `last.pt` incompatible avec un refine (1 canal, from noise)
- Ne pas le brancher sur l’API

---

## 3. Brancher l’API (`gan_refine.py`)

Déjà en place : `POST /v1/refine` et le pipeline `nlu → generate → refine → vectorize`.

Le stub fait un filtre PIL (contraste + médian + seuillage) et renvoie `method: gan_refine_stub`.

| # | Action | Priorité |
|---|--------|----------|
| A1 | Checkpoint dédié `gan_refine/last.pt` (pas le DCGAN FloorPlanCAD) | Fait |
| A2 | ~~`GAN_WEIGHTS` + GPU ; sinon stub~~ (`AI_STUB=1` force le stub) | Fait |
| A3 | ~~`refine()` U-Net ; layout inchangé~~ | Fait |
| A4 | ~~`method: gan_refine_v1` / `gan_refine_stub`~~ | Fait |
| A5 | ~~Persister le PNG raffiné~~ (`image_png_b64` → MinIO, `/preview`) | Fait |
| A6 | Poids **commercialisables** pour le SaaS (pas FloorPlanCAD) | Haute (prod) |
| A7 | Variable `AI_STUB=1` inchangée pour les tests CI sans GPU | Haute |

Le plan éditable continue de sortir de **`vectorize`**, pas du GAN.

---

## 4. Reste produit / ops

Repris et priorisé depuis [gaps.md](gaps.md).

| # | Action | Priorité |
|---|--------|----------|
| X1 | LLM réel pour le NLU (API ou local, JSON Schema) | Haute |
| X2 | Vraie diffusion conditionnée par `BuildingSpec` (produit) | Haute |
| X3 | Stripe Checkout / Portal / webhooks réels | Moyenne |
| X4 | OAuth Google / GitHub | Moyenne |
| X5 | Clés API publiques + webhooks cabinets | Moyenne |
| X6 | Rate limiting, CSRF HTMX, scan dépendances (Snyk) | Moyenne |
| X7 | E2E CI : login → generate → export | Moyenne |
| X8 | ~~Healthchecks Compose `api` / `ai`~~ | Fait |
| X9 | DWG (QCAD Pro) / IFC — le DXF QCAD Community est déjà dans la pipeline | Basse |
| X10 | `.env` prod / secrets manager | Moyenne |
| X11 | ~~Favicon~~ `/static/favicon.svg` | Fait |

---

## Ordre recommandé

```
Produit éditable (P1–P2, P5)
    → paires synthétiques + GAN refine (R1–R3)
        → ablations / métriques (R4–R5)     ← papier
        → brancher API avec fallback (A1–A3, A7)
            → poids CC-BY pour le SaaS (A6)
```

En parallèle possible : P6 (découpes Blender), X1 (LLM), dataset ResPlan (P4).

---

## Commandes utiles (recherche)

```powershell
python research/dataset/make_refine_pairs.py --count 512
python research/train_gan_refine.py --epochs 20
```

Poids : `research/benchmarks/results/gan_refine/last.pt`.

---

## Hors scope volontaire

- Brancher `last.pt` du DCGAN dans FastAPI
- Déployer un modèle FloorPlanCAD en production payante
- Remplacer le `PlanDocument` par une image GAN comme source de vérité
