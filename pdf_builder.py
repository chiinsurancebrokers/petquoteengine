import io
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

from reportlab.platypus import Paragraph, Frame, KeepInFrame, ListFlowable, ListItem
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

# --------------------------
# Absolute project paths (Streamlit Cloud safe)
# --------------------------
BASE_DIR = Path(__file__).resolve().parent
F_REG = BASE_DIR / "assets" / "fonts" / "NotoSans-Regular.ttf"
F_BOLD = BASE_DIR / "assets" / "fonts" / "NotoSans-Bold.ttf"
LOGO_PATH = BASE_DIR / "assets" / "logo" / "petshealth_logo.png"

# --------------------------
# Fonts (Greek Unicode)
# --------------------------
BASE_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"
if F_REG.exists() and F_BOLD.exists():
    pdfmetrics.registerFont(TTFont("NS", str(F_REG)))
    pdfmetrics.registerFont(TTFont("NSB", str(F_BOLD)))
    registerFontFamily("NS", normal="NS", bold="NSB", italic="NS", boldItalic="NSB")
    BASE_FONT = "NS"
    BOLD_FONT = "NSB"

# --------------------------
# PETSHEALTH Brand Colors
# --------------------------
BRAND = {
    "dark": colors.HexColor("#111827"),
    "blue": colors.HexColor("#1E4FA8"),
    "soft": colors.HexColor("#F3F4F6"),
    "bg": colors.HexColor("#F7FAFC"),
    "border": colors.HexColor("#E5E7EB"),
    "muted": colors.HexColor("#6B7280"),
}


def _wrap_words(text: str, max_chars: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    out, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= max_chars:
            cur = trial
        else:
            if cur:
                out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def _header(c: canvas.Canvas, W, H, right_title: str):
    c.setFillColor(BRAND["dark"])
    c.rect(0, H - 20 * mm, W, 20 * mm, stroke=0, fill=1)

    if LOGO_PATH.exists():
        try:
            logo = ImageReader(str(LOGO_PATH))
            c.drawImage(logo, 14 * mm, H - 17 * mm, width=40 * mm, height=14 * mm,
                        preserveAspectRatio=True, anchor='sw', mask='auto')
        except:
            pass

    c.setFillColor(colors.white)
    c.setFont(BOLD_FONT, 13)
    c.drawRightString(W - 14 * mm, H - 12.5 * mm, right_title)


def _footer(c: canvas.Canvas, W):
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.setFont(BASE_FONT, 8.5)
    c.drawString(14 * mm, 12 * mm, "PETSHEALTH | www.petshealth.gr | info@petshealth.gr | +30 211 700 533")
    c.setFont(BASE_FONT, 7.5)
    c.drawRightString(W - 14 * mm, 12 * mm, "Because we care for your pets as much as you do")


def _draw_polaroid(c, img_bytes, x, y, w, h, angle=0):
    if not img_bytes:
        return
    pad = 3 * mm
    bottom_extra = 7 * mm
    try:
        img = ImageReader(io.BytesIO(img_bytes))
    except Exception:
        return

    c.saveState()
    cx = x + w / 2
    cy = y + h / 2
    c.translate(cx, cy)
    c.rotate(angle)
    c.translate(-cx, -cy)

    c.setFillColor(colors.Color(0, 0, 0, alpha=0.12))
    c.roundRect(x + 1.2 * mm, y - 1.2 * mm, w, h, 6, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setStrokeColor(BRAND["border"])
    c.roundRect(x, y, w, h, 7, stroke=1, fill=1)

    img_x = x + pad
    img_y = y + pad + bottom_extra
    img_w = w - 2 * pad
    img_h = h - 2 * pad - bottom_extra
    c.drawImage(img, img_x, img_y, img_w, img_h, preserveAspectRatio=True, anchor='c', mask='auto')

    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 7.4)
    c.drawString(x + pad, y + 2.4 * mm, "PETSHEALTH")
    c.restoreState()


def _polaroids_for_page(data: dict, page_index: int):
    imgs = data.get("polaroid_images", []) or []
    if not imgs:
        return []
    a = imgs[(page_index - 1) % len(imgs)]
    b = imgs[(page_index) % len(imgs)] if len(imgs) > 1 else None
    return [a] + ([b] if b else [])


def _draw_page_polaroids(c, W, H, data: dict, page_index: int):
    pimgs = _polaroids_for_page(data, page_index)
    if not pimgs:
        return
    y = 18 * mm
    w = 40 * mm
    h = 48 * mm
    _draw_polaroid(c, pimgs[0], 14 * mm, y, w, h, angle=-6)
    _draw_polaroid(c, pimgs[1] if len(pimgs) > 1 else pimgs[0], W - 14 * mm - w, y, w, h, angle=6)


def _draw_bullet_block(c, x, y, items, max_chars=52, leading=9.2, size=8.2):
    c.setFont(BASE_FONT, size)
    c.setFillColor(BRAND["dark"])
    yy = y
    for it in (items or []):
        if not it:
            continue
        for i, ln in enumerate(_wrap_words(str(it), max_chars)):
            prefix = "• " if i == 0 else "  "
            c.drawString(x, yy, prefix + ln)
            yy -= leading
    return yy


def _plan_card(c, x, y_top, w, h, title, subtitle, blocks):
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(x, y_top - h, w, h, 10, stroke=1, fill=1)

    c.setFillColor(BRAND["bg"])
    c.roundRect(x, y_top - 14 * mm, w, 14 * mm, 10, stroke=0, fill=1)
    c.setFillColor(BRAND["blue"])
    c.roundRect(x, y_top - 4, w, 4, 2, stroke=0, fill=1)

    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.0)
    c.drawString(x + 6 * mm, y_top - 8.2 * mm, title)

    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 8.0)
    c.drawString(x + 6 * mm, y_top - 12.3 * mm, subtitle)

    yy = y_top - 18 * mm
    for section_title, bullet_items in blocks:
        bullet_items = (bullet_items or [])[:6]
        c.setFillColor(BRAND["dark"])
        c.setFont(BOLD_FONT, 9.0)
        c.drawString(x + 6 * mm, yy, section_title)
        yy -= 5
        yy = _draw_bullet_block(c, x + 8 * mm, yy, bullet_items, max_chars=52, leading=9.4, size=8.2)
        yy -= 5


def _platypus_bullets(items, style, max_items=10):
    items = (items or [])[:max_items]
    flow = []
    for it in items:
        if not it:
            continue
        p = Paragraph(str(it), style)
        flow.append(ListItem(p, leftIndent=10, bulletText="•", value="•"))
    return ListFlowable(flow, bulletType="bullet", leftIndent=10)


def build_quote_pdf(data: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    selected_plans = data.get("selected_plans", []) or []
    mode = data.get("quote_mode", "")
    pet_count = int(data.get("pet_count", 1) or 1)

    # ---------------- PAGE 1 ----------------
    c.setFillColor(BRAND["dark"])
    c.rect(0, H - 28 * mm, W, 28 * mm, stroke=0, fill=1)

    if LOGO_PATH.exists():
        try:
            logo = ImageReader(str(LOGO_PATH))
            c.drawImage(logo, 14 * mm, H - 24 * mm, width=45 * mm, height=18 * mm,
                        preserveAspectRatio=True, anchor='sw', mask='auto')
        except:
            c.setFillColor(colors.white)
            c.setFont(BOLD_FONT, 15)
            c.drawString(14 * mm, H - 16 * mm, "PETSHEALTH – Pet Insurance Quotation")
    else:
        c.setFillColor(colors.white)
        c.setFont(BOLD_FONT, 15)
        c.drawString(14 * mm, H - 16 * mm, "PETSHEALTH – Pet Insurance Quotation")

    c.setFont(BASE_FONT, 9.5)
    c.setFillColor(colors.HexColor("#E5E7EB"))
    c.drawRightString(W - 14 * mm, H - 22 * mm, f"Quote Date: {data.get('quote_date', '')}")

    hook = (data.get("marketing_hook") or "").strip()
    c.setFillColor(BRAND["blue"])
    c.setFont(BOLD_FONT, 11.5)
    c.drawString(14 * mm, H - 36 * mm, hook[:110])

    y = H - 60 * mm

    # Summary box
    box_x = 14 * mm
    box_w = W - 28 * mm
    box_h = 48 * mm if "Bulk" in mode else 44 * mm

    c.setFillColor(BRAND["bg"])
    c.roundRect(box_x, y - box_h, box_w, box_h, 10, stroke=0, fill=1)
    c.setFillColor(BRAND["blue"])
    c.roundRect(box_x, y - 4, box_w, 4, 2, stroke=0, fill=1)

    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 11.2)
    c.drawString(box_x + 8 * mm, y - 10 * mm, "Client & Pet Summary")

    c.setFont(BASE_FONT, 10)
    c.setFillColor(BRAND["dark"])
    c.drawString(box_x + 8 * mm, y - 18 * mm, f"Client: {data.get('client_name', '')}")
    c.drawString(box_x + 8 * mm, y - 26 * mm, f"Phone:  {data.get('client_phone', '')}")
    c.drawString(box_x + 8 * mm, y - 34 * mm, f"Email:  {data.get('client_email', '')}")
    loc = (data.get("location") or "").strip()
    if loc:
        c.drawString(box_x + 8 * mm, y - 42 * mm, f"Location: {loc}")

    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 9.5)

    if "Bulk" in mode:
        c.drawRightString(box_x + box_w - 8 * mm, y - 18 * mm, f"Pets: {pet_count} (Bulk quote)")
        bs = (data.get("bulk_summary") or "").strip()
        if bs:
            c.setFont(BASE_FONT, 9)
            yyb = y - 42 * mm
            for ln in bs.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                c.drawString(box_x + 8 * mm, yyb, ln[:120])
                yyb -= 11
    else:
        c.drawRightString(box_x + box_w - 8 * mm, y - 18 * mm,
                          f"Pet: {data.get('pet_name', '')} ({data.get('pet_species', '')})")
        c.drawRightString(box_x + box_w - 8 * mm, y - 26 * mm, f"Breed: {data.get('pet_breed', '')}")
        c.drawRightString(box_x + box_w - 8 * mm, y - 34 * mm,
                          f"DOB: {data.get('pet_dob', '')} | Microchip: {data.get('pet_microchip', '')}")

    # Proposed Solution
    y2 = y - box_h - 10 * mm
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 12)
    c.drawString(14 * mm, y2, "Recommended Options")
    y2 -= 8 * mm

    c.setFont(BASE_FONT, 10)
    if "PET CARE PLUS (INTERLIFE)" in selected_plans:
        c.drawString(14 * mm, y2, f"• {data.get('plan_1_name', '')} – {data.get('plan_1_provider', '')}")
        y2 -= 6 * mm
    if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
        c.drawString(14 * mm, y2, f"• {data.get('plan_2_name', '')} – {data.get('plan_2_provider', '')}")
        y2 -= 6 * mm

    # ============== PRICING CARD - FIXED SPACING ==============
    y3 = y2 - 10 * mm
    card_x = 14 * mm
    card_w = W - 28 * mm
    card_h = 52 * mm  # INCREASED from 42mm

    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(card_x, y3 - card_h, card_w, card_h, 10, stroke=1, fill=1)

    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 11)
    c.drawString(card_x + 8 * mm, y3 - 10 * mm, "Pricing Summary")
    c.setFont(BASE_FONT, 10)
    c.drawRightString(card_x + card_w - 8 * mm, y3 - 10 * mm, "Annual Premium (€)")

    # FIXED: More space between lines
    yy = y3 - 24 * mm  # Start lower
    line_gap = 11 * mm  # INCREASED gap

    if "PET CARE PLUS (INTERLIFE)" in selected_plans:
        c.setFillColor(BRAND["muted"])
        c.setFont(BASE_FONT, 10)
        c.drawString(card_x + 8 * mm, yy, data.get("plan_1_name", ""))
        c.setFillColor(BRAND["dark"])
        c.setFont(BOLD_FONT, 10.5)
        c.drawRightString(card_x + card_w - 8 * mm, yy,
                          str(data.get("plan_1_price_total", data.get("plan_1_price", ""))))
        yy -= line_gap

    if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
        c.setFillColor(BRAND["muted"])
        c.setFont(BASE_FONT, 10)
        c.drawString(card_x + 8 * mm, yy, data.get("plan_2_name", ""))
        c.setFillColor(BRAND["dark"])
        c.setFont(BOLD_FONT, 10.5)
        c.drawRightString(card_x + card_w - 8 * mm, yy,
                          str(data.get("plan_2_price_total", data.get("plan_2_price", ""))))

    # Total bar (clear and prominent)
    total_bar_h = 13 * mm
    c.setFillColor(BRAND["blue"])
    c.roundRect(card_x, y3 - card_h, card_w, total_bar_h, 10, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(BOLD_FONT, 12.5)
    c.drawString(card_x + 8 * mm, y3 - card_h + 4.5 * mm, "Total Annual Premium")
    c.drawRightString(card_x + card_w - 8 * mm, y3 - card_h + 4.5 * mm, str(data.get("total_price", "")))

    # Notes
    y4 = y3 - card_h - 8 * mm
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.5)
    c.drawString(14 * mm, y4, "Notes / Disclaimer")
    y4 -= 6 * mm
    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 9)
    for ln in _wrap_words(data.get("notes", ""), 112):
        c.drawString(14 * mm, y4, ln)
        y4 -= 11

    _draw_page_polaroids(c, W, H, data, page_index=1)
    _footer(c, W)

    # ---------------- PAGE 2 ----------------
    c.showPage()
    _header(c, W, H, "Plan Coverage Summary")

    top = H - 30 * mm
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 12.5)
    c.drawString(14 * mm, top, "Coverage Details (Summary)")
    top -= 8 * mm

    if len(selected_plans) == 1:
        x = 14 * mm
        w = W - 28 * mm
        h = 165 * mm
        y_top = top
        if selected_plans[0] == "PET CARE PLUS (INTERLIFE)":
            title = f"{data.get('plan_1_name', '')} ({data.get('plan_1_provider', '')})"
            subtitle = f"€{data.get('plan_1_price', '')}/year | Limit: {data.get('plan1_limit', '')} | Area: {data.get('plan1_area', '')}"
            blocks = [
                ("Key Facts", data.get("plan1_key_facts", [])),
                ("Covers (Summary)", data.get("plan1_covers", [])),
                ("Not Covered (Indicative)", data.get("plan1_exclusions", [])),
                ("Waiting Periods", data.get("plan1_waiting", [])),
            ]
        else:
            title = f"{data.get('plan_2_name', '')} ({data.get('plan_2_provider', '')})"
            subtitle = f"Limit: {data.get('plan2_limit', '')} | Area: {data.get('plan2_area', '')} | Network only"
            blocks = [
                ("Key Facts", data.get("plan2_key_facts", [])),
                ("Covers (Summary)", data.get("plan2_covers", [])),
                ("Not Covered (Indicative)", data.get("plan2_exclusions", [])),
                ("Waiting Periods", data.get("plan2_waiting", [])),
            ]
        _plan_card(c, x, y_top, w, h, title, subtitle, blocks)
    else:
        gap = 8 * mm
        card_w = (W - 28 * mm - gap) / 2
        card_h = 165 * mm
        x1 = 14 * mm
        x2 = 14 * mm + card_w + gap
        y_top = top

        if "PET CARE PLUS (INTERLIFE)" in selected_plans:
            title = f"{data.get('plan_1_name', '')} ({data.get('plan_1_provider', '')})"
            subtitle = f"€{data.get('plan_1_price', '')}/year | Limit: {data.get('plan1_limit', '')} | Area: {data.get('plan1_area', '')}"
            blocks = [
                ("Key Facts", data.get("plan1_key_facts", [])),
                ("Covers (Summary)", data.get("plan1_covers", [])),
                ("Not Covered (Indicative)", data.get("plan1_exclusions", [])),
                ("Waiting Periods", data.get("plan1_waiting", [])),
            ]
            _plan_card(c, x1, y_top, card_w, card_h, title, subtitle, blocks)

        if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
            title = f"{data.get('plan_2_name', '')} ({data.get('plan_2_provider', '')})"
            subtitle = f"Limit: {data.get('plan2_limit', '')} | Area: {data.get('plan2_area', '')} | Network only"
            blocks = [
                ("Key Facts", data.get("plan2_key_facts", [])),
                ("Covers (Summary)", data.get("plan2_covers", [])),
                ("Not Covered (Indicative)", data.get("plan2_exclusions", [])),
                ("Waiting Periods", data.get("plan2_waiting", [])),
            ]
            _plan_card(c, x2, y_top, card_w, card_h, title, subtitle, blocks)

    _draw_page_polaroids(c, W, H, data, page_index=2)
    _footer(c, W)

    # ---------------- PAGE 3 ----------------
    c.showPage()
    _header(c, W, H, "About & Official Highlights")

    body_style = ParagraphStyle(
        name="Body",
        fontName=BASE_FONT,
        fontSize=10,
        leading=13,
        textColor=BRAND["dark"],
        alignment=TA_LEFT,
    )
    small_style = ParagraphStyle(
        name="Small",
        fontName=BASE_FONT,
        fontSize=9.2,
        leading=12,
        textColor=BRAND["dark"],
        alignment=TA_LEFT,
    )

    margin_x = 14 * mm
    top_y = H - 30 * mm

    c.setFillColor(BRAND["bg"])
    c.setStrokeColor(BRAND["border"])
    c.roundRect(margin_x, top_y - 12 * mm, W - 2 * margin_x, 12 * mm, 8, stroke=1, fill=1)
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.2)
    c.drawString(margin_x + 6 * mm, top_y - 8.3 * mm,
                 "Trust: SAFE PET (2016)  •  Pet Insurance advisor  •  CII certified (PL4, W01)")

    top_y -= 16 * mm

    box1_h = 56 * mm
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(BRAND["bg"])
    c.roundRect(margin_x, top_y - box1_h, W - 2 * margin_x, box1_h, 10, stroke=1, fill=1)
    c.setFillColor(BRAND["blue"])
    c.roundRect(margin_x, top_y - 4, W - 2 * margin_x, 4, 2, stroke=0, fill=1)

    c.setFont(BOLD_FONT, 14)
    c.setFillColor(BRAND["dark"])
    c.drawString(margin_x + 6 * mm, top_y - 12 * mm, "About the Advisor")

    bio = (data.get("about_bio") or "").strip() or "Add your advisor bio in the app."
    bio_par = Paragraph(bio.replace("\n", "<br/>"), body_style)
    bio_frame = Frame(margin_x + 6 * mm, top_y - box1_h + 8 * mm, W - 2 * margin_x - 12 * mm, box1_h - 22 * mm,
                      showBoundary=0)
    bio_frame.addFromList([KeepInFrame(W - 2 * margin_x - 12 * mm, box1_h - 22 * mm, [bio_par], mode="shrink")], c)

    box2_top = top_y - box1_h - 8 * mm
    box2_h = 30 * mm
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(margin_x, box2_top - box2_h, W - 2 * margin_x, box2_h, 10, stroke=1, fill=1)

    c.setFont(BOLD_FONT, 12)
    c.setFillColor(BRAND["dark"])
    c.drawString(margin_x + 6 * mm, box2_top - 10 * mm, "Credentials (CII)")

    cii = data.get("cii_titles", []) or ["(Add CII titles in the app)"]
    cii_flow = _platypus_bullets(cii, small_style, max_items=6)
    cii_frame = Frame(margin_x + 6 * mm, box2_top - box2_h + 6 * mm, W - 2 * margin_x - 12 * mm, box2_h - 18 * mm,
                      showBoundary=0)
    cii_frame.addFromList([KeepInFrame(W - 2 * margin_x - 12 * mm, box2_h - 18 * mm, [cii_flow], mode="shrink")], c)

    box3_top = box2_top - box2_h - 10 * mm
    box3_h = 70 * mm

    c.setFont(BOLD_FONT, 12.5)
    c.setFillColor(BRAND["dark"])
    c.drawString(margin_x, box3_top, "Official Highlights (Editable)")
    box3_top -= 6 * mm

    gap = 8 * mm
    col_w = (W - 2 * margin_x - gap) / 2

    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(margin_x, box3_top - box3_h, col_w, box3_h, 10, stroke=1, fill=1)
    c.setFillColor(BRAND["soft"])
    c.roundRect(margin_x, box3_top - 12 * mm, col_w, 12 * mm, 10, stroke=0, fill=1)
    c.setFont(BOLD_FONT, 10.8)
    c.setFillColor(BRAND["dark"])
    c.drawString(margin_x + 6 * mm, box3_top - 8 * mm, "EUROLIFE – My Happy Pet")

    eu = data.get("official_eurolife", []) or ["(Optional) Use 'Load official highlights' in the app."]
    eu_flow = _platypus_bullets(eu, small_style, max_items=8)
    eu_frame = Frame(margin_x + 6 * mm, box3_top - box3_h + 6 * mm, col_w - 12 * mm, box3_h - 20 * mm, showBoundary=0)
    eu_frame.addFromList([KeepInFrame(col_w - 12 * mm, box3_h - 20 * mm, [eu_flow], mode="shrink")], c)

    xr = margin_x + col_w + gap
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(xr, box3_top - box3_h, col_w, box3_h, 10, stroke=1, fill=1)
    c.setFillColor(BRAND["soft"])
    c.roundRect(xr, box3_top - 12 * mm, col_w, 12 * mm, 10, stroke=0, fill=1)
    c.setFont(BOLD_FONT, 10.8)
    c.setFillColor(BRAND["dark"])
    c.drawString(xr + 6 * mm, box3_top - 8 * mm, "INTERLIFE – PET CARE")

    it = data.get("official_interlife", []) or ["(Optional) Use 'Load official highlights' in the app."]
    it_flow = _platypus_bullets(it, small_style, max_items=8)
    it_frame = Frame(xr + 6 * mm, box3_top - box3_h + 6 * mm, col_w - 12 * mm, box3_h - 20 * mm, showBoundary=0)
    it_frame.addFromList([KeepInFrame(col_w - 12 * mm, box3_h - 20 * mm, [it_flow], mode="shrink")], c)

    _draw_page_polaroids(c, W, H, data, page_index=3)
    _footer(c, W)

    c.save()
    return buf.getvalue()
