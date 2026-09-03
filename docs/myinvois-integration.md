# MyInvois (LHDN e-Invoice) 对接说明

> 本文档描述 erp-os 与马来西亚 LHDN MyInvois 的真实对接：如何申请凭据、如何切换模式、
> 协议细节、以及**尚未完成的部分**。

---

## 1. 当前状态

| 能力 | 状态 |
|---|---|
| Mock adapter（离线、确定性） | ✅ 可用，Demo 默认 |
| OAuth 2.0 client-credentials + token 缓存 | ✅ 已实现 |
| UBL 2.1 JSON 文档构造（v1.0，未签章） | ✅ 已实现 |
| 提交 / 轮询验证 / 查状态 / 买方拒收 | ✅ 已实现 |
| 异步验证对账（SUBMITTED → VALIDATED/REJECTED） | ✅ 已实现（手动按钮 + Celery 每 2 分钟） |
| **XAdES 数字签名（文档 v1.1）** | ❌ **未实现** — 见 §6 |
| 真实凭据下的端到端联调 | ⏳ 待凭据到位 |

代码不依赖任何凭据即可跑测试；`MYINVOIS_MODE=mock` 时完全不触网。

---

## 2. 三种模式

`MYINVOIS_MODE` 决定用哪个 adapter，**API/Portal 域名由该值推导，没有独立的 URL 配置项** ——
这是有意的：避免有人只改一个变量就把 preprod 凭据打到生产。

| 模式 | Adapter | API base | Portal base |
|---|---|---|---|
| `mock` | `MyInvoisMockAdapter` | — | — |
| `sandbox` | `MyInvoisRealAdapter` | `https://preprod-api.myinvois.hasil.gov.my` | `https://preprod.myinvois.hasil.gov.my` |
| `production` | `MyInvoisRealAdapter` | `https://api.myinvois.hasil.gov.my` | `https://myinvois.hasil.gov.my` |

---

## 3. 申请 Preprod 凭据

1. 用公司 TIN 登录 [MyTax 门户](https://mytax.hasil.gov.my)
2. 进入 **MyInvois → e-Invoice Settings → ERP System**（沙盒在 `preprod.myinvois.hasil.gov.my`）
3. 注册一个 ERP System，拿到 **Client ID** 和 **Client Secret**
4. 若是代客户提交（中介模式），另需被代理方在其 MyTax 授权本 ERP 为 Intermediary，
   并把对方 TIN 填入 `MYINVOIS_ON_BEHALF_OF`

> Preprod 数据保留 3 个月，限流低于生产，不产生法律效力。

---

## 4. 启用步骤

在 `.env` 里（**不要进 Git**）：

```bash
MYINVOIS_MODE=sandbox
MYINVOIS_CLIENT_ID=<从 MyTax 拿到的>
MYINVOIS_CLIENT_SECRET=<从 MyTax 拿到的>
# 仅中介模式需要
MYINVOIS_ON_BEHALF_OF=
```

重启 backend 与 celery-worker。缺凭据时 **启动构造 adapter 就会抛
`ConfigurationError`（MYINVOIS_MISSING_CREDENTIALS）**，不会拖到第一次提交才炸。

提交前请确认组织与客户主数据完整，否则 LHDN 会拒：

- Organization：`tin` / `registration_no` / `msic_code` / 地址 / 电话 / 邮箱
- Customer：`tin`（B2C 无 TIN 时自动用 LHDN 的 `EI00000000010`）/ 地址 / 电话

### 已知的数据缺口

| 字段 | 现状 | 影响 |
|---|---|---|
| `IndustryClassificationCode/@name`（MSIC 行业描述） | 只存了 code，描述发 `NOT APPLICABLE` | LHDN 目前不硬校验；若要精确，需给 Organization 增加 `msic_description` 字段 |
| 行项目 `ItemClassificationCode`（LHDN CLASS 码） | SKU 上无该字段，统一发 `022`（Others） | 同上；行业化时需给 SKU 增加分类码 |
| 免税行的 `TaxExemptionReason` | 统一发通用文案 | 若客户需逐项免税证明，需给行项目增加原因字段 |

---

## 5. 提交时序

LHDN 的提交是**两段式**的，这是本次对接最重要的一点：

```
ERP                          LHDN MyInvois
 │
 ├─ POST /connect/token ────────────▶
 │  ◀──────────── access_token (60 min，缓存在 Redis)
 │
 ├─ POST /api/v1.0/documentsubmissions
 │     {documents:[{format:"JSON", document:<base64>,
 │                  documentHash:<sha256 hex>, codeNumber:<单号>}]}
 │  ◀──────────── 202 {submissionUid, acceptedDocuments:[{uuid}], rejectedDocuments:[]}
 │
 │   （LHDN 在服务端异步校验）
 │
 ├─ GET /api/v1.0/documents/{uuid}/details   ← 最多轮询 MYINVOIS_POLL_ATTEMPTS 次
 │  ◀──────────── {status: Submitted | Valid | Invalid, longId, dateTimeValidated,
 │                 validationResults}
 ▼
```

对应的本地状态：

| LHDN 结果 | 本地 InvoiceStatus | 说明 |
|---|---|---|
| `rejectedDocuments` 非空 | 保持 `DRAFT` | 抛 `MyInvoisRejectedError`，附 LHDN 原始错误码 |
| `Valid` | `VALIDATED` | 写入 UIN + QR，发 `EInvoiceValidated`，启动 72h 反对期 |
| `Invalid` | 保持 `DRAFT` | 抛 `MyInvoisRejectedError`，附 `validationResults` 摘要 |
| 轮询预算用尽仍 `Submitted` | **`SUBMITTED`** | 已写入 UIN，等待对账 |

**`SUBMITTED` 绝不能重新提交** —— 单据已经在 LHDN 那边了，10 分钟内重复提交会被
`DuplicateSubmission` 拒绝。对账有两条路：

- 手动：发票详情页「Refresh Status」按钮 → `POST /api/invoices/{id}/refresh-status`
- 自动：Celery beat `einvoice-pending-scan`，每 2 分钟扫一次
  （也有管理端点 `POST /api/invoices/admin/run-pending-scan`）

QR / 公开验证链接：`{portalBase}/{uuid}/share/{longId}`，`longId` 只在验证通过后才有。

### 买方拒收

`PUT /api/v1.0/documents/state/{uuid}/state`，body `{"status":"Rejected","reason":"..."}`。
LHDN 侧限 72 小时（`DEMO_MODE` 下本地倒计时压缩为 72 秒，仅影响本地 FINAL 推进，
不改变 LHDN 的真实窗口）。

---

## 6. ⚠️ 未完成：数字签名

LHDN 文档分两个版本：

- **v1.0** —— 结构与 v1.1 完全相同，**签名校验关闭**
- **v1.1** —— 要求 XAdES 数字签名，证书须由**马来西亚持牌 CA** 签发

本实现输出 **v1.0**（`listVersionID: "1.0"`），因为项目目前没有证书。

`MYINVOIS_SIGN_ENABLED` 是一个防呆开关：打开它会在构造 adapter 时直接抛
`MYINVOIS_SIGNING_UNAVAILABLE`，**而不是**静默降级发未签章文档 —— 合规问题晚发现代价太大。

补齐签名需要：
1. 向持牌 CA 申请 X.509 证书（软证书或 HSM）
2. 实现 JSON XAdES：剔除 `UBLExtensions` / `Signature` → minify → SHA-256 →
   RSA-SHA256 签名 → 回填 `UBLExtensions` + `Signature`
3. 文档改发 `listVersionID: "1.1"`

---

## 7. 限流

| 端点 | LHDN 限制 |
|---|---|
| `/connect/token` | 100 RPM per Client ID |
| 提交 | 100 RPM，单次最多 100 份 / 5 MB，单张 ≤ 300 KB |
| 查文档详情 | 125 RPM |
| 拒收 | 12 RPM |

代码侧：单张发票超 300 KB 直接抛 `MYINVOIS_DOCUMENT_TOO_LARGE`（不浪费一次请求）；
429 与 5xx 按 1s / 2s 退避重试 3 次；4xx 立即失败。

---

## 8. 代码地图

| 文件 | 职责 |
|---|---|
| `app/integrations/myinvois.py` | Protocol + DTO（provider 无关，无 ORM 依赖） |
| `app/integrations/myinvois_mock.py` | 离线 mock |
| `app/integrations/myinvois_codes.py` | LHDN 代码表（州属 / 国家 / 税类 / UOM / 单据类型） |
| `app/integrations/myinvois_ubl.py` | UBL 2.1 JSON 文档构造（纯函数） |
| `app/integrations/myinvois_http.py` | OAuth + HTTP + 重试 + token 缓存 |
| `app/integrations/myinvois_real.py` | 真实 adapter（提交 / 轮询 / 查状态 / 拒收） |
| `app/integrations/myinvois_factory.py` | 按 `MYINVOIS_MODE` 选择实现 |
| `app/services/myinvois_payload.py` | ORM → payload 映射（Invoice 与 CN 共用） |

测试：`tests/unit/test_myinvois_ubl.py`（文档结构 + 代码表）、
`tests/unit/test_myinvois_real.py`（HTTP 协议，`httpx.MockTransport`，无网络）、
`tests/unit/test_einvoice_pending.py`（异步验证的服务层状态流转）。

---

## 9. 官方参考

- SDK 首页：https://sdk.myinvois.hasil.gov.my/
- 提交文档 API：https://sdk.myinvois.hasil.gov.my/einvoicingapi/02-submit-documents/
- 查文档详情：https://sdk.myinvois.hasil.gov.my/einvoicingapi/08-get-document-details/
- 拒收文档：https://sdk.myinvois.hasil.gov.my/einvoicingapi/04-reject-document/
- Credit Note v1.0：https://sdk.myinvois.hasil.gov.my/documents/credit-v1-0/
- JSON 签名：https://sdk.myinvois.hasil.gov.my/signature-creation-json/
