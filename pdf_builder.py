"""
PETSHEALTH Quote Engine - Secure PDF Builder (IMPROVED v2)
Professional PDF generation with comprehensive security and validation

IMPROVEMENTS v2 (2026-01-14):
- FIXED: Increased line spacing in plan cards bullets (10.5 → 12)
- FIXED: Better subtitle text wrapping for narrow columns
- FIXED: Larger "About the Advisor" box to prevent text cutoff

IMPROVEMENTS v1:
- Increased line spacing in plan cards (page 2)
- Text wrapping for long subtitles
- Better layout for dual-column cards
"""
import io
import logging
from pathlib import Path
from typing import Optional

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
    # Fallback to Helvetica

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
# SECURITY LIMITS
# --------------------------
MAX_TEXT_LENGTH = 500
MAX_LIST_ITEMS = 20
MAX_POLAROID_IMAGES = 10
MAX_IMAGE_SIZE_MB = 10


# --------------------------
# INPUT VALIDATION
# --------------------------

def _validate_data_dict(data: dict) -> dict:
    """
    Validate and sanitize the input data dictionary.

    Args:
        data: Input data for PDF generation

    Returns:
        Validated data dictionary

    Raises:
        ValueError: If required fields are missing or invalid
    """
    required_fields = [
        "client_name", "client_email", "quote_date",
        "total_price", "selected_plans"
    ]

    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    # Validate selected_plans is a list
    if not isinstance(data.get("selected_plans"), list):
        raise ValueError("selected_plans must be a list")

    # Ensure all text fields are strings
    text_fields = [
        "client_name", "client_phone", "client_email", "location",
        "marketing_hook", "notes", "pet_name", "pet_species", "pet_breed",
        "pet_dob", "pet_microchip", "plan_1_name", "plan_1_provider",
        "plan_2_name", "plan_2_provider", "about_bio"
    ]

    for field in text_fields:
        if field in data and data[field] is not None:
            data[field] = str(data[field])[:MAX_TEXT_LENGTH]

    # Validate list fields
    list_fields = [
        "plan1_key_facts", "plan1_covers", "plan1_exclusions", "plan1_waiting",
        "plan2_key_facts", "plan2_covers", "plan2_exclusions", "plan2_waiting",
        "cii_titles", "official_eurolife", "official_interlife"
    ]

    for field in list_fields:
        if field in data:
            if not isinstance(data[field], list):
                data[field] = []
            else:
                # Limit list size and sanitize items
                data[field] = [
                    str(item)[:MAX_TEXT_LENGTH]
                    for item in data[field][:MAX_LIST_ITEMS]
                ]

    # Validate polaroid images
    if "polaroid_images" in data:
        if not isinstance(data["polaroid_images"], list):
            data["polaroid_images"] = []
        else:
            images = data["polaroid_images"][:MAX_POLAROID_IMAGES]
            validated_images = []

            for img in images:
                if isinstance(img, bytes) and img:
                    # Check size
                    size_mb = len(img) / (1024 * 1024)
                    if size_mb <= MAX_IMAGE_SIZE_MB:
                        validated_images.append(img)
                    else:
                        logger.warning(f"Image too large: {size_mb:.1f}MB, skipping")

            data["polaroid_images"] = validated_images

    logger.info(f"Data validation passed: {len(data.get('selected_plans', []))} plans")
    return data


def _safe_str(text: Optional[str], max_length: int = MAX_TEXT_LENGTH) -> str:
    """
    Safely convert to string and truncate if needed.

    Args:
        text: Input text
        max_length: Maximum allowed length

    Returns:
        Safe string
    """
    if text is None:
        return ""

    text = str(text)

    # Remove control characters except newlines and tabs
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')

    if len(text) > max_length:
        text = text[:max_length - 3] + "..."

    return text


def _safe_list(items: Optional[list], max_items: int = MAX_LIST_ITEMS) -> list:
    """
    Safely convert to list and limit size.

    Args:
        items: Input list
        max_items: Maximum number of items

    Returns:
        Safe list
    """
    if not items:
        return []

    if not isinstance(items, list):
        return []

    return [_safe_str(item) for item in items[:max_items] if item]


# --------------------------
# TEXT WRAPPING
# --------------------------

def _wrap_words(text: str, max_chars: int) -> list[str]:
    """
    Wrap text to fit within character limit per line.

    Args:
        text: Input text
        max_chars: Maximum characters per line

    Returns:
        List of wrapped lines
    """
    text = _safe_str(text, max_length=1000)
    words = text.split()

    if not words:
        return [""]

    lines = []
    current_line = ""

    for word in words:
        trial = (current_line + " " + word).strip()

        if len(trial) <= max_chars:
            current_line = trial
        else:
            if current_line:
                lines.append(current_line)
            current_line = word[:max_chars]  # Truncate long words

    if current_line:
        lines.append(current_line)

    return lines if lines else [""]


# --------------------------
# PDF DRAWING UTILITIES
# --------------------------

def _draw_header(c: canvas.Canvas, W: float, H: float, right_title: str):
    """
    Draw page header with logo and title.

    Args:
        c: Canvas object
        W: Page width
        H: Page height
        right_title: Title text for right side
    """
    # Dark header bar
    c.setFillColor(BRAND["dark"])
    c.rect(0, H - 20 * mm, W, 20 * mm, stroke=0, fill=1)

    # Logo
    if LOGO_PATH.exists():
        try:
            logo = ImageReader(str(LOGO_PATH))
            c.drawImage(
                logo, 14 * mm, H - 17 * mm,
                width=40 * mm, height=14 * mm,
                preserveAspectRatio=True, anchor='sw', mask='auto'
            )
        except Exception as e:
            logger.warning(f"Failed to load logo: {e}")

    # Title text
    c.setFillColor(colors.white)
    c.setFont(BOLD_FONT, 13)
    safe_title = _safe_str(right_title, max_length=100)
    c.drawRightString(W - 14 * mm, H - 12.5 * mm, safe_title)


def _draw_footer(c: canvas.Canvas, W: float):
    """
    Draw page footer with contact info.

    Args:
        c: Canvas object
        W: Page width
    """
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.setFont(BASE_FONT, 8.5)
    c.drawString(
        14 * mm, 12 * mm,
        "PETSHEALTH | www.petshealth.gr | info@petshealth.gr | +30 211 700 533"
    )
    c.setFont(BASE_FONT, 7.5)
    c.drawRightString(
        W - 14 * mm, 12 * mm,
        "Because we care for your pets as much as you do"
    )


def _draw_polaroid(
        c: canvas.Canvas,
        img_bytes: bytes,
        x: float, y: float,
        w: float, h: float,
        angle: float = 0
):
    """
    Draw a polaroid-style image with shadow and label.

    Args:
        c: Canvas object
        img_bytes: Image data as bytes
        x, y: Position
        w, h: Size
        angle: Rotation angle
    """
    if not img_bytes:
        return

    pad = 3 * mm
    bottom_extra = 7 * mm

    try:
        img = ImageReader(io.BytesIO(img_bytes))
    except Exception as e:
        logger.warning(f"Failed to load polaroid image: {e}")
        return

    c.saveState()

    # Rotate around center
    cx = x + w / 2
    cy = y + h / 2
    c.translate(cx, cy)
    c.rotate(angle)
    c.translate(-cx, -cy)

    # Shadow
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.12))
    c.roundRect(x + 1.2 * mm, y - 1.2 * mm, w, h, 6, stroke=0, fill=1)

    # Polaroid frame
    c.setFillColor(colors.white)
    c.setStrokeColor(BRAND["border"])
    c.roundRect(x, y, w, h, 7, stroke=1, fill=1)

    # Image
    img_x = x + pad
    img_y = y + pad + bottom_extra
    img_w = w - 2 * pad
    img_h = h - 2 * pad - bottom_extra

    try:
        c.drawImage(
            img, img_x, img_y, img_w, img_h,
            preserveAspectRatio=True, anchor='c', mask='auto'
        )
    except Exception as e:
        logger.warning(f"Failed to draw polaroid image: {e}")

    # Label
    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 7.4)
    c.drawString(x + pad, y + 2.4 * mm, "PETSHEALTH")

    c.restoreState()


def _polaroids_for_page(data: dict, page_index: int) -> list[bytes]:
    """
    Get polaroid images for a specific page.

    Args:
        data: Data dictionary
        page_index: Page number (1-indexed)

    Returns:
        List of image bytes (max 2)
    """
    imgs = data.get("polaroid_images", []) or []
    if not imgs:
        return []

    # Rotate through images
    idx_a = (page_index - 1) % len(imgs)
    idx_b = page_index % len(imgs) if len(imgs) > 1 else None

    result = [imgs[idx_a]]
    if idx_b is not None:
        result.append(imgs[idx_b])

    return result


def _draw_page_polaroids(
        c: canvas.Canvas,
        W: float, H: float,
        data: dict,
        page_index: int
):
    """
    Draw polaroids on a page.

    Args:
        c: Canvas object
        W: Page width
        H: Page height
        data: Data dictionary
        page_index: Page number
    """
    pimgs = _polaroids_for_page(data, page_index)
    if not pimgs:
        return

    y = 18 * mm
    w = 40 * mm
    h = 48 * mm

    # Left polaroid
    _draw_polaroid(c, pimgs[0], 14 * mm, y, w, h, angle=-6)

    # Right polaroid
    if len(pimgs) > 1:
        _draw_polaroid(c, pimgs[1], W - 14 * mm - w, y, w, h, angle=6)


def _draw_bullet_block(
        c: canvas.Canvas,
        x: float, y: float,
        items: list[str],
        max_chars: int = 52,
        leading: float = 12,  # FIXED: Increased from 10.5 to 12
        size: float = 8.2
) -> float:
    """
    Draw a block of bulleted text.

    Args:
        c: Canvas object
        x, y: Starting position
        items: List of bullet items
        max_chars: Max characters per line
        leading: Line spacing (FIXED: now 12 for better readability)
        size: Font size

    Returns:
        Final y position
    """
    c.setFont(BASE_FONT, size)
    c.setFillColor(BRAND["dark"])

    yy = y
    items = _safe_list(items, max_items=10)

    for item in items:
        if not item:
            continue

        lines = _wrap_words(item, max_chars)
        for i, line in enumerate(lines):
            prefix = "• " if i == 0 else "  "
            c.drawString(x, yy, prefix + line)
            yy -= leading

    return yy


def _draw_plan_card(
        c: canvas.Canvas,
        x: float, y_top: float,
        w: float, h: float,
        title: str, subtitle: str,
        blocks: list[tuple[str, list[str]]]
):
    """
    Draw a plan coverage card with improved spacing and text wrapping.

    FIXED v2: Better subtitle wrapping for narrow columns

    Args:
        c: Canvas object
        x, y_top: Position (top-left corner)
        w, h: Size
        title: Card title
        subtitle: Card subtitle
        blocks: List of (section_title, bullet_items) tuples
    """
    # Card border
    c.setStrokeColor(BRAND["border"])
    c.setFillColor(colors.white)
    c.roundRect(x, y_top - h, w, h, 10, stroke=1, fill=1)

    # Header section - increased height for wrapped subtitle
    header_h = 16 * mm  # Increased from 14mm
    c.setFillColor(BRAND["bg"])
    c.roundRect(x, y_top - header_h, w, header_h, 10, stroke=0, fill=1)

    # Top accent bar
    c.setFillColor(BRAND["blue"])
    c.roundRect(x, y_top - 4, w, 4, 2, stroke=0, fill=1)

    # Title
    c.setFillColor(BRAND["dark"])
    c.setFont(BOLD_FONT, 10.0)
    safe_title = _safe_str(title, max_length=80)
    c.drawString(x + 6 * mm, y_top - 8.2 * mm, safe_title)

    # Subtitle with text wrapping - FIXED v2: Dynamic calculation
    c.setFillColor(BRAND["muted"])
    c.setFont(BASE_FONT, 7.5)  # Slightly smaller font
    safe_subtitle = _safe_str(subtitle, max_length=150)

    # FIXED: Better calculation for narrow columns
    # Use actual card width in mm, divide by average char width (2.2mm for 7.5pt font)
    usable_width_mm = w - 12 * mm  # Card width minus padding
    avg_char_width = 2.2  # mm per character at 7.5pt
    card_w_chars = max(20, int(usable_width_mm / avg_char_width))  # Min 20 chars

    subtitle_lines = _wrap_words(safe_subtitle, card_w_chars)

    subtitle_y = y_top - 11.5 * mm
    for sub_line in subtitle_lines[:2]:  # Max 2 lines for subtitle
        c.drawString(x + 6 * mm, subtitle_y, sub_line)
        subtitle_y -= 8

    # Content sections - INCREASED LINE SPACING (v1)
    yy = y_top - 20 * mm  # Adjusted start position

    for section_title, bullet_items in blocks:
        bullet_items = _safe_list(bullet_items, max_items=6)

        # Section title
        c.setFillColor(BRAND["dark"])
        c.setFont(BOLD_FONT, 9.0)
        safe_section = _safe_str(section_title, max_length=50)
        c.drawString(x + 6 * mm, yy, safe_section)
        yy -= 5

        # Bullets with INCREASED line spacing (12 - FIXED v2)
        yy = _draw_bullet_block(
            c, x + 8 * mm, yy,
            bullet_items,
            max_chars=card_w_chars - 5, leading=12, size=8.2  # FIXED: Use dynamic chars
        )
        yy -= 5


def _create_platypus_bullets(
        items: list[str],
        style: ParagraphStyle,
        max_items: int = 10
) -> ListFlowable:
    """
    Create a platypus ListFlowable for complex layouts.

    Args:
        items: List of items
        style: Paragraph style
        max_items: Maximum items

    Returns:
        ListFlowable object
    """
    items = _safe_list(items, max_items=max_items)
    flow = []

    for item in items:
        if not item:
            continue
        p = Paragraph(item, style)
        flow.append(ListItem(p, leftIndent=10, bulletText="•", value="•"))

    return ListFlowable(flow, bulletType="bullet", leftIndent=10)


# --------------------------
# MAIN PDF BUILDER
# --------------------------

def build_quote_pdf(data: dict) -> bytes:
    """
    Build a professional PDF quote from data dictionary.

    Args:
        data: Dictionary containing all quote data

    Returns:
        PDF as bytes

    Raises:
        ValueError: If required data is missing or invalid
        Exception: If PDF generation fails
    """
    logger.info("Starting PDF generation...")

    try:
        # Validate input data
        data = _validate_data_dict(data)

        # Create PDF buffer
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        W, H = A4

        selected_plans = data.get("selected_plans", [])
        mode = data.get("quote_mode", "")
        pet_count = int(data.get("pet_count", 1))

        logger.info(f"Generating PDF: {len(selected_plans)} plans, mode={mode}")

        # ============================================
        # PAGE 1: QUOTE SUMMARY
        # ============================================

        # Header
        c.setFillColor(BRAND["dark"])
        c.rect(0, H - 28 * mm, W, 28 * mm, stroke=0, fill=1)

        # Logo
        if LOGO_PATH.exists():
            try:
                logo = ImageReader(str(LOGO_PATH))
                c.drawImage(
                    logo, 14 * mm, H - 24 * mm,
                    width=45 * mm, height=18 * mm,
                    preserveAspectRatio=True, anchor='sw', mask='auto'
                )
            except Exception as e:
                logger.warning(f"Logo failed, using text: {e}")
                c.setFillColor(colors.white)
                c.setFont(BOLD_FONT, 15)
                c.drawString(14 * mm, H - 16 * mm, "PETSHEALTH – Pet Insurance Quotation")
        else:
            c.setFillColor(colors.white)
            c.setFont(BOLD_FONT, 15)
            c.drawString(14 * mm, H - 16 * mm, "PETSHEALTH – Pet Insurance Quotation")

        # Quote date
        c.setFont(BASE_FONT, 9.5)
        c.setFillColor(colors.HexColor("#E5E7EB"))
        quote_date = _safe_str(data.get("quote_date", ""), max_length=20)
        c.drawRightString(W - 14 * mm, H - 22 * mm, f"Quote Date: {quote_date}")

        # Marketing hook
        c.setFillColor(BRAND["blue"])
        c.setFont(BOLD_FONT, 11.5)
        hook = _safe_str(data.get("marketing_hook", ""), max_length=110)
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

        # Client details
        c.setFont(BASE_FONT, 10)
        c.setFillColor(BRAND["dark"])
        client_name = _safe_str(data.get("client_name", ""), max_length=50)
        client_phone = _safe_str(data.get("client_phone", ""), max_length=20)
        client_email = _safe_str(data.get("client_email", ""), max_length=50)

        c.drawString(box_x + 8 * mm, y - 18 * mm, f"Client: {client_name}")
        c.drawString(box_x + 8 * mm, y - 26 * mm, f"Phone:  {client_phone}")
        c.drawString(box_x + 8 * mm, y - 34 * mm, f"Email:   {client_email}")

        location = _safe_str(data.get("location", ""), max_length=50)
        if location:
            c.drawString(box_x + 8 * mm, y - 42 * mm, f"Location: {location}")

        # Pet details
        c.setFillColor(BRAND["muted"])
        c.setFont(BASE_FONT, 9.5)

        if "Bulk" in mode:
            c.drawRightString(
                box_x + box_w - 8 * mm, y - 18 * mm,
                f"Pets: {pet_count} (Bulk quote)"
            )
            bulk_summary = _safe_str(data.get("bulk_summary", ""), max_length=300)
            if bulk_summary:
                c.setFont(BASE_FONT, 9)
                yyb = y - 42 * mm
                for line in bulk_summary.splitlines()[:4]:
                    line = _safe_str(line, max_length=120)
                    if line:
                        c.drawString(box_x + 8 * mm, yyb, line)
                        yyb -= 11
        else:
            pet_name = _safe_str(data.get("pet_name", ""), max_length=30)
            pet_species = _safe_str(data.get("pet_species", ""), max_length=20)
            pet_breed = _safe_str(data.get("pet_breed", ""), max_length=30)
            pet_dob = _safe_str(data.get("pet_dob", ""), max_length=15)
            pet_microchip = _safe_str(data.get("pet_microchip", ""), max_length=20)

            c.drawRightString(
                box_x + box_w - 8 * mm, y - 18 * mm,
                f"Pet: {pet_name} ({pet_species})"
            )
            c.drawRightString(box_x + box_w - 8 * mm, y - 26 * mm, f"Breed: {pet_breed}")
            c.drawRightString(
                box_x + box_w - 8 * mm, y - 34 * mm,
                f"DOB: {pet_dob} | Microchip: {pet_microchip}"
            )

        # Recommended options
        y2 = y - box_h - 10 * mm
        c.setFillColor(BRAND["dark"])
        c.setFont(BOLD_FONT, 12)
        c.drawString(14 * mm, y2, "Recommended Options")
        y2 -= 8 * mm

        c.setFont(BASE_FONT, 10)
        plan_1_name = _safe_str(data.get("plan_1_name", ""), max_length=50)
        plan_1_provider = _safe_str(data.get("plan_1_provider", ""), max_length=30)
        plan_2_name = _safe_str(data.get("plan_2_name", ""), max_length=50)
        plan_2_provider = _safe_str(data.get("plan_2_provider", ""), max_length=30)

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
        c.drawRightString(
            card_x + card_w - 8 * mm, y3 - 10 * mm,
            "Annual Premium (€)"
        )

        # Plan prices
        yy = y3 - 24 * mm
        line_gap = 11 * mm

        plan_1_price_total = _safe_str(data.get("plan_1_price_total", ""), max_length=20)
        plan_2_price_total = _safe_str(data.get("plan_2_price_total", ""), max_length=20)

        if "PET CARE PLUS (INTERLIFE)" in selected_plans:
            c.setFillColor(BRAND["muted"])
            c.setFont(BASE_FONT, 10)
            c.drawString(card_x + 8 * mm, yy, plan_1_name)
            c.setFillColor(BRAND["dark"])
            c.setFont(BOLD_FONT, 10.5)
            c.drawRightString(card_x + card_w - 8 * mm, yy, plan_1_price_total)
            yy -= line_gap

        if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
            c.setFillColor(BRAND["muted"])
            c.setFont(BASE_FONT, 10)
            c.drawString(card_x + 8 * mm, yy, plan_2_name)
            c.setFillColor(BRAND["dark"])
            c.setFont(BOLD_FONT, 10.5)
            c.drawRightString(card_x + card_w - 8 * mm, yy, plan_2_price_total)

        # Total bar
        total_bar_h = 13 * mm
        c.setFillColor(BRAND["blue"])
        c.roundRect(card_x, y3 - card_h, card_w, total_bar_h, 10, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(BOLD_FONT, 12.5)
        c.drawString(card_x + 8 * mm, y3 - card_h + 4.5 * mm, "Total Annual Premium")

        total_price = _safe_str(data.get("total_price", ""), max_length=20)
        c.drawRightString(card_x + card_w - 8 * mm, y3 - card_h + 4.5 * mm, total_price)

        # Notes
        y4 = y3 - card_h - 8 * mm
        c.setFillColor(BRAND["dark"])
        c.setFont(BOLD_FONT, 10.5)
        c.drawString(14 * mm, y4, "Notes / Disclaimer")
        y4 -= 6 * mm

        c.setFillColor(BRAND["muted"])
        c.setFont(BASE_FONT, 9)
        notes = _safe_str(data.get("notes", ""), max_length=500)
        for line in _wrap_words(notes, 112):
            c.drawString(14 * mm, y4, line)
            y4 -= 11

        # Polaroids and footer
        _draw_page_polaroids(c, W, H, data, page_index=1)
        _draw_footer(c, W)

        # ============================================
        # PAGE 2: COVERAGE DETAILS - IMPROVED
        # ============================================

        c.showPage()
        _draw_header(c, W, H, "Plan Coverage Summary")

        top = H - 30 * mm
        c.setFillColor(BRAND["dark"])
        c.setFont(BOLD_FONT, 12.5)
        c.drawString(14 * mm, top, "Coverage Details (Summary)")
        top -= 8 * mm

        # Single plan or dual plans
        if len(selected_plans) == 1:
            x = 14 * mm
            w = W - 28 * mm
            h = 165 * mm
            y_top = top

            if selected_plans[0] == "PET CARE PLUS (INTERLIFE)":
                title = f"{plan_1_name} ({plan_1_provider})"
                plan_1_price = _safe_str(data.get("plan_1_price", ""), max_length=10)
                plan1_limit = _safe_str(data.get("plan1_limit", ""), max_length=50)
                plan1_area = _safe_str(data.get("plan1_area", ""), max_length=50)
                subtitle = f"€{plan_1_price}/year | Limit: {plan1_limit} | Area: {plan1_area}"
                blocks = [
                    ("Key Facts", data.get("plan1_key_facts", [])),
                    ("Covers (Summary)", data.get("plan1_covers", [])),
                    ("Not Covered (Indicative)", data.get("plan1_exclusions", [])),
                    ("Waiting Periods", data.get("plan1_waiting", [])),
                ]
            else:
                title = f"{plan_2_name} ({plan_2_provider})"
                plan2_limit = _safe_str(data.get("plan2_limit", ""), max_length=50)
                plan2_area = _safe_str(data.get("plan2_area", ""), max_length=50)
                subtitle = f"Limit: {plan2_limit} | Area: {plan2_area} | Network only"
                blocks = [
                    ("Key Facts", data.get("plan2_key_facts", [])),
                    ("Covers (Summary)", data.get("plan2_covers", [])),
                    ("Not Covered (Indicative)", data.get("plan2_exclusions", [])),
                    ("Waiting Periods", data.get("plan2_waiting", [])),
                ]

            _draw_plan_card(c, x, y_top, w, h, title, subtitle, blocks)

        else:
            # Two plans side by side - IMPROVED LAYOUT
            gap = 8 * mm
            card_w = (W - 28 * mm - gap) / 2
            card_h = 170 * mm  # Slightly increased height for better spacing
            x1 = 14 * mm
            x2 = 14 * mm + card_w + gap
            y_top = top

            if "PET CARE PLUS (INTERLIFE)" in selected_plans:
                title = f"{plan_1_name} ({plan_1_provider})"
                plan_1_price = _safe_str(data.get("plan_1_price", ""), max_length=10)
                plan1_limit = _safe_str(data.get("plan1_limit", ""), max_length=40)
                plan1_area = _safe_str(data.get("plan1_area", ""), max_length=40)
                subtitle = f"€{plan_1_price}/year | Limit: {plan1_limit} | Area: {plan1_area}"
                blocks = [
                    ("Key Facts", data.get("plan1_key_facts", [])),
                    ("Covers (Summary)", data.get("plan1_covers", [])),
                    ("Not Covered (Indicative)", data.get("plan1_exclusions", [])),
                    ("Waiting Periods", data.get("plan1_waiting", [])),
                ]
                _draw_plan_card(c, x1, y_top, card_w, card_h, title, subtitle, blocks)

            if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
                title = f"{plan_2_name} ({plan_2_provider})"
                plan2_limit = _safe_str(data.get("plan2_limit", ""), max_length=40)
                plan2_area = _safe_str(data.get("plan2_area", ""), max_length=40)
                # FIXED: Shorter subtitle to prevent overflow in narrow column
                subtitle = f"Unlimited (in-network) | {plan2_area[:25]}"
                blocks = [
                    ("Key Facts", data.get("plan2_key_facts", [])),
                    ("Covers (Summary)", data.get("plan2_covers", [])),
                    ("Not Covered (Indicative)", data.get("plan2_exclusions", [])),
                    ("Waiting Periods", data.get("plan2_waiting", [])),
                ]
                _draw_plan_card(c, x2, y_top, card_w, card_h, title, subtitle, blocks)

        _draw_page_polaroids(c, W, H, data, page_index=2)
        _draw_footer(c, W)

        # ============================================
        # PAGE 3: ABOUT & HIGHLIGHTS - FIXED v2
        # ============================================

        c.showPage()
        _draw_header(c, W, H, "About & Official Highlights")

        # Paragraph styles
        body_style = ParagraphStyle(
            name="Body",
            fontName=BASE_FONT,
            fontSize=9.5,  # FIXED: Slightly smaller for more text
            leading=12.5,  # FIXED: Adjusted leading
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

        # Trust banner
        c.setFillColor(BRAND["bg"])
        c.setStrokeColor(BRAND["border"])
        c.roundRect(margin_x, top_y - 12 * mm, W - 2 * margin_x, 12 * mm, 8, stroke=1, fill=1)
        c.setFillColor(BRAND["dark"])
        c.setFont(BOLD_FONT, 10.2)
        c.drawString(
            margin_x + 6 * mm, top_y - 8.3 * mm,
            "Trust: SAFE PET (2016)  •  Pet Insurance advisor  •  CII certified (PL4, W01)"
        )

        top_y -= 16 * mm

        # About advisor box - FIXED: Increased height
        box1_h = 65 * mm  # FIXED: Increased from 56mm to 65mm
        c.setStrokeColor(BRAND["border"])
        c.setFillColor(BRAND["bg"])
        c.roundRect(margin_x, top_y - box1_h, W - 2 * margin_x, box1_h, 10, stroke=1, fill=1)
        c.setFillColor(BRAND["blue"])
        c.roundRect(margin_x, top_y - 4, W - 2 * margin_x, 4, 2, stroke=0, fill=1)

        c.setFont(BOLD_FONT, 14)
        c.setFillColor(BRAND["dark"])
        c.drawString(margin_x + 6 * mm, top_y - 12 * mm, "About the Advisor")

        bio = _safe_str(data.get("about_bio", ""), max_length=1000)
        if not bio:
            bio = "Professional pet insurance advisor. Contact us for more information."

        bio_par = Paragraph(bio.replace("\n", "<br/>"), body_style)
        bio_frame = Frame(
            margin_x + 6 * mm, top_y - box1_h + 8 * mm,
            W - 2 * margin_x - 12 * mm, box1_h - 22 * mm,
            showBoundary=0
        )
        bio_frame.addFromList([
            KeepInFrame(W - 2 * margin_x - 12 * mm, box1_h - 22 * mm, [bio_par], mode="shrink")
        ], c)

        # CII credentials box
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
        cii_frame = Frame(
            margin_x + 6 * mm, box2_top - box2_h + 6 * mm,
            W - 2 * margin_x - 12 * mm, box2_h - 18 * mm,
            showBoundary=0
        )
        cii_frame.addFromList([
            KeepInFrame(W - 2 * margin_x - 12 * mm, box2_h - 18 * mm, [cii_flow], mode="shrink")
        ], c)

        # Official highlights
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
            eu = ["Professional coverage with network benefits"]

        eu_flow = _create_platypus_bullets(eu, small_style, max_items=8)
        eu_frame = Frame(
            margin_x + 6 * mm, box3_top - box3_h + 6 * mm,
            col_w - 12 * mm, box3_h - 20 * mm,
            showBoundary=0
        )
        eu_frame.addFromList([
            KeepInFrame(col_w - 12 * mm, box3_h - 20 * mm, [eu_flow], mode="shrink")
        ], c)

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
            it = ["Comprehensive coverage with flexibility"]

        it_flow = _create_platypus_bullets(it, small_style, max_items=8)
        it_frame = Frame(
            xr + 6 * mm, box3_top - box3_h + 6 * mm,
            col_w - 12 * mm, box3_h - 20 * mm,
            showBoundary=0
        )
        it_frame.addFromList([
            KeepInFrame(col_w - 12 * mm, box3_h - 20 * mm, [it_flow], mode="shrink")
        ], c)

        _draw_page_polaroids(c, W, H, data, page_index=3)
        _draw_footer(c, W)

        # Save and return PDF
        c.save()
        pdf_bytes = buf.getvalue()

        logger.info(f"✅ PDF generated successfully: {len(pdf_bytes)} bytes")
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ PDF generation failed: {e}", exc_info=True)
        raise