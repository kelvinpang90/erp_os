---
name: erp-seed-generator
version: 1.0.0
description: |
  Use this skill when generating seed / demo / test data for the Malaysian
  ERP project (erp-os). Covers SKUs with authentic Malaysian brand names
  and pricing, Malaysian suppliers (Sdn Bhd patterns), B2B and B2C customers,
  warehouses in KL/Penang/JB, and historical orders spanning 6 months
  with seasonal patterns (Ramadan, CNY, year-end spikes).
  Trigger keywords: seed data, demo data, SKU generation, supplier generation,
  customer generation, populate database, historical orders, malaysian retail data,
  reset demo data.
  Do NOT use for: production customer data, non-Malaysia markets, schema design,
  generic faker output.
---

# ERP Seed Data Generator — Malaysia Edition

本 skill 用于为 `erp-os` 项目生成马来西亚本地化的真实 seed 数据，保证 Demo 呈现"看起来就是马来公司在用"的专业感。

## 适用场景

- 首次初始化数据库
- 每日凌晨 Demo Reset 后重建事务数据
- 新增一批 SKU / 供应商 / 客户
- 调整季节性数据让 Dashboard 图表好看

## 不适用场景

- 生产数据（PDPA 合规不允许用假数据）
- 非马来西亚市场（SST、MSIC、TIN 不适用）
- Schema 设计（看 `docs/ddl.sql` 和 `CLAUDE.md`）

---

## 核心原则

### 1. 真实性大于完整性
客户看数据第一眼就会判断专业度。**宁可少但真，不要多但假**。

- ❌ 不要用 `Supplier001`、`ProductA`、`John Doe`
- ✅ 用真实存在的马来品牌/公司名：`Milo 3-in-1 30s`、`Tan Chong Trading Sdn Bhd`、`Lim Wei Ming`

### 2. 本地化细节是加分项
马来客户的华商老板特别关注这些细节：

- 公司名后缀：`Sdn Bhd` / `Enterprise` / `Trading` / `Holdings`（不要 LLC / Inc / GmbH）
- 人名：华人 + 马来 + 印度族混合（如 `Tan Chong Wei` / `Ahmad bin Ismail` / `Priya Ramasamy`）
- 地址：真实的 KL / Selangor / Penang / JB / Ipoh 街道
- 电话：`+60 3-XXXX XXXX`（KL）/ `+60 4-XXX XXXX`（Penang）
- 邮编：KL 50000-59999 / Selangor 40000-48999 / Penang 10000-14999 / JB 80000-86999
- 价格：RM 单位，不要 $ / ¥

### 3. 参考 CLAUDE.md 的 Schema 约定
生成前必读 `docs/ddl.sql`。关键字段：

- 所有金额 `DECIMAL(18, 4)`
- 所有业务表要 `organization_id = 1`（默认 DEMO 组织）
- 软删除字段 `deleted_at = NULL`
- `version = 0`
- 时间 UTC（订单 `business_date` 独立字段）

---

## 生成规模（默认）

| 实体 | 数量 | 备注 |
|---|---|---|
| Brands | 40-60 | 真实马来常见品牌 |
| Categories | 20-30（树形 2 层） | Food / Beverage / Personal Care / Electronics 等 |
| SKUs | 200 | 覆盖 4-5 个主品类 |
| Suppliers | 30 | 华商 20 + 马来商 8 + 印度商 2 |
| Customers | 50 | B2B 30 + B2C 20 |
| Warehouses | 3 | Main-KL / Branch-Penang / Branch-JB |
| Historical POs | ~150 | 过去 6 个月，含各种状态 |
| Historical SOs | ~300 | 过去 6 个月，含各种状态 |
| Historical Invoices | ~250 | 跟随 SO，含 Validated / Final / Rejected 样本 |
| Consolidated Invoices | 6 | 月度 B2C 汇总 |
| Credit Notes | ~20 | 退货场景 |
| Stock Movements | ~2000 | PO + SO + 调拨 + 调整 |
| Stock Adjustments | ~10 | 含 PHYSICAL_COUNT / DAMAGE 场景 |
| Stock Transfers | ~15 | 多仓调拨 |
| Notifications | ~30 | 低库存 / e-Invoice 状态 |

---

## 数据生成步骤

### Step 1：读取参考数据
加载本 skill 的 reference/ 文件：
- `reference/malaysian_brands.json` — 真实品牌数据
- `reference/msic_common_codes.json` — 常用 MSIC 行业码
- `reference/sst_classification_guide.md` — 商品到 SST 档位的映射
- `reference/malaysian_company_patterns.md` — 公司名生成规则
- `reference/malaysian_names.json` — 人名池（按族群）
- `reference/malaysian_addresses.json` — 地址模板（按城市）

### Step 2：生成 Master Data（基础数据）
顺序：currencies → tax_rates → uoms → brands → categories → msic_codes → warehouses → users → roles → permissions

> Master data 在 Demo Reset 时**不删除**，只生成一次。

### Step 3：生成 SKU
每个 SKU 必须包含：

```yaml
code: SKU-00001              # 递增
barcode: 9556001234567       # 马来常见 EAN-13 9556xxxxxxxxx
name: "Milo 3-in-1 Regular 30s"  # 英文主名
name_zh: "美禄 3合1 原味 30小包"  # 可选，有华商常用中文名的加
brand_id: <Milo 的品牌 id>
category_id: <Beverage/Powder 的分类 id>
base_uom: PKT
tax_rate: SST-10                  # 一般商品；药品/基本食品 EXEMPT
unit_price_excl_tax: 18.90       # RM
unit_price_incl_tax: 20.79       # 含 10% SST
safety_stock: 20
reorder_point: 40
reorder_qty: 100
track_batch: true                  # 食品类建议开
track_expiry: true
shelf_life_days: 540               # Milo 18 个月
```

### Step 4：生成 Supplier
公司名模板（详见 `reference/malaysian_company_patterns.md`）：

```
{姓氏} {商业动词} Sdn Bhd
例：Tan Chong Trading Sdn Bhd
    Lim & Sons Enterprise
    Syarikat Ahmad Ismail Sdn Bhd
    Raju Brothers Distributors Sdn Bhd
```

TIN 格式：`C` + 10 位数字（企业）或 12 位数字（个人）。

### Step 5：生成 Customer
B2B 客户：类似 Supplier 但做零售/批发。
B2C 客户：个人，TIN 为 12 位 NRIC 格式（`YYMMDD-PB-XXXX`）。

### Step 6：生成 Stock 初始状态
每个 SKU × Warehouse 组合一条 Stock 记录：
- `initial_on_hand`：根据 SKU 属性给合理值（快消品 200-500、电子产品 10-50）
- `on_hand = initial_on_hand`
- `avg_cost`：按 `unit_price_excl_tax × (0.55~0.75)` 设置（毛利 25-45%）
- `initial_avg_cost = avg_cost`（Demo Reset 恢复用）

### Step 7：生成历史事务数据
**关键：产生季节性曲线，让 Dashboard 图表好看**：

- **1-2 月**：CNY 前糖果/饮料销量翻倍
- **3-4 月**：斋戒月前食品/饮料略涨（Ramadan prep）
- **5-6 月**：Hari Raya 后回落
- **7-9 月**：平稳
- **10-12 月**：年终 + 双 11 双 12 促销，所有品类 +30%

订单时间分布：
- 85% CONFIRMED / FULLY_RECEIVED / FULLY_SHIPPED / INVOICED（正常成交）
- 10% PARTIAL_RECEIVED / PARTIAL_SHIPPED（演示部分流程）
- 5% CANCELLED（演示取消场景）

发票状态分布：
- 70% FINAL（历史订单已过 72h）
- 15% VALIDATED（最近几天）
- 10% SUBMITTED（正在提交中）
- 3% REJECTED（演示拒绝场景）
- 2% DRAFT

### Step 8：生成 Notifications
基于事务数据推导：
- SKU 库存 < safety_stock 的 → `LOW_STOCK`
- 最近 72h 内 VALIDATED 的 e-Invoice → `EINVOICE_EXPIRING`（倒计时）
- 最近 7 天 REJECTED 的 → `EINVOICE_REJECTED`

---

## 输出格式

**优先输出 SQL INSERT**（可直接 `mysql < seed.sql` 执行）：

```sql
-- skus.sql
INSERT INTO skus (organization_id, code, name, name_zh, brand_id, category_id, ...) VALUES
  (1, 'SKU-00001', 'Milo 3-in-1 Regular 30s', '美禄3合1 原味 30小包', 5, 12, ...),
  (1, 'SKU-00002', 'Maggi Curry 79g', '美极咖喱面 79g', 8, 15, ...),
  ...
```

**或输出 Excel**（配合 xlsx skill，方便人工审查修改再导入）：
- 一个 `.xlsx` 多个 sheet：`brands` / `categories` / `skus` / `suppliers` / `customers`
- 带数据校验（SST rate 下拉、必填高亮）

**或输出 Python 脚本**（`backend/scripts/seed_master_data.py`）直接用 SQLAlchemy bulk_insert。

---

## 与其他 skill 配合

- **xlsx skill**：用 xlsx 生成审查版 Excel，人工改 → 再读 Excel 生成 SQL
- **pdf skill**：生成几张 OCR 测试用的发票 PDF 样本（配 seed 的 supplier）
- **einvoice-validator skill**：生成的 invoice seed 数据跑一遍 validator 确保合规

---

## 演示加分 tips

1. **把你的目标客户放进 seed data**：如果要演示给某个药店连锁，seed 里加几个"X药房"类似的 customer 让客户看到"哎这不就是我们吗"
2. **有一张戏剧性的订单**：例如 SKU-001 一次性下了 1000 PCS，触发低库存预警（演示时可以秀）
3. **至少一张 REJECTED 的 e-Invoice**：有故事（拒绝原因明确、附件可看），演示 Credit Note 流程
4. **准备 OCR 测试的"配对"发票**：seed 里有供应商 Tan Chong Trading，pdf skill 生成一张 Tan Chong Trading 的发票 PDF，演示 OCR 识别后自动匹配到这家供应商

---

## 边界情况提醒

- **金额精度**：全程用 `Decimal`，不要用 float，不要用 Python 的 `round()`（用 `quantize(Decimal('0.0001'))`）
- **SST 计算一致性**：`subtotal_excl_tax × tax_rate = tax_amount`，小数点要跟 DDL 定义一致
- **批号命名**：`BATCH-{YYYYMMDD}-{4位递增}`，如 `BATCH-20260401-0001`
- **文档号连续性**：Reset 后文档号重置到与历史订单数量匹配的位置（避免 `SO-2026-0001` 突然跳 `SO-2026-0500`）
- **Stock 与 Movement 一致性**：生成完所有 Movement 后，Stock 表的 `on_hand` 必须 = `initial_on_hand + Σ(inbound) - Σ(outbound)`。生成结束后用 SQL 自检。

---

## 一个完整示例 prompt

用户说："给我造 200 个 SKU，主打快消品"
→ 本 skill 应该：

1. 读 `reference/malaysian_brands.json`，选出快消类（食品饮料、个人护理、清洁用品）约 40 个品牌
2. 为每个品牌生成 3-6 个 SKU 变体（口味/规格）
3. 价格参考真实马来超市价（Jaya Grocer / Village Grocer 水平）
4. SST 大部分 10%，基本食品（米、油、面粉）0%
5. 保质期按品类（饮料 12-18 月，薯片 6 月，清洁 24 月）
6. 输出 SQL + Excel 两份，让用户选
