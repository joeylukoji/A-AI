#!/usr/bin/env bash
# Prépare une Ubuntu 24.04 (EC2) et lance la stack de preview.
# À exécuter depuis la racine du dépôt, avec sudo : sudo ./deploy/bootstrap-ec2.sh
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "relancer avec sudo : sudo ./deploy/bootstrap-ec2.sh" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

export DEBIAN_FRONTEND=noninteractive

. /etc/os-release

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    systemctl enable --now docker
    return
  fi
  case "${ID:-}" in
    amzn)
      dnf install -y docker openssl
      mkdir -p /usr/libexec/docker/cli-plugins
      curl -fsSL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-x86_64" \
        -o /usr/libexec/docker/cli-plugins/docker-compose
      chmod +x /usr/libexec/docker/cli-plugins/docker-compose
      ;;
    *)
      apt-get update
      apt-get install -y --no-install-recommends ca-certificates curl openssl ufw
      if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
        chmod 0644 /etc/apt/keyrings/docker.asc
      fi
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
        >/etc/apt/sources.list.d/docker.list
      apt-get update
      apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
      ;;
  esac
  systemctl enable --now docker
}

install_docker

if id ubuntu >/dev/null 2>&1; then
  usermod -aG docker ubuntu || true
fi
if id ec2-user >/dev/null 2>&1; then
  usermod -aG docker ec2-user || true
fi

if ! swapon --show | grep -q .; then
  if [[ ! -f /swapfile ]]; then
    avail_gb="$(df -BG --output=avail / | tail -1 | tr -dc '0-9')"
    if [[ "${avail_gb:-0}" -lt 20 ]]; then
      SWAP_MB=1024
    else
      SWAP_MB=4096
    fi
    fallocate -l "${SWAP_MB}M" /swapfile || dd if=/dev/zero of=/swapfile bs=1M count="$SWAP_MB"
    chmod 600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

if [[ "${ID:-}" == "ubuntu" || "${ID:-}" == "debian" ]]; then
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw allow 443/udp
  ufw --force enable
fi

public_ipv4() {
  local token ip
  token="$(curl -fsS -m 2 -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true)"
  if [[ -n "$token" ]]; then
    ip="$(curl -fsS -m 2 -H "X-aws-ec2-metadata-token: $token" \
      http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)"
  fi
  if [[ -z "$ip" ]]; then
    ip="$(curl -fsS -m 5 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]' || true)"
  fi
  echo "$ip"
}

if [[ -z "${AAI_DOMAIN:-}" ]]; then
  PUB_IP="$(public_ipv4)"
  if [[ -z "$PUB_IP" ]]; then
    echo "impossible de détecter l'IP publique. Passez AAI_DOMAIN=..." >&2
    exit 1
  fi
  AAI_DOMAIN="${PUB_IP//./-}.sslip.io"
  echo "AAI_DOMAIN auto: $AAI_DOMAIN"
fi
ACME_EMAIL="${ACME_EMAIL:-preview@${AAI_DOMAIN}}"

if [[ ! -f deploy/.env ]]; then
  sudo -u "${SUDO_USER:-ubuntu}" \
    env AAI_DOMAIN="$AAI_DOMAIN" ACME_EMAIL="$ACME_EMAIL" \
        AI_STUB="${AI_STUB:-1}" TOGETHER_API_KEY="${TOGETHER_API_KEY:-}" \
        EDENAI_API_KEY="${EDENAI_API_KEY:-}" ADMIN_EMAILS="${ADMIN_EMAILS:-}" \
    bash "$REPO_ROOT/deploy/gen-env.sh"
fi

chmod 600 deploy/.env
chown "${SUDO_USER:-ubuntu}:${SUDO_USER:-ubuntu}" deploy/.env || true

if grep -qE '^(SESSION_SECRET|INTERNAL_TOKEN)=(dev-secret-change-me|dev-secret-change-me-in-production|dev-internal-token)[[:space:]]*$' deploy/.env \
  || grep -qE '^S3_ACCESS_KEY=minioadmin[[:space:]]*$' deploy/.env; then
  echo "deploy/.env contient encore des placeholders. Lancez ./deploy/gen-env.sh (ne copiez pas .env.production.example tel quel)." >&2
  exit 1
fi

echo "construction des images (sans Blender)…"
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up -d --build

echo
echo "stack lancée. Vérifier :"
echo "  docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env ps"
echo "  curl -fsS https://\$(grep ^AAI_DOMAIN= deploy/.env | cut -d= -f2)/healthz"
echo
echo "Les clients ouvrent PUBLIC_BASE_URL (HTTPS). Créez un compte, puis ADMIN_EMAILS si besoin."
