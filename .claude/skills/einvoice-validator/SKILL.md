---
name: einvoice-validator
version: 1.0.0
description: |
  Use this skill when validating or implementing validation for Malaysian
  LHDN e-Invoice fields before submission to MyInvois. Covers TIN format
  validation, SST classification correctness, MSIC code mapping, required
  field completeness, buyer/seller info checks, amount consistency, and
  LHDN-specific business rules.
  Trigger keywords: e-invoice validation, MyInvois check, LHDN compliance,
  SST classification check, TIN validation, MSIC code check, invoice precheck,
  consolidated invoice rules, credit note rules.
  Do NOT use for: non-Malaysian invoice formats, GST (abolished 2018),
  internal financial audit, payment processing.
---

# e-Invoice Validator — LHDN MyInvois Compliance

本 skill 提供马来西亚 e-Invoice 提交前的**硬规则 + 软规则**校验逻辑库，覆盖 LHDN Specific Guideline v2.3 要求的字段合规性。用于：

1. 实现 `backend/app/services/einvoice.py` 里的 `precheck()` 方法
2. AI 预校验的 prompt 生成（`backend/app/prompts/einvoice_precheck.yaml`）
3. Seed 数据时确保生成的 invoice 都能通过校验
4. 做单元测试 `backend/tests/unit/test_einvoice_precheck.py`

---

## 两层校验体系

### 🔴 硬规则（代码层）
必须通过，不通过拒绝提交。完全用代码实现，不调 LLM。

### 🟡 软规则（LLM 辅助）
建议性检查。即使不通过也可以"Override & Submit"，但会给出警告。用 LLM 做语义判断。

---

## 硬规则清单（Hard Rules）

### H1. 必填字段检查

Seller（己方组织）：
- `tin` 必填，格式 `^C\d{10}$`（企业）或 `^\d{12}$`（个人）
- `name` 必填
- `registration_no` 必填
- `sst_registration_no`：若 seller 是 SST 注册商必填
- `msic_code` 必填，必须在 `reference/msic_2008_codes.json` 白名单
- `address_line1 / city / state / postcode / country` 必填

Buyer：
- B2B：`tin + name + registration_no + address` 全必填
- B2C：`name + address` 必填；`tin` 可为 `000000000000`（Consolidated Invoice 用 "General Public"）
- Consolidated：`buyer_name = "General Public"` + `buyer_tin = "EI00000000010"`

Invoice：
- `document_no` 必填（`INV-YYYY-NNNNN` 格式）
- `business_date` 必填，不能是未来
- `currency` 必填 ISO 4217
- `exchange_rate`：非 MYR 必填
- 至少一行 line item
- `subtotal_excl_tax + tax_amount = total_incl_tax`（±0.01 容差）

### H2. TIN 格式

```python
import re

CORP_TIN = re.compile(r'^C\d{10}$')
INDIV_TIN = re.compile(r'^\d{12}$')
GENERAL_PUBLIC_TIN = "EI00000000010"

def is_valid_tin(tin: str, is_corp: bool) -> bool:
    if tin == GENERAL_PUBLIC_TIN: return True
    return bool(CORP_TIN.match(tin) if is_corp else INDIV_TIN.match(tin))
```

### H3. SST 计算一致性

```python
# 每行
expected_tax = (unit_price_excl_tax * qty - discount) * tax_rate_percent / 100
assert abs(line.tax_amount - expected_tax) < Decimal("0.01")

# 整单
assert sum(l.line_total_excl_tax for l in lines) == invoice.subtotal_excl_tax
assert sum(l.tax_amount for l in lines) == invoice.tax_amount
assert invoice.subtotal_excl_tax + invoice.tax_amount - invoice.discount_amount == invoice.total_incl_tax
```

### H4. MSIC Code 白名单

MSIC 2008 码必须在 `reference/msic_2008_codes.json` 里存在。

### H5. 邮编 ↔ 州一致性

邮编前 2 位对应州（详见 `reference/postcode_state_map.md`）：
- KL: 50-59
- Selangor: 40-48
- Penang: 10-14
- Johor: 80-86
- ... 等

不一致 → 硬规则失败（LHDN 会拒）。

### H6. 货币一致性

同一张 invoice 所有 line 的 currency 必须一致，且等于 invoice 头的 currency。

### H7. Consolidated Invoice 规则

- `invoice_type = CONSOLIDATED`
- `business_date` 必须是月末后 7 天内
- `sales_order_id` 应该为 NULL
- `buyer_tin = 'EI00000000010'`, `buyer_name = 'General Public'`
- 至少 1 行（通常是汇总行，描述为 "B2C Sales for {month} {year}"）

### H8. Credit Note 规则

- 必须关联一张 `invoice_id`（被冲销的原发票）
- 原发票状态必须是 `VALIDATED / FINAL`
- CN 金额（绝对值）不能超过原发票金额
- CN 行必须对应原 invoice line

---

## 软规则清单（Soft Rules, LLM-assisted）

### S1. SST 分类合理性

依据 `reference/sst_classification_rules.md` 判断商品名称和 SST rate 是否匹配。

**例子**：
- 商品："Panadol Extra 500mg"，SST Rate = `SST-10` → 警告：药品应为 `EXEMPT`
- 商品："Jasmine Rice 5kg"，SST Rate = `SST-10` → 警告：基本食品应为 `EXEMPT`

### S2. MSIC Code 与业务匹配

根据 line item 描述判断 MSIC 码是否合理。

**例子**：
- MSIC = `47190`（百货零售）但销售商品是"Laptop Dell XPS 15"  
  → 建议 `47411`（电脑零售）

### S3. 买家地址与州匹配

邮编和州名一致性检查。

**例子**：
- `postcode = "50450"`, `state = "Penang"` → 警告：邮编属于 KL

### S4. 描述质量

Line item `description` 不应过于笼统。

**例子**：
- "Goods" / "Items" / "Product" → 建议：使用具体商品名

### S5. 大额订单异常检测

- 单张发票 > RM 100,000 → 提示二次确认
- 单品 qty > 1000 → 提示核对单位（UOM 是不是错了？PCS vs CTN）

---

## LLM Prompt 结构

用于 AI 软规则预校验，返回 JSON：

```yaml
# backend/app/prompts/einvoice_precheck.yaml
version: "1.0"
model: "claude-sonnet-4-6"
temperature: 0.1
timeout_seconds: 3

system: |
  You are a Malaysian LHDN e-Invoice compliance expert.
  You check invoice fields for logical consistency against Malaysian tax rules.
  Only flag issues; do not block submission.
  
user_template: |
  Check this invoice for issues:
  
  Seller: {seller_json}
  Buyer: {buyer_json}
  Lines: {lines_json}
  Totals: {totals_json}
  
  Rules to check:
  1. SST classification matches product type (pharmacy/basic food should be EXEMPT)
  2. MSIC code matches line item description
  3. Postcode matches state
  4. Description quality (not vague)
  
  Return JSON with this exact shape:
  {{
    "warnings": [
      {{
        "field": "lines[0].tax_rate",
        "current": "SST-10",
        "suggested": "EXEMPT",
        "reason": "Panadol is an OTC medicine, should be tax-exempt",
        "severity": "WARNING"
      }}
    ]
  }}

response_schema:
  type: object
  properties:
    warnings:
      type: array
      items:
        type: object
        properties:
          field: { type: string }
          current: { type: string }
          suggested: { type: string }
          reason: { type: string }
          severity: { type: string, enum: [INFO, WARNING, ERROR] }
```

---

## 输出格式

`precheck()` 方法返回结构：

```python
@dataclass
class PrecheckResult:
    passed: bool                              # 硬规则是否全通过
    hard_errors: list[HardError]              # 硬规则失败项
    soft_warnings: list[SoftWarning]          # 软规则警告项
    precheck_duration_ms: int
    ai_used: bool                              # AI 是否成功调用
    ai_error: str | None                       # AI 失败原因（超时/限流等）

@dataclass
class HardError:
    code: str                      # "MISSING_FIELD" | "INVALID_TIN" | ...
    field: str
    message: str
    i18n_key: str                  # "einvoice.error.missing_tin"
    i18n_params: dict

@dataclass
class SoftWarning:
    code: str
    field: str
    current: str
    suggested: str | None
    reason: str
    severity: str                   # "INFO" | "WARNING"
    can_auto_fix: bool
```

---

## UI 展示（参考）

Precheck 结果弹窗结构：

```
┌─────────────────────────────────────────────┐
│ 🟢 Ready to Submit (8/10 checks passed)      │
├─────────────────────────────────────────────┤
│ ✅ TIN Format Valid                          │
│ ✅ SST Calculated Correctly                  │
│ ✅ MSIC Code Valid                           │
│ ✅ Required Fields Complete                  │
│ ⚠️  SST Classification Suggestion            │
│     Line 1: "Panadol 500mg" as SST-10       │
│     Suggest: EXEMPT (OTC medicine)          │
│     [Apply Suggestion] [Keep As Is]         │
│ ⚠️  Postcode / State Mismatch                │
│     Postcode 50450 is KL, not Penang        │
│     [Fix] [Keep As Is]                      │
├─────────────────────────────────────────────┤
│           [Cancel]    [Submit Anyway]        │
└─────────────────────────────────────────────┘
```

---

## 降级策略（AI 挂了怎么办）

```python
async def precheck(invoice: Invoice) -> PrecheckResult:
    hard = run_hard_rules(invoice)            # 纯代码，不会挂
    
    try:
        soft = await run_ai_soft_rules(invoice, timeout=3)
    except (TimeoutError, APIError) as e:
        log.warning("AI precheck failed, using fallback", error=str(e))
        soft = run_fallback_soft_rules(invoice)  # 简单规则，覆盖部分场景
    
    return PrecheckResult(
        passed=len(hard.errors) == 0,
        hard_errors=hard.errors,
        soft_warnings=soft.warnings,
        ai_used=not isinstance(e, Exception),
    )
```

`run_fallback_soft_rules` 用**关键词匹配**代替 LLM：
- 商品名含 "mg | capsule | tablet | syrup" 且 `tax_rate != EXEMPT` → 警告
- MSIC `47190` + 商品名含 "laptop | computer | phone" → 警告

---

## 引用文件

以下文件在本 skill 的 `reference/` 下，使用时按需加载：

- `lhdn_required_fields.md` — 完整必填字段表
- `tin_format.md` — TIN 格式详细规则
- `sst_classification_rules.md` — SST 分类决策树
- `msic_2008_codes.json` — MSIC 2008 白名单（40 个常用）
- `postcode_state_map.md` — 邮编州对应表

---

## 与其他 skill 的关系

- **erp-seed-generator**：seed 生成的 invoice 必须能通过本 validator 硬规则
- **new-resource**：实现 Invoice 模块时 precheck service 用本 skill 的规则
