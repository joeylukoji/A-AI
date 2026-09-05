# Écarts / ce qui manque

État au moment de l’ajout de la suite de tests. Priorisé pour le MVP.

Liste consolidée (recherche + produit + API) : [ameliorations.md](ameliorations.md).

## Bugs corrigés avec les tests

- Pipeline IA `422` quand `constraints: null` (Go + Pydantic)
- Spam `Timeout reading from socket` du worker Blender (socket Redis)

## Manques fonctionnels

| Domaine | Manque | Priorité |
|---------|--------|----------|
| IA | Vrais modèles diffusion / GAN (poids entraînés) | Haute (recherche) |
| IA | LLM réel (API) pour NLU — heuristiques seulement | Haute |
| 3D | ~~Image Docker Blender + MinIO~~ (fait : Blender 4.2.5, GLB/OBJ → MinIO, viewer) | — |
| 3D | Découpe portes/fenêtres dans Blender, multi-étages | Moyenne |
| Exports | DWG / IFC (hors MVP) | Basse |
| Auth | OAuth (Google/GitHub) | Moyenne |
| Billing | Stripe Checkout / Portal / webhooks réels | Moyenne |
| API cabinets | Clés API publiques + webhooks sortants | Moyenne |
| Multi-étages | Un seul niveau dans éditeur / génération | Moyenne |
| Preview raster | ~~PNG persisté~~ via `image_png_b64` + `/api/v1/projects/{id}/preview` | — |
| Observabilité | OpenTelemetry complet (traces exporters) | Basse |
| CI | Pipeline GitHub Actions (tests Go + pytest) | Haute |
| Dataset | FloorPlanCAD Kaggle branché (images+YOLO) ; ResPlan pickle toujours optionnel | Moyenne |
| Sécu | Rate limiting, CSRF HTMX, scan dépendances automatisé | Moyenne |

## Manques qualité / ops

- Pas de tests d’intégration E2E automatisés (login → generate → export) dans CI
- Pas de `.env` de prod / secrets manager
- ~~Healthchecks Compose incomplets sur `api` / `ai`~~
- ~~Favicon manquant~~
- Encodage labels FR parfois cassé selon locale console (UTF-8 OK en HTTP)

## Couverture de tests actuelle

- Go : `domain`, `export`, `billing` (unit + quota DB optionnel), `auth` (slugify), `jobs` (queues), `httpapi` (healthz), `plan-schema`
- Python : pipeline FastAPI (dont `constraints: null`), NLU, orthogonalité, métriques, stub Blender

Lancer :

```bash
go test ./...
pytest services/ai/tests research/metrics services/blender/tests -q
```
