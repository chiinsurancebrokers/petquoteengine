"""
PETSHEALTH Quote Engine - Complete PDF Builder (v5 FINAL)

All fixes implemented:
✅ Page 1: Client Summary + Recommended Options + Pricing Card + Notes (safe wrapping)
✅ Page 2: NO overlap (Platypus Frame + KeepInFrame) — robust layout
✅ Page 2: Title WRAPS (e.g., “EUROLIFE …”) and never touches border
✅ Page 2: Proper wrapping in narrow columns (soft-breaks for / - – |)
✅ Page 3: About bio no longer truncated (MAX_BIO_LENGTH = 30,000 chars)
✅ Page 3: Bio + Highlights are SAFE for Paragraph (XML-escaped) — no “missing text”
✅ Page 3: Official highlights ALWAYS render (KeepInFrame shrink) + supports long multiline bullets
✅ Python 3.9 compatible typing

Drop-in replacement: pdf_builder.py
"""
import io
import logging
import re
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

from reportlab.platypus import Paragraph, Frame, ListFlowable, ListItem, KeepInFrame
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

logger = logging.getLogger(__name__)

# --------------------------
# PATHS (Streamlit Cloud safe)
# --------------------------
BASE_DIR = Path(__file__).resolve().parent
FONTS_DIR = BASE_DIR / "assets" / "fonts"
LOGO_PATH = BASE_DIR / "assets" / "logo" / "petshealth_logo.png"

F_REG = FONTS_DIR / "NotoSans-Regular.ttf"
F_BOLD = FONTS_DIR / "NotoSans-Bold.ttf"

# --------------------------
# FONT CONFIGURATION
# --------------------------
BASE_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"

try:
    if F_REG.exists() and F_BOLD.exists():
        pdfmetrics.registerFont(TTFont("NS", str(F_REG)))
        pdfmetrics.registerFont(TTFont("NSB", str(F_BOLD)))
        registerFontFamily("NS", normal="NS", bold="NSB", italic="NS", boldItalic="NSB")
        BASE_FONT = "NS"
        BOLD_FONT = "NSB"
        logger.info("✅ NotoSans fonts loaded successfully")
    else:
        logger.warning("⚠️ NotoSans fonts not found, using Helvetica fallback")
except Exception as e:
    logger.error(f"❌ Font loading failed: {e}")

# --------------------------
# BRAND COLORS
# --------------------------
BRAND = {
    "dark": colors.HexColor("#111827"),
    "blue": colors.HexColor("#1E4FA8"),
    "soft": colors.HexColor("#F3F4F6"),
    "bg": colors.HexColor("#F7FAFC"),
    "border": colors.HexColor("#E5E7EB"),
    "muted": colors.HexColor("#6B7280"),
}

# --------------------------
# LIMITS
# --------------------------
MAX_TEXT_LENGTH = 500
MAX_BIO_LENGTH = 30000
MAX_LIST_ITEMS = 40          # allow longer highlight lists
MAX_POLAROID_IMAGES = 10
MAX_IMAGE_SIZE_MB = 10


# ============================================================
# SAFE HELPERS
# ============================================================
def _safe_str(text: Optional[str], max_length: int) -> str:
    if text is None:
        return ""
    text = str(text)
    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\n\t")
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def _safe_list(items: Any, max_items: int) -> List[str]:
    """
    Accepts list[str] or string; returns clean list[str]
    (string is split into logical bullets by _coerce_bullets()).
    """
    if items is None:
        return []
    if isinstance(items, str):
        return _coerce_bullets(items, max_items=max_items)
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for it in items[:max_items]:
        s = _safe_str(it, MAX_TEXT_LENGTH)
        if s.strip():
            out.append(s.strip())
    return out


def _validate_data_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    required = ["client_name", "client_email", "quote_date", "total_price", "selected_plans"]
    for f in required:
        if f not in data:
            raise ValueError(f"Missing required field: {f}")
    if not isinstance(data.get("selected_plans"), list):
        raise ValueError("selected_plans must be a list")

    text_fields = [
        "client_name", "client_phone", "client_email", "location", "marketing_hook", "notes",
        "pet_name", "pet_species", "pet_breed", "pet_dob", "pet_microchip",
        "plan_1_name", "plan_1_provider", "plan_2_name", "plan_2_provider",
        "about_bio", "bulk_summary",
        "plan1_limit", "plan1_area", "plan2_limit", "plan2_area",
        "plan_1_price", "plan_2_price", "plan_1_price_total", "plan_2_price_total",
        "total_price", "quote_date",
    ]
    for f in text_fields:
        if f in data and data[f] is not None:
            lim = MAX_BIO_LENGTH if f == "about_bio" else MAX_TEXT_LENGTH
            data[f] = _safe_str(data[f], lim)

    list_fields = [
        "plan1_key_facts", "plan1_covers", "plan1_exclusions", "plan1_waiting",
        "plan2_key_facts", "plan2_covers", "plan2_exclusions", "plan2_waiting",
        "cii_titles", "official_eurolife", "official_interlife",
    ]
    for f in list_fields:
        # allow BOTH list[str] and "big string"
        if f in data and isinstance(data[f], str):
            data[f] = _coerce_bullets(data[f], max_items=MAX_LIST_ITEMS)
        elif f in data and isinstance(data[f], list):
            data[f] = [_safe_str(x, MAX_TEXT_LENGTH) for x in data[f][:MAX_LIST_ITEMS] if x]
        else:
            data[f] = data.get(f, []) if isinstance(data.get(f), list) else []

    # Images (optional)
    if "polaroid_images" in data:
        imgs = data["polaroid_images"]
        if not isinstance(imgs, list):
            data["polaroid_images"] = []
        else:
            outb: List[bytes] = []
            for b in imgs[:MAX_POLAROID_IMAGES]:
                if isinstance(b, (bytes, bytearray)) and b:
                    size_mb = len(b) / (1024 * 1024)
                    if size_mb <= MAX_IMAGE_SIZE_MB:
                        outb.append(bytes(b))
            data["polaroid_images"] = outb

    return data


# ============================================================
# TEXT / WRAP / PARAGRAPH SAFETY
# ============================================================
def _xml_escape(s: str) -> str:
    """
    ReportLab Paragraph uses XML-ish markup.
    If user text contains &, <, > it can break rendering.
    """
    s = "" if s is None else str(s)
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def _soft_breaks(s: str) -> str:
    """
    Adds zero-width break opportunities for long tokens inside narrow columns.
    """
    if not s:
        return ""
    zwsp = "\u200b"
    s = str(s)
    return (
        s.replace("/", f"/{zwsp}")
         .replace("-", f"-{zwsp}")
         .replace("–", f"–{zwsp}")
         .replace("|", f"|{zwsp}")
    )


def _wrap_by_width(text: str, font: str, size: float, max_width: float) -> List[str]:
    """
    Wrap using real measured width (stringWidth). Hard-breaks very long tokens.
    Used for CANVAS-only lines (titles, etc).
    """
    text = _safe_str(text, max_length=5000)
    if not text.strip():
        return [""]

    words = text.split()
    lines: List[str] = []
    line = ""

    def fits(s: str) -> bool:
        return pdfmetrics.stringWidth(s, font, size) <= max_width

    for w in words:
        trial = (line + " " + w).strip()
        if line and fits(trial):
            line = trial
            continue

        if not line and fits(w):
            line = w
            continue

        if line:
            lines.append(line)
            line = ""

        if fits(w):
            line = w
        else:
            chunk = ""
            for ch in w:
                if fits(chunk + ch):
                    chunk += ch
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            line = chunk

    if line:
        lines.append(line)

    return lines or [""]


def _coerce_bullets(text: str, max_items: int = 40) -> List[str]:
    """
    Takes a long multiline string (like the one you pasted) and converts it into
    bullet items. Continuation lines are appended to the previous bullet with <br/>.
    Supports:
    - Lines starting with •, -, *, 1., 2), etc -> new bullet
    - Otherwise -> continuation of previous bullet
    """
    raw = _safe_str(text, max_length=50000)
    lines = [ln.strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]

    items: List[str] = []
    bullet_re = re.compile(r"^(?:[•\-\*]|(\d+[\.\)])|[–])\s+")

    def start_new(line: str) -> bool:
        return bool(bullet_re.match(line))

    def strip_marker(line: str) -> str:
        return bullet_re.sub("", line).strip()

    for ln in lines:
        if start_new(ln) or not items:
            items.append(strip_marker(ln) if start_new(ln) else ln)
        else:
            # continuation
            items[-1] = (items[-1] + "<br/>" + ln).strip()

        if len(items) >= max_items:
            break

    return [it for it in items if it.strip()]


# ============================================================
# PAGE 2 CARD (PLATYPUS, NO OVERLAP)
# ============================================================
def _make_card_styles() -> Tuple[ParagraphStyle, ParagraphStyle, ParagraphStyle]:
    section_style = ParagraphStyle(
        name="SectionTitle",
        fontName=BOLD_FONT,
        fontSize=9.0,
        leading=11.5,
        textColor=BRAND["dark"],
        alignment=TA_LEFT,
        spaceBefore=6,
        spaceAfter=3,
    )
    bullet_style = ParagraphStyle(
        name="Bullet",
        fontName=BASE_FONT,
        fontSize=8.2,
        leading=13.2,
        textColor=BRAND["dark"],
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        name="Subtitle",
        fontName=BASE_FONT,
        fontSize=7.5,
        leading=10.5,
        textColor=BRAND["muted"],
        alignment=TA_LEFT,
        spaceAfter=5,
    )
    return section_style, bullet_style, subtitle_style


def _bullets_flow(items: Any, bullet_style: ParagraphStyle, max_items: int = 10) -> ListFlowable:
    items_list = _safe_list(items, max_items=max_items)
    flow: List[ListItem] = []
    for it in items_list:
        # SAFE Paragraph text: escape + soft breaks + preserve <br/> from coerce
        safe = _xml_escape(it)
        safe = safe.replace("&lt;br/&gt;", "<br/>")  # allow our internal br only
        safe = _soft_breaks(safe)
        p = Paragraph(safe, bullet_style)
        flow.append(ListItem(p, leftIndent=10, bulletText="•"))
    return ListFlowable(flow, leftIndent=10)


def _draw_plan_card_platypus(
    c: canvas.Canvas,
    x: float, y_top: float,
    w: float, h: float,
    title: str, subtitle: str,
    blocks: List[Tuple[str, Any]],
) -> None:
    """
    Robust plan card:
    - Canvas draws the card chrome
    - Platypus Frame lays out subtitle + sections + bullet lists
    => nothing overlaps, ever.
    """
    # Card chrome
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(x, y_top - h, w, h, 10, stroke=1, fill=1)

    # Taller header to accommodate wrapped titles (like EUROLIFE...)
    header_h = 22 * mm
    c.setFillColor(BRAND["bg"])
    c.roundRect(x, y_top - header_h, w, header_h, 10, stroke=0, fill=1)

    c.setFillColor(BRAND["blue"])
    c.roundRect(x, y_top - 4, w, 4, 2, stroke=0, fill=1)

    # Title (wrap by real width)
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.0)

    safe_title = _safe_str(title, 160)
    # Add soft breaks for separators so “EUROLIFE ... (EUROLIFE” can wrap nicely
    # (only affects wrap logic for long tokens)
    safe_title_wrappable = safe_title.replace("/", "/ ").replace("-", "- ").replace("–", "– ").replace("|", "| ")

    title_lines = _wrap_by_width(safe_title_wrappable, BOLD_FONT, 10.0, w - 12 * mm)
    # draw max 2 lines
    title_y = y_top - 8.2 * mm
    for line in title_lines[:2]:
        c.drawString(x + 6 * mm, title_y, line.strip())
        title_y -= 4.6 * mm

    # Story content (Platypus)
    section_style, bullet_style, subtitle_style = _make_card_styles()

    story: List[Any] = []
    sub = _xml_escape(_safe_str(subtitle, 300))
    sub = _soft_breaks(sub)
    story.append(Paragraph(sub, subtitle_style))

    for sec_title, sec_items in blocks:
        story.append(Paragraph(_xml_escape(_safe_str(sec_title, 80)), section_style))
        story.append(_bullets_flow(sec_items, bullet_style, max_items=14))

    # Frame area (below header)
    frame_x = x + 6 * mm
    frame_y = (y_top - h) + 8 * mm
    frame_w = w - 12 * mm
    frame_h = h - header_h - 10 * mm

    frame = Frame(frame_x, frame_y, frame_w, frame_h, showBoundary=0)
    kif = KeepInFrame(frame_w, frame_h, story, mode="shrink")  # shrink if too long
    frame.addFromList([kif], c)


# ============================================================
# DRAWING UTILITIES
# ============================================================
def _draw_header(c: canvas.Canvas, W: float, H: float, right_title: str) -> None:
    c.setFillColor(BRAND["dark"])
    c.rect(0, H - 20 * mm, W, 20 * mm, stroke=0, fill=1)

    if LOGO_PATH.exists():
        try:
            logo = ImageReader(str(LOGO_PATH))
            c.drawImage(
                logo, 14 * mm, H - 17 * mm,
                width=40 * mm, height=14 * mm,
                preserveAspectRatio=True, anchor="sw", mask="auto"
            )
        except Exception as e:
            logger.warning(f"Logo load failed: {e}")

    c.setFillColor(colors.white)
    c.setFont(BOLD_FONT, 13)
    c.drawRightString(W - 14 * mm, H - 12.5 * mm, _safe_str(right_title, 120))


def _draw_footer(c: canvas.Canvas, W: float) -> None:
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.setFont(BASE_FONT, 8.5)
    c.drawString(14 * mm, 12 * mm, "PETSHEALTH | www.petshealth.gr | info@petshealth.gr | +30 211 700 533")
    c.setFont(BASE_FONT, 7.5)
    c.drawRightString(W - 14 * mm, 12 * mm, "Because we care for your pets as much as you do")


def _draw_polaroid(
    c: canvas.Canvas,
    img_bytes: bytes,
    x: float, y: float,
    w: float, h: float,
    angle: float = 0,
) -> None:
    if not img_bytes:
        return
    pad = 3 * mm
    bottom_extra = 7 * mm
    try:
        img = ImageReader(io.BytesIO(img_bytes))
    except Exception:
        return

    c.saveState()
    cx, cy = x + w / 2, y + h / 2
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
    try:
        c.drawImage(img, img_x, img_y, img_w, img_h, preserveAspectRatio=True, anchor="c", mask="auto")
    except Exception:
        pass

    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 7.4)
    c.drawString(x + pad, y + 2.4 * mm, "PETSHEALTH")

    c.restoreState()


def _polaroids_for_page(data: Dict[str, Any], page_index: int) -> List[bytes]:
    imgs = data.get("polaroid_images", []) or []
    if not imgs:
        return []
    idx_a = (page_index - 1) % len(imgs)
    idx_b = page_index % len(imgs) if len(imgs) > 1 else None
    out = [imgs[idx_a]]
    if idx_b is not None:
        out.append(imgs[idx_b])
    return out


def _draw_page_polaroids(c: canvas.Canvas, W: float, H: float, data: Dict[str, Any], page_index: int) -> None:
    pimgs = _polaroids_for_page(data, page_index)
    if not pimgs:
        return
    y = 18 * mm
    w = 40 * mm
    h = 48 * mm
    _draw_polaroid(c, pimgs[0], 14 * mm, y, w, h, angle=-6)
    if len(pimgs) > 1:
        _draw_polaroid(c, pimgs[1], W - 14 * mm - w, y, w, h, angle=6)


# ============================================================
# PAGE 3 BULLETS (robust, never blank)
# ============================================================
def _create_platypus_bullets(items: Any, style: ParagraphStyle, max_items: int = 12) -> ListFlowable:
    items_list = _safe_list(items, max_items=max_items)
    flow: List[ListItem] = []
    for it in items_list:
        safe = _xml_escape(it)
        safe = safe.replace("&lt;br/&gt;", "<br/>")  # allow our internal br only
        safe = _soft_breaks(safe)
        p = Paragraph(safe, style)
        flow.append(ListItem(p, leftIndent=10, bulletText="•"))
    if not flow:
        # ensure something renders (prevents "blank box")
        p = Paragraph(_xml_escape("—"), style)
        flow.append(ListItem(p, leftIndent=10, bulletText="•"))
    return ListFlowable(flow, bulletType="bullet", leftIndent=10)


def _keep_in_frame(frame: Frame, story: List[Any], w: float, h: float, c: canvas.Canvas, shrink: bool = True) -> None:
    """
    Always renders something, and shrinks if needed instead of clipping/blanking.
    """
    try:
        if shrink:
            frame.addFromList([KeepInFrame(w, h, story, mode="shrink")], c)
        else:
            frame.addFromList(story, c)
    except Exception as e:
        logger.warning(f"KeepInFrame fallback used due to: {e}")
        # fallback: render a short safe paragraph
        fallback = Paragraph(_xml_escape("Content could not be rendered."), ParagraphStyle(
            name="Fallback",
            fontName=BASE_FONT,
            fontSize=9,
            leading=12,
            textColor=BRAND["dark"],
            alignment=TA_LEFT,
        ))
        frame.addFromList([fallback], c)


# ============================================================
# MAIN BUILDER
# ============================================================
def build_quote_pdf(data: Dict[str, Any]) -> bytes:
    logger.info("Starting PDF generation (v5 FINAL)...")
    data = _validate_data_dict(data)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    selected_plans = data.get("selected_plans", [])
    mode = data.get("quote_mode", "")
    try:
        pet_count = int(data.get("pet_count", 1) or 1)
    except Exception:
        pet_count = 1

    plan_1_name = data.get("plan_1_name", "")
    plan_1_provider = data.get("plan_1_provider", "")
    plan_2_name = data.get("plan_2_name", "")
    plan_2_provider = data.get("plan_2_provider", "")

    # ============================================
    # PAGE 1: QUOTE SUMMARY
    # ============================================
    c.setFillColor(BRAND["dark"])
    c.rect(0, H - 28 * mm, W, 28 * mm, stroke=0, fill=1)

    if LOGO_PATH.exists():
        try:
            logo = ImageReader(str(LOGO_PATH))
            c.drawImage(
                logo, 14 * mm, H - 24 * mm,
                width=45 * mm, height=18 * mm,
                preserveAspectRatio=True, anchor="sw", mask="auto"
            )
        except Exception:
            c.setFillColor(colors.white)
            c.setFont(BOLD_FONT, 15)
            c.drawString(14 * mm, H - 16 * mm, "PETSHEALTH – Pet Insurance Quotation")
    else:
        c.setFillColor(colors.white)
        c.setFont(BOLD_FONT, 15)
        c.drawString(14 * mm, H - 16 * mm, "PETSHEALTH – Pet Insurance Quotation")

    c.setFont(BASE_FONT, 9.5)
    c.setFillColor(colors.HexColor("#E5E7EB"))
    quote_date = data.get("quote_date", "")
    c.drawRightString(W - 14 * mm, H - 22 * mm, f"Quote Date: {quote_date}")

    c.setFillColor(BRAND["blue"])
    c.setFont(BOLD_FONT, 11.5)
    hook = _safe_str(data.get("marketing_hook", ""), 140)
    c.drawString(14 * mm, H - 36 * mm, hook)

    # Client summary box
    y = H - 60 * mm
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
    client_name = data.get("client_name", "")
    client_phone = data.get("client_phone", "")
    client_email = data.get("client_email", "")

    c.drawString(box_x + 8 * mm, y - 18 * mm, f"Client: {client_name}")
    c.drawString(box_x + 8 * mm, y - 26 * mm, f"Phone:  {client_phone}")
    c.drawString(box_x + 8 * mm, y - 34 * mm, f"Email:   {client_email}")

    location = data.get("location", "")
    if location:
        c.drawString(box_x + 8 * mm, y - 42 * mm, f"Location: {location}")

    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 9.5)

    if "Bulk" in mode:
        c.drawRightString(box_x + box_w - 8 * mm, y - 18 * mm, f"Pets: {pet_count} (Bulk quote)")
        bulk_summary = data.get("bulk_summary", "")
        if bulk_summary:
            c.setFont(BASE_FONT, 9)
            yyb = y - 42 * mm
            for line in bulk_summary.splitlines()[:4]:
                line = line.strip()
                if line:
                    c.drawString(box_x + 8 * mm, yyb, _safe_str(line, 140))
                    yyb -= 11
    else:
        pet_name = data.get("pet_name", "")
        pet_species = data.get("pet_species", "")
        pet_breed = data.get("pet_breed", "")
        pet_dob = data.get("pet_dob", "")
        pet_microchip = data.get("pet_microchip", "")

        c.drawRightString(box_x + box_w - 8 * mm, y - 18 * mm, f"Pet: {pet_name} ({pet_species})")
        c.drawRightString(box_x + box_w - 8 * mm, y - 26 * mm, f"Breed: {pet_breed}")
        c.drawRightString(box_x + box_w - 8 * mm, y - 34 * mm, f"DOB: {pet_dob} | Microchip: {pet_microchip}")

    # Recommended options
    y2 = y - box_h - 10 * mm
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 12)
    c.drawString(14 * mm, y2, "Recommended Options")
    y2 -= 8 * mm

    c.setFont(BASE_FONT, 10)
    if "PET CARE PLUS (INTERLIFE)" in selected_plans:
        c.drawString(14 * mm, y2, f"• {plan_1_name} – {plan_1_provider}")
        y2 -= 6 * mm
    if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
        c.drawString(14 * mm, y2, f"• {plan_2_name} – {plan_2_provider}")
        y2 -= 6 * mm

    # Pricing card
    y3 = y2 - 10 * mm
    card_x = 14 * mm
    card_w = W - 28 * mm
    card_h = 52 * mm

    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(card_x, y3 - card_h, card_w, card_h, 10, stroke=1, fill=1)

    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 11)
    c.drawString(card_x + 8 * mm, y3 - 10 * mm, "Pricing Summary")
    c.setFont(BASE_FONT, 10)
    c.drawRightString(card_x + card_w - 8 * mm, y3 - 10 * mm, "Annual Premium (€)")

    yy = y3 - 24 * mm
    line_gap = 11 * mm

    plan_1_price_total = data.get("plan_1_price_total", "")
    plan_2_price_total = data.get("plan_2_price_total", "")

    if "PET CARE PLUS (INTERLIFE)" in selected_plans:
        c.setFillColor(BRAND["muted"])
        c.setFont(BASE_FONT, 10)
        c.drawString(card_x + 8 * mm, yy, _safe_str(plan_1_name, 40))
        c.setFillColor(BRAND["dark"])
        c.setFont(BOLD_FONT, 10.5)
        c.drawRightString(card_x + card_w - 8 * mm, yy, _safe_str(plan_1_price_total, 20))
        yy -= line_gap

    if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
        c.setFillColor(BRAND["muted"])
        c.setFont(BASE_FONT, 10)
        c.drawString(card_x + 8 * mm, yy, _safe_str(plan_2_name, 40))
        c.setFillColor(BRAND["dark"])
        c.setFont(BOLD_FONT, 10.5)
        c.drawRightString(card_x + card_w - 8 * mm, yy, _safe_str(plan_2_price_total, 20))

    total_bar_h = 13 * mm
    c.setFillColor(BRAND["blue"])
    c.roundRect(card_x, y3 - card_h, card_w, total_bar_h, 10, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(BOLD_FONT, 12.5)
    c.drawString(card_x + 8 * mm, y3 - card_h + 4.5 * mm, "Total Annual Premium")
    total_price = data.get("total_price", "")
    c.drawRightString(card_x + card_w - 8 * mm, y3 - card_h + 4.5 * mm, _safe_str(total_price, 24))

    # Notes / Disclaimer (wrapped, stops before footer)
    y4 = y3 - card_h - 8 * mm
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.5)
    c.drawString(14 * mm, y4, "Notes / Disclaimer")
    y4 -= 6 * mm

    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 9)
    notes = data.get("notes", "")
    notes_width = W - 28 * mm
    for line in _wrap_by_width(notes, BASE_FONT, 9, notes_width):
        if y4 < 26 * mm:
            break
        c.drawString(14 * mm, y4, line)
        y4 -= 11

    _draw_page_polaroids(c, W, H, data, page_index=1)
    _draw_footer(c, W)

    # ============================================
    # PAGE 2: COVERAGE DETAILS (NO OVERLAP)
    # ============================================
    c.showPage()
    _draw_header(c, W, H, "Plan Coverage Summary")

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
            title = f"{plan_1_name} ({plan_1_provider})"
            subtitle = f"€{data.get('plan_1_price','')}/year | Limit: {data.get('plan1_limit','')} | Area: {data.get('plan1_area','')}"
            blocks = [
                ("Key Facts", data.get("plan1_key_facts", [])),
                ("Covers (Summary)", data.get("plan1_covers", [])),
                ("Not Covered (Indicative)", data.get("plan1_exclusions", [])),
                ("Waiting Periods", data.get("plan1_waiting", [])),
            ]
        else:
            title = f"{plan_2_name} ({plan_2_provider})"
            subtitle = f"Unlimited (in-network) | Area: {data.get('plan2_area','')}"
            blocks = [
                ("Key Facts", data.get("plan2_key_facts", [])),
                ("Covers (Summary)", data.get("plan2_covers", [])),
                ("Not Covered (Indicative)", data.get("plan2_exclusions", [])),
                ("Waiting Periods", data.get("plan2_waiting", [])),
            ]

        _draw_plan_card_platypus(c, x, y_top, w, h, title, subtitle, blocks)

    else:
        gap = 8 * mm
        card_w = (W - 28 * mm - gap) / 2
        card_h = 170 * mm
        x1 = 14 * mm
        x2 = x1 + card_w + gap
        y_top = top

        if "PET CARE PLUS (INTERLIFE)" in selected_plans:
            title = f"{plan_1_name} ({plan_1_provider})"
            subtitle = f"€{data.get('plan_1_price','')}/year | Limit: {data.get('plan1_limit','')} | Area: {data.get('plan1_area','')}"
            blocks = [
                ("Key Facts", data.get("plan1_key_facts", [])),
                ("Covers (Summary)", data.get("plan1_covers", [])),
                ("Not Covered (Indicative)", data.get("plan1_exclusions", [])),
                ("Waiting Periods", data.get("plan1_waiting", [])),
            ]
            _draw_plan_card_platypus(c, x1, y_top, card_w, card_h, title, subtitle, blocks)

        if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
            # IMPORTANT: long provider names will WRAP now
            title = f"{plan_2_name} ({plan_2_provider})"
            subtitle = f"Unlimited (in-network) | Area: {data.get('plan2_area','')}"
            blocks = [
                ("Key Facts", data.get("plan2_key_facts", [])),
                ("Covers (Summary)", data.get("plan2_covers", [])),
                ("Not Covered (Indicative)", data.get("plan2_exclusions", [])),
                ("Waiting Periods", data.get("plan2_waiting", [])),
            ]
            _draw_plan_card_platypus(c, x2, y_top, card_w, card_h, title, subtitle, blocks)

    _draw_page_polaroids(c, W, H, data, page_index=2)
    _draw_footer(c, W)

    # ============================================
    # PAGE 3: ABOUT & OFFICIAL HIGHLIGHTS
    # ============================================
    c.showPage()
    _draw_header(c, W, H, "About & Official Highlights")

    body_style = ParagraphStyle(
        name="Body",
        fontName=BASE_FONT,
        fontSize=9.3,
        leading=12.8,
        textColor=BRAND["dark"],
        alignment=TA_LEFT,
    )
    small_style = ParagraphStyle(
        name="Small",
        fontName=BASE_FONT,
        fontSize=9.0,
        leading=12.2,
        textColor=BRAND["dark"],
        alignment=TA_LEFT,
    )

    margin_x = 14 * mm
    top_y = H - 30 * mm

    # Trust banner
    c.setFillColor(BRAND["bg"])
    c.setStrokeColor(BRAND["border"])
    c.roundRect(margin_x, top_y - 12 * mm, W - 2 * margin_x, 12 * mm, 8, stroke=1, fill=1)
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.2)
    c.drawString(margin_x + 6 * mm, top_y - 8.3 * mm, "Trust: SAFE PET (2016)  •  Pet Insurance advisor  •  CII certified (PL4, W01)")
    top_y -= 16 * mm

    # About advisor box (no truncation from builder side)
    box1_h = 92 * mm
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(BRAND["bg"])
    c.roundRect(margin_x, top_y - box1_h, W - 2 * margin_x, box1_h, 10, stroke=1, fill=1)
    c.setFillColor(BRAND["blue"])
    c.roundRect(margin_x, top_y - 4, W - 2 * margin_x, 4, 2, stroke=0, fill=1)

    c.setFont(BOLD_FONT, 14)
    c.setFillColor(BRAND["dark"])
    c.drawString(margin_x + 6 * mm, top_y - 12 * mm, "About the Advisor")

    bio = _safe_str(data.get("about_bio", "") or "", MAX_BIO_LENGTH).strip()
    if not bio:
        bio = "Professional pet insurance advisor. Contact us for more information."

    bio_safe = _xml_escape(bio).replace("\n", "<br/>")
    bio_safe = _soft_breaks(bio_safe)
    bio_par = Paragraph(bio_safe, body_style)

    bio_frame_x = margin_x + 6 * mm
    bio_frame_y = top_y - box1_h + 8 * mm
    bio_frame_w = W - 2 * margin_x - 12 * mm
    bio_frame_h = box1_h - 24 * mm
    bio_frame = Frame(bio_frame_x, bio_frame_y, bio_frame_w, bio_frame_h, showBoundary=0)
    _keep_in_frame(bio_frame, [bio_par], bio_frame_w, bio_frame_h, c, shrink=False)

    # Credentials box
    box2_top = top_y - box1_h - 8 * mm
    box2_h = 30 * mm
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(margin_x, box2_top - box2_h, W - 2 * margin_x, box2_h, 10, stroke=1, fill=1)

    c.setFont(BOLD_FONT, 12)
    c.setFillColor(BRAND["dark"])
    c.drawString(margin_x + 6 * mm, box2_top - 10 * mm, "Credentials (CII)")

    cii = data.get("cii_titles", [])
    if not cii:
        cii = ["CII Certified Pet Insurance Professional"]
    cii_flow = _create_platypus_bullets(cii, small_style, max_items=6)

    cii_frame_x = margin_x + 6 * mm
    cii_frame_y = box2_top - box2_h + 6 * mm
    cii_frame_w = W - 2 * margin_x - 12 * mm
    cii_frame_h = box2_h - 18 * mm
    cii_frame = Frame(cii_frame_x, cii_frame_y, cii_frame_w, cii_frame_h, showBoundary=0)
    _keep_in_frame(cii_frame, [cii_flow], cii_frame_w, cii_frame_h, c, shrink=True)

    # Official highlights (two columns)
    box3_top = box2_top - box2_h - 10 * mm
    box3_h = 70 * mm

    c.setFont(BOLD_FONT, 12.5)
    c.setFillColor(BRAND["dark"])
    c.drawString(margin_x, box3_top, "Official Highlights (Editable)")
    box3_top -= 6 * mm

    gap = 8 * mm
    col_w = (W - 2 * margin_x - gap) / 2

    # EUROLIFE column
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(margin_x, box3_top - box3_h, col_w, box3_h, 10, stroke=1, fill=1)
    c.setFillColor(BRAND["soft"])
    c.roundRect(margin_x, box3_top - 12 * mm, col_w, 12 * mm, 10, stroke=0, fill=1)
    c.setFont(BOLD_FONT, 10.8)
    c.setFillColor(BRAND["dark"])
    c.drawString(margin_x + 6 * mm, box3_top - 8 * mm, "EUROLIFE – My Happy Pet")

    eu = data.get("official_eurolife", [])
    if not eu:
        eu = [
            "Προγραμμάτισε την επίσκεψη σου στα γραφεία μας μέσω της εφαρμογής Book Your Visit",
            "Προστάτεψε αποτελεσματικά τον πιο χνουδωτό σου φίλο από 75€/ χρόνο",
        ]
    eu_flow = _create_platypus_bullets(eu, small_style, max_items=18)
    eu_frame_x = margin_x + 6 * mm
    eu_frame_y = box3_top - box3_h + 6 * mm
    eu_frame_w = col_w - 12 * mm
    eu_frame_h = box3_h - 20 * mm
    eu_frame = Frame(eu_frame_x, eu_frame_y, eu_frame_w, eu_frame_h, showBoundary=0)
    _keep_in_frame(eu_frame, [eu_flow], eu_frame_w, eu_frame_h, c, shrink=True)

    # INTERLIFE column
    xr = margin_x + col_w + gap
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(xr, box3_top - box3_h, col_w, box3_h, 10, stroke=1, fill=1)
    c.setFillColor(BRAND["soft"])
    c.roundRect(xr, box3_top - 12 * mm, col_w, 12 * mm, 10, stroke=0, fill=1)
    c.setFont(BOLD_FONT, 10.8)
    c.setFillColor(BRAND["dark"])
    c.drawString(xr + 6 * mm, box3_top - 8 * mm, "INTERLIFE – PET CARE")

    it = data.get("official_interlife", [])
    if not it:
        it = [
            "Όταν αγαπώ… προσφέρω, φροντίζω, προνοώ!",
            "Ουσιαστική κάλυψη έναντι ατυχημάτων ή/και ασθενειών σε σκύλους, ανεξαρτήτως ράτσας.",
            "Νοσηλεία • Εξετάσεις • Αμοιβές Ιατρών • Θεραπείες & Χειρουργικές Επεμβάσεις",
        ]
    it_flow = _create_platypus_bullets(it, small_style, max_items=18)
    it_frame_x = xr + 6 * mm
    it_frame_y = box3_top - box3_h + 6 * mm
    it_frame_w = col_w - 12 * mm
    it_frame_h = box3_h - 20 * mm
    it_frame = Frame(it_frame_x, it_frame_y, it_frame_w, it_frame_h, showBoundary=0)
    _keep_in_frame(it_frame, [it_flow], it_frame_w, it_frame_h, c, shrink=True)

    _draw_page_polaroids(c, W, H, data, page_index=3)
    _draw_footer(c, W)

    c.save()
    pdf_bytes = buf.getvalue()
    logger.info(f"✅ PDF generated successfully: {len(pdf_bytes)} bytes")
    return pdf_bytes
