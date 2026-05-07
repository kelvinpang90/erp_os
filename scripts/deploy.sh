#!/usr/bin/env bash
# Pull latest main, rebuild containers, run migrations.
#
# Run on the VPS directly OR have GitHub Actions ssh in and execute it.
# Required env vars (set in shell or sourced from /etc/erp-os.env):
#   REPO_DIR        absolute path to the checkout (default: /opt/erp-os)
#   COMPOSE_FILE    docker compose file (default: docker-compose.prod.yml)
#   BRANCH          git branch (default: main)

set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/erp-os}"
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_DIR}/docker-compose.prod.yml}"
BRANCH="${BRANCH:-main}"

cd "${REPO_DIR}"

echo "[$(date -u --iso-8601=seconds)] Fetching ${BRANCH}…"
git fetch --quiet origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"

echo "[$(date -u --iso-8601=seconds)] Building & starting services…"
docker compose -f "${COMPOSE_FILE}" up -d --build

echo "[$(date -u --iso-8601=seconds)] Waiting for backend health…"
for i in {1..30}; do
    if docker compose -f "${COMPOSE_FILE}" exec -T backend curl -fs http://localhost:8000/health >/dev/null; then
        break
    fi
    sleep 2
done

echo "[$(date -u --iso-8601=seconds)] Running Alembic migrations…"
docker compose -f "${COMPOSE_FILE}" exec -T backend alembic upgrade head

echo "[$(date -u --iso-8601=seconds)] Verifying public health…"
curl -fs http://localhost/health | tee /dev/stderr | grep -q '"status"'

echo "[$(date -u --iso-8601=seconds)] Deploy complete."
