# Shared Infrastructure (nginx + mysql + redis)

VPS 上多项目共用的基建栈。预期部署到 VPS 的 `/srv/infra/`（或任何位置），各业务项目（erp、未来 app2…）通过两个 external docker network 接入。

## 架构

```
Cloudflare (DNS + Full SSL + CDN)
        │
        ▼
  infra_nginx :80/:443  ──── proxy_net ──── erp_backend, erp_frontend, app2_*, ...
                                                   │
                                              data_net
                                                   │
                              infra_mysql, infra_redis
```

- **proxy_net**：nginx ↔ 各项目 web 容器
- **data_net**：各项目 ↔ mysql/redis（项目间互不可见）
- mysql/redis **不发布 host 端口**（只能从 data_net 内访问）

## 隔离策略

| 资源 | 隔离方式 |
|---|---|
| MySQL | 每个项目独立 database + 独立用户（仅授权该 db） |
| Redis | 每个项目分配 16 个 db 编号（erp: 0-15, app2: 16-31, ...）。`databases 256` |
| 流量 | nginx 子域名 vhost（erp.example.com, app2.example.com） |
| 网络 | docker external network `data_net` 不发布到 host |

## 首次部署

```bash
# 1. 进 VPS，把整个 infra/ 目录传上去
rsync -avz infra/ user@vps:/srv/infra/
ssh user@vps
cd /srv/infra

# 2. 配置 env
cp .env.example .env
vim .env  # 填 MYSQL_ROOT_PASSWORD

# 3. 编辑 mysql/init/00-init.sql，把 CHANGE_ME_* 替换为强密码
#    或保留默认，启动后用 provision-project.sh 重置

# 4. 准备 Cloudflare Origin Certificate
#    CF Dashboard → SSL/TLS → Origin Server → Create Certificate (15y)
#    把生成的 cert 存为 nginx/certs/origin.crt
#    把生成的 key  存为 nginx/certs/origin.key
chmod 600 nginx/certs/origin.key

# 5. 准备 ERP 的 vhost
cp nginx/conf.d/erp.conf.example nginx/conf.d/erp.conf
sed -i 's/erp\.example\.com/erp.YOUR-DOMAIN.com/g' nginx/conf.d/erp.conf

# 6. 启动
docker compose up -d
docker compose ps  # 全 healthy

# 7. 部署 ERP 项目（见项目根 README）
```

## 新增项目

```bash
cd /srv/infra
./scripts/provision-project.sh app2 16
# 按脚本提示完成 nginx vhost 和 reload
```

## 常用命令

```bash
# Reload nginx（改了 conf.d 后）
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload

# 进 mysql shell
docker compose exec mysql mysql -uroot -p

# 看 redis 各 db 占用
docker compose exec redis redis-cli INFO keyspace

# 备份 mysql（建议 cron daily）
docker compose exec -T mysql mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" \
    --all-databases --single-transaction --routines --triggers \
    | gzip > /srv/backups/mysql-$(date +%F).sql.gz

# 看 nginx 访问日志
docker compose exec nginx tail -f /var/log/nginx/access.log
```

## Cloudflare 设置要点

1. DNS A 记录指 VPS，**橙云**（Proxied）
2. SSL/TLS 模式：**Full (strict)**
3. Origin Server → Create Certificate（15 年）→ 装到 `nginx/certs/`
4. （可选）Authenticated Origin Pulls：源站 nginx 加 `ssl_verify_client on` + CF root cert，只接受 CF 流量

## 安全检查清单

- [ ] `infra/.env` 不进 Git（已在根 .gitignore 中 `.env.*` 排除）
- [ ] `nginx/certs/*.key` 不进 Git
- [ ] `mysql/init/00-init.sql` 上线前替换所有 `CHANGE_ME_*`，或在 mysql 启动后立即用 ALTER USER 改密
- [ ] `redis.conf` 如开放跨主机访问，必须设 `requirepass`
- [ ] VPS 防火墙只开 22/80/443，3306/6379 严禁对外
- [ ] CF "Authenticated Origin Pulls" 开启（防绕过 CF 直连源站 IP）
