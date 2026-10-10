# Premier déploiement AWS (preview clients)

Cible : **une instance EC2** qui fait tourner toute la stack derrière Caddy (TLS
Let’s Encrypt). Suffisant pour faire tester l’application par des clients.
Ce n’est **pas** la cible HA (RDS, ElastiCache, S3 managé, GPU) décrite dans
[architecture.md](architecture.md).

La compose de dev (`deploy/docker-compose.yml`) **ne doit pas** être exposée :
ports Postgres/Redis/MinIO ouverts, secrets publics, pas de TLS. Utiliser
`deploy/docker-compose.prod.yml`.

## Ce que les clients voient

- URL unique en HTTPS (seul le reverse proxy écoute 80/443)
- Inscription / login (pas de compte `demo@a-ai.local` en production)
- Génération 2D, éditeur, exports PDF/SVG/DXF
- **Pas de worker Blender** sur cette preview (image trop lourde) : la 3D reste en file d'attente
- IA en **stub** par défaut (sans clés payantes). Brancher `TOGETHER_API_KEY`
  ensuite pour le NLU et les images réels

Postgres, Redis, MinIO, FastAPI IA et QCAD restent sur le réseau Docker interne.

## Prérequis

| Élément | Recommandation |
|---------|----------------|
| Compte AWS | région `eu-west-3` (Paris) ou plus proche des testeurs |
| Instance | **t3.large** (8 Gio) suffit sans Blender ; **t3.xlarge** si tu rajoutes le worker 3D plus tard |
| Disque | **40 Gio gp3** (80 Gio seulement si Blender est ajouté) |
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| Accès | paire de clés SSH ; pas de mot de passe root |
| Nom de domaine | enregistrement **A** vers l’IP publique (Let’s Encrypt refuse `*.compute.amazonaws.com`) |
| Budget | ~0,15–0,30 USD/h selon le type ; **arrêter** l’instance hors démo |

Sans domaine : un enregistrement du type `IP-avec-tirets.sslip.io` (ex.
`1-2-3-4.sslip.io` pour `1.2.3.4`) convient pour une preview.

## 1. Groupe de sécurité

Créer un security group `aai-preview` :

| Type | Port | Source | Rôle |
|------|------|--------|------|
| SSH | 22 | **votre IP uniquement** | admin |
| HTTP | 80 | 0.0.0.0/0, ::/0 | challenge ACME + redirect |
| HTTPS | 443 | 0.0.0.0/0, ::/0 | application |

Aucun autre port (surtout pas 5432, 6379, 8080, 8000, 9000).

## 2. Instance EC2 (console)

1. Launch instance → Ubuntu 24.04 → type ci-dessus → 80 Gio.
2. Key pair existante ou nouvelle (`.pem` conservée hors du dépôt).
3. Network : le security group `aai-preview`.
4. **Allocate Elastic IP** et l’associer (l’IP ne change pas au stop/start).
5. DNS : `A` `app.votre-domaine` → Elastic IP. Attendre la propagation
   (`nslookup app.votre-domaine` doit renvoyer cette IP) **avant** le premier
   `compose up`, sinon Caddy ne pourra pas obtenir le certificat.

Optionnel : désactiver `IMDSv1` (Metadata v2 only) dans Advanced details.

## 3. Copier le projet sur l’instance

Depuis Windows (PowerShell), en remplaçant la clé et l’IP :

```powershell
scp -r -i $env:USERPROFILE\.ssh\a-ai-ec2.pem `
  C:\Users\Joy\Desktop\A-AI ubuntu@VOTRE_ELASTIC_IP:~/A-AI
```

Ou, si le dépôt est clonable depuis l’instance :

```bash
ssh -i ~/.ssh/a-ai-ec2.pem ubuntu@VOTRE_ELASTIC_IP
git clone <url> ~/A-AI
```

Ne **pas** copier `deploy/.env` local (dev). Les secrets de preview sont
générés sur l’instance.

## 4. Lancer la stack

Depuis Windows (clé `45dertyop.pem`) :

```powershell
powershell -File deploy/push-ec2.ps1 <IPV4_PUBLIQUE>
```

Le script copie le dépôt (sans `vendor` / Blender) et lance `bootstrap-ec2.sh` sur l’instance. Sans `AAI_DOMAIN`, l’URL devient `https://<ip-en-tirets>.sslip.io`.

Ou à la main sur l’instance :

```bash
cd ~/A-AI
sed -i 's/\r$//' deploy/*.sh
sudo ./deploy/bootstrap-ec2.sh
```

Le premier build (API Go + FastAPI, **sans** Blender) prend quelques minutes.

IA réelle dès le départ (sinon `AI_STUB=1`) :

```bash
sudo AI_STUB=0 TOGETHER_API_KEY=xxx ./deploy/bootstrap-ec2.sh
```

## 5. Vérifier

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env ps
curl -fsS https://app.votre-domaine/healthz
```

Tous les services `api`, `ai`, `qcad`, `postgres`, `redis`, `minio`, `caddy`
doivent être `healthy` / `running`. `minio-init` se termine (`exited 0`).

Les testeurs ouvrent `https://app.votre-domaine` et **créent leur propre compte**.

## 6. Administrateur `/admin`

L’inscription est libre. Pour un compte plateforme :

1. S’inscrire avec l’email prévu.
2. Ajouter cet email à `ADMIN_EMAILS` dans `deploy/.env`.
3. `docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up -d api`

Ne jamais lister un email **avant** que le compte existe (voir
[production.md](production.md) §2).

## 7. Mises à jour du code

```bash
# après rsync/scp/git pull
cd ~/A-AI
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up -d --build
```

Les volumes `pgdata` / `miniodata` / `caddy_data` sont conservés. Ne pas relancer
`gen-env.sh --force` : cela régénère Postgres/MinIO/Redis et **perd** sessions et
artefacts (les volumes eux-mêmes restent, mais les mots de passe ne correspondent plus).

## 8. Sauvegarde minimale (preview)

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec -T postgres \
  pg_dump -U aai aai | gzip > ~/aai-$(date +%F).sql.gz
```

Copier aussi `deploy/.env` hors de l’instance (coffre, pas le git). Sans ce
fichier, les volumes chiffrés par mot de passe sont inutilisables.

## 9. Coût et arrêt

```bash
# AWS console : Instance state → Stop (disque toujours facturé, CPU non)
```

Au redémarrage : l’Elastic IP reste ; `restart: unless-stopped` relance les
conteneurs si Docker est enabled (le bootstrap le fait).

## Dépannage

| Symptôme | Piste |
|----------|--------|
| Caddy : `obtain certificate` / TLS handshake fail | DNS pas encore sur l’Elastic IP ; ports 80/443 fermés dans le SG ou UFW |
| API `refusing to start in production` | `.env` encore sur les placeholders ; relancer `gen-env.sh` **une** fois si le fichier n’a jamais servi |
| Login cookie perdu | `PUBLIC_BASE_URL` ≠ URL HTTPS réelle (CSRF + cookie `Secure`) |
| Job 2D coincé `queued` | `docker compose … logs ai` ; `INTERNAL_TOKEN` identique api/ai |
| 3D échoue | `logs blender-worker` ; instance trop petite (OOM) → passer en t3.2xlarge |
| Let’s Encrypt rate limit | trop de tentatives sur le même domaine ; attendre ou utiliser un sous-domaine neuf |

Checklist secrets / réseau plus large : [production.md](production.md).
