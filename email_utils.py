"""
PETSHEALTH Quote Engine - Secure Email Utilities
Implements secure email sending with validation, sanitization, and rate limiting
"""
import ssl
import smtplib
import logging
from email.message import EmailMessage
from datetime import datetime, timedelta
from typing import Optional
from collections import deque

from config import get_smtp_config, MAX_PDF_SIZE_MB, MAX_EMAILS_PER_HOUR
from input_validators import validate_email, sanitize_email_header, sanitize_filename

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class EmailError(Exception):
    """Custom exception for email-related errors"""
    pass


class RateLimitError(EmailError):
    """Raised when rate limit is exceeded"""
    pass


# --------------------------
# Rate Limiting
# --------------------------

class EmailRateLimiter:
    """Simple in-memory rate limiter for email sends"""

    def __init__(self, max_emails: int = MAX_EMAILS_PER_HOUR, window_minutes: int = 60):
        self.max_emails = max_emails
        self.window_seconds = window_minutes * 60
        self.timestamps = deque()

    def check_and_record(self) -> bool:
        """
        Check if rate limit allows sending, and record the attempt.

        Returns:
            True if send is allowed

        Raises:
            RateLimitError: If rate limit exceeded
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Remove old timestamps
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()

        # Check limit
        if len(self.timestamps) >= self.max_emails:
            next_available = self.timestamps[0] + timedelta(seconds=self.window_seconds)
            wait_minutes = (next_available - now).total_seconds() / 60
            raise RateLimitError(
                f"Email rate limit exceeded ({self.max_emails} per hour). "
                f"Try again in {wait_minutes:.1f} minutes."
            )

        # Record this attempt
        self.timestamps.append(now)
        return True

    def get_remaining(self) -> int:
        """Get remaining email quota"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Remove old timestamps
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()

        return max(0, self.max_emails - len(self.timestamps))


# Global rate limiter instance
_rate_limiter = EmailRateLimiter()


# --------------------------
# Email Sending
# --------------------------

def send_quote_email(
        to_email: str,
        subject: str,
        body_text: str,
        pdf_bytes: bytes,
        filename: str = "PETSHEALTH_Quote.pdf",
        cc_email: Optional[str] = None,
        check_rate_limit: bool = True,
) -> dict:
    """
    Send a professional quote email with PDF attachment (SECURE).

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body_text: Plain text email body
        pdf_bytes: PDF file as bytes
        filename: Attachment filename (will be sanitized)
        cc_email: Optional CC email address
        check_rate_limit: Whether to enforce rate limiting

    Returns:
        Dictionary with send status and metadata

    Raises:
        EmailError: If email sending fails
        RateLimitError: If rate limit exceeded
        ValueError: If inputs are invalid
    """

    start_time = datetime.now()

    # === RATE LIMITING ===

    if check_rate_limit:
        _rate_limiter.check_and_record()
        logger.info(f"Rate limit check passed. Remaining: {_rate_limiter.get_remaining()}")

    # === INPUT VALIDATION ===

    # Validate recipient email
    if not validate_email(to_email):
        logger.error(f"Invalid recipient email: {to_email}")
        raise ValueError(f"Invalid recipient email address: {to_email}")

    # Validate CC email if provided
    if cc_email:
        if not validate_email(cc_email):
            logger.error(f"Invalid CC email: {cc_email}")
            raise ValueError(f"Invalid CC email address: {cc_email}")

    # Validate PDF
    if not pdf_bytes or not isinstance(pdf_bytes, bytes):
        raise ValueError("PDF attachment is empty or invalid")

    pdf_size_mb = len(pdf_bytes) / (1024 * 1024)
    if pdf_size_mb > MAX_PDF_SIZE_MB:
        raise ValueError(
            f"PDF attachment too large: {pdf_size_mb:.2f}MB "
            f"(max: {MAX_PDF_SIZE_MB}MB)"
        )

    # Validate subject and body
    if not subject or not subject.strip():
        raise ValueError("Email subject cannot be empty")

    if not body_text or not body_text.strip():
        raise ValueError("Email body cannot be empty")

    # === SANITIZATION ===

    to_email = sanitize_email_header(to_email)
    subject = sanitize_email_header(subject)
    cc_email = sanitize_email_header(cc_email) if cc_email else None
    filename = sanitize_filename(filename)

    # Ensure filename ends with .pdf
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'

    logger.info(f"Preparing email: to={to_email}, cc={cc_email}, size={pdf_size_mb:.2f}MB")

    # === LOAD SMTP CONFIGURATION ===

    smtp_config = get_smtp_config()
    smtp_host = smtp_config['host']
    smtp_port = smtp_config['port']
    smtp_user = smtp_config['user']
    smtp_pass = smtp_config['pass']

    if not smtp_user or not smtp_pass:
        logger.error("Missing SMTP credentials")
        raise EmailError(
            "Missing SMTP credentials. Configure SMTP_USER and SMTP_PASS "
            "in Streamlit Secrets or environment variables."
        )

    # === BUILD EMAIL MESSAGE ===

    msg = EmailMessage()
    msg["From"] = f"PETSHEALTH <{smtp_user}>"
    msg["To"] = to_email
    if cc_email:
        msg["Cc"] = cc_email
    msg["Subject"] = subject
    msg["Reply-To"] = smtp_user
    msg["X-Mailer"] = "PETSHEALTH Quote Engine v1.0"
    msg["X-Priority"] = "3"  # Normal priority

    # Set content
    msg.set_content(body_text, charset='utf-8')

    # Add PDF attachment
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=filename
    )

    # === SEND EMAIL ===

    try:
        # Create secure SSL context
        context = ssl.create_default_context()
        # Optionally verify certificates (recommended for production)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        logger.info(f"Connecting to SMTP: {smtp_host}:{smtp_port}")

        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            # Identify to server
            server.ehlo()

            # Upgrade to TLS
            logger.debug("Starting TLS...")
            server.starttls(context=context)

            # Re-identify after TLS
            server.ehlo()

            # Authenticate
            logger.debug("Authenticating...")
            server.login(smtp_user, smtp_pass)

            # Send message
            logger.info(f"Sending email to {to_email}...")
            refused = server.send_message(msg)

            if refused:
                logger.warning(f"Some recipients refused: {refused}")

            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"✅ Email sent successfully to {to_email} "
                f"({pdf_size_mb:.2f}MB, {elapsed:.2f}s)"
            )

            return {
                "success": True,
                "to": to_email,
                "cc": cc_email,
                "size_mb": round(pdf_size_mb, 2),
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now().isoformat(),
                "refused_recipients": refused,
            }

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        raise EmailError(
            "Email authentication failed. Please check SMTP credentials."
        ) from e

    except smtplib.SMTPRecipientsRefused as e:
        logger.error(f"Recipients refused: {e}")
        raise EmailError(
            f"Recipient email was rejected by the server: {to_email}"
        ) from e

    except smtplib.SMTPSenderRefused as e:
        logger.error(f"Sender refused: {e}")
        raise EmailError(
            "Sender email was rejected. Check SMTP_USER configuration."
        ) from e

    except smtplib.SMTPDataError as e:
        logger.error(f"SMTP data error: {e}")
        raise EmailError(
            "Email data was rejected. Message may be too large or contain invalid content."
        ) from e

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        raise EmailError(f"SMTP error occurred: {str(e)}") from e

    except ssl.SSLError as e:
        logger.error(f"SSL/TLS error: {e}")
        raise EmailError(
            "SSL/TLS connection failed. Check your network or SMTP settings."
        ) from e

    except TimeoutError as e:
        logger.error(f"Connection timeout: {e}")
        raise EmailError(
            "Connection to email server timed out. Check your network connection."
        ) from e

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise EmailError(f"Unexpected error sending email: {str(e)}") from e


def get_rate_limit_status() -> dict:
    """
    Get current rate limit status.

    Returns:
        Dictionary with rate limit info
    """
    return {
        "max_per_hour": _rate_limiter.max_emails,
        "remaining": _rate_limiter.get_remaining(),
        "used": _rate_limiter.max_emails - _rate_limiter.get_remaining(),
    }


def test_smtp_connection() -> dict:
    """
    Test SMTP connection and credentials (without sending email).

    Returns:
        Dictionary with connection test results
    """
    try:
        smtp_config = get_smtp_config()
        smtp_host = smtp_config['host']
        smtp_port = smtp_config['port']
        smtp_user = smtp_config['user']
        smtp_pass = smtp_config['pass']

        if not smtp_user or not smtp_pass:
            return {
                "success": False,
                "error": "Missing SMTP credentials"
            }

        context = ssl.create_default_context()

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(smtp_user, smtp_pass)

        return {
            "success": True,
            "message": f"Successfully connected to {smtp_host}:{smtp_port}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
