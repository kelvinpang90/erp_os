# ERP OS — Project Bible

> 马来西亚本土中小企业 ERP 演示系统。本文件是 Claude Code 每次进入项目时自动加载的核心规格书。所有代码、决策、流程必须遵循本文档。变更需在此同步。

---

## Part 1. 用户工作原则（必读）

### 沟通
- 全部使用中文回复
- 需求模糊时先澄清，不脑补需求
- 除了注释，代码全部使用英文

### 思考
- 第一性原理：从原始需求出发，目标不清先讨论，动机和目标不明确时停下来沟通
- 路径不优主动建议：发现更短路径时及时指出
- 多想少动：谋定而后动

### 执行
- 非平凡任务进计划模式：3+ 步骤或涉及架构决策时，先规划
- 写代码前先描述方案：等批准再动手
- 超 3 个文件先拆分：拆成小任务，明确每个文件改什么
- 使用子智能体：复杂任务、研究探索、并行分析委托子智能体，保持主上下文整洁
- 测试驱动修复：出 bug 时先写能重现的测试再修复
- 自主 Bug 修复：收到 bug 直接修，不手把手教
- 不堆砌兼容性代码：除非主动要求
- 不临时修复：找到根本原因
- 追求优雅：非平凡修改问自己"有没有更优雅的方式"；简单修复不过度设计
- 完成前验证：问自己"资深工程师会批准这个吗？"
- 列出边缘情况：写完代码后主动思考哪里可能出错

### 任务管理
- 先计划：写到 `tasks/todo.md`，包含可选项
- 验证计划：获得确认后再实施
- 追踪进度：逐步标记完成项
- 记录结果：在 `tasks/todo.md` 添加评审部分
- 记录教训：纠正后更新 `tasks/lessons.md`

### 核心
**多想少动 · 知错即改 · 往正确的方向走**

---

## Part 2. 项目基本信息

| 项 | 值 |
|---|---|
| 项目代号 | `erp-os` |
| 目标客户 | 马来西亚本地中小 + 中型连锁企业（通用行业，5–500 人规模）|
| 主要卖点 | e-Invoice (LHDN MyInvois) 全流程 + AI 自动化 + 多仓 6 维库存 |
| 时间预算 | 1-2 周（Claude Code 开发）|
| 策略 | 核心三线深度闭环 + 周边模块页面展示（混合方案）|
| 交付形态 | docker-compose 一键起 + 云 Demo 站点（子域名）|
| 演示方式 | 当面演示 + 客户自试（每天凌晨 3am 马来时间 reset）|
| 用户邮箱 | pengwenkai@hotmail.com |
| 当前日期 | 2026-04-23 |

### 核心业务模块

**三条核心闭环（深做）：**
1. **e-Invoice / MyInvois** — 提交 / 验证 / UIN / 72h 反对期 / Consolidated / AI 预校验 / Credit Note
2. **采购流程** — 供应商 / PO / OCR 录入 / 收货 / 入库 / 结算（多币种）
3. **销售流程** — 客户 / SO / 出库 / e-Invoice 生成 / 回款 / 退货（Credit Note）

**支撑模块（核心做，参与业务闭环）：**
4. SKU 管理（SST 分类 / MSIC 码 / UOM / 加权平均成本 / 批号 / 效期 / 序列号字段）
5. Stock Movement（入库 / 出库 / 调拨 / 调整）
6. Branch Inventory（多仓 6 维库存 + 调拨）
7. Low Stock Alert（安全库存预警 + 批量补货建议）

**展示模块（页面精致，简化逻辑）：**
8. Supplier 管理
9. Customer 管理
10. 报表中心（固定 10 张图表 + AI 日报摘要卡）
11. 设置（语言 / 主题 / 货币汇率 / 税率 / 角色权限 / AI 功能开关）

---

## Part 3. 技术栈（版本锁定，不得擅自升级）

### Backend
- **Python** 3.12
- **FastAPI** 0.115
- **SQLAlchemy** 2.0（async）
- **Alembic** 1.13（数据库迁移）
- **Pydantic** v2（DTO 校验）
- **pydantic-settings**（env 配置）
- **Celery** 5.4 + Redis broker（异步任务 / 定时任务）
- **structlog**（结构化日志）
- **pytest** + **pytest-asyncio** + **httpx**（测试）
- **ruff** + **mypy**（lint / type check）
- **uvicorn**（ASGI server）

### Frontend
- **React** 18
- **TypeScript** 5.4
- **Vite** 5（bundler）
- **Ant Design Pro** 最新稳定版（UI 框架）
- **@ant-design/charts** + **Recharts**（图表）
- **react-i18next**（i18n，默认 en-US，可切 zh-CN）
- **react-router-dom** v6（路由）
- **axios**（HTTP client）
- **orval**（OpenAPI → TS client 自动生成）
- **zustand**（轻量全局状态）
- **dayjs**（日期处理）
- **vitest** + **@testing-library/react**（单测）
- **playwright**（E2E）
- **eslint** + **prettier**

### 基础设施
- **MySQL** 8.0（主数据库）
- **Redis** 7（缓存 / session / sequence / lock / rate limit / ai cache / Celery broker）
- **Docker** + **docker-compose**
- **Nginx**（反代 + 静态托管）
- **Cloudflare**（DNS + HTTPS + CDN）

### 外部服务
- **Anthropic Claude API**（OCR / e-Invoice 预校验 / Dashboard 日报）
- **Sentry**（错误追踪）
- **UptimeRobot**（uptime 监控）

---

## Part 4. 架构决策汇总

### 🔴 A 级：数据模型红线（违反即重构全库）

- **A1** 所有金额用 `Numeric(18, 4)` / Python `Decimal`，**禁用 float**
- **A2** 所有业务表预留 `organization_id INT NOT NULL`（现在 seed 一条 `org_id=1`，留多租户扩展）
- **A3** 所有业务实体软删除：加 `deleted_at TIMESTAMP NULL` + `is_active BOOLEAN DEFAULT TRUE`
- **A4** 业务文档号用 Redis `INCR` 原子生成，格式 `<PREFIX>-<YEAR>-<5位数字>`，例：`PO-2026-00042`
- **A5** 时间：UTC 存储（`TIMESTAMP`），业务日期独立字段（`business_date DATE`）。前端按浏览器时区显示
- **A6** 所有状态字段用 Python Enum + SQLAlchemy Enum 类型，显式定义状态机 transitions

### 🟡 B 级：架构脊柱

- **B1** 分层：Router（HTTP）/ Service（业务逻辑）/ Repository（数据访问）。Pydantic Schema 区分 `CreateDto` / `UpdateDto` / `ResponseDto`
- **B2** 事件驱动：In-process sync EventBus + after_commit 钩子处理异步 handler。三个核心事件：`StockMovementOccurred`、`DocumentStatusChanged`、`EInvoiceValidated`
- **B3** Transaction 边界在 Service 层；乐观锁用 `version` 字段；库存扣减用原子 SQL（`UPDATE ... WHERE available >= ?`）
- **B4** 前后端契约：orval 从 `/openapi.json` 自动生成 TS client，CI 校验同步
- **B5** 前端权限 / 菜单由后端下发：`/api/auth/me` 返回 `permissions: string[]` 和 `menu: MenuTree[]`

### 🟠 C 级：ERP 业务隐形默认值

- **C1** Order / Invoice / Payment **数据模型必须多对多**（partial shipment / partial invoicing / partial payment）
- **C2** 部分收货（GoodsReceipt）/ 部分发货（DeliveryOrder）独立成表，和 PO/SO 是 1:N 关系
- **C3** 金额字段命名明确：`unit_price_excl_tax` / `unit_price_incl_tax` / `total_excl_tax` / `tax_amount` / `total_incl_tax`
- **C4** 汇率快照：每张涉外币单据存 `currency_code` + `exchange_rate` + `base_currency_amount`，rate 创建时 snapshot
- **C5** SKU / StockMovement 表预留 `batch_no` / `expiry_date` / `serial_no` 字段（通用行业 NULL，为未来行业化留口）
- **C6** 库存变动必须有 StockMovement 记录；盘点差异走 StockAdjustment，原因 enum：`PHYSICAL_COUNT` / `DAMAGE` / `THEFT` / `CORRECTION`

### 🟢 D 级：AI 工程化

- **D1** 每个 AI 功能必须有 non-AI 降级路径（OCR 失败 → 手动录入；预校验失败 → 只跑硬规则；日报失败 → cached 摘要）。所有 AI 调用 3 秒 timeout
- **D2** Prompt 集中放 `backend/app/prompts/` 目录，YAML 格式，Git 版本化；LLM 返回用 Pydantic structured output（JSON mode）
- **D3** AI 调用记录 `ai_call_logs` 表：`user_id` / `endpoint` / `input_tokens` / `output_tokens` / `cost_usd` / `latency_ms`；IP 级 + 用户级 rate limit

### AI 三层开关（强制遵守）

```
Layer 1 (env): settings.AI_ENABLED = false → 全局硬关闭
Layer 2 (org master): organization.ai_master_enabled → 组织级总闸
Layer 3 (per-feature): organization.ai_features = { ocr_invoice, einvoice_precheck, dashboard_summary }
```

任何 AI endpoint 调用前必经 `AIFeatureGate.is_enabled(feature, org_id)` 检查。

### ⚪ E 级：工程实践（默认遵守）

- **E1** SQLAlchemy 查询禁止 N+1：列表 API 必须显式 `selectinload` / `joinedload`
- **E2** 外键必加索引；常用复合索引 `(organization_id, status, created_at)`
- **E7** 禁止 `Base.metadata.create_all()`，所有 schema 变更走 Alembic migration
- **E8** docker-compose 所有 service 必须有 healthcheck + `depends_on` 条件

---

## Part 5. 目录结构

### 项目根

```
erp-os/
├── .claude/                          # Claude Code 项目级配置（进 Git）
│   ├── skills/                       # 项目专用 skills
│   │   ├── erp-seed-generator/
│   │   ├── einvoice-validator/
│   │   └── new-resource/
│   ├── commands/                     # Slash commands
│   │   ├── new-resource.md
│   │   ├── add-migration.md
│   │   └── demo-reset.md
│   └── settings.local.json           # gitignored（个人设置）
├── backend/                          # FastAPI 后端
├── frontend/                         # React 前端
├── docker/                           # Dockerfile + nginx 配置
├── docs/                             # 项目文档
│   ├── ddl.sql                       # 数据库 DDL 草案
│   ├── architecture.md
│   └── api-contract.md
├── scripts/                          # 运维脚本
│   ├── backup.sh
│   └── deploy.sh
├── tasks/
│   ├── todo.md                       # 开发任务清单
│   └── lessons.md                    # 踩坑记录
├── docker-compose.yml                # 本地开发
├── docker-compose.prod.yml           # 生产 / demo 站点
├── .env.example
├── .gitignore
├── CLAUDE.md                         # 本文件
├── README.md
└── LICENSE
```

### Backend 目录结构

```
backend/
├── app/
│   ├── main.py                       # FastAPI app 入口 + lifespan
│   ├── core/                         # 核心基础设施
│   │   ├── config.py                 # pydantic-settings
│   │   ├── database.py               # async engine + session factory
│   │   ├── redis.py                  # Redis 连接（多 DB）
│   │   ├── security.py               # JWT / 密码 hash
│   │   ├── deps.py                   # FastAPI dependencies (get_current_user, require_role)
│   │   ├── exceptions.py             # 自定义异常层级
│   │   ├── logging.py                # structlog 配置
│   │   └── storage.py                # 文件存储抽象（LocalFS / S3 future）
│   ├── models/                       # SQLAlchemy ORM
│   │   ├── base.py                   # BaseModel + Mixins (SoftDelete, Timestamped, OrgScoped)
│   │   ├── user.py
│   │   ├── sku.py
│   │   ├── supplier.py
│   │   ├── purchase_order.py
│   │   ├── sales_order.py
│   │   ├── invoice.py
│   │   ├── credit_note.py
│   │   ├── stock.py
│   │   ├── stock_movement.py
│   │   ├── notification.py
│   │   ├── audit_log.py
│   │   └── ...
│   ├── schemas/                      # Pydantic DTOs
│   │   ├── common.py                 # Pagination, ErrorResponse
│   │   ├── sku.py                    # SKUCreate / SKUUpdate / SKUResponse
│   │   └── ...
│   ├── repositories/                 # 数据访问层
│   │   ├── base.py                   # BaseRepository[T] (CRUD generic)
│   │   ├── sku.py
│   │   └── ...
│   ├── services/                     # 业务逻辑层
│   │   ├── sequence.py               # DocumentSequenceService
│   │   ├── costing.py                # WeightedAverageCostService
│   │   ├── inventory.py              # Stock status transitions
│   │   ├── purchase.py               # PO lifecycle
│   │   ├── sales.py                  # SO lifecycle
│   │   ├── einvoice.py               # e-Invoice submission / validation
│   │   ├── credit_note.py
│   │   ├── dashboard.py
│   │   ├── ai_gate.py                # AIFeatureGate
│   │   └── ...
│   ├── routers/                      # FastAPI routes
│   │   ├── auth.py                   # /api/auth/*
│   │   ├── sku.py                    # /api/skus/*
│   │   ├── purchase_order.py
│   │   ├── sales_order.py
│   │   ├── invoice.py
│   │   ├── credit_note.py
│   │   ├── inventory.py
│   │   ├── supplier.py
│   │   ├── customer.py
│   │   ├── dashboard.py
│   │   ├── ai.py                     # /api/ai/ocr, /api/ai/einvoice-precheck
│   │   ├── settings.py
│   │   ├── admin.py                  # /api/admin/* (DevTools, reset)
│   │   └── files.py                  # /api/files/* (protected file access)
│   ├── events/                       # 事件驱动
│   │   ├── base.py                   # EventBus, DomainEvent
│   │   ├── types.py                  # StockMovementOccurred, DocumentStatusChanged, EInvoiceValidated
│   │   ├── registry.py               # 启动时注册订阅
│   │   └── handlers/
│   │       ├── audit.py
│   │       ├── notification.py
│   │       ├── cache.py
│   │       ├── inventory.py
│   │       └── ai.py
│   ├── tasks/                        # Celery tasks
│   │   ├── celery_app.py             # Celery 实例 + Beat schedule
│   │   ├── ocr.py                    # OCR 异步任务
│   │   ├── einvoice.py               # MyInvois 提交 / 72h 扫描
│   │   ├── dashboard.py              # AI 日报生成
│   │   └── demo_reset.py             # 凌晨 3am reset
│   ├── prompts/                      # LLM prompts (YAML)
│   │   ├── ocr_invoice.yaml
│   │   ├── einvoice_precheck.yaml
│   │   └── dashboard_summary.yaml
│   ├── enums.py                      # 所有业务枚举集中（POStatus, SOStatus, InvoiceStatus, ...）
│   └── constants.py                  # 业务常量（默认值等）
├── alembic/
│   ├── versions/
│   └── env.py
├── tests/
│   ├── conftest.py                   # fixtures (db_session, sku_factory, ...)
│   ├── factories/                    # factory-boy 测试数据工厂
│   ├── unit/                         # 业务逻辑单测
│   │   ├── test_costing.py
│   │   ├── test_sequence.py
│   │   ├── test_state_machine.py
│   │   └── test_einvoice_precheck.py
│   ├── integration/                  # API 测试
│   │   ├── test_auth.py
│   │   ├── test_purchase_flow.py
│   │   └── test_sales_flow.py
│   └── e2e/                          # Playwright E2E
│       ├── test_purchase_e2e.py
│       ├── test_sales_e2e.py
│       └── test_einvoice_e2e.py
├── scripts/
│   ├── seed_master_data.py           # SKU / Supplier / Customer seed
│   ├── seed_transactional.py         # 500 历史订单 seed
│   └── demo_reset.py                 # 手动触发 reset
├── alembic.ini
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
└── .env.example
```

### Frontend 目录结构

```
frontend/
├── public/
│   ├── logo.svg
│   └── favicon.ico
├── src/
│   ├── main.tsx                      # React 入口
│   ├── App.tsx                       # 根组件 + 路由
│   ├── api/                          # API 调用层
│   │   ├── generated/                # orval 生成的 TS client（不手改）
│   │   │   ├── sku.ts
│   │   │   ├── purchaseOrder.ts
│   │   │   └── ...
│   │   ├── client.ts                 # axios 实例 + interceptors
│   │   └── errorHandler.ts           # 错误码 → UI 展示策略
│   ├── components/                   # 通用组件
│   │   ├── ProtectedRoute.tsx
│   │   ├── RoleRoute.tsx
│   │   ├── Layout/
│   │   │   ├── AppLayout.tsx         # 主布局（侧栏 + 顶栏 + 内容）
│   │   │   ├── Sidebar.tsx           # 后端下发菜单渲染
│   │   │   └── TopBar.tsx            # 语言切换 / 主题切换 / 角色切换 / 通知铃铛
│   │   ├── ResourceListPage.tsx      # 通用 ProTable 封装
│   │   ├── ResourceDetailPage.tsx    # 通用 ProForm 封装
│   │   ├── SSEUploader.tsx           # 带 SSE 进度条的上传组件（OCR 用）
│   │   ├── CurrencyDisplay.tsx       # 多币种展示
│   │   ├── StockStatusBadge.tsx      # 6 维库存徽章
│   │   └── ConfirmModal.tsx
│   ├── pages/                        # 页面
│   │   ├── LoginPage.tsx
│   │   ├── 403Page.tsx
│   │   ├── Dashboard/
│   │   │   ├── index.tsx
│   │   │   ├── AISummaryCard.tsx     # AI 日报摘要
│   │   │   ├── KPICards.tsx
│   │   │   └── TrendCharts.tsx
│   │   ├── SKU/
│   │   │   ├── ListPage.tsx
│   │   │   ├── DetailPage.tsx
│   │   │   ├── EditPage.tsx
│   │   │   └── columns.tsx           # ProTable columns 配置
│   │   ├── Inventory/
│   │   │   ├── StockListPage.tsx
│   │   │   ├── MovementListPage.tsx
│   │   │   ├── BranchInventoryPage.tsx
│   │   │   ├── AlertPage.tsx
│   │   │   └── AdjustmentPage.tsx
│   │   ├── Purchase/
│   │   │   ├── POListPage.tsx
│   │   │   ├── PODetailPage.tsx
│   │   │   ├── POEditPage.tsx
│   │   │   ├── OCRUploadPage.tsx     # OCR 入口
│   │   │   ├── GoodsReceiptPage.tsx
│   │   │   └── SupplierListPage.tsx
│   │   ├── Sales/
│   │   │   ├── SOListPage.tsx
│   │   │   ├── SODetailPage.tsx
│   │   │   ├── SOEditPage.tsx
│   │   │   ├── DeliveryOrderPage.tsx
│   │   │   └── CustomerListPage.tsx
│   │   ├── EInvoice/
│   │   │   ├── InvoiceListPage.tsx
│   │   │   ├── InvoiceDetailPage.tsx
│   │   │   ├── PrecheckModal.tsx     # AI 预校验弹窗
│   │   │   ├── CreditNotePage.tsx
│   │   │   └── ConsolidatedPage.tsx
│   │   ├── Reports/
│   │   │   └── index.tsx
│   │   ├── Settings/
│   │   │   ├── GeneralPage.tsx
│   │   │   ├── CurrenciesPage.tsx
│   │   │   ├── TaxRatesPage.tsx
│   │   │   ├── AIFeaturesPage.tsx
│   │   │   └── UsersPage.tsx
│   │   └── Admin/
│   │       ├── DevToolsPage.tsx      # 可观测事件流
│   │       └── DemoResetPage.tsx
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── usePermission.ts
│   │   ├── useTheme.ts
│   │   ├── useSSE.ts                 # SSE 流式响应封装
│   │   └── useDebounce.ts
│   ├── stores/                       # zustand
│   │   ├── authStore.ts              # 用户 / permissions / menu
│   │   ├── themeStore.ts             # 浅色 / 深色
│   │   └── notificationStore.ts
│   ├── locales/                      # i18n
│   │   ├── en-US/
│   │   │   ├── common.json
│   │   │   ├── menu.json
│   │   │   ├── sku.json
│   │   │   ├── purchase.json
│   │   │   ├── sales.json
│   │   │   ├── einvoice.json
│   │   │   └── errors.json
│   │   └── zh-CN/
│   │       └── (mirror)
│   ├── utils/
│   │   ├── format.ts                 # 货币 / 日期格式化
│   │   ├── validators.ts
│   │   ├── permissions.ts            # errorCodes 自动生成（与后端同步）
│   │   └── errorCodes.ts             # 从后端 OpenAPI 同步的错误码枚举
│   ├── types/
│   │   └── global.d.ts
│   └── theme/
│       ├── light.ts                  # Ant Design Pro 主题配置
│       └── dark.ts
├── tests/
│   ├── unit/
│   └── e2e/
├── .env.example
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── eslint.config.js
├── playwright.config.ts
├── orval.config.ts
└── Dockerfile
```

---

## Part 6. 代码约定

### Backend

#### 命名
- 文件：`snake_case.py`
- 类：`PascalCase`
- 函数 / 变量：`snake_case`
- 常量：`UPPER_CASE`
- 枚举成员：`UPPER_CASE`
- 私有方法：`_leading_underscore`
- Pydantic Schema 后缀：`Create` / `Update` / `Response` / `Detail`

#### 分层铁律
| 层 | 允许做 | 禁止做 |
|---|---|---|
| **Router** | 调 Service、返回 Response Schema | 写 ORM query、写业务逻辑、持有 DB session |
| **Service** | 业务逻辑、发布事件、调用 Repository、开启事务 | 直接返回 ORM 对象给 Router（必须包 Pydantic） |
| **Repository** | ORM query、简单聚合 | 写业务判断、发布事件 |
| **Event Handler** | 订阅事件、写 DB、清缓存、enqueue Celery | 开启新事务（用传入的 session） |

#### 异常处理
- 所有异常继承自 `app.core.exceptions.AppException`
- Router **禁止** `raise HTTPException(...)`，改用 `raise BusinessRuleError(...)`
- 全局 exception handler 统一转 JSON 响应格式

#### 异步
- I/O 操作必须 `async`（DB、Redis、HTTP、LLM API）
- 纯计算可以 sync（costing、格式化）
- 禁止在 async 里调 blocking call（会阻塞整个 event loop）

#### 函数签名模板

```python
# Service 层标准签名
async def <action>_<entity>(
    session: AsyncSession,
    *args,
    user: User,
    **kwargs,
) -> <Entity>Response:
    """<One-line description>.
    
    Args:
        ...
    Raises:
        BusinessRuleError: ...
    Returns:
        ...
    """
```

#### 金额处理
- **禁用 float**，一律 `Decimal`
- 计算用 `decimal.getcontext().prec = 28`
- 输入输出用 Pydantic `Decimal` 类型，JSON 序列化为字符串（不丢精度）

### Frontend

#### 命名
- 文件：组件 `PascalCase.tsx`，工具 `camelCase.ts`
- 组件：`PascalCase`
- Hook：`useXxx`
- 样式类：优先 Ant Design token，必要时 CSS Modules
- i18n key：`<namespace>.<key>`，例 `sku.form.price`

#### 组件约束
- 所有组件必须有明确 Props TypeScript interface
- 禁止 `any` 类型（必要时 `unknown` + type guard）
- 页面组件不写表单 / 表格 JSX，调用 `ResourceListPage` / `ResourceDetailPage`
- ProTable columns 必须抽到 `columns.tsx` 文件

#### 状态管理
- 服务端数据：orval 生成的 hook + TanStack Query（或 Ant Design Pro 的 `useRequest`）
- 全局客户端状态（auth / theme）：zustand
- 页面局部状态：`useState`
- **禁用 Redux**（过度设计）

#### 路由
- 所有受保护路由套 `<ProtectedRoute>`
- 角色限制路由套 `<RoleRoute roles={...}>`
- 菜单不硬编码，读 `authStore.menu`
- 按钮权限用 `usePermission()` hook

#### 错误处理
- axios interceptor 统一拦截，按错误码分发 toast / modal / inline
- 错误消息 i18n key：`errors.<ERROR_CODE>`
- 错误码枚举从后端自动生成到 `utils/errorCodes.ts`

#### 性能
- 列表默认分页（20 / page），提供 50 / 100 选项
- 大列表用 Ant Design Pro 的虚拟滚动
- 图表懒加载
- 图片 lazy loading

---

## Part 7. 业务规则速查

### 文档号生成
- 格式：`<PREFIX>-<YEAR>-<5 位>`，例：`PO-2026-00042`
- 前缀：PO / SO / INV / CN / GR / DO / TR / ADJ / QT
- 用 Redis `INCR` 原子自增，key：`seq:{org_id}:{doc_type}:{year}`
- 同步写 `document_sequences` 表（断电恢复 + 审计）

### PO 状态机

```
DRAFT ──confirm──▶ CONFIRMED ──receive──▶ PARTIAL_RECEIVED ──receive──▶ FULLY_RECEIVED
  │                    │
  └──cancel──▶ CANCELLED      CONFIRMED ──cancel──▶ CANCELLED (仅未收货前可取消，Manager 角色)
```

副作用：
- `DRAFT → CONFIRMED`：库存 `Incoming` +
- `CONFIRMED → PARTIAL/FULLY_RECEIVED`：`Incoming` -，`On-hand` +，生成 GoodsReceipt
- `CONFIRMED → CANCELLED`：`Incoming` -

### SO 状态机

```
DRAFT ──confirm──▶ CONFIRMED ──ship──▶ PARTIAL_SHIPPED ──ship──▶ FULLY_SHIPPED ──invoice──▶ INVOICED ──payment──▶ PAID
                       │                                                                             
                       └──invoice──▶ INVOICED（允许先开票后发货）
```

副作用：
- `DRAFT → CONFIRMED`：`Reserved` +，`Available` -
- `CONFIRMED/SHIPPED → SHIPPED`：`Reserved` -，`On-hand` -
- `SHIPPED → INVOICED`：生成 e-Invoice 草稿

### e-Invoice 状态机

```
DRAFT → SUBMITTED → VALIDATED ───(72h window)───▶ FINAL
              │          │
              │          └── buyer reject ──▶ REJECTED
              │
              └── LHDN reject ──▶ REJECTED
```

关键规则：
- 提交前 **必走 AI 预校验**（除非 AI 开关关闭）
- Validated 后 72h 内 buyer 可 Reject（需原因必填 + 附件可选）
- **Demo Mode**：`settings.DEMO_MODE = true` 时 72h → 72s（演示友好）
- Celery Beat 每 10 分钟扫 `VALIDATED` 且超 72h 的发票 → 标 FINAL
- B2C 场景月底 7 天内生成 Consolidated e-Invoice

### 库存 6 维

```python
class Stock:
    on_hand: Decimal          # 实物在库
    reserved: Decimal         # 已下单锁定
    quality_hold: Decimal     # 质检 / 损坏待处理
    available: Decimal        # 计算字段 = on_hand - reserved - quality_hold
    incoming: Decimal         # 已下 PO 未到货（汇总 active POs）
    in_transit: Decimal       # 调拨在途（汇总 active transfers）
```

### 加权平均成本

```python
# 入库（采购 / 盘盈）
new_avg_cost = (current_qty * current_avg_cost + incoming_qty * incoming_unit_cost) / (current_qty + incoming_qty)

# 出库（销售 / 盘亏 / 供应商退货）
avg_cost 不变
COGS = outbound_qty * current_avg_cost

# 客户退货入库
按原销售时的 snapshot_avg_cost 回填（每条 SO line 存 snapshot）

# 调拨
From 仓：avg_cost 不变
To 仓：按 From 仓当时 avg_cost 作为 incoming_unit_cost 重算
```

### SST（马来销售服务税）

- 三档：10% Sales Tax（大部分商品）/ 6% Service Tax（服务）/ 0% Exempt（药品 / 基本食品）
- 所有商品录入时必填 `sst_rate`
- 金额字段含税 / 不含税分开存：`subtotal_excl_tax` + `tax_amount` + `total_incl_tax`

### 多币种

- 本币固定 `MYR`
- 外币交易存 `currency_code` + `exchange_rate`（创建时 snapshot）+ `base_currency_amount`
- 汇率管理页（Admin）：手动维护 USD / SGD / CNY → MYR
- 报表默认本币，可切显示货币

### 4 个角色 + 权限

| 角色 | 主要功能 | 看不到 |
|---|---|---|
| **Admin** | 全权限、配置、用户管理 | — |
| **Manager** | 审批、报表、跨模块看 | — |
| **Sales** | 销售单、客户、发货、e-Invoice | 成本价、供应商清单 |
| **Purchaser** | 采购单、供应商、收货、OCR | 销售利润、客户清单 |

权限粒度：**模块级 + 关键动作级**（不做字段级，但用 role 过滤显示）。

---

## Part 8. 安全规则

### 认证
- JWT：access token 15min + refresh token 7d（一次性，rotate）
- 密码：bcrypt，cost factor 12
- Refresh token 存 Redis（DB 2），支持 revoke
- 登录失败 5 次锁 5 分钟

### 授权
- 所有 API endpoint 必须有 `Depends(get_current_user)`（除 `/api/auth/*` 和 `/api/health`）
- 角色受限 endpoint 套 `Depends(require_role("admin"))`
- Service 层**再次校验** `organization_id`（防 IDOR）

### CORS
- 白名单域名（env 配置），禁止 `allow_origins=["*"]`

### Rate Limit（slowapi）
- 全局：100 req/min per IP
- 登录：10 req/min per IP
- AI endpoint：5 req/min per user
- OCR：20 次/day per user（demo 配额）

### 输入
- 所有 query / body 必过 Pydantic
- SQL 只用 ORM 或参数化，禁止字符串拼接
- 文件上传：MIME 白名单 + 大小限制（见 Part 9）

### Secrets
- 所有 secret 走 env 变量，禁止硬编码
- `.env.*` 严格 gitignore
- 预 commit hook 扫描 `git-secrets`

### 审计
- 三张核心表审计：`orders`（PO/SO）、`invoices`、`credit_notes`
- 审计字段：`actor_user_id`、`action`、`before`（JSON）、`after`（JSON）、`occurred_at`、`ip`、`user_agent`

---

## Part 9. 性能规则

### 数据库
- 外键必加索引
- 常用复合索引：`(organization_id, status, created_at)`、`(organization_id, deleted_at)`
- 大表（stock_movements / audit_logs）按 `created_at` 月度分区（生产化再做）
- 查询必显式 `selectinload` / `joinedload`，禁止懒加载导致 N+1
- 列表 API 默认 `LIMIT 20`，最大 100

### 缓存（Redis DB 1）
- Dashboard 聚合：TTL 5 分钟 + `StockMovementOccurred` 事件主动失效
- SKU 列表热数据：TTL 30 分钟
- 响应数据带 `staleness_seconds` 字段告知前端数据新旧度

### 并发
- 库存扣减：`UPDATE stocks SET available = available - ? WHERE ... AND available >= ?`，行数 0 抛 `InsufficientStock`
- 成本重算：`SELECT ... FOR UPDATE` 行锁
- 文档号：Redis `INCR` 原子
- 分布式锁（特殊场景）：`redis.lock(timeout=5, blocking_timeout=2)`

### 文件上传
- 大小限制：OCR invoice 10MB / e-Invoice PDF 5MB / avatar 2MB / Excel import 20MB
- MIME 白名单
- OCR 图片上传自动压缩到 ≤2MB（节省 LLM token）
- 文件名 UUID，防遍历 + 冲突

---

## Part 10. AI 功能规则

### 启用的 3 个 AI 功能
1. **Purchase Order OCR 录入**（SSE 流式进度）
2. **e-Invoice 智能预校验**（同步，< 3s timeout，失败降级为硬规则）
3. **Dashboard AI 日报摘要**（Celery 异步生成，Redis 缓存）

### 三层开关（必走）
```python
if not settings.AI_ENABLED: return disabled
if not org.ai_master_enabled: return disabled
if not org.ai_features[feature]: return disabled
```

### Prompt 管理
- 所有 prompt 在 `backend/app/prompts/*.yaml`
- 结构：`version` / `model` / `temperature` / `system` / `user_template` / `response_schema`
- LLM 返回必须结构化（Pydantic schema）+ JSON mode

### 降级策略
| AI 功能 | 降级方案 |
|---|---|
| OCR 失败 | 弹"请手动输入"，跳到表单空白状态 |
| 预校验失败 | 只跑硬规则（TIN 正则、金额计算），跳过软校验 |
| 日报失败 | 显示上次缓存摘要 + `staleness` 角标 |

### 成本控制
- `ai_call_logs` 表记录每次调用
- IP 级 rate limit（slowapi）
- 用户级日配额（Redis 计数）
- 超配额返回友好提示 + 转化 CTA

### 演示增强（Demo Mode）
- `settings.DEMO_MODE = true`：e-Invoice 72h → 72s，方便演示 FINAL 状态跳转
- Admin 页面显示 Demo Mode 状态灯

---

## Part 11. 测试规则

### 分层
| 层 | 目标覆盖 | 工具 |
|---|---|---|
| Unit | 核心业务逻辑 ≥ 80%（costing / sequence / state_machine / einvoice_precheck / event handler） | pytest + pytest-asyncio |
| Integration | 关键 API 路径 100% | pytest + httpx AsyncClient |
| E2E | 3 条黄金路径 100% 通过 | Playwright |
| Frontend | 核心 hook + util 30% | Vitest + React Testing Library |

### E2E 黄金路径
1. **采购闭环**：OCR 上传 → PO 确认 → 收货 → 库存增加
2. **销售闭环**：SO 创建 → 确认（Reserved +）→ 发货（On-hand -）→ e-Invoice 预校验 → 提交 → UIN 回填
3. **库存闭环**：多仓 6 维展示 → 调拨单 → 确认 → From In-transit / To Incoming → 收货 → 库存更新

### 运行频率
- PR check：每次 push 跑 unit + integration
- E2E：每晚跑一次 + 合并 main 前手动触发
- 覆盖率报告：可视化 HTML（pytest-cov）

### Fixture 约定
- 每个 test 一个独立 transaction，结束回滚
- 用 factory-boy 造测试数据，禁止在测试文件里手拼 dict
- mock 外部服务（LLM API、MyInvois）

---

## Part 12. 部署 / DevOps 规则

### 环境
- `.env.development`（本地）
- `.env.test`（CI）
- `.env.production`（生产 / demo 站点）
- `.env.example` 进 Git，其他 gitignore

### 部署拓扑
```
Cloudflare（DNS + HTTPS + CDN + DDoS）
        ↓
    VPS（马来西亚本地，RM 20-50/月）
        ↓
    docker-compose.prod.yml:
    ├── nginx（反代 + 静态）
    ├── backend（FastAPI, 2 workers）
    ├── celery-worker-default
    ├── celery-worker-ai（AI 任务独立 queue）
    ├── celery-beat
    ├── mysql（data volume）
    └── redis（data volume）
```

### CI/CD（GitHub Actions）
- `.github/workflows/pr-check.yml`：PR 时跑 lint + unit test + build check
- `.github/workflows/nightly-e2e.yml`：每晚跑 E2E
- `.github/workflows/deploy-demo.yml`：push main → build image → SSH VPS → restart containers

### 备份
- Daily cron：`mysqldump` → gzip → 保留 7 天
- Demo Reset 前额外备份（出错可恢复）

### 监控
- Sentry（错误追踪，前后端都接）
- UptimeRobot（uptime，5min 检查）
- docker logs（开发期足够）
- structlog JSON 格式 + `request_id` 贯穿前后端

### Demo Reset（凌晨 3am 马来时间）
- 保留：users、roles、orgs、warehouses、SKUs、suppliers、customers、settings
- 重置：orders、invoices、CN、stock movements、stock 状态、notifications、audit logs、临时 uploads
- 失败：回滚 + 告警 + 保留旧数据
- 手动触发按钮：`/admin/demo-reset`（Admin 独有）

---

## Part 13. 演示账号

固定 4 个演示账号（Demo Reset 保留）：

| 用户名 | 密码 | 角色 | 默认首页 |
|---|---|---|---|
| `admin@demo.my` | `Admin@123` | Admin | Dashboard |
| `manager@demo.my` | `Manager@123` | Manager | Dashboard |
| `sales@demo.my` | `Sales@123` | Sales | Sales Orders |
| `purchaser@demo.my` | `Purchaser@123` | Purchaser | Purchase Orders |

登录页提供"一键登录"卡片切换（演示加速）。

**默认组织**：`Demo Malaysia Sdn Bhd`（`organization_id = 1`）

**默认仓库**：3 个
- `Main Warehouse - Kuala Lumpur`
- `Branch - Penang`
- `Branch - Johor Bahru`

---

## Part 14. 开发工作流 & Skills 使用

### Skills 索引（项目级，在 `.claude/skills/`）

| Skill | 用途 | 何时触发 |
|---|---|---|
| `erp-seed-generator` | 生成马来本地化真实 seed 数据 | 需要造 SKU / supplier / customer / 历史订单 |
| `einvoice-validator` | e-Invoice 字段校验规则库 | 实现预校验逻辑或审查 e-Invoice 代码 |
| `new-resource` | CRUD 五件套模板 | 新增资源模块（model + schema + repo + service + router） |

### Slash Commands（`.claude/commands/`）

| 命令 | 用途 |
|---|---|
| `/new-resource <Name>` | 一键生成标准 CRUD 五件套 + 前端 ProTable 页 |
| `/add-migration <desc>` | 创建 Alembic migration 骨架 |
| `/demo-reset` | 手动触发演示数据 reset |

### 通用 Skills（系统级，已有）
- `docx` / `pdf` / `pptx` / `xlsx`：生成演示物料、报表、模板
- `skill-creator`：创建新的项目专用 skill

### 推荐开发节奏（Claude Max 配额友好）
- **每个 5h 窗口专注一个完整模块**（见 `tasks/todo.md`）
- 一个 session 一个模块主题，做完 `/clear` 换 session
- 批量模板生成用 `/new-resource`
- 脏活（seed / test / i18n / UI 调优）委托 subagent
- 小改用 Edit + 行号，大改用 Plan Mode 先审再写

---

## Part 15. Claude Code 数据库操作规范

### 🚫 三大铁律

| 操作类型 | 必须用 | 禁止 |
|---|---|---|
| **查询**（SELECT / COUNT / DESCRIBE） | MCP server 的 mysql 工具 / Bash `docker exec mysql` | — |
| **DDL**（CREATE / ALTER / DROP TABLE / CREATE INDEX） | Alembic migration（`/add-migration` command） | 直接 `ALTER TABLE`、`Base.metadata.create_all()` |
| **数据改动**（INSERT / UPDATE / DELETE） | `backend/scripts/*.py`（进 Git，可 review、可重跑） | Claude 直接对生产库跑 DML |

### 权限矩阵

| 环境 | Claude 能做 | 禁止 |
|---|---|---|
| 本地 Dev | 只读 MCP SELECT / Bash SELECT / 跑 Alembic / 跑 scripts/*.py | 直接 `DROP TABLE`、跳过 migration |
| Demo VPS | 只读 MCP SELECT（claude_ro 账号）/ Git PR → CI 部署 | SSH 到服务器直接改库 |
| 真生产 | **完全回避** | Claude 永远不触碰生产库 |

### MCP MySQL 初始化（Window 02 后执行一次）

```bash
# 1. 建只读账号（密码换成强随机）
PWD=$(openssl rand -hex 16)
docker compose exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<EOF
CREATE USER IF NOT EXISTS 'claude_ro'@'%' IDENTIFIED BY '$PWD';
GRANT SELECT ON erp_os.* TO 'claude_ro'@'%';
FLUSH PRIVILEGES;
EOF
echo "CLAUDE_MYSQL_PASSWORD=$PWD" >> .env.claude

# 2. 生成 .claude/mcp.json
mkdir -p .claude
cat > .claude/mcp.json <<EOF
{
  "mcpServers": {
    "erp-mysql": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "--network", "erp_os_default",
               "-e", "MYSQL_HOST=mysql",
               "-e", "MYSQL_USER=claude_ro",
               "-e", "MYSQL_PASSWORD=$PWD",
               "-e", "MYSQL_DATABASE=erp_os",
               "mcp/mysql"]
    }
  }
}
EOF

# 3. gitignore 敏感文件
{ echo ".env.claude"; echo ".claude/mcp.json"; echo ".claude/settings.local.json"; } >> .gitignore

# 4. 重启 Claude Code（完全退出再打开），新 session 里应该能看到 mcp__erp_mysql__* 工具
```

### 日常使用速查

| 场景 | 用什么 |
|---|---|
| "表里几条数据" / "库存对不对" | MCP 工具 |
| "加一列 `safety_stock`" | `/add-migration` |
| "批量 seed 200 SKU" | Python 脚本 + `erp-seed-generator` skill |
| "紧急改一条记录" | Adminer（浏览器）+ 审计日志 |
| "dump 某张表做备份" | `docker compose exec mysql mysqldump ...` |

### Adminer（可选 GUI）

在 `docker-compose.yml` 加 dev profile：
```yaml
adminer:
  image: adminer:latest
  ports: ["8080:8080"]
  profiles: [dev]
  depends_on: [mysql]
```
启动：`docker compose --profile dev up -d`，浏览器打开 `http://localhost:8080`。

---

## Part 16. 核心约束清单（一页总览）

### 🚫 永不允许
- float 存金额
- `Base.metadata.create_all()` 代替 migration
- Router 里写业务逻辑
- 前端硬编码菜单
- LLM 调用没有降级
- 硬编码 secret
- SQL 字符串拼接
- `raise HTTPException(...)`（用自定义异常）
- `allow_origins=["*"]`
- 跨层直接访问（Router → Repository 绕过 Service）
- Claude 直接操作生产数据库

### ✅ 必须始终做
- 金额 `Decimal(18, 4)`
- 表预留 `organization_id`
- 软删除 `deleted_at`
- 状态用 Enum + 状态机校验
- 库存变动经 `StockMovement` 记录
- 事件驱动发布（3 个核心事件）
- Pydantic DTO 输入输出
- 结构化日志 + `request_id`
- i18n key（前后端所有文案）
- 权限检查（router 层）+ 组织校验（service 层）
- AI 三层开关检查
- 测试：核心业务 ≥ 80%
- 所有 commit 过 pre-commit hook

---

## 附录 A：关键外部参考

- LHDN e-Invoice Specific Guideline：待补链接
- MyInvois API Doc：待补链接
- MSIC 2008 Classification：待补链接
- MFRS（Malaysia Financial Reporting Standards）：加权平均 / FIFO 允许，LIFO 禁止

## 附录 B：变更日志

| 日期 | 变更 | 作者 |
|---|---|---|
| 2026-04-23 | 初始版本（21 轮架构讨论后定稿）| Kelvin + Claude |
| 2026-04-23 | 新增 Part 15：Claude Code 数据库操作规范 + MCP 初始化脚本 | Kelvin + Claude |
