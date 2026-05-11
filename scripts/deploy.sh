#!/usr/bin/env bash
# Pull latest images from ghcr.io, rerun migrations.
#
# Run on the VPS directly OR have GitHub Actions ssh in and execute it.
# Required env vars (set in shell or sourced from /etc/erp-os.env):
#   REPO_DIR        absolute path to the checkout (default: /opt/erp_os)
#   COMPOSE_FILE    docker compose file (default: $REPO_DIR/docker-compose.yml)
#   BRANCH          git branch (default: main)
#
# Note: ghcr.io login must already be performed (docker login ghcr.io).
# CI does this inline; for manual runs, `echo $GHCR_PAT | docker login ghcr.io -u <user> --password-stdin`.

set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/erp_os}"
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_DIR}/docker-compose.yml}"
BRANCH="${BRANCH:-main}"

cd "${REPO_DIR}"

echo "[$(date -u --iso-8601=seconds)] Pulling ${BRANCH}…"
git fetch --quiet origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"

echo "[$(date -u --iso-8601=seconds)] Pulling images from ghcr.io…"
docker compose -f "${COMPOSE_FILE}" pull

echo "[$(date -u --iso-8601=seconds)] Starting services…"
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

echo "[$(date -u --iso-8601=seconds)] Waiting for backend health…"
for i in {1..30}; do
    if docker compose -f "${COMPOSE_FILE}" exec -T erp_backend curl -fs http://localhost:8000/health >/dev/null; then
        break
    fi
    sleep 2
done

echo "[$(date -u --iso-8601=seconds)] Running Alembic migrations…"
docker compose -f "${COMPOSE_FILE}" exec -T erp_backend alembic upgrade head

echo "[$(date -u --iso-8601=seconds)] Pruning dangling images…"
docker image prune -f

echo "[$(date -u --iso-8601=seconds)] Deploy complete."
