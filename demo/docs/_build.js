// Build 4 DOCX files for ERP OS demo
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, TabStopType, TabStopPosition,
  TableOfContents, HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber, PageBreak,
} = require("docx");

const OUT = __dirname;

// ---------- shared helpers ----------
const A4 = { width: 11906, height: 16838 };
const MARGIN = { top: 1440, right: 1440, bottom: 1440, left: 1440 };
const CONTENT_W = A4.width - MARGIN.left - MARGIN.right; // 9026

const border = { style: BorderStyle.SINGLE, size: 6, color: "BFBFBF" };
const cellBorders = { top: border, bottom: border, left: border, right: border };

function makeStyles(font) {
  return {
    default: { document: { run: { font, size: 22 } } }, // 11pt
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 56, bold: true, font, color: "1F3864" },
        paragraph: { spacing: { before: 240, after: 360 }, alignment: AlignmentType.CENTER } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font, color: "1F3864" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font, color: "2E75B6" },
        paragraph: { spacing: { before: 240, after: 140 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 } },
    ],
  };
}

const numbering = {
  config: [
    { reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  ],
};

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120 },
    ...opts,
    children: [new TextRun({ text, ...(opts.run || {}) })],
  });
}
function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] }); }
function h2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] }); }
function h3(text) { return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] }); }
function bullet(text) {
  return new Paragraph({ numbering: { reference: "bullets", level: 0 },
    children: [new TextRun(text)] });
}
function pageBreak() { return new Paragraph({ children: [new PageBreak()] }); }

function cell(text, opts = {}) {
  const runs = Array.isArray(text)
    ? text.map(t => new TextRun(typeof t === "string" ? t : t))
    : [new TextRun({ text: String(text), bold: !!opts.bold })];
  return new TableCell({
    borders: cellBorders,
    width: { size: opts.width, type: WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: runs })],
  });
}

function makeTable(columnWidths, rows, headerFill = "D9E2F3") {
  return new Table({
    width: { size: columnWidths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths,
    rows: rows.map((r, i) => new TableRow({
      children: r.map((txt, j) => cell(txt, {
        width: columnWidths[j],
        bold: i === 0,
        fill: i === 0 ? headerFill : undefined,
      })),
    })),
  });
}

function buildSection(children, font) {
  return {
    properties: { page: { size: A4, margin: MARGIN } },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: "ERP OS", color: "808080", size: 18 })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "Page ", color: "808080", size: 18 }),
          new TextRun({ children: [PageNumber.CURRENT], color: "808080", size: 18 }),
        ],
      })] }),
    },
    children,
  };
}

// ---------- FAQ data ----------
const FAQ_EN = [
  ["A. Data Security & Compliance", [
    ["Where is our data stored, and who can access it?",
     "Your data is hosted on a Malaysia-based VPS with daily encrypted backups. Access is limited to authorised users in your organisation through role-based permissions (Admin, Manager, Sales, Purchaser), and our engineers can only access production data with your written approval for incident response."],
    ["Are you compliant with the latest LHDN MyInvois rules?",
     "Yes. We track LHDN announcements actively and ship updates whenever the specification changes. Our e-Invoice module covers TIN format, MSIC codes, SST classifications, the 72-hour rejection window, Consolidated Invoices, and Credit Notes."],
    ["How fast do you push updates when LHDN changes the rules?",
     "Critical compliance changes are released within 5 working days of an official LHDN announcement. Non-critical clarifications are bundled into our regular monthly release."],
    ["What is your backup and disaster recovery policy?",
     "Daily automated database dumps are retained for 7 days, with weekly snapshots kept for one month. Backups are encrypted and stored separately from the production server. Restore drills are run quarterly."],
  ]],
  ["B. Pricing & Commercials", [
    ["How is pricing calculated? Per user or per company size?",
     "We charge a one-off implementation fee plus an annual subscription based on the number of named users. There are no hidden fees for storage or basic AI usage within the standard quota."],
    ["What is included in the implementation fee?",
     "Implementation covers data migration support, master data setup (SKUs, suppliers, customers), user training (two sessions), and one month of post-launch hyper-care. Customisation outside the standard scope is quoted separately."],
    ["How long does it take to go live?",
     "A standard rollout takes 2 to 4 weeks depending on data readiness and the number of warehouses. We can run a live pilot on a single warehouse within the first week."],
    ["Is there a trial period?",
     "Yes. We offer a 14-day free trial on our cloud demo environment with sample data, and a 30-day money-back window after paid go-live if the system does not meet the agreed acceptance criteria."],
  ]],
  ["C. AI Features", [
    ["How accurate is the AI? Who is responsible if OCR gets it wrong?",
     "Our invoice OCR is around 92 to 95 percent accurate on clear scans. Every AI-extracted field is editable before posting, and a human must confirm the document. The user posting the document remains the system of record."],
    ["Who pays for the AI usage cost?",
     "Each subscription tier includes a generous monthly AI quota that covers normal SME usage. Overage is billed transparently at cost plus a small margin, and you can cap usage at the organisation level."],
    ["Can we turn off AI features if we do not want to use them?",
     "Yes. AI can be disabled at three layers: globally (system), at the organisation level (master switch), or per individual feature (OCR, e-Invoice precheck, dashboard summary). All workflows have a non-AI fallback."],
    ["Will you use our data to train AI models?",
     "No. We do not use customer data to train models. We call the Anthropic Claude API with zero-retention enterprise terms, and prompts are scrubbed of unnecessary identifiers before transmission."],
  ]],
  ["D. Integration & Migration", [
    ["Can we migrate from our existing system, such as SQL Account or AutoCount?",
     "Yes. We provide CSV and Excel import templates for masters (SKU, supplier, customer, opening balance) and offer paid migration support for transactional history if required. A typical migration takes 3 to 7 working days."],
    ["Do you offer a public API?",
     "Yes. Every backend endpoint is published as an OpenAPI specification and a typed TypeScript client is generated automatically. API keys are issued per integration with scoped permissions."],
    ["Can you integrate with e-commerce platforms like Shopee or Lazada?",
     "Direct connectors are on our roadmap. Today we support order import via CSV and offer a webhook endpoint that integration partners can use. We can scope a custom connector as a paid add-on."],
  ]],
  ["E. Support & After-Sales", [
    ["What is your support response time commitment?",
     "Standard support responds within one business day. Priority support, included in the Business tier, responds within 4 working hours during business days for severity 1 and 2 issues."],
    ["What happens if the system goes down? What is your SLA?",
     "Our cloud SLA is 99.5 percent monthly uptime, with service credits if we miss it. We monitor uptime with UptimeRobot and run health checks on every container, and we publish a public status page."],
    ["Can the system be deployed on-premises rather than on the cloud?",
     "Yes. Because the entire stack ships as docker-compose, we can deploy on a customer-owned server. On-premise deployments are quoted separately and require an annual maintenance contract."],
  ]],
];

const FAQ_ZH = [
  ["A. 数据安全与合规", [
    ["我们的数据存在哪里？谁能访问？",
     "您的数据存放在马来西亚本地的 VPS 服务器上,每天自动加密备份。访问权限由组织内的角色控制（Admin / Manager / Sales / Purchaser）,只有授权用户能进。我们工程师没有书面授权不会碰生产数据,只在出问题需要排查时才会临时介入。"],
    ["你们符合 LHDN MyInvois 最新规范吗？",
     "符合。我们持续追踪 LHDN 的公告,规范一变就跟着更新。e-Invoice 模块覆盖 TIN 格式、MSIC 行业码、SST 税率分类、72 小时反对期、Consolidated Invoice、Credit Note 全流程。"],
    ["LHDN 规则改了你们多快能跟上？",
     "影响合规的关键变更,我们承诺在 LHDN 正式公告后 5 个工作日内发版上线。非关键的细节澄清,会合并到每月的常规版本里。"],
    ["数据备份和灾难恢复怎么做？",
     "每天自动 dump 数据库并加密存储,保留 7 天,每周再做一次快照保留一个月。备份和生产服务器物理隔离,我们每季度做一次恢复演练,确保真出事能拉回来。"],
  ]],
  ["B. 价格与商务", [
    ["价格怎么算？按用户数还是按公司规模？",
     "我们按一次性实施费 + 每年订阅费收。订阅费按命名用户数算,标准 AI 用量额度内不另收钱,存储也不限量。"],
    ["实施费包含什么？",
     "包含数据迁移协助、主数据建档（SKU、供应商、客户）、两场用户培训、上线后一个月的密切跟进。超出标准范围的定制开发会另外报价,不会糊里糊涂收钱。"],
    ["上线要多久？",
     "标准上线周期 2 到 4 周,看您数据准备情况和仓库数量。我们可以第一周就在一个仓库先跑试点,让您边用边调。"],
    ["有试用期吗？",
     "有。云端 Demo 站点提供 14 天免费试用,带样例数据可以随便点。正式付费上线后,30 天内若达不到验收标准可以无条件退款。"],
  ]],
  ["C. AI 功能", [
    ["AI 准确率如何？OCR 出错谁负责？",
     "我们的发票 OCR 在清晰扫描件上准确率约 92% 到 95%。每个 AI 抽出来的字段都可以人工改,过账前必须由用户确认。最终发起单据的用户对内容负责,AI 是助手不是替代。"],
    ["AI 调用的成本谁出？",
     "每个套餐都包含每月的 AI 用量额度,正常做生意肯定够用。超出部分按成本价加少量利润透明计费,您也可以在组织层面设上限,避免某天用爆。"],
    ["不想用 AI 能关掉吗？",
     "可以。AI 有三层开关：系统级、组织级总闸、单个功能级（OCR、e-Invoice 预校验、Dashboard 日报）。每个 AI 功能都有不用 AI 的降级路径,关掉一样能做生意。"],
    ["你们会用我们的数据训练 AI 模型吗？",
     "不会。我们不用客户数据做模型训练。底层调用 Anthropic Claude API 走的是企业零留存条款,prompt 在传输前会去掉不必要的身份信息。"],
  ]],
  ["D. 集成与迁移", [
    ["能从现有系统（SQL Account、AutoCount）迁过来吗？",
     "可以。我们提供 CSV / Excel 导入模板,主数据（SKU、供应商、客户、期初库存）自助导入。历史交易数据如果要迁,可以付费协助,通常 3 到 7 个工作日搞定。"],
    ["有开放 API 吗？",
     "有。所有后端接口都按 OpenAPI 规范发布,前端 TypeScript 客户端自动生成。API key 按集成对象单独发放,可以设权限范围,不会一把钥匙开所有门。"],
    ["能跟 Shopee、Lazada 这些电商平台对接吗？",
     "直连对接在我们路线图里。目前支持 CSV 订单导入和 webhook 回调,集成伙伴可以用。如果您需要定制连接器,我们可以按项目报价做。"],
  ]],
  ["E. 售后与支持", [
    ["售后响应时间承诺是什么？",
     "标准支持承诺 1 个工作日内响应。Business 套餐含的优先支持,工作日内 4 小时响应严重等级 1、2 的问题,不让您干等。"],
    ["系统宕机怎么办？SLA 多少？",
     "云端 SLA 是每月 99.5% 可用率,达不到我们退服务费抵扣。我们用 UptimeRobot 监控,每个容器都跑健康检查,有公开的状态页可以查。"],
    ["能私有化部署吗（不上云）？",
     "可以。整套系统用 docker-compose 一键起,完全可以部署在您自己的服务器上。私有化部署单独报价,需要签年度维护合同保证持续支持。"],
  ]],
];

// ---------- FAQ builder ----------
function buildFAQ(title, intro, sections, font) {
  const children = [
    new Paragraph({ style: "Title", children: [new TextRun(title)] }),
    p(intro),
    pageBreak(),
  ];
  let qNum = 0;
  for (const [secTitle, qa] of sections) {
    children.push(h1(secTitle));
    for (const [q, a] of qa) {
      qNum++;
      children.push(h3(`Q${qNum}. ${q}`));
      children.push(p(a));
    }
  }
  return new Document({
    styles: makeStyles(font),
    numbering,
    sections: [buildSection(children, font)],
  });
}

// ---------- Proposal builder ----------
function buildProposal(lang, font) {
  const T = lang === "en" ? {
    coverTitle: "Proposal for ERP OS Implementation",
    preparedFor: "Prepared for: {{CUSTOMER_NAME}}",
    preparedBy: "Prepared by: ERP OS Team",
    date: "Date: {{PROPOSAL_DATE}}",
    logo: "[ COMPANY LOGO ]",
    toc: "Table of Contents",
    h: {
      exec: "1. Executive Summary",
      bg: "2. Customer Background",
      challenges: "3. Understanding Your Challenges",
      solution: "4. Our Solution",
      plan: "5. Implementation Plan",
      pricing: "6. Pricing & Commercials",
      sla: "7. SLA & Support",
      team: "8. Our Team",
      appendix: "9. Appendix: Reference Cases",
    },
    execBody: "ERP OS is a Malaysia-focused ERP platform built around three deeply-integrated business loops (e-Invoice, Purchasing, Sales) and three production-grade AI features (invoice OCR, e-Invoice precheck, dashboard summary). This proposal outlines how we will implement ERP OS for {{CUSTOMER_NAME}} within {{TIMELINE}}, supporting {{NUM_USERS}} users across your operations.",
    bgRows: [
      ["Field", "Detail"],
      ["Customer Name", "{{CUSTOMER_NAME}}"],
      ["Industry", "{{CUSTOMER_INDUSTRY}}"],
      ["Company Size", "{{CUSTOMER_SIZE}}"],
      ["Number of Warehouses", "{{NUM_WAREHOUSES}}"],
      ["Number of Users", "{{NUM_USERS}}"],
      ["Primary Contact", "{{CONTACT_NAME}} ({{CONTACT_EMAIL}})"],
    ],
    challenges: [
      "Pain Point 1: {{PAIN_POINT_1}} — manual invoice processing consumes significant staff time and introduces data entry errors.",
      "Pain Point 2: {{PAIN_POINT_2}} — fragmented stock visibility across multiple warehouses leads to stock-outs and over-ordering.",
      "Pain Point 3: {{PAIN_POINT_3}} — LHDN e-Invoice compliance is an unbudgeted operational burden without automation.",
    ],
    solIntro: "We address these challenges through three integrated business loops, each enhanced with optional AI:",
    loops: [
      ["Loop", "Coverage", "AI Enhancement"],
      ["e-Invoice", "Submission, validation, UIN, 72h rejection window, Consolidated Invoice, Credit Note", "AI precheck before submission"],
      ["Purchasing", "Supplier, PO, goods receipt, multi-currency settlement", "OCR-based invoice capture"],
      ["Sales", "Customer, SO, delivery order, e-Invoice generation, payment, returns", "Auto e-Invoice draft"],
    ],
    planIntro: "We deliver in four weekly milestones:",
    planRows: [
      ["Week", "Milestone", "Deliverable"],
      ["Week 1", "Setup & Master Data", "Environment provisioned, masters imported, 4 user roles configured"],
      ["Week 2", "Pilot Warehouse Go-Live", "One warehouse live, daily PO and SO transactions running"],
      ["Week 3", "Full Rollout & e-Invoice", "All warehouses live, e-Invoice submission to LHDN active"],
      ["Week 4", "Training & Hyper-Care", "Two training sessions, hyper-care monitoring, sign-off"],
    ],
    pricingIntro: "Pricing summary (all amounts in MYR, exclusive of SST):",
    pricingRows: [
      ["Item", "Amount"],
      ["Implementation Fee (one-off)", "{{IMPL_FEE}}"],
      ["Annual Subscription ({{NUM_USERS}} users)", "{{ANNUAL_FEE}}"],
      ["Optional: On-premise deployment", "{{ONPREM_FEE}}"],
      ["Optional: Custom integration ({{INTEGRATION_NAME}})", "{{INTEGRATION_FEE}}"],
      ["Total Year 1", "{{TOTAL_Y1}}"],
    ],
    slaBullets: [
      "Standard support response: 1 business day",
      "Priority support response (Business tier): 4 business hours",
      "Cloud uptime SLA: 99.5% monthly, with service credits",
      "Critical LHDN compliance updates: shipped within 5 working days",
      "Daily encrypted backups, 7-day rolling retention",
    ],
    teamBody: "Our team combines local Malaysian ERP domain experts with senior engineers experienced in AI engineering, security, and high-availability systems. The named project lead for {{CUSTOMER_NAME}} is {{PROJECT_LEAD}}.",
    appendixBody: "Reference Case 1: {{REFERENCE_CASE_1}}\nReference Case 2: {{REFERENCE_CASE_2}}\nReference Case 3: {{REFERENCE_CASE_3}}",
  } : {
    coverTitle: "ERP OS 实施方案建议书",
    preparedFor: "致：{{CUSTOMER_NAME}}",
    preparedBy: "提交方：ERP OS 团队",
    date: "日期：{{PROPOSAL_DATE}}",
    logo: "[ 公司 LOGO ]",
    toc: "目录",
    h: {
      exec: "1. 方案摘要",
      bg: "2. 客户背景",
      challenges: "3. 我们对您挑战的理解",
      solution: "4. 解决方案",
      plan: "5. 实施计划",
      pricing: "6. 价格与商务",
      sla: "7. SLA 与支持",
      team: "8. 团队介绍",
      appendix: "9. 附录：参考案例",
    },
    execBody: "ERP OS 是一套面向马来西亚本土的 ERP 系统,围绕三条深度闭环（e-Invoice、采购、销售）和三个生产级 AI 功能（发票 OCR、e-Invoice 预校验、Dashboard 日报）打造。本建议书说明我们将如何在 {{TIMELINE}} 内为 {{CUSTOMER_NAME}} 完成实施,支持 {{NUM_USERS}} 个用户的日常使用。",
    bgRows: [
      ["项目", "内容"],
      ["客户名称", "{{CUSTOMER_NAME}}"],
      ["所属行业", "{{CUSTOMER_INDUSTRY}}"],
      ["公司规模", "{{CUSTOMER_SIZE}}"],
      ["仓库数量", "{{NUM_WAREHOUSES}}"],
      ["用户数量", "{{NUM_USERS}}"],
      ["主要联系人", "{{CONTACT_NAME}}（{{CONTACT_EMAIL}}）"],
    ],
    challenges: [
      "痛点 1：{{PAIN_POINT_1}} —— 手工录入发票占用大量人手,容易出错。",
      "痛点 2：{{PAIN_POINT_2}} —— 多仓库存信息不通,经常缺货或重复采购。",
      "痛点 3：{{PAIN_POINT_3}} —— LHDN e-Invoice 合规如果没有自动化,会成为长期的运营负担。",
    ],
    solIntro: "我们通过三条业务闭环加可选 AI 来解决这些问题：",
    loops: [
      ["闭环", "覆盖范围", "AI 增强"],
      ["e-Invoice", "提交、校验、UIN、72 小时反对期、Consolidated、Credit Note", "提交前 AI 预校验"],
      ["采购", "供应商、PO、收货、多币种结算", "OCR 发票录入"],
      ["销售", "客户、SO、出库、e-Invoice 生成、回款、退货", "自动生成 e-Invoice 草稿"],
    ],
    planIntro: "实施按 4 周里程碑交付：",
    planRows: [
      ["周次", "里程碑", "交付物"],
      ["第 1 周", "环境与主数据", "环境部署完成、主数据导入、4 个角色配置完成"],
      ["第 2 周", "试点仓库上线", "首个仓库上线,日常 PO、SO 业务跑通"],
      ["第 3 周", "全量上线 + e-Invoice", "所有仓库上线,e-Invoice 对接 LHDN 正式提交"],
      ["第 4 周", "培训与密切跟进", "两场用户培训、上线后跟进、客户验收签字"],
    ],
    pricingIntro: "价格说明（金额单位 MYR,未含 SST）：",
    pricingRows: [
      ["项目", "金额"],
      ["实施费（一次性）", "{{IMPL_FEE}}"],
      ["年度订阅费（{{NUM_USERS}} 用户）", "{{ANNUAL_FEE}}"],
      ["可选：私有化部署", "{{ONPREM_FEE}}"],
      ["可选：定制集成（{{INTEGRATION_NAME}}）", "{{INTEGRATION_FEE}}"],
      ["第一年合计", "{{TOTAL_Y1}}"],
    ],
    slaBullets: [
      "标准支持响应：1 个工作日内",
      "优先支持响应（Business 套餐）：4 个工作小时内",
      "云端可用率 SLA：每月 99.5%,未达到退服务费抵扣",
      "LHDN 关键合规更新：5 个工作日内发版",
      "每日加密备份,滚动保留 7 天",
    ],
    teamBody: "团队由熟悉马来本地 ERP 业务的领域专家,加上有 AI 工程、安全、高可用经验的资深工程师组成。本项目为 {{CUSTOMER_NAME}} 指定的项目负责人是 {{PROJECT_LEAD}}。",
    appendixBody: "参考案例 1：{{REFERENCE_CASE_1}}\n参考案例 2：{{REFERENCE_CASE_2}}\n参考案例 3：{{REFERENCE_CASE_3}}",
  };

  // Cover page
  const cover = [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 2400, after: 600 },
      children: [new TextRun({ text: T.logo, color: "808080", size: 28 })] }),
    new Paragraph({ style: "Title", children: [new TextRun(T.coverTitle)] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 600, after: 200 },
      children: [new TextRun({ text: T.preparedFor, bold: true, size: 28 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: T.preparedBy, size: 24 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: T.date, size: 24 })] }),
    pageBreak(),
  ];

  // TOC
  const toc = [
    new Paragraph({ style: "Title", children: [new TextRun(T.toc)] }),
    new TableOfContents(T.toc, { hyperlink: true, headingStyleRange: "1-3" }),
    pageBreak(),
  ];

  const body = [];
  // 1 Executive Summary
  body.push(h1(T.h.exec));
  body.push(p(T.execBody));

  // 2 Background
  body.push(h1(T.h.bg));
  body.push(makeTable([2400, 6626], T.bgRows));

  // 3 Challenges
  body.push(h1(T.h.challenges));
  for (const c of T.challenges) body.push(bullet(c));

  // 4 Solution
  body.push(h1(T.h.solution));
  body.push(p(T.solIntro));
  body.push(makeTable([1800, 5226, 2000], T.loops));

  // 5 Plan
  body.push(h1(T.h.plan));
  body.push(p(T.planIntro));
  body.push(makeTable([1500, 2800, 4726], T.planRows));

  // 6 Pricing
  body.push(h1(T.h.pricing));
  body.push(p(T.pricingIntro));
  body.push(makeTable([5526, 3500], T.pricingRows));

  // 7 SLA
  body.push(h1(T.h.sla));
  for (const s of T.slaBullets) body.push(bullet(s));

  // 8 Team
  body.push(h1(T.h.team));
  body.push(p(T.teamBody));

  // 9 Appendix
  body.push(h1(T.h.appendix));
  for (const line of T.appendixBody.split("\n")) body.push(p(line));

  return new Document({
    styles: makeStyles(font),
    numbering,
    features: { updateFields: true },
    sections: [buildSection([...cover, ...toc, ...body], font)],
  });
}

// ---------- run ----------
async function write(doc, name) {
  const buf = await Packer.toBuffer(doc);
  const fp = path.join(OUT, name);
  fs.writeFileSync(fp, buf);
  console.log("wrote", fp, buf.length, "bytes");
}

(async () => {
  await write(
    buildFAQ(
      "ERP OS — Frequently Asked Questions",
      "This document answers the questions we hear most often from prospective customers. If you have a question that is not covered here, please reach out to our team.",
      FAQ_EN, "Calibri"),
    "FAQ-en.docx");

  await write(
    buildFAQ(
      "ERP OS 常见问题解答",
      "本文档汇总了潜在客户最常问的问题。如果您的问题没有在这里找到答案,欢迎随时联系我们的团队。",
      FAQ_ZH, "Microsoft YaHei"),
    "FAQ-zh.docx");

  await write(buildProposal("en", "Calibri"), "Proposal-Template-en.docx");
  await write(buildProposal("zh", "Microsoft YaHei"), "Proposal-Template-zh.docx");
})().catch(e => { console.error(e); process.exit(1); });
