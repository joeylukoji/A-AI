# A-AI — Génération de plans architecturaux 2D → 3D

Plateforme SaaS qui transforme un brief en langage naturel en plan architectural éditable, puis en maquette 3D.

## Objectifs

1. Générer des plans 2D à partir des besoins utilisateur
2. Permettre à un architecte de modifier le plan avant validation
3. Transformer le plan 2D en maquette 3D (Blender)
4. Exposer le tout en application web SaaS multi-tenant

## Stack

| Couche | Technologie |
|--------|-------------|
| UI SaaS | HTMX + Tailwind + templates Go |
| Éditeur | Canvas/SVG (JS) |
| API métier | Go (stdlib, monolithe modulaire) |
| IA | FastAPI + PyTorch (LLM → diffusion → GAN) |
| 3D | Blender headless |
| Bus | Redis (files + pub/sub) |
| Données | PostgreSQL + stockage objet S3-compatible |

## Documentation

| Document | Contenu |
|----------|---------|
| [docs/architecture.md](docs/architecture.md) | Architecture système, modules, déploiement |
| [docs/data-model.md](docs/data-model.md) | Schéma de données et `PlanDocument` |
| [docs/api.md](docs/api.md) | Endpoints HTTP et contrats jobs |
| [docs/ai-pipeline.md](docs/ai-pipeline.md) | Pipeline LLM → diffusion → GAN → 3D |
| [docs/research.md](docs/research.md) | Dataset, métriques, piste publication |
| [docs/getting-started.md](docs/getting-started.md) | Installation et démarrage local |
| [docs/product.md](docs/product.md) | Produit SaaS, plans tarifaires, roadmap |
| [docs/pipeline-scientific-audit.md](docs/pipeline-scientific-audit.md) | Audit scientifique du pipeline de génération |
| [docs/architecture-2d-audit.md](docs/architecture-2d-audit.md) | Audit de l'architecture du plan 2D |
| [docs/layout-variants.md](docs/layout-variants.md) | Variantes de partis d'aménagement |
| [docs/deploy-aws.md](docs/deploy-aws.md) | Déploiement sur AWS EC2 |
| [docs/gaps.md](docs/gaps.md) | Écarts connus et limites |

## Structure du dépôt

```
A-AI/
├── cmd/api/                 # Entrée HTTP Go
├── internal/                # Domaines métier Go
├── web/                     # Templates HTMX + assets
├── services/
│   ├── ai/                  # FastAPI (inference)
│   └── blender/             # Worker + scripts Blender
├── packages/plan-schema/    # JSON Schema partagés
├── research/                # Dataset, métriques, ablations
├── deploy/                  # Docker Compose / K8s
└── docs/                    # Documentation
```

## Démarrage rapide

Voir [docs/getting-started.md](docs/getting-started.md).

```bash
docker compose -f deploy/docker-compose.yml up --build
```

Puis ouvrir `http://localhost:8080`.

Preview clients sur une instance AWS : [docs/deploy-aws.md](docs/deploy-aws.md)
(`deploy/docker-compose.prod.yml`, pas la compose de dev).

## Tests

```bash
make test
# ou:
go test ./...
python -m pytest services/ai/tests research/metrics services/blender/tests services/qcad research/dataset -q
```

Écarts connus / roadmap manquante : [docs/gaps.md](docs/gaps.md).


## Principe produit

L’image 2D générée par l’IA est un **brouillon visuel**. La source de vérité exploitable est le **`PlanDocument`** vectoriel (pièces, murs, ouvertures, cotes), versionné et exportable (PDF, SVG/DXF, OBJ/glTF).



## Reproductibilité (évaluation scientifique)

- Toute la suite de tests est exécutable hors ligne : `make test` (Go + Python) et `node --test web/tests/` (éditeur JS).
- Les métriques géométriques et les benchmarks sont dans [`research/`](research/) (`make test-ablation` pour les ablations).
- Le contrat de validation des plans est spécifié dans [`packages/plan-schema/`](packages/plan-schema/) (`validation-profile.md`, `validation-cases.json`), partagé entre Go et Python.
- Les limites connues sont listées sans complaisance dans [docs/gaps.md](docs/gaps.md).

## Licence

Code sous licence [MIT](LICENSE). Le dataset ResPlan et les modèles 3D tiers conservent leurs propres licences : voir [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
