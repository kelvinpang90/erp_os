# Deployment runbook (W21 / first real deploy)

> **Status**: code is ready (W18). This runbook is the playbook for the day
> we actually point Cloudflare at a VPS. Nothing here was executed in W18 —
> all of this requires a paid VPS + a domain.

## 0. Prerequisites

| Item | Notes |
|---|---|
| VPS | 2 vCPU / 4 GB RAM minimum. Provider: DigitalOcean SGP1 / Vultr KL / OVH SBG. |
| Domain | One subdomain (`erp-demo.<your-domain>`) is enough. |
| Cloudflare account | Free tier — adds HTTPS + CDN + bot protection. |
| GitHub repo | This one. |
| Sentry account | Free tier; one project per env (backend + frontend can share). |
| UptimeRobot | Free tier covers 50 monitors. |

## 1. VPS bootstrap

```bash
# Run as root once
adduser deploy
usermod -aG sudo deploy
# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
# Firewall: only 22 + 80 + 443 open
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
# Swap (helps small VPS handle build spikes)
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
# Clone
sudo -u deploy git clone https://github.com/<owner>/<repo>.git /opt/erp-os
```

Drop `.env.production` next to `docker-compose.prod.yml`. Keys to populate:

```dotenv
ENVIRONMENT=production
DEMO_MODE=true
SECRET_KEY=<openssl rand -hex 32>
DATABASE_URL=mysql+aiomysql://root:<MYSQL_ROOT_PASSWORD>@mysql:3306/erp_os
MYSQL_ROOT_PASSWORD=<openssl rand -hex 16>
MYSQL_DATABASE=erp_os
REDIS_HOST=redis
ANTHROPIC_API_KEY=<key>
SENTRY_DSN=<from sentry.io>
VITE_API_URL=/api
VITE_SENTRY_DSN=<frontend DSN>
APP_VERSION=0.1.0
```

## 2. Cloudflare DNS

1. Add an `A` record: `erp-demo` → VPS IPv4. Proxy = ON (orange cloud).
2. SSL/TLS mode = "Full". Cloudflare terminates HTTPS; nginx in the VPS only
   needs to listen on 80.
3. Page Rule (optional): `erp-demo.example.com/api/*` → cache level Bypass.

## 3. First deploy

```bash
cd /opt/erp-os
bash scripts/deploy.sh
```

`deploy.sh`:
- `git fetch && git reset --hard origin/main`
- `docker compose -f docker-compose.prod.yml up -d --build`
- runs `alembic upgrade head` inside the backend container
- curls `/health` to confirm

Master data + transactional seed:
```bash
docker compose -f docker-compose.prod.yml exec backend python scripts/seed_master_data.py
docker compose -f docker-compose.prod.yml exec backend python scripts/seed_all_master.py
docker compose -f docker-compose.prod.yml exec backend python scripts/seed_transactional.py
```

## 4. Crontab on the host

```cron
0 2 * * *  /opt/erp-os/scripts/backup.sh >> /var/log/erp-backup.log 2>&1
```

(The 03:00 demo reset itself runs inside the `celery-beat` container, not via
host cron.)

## 5. UptimeRobot monitors

| Monitor | URL | Interval |
|---|---|---|
| Public health | `https://erp-demo.example.com/health` | 5 min |
| API ping | `https://erp-demo.example.com/api/auth/health` (if added) | 5 min |

## 6. Sentry

Backend DSN goes in `.env.production` → `SENTRY_DSN`.
Frontend DSN goes in `.env.production` → `VITE_SENTRY_DSN`. The frontend is
re-built when `deploy.sh` runs, so the DSN is baked into the static bundle.

## 7. GitHub Actions secrets

Set under **Settings → Environments → demo**:

| Secret | What it is |
|---|---|
| `DEPLOY_HOST` | VPS hostname (e.g. `erp-demo.example.com`) |
| `DEPLOY_USER` | SSH user (`deploy`) |
| `DEPLOY_PATH` | Repo dir on VPS (`/opt/erp-os`) |
| `DEPLOY_SSH_KEY` | Private key content (matching `~/.ssh/authorized_keys` on the VPS) |
| `DEPLOY_SSH_KNOWN_HOSTS` | `ssh-keyscan erp-demo.example.com` output |

`deploy-demo.yml` short-circuits with a warning when these aren't set, so the
workflow stays green during the W18 → W21 gap.

## 8. Verifying the demo reset

After deploy, hit the Admin page → "Demo reset" → button. Watch
`/api/admin/demo-reset/history` until the latest row flips to `SUCCESS`.
Visit Sales Orders + Dashboard to confirm 500 historical docs are present.
