# A-AI — 2D → 3D architectural floor plan generation

A SaaS platform that turns a natural-language brief into an editable architectural floor plan, then into a 3D model.

## Goals

1. Generate 2D floor plans from user requirements
2. Let an architect edit the plan before validation
3. Turn the 2D plan into a 3D model (Blender)
4. Deliver everything as a multi-tenant SaaS web application

## Stack

| Layer | Technology |
|-------|------------|
| SaaS UI | HTMX + Tailwind + Go templates |
| Editor | Canvas/SVG (JS) |
| Business API | Go (stdlib, modular monolith) |
| AI | FastAPI + PyTorch (LLM → diffusion → GAN) |
| 3D | Headless Blender |
| Bus | Redis (queues + pub/sub) |
| Data | PostgreSQL + S3-compatible object storage |

## Documentation

The detailed documentation in `docs/` is written in French.

| Document | Contents |
|----------|----------|
| [docs/architecture.md](docs/architecture.md) | System architecture, modules, deployment |
| [docs/data-model.md](docs/data-model.md) | Data schema and `PlanDocument` |
| [docs/api.md](docs/api.md) | HTTP endpoints and job contracts |
| [docs/ai-pipeline.md](docs/ai-pipeline.md) | LLM → diffusion → GAN → 3D pipeline |
| [docs/research.md](docs/research.md) | Dataset, metrics, publication track |
| [docs/getting-started.md](docs/getting-started.md) | Installation and local setup |
| [docs/product.md](docs/product.md) | SaaS product, pricing plans, roadmap |
| [docs/pipeline-scientific-audit.md](docs/pipeline-scientific-audit.md) | Scientific audit of the generation pipeline |
| [docs/architecture-2d-audit.md](docs/architecture-2d-audit.md) | Audit of the 2D plan architecture |
| [docs/layout-variants.md](docs/layout-variants.md) | Layout variants |
| [docs/deploy-aws.md](docs/deploy-aws.md) | Deployment on AWS EC2 |
| [docs/gaps.md](docs/gaps.md) | Known gaps and limitations |

## Repository layout

```
A-AI/
├── cmd/api/                 # Go HTTP entry point
├── internal/                # Go business domains
├── web/                     # HTMX templates + assets
├── services/
│   ├── ai/                  # FastAPI (inference)
│   └── blender/             # Blender worker + scripts
├── packages/plan-schema/    # Shared JSON Schemas
├── research/                # Dataset, metrics, ablations
├── deploy/                  # Docker Compose / K8s
└── docs/                    # Documentation
```

## Quick start

See [docs/getting-started.md](docs/getting-started.md).

```bash
git clone --recurse-submodules https://github.com/joeylukoji/A-AI.git
docker compose -f deploy/docker-compose.yml up --build
```

Then open `http://localhost:8080`.

Client preview on an AWS instance: [docs/deploy-aws.md](docs/deploy-aws.md)
(uses `deploy/docker-compose.prod.yml`, not the dev compose file).

## Tests

```bash
make test
# or:
go test ./...
python -m pytest services/ai/tests research/metrics services/blender/tests services/qcad research/dataset -q
node --test web/tests/
```

## Product principle

The AI-generated 2D image is a **visual draft**. The usable source of truth is the vector **`PlanDocument`** (rooms, walls, openings, dimensions), versioned and exportable (PDF, SVG/DXF, OBJ/glTF).

## Reproducibility (scientific evaluation)

- The full test suite runs offline: `make test` (Go + Python) and `node --test web/tests/` (JS editor).
- Geometric metrics and benchmarks live in [`research/`](research/) (`make test-ablation` for ablations).
- The plan validation contract is specified in [`packages/plan-schema/`](packages/plan-schema/) (`validation-profile.md`, `validation-cases.json`) and shared between Go and Python.
- Known limitations are listed candidly in [docs/gaps.md](docs/gaps.md).

## License

Code released under the [MIT License](LICENSE). The ResPlan dataset and third-party 3D models keep their own licenses: see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
