# API HTTP

Base URL locale : `http://localhost:8080`

Deux surfaces :

1. **Pages HTMX** — HTML partiel / full page (cookies session)
2. **API JSON** — préfixe `/api/v1` (session ou, plus tard, clé API)

Sauf mention contraire, les endpoints JSON requièrent une session authentifiée et un contexte org (`X-Org-ID` ou org courante en session).

## Auth

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/login` | Formulaire login |
| POST | `/login` | Authentification (form / HTMX) |
| GET | `/register` | Formulaire inscription |
| POST | `/register` | Création user + org personnelle |
| POST | `/logout` | Invalidation session |
| GET | `/api/v1/me` | Utilisateur + orgs courantes |

### POST `/register`

```json
{ "email": "a@b.c", "password": "••••••••", "name": "Ada", "org_name": "Studio Ada" }
```

### POST `/login`

```json
{ "email": "a@b.c", "password": "••••••••" }
```

Réponse : cookie `aai_session` + redirect `/projects`.

## Organisations

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/api/v1/orgs` | Liste des orgs de l’utilisateur |
| POST | `/api/v1/orgs` | Créer une org |
| POST | `/api/v1/orgs/{id}/invite` | Inviter un membre |
| PATCH | `/api/v1/orgs/{id}/members/{userId}` | Changer le rôle |

Rôles : `owner`, `architect`, `viewer`.

## Projets

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/projects` | Liste HTML |
| POST | `/projects` | Créer (form HTMX) |
| GET | `/projects/{id}` | Studio projet |
| GET | `/api/v1/projects` | Liste JSON |
| POST | `/api/v1/projects` | `{ "name": "...", "brief": "..." }` |
| GET | `/api/v1/projects/{id}` | Détail + révision courante |
| PATCH | `/api/v1/projects/{id}` | Renommer / mettre à jour brief |

## Génération & jobs

| Méthode | Chemin | Description |
|---------|--------|-------------|
| POST | `/api/v1/projects/{id}/generate` | Enqueue `generate_2d` |
| POST | `/api/v1/projects/{id}/generate-3d` | Enqueue `generate_3d` |
| GET | `/api/v1/jobs/{id}` | Statut job |
| GET | `/api/v1/projects/{id}/events` | SSE progression |

### POST `/api/v1/projects/{id}/generate`

```json
{
  "brief": "Maison de 4 chambres avec garage et cuisine ouverte",
  "constraints": { "total_area_m2": 140, "floors": 1 }
}
```

Réponse `202` :

```json
{ "job_id": "…", "status": "queued" }
```

### SSE `/api/v1/projects/{id}/events`

Événements :

```
event: job.updated
data: {"job_id":"…","type":"generate_2d","status":"running","step":"diffusion"}

event: plan.ready
data: {"revision_id":"…","version":1,"preview_url":"/api/v1/artifacts/…"}
```

## Révisions & éditeur

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/api/v1/projects/{id}/revisions` | Historique |
| GET | `/api/v1/revisions/{id}` | `PlanDocument` + métadonnées |
| PUT | `/api/v1/projects/{id}/plan` | Autosave éditeur → nouvelle révision |
| GET | `/projects/{id}/editor` | Page éditeur Canvas |

### PUT `/api/v1/projects/{id}/plan`

```json
{
  "plan_document": { "version": "1.0", "units": "m", "floor": {}, "walls": [], "rooms": [], "openings": [] },
  "base_revision_id": "…"
}
```

Si `base_revision_id` ≠ révision courante → `409 Conflict` (édition concurrente).

## Exports

| Méthode | Chemin | Description |
|---------|--------|-------------|
| POST | `/api/v1/revisions/{id}/export` | `{ "format": "pdf" \| "svg" \| "dxf" \| "obj" \| "gltf" }` — DXF = calques QCAD ; header `X-CAD-Tool` |
| GET | `/api/v1/artifacts/{id}` | Download signé / stream authentifié |

## Billing

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/billing` | Page plans / usage |
| POST | `/api/v1/billing/checkout` | Session Stripe Checkout |
| POST | `/api/v1/billing/portal` | Customer portal |
| POST | `/webhooks/stripe` | Webhooks Stripe (signature requise) |
| GET | `/api/v1/billing/usage` | Quotas période courante |

## API publique cabinets (phase 2)

Préfixe prévu : `/api/public/v1` avec header `Authorization: Bearer aai_…`.

Webhooks sortants :

- `plan.ready`
- `model.ready`
- `export.ready`
- `job.failed`

## Codes d’erreur JSON

```json
{
  "error": {
    "code": "quota_exceeded",
    "message": "Limite de générations atteinte pour le plan free"
  }
}
```

| Code HTTP | Exemples |
|-----------|----------|
| 400 | validation schema |
| 401 | non authentifié |
| 403 | RBAC / rôle insuffisant |
| 404 | ressource absente |
| 409 | conflit de révision |
| 402 / 429 | quota / rate limit |
| 502 | worker IA/Blender indisponible |

## Contrats workers (internes)

Go → Redis payload minimal :

```json
{
  "job_id": "…",
  "type": "generate_2d",
  "project_id": "…",
  "org_id": "…",
  "input": { "brief": "…", "constraints": {} },
  "callback_url": "http://api:8080/internal/jobs/{id}/complete"
}
```

Endpoint interne `POST /internal/jobs/{id}/complete` protégé par `INTERNAL_TOKEN`.
