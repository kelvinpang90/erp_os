#!/usr/bin/env bash
# Daily MySQL dump for the demo VPS. Schedule via host crontab:
#   0 2 * * * /opt/erp-os/scripts/backup.sh >> /var/log/erp-backup.log 2>&1
#
# Runs ~1h before the 03:00 demo reset so a clean snapshot is captured each
# day before destructive operations. Keeps the last 7 dumps.

set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/erp-os}"
BACKUP_DIR="${BACKUP_DIR:-${REPO_DIR}/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_DIR}/docker-compose.prod.yml}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TS="$(date -u +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/erp_os_${TS}.sql.gz"

mkdir -p "${BACKUP_DIR}"

# Pull MYSQL_ROOT_PASSWORD from the prod env file without exporting it to the
# parent shell — keeps secrets out of `ps`.
ENV_FILE="${REPO_DIR}/.env.production"
if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} missing" >&2
    exit 1
fi
# shellcheck disable=SC1090
MYSQL_ROOT_PASSWORD="$(grep -E '^MYSQL_ROOT_PASSWORD=' "${ENV_FILE}" | cut -d= -f2-)"
DB_NAME="$(grep -E '^MYSQL_DATABASE=' "${ENV_FILE}" | cut -d= -f2- | head -n1)"
DB_NAME="${DB_NAME:-erp_os}"

echo "[$(date -u --iso-8601=seconds)] Backing up ${DB_NAME} → ${OUT}"

docker compose -f "${COMPOSE_FILE}" exec -T mysql \
    mysqldump --single-transaction --quick \
              -uroot -p"${MYSQL_ROOT_PASSWORD}" "${DB_NAME}" \
    | gzip > "${OUT}"

echo "[$(date -u --iso-8601=seconds)] Backup size: $(du -h "${OUT}" | cut -f1)"

find "${BACKUP_DIR}" -name 'erp_os_*.sql.gz' -mtime +"${RETENTION_DAYS}" -print -delete

echo "[$(date -u --iso-8601=seconds)] Done."
