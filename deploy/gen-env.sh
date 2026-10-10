#!/usr/bin/env bash
# Génère deploy/.env pour une preview AWS (secrets aléatoires, pas de placeholders).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${ROOT}/.env"
FORCE=0

usage() {
  cat <<'EOF'
Usage: AAI_DOMAIN=app.exemple.com ACME_EMAIL=ops@exemple.com ./deploy/gen-env.sh [--force]

Génère deploy/.env avec des secrets aléatoires. Refuse d'écraser un fichier
existant sauf --force.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "option inconnue: $arg" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "${AAI_DOMAIN:-}" || -z "${ACME_EMAIL:-}" ]]; then
  echo "AAI_DOMAIN et ACME_EMAIL sont obligatoires." >&2
  usage
  exit 2
fi

if [[ -f "$OUT" && "$FORCE" != "1" ]]; then
  echo "$OUT existe déjà. Passez --force pour régénérer (cela casse sessions, MinIO et Redis)." >&2
  exit 1
fi

need_openssl() {
  command -v openssl >/dev/null 2>&1 || {
    echo "openssl est requis" >&2
    exit 1
  }
}

need_openssl

hex() { openssl rand -hex "$1"; }

POSTGRES_PASSWORD="$(hex 16)"
REDIS_PASSWORD="$(hex 16)"
SESSION_SECRET="$(hex 32)"
INTERNAL_TOKEN="$(hex 32)"
S3_ACCESS_KEY="$(hex 8)"
S3_SECRET_KEY="$(hex 24)"
AI_STUB="${AI_STUB:-1}"
ADMIN_EMAILS="${ADMIN_EMAILS:-}"
TOGETHER_API_KEY="${TOGETHER_API_KEY:-}"
EDENAI_API_KEY="${EDENAI_API_KEY:-}"

umask 077
cat >"$OUT" <<EOF
AAI_DOMAIN=${AAI_DOMAIN}
ACME_EMAIL=${ACME_EMAIL}
PUBLIC_BASE_URL=https://${AAI_DOMAIN}
APP_ENV=production
TRUST_PROXY_HEADERS=1

POSTGRES_USER=aai
POSTGRES_DB=aai
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DATABASE_URL=postgres://aai:${POSTGRES_PASSWORD}@postgres:5432/aai?sslmode=disable

REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

SESSION_SECRET=${SESSION_SECRET}
INTERNAL_TOKEN=${INTERNAL_TOKEN}

S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=${S3_ACCESS_KEY}
S3_SECRET_KEY=${S3_SECRET_KEY}
S3_BUCKET=aai-artifacts
S3_USE_PATH_STYLE=1
S3_REGION=us-east-1

AI_BASE_URL=http://ai:8000
QCAD_URL=
AI_STUB=${AI_STUB}
TOGETHER_API_KEY=${TOGETHER_API_KEY}
TOGETHER_NLU=1
TOGETHER_PLANNER=1
TOGETHER_PLANNER_MODEL=openai/gpt-oss-120b
TOGETHER_PLANNER_EFFORT=low
IMAGE_BACKEND=together
IMAGE_RENDERER=gemini
TOGETHER_IMAGE_STYLE=illustration
TOGETHER_IMAGE_LABELS=none
TOGETHER_IMAGE_MAX_PX=1280
TOGETHER_IMAGE_TIMEOUT=240
EDENAI_API_KEY=${EDENAI_API_KEY}
EDENAI_IMAGE_MODEL=image/generation/google/gemini-3-pro-image-preview

ADMIN_EMAILS=${ADMIN_EMAILS}

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_PRO=
STRIPE_PRICE_BUREAU=
EOF

chmod 600 "$OUT"
echo "écrit $OUT (mode 600). PUBLIC_BASE_URL=https://${AAI_DOMAIN}"
if [[ "$AI_STUB" == "1" ]]; then
  echo "AI_STUB=1 (démo sans clés LLM). Pour l'IA réelle : éditez .env puis recreez le service ai."
fi
