"""Generate one-pagers (EN/ZH) and 5 sample invoices for ERP OS demo."""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent
INV_DIR = OUT / "sample-invoices"
INV_DIR.mkdir(parents=True, exist_ok=True)

# Register CJK font for the Chinese one-pager
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

PRIMARY = colors.HexColor("#1677ff")
DARK = colors.HexColor("#262626")
BG = colors.HexColor("#f5f5f5")
LIGHT_BORDER = colors.HexColor("#d9d9d9")


# ---------------------------------------------------------------------------
# One-pager helpers
# ---------------------------------------------------------------------------
def draw_one_pager(path: Path, *, lang: str) -> None:
    """Draw a single-page A4 landscape one-pager."""
    page = landscape(A4)  # 842 x 595
    W, H = page
    c = canvas.Canvas(str(path), pagesize=page)

    if lang == "zh":
        body_font = "STSong-Light"
        bold_font = "STSong-Light"
    else:
        body_font = "Helvetica"
        bold_font = "Helvetica-Bold"

    # Background
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Left visual area (mock product screenshot)
    left_w = W * 0.5
    margin = 20
    c.setFillColor(colors.white)
    c.rect(margin, margin, left_w - margin * 1.5, H - margin * 2, fill=1, stroke=0)

    # Mock browser top bar
    c.setFillColor(PRIMARY)
    c.rect(margin, H - margin - 30, left_w - margin * 1.5, 30, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(bold_font, 12)
    c.drawString(margin + 14, H - margin - 20, "ERP OS  |  Dashboard")

    # Mock sidebar
    sidebar_x = margin
    sidebar_y = margin
    sidebar_h = H - margin * 2 - 30
    c.setFillColor(colors.HexColor("#001529"))
    c.rect(sidebar_x, sidebar_y, 90, sidebar_h, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(body_font, 8)
    if lang == "zh":
        menu_items = ["仪表盘", "采购", "销售", "库存", "电子发票", "报表", "设置"]
    else:
        menu_items = ["Dashboard", "Purchase", "Sales", "Inventory", "e-Invoice", "Reports", "Settings"]
    for i, item in enumerate(menu_items):
        c.drawString(sidebar_x + 10, H - margin - 50 - i * 22, item)

    # Mock KPI cards
    card_x0 = sidebar_x + 100
    card_y0 = H - margin - 80
    card_w = (left_w - margin * 1.5 - 110) / 3 - 8
    card_h = 60
    if lang == "zh":
        kpis = [("今日销售", "RM 24,580"), ("待发货 SO", "12"), ("低库存 SKU", "8")]
    else:
        kpis = [("Today's Sales", "RM 24,580"), ("Pending SO", "12"), ("Low Stock", "8")]
    for i, (label, value) in enumerate(kpis):
        x = card_x0 + i * (card_w + 8)
        c.setFillColor(colors.HexColor("#fafafa"))
        c.setStrokeColor(LIGHT_BORDER)
        c.rect(x, card_y0 - card_h, card_w, card_h, fill=1, stroke=1)
        c.setFillColor(DARK)
        c.setFont(body_font, 8)
        c.drawString(x + 8, card_y0 - 18, label)
        c.setFillColor(PRIMARY)
        c.setFont(bold_font, 14)
        c.drawString(x + 8, card_y0 - 40, value)

    # Mock chart area
    chart_y = margin + 100
    chart_h = card_y0 - card_h - chart_y - 12
    chart_x = card_x0
    chart_w = left_w - margin * 1.5 - 110
    c.setFillColor(colors.HexColor("#fafafa"))
    c.setStrokeColor(LIGHT_BORDER)
    c.rect(chart_x, chart_y, chart_w, chart_h, fill=1, stroke=1)
    c.setFillColor(DARK)
    c.setFont(bold_font, 9)
    title = "营业趋势 / 30 天" if lang == "zh" else "Revenue Trend / 30 days"
    c.drawString(chart_x + 8, chart_y + chart_h - 14, title)
    # bars
    bar_count = 14
    bar_w = (chart_w - 24) / bar_count - 4
    import random
    random.seed(7)
    for i in range(bar_count):
        bh = 20 + random.random() * (chart_h - 50)
        bx = chart_x + 12 + i * (bar_w + 4)
        c.setFillColor(PRIMARY)
        c.rect(bx, chart_y + 10, bar_w, bh, fill=1, stroke=0)

    # Mock table area below chart
    tbl_y = margin
    tbl_h = chart_y - tbl_y - 8
    c.setFillColor(colors.HexColor("#fafafa"))
    c.setStrokeColor(LIGHT_BORDER)
    c.rect(chart_x, tbl_y, chart_w, tbl_h, fill=1, stroke=1)
    c.setFillColor(DARK)
    c.setFont(bold_font, 9)
    tbl_title = "最近订单" if lang == "zh" else "Recent Orders"
    c.drawString(chart_x + 8, tbl_y + tbl_h - 14, tbl_title)
    c.setFont(body_font, 7)
    rows = ["SO-2026-00198", "SO-2026-00197", "PO-2026-00041", "INV-2026-00132"]
    for i, r in enumerate(rows):
        c.drawString(chart_x + 8, tbl_y + tbl_h - 30 - i * 12, r)
        c.drawRightString(chart_x + chart_w - 8, tbl_y + tbl_h - 30 - i * 12, "RM 1,250.00")

    # ----- Right text area -----
    rx = left_w + 10
    rw = W - rx - margin

    # Product name (top-right)
    c.setFillColor(PRIMARY)
    c.setFont(bold_font, 20)
    if lang == "zh":
        c.drawString(rx, H - margin - 22, "ERP OS — 为马来西亚中小企业定制")
    else:
        c.drawString(rx, H - margin - 22, "ERP OS - Built for Malaysia SMEs")

    # Subtitle / tagline
    c.setFillColor(DARK)
    c.setFont(body_font, 11)
    if lang == "zh":
        tagline = "三大业务闭环 + AI 智能化 + 本地合规  一站搞定"
    else:
        tagline = "Three core flows + AI automation + Local compliance, all-in-one"
    c.drawString(rx, H - margin - 42, tagline)

    # Divider
    c.setStrokeColor(PRIMARY)
    c.setLineWidth(2)
    c.line(rx, H - margin - 52, rx + 80, H - margin - 52)

    # Section header: KEY FEATURES
    c.setFillColor(DARK)
    c.setFont(bold_font, 13)
    header = "三大核心卖点" if lang == "zh" else "Why ERP OS"
    c.drawString(rx, H - margin - 80, header)

    # Three selling points
    if lang == "zh":
        points = [
            ("[*]", "e-Invoice / MyInvois 全流程合规",
             "提交 / 验证 / UIN 回填 / 72h 反对期 / Consolidated / Credit Note  全覆盖。"),
            ("[AI]", "三大 AI 自动化能力",
             "PO 发票 OCR 录入 / e-Invoice 智能预校验 / Dashboard 日报摘要,  全部含降级路径。"),
            ("[#]", "多仓 6 维库存 + 加权平均成本",
             "On-hand / Reserved / QC / Available / Incoming / In-transit;  实时调拨 + 安全库存预警。"),
        ]
    else:
        points = [
            ("[*]", "End-to-end MyInvois e-Invoice Compliance",
             "Submit / Validate / UIN sync / 72h rejection / Consolidated / Credit Note  fully covered."),
            ("[AI]", "Three AI Automation Capabilities",
             "PO invoice OCR ingestion / e-Invoice smart precheck / Dashboard daily digest,  all with graceful fallbacks."),
            ("[#]", "6-Dimension Multi-Warehouse Stock + WAC",
             "On-hand / Reserved / QC / Available / Incoming / In-transit;  real-time transfer + safety-stock alerts."),
        ]
    py = H - margin - 105
    for icon, title, desc in points:
        c.setFillColor(PRIMARY)
        c.setFont(bold_font, 12)
        c.drawString(rx, py, icon)
        c.setFillColor(DARK)
        c.setFont(bold_font, 11)
        c.drawString(rx + 32, py, title)
        c.setFont(body_font, 9)
        c.setFillColor(colors.HexColor("#595959"))
        # wrap desc to 2 lines if necessary - simple split
        c.drawString(rx + 32, py - 14, desc)
        py -= 50

    # Tech stack / proof points
    c.setFillColor(DARK)
    c.setFont(bold_font, 11)
    th = "技术栈" if lang == "zh" else "Tech Stack"
    c.drawString(rx, py - 6, th)
    c.setFont(body_font, 9)
    c.setFillColor(colors.HexColor("#595959"))
    stack = "FastAPI 0.115  -  React 18 + Ant Design Pro  -  MySQL 8  -  Redis 7  -  Celery  -  Docker"
    c.drawString(rx, py - 22, stack)

    # Bottom contact
    c.setStrokeColor(LIGHT_BORDER)
    c.setLineWidth(0.5)
    c.line(rx, margin + 40, W - margin, margin + 40)
    c.setFillColor(DARK)
    c.setFont(bold_font, 10)
    contact_lbl = "联系我们" if lang == "zh" else "Get in touch"
    c.drawString(rx, margin + 22, contact_lbl)
    c.setFont(body_font, 9)
    c.setFillColor(PRIMARY)
    c.drawString(rx + 80, margin + 22, "demo@erp-os.my")
    c.drawString(rx + 220, margin + 22, "https://erp-demo.example.my")

    c.setFillColor(colors.HexColor("#8c8c8c"))
    c.setFont(body_font, 7)
    foot = "(C) 2026 ERP OS  |  Demo build" if lang == "en" else "(C) 2026 ERP OS  |  演示版本"
    c.drawString(rx, margin + 6, foot)

    c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Invoice generator
# ---------------------------------------------------------------------------
def draw_invoice(
    path: Path,
    *,
    supplier_name: str,
    supplier_addr: str,
    supplier_tin: str,
    supplier_tel: str,
    invoice_no: str,
    invoice_date: str,
    due_date: str,
    line_items: list[tuple[str, float, str, float, str]],  # desc, qty, uom, unit_price, sst%
    currency: str = "MYR",
    exchange_rate: float | None = None,
    notes: str = "",
) -> None:
    """Draw a clean A4 portrait invoice optimized for OCR."""
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    margin = 18 * mm

    # Supplier header (top)
    y = H - margin
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y - 14, supplier_name)
    c.setFont("Helvetica", 10)
    c.drawString(margin, y - 30, supplier_addr)
    c.drawString(margin, y - 44, f"TIN: {supplier_tin}    Tel: {supplier_tel}")

    # Horizontal rule
    c.setStrokeColor(DARK)
    c.setLineWidth(1)
    c.line(margin, y - 54, W - margin, y - 54)

    # INVOICE title block
    title_y = y - 80
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, title_y, "INVOICE")

    # Invoice meta (right)
    meta_x = W - margin - 75 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(meta_x, title_y, "Invoice No:")
    c.drawString(meta_x, title_y - 14, "Invoice Date:")
    c.drawString(meta_x, title_y - 28, "Due Date:")
    if currency != "MYR":
        c.drawString(meta_x, title_y - 42, "Currency:")
    c.setFont("Helvetica", 10)
    c.drawString(meta_x + 28 * mm, title_y, invoice_no)
    c.drawString(meta_x + 28 * mm, title_y - 14, invoice_date)
    c.drawString(meta_x + 28 * mm, title_y - 28, due_date)
    if currency != "MYR":
        c.drawString(meta_x + 28 * mm, title_y - 42, currency)

    # Bill To
    bt_y = title_y - 60
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, bt_y, "Bill To:")
    c.setFont("Helvetica", 10)
    c.drawString(margin, bt_y - 14, "Demo Malaysia Sdn Bhd")
    c.drawString(margin, bt_y - 28, "1, Jalan Demo, 50000 Kuala Lumpur")
    c.drawString(margin, bt_y - 42, "TIN: C00000000001")

    # Items table
    table_y = bt_y - 70
    cols = [
        ("No",     12 * mm),
        ("Description", 70 * mm),
        ("Qty",    16 * mm),
        ("UOM",    16 * mm),
        ("Unit Price", 26 * mm),
        ("SST %",  14 * mm),
        ("Amount", 26 * mm),
    ]
    # Header background
    c.setFillColor(colors.HexColor("#e6f4ff"))
    c.rect(margin, table_y - 4, W - 2 * margin, 16, fill=1, stroke=0)
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 10)
    cx = margin + 2
    for label, w in cols:
        if label in ("Qty", "Unit Price", "Amount"):
            c.drawRightString(cx + w - 2, table_y + 4, label)
        else:
            c.drawString(cx, table_y + 4, label)
        cx += w

    # Rows
    c.setFont("Helvetica", 10)
    row_y = table_y - 6
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    line_results = []
    for i, (desc, qty, uom, unit_price, sst) in enumerate(line_items, start=1):
        row_y -= 18
        cx = margin + 2
        amount = Decimal(str(qty)) * Decimal(str(unit_price))
        sst_dec = Decimal(str(sst)) / Decimal("100")
        tax = (amount * sst_dec).quantize(Decimal("0.01"))
        subtotal += amount
        tax_total += tax
        line_results.append((i, desc, qty, uom, unit_price, sst, amount))

        values = [
            (str(i), False),
            (desc, False),
            (f"{qty:g}", True),
            (uom, False),
            (f"{unit_price:,.2f}", True),
            (f"{sst:g}%", False),
            (f"{float(amount):,.2f}", True),
        ]
        for (val, right_align), (_, w) in zip(values, cols):
            if right_align:
                c.drawRightString(cx + w - 2, row_y, val)
            else:
                # truncate desc if too long
                if w < 75 * mm and len(val) > 42:
                    val = val[:39] + "..."
                c.drawString(cx, row_y, val)
            cx += w

    # Bottom line under rows
    c.setStrokeColor(LIGHT_BORDER)
    c.line(margin, row_y - 6, W - margin, row_y - 6)

    # Totals box (right)
    tot_y = row_y - 24
    label_x = W - margin - 60 * mm
    val_x = W - margin - 2

    subtotal_q = subtotal.quantize(Decimal("0.01"))
    tax_total_q = tax_total.quantize(Decimal("0.01"))
    total = (subtotal_q + tax_total_q).quantize(Decimal("0.01"))

    c.setFont("Helvetica", 10)
    c.drawString(label_x, tot_y, f"Subtotal ({currency}):")
    c.drawRightString(val_x, tot_y, f"{float(subtotal_q):,.2f}")
    tot_y -= 14
    c.drawString(label_x, tot_y, f"SST ({currency}):")
    c.drawRightString(val_x, tot_y, f"{float(tax_total_q):,.2f}")
    tot_y -= 14
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(PRIMARY)
    c.drawString(label_x, tot_y, f"Total ({currency}):")
    c.drawRightString(val_x, tot_y, f"{float(total):,.2f}")
    c.setFillColor(DARK)

    # Currency conversion block
    if exchange_rate is not None:
        tot_y -= 18
        c.setFont("Helvetica", 10)
        c.drawString(label_x, tot_y, "Exchange Rate:")
        c.drawRightString(val_x, tot_y, f"1 {currency} = {exchange_rate:.4f} MYR")
        tot_y -= 14
        myr_total = (total * Decimal(str(exchange_rate))).quantize(Decimal("0.01"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(label_x, tot_y, "MYR Equivalent:")
        c.drawRightString(val_x, tot_y, f"{float(myr_total):,.2f}")

    # Notes
    notes_y = tot_y - 40
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, notes_y, "Notes:")
    c.setFont("Helvetica", 9)
    if not notes:
        notes = "Payment due within terms above. Goods sold are not returnable. Please make payment to the bank account on file."
    # simple word-wrap
    words = notes.split()
    line = ""
    line_y = notes_y - 14
    max_chars = 95
    for w in words:
        if len(line) + len(w) + 1 > max_chars:
            c.drawString(margin, line_y, line)
            line_y -= 12
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        c.drawString(margin, line_y, line)

    # Signature
    sig_y = margin + 20
    c.setStrokeColor(DARK)
    c.line(margin, sig_y, margin + 60 * mm, sig_y)
    c.line(W - margin - 60 * mm, sig_y, W - margin, sig_y)
    c.setFont("Helvetica", 9)
    c.drawString(margin, sig_y - 12, "Authorised Signature")
    c.drawString(W - margin - 60 * mm, sig_y - 12, "Received By")

    # Footer
    c.setFillColor(colors.HexColor("#8c8c8c"))
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(W / 2, margin - 4, f"{supplier_name}  |  This is a system-generated invoice.")

    c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Build everything
# ---------------------------------------------------------------------------
def main() -> None:
    # One-pagers
    draw_one_pager(OUT / "one-pager-en.pdf", lang="en")
    draw_one_pager(OUT / "one-pager-zh.pdf", lang="zh")

    # Invoice 1 - Tan Chong Trading (SST 10%)
    draw_invoice(
        INV_DIR / "INV-TanChongTrading.pdf",
        supplier_name="Tan Chong Trading Sdn Bhd",
        supplier_addr="12, Jalan Bukit Bintang, 55100 Kuala Lumpur",
        supplier_tin="C12345678901",
        supplier_tel="+60 3-2148 5566",
        invoice_no="TCT-2026-04812",
        invoice_date="2026-05-02",
        due_date="2026-06-01",
        line_items=[
            ("White Rice 50kg (Premium Grade)", 10, "BAG", 95.00, 10),
            ("Cooking Oil 5L (Bottle Carton x12)", 5, "CTN", 168.00, 10),
            ("Refined Sugar 25kg", 4, "BAG", 90.00, 10),
        ],
        notes="Payment terms: Net 30 days. Late payment 1.5% per month. Goods received in good order.",
    )

    # Invoice 2 - Syarikat Ahmad (Service tax 6%)
    draw_invoice(
        INV_DIR / "INV-SyarikatAhmad.pdf",
        supplier_name="Syarikat Ahmad Logistics Sdn Bhd",
        supplier_addr="45, Jalan Tun Razak, 50400 Kuala Lumpur",
        supplier_tin="C98765432109",
        supplier_tel="+60 3-2691 7788",
        invoice_no="SAL-2026-00329",
        invoice_date="2026-05-04",
        due_date="2026-06-03",
        line_items=[
            ("Inland transport - KL to Penang (40ft container)", 2, "TRIP", 1850.00, 6),
            ("Warehousing service - May 2026", 1, "MTH", 2400.00, 6),
            ("Loading and unloading service", 8, "HR", 75.00, 6),
        ],
        notes="Service Tax registered. Invoice covers logistics service for the period stated. Net 30 payment terms.",
    )

    # Invoice 3 - Rajesh Electronics (SST 10%, many lines)
    draw_invoice(
        INV_DIR / "INV-RajeshElectronics.pdf",
        supplier_name="Rajesh Electronics Trading Sdn Bhd",
        supplier_addr="78, Jalan Klang Lama, 58000 Kuala Lumpur",
        supplier_tin="C55667788990",
        supplier_tel="+60 3-7980 1234",
        invoice_no="RET-2026-01057",
        invoice_date="2026-05-06",
        due_date="2026-06-05",
        line_items=[
            ("USB-C Cable 1m Braided (Black)", 100, "PCS", 8.50, 10),
            ("USB-C Cable 2m Braided (Black)", 60, "PCS", 12.00, 10),
            ("Lightning Cable 1m MFi", 80, "PCS", 18.00, 10),
            ("Wall Charger 20W USB-C PD", 50, "PCS", 35.00, 10),
            ("Wall Charger 65W GaN Dual Port", 30, "PCS", 95.00, 10),
            ("Car Charger 30W Dual USB", 40, "PCS", 28.00, 10),
            ("Powerbank 10000mAh USB-C", 25, "PCS", 65.00, 10),
            ("Powerbank 20000mAh PD 22.5W", 20, "PCS", 120.00, 10),
            ("Wireless Charger 15W Qi Pad", 30, "PCS", 45.00, 10),
            ("Phone Case Universal 6.1in Clear", 100, "PCS", 6.50, 10),
        ],
        notes="All goods carry 7-day DOA warranty. Damaged shipment must be reported within 48 hours of delivery.",
    )

    # Invoice 4 - Eco Fresh Foods (mixed SST 0% exempt + 10%)
    draw_invoice(
        INV_DIR / "INV-EcoFreshFoods.pdf",
        supplier_name="Eco Fresh Foods Sdn Bhd",
        supplier_addr="23, Jalan Sungai Besi, 57100 Kuala Lumpur",
        supplier_tin="C11223344556",
        supplier_tel="+60 3-9221 4455",
        invoice_no="EFF-2026-00768",
        invoice_date="2026-05-07",
        due_date="2026-06-06",
        line_items=[
            ("Basmati Rice 10kg (Exempt - basic food)", 30, "BAG", 58.00, 0),
            ("Wheat Flour 5kg (Exempt - basic food)", 50, "BAG", 18.00, 0),
            ("White Sugar 1kg (Exempt - basic food)", 100, "PKT", 4.20, 0),
            ("Instant Noodle Variety Pack (Processed)", 40, "CTN", 65.00, 10),
            ("Canned Sardine 425g (Processed)", 60, "CAN", 9.50, 10),
            ("Snack Cookies Assorted Tin (Processed)", 20, "TIN", 38.00, 10),
        ],
        notes="Mixed tax rates: basic food items are SST exempt (0%), processed/packaged goods carry 10% SST.",
    )

    # Invoice 5 - Multi-currency USD
    draw_invoice(
        INV_DIR / "INV-MultiCurrency-USD.pdf",
        supplier_name="Global Tech Imports Pte Ltd",
        supplier_addr="160 Robinson Road, #10-01 SBF Center, Singapore 068914",
        supplier_tin="C77889900112",
        supplier_tel="+65 6789 4321",
        invoice_no="GTI-2026-02145",
        invoice_date="2026-05-08",
        due_date="2026-06-07",
        line_items=[
            ("Rack Server 1U Xeon Silver 32GB 2x1TB SSD", 2, "UNIT", 2850.00, 10),
            ("Network Switch 48-port Gigabit Managed", 4, "UNIT", 680.00, 10),
            ("UPS 3kVA Online Tower", 2, "UNIT", 1250.00, 10),
            ("Industrial Label Printer Thermal 300dpi", 3, "UNIT", 540.00, 10),
        ],
        currency="USD",
        exchange_rate=4.45,
        notes="Imported goods, FOB Singapore. Exchange rate snapshot at invoice date. Import duties payable separately by buyer.",
    )

    # Report
    files = [
        OUT / "one-pager-en.pdf",
        OUT / "one-pager-zh.pdf",
        INV_DIR / "INV-TanChongTrading.pdf",
        INV_DIR / "INV-SyarikatAhmad.pdf",
        INV_DIR / "INV-RajeshElectronics.pdf",
        INV_DIR / "INV-EcoFreshFoods.pdf",
        INV_DIR / "INV-MultiCurrency-USD.pdf",
    ]
    print("Generated files:")
    for f in files:
        size = f.stat().st_size
        print(f"  {f}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
