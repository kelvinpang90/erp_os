#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 新项目 onboard：建 MySQL DB+用户，提示 Redis db 区段
# Usage:
#   cd /srv/infra
#   ./scripts/provision-project.sh <project_db> <redis_db_start>
# Example:
#   ./scripts/provision-project.sh app2 16
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

if [ $# -ne 2 ]; then
    echo "Usage: $0 <project_db> <redis_db_start>"
    echo "Example: $0 app2 16"
    exit 1
fi

PROJECT="$1"
REDIS_START="$2"
REDIS_END=$((REDIS_START + 15))

if [ "$REDIS_END" -gt 255 ]; then
    echo "❌ redis_db_start 超出 256 上限（infra/redis/redis.conf 配置 databases=256）"
    exit 1
fi

# 项目名校验（防 SQL 注入 / 目录注入）
if ! [[ "$PROJECT" =~ ^[a-z][a-z0-9_]{1,30}$ ]]; then
    echo "❌ project name 必须小写字母开头，仅含 [a-z0-9_]，2-31 字符"
    exit 1
fi

# 切到 infra 根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$INFRA_ROOT"

if [ ! -f .env ]; then
    echo "❌ infra/.env 不存在，先 cp .env.example .env 并填值"
    exit 1
fi

set -o allexport
# shellcheck disable=SC1091
source .env
set +o allexport

if [ -z "${MYSQL_ROOT_PASSWORD:-}" ]; then
    echo "❌ MYSQL_ROOT_PASSWORD 未设置"
    exit 1
fi

# 生成 16 字节随机密码
NEW_PWD=$(openssl rand -hex 16)

echo "🔐 Creating MySQL database & user for project: $PROJECT"
docker compose exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<EOF
CREATE DATABASE IF NOT EXISTS \`${PROJECT}\`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${PROJECT}_app'@'%' IDENTIFIED BY '${NEW_PWD}';
ALTER USER '${PROJECT}_app'@'%' IDENTIFIED BY '${NEW_PWD}';
GRANT ALL PRIVILEGES ON \`${PROJECT}\`.* TO '${PROJECT}_app'@'%';
FLUSH PRIVILEGES;
EOF

echo "🔍 Verifying connectivity..."
if docker compose exec -T mysql mysql -u"${PROJECT}_app" -p"${NEW_PWD}" "${PROJECT}" \
    -e "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ ${PROJECT}_app can connect to ${PROJECT}"
else
    echo "❌ Connectivity check failed"
    exit 1
fi

cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Provisioned: $PROJECT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MySQL:
  Database:  ${PROJECT}
  User:      ${PROJECT}_app
  Password:  ${NEW_PWD}
  Host:      mysql (在 data_net 内)
  Port:      3306

Redis:
  DB range:  ${REDIS_START} - ${REDIS_END}
  Host:      redis (在 data_net 内)
  Port:      6379

Connection strings:
  DATABASE_URL=mysql+aiomysql://${PROJECT}_app:${NEW_PWD}@mysql:3306/${PROJECT}
  CELERY_BROKER_URL=redis://redis:6379/${REDIS_START}

Next steps:
  1. 把上面的密码安全保存到 /srv/${PROJECT}/.env.production
  2. cp infra/nginx/conf.d/erp.conf.example infra/nginx/conf.d/${PROJECT}.conf
  3. 编辑 ${PROJECT}.conf：替换 erp_backend → ${PROJECT}_backend，erp_frontend → ${PROJECT}_frontend，erp.example.com → 真实域名
  4. docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload
  5. Cloudflare DNS 加 A 记录指向 VPS，开橙云

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
