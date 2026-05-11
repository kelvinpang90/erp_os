# 15 分钟版演示视频脚本

> 受众：业务负责人 / IT 主管。目标：完整展示三大闭环 + ROI，让观众主动要 Proposal。
> 结构：开场 1min + 采购闭环 4min + 销售/e-Invoice 闭环 5min + 库存/Dashboard 3min + ROI/收尾 2min。

---

## 录制前清单

- [ ] 同 5min 版清单
- [ ] 准备 3 张 sample invoice（Tan Chong / Syarikat Ahmad / Multi-Currency USD）
- [ ] 准备一个未确认的 SO（在 demo data 里找一个 DRAFT 状态的，或者新建）
- [ ] 关掉 OCR 实际请求超时设置 → DEMO_MODE 下要保证演示稳定
- [ ] 录制前 2 小时刷一次 Dashboard 让 Redis 缓存预热

---

## Part 1: 开场 + 痛点（0:00 — 1:00）

> 同 5min 版 0:00-1:00，但语速可以稍慢，多带点情绪。

**话术加强**：
> 我们花了三个月走访马来本地 30 多家中小企业。听到最多的三个问题：第一，LHDN e-Invoice 怎么搞？第二，几个仓库账实总对不上。第三，AI 都炒了两年了，到底能不能帮我录发票？今天这 15 分钟，我会一一回答。

---

## Part 2: 采购闭环（1:00 — 5:00）

### 1:00 — 1:30 PO 创建（手工版）

**画面**：Purchase Orders → New PO

**话术**：
> 先给大家看普通方式怎么开 PO。选供应商、加 line item、选 SKU、填数量、价格、SST……一张 5 行的 PO 大概要 3-5 分钟。

**操作**：手工填一张 3 行 PO 草稿（不提交）

### 1:30 — 2:30 PO 创建（OCR 版）

**画面**：清空草稿 → 切到 OCR Upload Page

**话术**：
> 现在看 AI OCR 怎么做。我把刚收到的 Tan Chong Trading 的 PDF 拖进来。

**操作**：
1. 拖入 `INV-TanChongTrading.pdf`
2. SSE 进度条（讲解：这是流式响应，Claude Vision 识别中）
3. 表单自动填好

**话术**：
> 5 秒钟。supplier 自动匹配数据库已有的、line items 字段全填好、SST 算对了、total 也算好了。会计只需要复核一下，按确认。

**操作**：点 Confirm → 状态变 CONFIRMED → 库存 incoming +

### 2:30 — 3:30 收货（Goods Receipt）

**画面**：从 PO 详情页点 "Create Goods Receipt"

**话术**：
> 货到了。我们做收货单，可以一次全收，也可以分批收。

**操作**：
1. 部分收货：第 1 行收 50%，第 2 行全收，第 3 行不收
2. 提交 → PO 状态变 PARTIAL_RECEIVED
3. 切到 Stock List → 展示对应 SKU 的 on_hand + / incoming -

**话术**：
> 库存自动更新：on_hand 增加，incoming 减少。同时系统自动重算了加权平均成本——这是符合 MFRS 的标准做法，不需要会计手算。

### 3:30 — 4:30 Stock Movement 流水

**画面**：切到 Stock Movements → 筛选刚才那个 SKU

**话术**：
> 每一笔库存变动都有完整流水。type 是 PURCHASE_IN，关联到刚才的 PO 和 GR，操作人、时间、单价、新成本——全程可追溯。这就是 ERP 跟 Excel 最大的区别：审计跟得上。

### 4:30 — 5:00 Supplier 管理

**画面**：切到 Suppliers 列表

**话术**：
> 供应商管理：30 家本地供应商已经预填——华商、马来商、印度商都有。点详情可以看历史采购统计、应付账款、最近合作的 SKU。

---

## Part 3: 销售 + e-Invoice 闭环（5:00 — 10:00）

### 5:00 — 5:30 创建 SO

**画面**：Sales Orders → New SO

**操作**：
1. 选客户 "Sunshine Mart Sdn Bhd"
2. 加 3 个 SKU
3. 系统实时显示每个 SKU 的可用库存
4. 提交草稿 → 点 Confirm

**话术**：
> 销售单确认后，库存的 reserved 立刻 +，available 立刻 -。这意味着：另一个销售员同时下单同一个 SKU，看到的可用数已经少了——避免超卖。

### 5:30 — 6:00 防超卖（小演示）

**画面**：开第二个浏览器窗口，模拟另一个销售员

**话术**：
> 演示给大家看。我用另一个 Sales 账号开同一个 SKU，再下一单超过库存——

**操作**：尝试下一个超量 SO → 提示 "InsufficientStock"

> 系统在 SQL 层面用原子操作拦住，并发 100 个请求都不会超卖。这是 ERP 跟简单进销存最大的差别。

### 6:00 — 6:30 发货（Delivery Order）

**画面**：回到刚才的 SO → "Create Delivery Order"

**操作**：
1. 全量发货
2. 提交 → SO 状态 → FULLY_SHIPPED
3. 库存 on_hand -, reserved -

**话术**：
> 同时系统记录了出库时的 snapshot_avg_cost——以后客户退货，按当时的成本回填，COGS 算账完全一致。

### 6:30 — 7:30 e-Invoice 草稿 + AI 预校验

**画面**：SO 详情页 → "Generate Invoice"

**话术**：
> 现在生成 e-Invoice。

**操作**：
1. 跳到 invoice 草稿页（自动从 SO 抓字段）
2. 点 "AI Precheck" 按钮
3. PrecheckModal 弹窗显示 10 项规则结果

**话术**：
> 重点说预校验：硬规则部分本地秒出——TIN 格式、SST 计算、邮编州一致；软规则调 Claude API，检查 supplier 名字拼写、商品描述合理性。3 秒内出结果，超时就只跑硬规则降级。

**操作**：故意制造一个错误（比如 TIN 多打一位）→ 看到红色警告 + 修复建议

### 7:30 — 8:30 提交 MyInvois + UIN

**操作**：
1. 修复错误 → 再点 Precheck → 全绿
2. 点 "Submit to MyInvois"
3. 立即返回 UIN + QR code
4. 状态 SUBMITTED → VALIDATED
5. 滑到底部展示 72 秒倒计时

**话术**：
> Demo 模式下 72 小时压成 72 秒。生产环境就是真实的 72 小时反对期：买家收到发票不对可以拒，我们这边自动收到通知。72 秒后自动 FINAL，永久存档。

### 8:30 — 9:30 Credit Note 退货

**画面**：找一张 FINAL 状态的旧 invoice → "Create Credit Note"

**话术**：
> 客户退货怎么办？开 Credit Note。

**操作**：
1. 选要退的 line items
2. 填退货原因
3. 提交 → 库存 on_hand + (按 snapshot_avg_cost)
4. 自动提交一张 Credit Note 到 MyInvois

**话术**：
> 退货入库、会计冲销、e-Invoice 红冲——一气呵成。

### 9:30 — 10:00 Consolidated Invoice (B2C)

**画面**：Admin → e-Invoice → "Generate Monthly Consolidated"

**话术**：
> B2C 场景，比如零售门店每月几千张小票，LHDN 允许月底汇总成一张 Consolidated e-Invoice。我们一键生成，按客户分组、自动求和、自动提交。这是合规操作——不做的话每张小票都要个开 e-Invoice，不可能。

---

## Part 4: 库存 + Dashboard（10:00 — 13:00）

### 10:00 — 11:00 多仓 6 维库存

**画面**：Branch Inventory 热力图

**话术**：
> 三个仓库——KL 主仓、槟城、JB——SKU × 仓库矩阵。颜色越深库存越足，越浅就要补货。

**操作**：
1. Hover 一个 SKU → 弹 6 维详情（on_hand / reserved / quality_hold / available / incoming / in_transit）
2. 点一个低库存格 → 跳到该 SKU 详情页
3. 切到 "Cost Trend" Tab → 显示加权平均成本变动趋势

### 11:00 — 11:30 调拨

**画面**：Stock Transfers → New Transfer

**操作**：
1. 从 KL 主仓 → 槟城仓
2. 选 SKU + 数量
3. Confirm → In Transit
4. 槟城收货 → On hand

**话术**：
> 调拨单四个状态：草稿、确认、在途、已收。在途期间 KL 仓 in_transit 减少、槟城仓 incoming 增加，账面永远清晰。

### 11:30 — 12:30 Low Stock Alert

**画面**：Inventory → Low Stock Alerts

**操作**：
1. 看到红色预警列表
2. 全选 → "Generate Restock POs"
3. 跳到 PO 创建页（多张 PO 草稿，按 supplier 分组、预填 reorder qty）

**话术**：
> 凡是低于 safety_stock 的 SKU 都会出现在这里。可以一次全选，按供应商分组生成补货 PO 草稿——采购员只需要审核一下、调一调数量、点确认。

### 12:30 — 13:00 Dashboard + AI 日报

**画面**：回 Dashboard

**话术**：
> Dashboard 总览：今日销售、待发货、低库存数、待验证发票数、AI 累计成本——5 个 KPI 一眼看完。
>
> 中间这块是 AI 日报，每 30 分钟刷新一次。"昨天卖了 RM 12,500，比上周二高 18%。Top SKU 是 Milo 1kg。有 3 张 invoice 等买家确认，2 个 SKU 库存预警。"——这就是给老板的早报。

---

## Part 5: 收尾 ROI + CTA（13:00 — 15:00）

### 13:00 — 13:30 角色权限演示

**画面**：右上角切换角色

**话术**：
> 4 个内置角色：Admin / Manager / Sales / Purchaser。

**操作**：切 Sales → 菜单只剩销售；切 Purchaser → 看不到客户；切 Manager → 看到 cross-module 报表

> 权限按需配置，可以再细分——比如某个销售员只看自己客户。

### 13:30 — 14:00 i18n + 主题

**画面**：右上角切换语言 + 主题

**操作**：en → 中文（所有界面瞬间变中文）→ 浅色 → 深色

**话术**：
> 中英双语、深浅主题、随时切换。每个用户偏好独立保存。

### 14:00 — 14:30 ROI 算账

**画面**：切到 PPTX 的 ROI slide（或叠加屏幕字幕）

**话术**：
> 算笔账。一个 5 人公司，会计每天录 30 张供应商发票，每张 8 分钟，一年就是 1000 小时——按 RM 60 时薪算，6 万块。OCR 上来后，每张 30 秒，省 95%——一年省 5.7 万。这还不算少录错的罚款。
>
> 一年许可费比这少得多，9 个月回本。

### 14:30 — 15:00 收尾 CTA

**画面**：产品 logo + 联系方式

**话术**：
> 今天讲了三大闭环、AI 自动化、多仓库存、合规。所有功能都是真实可用的——演示站点 `erp-demo.example.my`，账号 admin@demo.my，密码 Admin@123，欢迎自己玩。
>
> 想要正式 Proposal、要看你公司定制版、要约线下 Demo——发邮件到 demo@erp-os.my。我们 24 小时内回。
>
> 感谢观看，下次见。

---

## 后期剪辑要点

- 每个 Part 开头加章节卡（Part 1: Procurement / Part 2: Sales & e-Invoice / ...）
- OCR / Precheck / 防超卖 / 倒计时 4 处放慢 2x
- ROI 数字部分加动画 lower-third
- 全程背景音乐 -25dB
- 片头 logo 3 秒 / 片尾 CTA hold 5 秒
