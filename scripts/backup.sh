#!/usr/bin/env bash
# Daily MySQL dump for the demo VPS. Schedule via host crontab:
#   0 2 * * * /opt/erp_os/scripts/backup.sh >> /var/log/erp-backup.log 2>&1
#
# Runs ~1h before the 03:00 demo reset so a clean snapshot is captured each
# day before destructive operations. Keeps the last 7 dumps.
#
# Topology: mysql is part of the shared vps_infra stack, not this compose.
# We dump via the infra_mysql container directly.

set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/erp_os}"
BACKUP_DIR="${BACKUP_DIR:-${REPO_DIR}/backups}"
MYSQL_CONTAINER="${MYSQL_CONTAINER:-infra_mysql}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TS="$(date -u +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/erp_os_${TS}.sql.gz"

mkdir -p "${BACKUP_DIR}"

# Pull DB credentials from the .env file without exporting them to the parent
# shell — keeps secrets out of `ps`.
ENV_FILE="${REPO_DIR}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} missing" >&2
    exit 1
fi

# DATABASE_URL=mysql+aiomysql://erp_app:<pwd>@infra_mysql:3306/erp_os
DB_URL="$(grep -E '^DATABASE_URL=' "${ENV_FILE}" | cut -d= -f2-)"
DB_USER="$(echo "${DB_URL}" | sed -E 's|^.+://([^:]+):.*|\1|')"
DB_PASS="$(echo "${DB_URL}" | sed -E 's|^.+://[^:]+:([^@]+)@.*|\1|')"
DB_NAME="$(echo "${DB_URL}" | sed -E 's|^.+/([^?]+).*|\1|')"
DB_NAME="${DB_NAME:-erp_os}"

echo "[$(date -u --iso-8601=seconds)] Backing up ${DB_NAME} → ${OUT}"

docker exec -i "${MYSQL_CONTAINER}" \
    mysqldump --single-transaction --quick \
              -u"${DB_USER}" -p"${DB_PASS}" "${DB_NAME}" \
    | gzip > "${OUT}"

echo "[$(date -u --iso-8601=seconds)] Backup size: $(du -h "${OUT}" | cut -f1)"

find "${BACKUP_DIR}" -name 'erp_os_*.sql.gz' -mtime +"${RETENTION_DAYS}" -print -delete

echo "[$(date -u --iso-8601=seconds)] Done."
