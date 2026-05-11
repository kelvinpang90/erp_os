# Setlist — 30 分钟深度演示（IT + 财务联席）

> 受众：IT 主管 + 财务主管 + 老板。比 15min 版多技术细节 + 合规深挖 + AI 成本透明。
> 桌面贴墙第二屏。

---

## 演示前准备（同 15min 版 + 加项）

✅ 15min 版全部 ✅
✅ 准备 3 张 OCR 样本：`INV-TanChongTrading.pdf` / `INV-MultiCurrency-USD.pdf` / `INV-EcoFreshFoods.pdf`
✅ 准备一张错误样本（手工编辑过 TIN 字段，模拟 OCR 误识别）
✅ 后台开 Sentry / Grafana 监控页（如客户问可秒切）
✅ 架构图 PPTX 单独打开（`erp-os-30min-en.pptx` / `-zh.pptx`）

---

## ⏱️ 0:00 — 2:00 开场 + 痛点 + 自我介绍

📍 PPTX slide 1-3
🎤 关键句：
- "30 家走访 + e-Invoice 合规深度调研"
- "今天 30 分钟分 4 part：业务流程 / 技术架构 / 合规细节 / 商务"

---

## ⏱️ 2:00 — 9:00 业务三大闭环（节奏同 15min 版的 1:00-10:00 但每段稍展开）

### 2:00 — 4:00 采购闭环（OCR + GR + 库存追溯）
👉 同 15min setlist 1:00-4:30 节奏
**加点**：
- 给 USD 多币种发票演示一次（强调汇率 snapshot）
- 切到 Audit Logs → 展示这张 PO 的完整修改历史

### 4:00 — 7:00 销售 + e-Invoice
👉 同 15min setlist 5:00-9:30
**加点**：
- 防超卖演示后切到后端日志 → 展示 SQL `WHERE on_hand - reserved >= ?` 原子语句
- Precheck 演示后展开 PrecheckModal 详情 → 显示哪几条是硬规则、哪几条是 AI 软规则

### 7:00 — 9:00 库存深度
👉 同 15min setlist 10:00-12:30 + Stock Adjustment（盘点差异）
**加点**：
- Stock Adjustment 演示一次：盘亏 RM 200 → 选原因 DAMAGE → audit log 记录
- 切到 inventory matrix → 展示 hover 6 维 + 颜色阈值可配置

---

## ⏱️ 9:00 — 14:00 ⭐ 技术架构（IT 关心）

📍 切到 PPTX 架构图 slide

### 9:00 — 10:00 整体架构图
🎤 念点：
- "FastAPI 后端 / async / SQLAlchemy 2.0"
- "MySQL 8.0 主存 / Redis 7 多 DB（缓存 / session / sequence / lock / AI cache）"
- "Celery 异步队列 / 独立 AI worker"
- "React 18 + TS + Ant Design Pro / 中英双语"
- "Docker compose 一键起 / 也可 K8s"

### 10:00 — 11:00 数据模型亮点
🎤 念点：
- "金额全 Decimal(18,4) / 不用 float"
- "所有业务表预留 organization_id / 多租户预留口"
- "软删除 / 乐观锁 / 加权平均成本审计字段"
- "事件驱动：StockMovementOccurred / DocumentStatusChanged / EInvoiceValidated"

### 11:00 — 12:00 安全 & 权限
🎤 念点：
- "JWT access 15min + refresh 7d / 可 revoke"
- "bcrypt cost 12 / 登录 5 次锁 5 分钟"
- "RBAC 4 角色 / Service 层组织二次校验防 IDOR"
- "审计 3 核心表 before/after JSON"
- "Rate limit / SQL 全 ORM 参数化 / Sentry 错误追踪"

🖱️ 切回前端 → Settings → Users 页演示用户管理

### 12:00 — 13:00 部署 & 运维
🎤 念点：
- "docker-compose.prod.yml / nginx 反代 / SSE 不 buffer"
- "Cloudflare DNS+HTTPS+CDN / VPS 马来本地 RM 50/月起"
- "GitHub Actions: PR 跑 lint+test / 合并 main 自动部署"
- "Daily mysqldump 备份 7 天 / Demo Reset 凌晨 3am 自动跑"
- "Sentry + UptimeRobot / structlog JSON request_id 贯穿前后端"

🖱️ 切到终端 → 演示 `git log --oneline -20` 显示真实开发提交

### 13:00 — 14:00 集成 & 扩展
🎤 念点：
- "OpenAPI auto-generated / orval 出 TS client / 前后端契约 CI 校验"
- "对外 REST API / webhook 框架预留"
- "未来集成方向：Shopee/Lazada / 银行流水 / Xero/QuickBooks 同步"

---

## ⏱️ 14:00 — 19:00 ⭐ e-Invoice 合规深挖（财务关心）

📍 切回前端 + 偶尔跳 PPTX 合规 slide

### 14:00 — 15:30 LHDN 完整流程
🎤 念点：
- "DRAFT → SUBMITTED → VALIDATED → FINAL，一条状态机"
- "VALIDATED 后 72h 反对期 / 买家收到不对可拒"
- "我们用 lazy trigger + admin scan 双保险，绝不漏"
- "DEMO_MODE 把 72h 压到 72s 演示"

🖱️ 找一张 VALIDATED 的发票 → 看倒计时

### 15:30 — 16:30 Consolidated Invoice
🎤 念点：
- "B2C 月底汇总：零售门店几千张小票一张总发票"
- "按客户 grouping 算 / 自动求和 / 反向校验避免双开"
- "演示一次 monthly consolidated"

🖱️ Admin → "Generate Monthly Consolidated"

### 16:30 — 17:30 Credit Note 红冲
🎤 念点：
- "退货：CN 关联原 invoice / 库存按 snapshot 回填"
- "MyInvois 红冲 / 会计自动冲销 / 完整审计"

🖱️ 演示一次 CN 创建（同 15min 版）

### 17:30 — 18:30 SST 三档处理
📍 SKU 页 → 找一个 0% Exempt + 一个 10% + 一个 6% Service Tax
🎤 念点：
- "SST 三档：10% Sales / 6% Service / 0% Exempt"
- "MSIC 码自动映射 / 含税不含税字段分开存"
- "Eco Fresh Foods 这种混合发票，行级 SST 独立算"

### 18:30 — 19:00 e-Invoice 边缘 case
🎤 念点：
- "买家 TIN 不知道？General Public TIN 兜底（EI00000000010）"
- "外币发票：snapshot exchange_rate 落库，对账永远一致"
- "MyInvois adapter 用 Protocol 抽象 / mock + sandbox + production 三模式 / 真实对接零侵入"

---

## ⏱️ 19:00 — 22:00 ⭐ AI 透明（财务最在意成本）

### 19:00 — 20:00 三层开关
📍 Settings → AI Features
🎤 念点：
- "Layer 1: 全局 env 开关（部署时定）"
- "Layer 2: 组织级总闸（老板可关）"
- "Layer 3: per-feature（OCR / Precheck / Summary 各自独立）"

🖱️ 切换 master 开关 → 所有 AI 按钮立刻灰显 → 切回

### 20:00 — 21:00 降级策略
🎤 念点：
- "OCR 挂 → 弹手工录入 / 不影响业务"
- "Precheck 挂 → 只跑硬规则 / 提交照样过"
- "Daily Summary 挂 → 显示上次缓存 + staleness 角标"
- "3 秒 timeout / 不阻塞用户"

🖱️ 演示一次故意关 AI master → OCR 上传按钮灰显

### 21:00 — 22:00 成本控制
📍 Reports → AI Cost / AI Calls Charts
🎤 念点：
- "ai_call_logs 每次记录：endpoint / tokens / cost USD / latency"
- "IP 级 rate limit + 用户级日配额"
- "OCR 一张约 $0.005 / Precheck 约 $0.002 / Summary 一天 $0.05"
- "5 人公司一年 AI 成本 < $200 USD"

🖱️ 滑过 AI Cost 图表 → "都看得见"

---

## ⏱️ 22:00 — 25:00 多角色 + 设置 + Admin 工具

### 22:00 — 23:00 角色切换 + i18n + 主题
👉 同 15min setlist 13:00-14:00

### 23:00 — 24:00 设置页全览
📍 Settings hub
🖱️ 点过：Currencies / Tax Rates / UOMs / Brands / Categories / AI Features / Users
🎤 "所有主数据可配置 / 不用改代码 / 不同公司不同税率都能跑"

### 24:00 — 25:00 Admin Dev Tools
📍 Admin → Dev Tools 事件流
🖱️ 演示一下 SO confirm → 实时看到事件 + handler 链路
🎤 "可观测性 / 客户信任的关键 / 出 bug 我们能定位到 event 级"

🖱️ Admin → Demo Reset 按钮 / Audit Logs 浏览页 → "都给客户敞开"

---

## ⏱️ 25:00 — 27:00 ROI 详细算账

📍 切到 PPTX ROI slide

### 算账 1：OCR 节省
> 5 人公司 × 每天 30 张 × 8min = 1000h/年 = RM 60K
> OCR 后省 95% = RM 57K/年

### 算账 2：避免 LHDN 罚款
> 每张错单罚款 RM 200-500
> 一年 50 张错 = RM 10-25K
> Precheck 把错降到 1-2 张 = 节省 RM 9-23K

### 算账 3：库存账实
> 平均库存 RM 500K × 账实差 5% = 暴露 RM 25K 风险
> 6 维库存 + 调拨追溯把差降到 < 1% = 减少 RM 20K 损失

### 算账 4：管理时间
> 老板每周看报表 + 对账 = 5h × 50 周 × RM 200/h = RM 50K
> Dashboard + AI 日报 = 30min/周 = RM 5K
> 节省 RM 45K

### 总计
> 一年硬节约 RM 130K+
> 软节约（决策快、客户体验、合规安全）无价

---

## ⏱️ 27:00 — 29:00 商务 + 实施

### 价格方案
🎤 念点（细节看 Proposal）：
- "5-20 人公司：起步价 / 包基础培训"
- "20-100 人：标准版 / 含 OCR 配额 / 优先响应"
- "100+ 公司：企业版 / 自部署可选 / 专属客户经理"
- "AI 调用按实付 / 透明账单"

### 实施时间表
🎤 念点：
- "Week 1: Kick-off + 主数据迁移"
- "Week 2: SKU + Supplier + Customer 导入 + 培训"
- "Week 3: PO/SO 试运行 + e-Invoice 测试提交"
- "Week 4: 上线 + 1 周 hypercare"
- "总共 4 周 / 平均 / 复杂的话 6-8 周"

### SLA
- 7×12 工作时间响应 < 1h
- 严重故障 4h 内复原
- 月度 99.5% uptime 承诺

---

## ⏱️ 29:00 — 30:00 收尾 + 下一步

🎤 关键句：
- "今天 30 分钟覆盖：业务三闭环 / 技术架构 / 合规深挖 / AI 透明 / 商务 / 实施"
- "演示站随时可玩：admin@demo.my / Admin@123"
- "Proposal 24h 内邮件 / 线下深度 Demo 可预约 / 试用 30 天"
- "demo@erp-os.my"

🖱️ 切回 Dashboard 留住屏幕

---

## 🆘 救场预案（同 15min 版 + 加项）

| 客户问题 | 应对 |
|---|---|
| "你们能不能 on-premise 部署？" | "可以 / docker compose 一键 / 数据完全在你机房" |
| "数据迁移费时多久？" | "标准模板：SKU/Supplier/Customer Excel 导入 / 1-3 天 / 历史订单按需" |
| "如果你们公司倒了？" | "代码全部交付 / docker image 在你这 / 数据库你的 / 不依赖我们也能跑" |
| "AI 用我们数据训练吗？" | "Anthropic API zero-retention / 我们不存 prompt input / 合同条款明确" |
| "支不支持中文 invoice？" | "完全支持 / OCR 中英混合识别 / e-Invoice LHDN 接受英文为主" |
| "能不能改业务流程？" | "状态机和事件驱动设计为开 / 改流程 1-2 周可定制 / 报价透明" |

---

## 🔥 演示后立即做

1. 邮件感谢 + 附 Proposal Template + 30min PPTX
2. 询问下一步意向（Demo 试用 / 报价 / 技术对接）
3. 24h 内安排定制版 Demo（如需）
4. 把客户问的"独特问题"记 `tasks/lessons.md`，下次准备
