# Checklist mise en production

`deploy/docker-compose.yml` est une stack de **développement local** : ports DB/Redis/MinIO
exposés, secrets par défaut publics (committés dans `deploy/.env.example`), pas de TLS. Ne pas
la déployer telle quelle. Ce document liste ce qu'il faut changer pour un déploiement réel.

## 1. Secrets

`internal/config.Config.Validate()` refuse de démarrer si `APP_ENV=production` et que l'un de
ces secrets vaut encore son placeholder de dev :

| Variable | Génération |
|----------|-----------|
| `SESSION_SECRET` | `openssl rand -hex 32` |
| `INTERNAL_TOKEN` | `openssl rand -hex 32` (partagé entre `api`, `ai`, `blender-worker`) |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | identifiants réels du bucket S3-compatible (pas `minioadmin`) |
| `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` | si la facturation Stripe réelle est activée, les deux sont requis ensemble |

`APP_ENV=production` désactive aussi la création automatique du compte
`demo@a-ai.local` / `demo-demo-demo` (`EnsureDemoUser`) — sinon n'importe qui connaissant
ces identifiants publics obtiendrait un compte au premier démarrage.

## 1bis. Authentification inter-services

`services/ai` (FastAPI) exige désormais `X-Internal-Token` (même valeur que `INTERNAL_TOKEN`
côté `api`/`blender-worker`) sur tous ses endpoints `/v1/*` sauf `/healthz` et
`/v1/adapt/rules` (lecture seule, sans coût) — voir `require_internal_token` dans
`services/ai/app/main.py`. Si `INTERNAL_TOKEN` n'est pas défini dans l'environnement du
conteneur `ai`, le contrôle est un no-op (rétrocompatible avec un `uvicorn`/pytest local sans
secret configuré) : **vérifier que `INTERNAL_TOKEN` est bien défini et identique entre `api`
et `ai` en production**, sinon le pipeline IA (appels Together facturés, inférence GPU) reste
appelable par quiconque atteint le port du service.

`services/qcad` (sidecar DXF) n'a **pas** cette protection — c'est un service interne appelé
sans token par `internal/export/qcad.go`. Risque faible (pas de coût direct, normalise un DXF
déjà généré côté Go) mais à ne jamais exposer publiquement ; garder son port hors de tout
reverse proxy public.

## 2. Réseau

- Ne pas exposer les ports `5432` (Postgres), `6379` (Redis), `9000/9001` (MinIO) sur une
  interface publique — seul `api` (8080) doit être joignable depuis l'extérieur, derrière un
  reverse proxy TLS (Caddy/Traefik/Nginx/ingress K8s).
- `TRUST_PROXY_HEADERS=1` uniquement si `api` est effectivement derrière ce reverse proxy —
  sinon un client peut usurper `X-Forwarded-For` et contourner le rate limiting par IP
  (`internal/httpapi/security.go`).
- Le rate limiter et la protection CSRF (`internal/httpapi/security.go`) sont en mémoire
  process ; avec plusieurs répliques de `api`, chaque instance a son propre compteur — c'est
  un plancher de sécurité, pas une garantie exacte de débit global. Passer à un limiteur
  partagé (Redis) si l'API est mise à l'échelle horizontalement.

## 3. Intégrations externes (hors périmètre de ce durcissement)

Ces éléments restent des stubs documentés (nécessitent des comptes/clés que l'opérateur doit
fournir) :

- **Stripe** : Checkout/Portal/webhooks réels (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`).
- **OAuth** Google/GitHub pour l'auth (actuellement email + mot de passe uniquement).
- **LLM réel** pour le NLU si `TOGETHER_PLANNER=0` (sinon heuristique).

Voir [gaps.md](gaps.md) et [ameliorations.md](ameliorations.md) pour le détail produit.

## 4. CI / scan de dépendances

`.github/workflows/test.yml` fait tourner à chaque push/PR :

- Go : `gofmt -l`, cohérence de `vendor/`, `go vet`, `go build`, `go test -race`.
- `govulncheck` sur le module Go (base de vulnérabilités officielle Go).
- Python : `pytest` sur `services/ai`, `services/blender`, `services/qcad`, `research/`.
- `pip-audit` sur `services/ai` et `services/blender` (non bloquant pour l'instant — à
  durcir une fois la base d'alertes triée).

Rien n'est configuré pour Snyk/Dependabot ; à brancher séparément si souhaité (compte externe).

## 5. Images Docker

Chaque `Dockerfile` de service tourne désormais sous un utilisateur non-root (`aai`).
`minio`/`minio/mc` sont épinglés à une version précise dans `docker-compose.yml` (pas
`:latest`) pour la reproductibilité — à monter en version délibérément, pas par
`docker compose pull` silencieux.

`services/blender/Dockerfile` télécharge le binaire Blender officiel via HTTPS depuis
`download.blender.org` (avec miroirs de secours) mais **sans vérification de somme de
contrôle** — l'environnement qui a produit ce durcissement n'avait pas d'accès réseau vers
`download.blender.org` pour récupérer le SHA256 officiel. À ajouter avant un déploiement
sensible : télécharger `SHA256SUMS` depuis `download.blender.org` pour la version pinnée et
vérifier l'archive avant extraction.

## 6. Sauvegardes / observabilité

- Postgres et MinIO utilisent des volumes Docker nommés (`pgdata`, `miniodata`) sans
  sauvegarde automatisée — mettre en place `pg_dump` planifié + réplication objet S3 avant
  d'y stocker des données clients réelles.
- `internal/obs` : pas d'export OpenTelemetry configuré (traces/metrics) — logs structurés
  JSON (`slog`) uniquement pour l'instant.
