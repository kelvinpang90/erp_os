#!/usr/bin/env bash
# setup-mcp-mysql.sh
# Setup Claude Code MCP server for erp-os MySQL (local dev environment only).
#
# Usage:
#   bash docs/scripts/setup-mcp-mysql.sh
#
# Prerequisites:
#   - docker compose is running with mysql service healthy
#   - .env.development exists at project root with MYSQL_ROOT_PASSWORD=...
#   - Window 02 completed (database erp_os and tables exist)
#
# After running:
#   - Fully quit Claude Code (NOT /clear)
#   - Reopen and verify mcp__erp_mysql__* tools are available

set -euo pipefail

# ---- Locate project root ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# ---- Sanity checks ----
if [ ! -f .env.development ]; then
  echo "❌ .env.development not found at $PROJECT_ROOT"
  echo "   Are you in the correct project root?"
  exit 1
fi

set -o allexport
# shellcheck disable=SC1091
source .env.development
set +o allexport

if [ -z "${MYSQL_ROOT_PASSWORD:-}" ]; then
  echo "❌ MYSQL_ROOT_PASSWORD not set in .env.development"
  exit 1
fi

if ! docker compose ps mysql 2>/dev/null | grep -qiE "running|healthy|up"; then
  echo "❌ MySQL container is not running."
  echo "   Run: docker compose up -d mysql"
  exit 1
fi

# ---- Detect docker network ----
NET_NAME=$(docker network ls --format '{{.Name}}' | grep -E '_default$' | head -1)
if [ -z "$NET_NAME" ]; then
  echo "❌ Cannot find docker-compose default network."
  echo "   Run: docker compose up -d"
  exit 1
fi
echo "📡 Detected docker network: $NET_NAME"

# ---- Generate strong password ----
PWD_NEW=$(openssl rand -hex 16)

# ---- Create/Update claude_ro user ----
echo "🔐 Creating MySQL user 'claude_ro' (read-only)..."
docker compose exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<EOF
CREATE USER IF NOT EXISTS 'claude_ro'@'%' IDENTIFIED BY '$PWD_NEW';
ALTER USER 'claude_ro'@'%' IDENTIFIED BY '$PWD_NEW';
GRANT SELECT ON erp_os.* TO 'claude_ro'@'%';
GRANT SHOW VIEW ON erp_os.* TO 'claude_ro'@'%';
FLUSH PRIVILEGES;
EOF

# ---- Verify read access ----
echo "🔍 Verifying read access..."
if docker compose exec -T mysql mysql -uclaude_ro -p"$PWD_NEW" erp_os \
     -e "SELECT 1;" > /dev/null 2>&1; then
  echo "✅ claude_ro can read erp_os"
else
  echo "❌ claude_ro cannot connect or read"
  exit 1
fi

# ---- Verify write is blocked ----
echo "🔍 Verifying write is blocked..."
WRITE_OUTPUT=$(docker compose exec -T mysql mysql -uclaude_ro -p"$PWD_NEW" erp_os \
  -e "CREATE TABLE _test_perm_check (id INT);" 2>&1 || true)
if echo "$WRITE_OUTPUT" | grep -qi "denied"; then
  echo "✅ claude_ro write blocked (correct)"
else
  echo "⚠️  WARNING: write permission not blocked as expected"
  echo "   Output: $WRITE_OUTPUT"
fi

# ---- Save password ----
echo "CLAUDE_MYSQL_PASSWORD=$PWD_NEW" > .env.claude
chmod 600 .env.claude
echo "💾 Password saved to .env.claude (chmod 600)"

# ---- Pull MCP image ----
echo "📦 Pulling mcp/mysql image..."
if ! docker pull mcp/mysql 2>&1 | tee /tmp/mcp-pull.log | grep -qi "up to date\|Downloaded\|Status"; then
  echo "⚠️  Could not verify image pull, but continuing..."
fi

# ---- Write mcp.json ----
echo "📝 Writing .claude/mcp.json..."
mkdir -p .claude
cat > .claude/mcp.json <<EOF
{
  "mcpServers": {
    "erp-mysql": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network", "$NET_NAME",
        "-e", "MYSQL_HOST=mysql",
        "-e", "MYSQL_PORT=3306",
        "-e", "MYSQL_USER=claude_ro",
        "-e", "MYSQL_PASSWORD=$PWD_NEW",
        "-e", "MYSQL_DATABASE=erp_os",
        "mcp/mysql"
      ]
    }
  }
}
EOF
chmod 600 .claude/mcp.json
echo "✅ .claude/mcp.json written"

# ---- Update .gitignore ----
if [ ! -f .gitignore ] || ! grep -qF ".env.claude" .gitignore; then
  cat >> .gitignore <<'EOF'

# Claude Code — personal & secrets (DO NOT COMMIT)
.env.claude
.claude/mcp.json
.claude/settings.local.json
EOF
  echo "✅ .gitignore updated (added Claude secrets)"
else
  echo "ℹ️  .gitignore already has Claude secrets entries"
fi

# ---- Write example file for team sharing ----
if [ ! -f .claude/mcp.json.example ]; then
  cat > .claude/mcp.json.example <<'EOF'
{
  "mcpServers": {
    "erp-mysql": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network", "<YOUR_COMPOSE_NETWORK>",
        "-e", "MYSQL_HOST=mysql",
        "-e", "MYSQL_PORT=3306",
        "-e", "MYSQL_USER=claude_ro",
        "-e", "MYSQL_PASSWORD=<SET_BY_setup-mcp-mysql.sh>",
        "-e", "MYSQL_DATABASE=erp_os",
        "mcp/mysql"
      ]
    }
  }
}
EOF
  echo "✅ .claude/mcp.json.example created (safe to commit)"
fi

# ---- Done ----
cat <<'EOF'

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ MCP MySQL Setup COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEXT STEPS:
  1. Fully QUIT Claude Code (not /clear; completely exit the app)
  2. Reopen Claude Code
  3. In a new session, ask:
       "list tools from erp-mysql"
     You should see mcp__erp_mysql__* tools.

FILES CREATED / UPDATED:
  .env.claude                   (password, gitignored)
  .claude/mcp.json              (MCP config, gitignored)
  .claude/mcp.json.example      (template, safe to commit)
  .gitignore                    (added Claude secrets entries)

MANUAL VERIFICATION:
  source .env.claude
  docker compose exec -T mysql mysql \
    -uclaude_ro -p"$CLAUDE_MYSQL_PASSWORD" \
    erp_os -e "SHOW TABLES;"

TROUBLESHOOTING:
  See docs/mcp-setup.md § Common Pitfalls

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
