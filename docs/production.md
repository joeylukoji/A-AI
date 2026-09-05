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

## 2. Administrateurs plateforme (`/admin`)

`ADMIN_EMAILS` (emails séparés par des virgules) désigne les comptes autorisés à ouvrir
`/admin`, qui affiche **les plans de toutes les organisations**. C'est le seul endroit du
produit qui traverse volontairement les frontières entre clients — à traiter comme un accès
privilégié :

**Ordre obligatoire : créer le compte d'abord, l'ajouter à `ADMIN_EMAILS` ensuite.**
L'inscription est en libre-service et sans vérification d'email. Si une adresse est listée
alors qu'aucun compte ne la porte, elle serait revendicable par n'importe qui — qui hériterait
alors de la lecture de toutes les organisations. Deux garde-fous appliquent cette règle :

1. `Register` **refuse** une adresse listée dans `ADMIN_EMAILS` (`ErrReservedEmail`), avec le
   même message que pour une adresse déjà prise, afin de ne pas révéler quels comptes sont
   privilégiés.
2. La promotion n'a lieu qu'au démarrage (`store.GrantPlatformAdmins`), sur des comptes
   **existants** — il n'y a plus de promotion silencieuse à chaque requête.

Conséquences pratiques :

- Pour ajouter un administrateur : il s'inscrit normalement, **puis** on ajoute son email à
  `ADMIN_EMAILS` et on redémarre l'API.
- Retirer un email révoque l'accès au prochain démarrage ; `users.is_platform_admin` reflète
  toujours l'environnement.
- `ADMIN_EMAILS` vide (défaut) = **aucun** administrateur, `/admin` renvoie 404 pour tout le
  monde. C'est le comportement voulu tant qu'on n'en a pas besoin.
- Un non-administrateur reçoit 404 sur les pages (l'existence de la zone n'est pas annoncée) et
  403 sur `/api/v1/admin/*`.

## 3. Authentification inter-services

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

## 4. Réseau

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

## 5. Intégrations externes (hors périmètre de ce durcissement)

Ces éléments restent des stubs documentés (nécessitent des comptes/clés que l'opérateur doit
fournir) :

- **Stripe** : Checkout/Portal/webhooks réels (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`).
- **OAuth** Google/GitHub pour l'auth (actuellement email + mot de passe uniquement).
- **LLM réel** pour le NLU si `TOGETHER_PLANNER=0` (sinon heuristique).

Voir [gaps.md](gaps.md) et [ameliorations.md](ameliorations.md) pour le détail produit.

## 6. CI / scan de dépendances

`.github/workflows/test.yml` fait tourner à chaque push/PR :

- Go : `gofmt -l`, cohérence de `vendor/`, `go vet`, `go build`, `go test -race`.
- `govulncheck` sur le module Go (base de vulnérabilités officielle Go). `go.mod` épingle
  `toolchain go1.26.8` : les CVE restantes étaient toutes dans la bibliothèque standard d'un
  toolchain plus ancien, et l'épinglage garantit qu'un build ne peut pas les réintroduire
  silencieusement (8 vulnérabilités → 0).
- Python : `pytest` sur `services/ai`, `services/blender`, `services/qcad`, `research/`.
- `pip-audit` sur `services/ai` et `services/blender` (non bloquant pour l'instant — à
  durcir une fois la base d'alertes triée).

Rien n'est configuré pour Snyk/Dependabot ; à brancher séparément si souhaité (compte externe).

## 7. Images Docker

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

## 8. Sauvegardes / observabilité

- Postgres et MinIO utilisent des volumes Docker nommés (`pgdata`, `miniodata`) sans
  sauvegarde automatisée — mettre en place `pg_dump` planifié + réplication objet S3 avant
  d'y stocker des données clients réelles.
- `internal/obs` : pas d'export OpenTelemetry configuré (traces/metrics) — logs structurés
  JSON (`slog`) uniquement pour l'instant.
