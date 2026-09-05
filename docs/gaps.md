# Écarts / ce qui manque

État au moment de l’ajout de la suite de tests. Priorisé pour le MVP.

Liste consolidée (recherche + produit + API) : [ameliorations.md](ameliorations.md).

## Bugs corrigés avec les tests

- Pipeline IA `422` quand `constraints: null` (Go + Pydantic)
- Spam `Timeout reading from socket` du worker Blender (socket Redis)
- `vendor/` désynchronisé de `go.mod` (`go build` échouait à la racine) — `go mod vendor`
  relancé, vérifié en CI désormais
- Compte `demo@a-ai.local` / `demo-demo-demo` auto-créé même en prod — désactivé hors dev/test
- **Liste des projets tronquée** : `{{if ge .ComplianceScore 80}}` comparait un `*int`, ce que
  `html/template` refuse ; le rendu s'arrêtait en plein HTML dès qu'un projet avait un score,
  ne laissant visible que le plus récent (accesseurs `Score()`)
- **Historique des plans invisible** : chaque génération créait bien une révision en base, mais
  la page projet n'affichait que la révision courante — les précédentes semblaient perdues
- **Pièces murées** : 12 % des plans générés contenaient une pièce sans aucune porte
- **Pièces perdues / superposées** dans le pavage (768 plans sur 4 000 en fuzzing)
- `INTERNAL_TOKEN` comparé avec `==` (timing attack) — `crypto/subtle.ConstantTimeCompare`
- Démarrage possible en prod avec les secrets par défaut publics du repo (`SESSION_SECRET`,
  `INTERNAL_TOKEN`, `S3_ACCESS_KEY`/`S3_SECRET_KEY`) — `config.Validate()` bloque le boot

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
| CI | ~~Pipeline GitHub Actions (tests Go + pytest)~~ (fait, `.github/workflows/test.yml`) | — |
| Dataset | FloorPlanCAD Kaggle branché (images+YOLO) ; ResPlan pickle toujours optionnel | Moyenne |
| Sécu | ~~Rate limiting, CSRF HTMX, scan dépendances automatisé~~ (fait : `internal/httpapi/security.go` + `govulncheck`/`pip-audit` en CI — voir [production.md](production.md)) | — |

## Manques qualité / ops

- Pas de tests d’intégration E2E automatisés (login → generate → export) dans CI
- Pas de `.env` de prod / secrets manager (checklist manuelle : [production.md](production.md))
- ~~Healthchecks Compose incomplets sur `api` / `ai`~~
- ~~Favicon manquant~~
- Encodage labels FR parfois cassé selon locale console (UTF-8 OK en HTTP)
- `services/blender/Dockerfile` télécharge Blender sans vérifier de somme de contrôle
  (pas d'accès réseau vers `download.blender.org` au moment du durcissement pour récupérer
  le SHA256 officiel) — voir [production.md](production.md) §5

## Couverture de tests actuelle

- Go : `domain`, `export`, `billing` (unit + quota DB optionnel), `auth` (slugify), `jobs` (queues), `httpapi` (healthz), `plan-schema`
- Python : pipeline FastAPI (dont `constraints: null`), NLU, orthogonalité, métriques, stub Blender

Lancer :

```bash
go test ./...
pytest services/ai/tests research/metrics services/blender/tests -q
```
