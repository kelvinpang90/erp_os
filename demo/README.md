# ERP OS — Demo Material Pack (W20)

客户演示物料一站式仓库。所有产物按媒体类型分目录。

## 目录结构

```
demo/
├── decks/          # 6 份 PPTX (5/15/30 min × EN/ZH) + build.js 源码 + screenshots/
├── pdfs/           # 双语 one-pager + 5 张 OCR sample invoices + _generate.py 源码
├── docs/           # FAQ (EN/ZH) + Proposal Template (EN/ZH) + _build.js 源码
├── videos/         # 录制脚本 + recording guide（mp4 不入库）
├── setlist-15min.md  # 现场 Demo 桌面便签（15 分钟版）
├── setlist-30min.md  # 现场 Demo 桌面便签（30 分钟深度版）
└── README.md       # 本文件
```

## 重新生成

```bash
# PPTX（需 Node 18+）
cd demo/decks && npm install && node build.js

# PDF（需 Python 3 + reportlab）
cd demo/pdfs && python _generate.py

# DOCX（需 Node 18+ + docx 包）
cd demo/docs && node _build.js
```

## 用法速查

| 场景 | 拿哪份 |
|---|---|
| 高管 5 分钟介绍（电梯版） | `decks/erp-os-5min-{en,zh}.pptx` + `pdfs/one-pager-{en,zh}.pdf` |
| 业务负责人深度 Demo（15 分钟） | `decks/erp-os-15min-{en,zh}.pptx` + `setlist-15min.md` |
| IT + 财务联席（30 分钟） | `decks/erp-os-30min-{en,zh}.pptx` + `setlist-30min.md` |
| 客户问"有什么 FAQ" | `docs/FAQ-{en,zh}.docx` |
| 客户要正式报价 | `docs/Proposal-Template-{en,zh}.docx`（替换 `{{占位符}}`） |
| OCR Demo 用样本发票 | `pdfs/sample-invoices/INV-*.pdf`（5 张覆盖不同 SST/币种场景） |
| 录视频 | `videos/script-{5,15}min.md` + `videos/recording-guide.md` |

## 截图补充

`decks/screenshots/` 当前为空。建议演示前用 demo 数据跑 9 张关键截图：

1. Dashboard（KPI + AI 摘要）
2. SKU 列表
3. PO 详情 + OCR 上传
4. SO 详情 + 发货
5. Invoice + Precheck Modal
6. Invoice 提交后 UIN + QR
7. Branch Inventory 热力图
8. Low Stock Alerts
9. Reports 中心

截好后命名 `01-dashboard.png` ... `09-reports.png` 放进 `screenshots/`，PPTX 中的 `[Screenshot: ...]` 占位框对应替换。

## 不入库内容

- `decks/node_modules/`（pptxgenjs 依赖，~500 文件）
- `decks/package-lock.json`
- 录制原片 `videos/recordings/*.mp4`（用 Drive / Vimeo 单独管理）

详见根目录 `.gitignore`。
