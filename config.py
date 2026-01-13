"""
PETSHEALTH Quote Engine - Secure Configuration
"""
import os
from pathlib import Path

# --------------------------
# Application Settings
# --------------------------
APP_TITLE = "PETSHEALTH – Pet Insurance Quote Engine"
APP_ICON = "🐾"

# --------------------------
# Security Limits
# --------------------------
MAX_EMAIL_LENGTH = 254  # RFC 5321 standard
MAX_TEXT_INPUT_LENGTH = 500
MAX_TEXT_AREA_LENGTH = 5000
MAX_FILE_UPLOAD_SIZE_MB = 10
MAX_PDF_SIZE_MB = 25  # Email attachment limit
MAX_POLAROID_IMAGES = 10
MAX_EMAILS_PER_HOUR = 20  # Rate limit

# --------------------------
# File Paths (relative to project root)
# --------------------------
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
IPID_DIR = ASSETS_DIR / "ipid"
FONTS_DIR = ASSETS_DIR / "fonts"
LOGO_PATH = ASSETS_DIR / "logo" / "petshealth_logo.png"

# --------------------------
# IPID Mappings
# --------------------------
IPID_MAP = {
    "PET CARE PLUS (INTERLIFE)": str(IPID_DIR / "PETCARE_PLUS_IPID.pdf"),
    "EUROLIFE My Happy Pet (SAFE PET SYSTEM)": str(IPID_DIR / "EUROLIFE_MY_HAPPY_PET_IPID.pdf"),
}
PLAN_KEYS = list(IPID_MAP.keys())

# --------------------------
# URLs
# --------------------------
PETSHEALTH_HOME_URL = "https://www.petshealth.gr/"
PETSHEALTH_TEAM_URL = "https://www.petshealth.gr/petshealt-team"
EUROLIFE_URL = "https://www.eurolife.gr/el-GR/proionta/idiotes/katoikidio/my-happy-pet"
INTERLIFE_URL = "https://www.interlife-programs.gr/asfalisi/eidika-programmata/#petcare"

# --------------------------
# Email Settings
# --------------------------
ADVISOR_EMAIL = "xiatropoulos@gmail.com"  # Centralized - easy to update


# --------------------------
# SMTP Configuration (from secrets/env)
# --------------------------
def get_smtp_config():
    """Get SMTP configuration from Streamlit secrets or environment"""
    # Try Streamlit secrets first
    try:
        import streamlit as st
        if hasattr(st, 'secrets'):
            return {
                'host': st.secrets.get('SMTP_HOST', 'smtp.gmail.com'),
                'port': int(st.secrets.get('SMTP_PORT', 587)),
                'user': st.secrets.get('SMTP_USER', ''),
                'pass': st.secrets.get('SMTP_PASS', ''),
            }
    except Exception:
        pass

    # Fallback to environment variables
    return {
        'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
        'port': int(os.getenv('SMTP_PORT', 587)),
        'user': os.getenv('SMTP_USER', ''),
        'pass': os.getenv('SMTP_PASS', ''),
    }


# --------------------------
# Allowed File Types
# --------------------------
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_IMAGE_MIMETYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
}

# --------------------------
# Web Scraping Settings
# --------------------------
WEB_SCRAPE_TIMEOUT = 20
WEB_SCRAPE_MAX_ITEMS = 18
WEB_SCRAPE_USER_AGENT = "Mozilla/5.0 (PETSHEALTH/1.0; +https://www.petshealth.gr)"
