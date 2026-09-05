# Modèle de données

## Entités PostgreSQL

### users

| Colonne | Type | Description |
|---------|------|-------------|
| id | UUID PK | |
| email | CITEXT UNIQUE | |
| password_hash | TEXT | null si OAuth seul |
| name | TEXT | |
| created_at | TIMESTAMPTZ | |

### orgs

| Colonne | Type | Description |
|---------|------|-------------|
| id | UUID PK | |
| name | TEXT | |
| slug | TEXT UNIQUE | |
| created_at | TIMESTAMPTZ | |

### memberships

| Colonne | Type | Description |
|---------|------|-------------|
| org_id | UUID FK | |
| user_id | UUID FK | |
| role | TEXT | `owner` \| `architect` \| `viewer` |
| PK | (org_id, user_id) | |

### subscriptions

| Colonne | Type | Description |
|---------|------|-------------|
| id | UUID PK | |
| org_id | UUID FK UNIQUE | |
| plan | TEXT | `free` \| `pro` \| `bureau` |
| stripe_customer_id | TEXT | |
| stripe_subscription_id | TEXT | |
| status | TEXT | `active` \| `past_due` \| `canceled` |
| current_period_end | TIMESTAMPTZ | |

### usage_quotas

| Colonne | Type | Description |
|---------|------|-------------|
| org_id | UUID FK | |
| period_start | DATE | mois calendaire |
| generations_used | INT | |
| exports_used | INT | |
| gpu_minutes_used | NUMERIC | |
| PK | (org_id, period_start) | |

### projects

| Colonne | Type | Description |
|---------|------|-------------|
| id | UUID PK | |
| org_id | UUID FK | |
| name | TEXT | |
| brief | TEXT | dernier brief NL |
| status | TEXT | `draft` \| `generating` \| `ready` \| `archived` |
| current_revision_id | UUID | nullable FK logique |
| created_by | UUID FK | |
| created_at / updated_at | TIMESTAMPTZ | |

### plan_revisions

Révisions **immutables**. Toute édition crée une nouvelle ligne.

| Colonne | Type | Description |
|---------|------|-------------|
| id | UUID PK | |
| project_id | UUID FK | |
| version | INT | monotone par projet |
| source | TEXT | `ai` \| `editor` \| `import` |
| plan_document | JSONB | `PlanDocument` |
| building_spec | JSONB | `BuildingSpec` nullable |
| preview_key | TEXT | clé S3 raster |
| created_by | UUID FK | |
| created_at | TIMESTAMPTZ | |
| UNIQUE | (project_id, version) | |

### jobs

| Colonne | Type | Description |
|---------|------|-------------|
| id | UUID PK | |
| org_id | UUID FK | |
| project_id | UUID FK | |
| type | TEXT | voir ci-dessous |
| status | TEXT | `queued` \| `running` \| `succeeded` \| `failed` |
| input | JSONB | |
| output | JSONB | |
| error | TEXT | |
| created_at / started_at / finished_at | TIMESTAMPTZ | |

Types de jobs : `nlu`, `generate_2d`, `refine`, `edit_sync`, `generate_3d`, `export`.

### artifacts

| Colonne | Type | Description |
|---------|------|-------------|
| id | UUID PK | |
| project_id | UUID FK | |
| revision_id | UUID FK nullable | |
| job_id | UUID FK nullable | |
| kind | TEXT | `preview_png` \| `plan_json` \| `pdf` \| `dxf` \| `obj` \| `gltf` |
| storage_key | TEXT | chemin S3 |
| content_type | TEXT | |
| checksum_sha256 | TEXT | |
| bytes | BIGINT | |
| created_at | TIMESTAMPTZ | |

## Contrats JSON partagés

Fichiers dans `packages/plan-schema/` :

- `building-spec.schema.json`
- `plan-document.schema.json`

### BuildingSpec (sortie LLM)

```json
{
  "version": "1.0",
  "brief": "Maison 4 chambres avec garage et cuisine ouverte",
  "total_area_m2": 140,
  "floors": 1,
  "style": "contemporary",
  "rooms": [
    { "id": "r1", "type": "living", "area_m2": 35, "adjacent_to": ["r2", "r3"] },
    { "id": "r2", "type": "kitchen", "area_m2": 15, "open_to": ["r1"] },
    { "id": "r3", "type": "bedroom", "area_m2": 14, "count": 4 },
    { "id": "r4", "type": "garage", "area_m2": 20 }
  ],
  "constraints": {
    "orthogonal": true,
    "max_width_m": 14,
    "max_depth_m": 12
  }
}
```

### PlanDocument (source de vérité)

```json
{
  "version": "1.0",
  "units": "m",
  "floor": {
    "level": 0,
    "height_m": 2.7,
    "bounds": { "width": 14, "depth": 12 }
  },
  "walls": [
    {
      "id": "w1",
      "a": { "x": 0, "y": 0 },
      "b": { "x": 14, "y": 0 },
      "thickness_m": 0.2
    }
  ],
  "rooms": [
    {
      "id": "r1",
      "name": "Séjour",
      "type": "living",
      "polygon": [
        { "x": 0, "y": 0 },
        { "x": 7, "y": 0 },
        { "x": 7, "y": 6 },
        { "x": 0, "y": 6 }
      ]
    }
  ],
  "openings": [
    {
      "id": "o1",
      "wall_id": "w1",
      "type": "door",
      "offset_m": 1.2,
      "width_m": 0.9
    }
  ]
}
```

## Règles métier

1. Le raster IA n’est **jamais** la source de vérité export/3D.
2. Toute sauvegarde éditeur crée une **nouvelle** `plan_revision`.
3. Un job `generate_3d` ou `export` pointe toujours vers une `revision_id` précise.
4. Les rôles `viewer` ne peuvent ni éditer ni lancer de génération.
5. Les quotas sont vérifiés **avant** enqueue Redis.
