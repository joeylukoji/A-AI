# Pipeline IA

## Chaîne de génération

```
Brief NL
   → LLM (NLU) → BuildingSpec
   → Diffusion conditionnée → raster + layout hypothèse
   → GAN refine → raster propre / super-résolution
   → Vectorisation → PlanDocument
   → Export 2D QCAD : DXF (calques WALLS / ROOMS / OPENINGS / LABELS)
   → (optionnel) QCAD Community CLI normalise le DXF
   → (optionnel) Blender → glTF / OBJ
```

Le LLM **ne pilote pas** Blender. Il produit uniquement un JSON validé (`BuildingSpec`). Blender consomme un `PlanDocument` via un script Python déterministe.

## Étape 1 — NLU (LLM)

**Entrée** : brief texte + contraintes numériques optionnelles  
**Sortie** : `BuildingSpec` conforme à `packages/plan-schema/building-spec.schema.json`

Responsabilités :

- Extraire surface, nombre de pièces, adjacences, style
- Normaliser les types de pièces (`bedroom`, `kitchen`, `garage`, …)
- Rejeter / demander clarification si brief trop vague (mode produit futur)

Implémentation MVP : parseur heuristique + stub LLM (`services/ai/app/nlu.py`).  
Prod : appel modèle (API ou local) avec JSON Schema constrained decoding.

## Étape 2 — Diffusion 2D

**Entrée** : `BuildingSpec`  
**Sortie** : image raster (PNG) + layout intermédiaire (grilles / masques pièces)

Objectifs produit :

- Diversité et réalisme des layouts
- Respect approximatif des surfaces et adjacences

Mode stub : génération procédurale orthogonale déterministe à partir du `BuildingSpec` (pas de poids réseau requis).

### Backend API — Together AI (chemin produit)

HouseDiffusion (`model250000.pt`) et le GAN entraîné **ne génèrent plus** le plan.
Si `TOGETHER_API_KEY` est défini, la chaîne est :

**0. NLU — LLM `openai/gpt-oss-120b`.** `nlu.parse_brief` extrait le programme
(types + comptes) du brief. Filtre : pas de garage / bureau / salle à manger
inventés. Repli heuristique si `TOGETHER_NLU=0` ou JSON invalide.

**1. Disposition — même LLM.** `diffusion._llm_layout` demande un **pavage**
`{name, x, y, w, d}` qui remplit l'emprise, **exactement** les pièces du
programme (mêmes noms, même nombre). `_normalize_llm_rooms` refuse tout
chevauchement, toute pièce hors programme, et tout trou > 15 %. Si le pavage
est rejeté, `_merge_llm_program` reprend seulement les surfaces / l'ordre
(toujours sans pièce ajoutée) puis `pack_rooms` (BSP).

**2. Image.** Par défaut (`IMAGE_RENDERER=vector`) `diffusion._render_floorplan`
dessine le plan : murs poché, **mobilier du type** (lit dans une chambre, canapé
dans le séjour, etc.), portes, fenêtres, libellés **canoniques** (`Séjour`,
`Chambre 1`, `SDB`…) — jamais le texte brut du modèle. `IMAGE_RENDERER=flux`
(défaut avec clé) appelle FLUX.2-max **sans aucun texte** : l'illustration est
livrée propre, sans libellés ni lettres.

Le prompt FLUX (`diffusion._flux_prompt`, chemin `IMAGE_RENDERER=flux`) est
pilotable par `TOGETHER_IMAGE_STYLE` :

| Valeur | Rendu |
|--------|-------|
| `illustration` (défaut) | Plan vu de dessus, pièces en aplats pastel + mobilier schématique, style présentation immobilier |
| `cad` | Plan technique noir & blanc, murs poché, arcs de porte, cotes |
| `render3d` | Vue 3D « maison de poupée », toit retiré, pièces meublées |

L'image FLUX ne contient **aucun texte** (le prompt l'interdit et aucun overlay
n'est appliqué). Le rendu vectoriel de repli garde ses libellés canoniques.
`TOGETHER_IMAGE_LABELS=model` reste possible pour expérimenter mais n'est plus
le défaut.

Config : `TOGETHER_API_KEY`, `IMAGE_BACKEND=together`, `IMAGE_RENDERER`
(`vector` défaut | `flux`), `TOGETHER_PLANNER` (défaut 1), `TOGETHER_NLU`
(défaut 1), `TOGETHER_PLANNER_MODEL` (défaut `openai/gpt-oss-120b`),
`TOGETHER_PLANNER_EFFORT` (défaut `low`) — voir `deploy/.env.example`.

## Étape 3 — GAN de raffinement (contribution recherche)

**Entrée** : raster diffusion (+ éventuellement masques)  
**Sortie** : raster raffiné

Rôles scientifiques / produit :

- Nettoyage des traits
- Alignement orthogonal
- Super-résolution
- Correction topologique légère (murs semi-ouverts, bruit)

Voir [research.md](research.md) pour le protocole d’ablations.

Mode stub (`AI_STUB=1` ou pas de poids) : filtre morphologique + nettoyage binaire.

Mode réel : U-Net conditionné (image grossière + masque de pièces) → raster propre.  
Paires : `python research/dataset/make_refine_pairs.py`  
Train GPU : `python research/train_gan_refine.py` → `GAN_WEIGHTS=.../gan_refine/last.pt`.  
Le `layout` n’est **pas** modifié.

Option visuelle (pas un plan éditable) : [ControlNet Canny](https://huggingface.co/lllyasviel/sd-controlnet-canny) via `AI_STUB=0 CONTROLNET=1`. Licence OpenRAIL.

## Étape 4 — Vectorisation

**Entrée** : raster raffiné + layout  
**Sortie** : `PlanDocument`

MVP : heuristiques (composantes connexes, squelettisation, snap orthogonal, polygones pièces).  
Cible : réseau auxiliaire + règles métier.

Sans vectorisation fiable, exports et 3D restent non exploitables.

## Étape 5 — Export 2D CAD (QCAD Community)

**Entrée** : `PlanDocument`  
**Sortie** : `plan.dxf` (DXF 2000 / AC1015, unités mètres)

Le writer Go produit un DXF **ouvert et éditable** dans [QCAD Community](https://www.qcad.org/) (GPLv3) :

| Calque | Contenu |
|--------|---------|
| `WALLS` | Murs (`LINE`) |
| `ROOMS` | Polygones de pièces (`LWPOLYLINE`) |
| `OPENINGS` | Portes / fenêtres sur le mur |
| `LABELS` | Noms de pièces (`TEXT`) |

Si `QCAD_URL` (sidecar Docker) ou `QCAD_BIN` (binaire local) est joignable, l’export est **réécrit** par QCAD. Sinon le DXF Go suffit (`X-CAD-Tool: qcad-dxf`).

Image : `services/qcad/Dockerfile`, démarrée avec le compose par défaut (`make up`).

Le DWG reste hors Community (version payante QCAD). Format ouvert = **DXF**.

Script embarqué : `internal/export/qcad_normalize.js`.

## Étape 6 — Génération 3D (Blender)

**Entrée** : `PlanDocument` (révision validée)  
**Sortie** : `.glb` + `.obj` (+ preview optionnelle)

Script : `services/blender/scripts/build_model.py`

Algorithme :

1. Créer le plancher selon `floor.bounds`
2. Extruder chaque mur (`thickness_m`, `floor.height_m`) depuis le catalogue `wall.exterior` / `wall.interior`
3. Découper les ouvertures (portes / fenêtres)
4. Instancier le mobilier `furniture[]` depuis le catalogue (chaises, lits, tables…) — pas de Flux
5. Exporter glTF + OBJ

Catalogue : `services/blender/catalog/` (recettes paramétriques réutilisables ; GLB CC0 optionnel dans `catalog/glb/`).

## Orchestration jobs

Job parent `generate_2d` (vu par l’utilisateur) enchaîne en interne :

1. `nlu`
2. `generate` (diffusion)
3. `refine` (GAN)
4. `vectorize`

Échec d’une sous-étape → `jobs.status = failed` + message SSE.

Job `generate_3d` est indépendant et nécessite une `revision_id`.

## Fichiers de service

```
services/ai/
├── app/
│   ├── main.py          # FastAPI
│   ├── nlu.py
│   ├── diffusion.py
│   ├── gan_refine.py
│   ├── vectorize.py
│   └── stubs.py
├── requirements.txt
└── Dockerfile

services/blender/
├── worker.py              # queue Redis + upload MinIO
├── s3util.py
├── scripts/build_model.py # Blender 4.2 headless → OBJ/GLB
└── Dockerfile             # Ubuntu + Blender 4.2.5 (~350 Mo)

internal/export/
├── dxf.go                 # DXF 2000 calques QCAD
├── qcad.go                # QCAD_URL (Docker) ou QCAD_BIN (local)
└── qcad_normalize.js      # -no-gui -autostart

services/qcad/             # sidecar Compose par défaut
├── Dockerfile             # Ubuntu 22.04 + paquet apt qcad
└── server.py              # POST /normalize
```

Artefacts 3D : MinIO (`aai-artifacts`) + table `artifacts` ; lecture via `GET /api/v1/artifacts/{id}/content`.

## Variables d’environnement IA

| Variable | Défaut | Rôle |
|----------|--------|------|
| `AI_STUB` | `1` | Active les générateurs factices (GAN refine = stub) |
| `GAN_WEIGHTS` | | Checkpoint pix2pix `last.pt` (GPU, `AI_STUB=0`) |
| `CONTROLNET` | | `1` = raffiner avec [ControlNet Canny](https://huggingface.co/lllyasviel/sd-controlnet-canny) |
| `REDIS_URL` | | File de jobs |
| `S3_ENDPOINT` | | Stockage artefacts |
| `INTERNAL_TOKEN` | | Auth callbacks Go |
| `MODEL_WEIGHTS_DIR` | | Poids diffusion / GAN (prod) |
| `QCAD_BIN` | | Binaire QCAD local (`qcad` / `qcadcmd`) |
| `QCAD_URL` | | Sidecar Docker `http://qcad:9090` (profil `qcad`) |

## Latence cible (MVP stub)

| Étape | Budget |
|-------|--------|
| NLU stub | < 100 ms |
| Diffusion stub | < 1 s |
| GAN stub | < 500 ms |
| Vectorize | < 1 s |
| Blender (plan simple) | < 30 s |

Budgets GPU réels seront mesurés dans `research/benchmarks/`.
