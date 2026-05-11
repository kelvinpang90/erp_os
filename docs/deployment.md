# ERP OS — VPS 部署 Runbook（共享 vps_infra 栈）

把 erp_os 接入已经运行 crm_os 的 VPS，复用同一组 nginx / mysql / redis 容器（vps_infra 栈），通过子域名分流。

## 前置假设

- VPS 上已起 vps_infra 栈，external network `proxy_net`、`data_net` 已存在
- vps_infra 的 nginx 容器把 `/srv/infra/nginx/conf.d/` 挂载为配置目录，`*.conf` 自动加载
- crm_os 已运行在 `/opt/crm_os/`，对应域名 `crm.kelvinpeng.com`
- 你拥有主域 `kelvinpeng.com` 的 Cloudflare 控制权
- 域名：ERP `erp.kelvinpeng.com`，CRM `crm.kelvinpeng.com`

---

## 一、Cloudflare DNS

加一条 A 记录：
- `erp.kelvinpeng.com` → VPS 公网 IP，代理状态可启用（橙云）

CRM 已有的 A 记录不动。

---

## 二、共享基础设施改动（一次性）

### 2.0 Clone 仓库到 VPS（前置）

后续步骤要从仓库里拷贝 `erp.conf`，先把代码 clone 下来：

```bash
sudo mkdir -p /opt/erp_os && sudo chown $USER /opt/erp_os
cd /opt/erp_os
git clone https://github.com/<owner>/erp_os.git .
```

### 2.1 MySQL（infra_mysql 容器内）

```bash
docker exec -it infra_mysql mysql -uroot -p
```

```sql
CREATE DATABASE erp_os CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'erp_app'@'%' IDENTIFIED BY '<STRONG_PWD_1>';
GRANT ALL PRIVILEGES ON erp_os.* TO 'erp_app'@'%';
CREATE USER 'erp_ro'@'%' IDENTIFIED BY '<STRONG_PWD_2>';
GRANT SELECT ON erp_os.* TO 'erp_ro'@'%';
FLUSH PRIVILEGES;
```

`erp_app` 仅授 `erp_os.*`，不会误改 CRM 库；`erp_ro` 给 Claude Code MCP 只读用。

### 2.2 Redis（infra_redis）

不需要服务端改动。erp_os 占用 DB 5/6/7/8（default/cache/auth/rate）+ DB 10/11（Celery broker/result），完全错开 crm_os 占用的 DB 0–4。部署前 `redis-cli INFO keyspace` 确认无冲突。

### 2.3 nginx（vps_infra 共享）

> **真相源约定**：仓库内 `nginx/conf.d/erp.conf` 是**模板 + 版本控制副本**，**不**被任何 CI 自动同步到 VPS。真正生效的是 `/srv/infra/nginx/conf.d/erp.conf`，由人工 `scp` / `nano` 维护。改配置时两边都改，仓库改完 commit 留痕，VPS 改完 `nginx -t && nginx -s reload`。

**步骤 1：准备 SSL 证书（复用 `*.kelvinpeng.com` 通配符 Origin Certificate）**

已有一张 Cloudflare Origin Certificate 覆盖 `*.kelvinpeng.com, kelvinpeng.com`（CRM 已在用），通配符天然覆盖 `erp.kelvinpeng.com`，**不需要重新签**。在 VPS 上把已有 PEM 文件搬到一个共享目录，两个 vhost 都引用它，未来续签只改一处：

```bash
sudo mkdir -p /srv/infra/nginx/certs/_wildcard.kelvinpeng.com
sudo cp /srv/infra/nginx/certs/crm.kelvinpeng.com/fullchain.pem \
        /srv/infra/nginx/certs/_wildcard.kelvinpeng.com/
sudo cp /srv/infra/nginx/certs/crm.kelvinpeng.com/privkey.pem \
        /srv/infra/nginx/certs/_wildcard.kelvinpeng.com/
sudo chmod 644 /srv/infra/nginx/certs/_wildcard.kelvinpeng.com/fullchain.pem
sudo chmod 600 /srv/infra/nginx/certs/_wildcard.kelvinpeng.com/privkey.pem
```

容器内路径：`/etc/nginx/certs/_wildcard.kelvinpeng.com/{fullchain.pem,privkey.pem}`，与 `erp.conf` 中的 `ssl_certificate` 一致。

> 顺手把 `crm.conf` 里的 `ssl_certificate` 路径也改成 `_wildcard.kelvinpeng.com/`，统一证书源。改完 `nginx -t && nginx -s reload`。原 `crm.kelvinpeng.com/` 目录留作备份，确认无误后再删。

**步骤 2：放置 vhost 配置**

```bash
sudo cp /opt/erp_os/nginx/conf.d/erp.conf /srv/infra/nginx/conf.d/erp.conf
```

**步骤 3：reload nginx**

CRM 的 `/srv/infra/nginx/conf.d/crm.conf` 已是 `server_name crm.kelvinpeng.com;` + 443 SSL 模式，不需要改。
```bash
docker exec infra_nginx nginx -t            # 语法校验
docker exec infra_nginx nginx -s reload
```

---

## 三、首次部署 ERP（VPS 上执行）

> 仓库已在 2.0 步骤 clone 到 `/opt/erp_os`，下面所有命令默认在该目录执行。

### 3.1 准备 .env.production

```bash
cp .env.production.example .env.production
vim .env.production
```

必填：
- `GHCR_OWNER` — 小写 GitHub owner（与镜像名 `ghcr.io/<owner>/erp_os-*` 一致）
- `SECRET_KEY` — `openssl rand -hex 32`
- `DATABASE_URL` 中的 `erp_app` 密码
- `CORS_ORIGINS=https://erp.kelvinpeng.com`
- `ANTHROPIC_API_KEY`（如需 AI 功能）

### 3.2 登录 ghcr.io 并拉镜像

```bash
# 用一个 read:packages PAT
echo $GHCR_PAT | docker login ghcr.io -u <github_user> --password-stdin

docker compose -f docker-compose.prod.yml pull
```

### 3.3 启动 + 迁移 + seed

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml exec backend python scripts/seed_master_data.py
docker compose -f docker-compose.prod.yml exec backend python scripts/seed_transactional.py
```

### 3.4 reload nginx

```bash
docker exec infra_nginx nginx -s reload
```

### 3.5 冒烟

```bash
curl -fsS https://erp.kelvinpeng.com/health         # 200, {"status":"ok"}
curl -fsS https://crm.kelvinpeng.com/health         # CRM 不受影响
```

浏览器访问 `https://erp.kelvinpeng.com`，用 `admin@demo.my / Admin@123` 登录，看 Dashboard 出图、点一张 PO 跑通。

---

## 四、GitHub Actions 自动化部署

### 4.1 需要的 Secrets（仓库 Settings → Secrets）

| Secret | 值 |
|---|---|
| `VPS_HOST` | VPS 公网 IP 或 hostname |
| `VPS_USER` | SSH 用户（例 `deploy`） |
| `VPS_PORT` | SSH 端口（默认 22） |
| `VPS_SSH_KEY` | 私钥（与 VPS `~/.ssh/authorized_keys` 配对） |
| `ERP_PUBLIC_URL` | `https://erp.kelvinpeng.com`（冒烟用，可选） |

ghcr.io 拉取凭据：workflow 用 `secrets.GITHUB_TOKEN` 临时换出 docker login，VPS 端在 CI script 内即时 login/logout，不持久化。

### 4.2 Settings → Actions → Workflow permissions

勾上 "Read and write permissions"（packages: write 用）。

### 4.3 首次镜像可见性

第一次 push main 触发 build 后，到 GitHub → Packages 选择 `erp_os-backend` / `erp_os-frontend`：
- 改为 Public（demo 站点最简单，VPS 拉取免登录）
- 或保持 Private（更安全，但 CI script 已用 GITHUB_TOKEN inline login，足够）

---

## 五、验证清单

1. `docker compose -f docker-compose.prod.yml ps` 全部 healthy
2. `docker exec infra_nginx nginx -t` 通过
3. `curl https://erp.kelvinpeng.com/health` → 200
4. `curl https://crm.kelvinpeng.com/health` → 200（CRM 不受影响）
5. 4 个演示账号能登录（Admin / Manager / Sales / Purchaser）
6. Dashboard 出图，能下 1 张 PO + 1 张 SO + 1 张 e-Invoice（预校验走通）
7. `docker compose -f docker-compose.prod.yml logs celery_beat | grep "demo_reset"` 看到调度

---

## 六、回滚

```bash
# 软停（保留数据）
cd /opt/erp_os
docker compose -f docker-compose.prod.yml down

# 撤掉 nginx 路由
docker exec infra_nginx rm /etc/nginx/conf.d/erp.conf
docker exec infra_nginx nginx -s reload

# crm.conf 还原（如果改了）
docker exec infra_nginx sed -i 's/server_name crm.kelvinpeng.com;/server_name _;/' /etc/nginx/conf.d/crm.conf
docker exec infra_nginx nginx -s reload

# 硬清（含数据）
docker exec infra_mysql mysql -uroot -p -e "DROP DATABASE erp_os;"   # 先备份！
docker volume rm erp_os_uploads_data
```

---

## 七、风险点

- **R1 / SSL 证书过期**：Cloudflare Origin Certificate 默认 15 年，但要在到期前手动续签；可在 VPS 上 cron 定时检查 `openssl x509 -enddate -noout -in /srv/infra/nginx/certs/erp.kelvinpeng.com/fullchain.pem`。
- **R2 / Redis DB 冲突**：部署前用 `redis-cli` `INFO keyspace` 核对 crm_os 实际占用了哪些 DB；erp 默认 5/6/7/8/10/11，按需调整 `.env.production`。
- **R3 / MySQL 共享**：所有 Alembic / 脚本必须用 `erp_app` 账号，禁止用 root。`erp_app` 没有 crm_os 库权限，即使写错 SQL 也碰不到 CRM 数据。
- **R4 / 镜像可见性**：ghcr 包默认 Private。Workflow 内的 SSH script 已 inline `docker login` + `docker logout`，无需在 VPS 持久化凭据。
