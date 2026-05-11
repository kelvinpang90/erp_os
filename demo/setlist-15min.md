# Setlist — 15 分钟演示（桌面便签格式）

> 现场 Demo 时贴在第二屏 / 平板上。每分钟标"我现在该说什么 + 该点什么"。
> 字够大，演示时一眼能扫到。

---

## 演示前 5 分钟（桌面状态）

✅ Chrome 隐身窗口 / 100% zoom / `https://erp-demo.example.my`
✅ 已登录 admin@demo.my / 停在 Dashboard
✅ 桌面有 `INV-TanChongTrading.pdf`
✅ 第二屏开本文件
✅ 关 Slack / WeChat / 邮件
✅ 录屏（如果同步录）按 `Ctrl+Shift+R`

---

## ⏱️ 0:00 — 1:00 开场 + 痛点

📍 **页面**：Dashboard
🎤 **关键句**：
- "马来本地中小企业 / 三个痛点：e-Invoice / 多仓 / OCR"
- "30 家走访 / 听到最多的问题"

🖱️ **操作**：hover KPI 卡片，停在 "Pending Invoices" 和 "Low Stock"

---

## ⏱️ 1:00 — 2:30 采购：手工 vs OCR

### 1:00-1:30 手工
📍 **页面**：Purchase Orders → New PO
🎤 "看普通方式怎么开 / 5 行 PO 要 3-5 分钟"
🖱️ 填一行就停 → "太慢了，看 AI 版"

### 1:30-2:30 OCR
📍 **页面**：清空 → OCR Upload Page
🖱️ 拖入 `INV-TanChongTrading.pdf`
👀 SSE 进度 20→50→80→100
🎤 "Claude Vision / 5 秒 / supplier 自动匹配 / SST 算对"
🖱️ Confirm → CONFIRMED

---

## ⏱️ 2:30 — 4:30 收货 + 库存追溯

### 2:30-3:30 GR
📍 **页面**：刚才 PO → "Create Goods Receipt"
🖱️ 部分收货：行 1 收 50%、行 2 全收、行 3 不收
🎤 "PARTIAL_RECEIVED / on_hand+ / incoming- / 加权平均自动算 / MFRS 标准"

### 3:30-4:30 Stock Movement
📍 **页面**：Stock Movements → 筛选刚才 SKU
🎤 "PURCHASE_IN / 关联 PO+GR / 操作人 / 时间 / 单价 / 新成本 / 完整审计"

---

## ⏱️ 4:30 — 5:00 Supplier 速览

📍 **页面**：Suppliers
🎤 "30 家本地 / 华商马来商印度商 / 应付账款 / 历史采购"
🖱️ 进一个 supplier 详情（任选 Tan Chong）→ 30 秒后切走

---

## ⏱️ 5:00 — 6:00 销售单 + 防超卖

### 5:00-5:30 SO
📍 **页面**：Sales Orders → New SO
🖱️ 客户 Sunshine Mart / 3 SKU / 看实时可用库存
🎤 "Confirm → reserved+ / available- / 防超卖关键"

### 5:30-6:00 防超卖小演示
🖱️ 第二个浏览器窗口 / 同 SKU 超量下单
👀 提示 "InsufficientStock"
🎤 "SQL 原子操作 / 100 并发不超卖 / 这是 ERP vs 简单进销存"

---

## ⏱️ 6:00 — 6:30 发货 DO

📍 **页面**：刚才 SO → "Create Delivery Order"
🖱️ 全量 → FULLY_SHIPPED
🎤 "snapshot_avg_cost / 退货时按当时成本回 / COGS 一致"

---

## ⏱️ 6:30 — 8:30 ⭐ e-Invoice 核心

### 6:30-7:30 草稿 + Precheck
📍 **页面**：SO → "Generate Invoice"
🖱️ "AI Precheck" 按钮
👀 PrecheckModal 10 项规则
🎤 "硬规则秒出 / 软规则 Claude / 3 秒超时降级"

🖱️ ⚠️ **故意改错 TIN 多打一位** → 看红色警告
🎤 "TIN 格式 / SST 配比 / 邮编州一致 / 50 倍快"

### 7:30-8:30 提交 + UIN + 倒计时
🖱️ 修复 → 再 Precheck 全绿 → "Submit to MyInvois"
👀 立即返回 UIN + QR
🖱️ 滑到底部 → 72 秒倒计时
🎤 "Demo 模式 72s = 生产 72h / 买家可拒 / FINAL 自动归档"

---

## ⏱️ 8:30 — 10:00 Credit Note + Consolidated

### 8:30-9:30 CN 退货
📍 **页面**：找 FINAL 旧 invoice → "Create Credit Note"
🖱️ 选要退的 line / 填原因 / 提交
👀 库存 on_hand+ / 自动提交红冲到 MyInvois
🎤 "退货 / 会计冲销 / e-Invoice 红冲 / 一气呵成"

### 9:30-10:00 Consolidated
📍 **页面**：Admin → e-Invoice → "Generate Monthly Consolidated"
🎤 "B2C 月底汇总 / 几千张小票 → 一张 / LHDN 合规 / 否则不可能"

---

## ⏱️ 10:00 — 11:00 多仓 6 维

📍 **页面**：Branch Inventory 热力图
🎤 "三仓 / SKU × 仓库 / 颜色深浅"
🖱️ Hover 一格 → 6 维详情
🖱️ 点进 SKU 详情 → "Cost Trend" Tab → 加权平均趋势

---

## ⏱️ 11:00 — 11:30 调拨

📍 **页面**：Stock Transfers → New Transfer
🖱️ KL → 槟城 / 选 SKU / Confirm → In Transit → Receive
🎤 "4 状态 / in_transit + incoming 双账面"

---

## ⏱️ 11:30 — 12:30 Low Stock + 一键 PO

📍 **页面**：Inventory → Low Stock Alerts
👀 红色预警列表
🖱️ 全选 → "Generate Restock POs"
👀 跳到 PO 创建页（多张草稿 / 按 supplier 分组 / 预填）
🎤 "safety_stock 自动监控 / 采购员审批就行 / 老板不用问'我们有多少货'"

---

## ⏱️ 12:30 — 13:00 Dashboard + AI 日报

📍 **页面**：Dashboard
🎤 "5 KPI / AI 日报 30 分钟刷新 / 给老板的早报"
🖱️ 展开 AI Summary → 念两句

---

## ⏱️ 13:00 — 13:30 角色权限

🖱️ 右上角切换 Sales → 菜单变窄
🖱️ 切 Purchaser → 看不到客户
🖱️ 切回 Admin
🎤 "4 角色 / 销售看不到成本 / 采购看不到客户"

---

## ⏱️ 13:30 — 14:00 i18n + 主题

🖱️ 右上角 EN → 中文（瞬间切）→ 浅色 → 深色
🎤 "中英双语 / 深浅主题 / 用户偏好独立"

---

## ⏱️ 14:00 — 14:30 ROI 算账

🎤 **念脚本（背下来更好）**：
> "5 人公司 / 会计每天 30 张发票 × 8 分钟 = 一年 1000 小时 = RM 60K
> OCR 后 95% 节省 = 一年省 RM 57K
> 加上少录错避免罚款 / 一年许可费 9 个月回本"

---

## ⏱️ 14:30 — 15:00 收尾 CTA

🎤 **关键句**：
- "三大闭环 / AI / 多仓 / 合规 / 都是真实可用"
- "演示站 erp-demo.example.my / admin@demo.my / Admin@123"
- "正式 Proposal / 定制版 / 线下 Demo → demo@erp-os.my / 24h 回复"

🖱️ 切回 Dashboard 留住屏幕

---

## 🆘 救场预案

| 翻车 | 救场 |
|---|---|
| OCR 转圈不出结果 | "网络抖一下，我手工演示给大家看" → 切到手填 PO |
| Precheck 弹窗一直 Loading | "降级模式我也演示一下" → 关 AI 总开关 → 重试看到只跑硬规则 |
| Submit MyInvois 失败 | "Mock LHDN 偶尔抽风，正式环境是稳定的" → 跳过到 invoice 列表 |
| 倒计时没动 | "演示模式时钟独立，我们直接看下一张已 FINAL 的" |
| 浏览器卡死 | F5 刷新（不要慌，10 秒就回来）→ "云端版本我们 SSR 缓存" |
| 演示站连不上 | 切到本地备份机 `http://localhost:3000` → "今天网络环境特殊，本地版一样" |
| 全部炸 | 播 5min 视频兜底（必须提前下载到桌面） |

---

## 🔥 演示后 24 小时

- [ ] 邮件跟进每个观众，附 one-pager PDF + 演示账号
- [ ] 把今天演示踩到的小坑记 `tasks/lessons.md`
- [ ] 重要客户 24h 内约第二次深度 Demo（30min 版）
