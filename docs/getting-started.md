# Guide de démarrage

## Prérequis

- Docker + Docker Compose
- (Optionnel) Go 1.22+, Python 3.11+, Node (Tailwind CLI) pour le dev hors conteneur
- (Optionnel) Blender 4.x en local pour tester le worker sans image Docker

## Démarrage avec Docker

```bash
cd A-AI
cp deploy/.env.example deploy/.env
docker compose -f deploy/docker-compose.yml up --build
```

LibreCAD (GPLv2) est dans ce `up` : sidecar `http://localhost:9090/healthz`. L’API utilise `QCAD_URL=http://qcad:9090`. L’export **DXF** s’ouvre dans LibreCAD ou QCAD Community pour modifier les murs / pièces.

Services :

| Service | URL |
|---------|-----|
| App web / API Go | http://localhost:8080 |
| FastAPI IA | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

Compte de démo créé au boot (si migrations seed actives) :

- Email : `demo@a-ai.local`
- Mot de passe : `demo-demo-demo`

## Parcours utilisateur local

1. Se connecter sur `/login`
2. Créer un projet
3. Saisir un brief (« maison 4 chambres avec garage »)
4. Lancer la génération (pipeline stub)
5. Ouvrir l’éditeur Canvas, ajuster un mur, autosave
6. Lancer la génération 3D
7. Télécharger un export PDF / DXF (QCAD) / OBJ — le DXF s’ouvre dans [QCAD Community](https://www.qcad.org/) (calques WALLS / ROOMS / OPENINGS)

## Dev Go hors Docker

```bash
# infra seulement
docker compose -f deploy/docker-compose.yml up postgres redis minio -d

export DATABASE_URL=postgres://aai:aai@localhost:5432/aai?sslmode=disable
export REDIS_URL=redis://localhost:6379
export SESSION_SECRET=dev-secret-change-me
export INTERNAL_TOKEN=dev-internal-token

go run ./cmd/api
```

Migrations : appliquées au démarrage de l’API (`internal/store/migrate.go`) ou via :

```bash
go run ./cmd/api -migrate-only
```

## Dev FastAPI

```bash
cd services/ai
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
AI_STUB=1 uvicorn app.main:app --reload --port 8000
```

## Variables d’environnement principales

Voir `deploy/.env.example`.

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Connexion Postgres |
| `REDIS_URL` | File de jobs |
| `S3_ENDPOINT` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` | MinIO / S3 |
| `S3_BUCKET` | Bucket artefacts |
| `SESSION_SECRET` | Signature cookies |
| `INTERNAL_TOKEN` | Auth workers → API |
| `AI_BASE_URL` | URL FastAPI vue depuis Go |
| `STRIPE_SECRET_KEY` | Billing (optionnel en local) |
| `AI_STUB` | `1` pour générateurs factices |
| `TOGETHER_API_KEY` | Clé API Together — active l'image via `black-forest-labs/FLUX.2-max` (modèles locaux mis de côté) |
| `IMAGE_BACKEND` | `together` (défaut si clé) ou `procedural` pour forcer le rendu local |
| `TOGETHER_IMAGE_MODEL` | Défaut `black-forest-labs/FLUX.2-max` |

## Structure utile

```
cmd/api/            # serveur
web/templates/      # pages HTMX
web/static/         # CSS/JS éditeur
packages/plan-schema/
services/ai/
services/blender/
research/
docs/
```

## Dépannage

| Symptôme | Piste |
|----------|-------|
| Job reste `queued` | Worker AI / Redis down ; vérifier `docker compose logs ai` |
| 403 sur projet | Mauvais org / rôle `viewer` |
| 409 sur save plan | Révision concurrente — recharger l’éditeur |
| Blender fail | Build image ~350 Mo ; logs `blender-worker` ; `AI_STUB=0` + binaire présent |
| 3D sans GLB | Vérifier MinIO bucket `aai-artifacts` et `/api/v1/projects/{id}/artifacts` |
| Stripe noop | Clés absentes → mode billing stub (plan free) |

### Note Blender

Le premier `docker compose build blender-worker` télécharge Blender 4.2.5 (~350 Mo) — prévoir plusieurs minutes.

## Recherche GAN refine

```bash
python research/dataset/make_refine_pairs.py --count 512
python research/train_gan_refine.py --epochs 20
```

Poids : `research/benchmarks/results/gan_refine/last.pt`. Voir [docs/research.md](research.md).

## Tests rapides

```bash
# health
curl -s http://localhost:8080/healthz
curl -s http://localhost:8000/healthz
```
