# 5 分钟版演示视频脚本

> 受众：高管 / 老板首次接触。目标：5 分钟内让观众理解"这个系统能解决什么问题"+ 想看 Demo。
> 语速：约 150 字/分钟（中文）/ 130 wpm（英文）。每段 30 秒，共 10 段。

---

## 录制前清单

- [ ] 浏览器 zoom 100%，分辨率 1920×1080
- [ ] 关闭所有桌面通知（Slack / WeChat / 邮件）
- [ ] Demo 数据已 reset（昨晚 03:00 KL 自动跑过 / 或手动 `/admin/demo-reset`）
- [ ] 用 admin@demo.my 登录，停在 Dashboard 页
- [ ] 准备好 1 张 OCR sample invoice（建议 `INV-TanChongTrading.pdf`）
- [ ] OBS 录制：1080p / 30fps / 音频码率 192kbps

---

## 0:00 — 0:30 开场 + 钩子

**画面**：产品 logo 全屏 → 切换到 Dashboard 全景

**话术（中文）**：
> 大家好。如果你正在马来西亚做生意，2025 年起 LHDN 强制 e-Invoice。这意味着你每开一张发票，都要 30 秒内通过 MyInvois 验证。手工录入慢、出错就被罚款。今天给大家看一套专门为马来本地中小企业设计的 ERP 系统——ERP OS。

**话术（English）**：
> Hi everyone. If you're running a business in Malaysia, LHDN's e-Invoice mandate is now in full force. Every invoice must be validated through MyInvois within seconds. Manual entry is slow, and mistakes mean penalties. Today I'll show you an ERP system built specifically for Malaysian SMEs — ERP OS.

**镜头**：Dashboard KPI 卡片 / AI 日报摘要

---

## 0:30 — 1:00 痛点

**画面**：分屏对比 —— 左边手工 Excel + 一堆纸质发票，右边 ERP OS Dashboard

**话术**：
> 传统做法：Excel 算账、手工开发票、库存账实不符、月底对账加班到凌晨。我们见过太多老板因为这三件事掉头发：一是 e-Invoice 怎么交？交错怎么办？二是几个仓库的库存到底有多少？三是 OCR 录入太慢，一天录 50 张供应商发票，会计两个人都跟不上。

**镜头**：在 Dashboard 上 hover 到"待验证发票" / "低库存预警" KPI

---

## 1:00 — 1:30 亮点 1：OCR 录入

**画面**：切换到 Purchase Orders → 点 "OCR Upload"

**话术**：
> 第一个亮点：AI OCR。看，我把刚收到的供应商发票拖进来。

**操作**：
1. 拖入 `INV-TanChongTrading.pdf`
2. SSE 进度条跑（20 → 50 → 80 → 100%）
3. 表单自动填充：supplier / 3 个 line items / SST / total

**话术**：
> 5 秒钟，整张 PO 自动填好。原来要会计录 10 分钟的活，现在按一下确认就行。

---

## 1:30 — 2:00 亮点 2：e-Invoice 智能预校验

**画面**：切换到 Sales Orders → 找一张 CONFIRMED 的 SO → 点 "Generate Invoice"

**话术**：
> 第二个亮点：e-Invoice 预校验。这张销售单已经发货了，我点生成发票。

**操作**：
1. 点 "Generate Invoice" → 跳到发票草稿
2. 点 "Submit to MyInvois" 之前先点 "AI Precheck"
3. PrecheckModal 弹窗显示 10 项检查（绿对勾 + 红警告）

**话术**：
> 提交 LHDN 之前，AI 帮你跑 10 项规则检查：TIN 格式、SST 配比、邮编对应州——任何一项错都会被拒。AI 一次性帮你看完，比人眼快 50 倍。

---

## 2:00 — 2:30 e-Invoice 提交 + UIN

**画面**：在 PrecheckModal 点 "Submit Anyway"

**操作**：
1. Submit → 立即返回 UIN + QR code
2. 状态从 SUBMITTED → VALIDATED
3. 滑到底部展示 72h 倒计时（DEMO_MODE 下是 72 秒）

**话术**：
> 提交后立即拿到 UIN 和 QR 码。LHDN 给买家 72 小时反对期——演示模式下我们调成 72 秒，方便大家看完整流程。72 秒后自动 FINAL，整个 e-Invoice 闭环搞定。

---

## 2:30 — 3:00 亮点 3：多仓 6 维库存

**画面**：切换到 Branch Inventory 热力图

**话术**：
> 第三个亮点：多仓库存。三个仓库——KL 主仓 / 槟城 / 新山——每个 SKU 在每个仓库都有 6 个状态：实物在库、已锁定、质检冻结、可用、在途采购、调拨在途。

**操作**：
1. Hover 一个 SKU，弹出 6 维详情
2. 点 "Low Stock Alerts" → 看到一批红色预警
3. 点"批量生成补货 PO" → 跳到 PO 草稿（自动预填）

**话术**：
> 系统自动算出哪些 SKU 低于安全库存，一键生成补货采购单。老板再也不用问会计"我们还有多少货"。

---

## 3:00 — 3:30 AI 日报 + Reports

**画面**：回到 Dashboard，展开 AI Summary 卡片

**话术**：
> 每天早上 Dashboard 自动生成 AI 日报：昨天卖了多少钱、哪个 SKU 卖最好、哪些发票还没结、库存有没有异常——一段话讲清楚。

**操作**：跳到 Reports 中心，秀 10 张图表

> 想深挖数据，Reports 中心有 10 张专业图表：销售趋势、Top SKU、客户贡献度、库存周转、e-Invoice 状态分布……都是开箱即用。

---

## 3:30 — 4:00 多角色 + 权限

**画面**：右上角切换角色 → Sales

**话术**：
> 系统内置 4 个角色：Admin / Manager / Sales / Purchaser。销售员看不到成本价、采购员看不到客户清单——权限分得清清楚楚。

**操作**：切换到 Sales 角色 → 菜单变窄，只剩销售相关 → 切回 Admin

---

## 4:00 — 4:30 部署 + 价格

**画面**：切到 IDE / 终端，展示 `docker compose up -d`

**话术**：
> 部署很简单：一行 docker compose up，半小时上线。可以放云上、也可以放你自己机房。中英双语、深浅主题、随时切换。
>
> 价格按公司规模——5 个人到 500 个人都覆盖，比 SAP Business One 便宜一个量级。详细方案见我们的 Proposal。

---

## 4:30 — 5:00 收尾 CTA

**画面**：回到产品 logo 页 + 联系方式

**话术**：
> 总结一下：e-Invoice 全流程合规、AI 自动化、多仓库存、马来本地化。如果你正头疼 LHDN 合规或者想升级 ERP，扫码或者发邮件到 demo@erp-os.my，我们 24 小时内回。
>
> 谢谢观看。

**画面叠加**：
- 演示站点：`https://erp-demo.example.my`
- 邮箱：`demo@erp-os.my`
- 演示账号：`admin@demo.my / Admin@123`

---

## 后期剪辑要点

- 0:00 / 1:00 / 2:00 / 3:00 / 4:00 加章节标记
- OCR / Precheck / Inventory 的关键操作放慢 2x（让观众看清）
- 数字（"5 秒"/"72 秒"/"50 倍"）出现时叠加 lower-third 字幕
- 背景音乐：轻商务风，音量 -20dB
- 片尾 5 秒 logo + CTA hold
