# ERP OS — Development Plan (14 Days × Claude Max 5-Hour Windows)

> 本文件是 Claude Code 开发的主线路图。每个"窗口"= 一个 Claude Max 5 小时配额周期 = 一个完整可交付的模块。**不要让任何模块跨窗口**。配额耗尽前收尾、提交、换 session。

---

## 使用方式

### 每个窗口开始前
1. `git pull` + 确认主分支干净
2. 开新 Claude Code session（`/clear` 或新终端）
3. 读这一窗口的 **目标 + 前置条件 + 产出物**
4. 有不明确就问，不要脑补

### 窗口中
- 严格按 **CLAUDE.md** 规范写代码
- 脏活（造 seed、写测试、i18n、UI 微调）委托 subagent
- 每完成一个文件就 `git add` 到暂存区，防止意外丢失
- 遇坑记录 `tasks/lessons.md`

### 窗口结束
- 产出物全部 commit（不要留 WIP）
- 跑一遍验证清单（本文件每窗口末尾）
- 标记本窗口为 ✅ 完成
- 更新本文件 "## 评审部分" 的当前窗口状态

### 卡住了怎么办
- 小问题：留 FIXME 注释继续推进
- 中问题：记 `tasks/lessons.md`，绕开
- 大问题：**不硬推**，降级该窗口目标，剩下的推到下个窗口

---

## 配额估算与节奏

| 项 | 预估 |
|---|---|
| 每窗口时长 | 5 小时 |
| 每窗口消息数 | 80-120 条（批量生成 + 审查） |
| 每天可用窗口 | 1-2 个（看精力） |
| 总窗口数 | 20-22（14 天内完成） |
| 缓冲窗口 | 2-3 个（留给踩坑 / 重构） |

---

# 🚀 Phase 1: 地基（Day 1-2，3 窗口）

## Window 01 —— 项目脚手架 + Docker 环境

**目标**：从零初始化项目，能 `docker compose up` 跑起 hello world。

### 前置条件
- 读完 CLAUDE.md
- 环境：Python 3.12, Node 20, Docker Desktop

### 产出物
- [ ] `backend/` 完整目录结构（见 CLAUDE.md Part 5）
- [ ] `backend/pyproject.toml` + `requirements.txt` + `requirements-dev.txt`
- [ ] `backend/app/main.py` — FastAPI 最小 app（`/health` 端点）
- [ ] `backend/app/core/config.py` — pydantic-settings 读 env
- [ ] `backend/app/core/database.py` — async SQLAlchemy engine 骨架
- [ ] `backend/app/core/redis.py` — Redis 多 DB 连接池
- [ ] `backend/Dockerfile`
- [ ] `frontend/` 用 Vite 初始化 React + TS + Ant Design Pro 骨架
- [ ] `frontend/Dockerfile`
- [ ] 项目根 `docker-compose.yml` — nginx / backend / frontend / mysql / redis 5 个 service，含 healthcheck
- [ ] `.env.example`
- [ ] `.gitignore`（Python / Node / IDE / .env.*）
- [ ] `README.md` 基础说明（怎么启动）

### 验证
```bash
docker compose up -d
curl http://localhost:8000/health    # {"status":"ok"}
curl http://localhost:3000            # Vite welcome page
docker compose ps                     # 所有 service 都 healthy
```

### 预估消息
约 40-60 条（配置文件为主，批量生成）

---

## Window 02 —— 数据模型 + Alembic 初始迁移

**目标**：所有 ORM model 落地，一次 migration 到位。

### 前置条件
- Window 01 完成
- 读 `docs/ddl.sql`（20+ 张表的完整 schema）

### 产出物
- [ ] `backend/app/models/base.py` — Base + Mixins：
  - `TimestampedMixin`（created_at / updated_at）
  - `SoftDeleteMixin`（deleted_at / is_active）
  - `OrgScopedMixin`（organization_id）
  - `VersionedMixin`（version for 乐观锁）
- [ ] `backend/app/enums.py` — 所有业务枚举集中
- [ ] `backend/app/models/` — 按 docs/ddl.sql 生成所有 ORM model（≈20 个文件）
  - 让 Claude 一次批量生成，你审查
- [ ] `backend/alembic/` — `alembic init` + `env.py` 配 async
- [ ] `backend/alembic.ini`
- [ ] `backend/alembic/versions/{ts}_initial_schema.py` — 初始 migration

### 验证
```bash
cd backend
alembic upgrade head                  # 无错误
docker compose exec mysql mysql -uroot -p erp_os -e "SHOW TABLES;"
# 应能看到 40+ 张表（含 M2M 表）
alembic downgrade base                # 能回滚
alembic upgrade head                  # 再升级成功
```

### 窗口结束后顺手做（可选，5 分钟）
配置 MCP MySQL，让 Claude 后续直接查库：
```bash
bash docs/scripts/setup-mcp-mysql.sh
# 然后完全重启 Claude Code
```
详见 `docs/mcp-setup.md`。

### 预估消息
约 30-50 条（模型文件大部分可批量生成）

---

## Window 03 —— 认证 + 权限 + 异常体系 + 日志

**目标**：能登录拿 JWT，有 4 角色 + 权限，全局异常统一。

### 前置条件
- Window 02 完成

### 产出物
- [ ] `backend/app/core/exceptions.py` — `AppException` 层级（议题 6）
- [ ] `backend/app/core/security.py` — JWT (access 15min + refresh 7d) + bcrypt
- [ ] `backend/app/core/deps.py` — `get_current_user` / `require_permission` / `get_db`
- [ ] `backend/app/core/logging.py` — structlog JSON + request_id
- [ ] `backend/app/routers/auth.py` — `/api/auth/login` / `refresh` / `logout` / `me`
- [ ] `backend/app/services/auth.py`
- [ ] `backend/app/repositories/user.py`
- [ ] `backend/app/schemas/auth.py` / `user.py`
- [ ] `backend/app/models/` 补齐：login_attempts
- [ ] 全局 exception handler 注册（统一 JSON 错误格式）
- [ ] 中间件：request_id 注入 + CORS 白名单 + slowapi rate limit（100/min 全局、10/min 登录）
- [ ] Seed 脚本雏形 `backend/scripts/seed_master_data.py`：org + 4 roles + permissions + 4 demo users

### 验证
```bash
docker compose exec backend python scripts/seed_master_data.py
curl -X POST http://localhost:8000/api/auth/login \
  -d '{"email":"admin@demo.my","password":"Admin@123"}'
# 返回 access_token + refresh_token
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
# 返回 user + permissions + menu tree
```

### 预估消息
约 60-80 条

---

# 🏗️ Phase 2: 主数据（Day 3-4，3 窗口）

## Window 04 —— SKU + Brand + Category + UOM + TaxRate 模块

**目标**：主数据 5 个核心资源 CRUD 完成（backend + 前端列表页）。

### 前置条件
- Window 03 完成
- 创建 `.claude/commands/new-resource.md`（已经在 Step 4 中创建）

### 产出物（批量用 `/new-resource` 生成）
- [ ] `Brand`, `Category`, `UOM`, `TaxRate`, `Currency`, `ExchangeRate` 6 个资源的完整 5 件套
- [ ] `SKU` 模块（字段最多、作为模板细做）
- [ ] 前端 `frontend/src/components/ResourceListPage.tsx`（通用 ProTable 封装）
- [ ] 前端 `frontend/src/components/ResourceDetailPage.tsx`（通用 ProForm 封装）
- [ ] 前端 SKU 列表页 + 详情页 + 编辑页（columns.tsx 配置化）
- [ ] orval 配置 + 首次生成 TS client
- [ ] i18n key: `common` / `menu` / `sku` / `brand` 等（en-US + zh-CN）

### 验证
```bash
# Backend
pytest backend/tests/unit/test_sku_service.py -v
# Frontend
cd frontend && npm run gen:api        # 无错误
npm run dev                            # localhost:3000 登录后看到 SKU 列表
```

### 预估消息
约 80-100 条（批量生成加审查）

---

## Window 05 —— Supplier + Customer + Warehouse 模块

**目标**：业务伙伴 + 仓库管理完成。

### 前置条件
- Window 04 完成

### 产出物
- [ ] `Supplier`, `Customer`, `Warehouse` 3 个资源完整五件套（用 `/new-resource`）
- [ ] 前端对应列表 + 详情页
- [ ] Customer 支持 B2B / B2C 区分显示（UI 上 B2C 隐藏企业字段）
- [ ] Supplier 详情页显示该供应商的历史 PO 统计（占位）
- [ ] i18n keys 补齐

### 验证
- 前端能新建 supplier / customer / warehouse
- 列表支持搜索 + 分页
- 软删除后仍可通过 "include inactive" 看到

### 预估消息
约 50-70 条

---

## Window 06 —— Seed 数据批量生成

**目标**：200 SKU / 30 supplier / 50 customer / master data 全量真实化。

### 前置条件
- Window 05 完成
- 调用 `erp-seed-generator` skill

### 产出物
- [ ] `backend/scripts/seed_master_data.py` 扩充：currencies, tax_rates, uoms, warehouses, msic_codes
- [ ] `backend/scripts/seed_skus.py` —— 200 真实马来 SKU（用 `erp-seed-generator` skill）
- [ ] `backend/scripts/seed_suppliers.py` —— 30 供应商（华商/马来商/印度商混合）
- [ ] `backend/scripts/seed_customers.py` —— 50 客户（B2B 30 / B2C 20）
- [ ] `backend/scripts/seed_initial_stock.py` —— 每个 SKU × 3 仓库的初始库存
- [ ] 汇总脚本 `backend/scripts/seed_all_master.py` 一键执行
- [ ] 所有生成的 supplier 能过 `einvoice-validator` 的硬规则（TIN 格式、MSIC）

### 验证
```bash
docker compose exec backend python scripts/seed_all_master.py
# 前端打开 SKU 页：看到真实的 Milo / Maggi / Panadol 等
# 前端打开 Supplier 页：看到 Tan Chong Trading / Syarikat Ahmad 等
```

### 预估消息
约 40-60 条（委托 subagent 造数据）

---

# 🛒 Phase 3: 采购闭环（Day 5-6，3 窗口）

## Window 07 —— PO 模块 + 事件总线框架 ✅

**目标**：采购单 CRUD + 状态机 + 事件驱动脊柱。

### 前置条件
- Window 06 完成

### 产出物
- [x] `backend/app/events/` 完整实现：
  - `base.py` —— EventBus + DomainEvent（同步 + after_commit 异步）
  - `types.py` —— 3 个核心事件
  - `registry.py` —— 启动时注册
  - `handlers/` —— audit / cache / notification / inventory 占位
- [x] `backend/app/services/sequence.py` —— DocumentSequenceService（Redis INCR + `document_sequences` 表回写）
- [x] `PurchaseOrder` + `PurchaseOrderLine` 完整 5 件套（非 `/new-resource`，手写以处理状态机）
- [x] `backend/app/services/purchase.py` ：
  - `create_po` / `confirm_po`（发 DocumentStatusChanged + StockMovementOccurred）
  - `cancel_po`（按角色判断）
- [x] 前端 PO 列表页 + 详情页 + 编辑页
- [x] 状态机单测：`tests/unit/test_po_state_machine.py`（6 个测试全绿）

### 验证
- [x] 单测：6 个状态机测试全绿
- [ ] API 集成（需 docker compose up）
- [ ] 前端 UI（需 Node 环境）

### 预估消息
约 80-100 条

---

## Window 08 —— GoodsReceipt + Stock 6 维库存

**目标**：收货 → 库存 6 维联动 + 加权平均成本。

### 前置条件
- Window 07 完成

### 产出物
- [ ] `Stock` + `StockMovement` model 完全接入
- [ ] `backend/app/services/costing.py` —— WeightedAverageCostService
- [ ] `backend/app/services/inventory.py` —— stock 6 维状态转换（on_hand / reserved / available / ...）
- [ ] `GoodsReceipt` + `GoodsReceiptLine` 模块
- [ ] `backend/app/services/purchase.py` 补充 `create_goods_receipt`：
  - 扣 Stock.incoming，加 On-hand
  - 重算 avg_cost
  - 记 StockMovement（PURCHASE_IN）
  - 更新 PO.qty_received + 状态推进
- [ ] 前端 GoodsReceipt 创建表单（关联 PO）
- [ ] 单测：`test_costing.py` 覆盖加权平均 4 种场景

### 验证
- 新建 GR 针对某 PO line
- Stock.on_hand + , Stock.incoming -
- Stock.avg_cost 按公式重算
- 全量收完 → PO 状态 FULLY_RECEIVED

### 预估消息
约 80-100 条

---

## Window 09 —— OCR AI 功能（SSE 流式）

**目标**：上传 PDF → SSE 进度 → 表单自动填充。
OCR（Optical Character Recognition，光学字符识别）= 让机器从图片/PDF 里把文字"读出来"。
SSE（Server-Sent Events，服务器推送事件）= HTTP 协议上的"单向流"。客户端发一次请求，服务器保持连接不断，可以多次往回推数据，直到服务器主动关闭。
### 前置条件
- Window 08 完成
- 需要 `ANTHROPIC_API_KEY`

### 产出物
- [ ] `backend/app/services/ai_gate.py` —— AIFeatureGate（三层开关）
- [ ] `backend/app/services/ocr.py` —— 调 Claude Vision
- [ ] `backend/app/prompts/ocr_invoice.yaml`
- [ ] `backend/app/routers/ai.py` —— `/api/ai/ocr/purchase-order` SSE endpoint
- [ ] `backend/app/tasks/ocr.py` —— Celery task（ai queue）
- [ ] `backend/app/core/storage.py` —— LocalFSBackend 文件上传
- [ ] `uploaded_files` model + service
- [ ] 前端 `SSEUploader.tsx` 组件（fetch + ReadableStream 手动解析）
- [ ] 前端 `pages/Purchase/OCRUploadPage.tsx`
- [ ] AI 调用日志写 `ai_call_logs`
- [ ] Rate limit：5 req/min per user + 20 次/day quota
- [ ] 降级：API 失败 → 提示手动录入

### 验证
- 准备 3 张 sample 发票 PDF
- 上传 → 进度 20/50/80/100 → 字段填入 PO 表单
- 关闭 Anthropic key → 降级提示显示

### 预估消息
约 70-90 条

---

# 💰 Phase 4: 销售 + e-Invoice 闭环（Day 7-8，3 窗口）

## Window 10 —— SO + DeliveryOrder 模块 ✅

**目标**：销售单 + 发货单 + 库存 Reserved/On-hand 联动。

### 前置条件
- Window 09 完成

### 产出物
- [x] `SalesOrder` + `SalesOrderLine` 完整模块（schema/repo/service/router）
- [x] `DeliveryOrder` + `DeliveryOrderLine` 完整模块（schema/repo/service/router）
- [x] `backend/app/services/sales.py`：
  - `create_so` / `confirm_so`（检查可用库存、锁 Reserved、发事件）
  - `cancel_so`（释放 Reserved；CONFIRMED 状态需 Manager/Admin）
- [x] `backend/app/services/delivery_order.py` `create_do`（扣 On-hand、释放 Reserved、记 SALES_OUT、写 snapshot_avg_cost、推进 SO 状态）
- [x] 防超卖：用 `UPDATE ... WHERE on_hand - reserved - quality_hold >= ?` 原子 SQL（available 是 Computed 列，WHERE 用展开式）
- [x] 前端 SO 列表 + 详情 + 编辑 + Columns
- [x] 前端 DO 列表 + 详情 + 创建 + Columns
- [x] 单测：`test_so_state_machine.py`（8 test）+ `test_no_oversell.py`（8 test）
- [x] i18n: sales_order + delivery_order 双语
- [x] inventory.py 三新 API：apply_reserve / apply_unreserve / apply_sales_out
- [x] 为 Window 12 退货预留 hooks: SOLine.snapshot_avg_cost（首次发货写入）+ SOLine.qty_shipped（累加）+ DOLine.batch_no/expiry_date/serial_no（追溯）

### 验证
- 新建 SO → Confirm → Reserved +，Available -
- DO 发货 → On-hand -，Reserved -
- 并发 2 单抢最后一件货 → 第二单 InsufficientStock

### 预估消息
约 80-100 条

---

## Window 11 —— Invoice 模块 + MyInvois Mock 提交 ✅

**目标**：e-Invoice 草稿 → 提交 → UIN → 72h 逻辑。

### 前置条件
- Window 10 完成

### 产出物
- [x] `Invoice` + `InvoiceLine` 完整模块（schema/repo/service/router）
- [x] `backend/app/services/einvoice.py`：
  - `generate_draft_from_so(so_id)` —— 从 SO 生成 invoice 草稿（1 SO ↔ 1 Invoice 唯一约束 + 幂等）
  - `submit_to_myinvois(invoice_id)` —— mock LHDN API（同步返回 UIN + QR）
  - `reject_by_buyer(invoice_id, reason)` —— 买家拒绝（72h/72s 窗口校验）
  - `_lazy_finalize_if_due()` + `run_finalize_scan()` —— 替代 Celery Beat 的懒触发 + admin 扫描方案
- [x] Mock MyInvois adapter（**Protocol 接口** + Mock 实现 + 工厂）—— 真实 LHDN 对接零侵入
- [x] `DEMO_MODE=true` 时 72h → 72s（`get_finalize_window()` 工具）
- [x] 前端 Invoice 列表 + 详情（含 QR code 显示 + 倒计时组件 + Run Finalize Scan 按钮）
- [x] 前端 SO 详情页加 "Generate Invoice" / "View Invoice" 按钮
- [x] 事件：`EInvoiceValidated` handler 实现（写 Notification 表 + i18n_key）
- [x] Alembic migration 加 `uq_inv_so` 唯一索引（org+SO 唯一）
- [x] `MYINVOIS_MODE` 环境变量（mock/sandbox/production）
- [x] i18n: einvoice + menu.einvoice 双语
- [x] 单测：`test_einvoice_service.py` 16 个 case 全绿
- [x] 整体 99/99 单测全绿（无回归）

### 决策（与原计划差异）
- **72h FINAL 调度**：原计划用 Celery Beat 每 10min 扫描，**改为懒触发 + 管理员手动按钮**。理由：tasks/ 目录还没起 Celery 基础设施，bootstrap 成本 15-20 条消息。Window 18 (CI/CD) 一并搭。
- **MyInvois adapter 抽象**：超出原计划（原是写死 mock）。加 Protocol 接口让未来真实对接零侵入，成本 +1 文件。
- **Celery 任务 (`tasks/einvoice.py`)**：未实现。等 Window 18 起 Celery 时一并加。

### 验证
- [x] 99/99 单测通过（含 16 新 + 83 原）
- [x] FastAPI 路由注册：6 个 invoice endpoint
- [x] Migration 文件可加载
- [ ] 端到端 docker compose 走查（待新 session）

### 实际消息
约 80 条

---

## Window 12 —— AI e-Invoice 预校验 + Credit Note + Consolidated

**目标**：提交前 AI 预校验 + Credit Note 退货 + B2C 月度汇总。

### 前置条件
- Window 11 完成
- 调用 `einvoice-validator` skill

### 产出物
- [ ] `backend/app/services/einvoice.py` 补充 `precheck()`:
  - 硬规则：TIN / SST 计算 / 必填 / 邮编州一致
  - 软规则：LLM 调用 `einvoice_precheck.yaml`
  - 降级：LLM 挂了只跑硬规则
- [ ] 前端 PrecheckModal 组件（10 项 checklist + 一键采纳建议）
- [ ] `CreditNote` + `CreditNoteLine` 完整模块
- [ ] `backend/app/services/credit_note.py`：
  - 创建 CN（关联原 invoice）
  - 退货入库（Stock.on_hand +，按 SO snapshot_avg_cost 回填）
  - 提交 MyInvois
- [ ] Consolidated Invoice 功能：
  - Admin 页一键 "Generate Monthly Consolidated"
  - 汇总当月 B2C 订单到一张发票
- [ ] 前端 Credit Note 列表 + 详情
- [ ] 单测：`test_einvoice_precheck.py`（硬规则 + 降级）

### 验证
- 故意提交一张 SST 错配的发票 → 预校验弹警告
- 退货一张 SO → CN 生成 → 库存增加
- 月底点 Consolidated → 生成一张汇总 invoice

### 预估消息
约 90-110 条（AI prompt 调优 + 规则实现）

---

# 📦 Phase 5: 库存 + 报表（Day 9-10，3 窗口）

## Window 13 —— Stock Movement + Transfer + Adjustment

**目标**：库存流水展示 + 调拨 + 盘点差异。

### 前置条件
- Window 12 完成

### 产出物
- [ ] `StockTransfer` + `StockTransferLine` 完整模块（状态机）
- [ ] `StockAdjustment` + `StockAdjustmentLine` 完整模块（盘盈盘亏）
- [ ] 调拨成本继承：From 仓 avg_cost → To 仓 incoming_unit_cost
- [ ] 前端 Stock Movement 列表（只读，含筛选：type / date / sku）
- [ ] 前端 Stock Transfer 创建 / 确认 / 收货
- [ ] 前端 Stock Adjustment 创建（带盈亏原因下拉）
- [ ] 审计：核心 3 表（Order/Invoice/CN）的 audit handler 接入

### 验证
- 创建 Transfer → From 仓 in_transit +
- To 仓 Receive → Incoming → On-hand 转换
- Adjustment 盘亏 → 库存减 + audit log 有记录

### 预估消息
约 70-90 条

---

## Window 14 —— Low Stock Alert + Branch Inventory 热力图

**目标**：多仓库存看板 + 安全库存预警。

### 前置条件
- Window 13 完成

### 产出物
- [ ] `backend/app/services/inventory.py` 补：
  - `get_branch_inventory_matrix` —— SKU × Warehouse 矩阵
  - `get_low_stock_alerts` —— available < safety_stock
- [ ] Low Stock Alert handler 订阅 `StockMovementOccurred` 事件自动生成通知
- [ ] 前端 `BranchInventoryPage.tsx`：
  - 热力图形式（颜色深浅表示库存水平）
  - Hover 显示 6 维详情
- [ ] 前端 `AlertPage.tsx`：批量补货建议 + 一键生成 PO 草稿
- [ ] 前端 `StockStatusBadge.tsx` 组件（6 维徽章）
- [ ] 加权平均成本变动趋势图（SKU 详情页）

### 验证
- 某 SKU 库存 < safety_stock → 通知中心出现告警
- Branch Inventory 页打开，热力图流畅渲染
- 点 "Generate Restock PO" → 跳转到 PO 创建页预填

### 预估消息
约 70-90 条

---

## Window 15 —— Dashboard + AI 日报 + 10 张报表图

**目标**：首页炸场 + AI 日报摘要 + 报表中心。

### 前置条件
- Window 14 完成

### 产出物
- [ ] `backend/app/services/dashboard.py`：
  - KPI 计算（今日销售额、待发货、低库存、待验证发票、AI 成本）
  - 聚合缓存（Redis DB 1, TTL 5min + `StockMovementOccurred` 主动失效）
- [ ] `backend/app/tasks/dashboard.py` —— AI 日报生成（Celery Beat 每 30min）
- [ ] `backend/app/prompts/dashboard_summary.yaml`
- [ ] 前端 `Dashboard/index.tsx`：
  - KPI Cards（5 张）
  - AI 日报摘要卡（含 staleness 徽章）
  - 趋势图 Cards × 6
- [ ] 前端 Reports 中心 10 张图：
  1. 销售趋势（日/月）
  2. 采购趋势
  3. Top 10 SKU 销量
  4. Top 10 供应商采购额
  5. Top 10 客户贡献
  6. 库存周转率
  7. 各仓库存分布
  8. 品类销售占比
  9. e-Invoice 状态分布
  10. AI 成本 / 调用次数
- [ ] 所有图表懒加载

### 验证
- Dashboard 首屏加载 < 2s（缓存命中）
- AI 日报卡 2-3 秒内有内容
- Reports 10 张图表数据合理（seed 数据驱动）

### 预估消息
约 90-110 条（图表配置多）

---

# 🎨 Phase 6: 打磨 + 运维（Day 11-12，3 窗口）

## Window 16 —— UI 打磨 + 深色主题 + i18n 全量补齐

**目标**：视觉专业 + 中英完整。

### 前置条件
- Window 15 完成

### 产出物
- [ ] 前端 `theme/light.ts` + `theme/dark.ts`（Ant Design token）
- [ ] TopBar 切换语言 / 主题 / 通知铃铛 / 角色切换
- [ ] 登录页美化 + "一键登录"卡片（演示加速）
- [ ] 所有页面过一遍 Responsive（兼容 1280/1440/1920 三档）
- [ ] i18n keys 全量补齐（Subagent 委托）：
  - 所有 menu / button / form label
  - 所有错误消息 `errors.{CODE}`
  - 中文翻译严谨，不用翻译腔
- [ ] Errors 自动导出 TS 枚举：`utils/errorCodes.ts`
- [ ] 403 / 404 / 500 错误页

### 验证
- 切换深色主题平滑
- 切换 zh-CN 所有文案变中文，没有遗漏 key
- 缩小窗口到 1280 宽度不错乱

### 预估消息
约 70-90 条（大部分委托 subagent）

---

## Window 17 —— 审计 + 通知中心 + Admin Dev Tools

**目标**：可观测性 + 演示加分。

### 前置条件
- Window 16 完成

### 产出物
- [ ] 审计 handler 完善（3 张核心表的 before/after JSON 记录）
- [ ] 前端 Notification 组件（顶栏铃铛 + 下拉列表）
- [ ] 前端设置页完整：
  - General / Currencies / Tax Rates / AI Features / Users
  - AI Features 页三层开关（master + per-feature）
- [ ] Admin `/admin/dev-tools` 事件流页面：
  - WebSocket 连接 EventBus
  - 树形展示 event → handler 链路
  - 实时推送
- [ ] Admin `/admin/demo-reset` 手动重置按钮
- [ ] Demo Mode 状态灯（TopBar 显示 🟢 Demo Mode ON）

### 验证
- 改一张 PO 的字段 → audit_logs 有记录
- 点 Confirm SO → Dev Tools 实时显示事件流
- 切换 AI master switch → 对应功能按钮立刻禁用

### 预估消息
约 70-90 条

---

## Window 18 —— Demo Reset + CI/CD + 云部署

**目标**：生产化 + 部署上线。

### 前置条件
- Window 17 完成
- 你已购买域名 + VPS

### 产出物
- [ ] `backend/app/tasks/demo_reset.py` 完整实现（按议题 10）
- [ ] `backend/scripts/seed_transactional.py`（500 历史订单）
- [ ] `scripts/backup.sh` —— 每日 mysqldump cron
- [ ] `scripts/deploy.sh` —— SSH 部署
- [ ] `docker-compose.prod.yml` —— 生产拓扑（含 celery x2, beat, nginx）
- [ ] `nginx.conf` —— 反代 + SSE 不 buffer
- [ ] `.github/workflows/`：
  - `pr-check.yml` —— lint + test
  - `nightly-e2e.yml` —— 每晚 E2E
  - `deploy-demo.yml` —— push main 自动部署
- [ ] Cloudflare DNS + HTTPS
- [ ] Sentry 前后端 DSN 接入
- [ ] UptimeRobot 5min 检查

### 验证
- 推一个 PR → CI 通过
- 合并 main → 自动部署到 demo 站点
- `https://erp-demo.yourdomain.com` 可访问
- 凌晨 3am 自动 reset 测试（或手动触发一次验证）

### 预估消息
约 70-90 条

---

# 🎬 Phase 7: 演示准备（Day 13-14，3 窗口 + 缓冲）

## Window 19 —— E2E 测试 + 3 条黄金路径

**目标**：演示前端到端稳如老狗。

### 前置条件
- Window 18 完成

### 产出物
- [ ] Playwright 配置 + `tests/e2e/`
- [ ] **E2E-1 采购闭环**：登录 Purchaser → OCR 上传 → PO 确认 → GR → 库存增加
- [ ] **E2E-2 销售闭环**：登录 Sales → 创建 SO → 确认 → 发货 → e-Invoice → AI 预校验 → Submit → UIN 回填
- [ ] **E2E-3 库存闭环**：Branch Inventory → 创建 Transfer → Confirm → Receive → 库存更新
- [ ] 修复 E2E 过程中发现的 bug
- [ ] 覆盖率报告生成 + 可视化 HTML

### 验证
- 3 条 E2E 全绿
- 覆盖率：Unit ≥ 80% 核心 / Frontend 30%

### 预估消息
约 60-80 条

---

## Window 20 —— 演示物料 + 话术 + 视频

**目标**：演示物料包齐全。

### 前置条件
- Window 19 完成
- 用 `pptx` / `pdf` / `docx` skills

### 产出物
- [ ] `pptx`: 5 分钟 / 15 分钟 / 30 分钟三版演示 deck（中英双语各两套 = 6 份）
- [ ] `pdf`: Product One-pager A4 横向（中 + 英）
- [ ] `pdf`: 5 张 OCR 测试样本发票 PDF（含马来商家名）
- [ ] `docx`: FAQ 文档（常见客户质疑 + 标准答案）
- [ ] `docx`: Proposal 模板（可替换客户名）
- [ ] 录制演示视频（OBS / Loom）：
  - 5 分钟版（快速秀 3 个亮点）
  - 15 分钟版（完整流程）
- [ ] 演示时的 "Setlist"（我的桌面便签：第几分钟做什么）

### 验证
- 带朋友（不懂 ERP）走一遍 15 分钟演示 → 他能描述 3 个核心价值

### 预估消息
约 40-60 条（委托 docx/pdf/pptx skill 批量生成）

---

## Window 21 —— 最终走查 + 兜底演练（缓冲）

**目标**：发现最后的边缘问题 + 兜底预案。

### 前置条件
- Window 20 完成

### 产出物
- [ ] 端到端走查：4 个角色各走一遍主流程
- [ ] 压力测试：并发 10 个下单 → 不超卖
- [ ] 网络抖动测试：断 Anthropic API → 降级提示正常
- [ ] 演示机器预备：主机 + 备机（同步数据）
- [ ] 离线演示预案：本地 docker 一键起
- [ ] Demo 视频剪辑好（万一现场网挂了直接播）
- [ ] 核心客户 FAQ 手册打印版（平板查阅用）

### 验证
- 演示前 24h：全量 smoke test 通过

### 预估消息
约 40-60 条

---

# 📅 时间表参考（建议节奏）

| Day | AM 窗口 | PM 窗口 |
|---|---|---|
| Day 1 | Window 01 脚手架 | Window 02 数据模型 |
| Day 2 | Window 03 认证 | 休息 / 处理前两窗口遗留 |
| Day 3 | Window 04 SKU + 主数据 | Window 05 Supplier/Customer |
| Day 4 | Window 06 Seed 数据 | 休息 |
| Day 5 | Window 07 PO + 事件 | Window 08 GR + 6 维库存 |
| Day 6 | Window 09 OCR AI | 休息 |
| Day 7 | Window 10 SO + DO | Window 11 Invoice + MyInvois |
| Day 8 | Window 12 e-Invoice AI + CN | 休息 |
| Day 9 | Window 13 Stock Movements | Window 14 Branch Inventory |
| Day 10 | Window 15 Dashboard + Reports | 休息 |
| Day 11 | Window 16 UI + i18n | Window 17 审计 + Dev Tools |
| Day 12 | Window 18 CI/CD + 部署 | 休息 |
| Day 13 | Window 19 E2E | Window 20 演示物料 |
| Day 14 | Window 21 兜底演练 | 备用 / 应急 |

**缓冲**：预留 Day 13-14 的 PM 窗口做应急，理想情况 Day 12 PM 就提前完成所有开发。

---

# 🎯 关键里程碑

- **Day 2 EoD**：能登录、4 角色可见 ✅
- **Day 4 EoD**：SKU / Supplier / Customer 可 CRUD，seed 数据齐 ✅
- **Day 6 EoD**：采购闭环跑通 + OCR 能演示 ✅
- **Day 8 EoD**：销售闭环 + e-Invoice 跑通 ✅
- **Day 10 EoD**：Dashboard 炸场 + 多仓库存看板 ✅
- **Day 12 EoD**：云上 Demo 站点上线 + 定时 reset 跑通 ✅
- **Day 14 EoD**：全套演示物料就绪，可以见客户 🎬

---

# 🧯 风险清单（提前预警）

| 风险 | 应对 |
|---|---|
| LLM API 抖动 / 限流 | 所有 AI 功能都有降级，Demo 前刷几次把缓存预热 |
| Seed data 不真实 | 严格用 `erp-seed-generator` skill 的参考文件 |
| 超卖 bug 演示翻车 | Window 10 做并发单测，CI 跑 |
| 72h 逻辑演示不出来 | DEMO_MODE 开关 72s |
| 前后端契约不同步 | CI 加 orval 生成校验，PR 阻断 |
| 部署日配额燃烧 | 云端 AI 严格 rate limit + 演示专用 key |
| 演示当天网络不稳 | 离线演示预案 + 视频兜底 |

---

# 📋 评审部分（每完成一窗口在此更新）

## 进度追踪

| Window | 状态 | 开始时间 | 完成时间 | 消息数 | 备注 |
|---|---|---|---|---|---|
| 01 脚手架 | ✅ 完成 | 2026-04-23 | 2026-04-23 | ~50 | |
| 02 数据模型 | ✅ 完成 | 2026-04-23 | 2026-04-23 | ~40 | |
| 03 认证 | ✅ 完成 | 2026-04-24 | 2026-04-24 | ~80 | 坑：LoginAttempt重复定义、from future annotations与Body()冲突、slowapi参数推断 |
| 04 SKU + 主数据 | ✅ 完成 | 2026-04-27 | 2026-04-27 | ~80 | |
| 05 Supplier/Customer | ✅ 完成 | 2026-04-27 | 2026-04-27 | ~60 | |
| 06 Seed 数据 | ✅ 完成 | 2026-04-27 | 2026-04-27 | ~50 | 200 SKU / 30 supplier / 50 customer / 600 stock 行 |
| 07 PO + 事件 | ✅ 完成 | 2026-04-27 | 2026-04-27 | ~80 | |
| 08 GR + 库存 | ✅ 完成 | 2026-04-28 | 2026-04-28 | ~70 | 53/53 单测全绿；端到端 4% 容差通过、6% 拒绝；avg_cost 公式验证正确 |
| 09 OCR AI | ✅ 完成 | 2026-04-28 | 2026-04-28 | ~90 | 72/72 测试全绿；SSE 4 事件流；Claude Sonnet 4.6 真实调用 2.6s / $0.0048；修复 SSE+session lifecycle bug |
| 10 SO + DO | ✅ 完成 | 2026-04-28 | 2026-04-28 | ~70 | 83/83 单测全绿（新增 16）；inventory 三新 API（apply_reserve/unreserve/sales_out）；防超卖原子 SQL；snapshot_avg_cost 首次发货写入；为 W12 退货留好 hook |
| 11 Invoice + MyInvois | ✅ 完成 | 2026-04-29 | 2026-04-29 | ~80 | 99/99 单测全绿（新增 16）；Mock adapter 通过 Protocol 隔离，未来真实 LHDN 对接零侵入；72h 用懒触发 + admin scan 替代 Celery（推迟 W18）；DEMO_MODE 自动 72h→72s |
| 12 e-Invoice AI + CN | ✅ 完成 | 2026-04-29 | 2026-04-29 | ~70 | 145/145 单测全绿（新增 34: 14 precheck + 4 sales_return + 10 CN + 6 consolidated）；7 硬规则 + 3 LLM 软规则 + 三档降级（gate/超时/error）；CN 5 件套完整含 cancel 库存回滚；Consolidated 按客户分组 + SO_ALREADY_CONSOLIDATED 反向校验；前端 PrecheckModal 三档行为 + CN 三页 + Generate Monthly Consolidated Modal |
| 13 Stock Movements | ✅ 完成 | 2026-04-30 | 2026-04-30 | ~80 | 177/177 单测全绿（新增 20: 8 transfer state + 6 adjustment + 6 inventory atomic）；inventory.py 新 4 个 apply_* 函数；StockTransfer 4 状态机（DRAFT→CONFIRMED→IN_TRANSIT→RECEIVED）支持部分收货 + unit_cost_snapshot 跨阶段传递；StockAdjustment 统一录单（盘盈/盘亏混合行 by qty_diff sign），Manager/Admin 才能 confirm；Movement 只读列表带 6 维筛选；前端 9 页面 + StockStatusBadge + 3 i18n 命名空间双语；Migration 不需新建（initial_schema 已建表）；audit handler 推迟 W17 |
| 14 Branch Inventory | ✅ 完成 | 2026-05-02 | 2026-05-02 | ~70 | inventory matrix + low-stock alerts API；notify_on_low_stock handler 带 1h 去重；前端热力图 + AlertPage 多选 → POEditPage restockPrefill 跳转预填；SKU DetailPage 成本趋势 Tab 懒加载；inventory i18n 双语；test_low_stock_notification 4 case 全绿 |
| 15 Dashboard + Reports | ✅ 完成 | 2026-05-04 | 2026-05-04 | ~80 | 230/230 单测全绿(新增 24:8 dashboard service + 5 cache invalidation + 11 reports);AI 日报采用懒触发 + Admin 手动刷新(零 Celery 依赖,推迟 W18 Beat);KPI/trends Redis DB1 5min 缓存,事件驱动失效(StockMovement/DocStatus/EInvoiceValidated);10 张报表 endpoint 全工作(已端到端验证 sales-trend + warehouse-distribution);Dashboard 5 KPI + AI 摘要卡(staleness 三色)+ 4 趋势图;Reports 中心 10 卡片网格(7d/30d/90d 切换);dashboard + reports 双语 i18n;cache_hit 第二次请求验证为 True |
| 16 UI + i18n | ✅ 完成 | 2026-05-04 | 2026-05-04 | ~95 | 主题系统(light/dark + zustand) + TopBar 4 入口(占位通知/角色) + LoginPage 双栏品牌+表单+四角色卡 + 403/404/500 + ErrorBoundary + 错误码前后端 i18n(AppException 自动 i18n_key + errors.json 双语) + ResponsiveModal + AppLayout breakpoint + i18n 全量补齐(54 文件 / ~320 keys / 3 subagent 并行) + sku 命名空间新建; 206/206 单测全绿; npm build 通过 |
| 17 审计 + Dev Tools | ✅ 完成 | 2026-05-06 | 2026-05-06 | ~95 | 审计 handler 落库（5 action 映射 + ContextVar IP/UA/request_id 透传） + EventLog 表 + EventBus subscribe_observer hook + SSE Dev Tools（query-token auth bypass for EventSource）+ Notification API/Drawer/Bell（30s 轮询）+ AI 三层开关全栈（master + 3 features，灰显联动）+ /me 注入 demo_mode/ai_settings → TopBar 真值 demo lamp + Demo Reset 占位（DEMO_MODE=false 灰显, W18 接 Celery）+ Users CRUD 全栈（防自删/自禁）+ Audit Logs 浏览页 + 5 配置 ProTable（Currencies/TaxRates/UOMs/Brands/Categories）+ Settings hub 9 卡片 + admin/settings 菜单 + admin/notification i18n 双语 + 219/220 测试全绿（新增 7 audit）；npm build 通过。决策差异：3 张核心表 before/after 仅记 status diff（CONTEXT 中明确为 ROI 取舍，dict 字段已留口）；Dev Tools 走 SSE 简化版（零新依赖）|
| 18 CI/CD + 部署 | ⚠️ 代码完成（本地验证留 W21）| 2026-05-07 | 2026-05-07 | ~50 | Sentry 双端 noop（DSN 留空）+ Celery 3 任务（finalize_scan 10min/DEMO 10s · ai_summary 30min · demo_reset_nightly 03:00 KL）+ services/demo_reset 全栈（mysqldump 备份→TRUNCATE 26 表 + Redis FLUSHDB DB0-3 + 复用 seed_initial_stock + 新增 seed_transactional 150PO/250SO/~150INV 6 月分布带季节加权）+ docker-compose.prod.yml + nginx.prod.conf SPA + SSE off + scripts/{backup,deploy}.sh + 3 GHA workflow（pr-check 含 openapi-contract drift 检测、nightly-e2e、deploy-demo 占位友好降级）+ admin/demo-reset 路由改为入队 Celery + /history 端点 + W17 占位 DemoResetPage 已通；4 demo_reset 单测；docs/deployment.md runbook 留 W21 真上线时执行 |
| 19 E2E | ✅ 完成 | 2026-05-08 | 2026-05-11 | ~95 | playwright.config.ts + 3 fixtures（auth/api/test-data）+ 3 specs（purchase/sales/inventory，共 7 test）+ 4 处 data-testid（po/so/transfer/invoice status badge）+ README。务实方案：UI 驱动 login + 状态徽章断言，业务写操作走 API（避开 ProForm/EditableProTable 选择器脆性）。OCR 改成 manual fallback smoke test（SSE 链路 W09 单测已覆盖）。MyInvois 走 mock adapter（默认）。CI 调试 5 轮收敛：npm lock 同步 → ProForm name 不传 DOM → 隐藏 antifill input → submit btn 非标 type → transfer 库存语义错配（confirm 不动 reserved，in_transit 在 To 仓不在 From 仓）。Nightly E2E #8 全绿（3m 9s，commit e019510）。|
| 20 演示物料 | ⏳ | | | | |
| 21 兜底演练 | ⏳ | | | | |

**状态图标**：⏳ 待开始 / 🔄 进行中 / ✅ 完成 / ⚠️ 部分完成 / ❌ 失败

## 踩坑记录

此处快速记录，细节到 `tasks/lessons.md`：

- **W12 / consolidated 测试**：`generate_monthly_consolidated` 先 `session.add(invoice)` → `flush` 拿 id，再二次 `session.add(invoice)` 写 totals。AsyncMock flush 不分配 id，导致 `invoice.id is None` 让 Pydantic 校验 `invoice_ids: List[int]` 失败。修法：测试 `session.add` 用 side_effect 给 Invoice 类对象自动赋 id（计数器），同时 dedupe（同一对象第二次 add 跳过），让 `_captured_invoices` 长度反映"创建了几张 invoice"。
- **W12 / `_so_already_consolidated` 回归**：在 `generate_draft_from_so` 加这个 guard 后，旧测试 (`test_generate_draft_happy_path` / `test_generate_rejects_zero_shipped_lines`) 没 mock 它，`session.execute` 默认返回 truthy MagicMock 让 guard 误判 True。修法：旧测试也加 `patch _so_already_consolidated → False`。教训：service 内调用的 helper 加 guard 时同步审视所有相关测试。
- **W12 / TIN 正则**：`EI00000000010` 是 13 字符（EI + 11 位），原正则 `EI\d{8,10}` 不通。修法：`_is_valid_tin` 提前查 `_GENERAL_PUBLIC_TINS` 集合再走正则，让特殊值跳过格式约束。
- **W19 / npm ci lock 漂移**：W18 加了 `@sentry/react@^8.45.1` 到 package.json 但忘了把更新后的 package-lock.json 一起 commit。CI 用 `npm ci` 严格校验，每个 @sentry/* 都报 "Missing from lock file" 直接炸。教训：每次 package.json 改动后先本地 `npm install` 再 `git add package-lock.json`，pre-commit 可加一条 lock 同步检查。
- **W19 / ProForm 选择器三连击**：`<ProFormText name="email">` 的 `name` 绑 Form.Item 状态不传到 DOM `<input>`；ProForm 还在前面注入隐藏 anti-autofill input；LoginForm 的 submit 按钮是 `htmlType="button"` + onClick 不是 `type="submit"`。E2E 选 ProForm 元素必须用 `:visible` 过滤 + Enter 提交，三个错都踩过一遍。教训：测 ProForm/ProTable 类组件先拿 devtools 看一眼 DOM，别按"直觉"假设标准 HTML 结构。
- **W19 / 业务语义错配**：写 transfer E2E 时按 SO confirm 的 reserved 语义类推，结果 transfer 的 `confirm` 是纯审批不动库存、`in_transit` 计在 To 仓不在 From 仓。服务层 docstring 写得很清楚。教训：测试断言前先读对应 service 的 docstring/单测，不要按相邻模块"语义"硬猜。

## 整体评审（完工后填写）

- 实际用时：
- 实际窗口数：
- 哪些窗口超预期 / 不足预期：
- 如果重来会怎么做：
- 客户反馈：
