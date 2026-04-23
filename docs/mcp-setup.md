# MCP MySQL Setup — Claude Code 操作 ERP 数据库

> 让 Claude Code 通过 MCP (Model Context Protocol) 直接查询 ERP 数据库。本文档提供**一键脚本** + **分步手动** + **排错手册**三部分。
>
> **何时执行**：Window 02（数据模型 + Alembic initial migration）完成之后。现在执行也可以，只是空表查询没意义。
>
> **时间预估**：5-10 分钟

---

## 📋 最速路径（一键脚本）

在项目根目录执行：

```bash
bash docs/scripts/setup-mcp-mysql.sh
```

脚本做的事：建只读账号 → 写 mcp.json → 加 gitignore。完成后**手动完全重启 Claude Code**。

> 脚本在下文 [§ 一键脚本](#一键脚本完整代码) 一节，复制保存到 `docs/scripts/setup-mcp-mysql.sh` 即可。

---

## 🗺️ 流程图

```
 Window 02 完成
      ↓
┌─────────────────────────────────┐
│ Step 1  建只读账号 claude_ro     │  ◄── docker exec mysql + SQL
├─────────────────────────────────┤
│ Step 2  验证账号连通 + 权限隔离  │  ◄── SELECT + CREATE TABLE 应被拒
├─────────────────────────────────┤
│ Step 3  拉 MCP server 镜像       │  ◄── docker pull mcp/mysql
├─────────────────────────────────┤
│ Step 4  写 .claude/mcp.json      │  ◄── 含网络名 + 账号密码
├─────────────────────────────────┤
│ Step 5  密码文件进 .gitignore    │  ◄── 绝不泄露
├─────────────────────────────────┤
│ Step 6  完全重启 Claude Code     │  ◄── 不是 /clear，是 Quit + 开
├─────────────────────────────────┤
│ Step 7  验证 MCP 工具可见        │  ◄── 新 session 里问 Claude
└─────────────────────────────────┘
      ↓
 日常直接在对话里查数据库
```

---

## 🔐 前置条件

- [ ] `docker compose ps` 显示所有 service 健康
- [ ] `.env.development` 里有 `MYSQL_ROOT_PASSWORD=...`
- [ ] 数据库 `erp_os` 已建好（Window 02 之后）
- [ ] 知道 docker-compose 自动生成的网络名（通常是 `<目录名>_default`）

查网络名：
```bash
docker network ls | grep default
# 例如：erp_os_default 或 erp-os_default
```

---

# 分步手动版

## Step 1: 建只读账号 `claude_ro`

```bash
cd /path/to/erp-os
set -o allexport; source .env.development; set +o allexport

PWD=$(openssl rand -hex 16)      # 32 字符强随机

docker compose exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<EOF
CREATE USER IF NOT EXISTS 'claude_ro'@'%' IDENTIFIED BY '$PWD';
GRANT SELECT ON erp_os.* TO 'claude_ro'@'%';
GRANT SHOW VIEW ON erp_os.* TO 'claude_ro'@'%';
FLUSH PRIVILEGES;
EOF

# 保存密码到 .env.claude（不进 Git）
echo "CLAUDE_MYSQL_PASSWORD=$PWD" > .env.claude
chmod 600 .env.claude

echo "✅ claude_ro 账号已创建"
echo "   密码存于: .env.claude"
```

**权限说明**：
| Grant | 为什么给 |
|---|---|
| `SELECT` | 查数据 |
| `SHOW VIEW` | 能看视图定义（未来可能用） |

**绝不给**：`INSERT / UPDATE / DELETE / CREATE / ALTER / DROP / GRANT`。

---

## Step 2: 验证账号能连 + 权限隔离

```bash
source .env.claude

# 测试读（应成功）
docker compose exec -T mysql mysql \
  -uclaude_ro -p"$CLAUDE_MYSQL_PASSWORD" \
  erp_os <<'EOF'
SHOW TABLES;
SELECT COUNT(*) AS total_skus FROM skus;
EOF

# 测试写（应被拒绝）
docker compose exec -T mysql mysql \
  -uclaude_ro -p"$CLAUDE_MYSQL_PASSWORD" \
  erp_os -e "CREATE TABLE test_fail (id INT);" 2>&1 | grep "denied" \
  && echo "✅ 写权限被拒绝（正确）" \
  || echo "❌ 警告：写权限未被拒绝，检查账号配置"
```

预期：
- 读：显示表列表 + 计数
- 写：`ERROR 1142 (42000): CREATE command denied...` → 这是好事

---

## Step 3: 拉 MCP MySQL Server 镜像

```bash
# 推荐选项：官方 mcp/mysql
docker pull mcp/mysql
```

备选（如果官方镜像不可用）：
```bash
# 选项 B：社区版
docker pull ghcr.io/designcomputer/mysql-mcp-server:latest

# 选项 C：本地 npm 运行
npm install -g @benborla29/mcp-server-mysql
```

本文档后续以 `mcp/mysql` 为例。用其他版本只需调整 mcp.json 里的 image 名。

---

## Step 4: 写 `.claude/mcp.json`

```bash
source .env.claude

# 确认网络名
NET_NAME=$(docker network ls --format '{{.Name}}' | grep default | head -1)
echo "检测到网络: $NET_NAME"

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
        "-e", "MYSQL_PASSWORD=$CLAUDE_MYSQL_PASSWORD",
        "-e", "MYSQL_DATABASE=erp_os",
        "mcp/mysql"
      ]
    }
  }
}
EOF

echo "✅ .claude/mcp.json 已生成"
cat .claude/mcp.json
```

### 参数含义速查

| 参数 | 含义 |
|---|---|
| `command: docker` | MCP server 通过 docker run 启动 |
| `args: -i --rm` | 交互模式 + 自动清理容器 |
| `--network $NET_NAME` | 加入 docker-compose 网络，能用 `mysql` 主机名 |
| `-e MYSQL_HOST=mysql` | 用 service name（compose 网络内 DNS） |
| `-e MYSQL_USER=claude_ro` | 只读账号 |
| `-e MYSQL_PASSWORD=...` | 密码（明文，所以 mcp.json 必须 gitignore） |
| `-e MYSQL_DATABASE=erp_os` | 默认数据库 |
| `mcp/mysql` | 镜像名 |

---

## Step 5: 加入 `.gitignore`

```bash
cat >> .gitignore <<'EOF'

# Claude Code — personal & secrets (DO NOT COMMIT)
.env.claude
.claude/mcp.json
.claude/settings.local.json
EOF

git status              # .env.claude 和 mcp.json 应显示为 untracked
```

### 给团队协作用的模板

提交一个 `.claude/mcp.json.example`（不带密码）让队友参照：

```bash
cat > .claude/mcp.json.example <<'EOF'
{
  "mcpServers": {
    "erp-mysql": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network", "<YOUR_COMPOSE_NETWORK>",
        "-e", "MYSQL_HOST=mysql",
        "-e", "MYSQL_USER=claude_ro",
        "-e", "MYSQL_PASSWORD=<GENERATED_BY_setup-mcp-mysql.sh>",
        "-e", "MYSQL_DATABASE=erp_os",
        "mcp/mysql"
      ]
    }
  }
}
EOF
git add .claude/mcp.json.example
```

---

## Step 6: 完全重启 Claude Code

**⚠️ 必须完全退出**，不是 `/clear`：

- **CLI**：Ctrl+D 退出 → 终端里 `claude` 重启
- **桌面版 / Cowork**：系统托盘右键 Quit → 重新打开

MCP servers 只在启动时加载一次 mcp.json，所以必须硬重启。

---

## Step 7: 在新 session 里验证

开个新对话，问：

```
列出 erp-mysql 这个 MCP server 提供的工具
```

Claude 应该能列出：
- `mcp__erp_mysql__list_tables`
- `mcp__erp_mysql__describe_table`
- `mcp__erp_mysql__query` / `read_resource`
- （具体工具名取决于 MCP server 实现）

然后跑一个真查询：

```
用 erp-mysql 查 skus 表的前 5 条，如果没有数据就 SHOW TABLES 看一下
```

如果看到 SQL 执行 + 结果 → **配置成功** ✅

---

# ❌ 常见坑 & 排错

## 坑 1：Docker 找不到网络

**症状**：MCP server 启动报错 `network xxx not found`

**修复**：
```bash
docker network ls | grep default
```
用查到的实际网络名替换 `mcp.json` 里的 `--network` 参数。重启 Claude Code。

## 坑 2：`Access denied for user 'claude_ro'`

**原因**：密码对不上（mcp.json 里的密码和 MySQL 里实际密码不一致）

**修复**：
```bash
source .env.claude
# 重设密码
docker compose exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<EOF
ALTER USER 'claude_ro'@'%' IDENTIFIED BY '$CLAUDE_MYSQL_PASSWORD';
FLUSH PRIVILEGES;
EOF
```

## 坑 3：Claude Code 看不到 MCP 工具

**可能原因**：
1. 没完全重启（只按了 /clear）
2. mcp.json 语法错（JSON 不允许注释、尾逗号）
3. 镜像 `mcp/mysql` 没拉下来

**诊断**：
```bash
# 语法检查
cat .claude/mcp.json | python3 -m json.tool

# 试跑镜像
docker run -i --rm mcp/mysql --help

# 日志（路径因平台不同）
# macOS: ~/Library/Logs/Claude/
# Linux: ~/.config/Claude/logs/
# Windows: %APPDATA%\Claude\logs\
```

## 坑 4：MCP server 连不上 MySQL（容器内部）

**症状**：`Can't resolve host 'mysql'`

**原因**：MCP 容器没进入 docker-compose 网络

**修复**：
```bash
# 核对网络
docker network ls
# 你的 docker-compose 项目名可能是 erp_os / erp-os / ERP_OS 等，决定网络名
```

## 坑 5：Admin 想临时关 MCP

```bash
mv .claude/mcp.json .claude/mcp.json.disabled
# 重启 Claude Code，MCP 工具就不见了
# 需要时改回来
```

## 坑 6：密码意外 commit 到 Git

```bash
# 立刻作废现在的密码
docker compose exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" \
  -e "ALTER USER 'claude_ro'@'%' IDENTIFIED BY '$(openssl rand -hex 16)';"

# 用 git-filter-repo 或 BFG 清理历史（参考 GitHub 文档）
# 然后重新走 Step 4-5
```

---

# 🌐 Demo VPS 上的配置差异

演示站点（生产环境）上 **Claude Code 不应该直接连**。如果非要连（debug 用）：

1. SSH 到 VPS
2. 重复本文档 Step 1-5（但网络是 VPS 上的 docker 网络名）
3. **绝对不**把 mcp.json 下载到本地 Claude Code —— 隔离生产

更好的做法：**生产库完全不给 Claude 访问**。想看生产数据 → 用 Adminer UI + 手动审计。

---

# 📦 一键脚本完整代码

保存到 `docs/scripts/setup-mcp-mysql.sh`：

```bash
#!/usr/bin/env bash
# setup-mcp-mysql.sh
# Setup Claude Code MCP server for erp-os MySQL (dev environment only)

set -euo pipefail

cd "$(dirname "$0")/../.."

if [ ! -f .env.development ]; then
  echo "❌ .env.development not found. Are you in the project root?"
  exit 1
fi

set -o allexport; source .env.development; set +o allexport

# Sanity check: mysql container running?
if ! docker compose ps mysql | grep -q "running\|healthy"; then
  echo "❌ MySQL container is not running. Run 'docker compose up -d mysql' first."
  exit 1
fi

# Detect docker network
NET_NAME=$(docker network ls --format '{{.Name}}' | grep default | head -1)
if [ -z "$NET_NAME" ]; then
  echo "❌ Cannot find docker-compose default network. Is docker compose up?"
  exit 1
fi
echo "📡 Detected docker network: $NET_NAME"

# Generate password
PWD=$(openssl rand -hex 16)

# Create user
echo "🔐 Creating MySQL user 'claude_ro'..."
docker compose exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<EOF
CREATE USER IF NOT EXISTS 'claude_ro'@'%' IDENTIFIED BY '$PWD';
ALTER USER 'claude_ro'@'%' IDENTIFIED BY '$PWD';
GRANT SELECT ON erp_os.* TO 'claude_ro'@'%';
GRANT SHOW VIEW ON erp_os.* TO 'claude_ro'@'%';
FLUSH PRIVILEGES;
EOF

# Verify account
echo "🔍 Verifying read-only account..."
if docker compose exec -T mysql mysql -uclaude_ro -p"$PWD" erp_os \
     -e "SELECT 1;" > /dev/null 2>&1; then
  echo "✅ claude_ro can read"
else
  echo "❌ claude_ro cannot connect"
  exit 1
fi

if docker compose exec -T mysql mysql -uclaude_ro -p"$PWD" erp_os \
     -e "CREATE TABLE _test_perm (id INT);" 2>&1 | grep -q "denied"; then
  echo "✅ claude_ro write is blocked (correct)"
else
  echo "⚠️  Warning: write is NOT blocked"
fi

# Save password
echo "CLAUDE_MYSQL_PASSWORD=$PWD" > .env.claude
chmod 600 .env.claude

# Pull MCP image
echo "📦 Pulling mcp/mysql image..."
docker pull mcp/mysql

# Write mcp.json
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
        "-e", "MYSQL_PASSWORD=$PWD",
        "-e", "MYSQL_DATABASE=erp_os",
        "mcp/mysql"
      ]
    }
  }
}
EOF

# Update gitignore if needed
if ! grep -q "^.env.claude$" .gitignore 2>/dev/null; then
  cat >> .gitignore <<'EOF'

# Claude Code — personal & secrets (DO NOT COMMIT)
.env.claude
.claude/mcp.json
.claude/settings.local.json
EOF
  echo "✅ Updated .gitignore"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ MCP MySQL setup COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "NEXT STEPS:"
echo "  1. Fully quit Claude Code (not /clear)"
echo "  2. Reopen Claude Code"
echo "  3. In a new session, ask: \"list tools from erp-mysql\""
echo ""
echo "Files created/updated:"
echo "  .env.claude           (password, gitignored)"
echo "  .claude/mcp.json      (MCP config, gitignored)"
echo "  .gitignore            (added secrets entries)"
echo ""
echo "To verify manually:"
echo "  docker compose exec -T mysql mysql -uclaude_ro -p\"\$CLAUDE_MYSQL_PASSWORD\" erp_os -e 'SHOW TABLES;'"
echo ""
```

别忘了 `chmod +x docs/scripts/setup-mcp-mysql.sh`。

---

# 🔧 维护和清理

## 重置密码
```bash
bash docs/scripts/setup-mcp-mysql.sh
# 脚本 idempotent，重跑会 ALTER 密码
```

## 删除 Claude 账号
```bash
source .env.development
docker compose exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" \
  -e "DROP USER 'claude_ro'@'%'; FLUSH PRIVILEGES;"
rm -f .env.claude .claude/mcp.json
```

## 临时禁用 MCP
```bash
mv .claude/mcp.json .claude/mcp.json.bak
# 重启 Claude Code
```

---

# 相关文档

- `CLAUDE.md` Part 15: Claude Code 数据库操作规范（三大铁律）
- `.claude/commands/add-migration.md`: Schema 变更走 Alembic
- `docs/ddl.sql`: 初始 schema 参考
- `tasks/todo.md` Window 02: 数据模型 + Alembic（执行完后跑本文档 setup）
