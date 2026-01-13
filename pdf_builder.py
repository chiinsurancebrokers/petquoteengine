import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# Unicode fonts (Greek-safe)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

F_REG = os.path.join("assets", "fonts", "NotoSans-Regular.ttf")
F_BOLD = os.path.join("assets", "fonts", "NotoSans-Bold.ttf")

if os.path.exists(F_REG) and os.path.exists(F_BOLD):
    try:
        pdfmetrics.registerFont(TTFont("NS", F_REG))
        pdfmetrics.registerFont(TTFont("NSB", F_BOLD))
        BASE_FONT = "NS"
        BOLD_FONT = "NSB"
    except Exception:
        BASE_FONT = "Helvetica"
        BOLD_FONT = "Helvetica-Bold"
else:
    BASE_FONT = "Helvetica"
    BOLD_FONT = "Helvetica-Bold"

BRAND = {
    "blue": colors.HexColor("#1E4FA8"),
    "green": colors.HexColor("#6DB44D"),
    "accent": colors.HexColor("#F5A623"),
    "dark": colors.HexColor("#111827"),
    "muted": colors.HexColor("#6B7280"),
    "bg": colors.HexColor("#F7FAFC"),
    "border": colors.HexColor("#E5E7EB"),
    "soft": colors.HexColor("#F3F4F6"),
}

def _try_icon(path: str):
    return path if os.path.exists(path) else None

def _wrap(s: str, width: int):
    words = (s or "").split()
    lines, cur = [], []
    n = 0
    for w in words:
        add = len(w) + (1 if cur else 0)
        if n + add > width:
            lines.append(" ".join(cur))
            cur = [w]
            n = len(w)
        else:
            cur.append(w)
            n += add
    if cur:
        lines.append(" ".join(cur))
    return lines

def _draw_paragraph(c, x, y, text, max_chars=110, leading=12, font=None, size=9, color=None):
    font = font or BASE_FONT
    color = color or BRAND["muted"]
    c.setFont(font, size)
    c.setFillColor(color)
    t = c.beginText(x, y)
    t.setLeading(leading)
    for line in _wrap(text or "", max_chars):
        t.textLine(line)
    c.drawText(t)
    # return y after paragraph
    return y - leading * max(1, len(_wrap(text or "", max_chars)))

def _draw_bullets(c, x, y, items, max_width_chars=62, leading=11, font=None, size=8.8, color=None):
    font = font or BASE_FONT
    color = color or BRAND["dark"]
    c.setFont(font, size)
    c.setFillColor(color)
    yy = y
    for item in (items or []):
        for i, line in enumerate(_wrap(str(item), max_width_chars)):
            prefix = "• " if i == 0 else "  "
            c.drawString(x, yy, prefix + line)
            yy -= leading
    return yy

def _section(c, label, x, y):
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.2)
    c.drawString(x, y, label)
    return y - 12

def _draw_header(c, W, H, title_right):
    c.setFillColor(BRAND["dark"])
    c.rect(0, H - 20*mm, W, 20*mm, stroke=0, fill=1)

    logo_path = os.path.join("assets", "logo.png")
    if os.path.exists(logo_path):
        try:
            logo = ImageReader(logo_path)
            c.drawImage(logo, 14*mm, H - 16*mm, width=50*mm, height=14*mm, mask='auto')
        except Exception:
            pass

    c.setFillColor(colors.white)
    c.setFont(BOLD_FONT, 13)
    c.drawRightString(W - 14*mm, H - 12.5*mm, title_right)

def _draw_plan_card(c, x, y_top, w, h, title, subtitle, key_facts, covers, exclusions, waiting):
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(x, y_top - h, w, h, 10, stroke=1, fill=1)

    c.setFillColor(BRAND["bg"])
    c.roundRect(x, y_top - 14*mm, w, 14*mm, 10, stroke=0, fill=1)

    c.setFillColor(BRAND["blue"])
    c.roundRect(x, y_top - 4, w, 4, 2, stroke=0, fill=1)

    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.2)
    c.drawString(x + 6*mm, y_top - 8*mm, title)

    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 8.6)
    c.drawString(x + 6*mm, y_top - 12*mm, subtitle)

    yy = y_top - 18*mm

    yy = _section(c, "Key Facts", x + 6*mm, yy)
    yy = _draw_bullets(c, x + 8*mm, yy, key_facts, 60, 10) - 6

    yy = _section(c, "Covers (Summary)", x + 6*mm, yy)
    yy = _draw_bullets(c, x + 8*mm, yy, covers, 60, 10) - 6

    yy = _section(c, "Not Covered (Indicative)", x + 6*mm, yy)
    yy = _draw_bullets(c, x + 8*mm, yy, exclusions, 60, 10) - 6

    yy = _section(c, "Waiting Periods", x + 6*mm, yy)
    _draw_bullets(c, x + 8*mm, yy, waiting, 60, 10)

def build_quote_pdf(data: dict) -> bytes:
    """
    Expected keys:
      client_name, client_phone, client_email,
      pet_name, pet_species, pet_breed, pet_dob, pet_microchip,
      plan_1_name, plan_1_provider, plan_1_price,
      plan_2_name, plan_2_provider, plan_2_price,
      total_price, quote_date, notes

      plan1_limit, plan1_area, plan1_key_facts, plan1_covers, plan1_exclusions, plan1_waiting
      plan2_limit, plan2_area, plan2_key_facts, plan2_covers, plan2_exclusions, plan2_waiting

      about_bio (string), cii_titles (list)
      official_eurolife (list), official_interlife (list)
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    W, H = A4

    # ---------------- PAGE 1 ----------------
    c.setFillColor(BRAND["dark"])
    c.rect(0, H - 28*mm, W, 28*mm, stroke=0, fill=1)

    logo_path = os.path.join("assets", "logo.png")
    if os.path.exists(logo_path):
        try:
            logo = ImageReader(logo_path)
            c.drawImage(logo, 14*mm, H - 22*mm, width=55*mm, height=18*mm, mask='auto')
        except Exception:
            pass

    c.setFillColor(colors.white)
    c.setFont(BOLD_FONT, 14)
    c.drawRightString(W - 14*mm, H - 16*mm, "Pet Insurance Quotation")

    c.setFont(BASE_FONT, 9.5)
    c.setFillColor(colors.HexColor("#E5E7EB"))
    c.drawRightString(W - 14*mm, H - 22*mm, f"Quote Date: {data.get('quote_date','')}")

    y = H - 40*mm

    # Summary box
    box_x = 14*mm
    box_w = W - 28*mm
    box_h = 44*mm

    c.setFillColor(BRAND["bg"])
    c.roundRect(box_x, y - box_h, box_w, box_h, 10, stroke=0, fill=1)

    c.setFillColor(BRAND["blue"])
    c.roundRect(box_x, y - 4, box_w, 4, 2, stroke=0, fill=1)

    icon_owner = _try_icon(os.path.join("assets", "icon_owner.png"))
    icon_pet = _try_icon(os.path.join("assets", "icon_pet.png"))
    icon_phone = _try_icon(os.path.join("assets", "icon_phone.png"))
    icon_mail = _try_icon(os.path.join("assets", "icon_mail.png"))

    def draw_icon(path, x, yy, size=6*mm):
        if not path:
            c.setFillColor(BRAND["green"])
            c.circle(x + size/2, yy + size/2, size/2, stroke=0, fill=1)
            return
        img = ImageReader(path)
        c.drawImage(img, x, yy, width=size, height=size, mask="auto")

    pad = 8*mm
    col1_x = box_x + pad
    col2_x = box_x + box_w/2 + 4*mm
    row1_y = y - 16*mm
    row2_y = y - 28*mm
    row3_y = y - 40*mm

    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 11)
    c.drawString(col1_x, y - 10*mm, "Client & Pet Summary")

    c.setFont(BASE_FONT, 10)
    draw_icon(icon_owner, col1_x, row1_y, 6*mm)
    c.setFillColor(BRAND["dark"])
    c.drawString(col1_x + 8*mm, row1_y + 1.5*mm, f"Client: {data.get('client_name','')}")
    draw_icon(icon_phone, col1_x, row2_y, 6*mm)
    c.drawString(col1_x + 8*mm, row2_y + 1.5*mm, f"Phone: {data.get('client_phone','')}")
    draw_icon(icon_mail, col1_x, row3_y, 6*mm)
    c.drawString(col1_x + 8*mm, row3_y + 1.5*mm, f"Email: {data.get('client_email','')}")

    draw_icon(icon_pet, col2_x, row1_y, 6*mm)
    c.drawString(col2_x + 8*mm, row1_y + 1.5*mm, f"Pet: {data.get('pet_name','')} ({data.get('pet_species','')})")
    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 9.5)
    c.drawString(col2_x + 8*mm, row2_y + 1.5*mm, f"Breed: {data.get('pet_breed','')}")
    c.drawString(col2_x + 8*mm, row3_y + 1.5*mm, f"DOB: {data.get('pet_dob','')} | Microchip: {data.get('pet_microchip','')}")

    # Plans intro
    y2 = y - box_h - 10*mm
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 12)
    c.drawString(14*mm, y2, "Proposed Insurance Solution")

    y2 -= 8*mm
    c.setFont(BASE_FONT, 10)
    c.drawString(14*mm, y2, f"1) {data.get('plan_1_name','')} – {data.get('plan_1_provider','')}")
    y2 -= 6*mm
    c.drawString(14*mm, y2, f"2) {data.get('plan_2_name','')} – {data.get('plan_2_provider','')}")

    # Pricing card
    y3 = y2 - 16*mm
    card_x = 14*mm
    card_w = W - 28*mm
    card_h = 34*mm

    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(card_x, y3 - card_h, card_w, card_h, 10, stroke=1, fill=1)

    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 11)
    c.drawString(card_x + 8*mm, y3 - 10*mm, "Pricing Summary")

    c.setFont(BASE_FONT, 10)
    c.drawRightString(card_x + card_w - 8*mm, y3 - 10*mm, "Annual Premium (€)")

    c.setFillColor(BRAND["muted"])
    c.drawString(card_x + 8*mm, y3 - 18*mm, data.get("plan_1_name",""))
    c.setFillColor(BRAND["dark"])
    c.drawRightString(card_x + card_w - 8*mm, y3 - 18*mm, str(data.get("plan_1_price","")))

    c.setFillColor(BRAND["muted"])
    c.drawString(card_x + 8*mm, y3 - 25*mm, data.get("plan_2_name",""))
    c.setFillColor(BRAND["dark"])
    c.drawRightString(card_x + card_w - 8*mm, y3 - 25*mm, str(data.get("plan_2_price","")))

    c.setFillColor(BRAND["blue"])
    c.roundRect(card_x, y3 - card_h, card_w, 8*mm, 10, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(BOLD_FONT, 11)
    c.drawString(card_x + 8*mm, y3 - card_h + 2.2*mm, "Total Annual Premium")
    c.drawRightString(card_x + card_w - 8*mm, y3 - card_h + 2.2*mm, str(data.get("total_price","")))

    # Notes
    y4 = y3 - card_h - 10*mm
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 11)
    c.drawString(14*mm, y4, "Notes / Disclaimer")
    y4 -= 6*mm
    y4 = _draw_paragraph(c, 14*mm, y4, data.get("notes",""), max_chars=105, leading=12, font=BASE_FONT, size=9, color=BRAND["muted"])

    # Footer page 1
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.setFont(BASE_FONT, 8.5)
    c.drawString(14*mm, 12*mm, "PETSHEALTH | www.petshealth.gr | info@petshealth.gr")
    c.drawRightString(W - 14*mm, 12*mm, "Because we care for your pets as much as you do")

    # ---------------- PAGE 2 ----------------
    c.showPage()
    _draw_header(c, W, H, "Plan Coverage Summary")

    top = H - 30*mm
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 12)
    c.drawString(14*mm, top, "Coverage Details (Summary)")

    card_gap = 8*mm
    card_w2 = (W - 28*mm - card_gap) / 2
    card_h2 = 150*mm
    x1 = 14*mm
    x2 = 14*mm + card_w2 + card_gap
    y_top = top - 8*mm

    p1_title = f"{data.get('plan_1_name','')} ({data.get('plan_1_provider','')})"
    p1_sub = f"€{data.get('plan_1_price','')}/year | Limit: {data.get('plan1_limit','')} | Area: {data.get('plan1_area','')}"
    _draw_plan_card(
        c, x1, y_top, card_w2, card_h2,
        p1_title, p1_sub,
        data.get("plan1_key_facts", []),
        data.get("plan1_covers", []),
        data.get("plan1_exclusions", []),
        data.get("plan1_waiting", []),
    )

    p2_title = f"{data.get('plan_2_name','')} ({data.get('plan_2_provider','')})"
    p2_sub = f"Limit: {data.get('plan2_limit','')} | Area: {data.get('plan2_area','')} | Network only"
    _draw_plan_card(
        c, x2, y_top, card_w2, card_h2,
        p2_title, p2_sub,
        data.get("plan2_key_facts", []),
        data.get("plan2_covers", []),
        data.get("plan2_exclusions", []),
        data.get("plan2_waiting", []),
    )

    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.setFont(BASE_FONT, 8.5)
    c.drawString(14*mm, 12*mm, "PETSHEALTH | www.petshealth.gr | info@petshealth.gr")
    c.drawRightString(W - 14*mm, 12*mm, "Because we care for your pets as much as you do")

    # ---------------- PAGE 3 ----------------
    c.showPage()
    _draw_header(c, W, H, "About & Official Highlights")

    top = H - 30*mm

    # About section
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 12)
    c.drawString(14*mm, top, "About the Advisor")
    top -= 8*mm

    bio = data.get("about_bio", "") or ""
    if not bio.strip():
        bio = "Add your bio text in the app (Page 3 – editable)."

    # Bio card
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(BRAND["bg"])
    c.roundRect(14*mm, top - 46*mm, W - 28*mm, 46*mm, 10, stroke=1, fill=1)
    c.setFillColor(BRAND["blue"])
    c.roundRect(14*mm, top - 4, W - 28*mm, 4, 2, stroke=0, fill=1)

    ybio = top - 10*mm
    ybio = _draw_paragraph(c, 18*mm, ybio, bio, max_chars=118, leading=12, font=BASE_FONT, size=9.3, color=BRAND["dark"])

    # Credentials
    ycred = top - 52*mm
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 11)
    c.drawString(14*mm, ycred, "Credentials (CII)")
    ycred -= 7*mm

    cii = data.get("cii_titles", []) or []
    if not cii:
        cii = [
            "Chartered Insurance Institute – (PL4) Introduction to Pet Insurance (Unit achieved: June 2023)",
            "Chartered Insurance Institute – (W01) Award in General Insurance (English) (Unit achieved: March 2025)",
        ]
    ycred = _draw_bullets(c, 16*mm, ycred, cii, max_width_chars=118, leading=12, font=BASE_FONT, size=9.2, color=BRAND["dark"])
    ycred -= 8

    # Official highlights columns
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 12)
    c.drawString(14*mm, ycred, "Official Highlights (Editable)")
    ycred -= 8*mm

    col_gap = 8*mm
    col_w = (W - 28*mm - col_gap) / 2
    col_h = 86*mm
    xL = 14*mm
    xR = 14*mm + col_w + col_gap
    yTopCols = ycred

    # Left card: Eurolife
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(xL, yTopCols - col_h, col_w, col_h, 10, stroke=1, fill=1)
    c.setFillColor(BRAND["soft"])
    c.roundRect(xL, yTopCols - 12*mm, col_w, 12*mm, 10, stroke=0, fill=1)

    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.5)
    c.drawString(xL + 6*mm, yTopCols - 8*mm, "EUROLIFE – My Happy Pet")

    eu = data.get("official_eurolife", []) or []
    if not eu:
        eu = ["(Optional) Click “Load official highlights” in the app to auto-fill this section."]
    _draw_bullets(c, xL + 6*mm, yTopCols - 16*mm, eu, max_width_chars=58, leading=11, font=BASE_FONT, size=8.8, color=BRAND["dark"])

    # Right card: Interlife
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(xR, yTopCols - col_h, col_w, col_h, 10, stroke=1, fill=1)
    c.setFillColor(BRAND["soft"])
    c.roundRect(xR, yTopCols - 12*mm, col_w, 12*mm, 10, stroke=0, fill=1)

    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.5)
    c.drawString(xR + 6*mm, yTopCols - 8*mm, "INTERLIFE – PET CARE")

    it = data.get("official_interlife", []) or []
    if not it:
        it = ["(Optional) Click “Load official highlights” in the app to auto-fill this section."]
    _draw_bullets(c, xR + 6*mm, yTopCols - 16*mm, it, max_width_chars=58, leading=11, font=BASE_FONT, size=8.8, color=BRAND["dark"])

    # Footer page 3
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.setFont(BASE_FONT, 8.5)
    c.drawString(14*mm, 12*mm, "PETSHEALTH | www.petshealth.gr | info@petshealth.gr")
    c.drawRightString(W - 14*mm, 12*mm, "Because we care for your pets as much as you do")

    c.save()
    return buffer.getvalue()

