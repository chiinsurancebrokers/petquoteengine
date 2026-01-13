"""
PETSHEALTH Quote Engine - Input Validation & Sanitization
Prevents injection attacks, validates data, and sanitizes user inputs
"""
import re
import html
from typing import Optional
from pathlib import Path
import magic  # python-magic for file type detection
from config import (
    MAX_EMAIL_LENGTH,
    MAX_TEXT_INPUT_LENGTH,
    MAX_TEXT_AREA_LENGTH,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_MIMETYPES,
)


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


# --------------------------
# Email Validation
# --------------------------

def sanitize_email_header(value: str) -> str:
    """
    Remove characters that could enable email header injection attacks.

    Args:
        value: Input string (email, subject, etc.)

    Returns:
        Sanitized string safe for email headers
    """
    if not value:
        return ""

    # Remove newlines, carriage returns, and null bytes
    sanitized = re.sub(r'[\r\n\x00]', '', str(value))

    # Remove any control characters
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char == '\t')

    return sanitized.strip()


def validate_email(email: str) -> bool:
    """
    Validate email address format (RFC 5322 simplified).

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False

    email = email.strip()

    # Check length (RFC 5321: max 254 chars)
    if len(email) > MAX_EMAIL_LENGTH:
        return False

    # Basic format check
    if email.count('@') != 1:
        return False

    # More strict regex pattern
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@[a-zA-Z0-9][a-zA-Z0-9.-]{0,253}\.[a-zA-Z]{2,}$'

    if not re.match(pattern, email):
        return False

    # Additional checks
    local, domain = email.split('@')

    # Local part checks
    if local.startswith('.') or local.endswith('.'):
        return False
    if '..' in local:
        return False

    # Domain checks
    if domain.startswith('-') or domain.endswith('-'):
        return False
    if '..' in domain:
        return False

    return True


# --------------------------
# Text Input Sanitization
# --------------------------

def sanitize_text_input(text: str, max_length: int = MAX_TEXT_INPUT_LENGTH) -> str:
    """
    Sanitize short text inputs (names, phones, etc.).

    Args:
        text: Input text
        max_length: Maximum allowed length

    Returns:
        Sanitized text

    Raises:
        ValidationError: If input exceeds max length
    """
    if not text:
        return ""

    text = str(text).strip()

    if len(text) > max_length:
        raise ValidationError(f"Input too long (max {max_length} characters)")

    # Remove control characters except tabs and newlines
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n')

    # HTML escape to prevent XSS
    text = html.escape(text)

    return text


def sanitize_text_area(text: str, max_length: int = MAX_TEXT_AREA_LENGTH) -> str:
    """
    Sanitize longer text inputs (descriptions, notes, etc.).

    Args:
        text: Input text
        max_length: Maximum allowed length

    Returns:
        Sanitized text

    Raises:
        ValidationError: If input exceeds max length
    """
    if not text:
        return ""

    text = str(text).strip()

    if len(text) > max_length:
        raise ValidationError(f"Text too long (max {max_length} characters)")

    # Remove control characters except tabs and newlines
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n\r')

    # HTML escape
    text = html.escape(text)

    return text


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format (flexible for international).

    Args:
        phone: Phone number string

    Returns:
        True if valid format
    """
    if not phone:
        return False

    # Allow digits, spaces, +, -, (, )
    pattern = r'^[\d\s\+\-\(\)]{7,20}$'
    return bool(re.match(pattern, phone.strip()))


def validate_date(date_str: str) -> bool:
    """
    Validate date format (dd/mm/yyyy).

    Args:
        date_str: Date string

    Returns:
        True if valid format
    """
    if not date_str:
        return False

    pattern = r'^(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/\d{4}$'
    return bool(re.match(pattern, date_str.strip()))


# --------------------------
# File Validation
# --------------------------

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.

    Args:
        filename: Original filename

    Returns:
        Safe filename
    """
    if not filename:
        return "untitled"

    # Remove path components
    filename = Path(filename).name

    # Remove dangerous characters
    filename = re.sub(r'[^\w\s\-\.]', '_', filename)

    # Remove leading dots (hidden files)
    filename = filename.lstrip('.')

    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')

    return filename or "untitled"


def validate_image_file(file_bytes: bytes, filename: str) -> bool:
    """
    Validate uploaded image file (type and content).

    Args:
        file_bytes: File content as bytes
        filename: Original filename

    Returns:
        True if valid image

    Raises:
        ValidationError: If file is invalid or potentially malicious
    """
    if not file_bytes:
        raise ValidationError("Empty file")

    # Check file extension
    ext = Path(filename).suffix.lower().lstrip('.')
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")

    # Check magic bytes (actual file type)
    try:
        mime = magic.from_buffer(file_bytes, mime=True)
        if mime not in ALLOWED_IMAGE_MIMETYPES:
            raise ValidationError(f"File content doesn't match extension. Detected: {mime}")
    except Exception as e:
        # If python-magic not available, skip this check but log it
        pass

    # Check file size (basic sanity check)
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > 50:  # 50MB is excessive for an image
        raise ValidationError(f"Image too large: {size_mb:.1f}MB")

    return True


# --------------------------
# Number Validation
# --------------------------

def validate_price(value: float, min_val: float = 0.0, max_val: float = 10000.0) -> bool:
    """
    Validate price input.

    Args:
        value: Price value
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        True if valid
    """
    try:
        value = float(value)
        return min_val <= value <= max_val
    except (ValueError, TypeError):
        return False


def validate_count(value: int, min_val: int = 1, max_val: int = 100) -> bool:
    """
    Validate count/quantity input.

    Args:
        value: Count value
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        True if valid
    """
    try:
        value = int(value)
        return min_val <= value <= max_val
    except (ValueError, TypeError):
        return False


# --------------------------
# URL Validation
# --------------------------

def validate_url(url: str, allowed_domains: Optional[list[str]] = None) -> bool:
    """
    Validate URL format and optionally check domain whitelist.

    Args:
        url: URL to validate
        allowed_domains: Optional list of allowed domains

    Returns:
        True if valid
    """
    if not url or not isinstance(url, str):
        return False

    # Basic URL pattern
    pattern = r'^https?://[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*(/[^\s]*)?$'

    if not re.match(pattern, url):
        return False

    # Domain whitelist check
    if allowed_domains:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        return any(domain == allowed or domain.endswith('.' + allowed) for allowed in allowed_domains)

    return True


# --------------------------
# Sanitize Web Scraped Content
# --------------------------

def sanitize_scraped_text(text: str, max_length: int = 500) -> str:
    """
    Sanitize text scraped from web to prevent XSS and other attacks.

    Args:
        text: Scraped text
        max_length: Maximum length

    Returns:
        Safe text
    """
    if not text:
        return ""

    # HTML unescape first (BeautifulSoup might return escaped content)
    text = html.unescape(text)

    # Remove any HTML tags that might have been missed
    text = re.sub(r'<[^>]+>', '', text)

    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n\r')

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Truncate
    if len(text) > max_length:
        text = text[:max_length - 3] + '...'

    # HTML escape for safe display
    text = html.escape(text)

    return text


# --------------------------
# Batch Validation
# --------------------------

def validate_client_data(data: dict) -> dict:
    """
    Validate all client input data at once.

    Args:
        data: Dictionary of client data

    Returns:
        Dictionary of validation results

    Raises:
        ValidationError: If critical fields are invalid
    """
    errors = {}

    # Email (critical)
    if not validate_email(data.get('client_email', '')):
        errors['client_email'] = "Invalid email address"

    # Phone (if provided)
    phone = data.get('client_phone', '').strip()
    if phone and not validate_phone(phone):
        errors['client_phone'] = "Invalid phone number format"

    # Prices
    if not validate_price(data.get('plan_1_price', 0)):
        errors['plan_1_price'] = "Invalid price"
    if not validate_price(data.get('plan_2_price', 0)):
        errors['plan_2_price'] = "Invalid price"

    # Pet count
    if not validate_count(data.get('pet_count', 1), min_val=1, max_val=50):
        errors['pet_count'] = "Invalid pet count"

    # Date format
    dob = data.get('pet_dob', '').strip()
    if dob and not validate_date(dob):
        errors['pet_dob'] = "Invalid date format (use dd/mm/yyyy)"

    if errors:
        raise ValidationError(f"Validation failed: {errors}")

    return {"valid": True, "errors": {}}
