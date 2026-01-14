"""
PETSHEALTH Email Sender - COMPLETE STANDALONE VERSION
Zero external dependencies (except standard library)
Works with Gmail, Office365, and other SMTP servers

SETUP FOR GMAIL:
1. Go to https://myaccount.google.com/security
2. Enable 2-Factor Authentication
3. Go to https://myaccount.google.com/apppasswords
4. Generate App Password (16 characters)
5. Use App Password as SMTP_PASSWORD (NOT your Gmail password!)

USAGE:
    from petshealth_email_standalone import send_petshealth_quote

    result = send_petshealth_quote(
        to_email="client@example.com",
        client_name="John Doe",
        pdf_bytes=pdf_data,
        total_premium="€450.00",
        smtp_user="your@gmail.com",
        smtp_password="your_app_password_16chars"
    )
"""
import ssl
import smtplib
import os
import re
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from typing import Optional, Dict

# Setup logging
logger = logging.getLogger(__name__)

# ==============================================
# CONSTANTS
# ==============================================

MAX_EMAIL_LENGTH = 254
MAX_PDF_SIZE_MB = 25
MAX_SUBJECT_LENGTH = 200
MAX_BODY_LENGTH = 10000


# ==============================================
# VALIDATION FUNCTIONS (Built-in, no imports)
# ==============================================

def validate_email(email: str) -> bool:
    """Validate email address format"""
    if not email or not isinstance(email, str):
        return False

    email = email.strip()

    if len(email) > MAX_EMAIL_LENGTH:
        return False

    if email.count('@') != 1:
        return False

    # RFC 5322 simplified pattern
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@[a-zA-Z0-9][a-zA-Z0-9.-]{0,253}\.[a-zA-Z]{2,}$'

    if not re.match(pattern, email):
        return False

    local, domain = email.split('@')

    # Check for invalid patterns
    if local.startswith('.') or local.endswith('.') or '..' in local:
        return False

    if domain.startswith('-') or domain.endswith('-') or '..' in domain:
        return False

    return True


def sanitize_header(value: str) -> str:
    """Remove characters that could enable email header injection"""
    if not value:
        return ""

    # Remove newlines, carriage returns, null bytes
    sanitized = re.sub(r'[\r\n\x00]', '', str(value))

    # Remove control characters
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char == '\t')

    return sanitized.strip()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal"""
    if not filename:
        return "PETSHEALTH_Quote.pdf"

    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')

    # Remove dangerous characters
    filename = re.sub(r'[^\w\s\-\.]', '_', filename)

    # Remove leading dots
    filename = filename.lstrip('.')

    # Ensure .pdf extension
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'

    # Limit length
    if len(filename) > 100:
        filename = filename[:96] + '.pdf'

    return filename or "PETSHEALTH_Quote.pdf"


# ==============================================
# EMAIL TEMPLATES
# ==============================================

def create_email_body_text(client_name: str, total_premium: str, language: str = "en") -> str:
    """Create plain text email body"""

    if language == "el":
        return f"""Αγαπητέ/ή {client_name},

Σας ευχαριστούμε για το ενδιαφέρον σας στην ασφάλιση κατοικιδίου της PETSHEALTH!

Επισυνάπτεται η προσφορά μας με λεπτομέρειες κάλυψης και τιμολόγησης.

Ετήσιο Ασφάλιστρο: {total_premium}

Το PDF περιλαμβάνει:
✓ Πλήρη ανάλυση κάλυψης
✓ Όρους & προϋποθέσεις
✓ Αναμενόμενες περίοδοι αναμονής
✓ Πληροφορίες επικοινωνίας

Για οποιεσδήποτε ερωτήσεις ή διευκρινίσεις, μη διστάσετε να επικοινωνήσετε μαζί μας.

Με εκτίμηση,
PETSHEALTH Team

Τηλέφωνο: +30 211 700 533
Email: info@petshealth.gr
Website: www.petshealth.gr

Επειδή νοιαζόμαστε για τα κατοικίδιά σας όσο κι εσείς."""

    else:  # English
        return f"""Dear {client_name},

Thank you for your interest in PETSHEALTH pet insurance!

Please find attached your personalized quote with coverage details and pricing information.

Annual Premium: {total_premium}

The attached PDF includes:
✓ Complete coverage breakdown
✓ Terms & conditions summary
✓ Waiting periods
✓ Contact information

If you have any questions or need clarification on any aspect of the coverage, please don't hesitate to contact us.

Best regards,
PETSHEALTH Team

Phone: +30 211 700 533
Email: info@petshealth.gr
Website: www.petshealth.gr

Because we care for your pets as much as you do."""


def create_email_body_html(client_name: str, total_premium: str, language: str = "en") -> str:
    """Create HTML email body with professional styling"""

    if language == "el":
        greeting = f"Αγαπητέ/ή {client_name},"
        intro = "Σας ευχαριστούμε για το ενδιαφέρον σας στην ασφάλιση κατοικιδίου της PETSHEALTH!"
        quote_title = "Η Προσφορά Σας"
        premium_label = "Ετήσιο Ασφάλιστρο"
        includes_title = "Το PDF περιλαμβάνει:"
        items = [
            "Πλήρη ανάλυση κάλυψης",
            "Όρους & προϋποθέσεις",
            "Περίοδοι αναμονής",
            "Πληροφορίες επικοινωνίας"
        ]
        question_text = "Για ερωτήσεις ή διευκρινίσεις, επικοινωνήστε μαζί μας."
        regards = "Με εκτίμηση,"
        tagline = "Επειδή νοιαζόμαστε για τα κατοικίδιά σας όσο κι εσείς."
    else:
        greeting = f"Dear {client_name},"
        intro = "Thank you for your interest in PETSHEALTH pet insurance!"
        quote_title = "Your Quote"
        premium_label = "Annual Premium"
        includes_title = "The attached PDF includes:"
        items = [
            "Complete coverage breakdown",
            "Terms & conditions summary",
            "Waiting periods",
            "Contact information"
        ]
        question_text = "If you have any questions or need clarification, please contact us."
        regards = "Best regards,"
        tagline = "Because we care for your pets as much as you do."

    items_html = "".join([f'<li style="margin: 8px 0; color: #374151;">✓ {item}</li>' for item in items])

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #F3F4F6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #F3F4F6; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #FFFFFF; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden;">

                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1E4FA8 0%, #2563EB 100%); padding: 30px; text-align: center;">
                            <h1 style="margin: 0; color: #FFFFFF; font-size: 28px; font-weight: 700;">🐾 PETSHEALTH</h1>
                            <p style="margin: 8px 0 0 0; color: #E0E7FF; font-size: 14px;">Pet Insurance Quotation</p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; color: #111827; font-size: 16px; line-height: 1.6;">{greeting}</p>

                            <p style="margin: 0 0 30px 0; color: #374151; font-size: 15px; line-height: 1.6;">{intro}</p>

                            <!-- Quote Box -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #F7FAFC; border: 2px solid #1E4FA8; border-radius: 8px; margin: 0 0 30px 0;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <h2 style="margin: 0 0 12px 0; color: #1E4FA8; font-size: 18px; font-weight: 600;">{quote_title}</h2>
                                        <p style="margin: 0; color: #6B7280; font-size: 14px;">{premium_label}</p>
                                        <p style="margin: 8px 0 0 0; color: #111827; font-size: 28px; font-weight: 700;">{total_premium}</p>
                                    </td>
                                </tr>
                            </table>

                            <!-- Includes -->
                            <h3 style="margin: 0 0 16px 0; color: #111827; font-size: 16px; font-weight: 600;">{includes_title}</h3>
                            <ul style="margin: 0 0 30px 0; padding: 0 0 0 20px; list-style: none;">
                                {items_html}
                            </ul>

                            <p style="margin: 0 0 30px 0; color: #374151; font-size: 15px; line-height: 1.6;">{question_text}</p>

                            <p style="margin: 0 0 8px 0; color: #111827; font-size: 15px;">{regards}</p>
                            <p style="margin: 0; color: #1E4FA8; font-size: 16px; font-weight: 600;">PETSHEALTH Team</p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #F9FAFB; padding: 30px; border-top: 1px solid #E5E7EB; text-align: center;">
                            <p style="margin: 0 0 12px 0; color: #111827; font-size: 14px; font-weight: 600;">Contact Us</p>
                            <p style="margin: 0 0 4px 0; color: #6B7280; font-size: 13px;">📞 +30 211 700 533</p>
                            <p style="margin: 0 0 4px 0; color: #6B7280; font-size: 13px;">✉️ info@petshealth.gr</p>
                            <p style="margin: 0 0 16px 0; color: #6B7280; font-size: 13px;">🌐 www.petshealth.gr</p>
                            <p style="margin: 0; color: #9CA3AF; font-size: 12px; font-style: italic;">{tagline}</p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


# ==============================================
# MAIN EMAIL SENDER
# ==============================================

def send_petshealth_quote(
        to_email: str,
        client_name: str,
        pdf_bytes: bytes,
        total_premium: str = "€0.00",
        subject: Optional[str] = None,
        cc_email: Optional[str] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        language: str = "en",
        filename: str = "PETSHEALTH_Quote.pdf",
        use_html: bool = True
) -> Dict:
    """
    Send PETSHEALTH quote email with PDF attachment.

    Args:
        to_email: Recipient email address
        client_name: Client's name for personalization
        pdf_bytes: PDF file as bytes
        total_premium: Total annual premium (e.g., "€450.00")
        subject: Email subject (auto-generated if None)
        cc_email: Optional CC email address
        smtp_user: SMTP username (email address)
        smtp_password: SMTP password (Gmail App Password)
        smtp_host: SMTP server (default: smtp.gmail.com)
        smtp_port: SMTP port (default: 587 for TLS)
        language: "en" or "el" for email language
        filename: PDF attachment filename
        use_html: Send HTML email (default: True)

    Returns:
        Dict with success status and metadata

    Raises:
        ValueError: If inputs are invalid
        Exception: If sending fails

    Example:
        result = send_petshealth_quote(
            to_email="client@example.com",
            client_name="John Doe",
            pdf_bytes=pdf_data,
            total_premium="€450.00",
            smtp_user="your@gmail.com",
            smtp_password="your_16char_app_password"
        )
    """

    start_time = datetime.now()

    # ==============================================
    # 1. VALIDATE INPUTS
    # ==============================================

    logger.info(f"Starting email send to {to_email}")

    # Get SMTP credentials from env if not provided
    if not smtp_user:
        smtp_user = os.getenv('SMTP_USER') or os.getenv('PETSHEALTH_EMAIL')
    if not smtp_password:
        smtp_password = os.getenv('SMTP_PASSWORD') or os.getenv('PETSHEALTH_EMAIL_PASSWORD')

    if not smtp_user or not smtp_password:
        raise ValueError(
            "❌ Missing SMTP credentials!\n"
            "Either pass smtp_user and smtp_password arguments, or set environment variables:\n"
            "SMTP_USER=your@gmail.com\n"
            "SMTP_PASSWORD=your_16char_app_password\n\n"
            "For Gmail App Password: https://myaccount.google.com/apppasswords"
        )

    # Validate recipient email
    if not validate_email(to_email):
        raise ValueError(f"Invalid recipient email: {to_email}")

    # Validate CC email if provided
    if cc_email and not validate_email(cc_email):
        raise ValueError(f"Invalid CC email: {cc_email}")

    # Validate PDF
    if not pdf_bytes or not isinstance(pdf_bytes, bytes):
        raise ValueError("PDF attachment is empty or invalid")

    pdf_size_mb = len(pdf_bytes) / (1024 * 1024)
    if pdf_size_mb > MAX_PDF_SIZE_MB:
        raise ValueError(f"PDF too large: {pdf_size_mb:.2f}MB (max: {MAX_PDF_SIZE_MB}MB)")

    # Validate client name
    if not client_name or not client_name.strip():
        client_name = "Valued Customer"

    # Sanitize inputs
    to_email = sanitize_header(to_email)
    cc_email = sanitize_header(cc_email) if cc_email else None
    client_name = sanitize_header(client_name)
    total_premium = sanitize_header(total_premium)
    filename = sanitize_filename(filename)

    # Generate subject if not provided
    if not subject:
        if language == "el":
            subject = f"Προσφορά Ασφάλισης Κατοικιδίου - {client_name}"
        else:
            subject = f"Pet Insurance Quote - {client_name}"

    subject = sanitize_header(subject)[:MAX_SUBJECT_LENGTH]

    logger.info(f"Email validated: {to_email}, PDF: {pdf_size_mb:.2f}MB, Language: {language}")

    # ==============================================
    # 2. CREATE EMAIL MESSAGE
    # ==============================================

    msg = MIMEMultipart('alternative')
    msg['From'] = f"PETSHEALTH <{smtp_user}>"
    msg['To'] = to_email
    if cc_email:
        msg['Cc'] = cc_email
    msg['Subject'] = subject
    msg['Reply-To'] = smtp_user
    msg['X-Mailer'] = "PETSHEALTH Quote Engine v1.0"

    # Add text version (always)
    text_body = create_email_body_text(client_name, total_premium, language)
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))

    # Add HTML version (if enabled)
    if use_html:
        html_body = create_email_body_html(client_name, total_premium, language)
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    # Attach PDF
    pdf_part = MIMEApplication(pdf_bytes, _subtype='pdf')
    pdf_part.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(pdf_part)

    logger.info(f"Email message created: Subject='{subject}', HTML={use_html}")

    # ==============================================
    # 3. SEND EMAIL
    # ==============================================

    try:
        # Create secure SSL context
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        logger.info(f"Connecting to {smtp_host}:{smtp_port}...")

        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            # Enable debug logging if needed
            # server.set_debuglevel(1)

            # Identify to server
            server.ehlo()

            # Upgrade to TLS
            logger.info("Starting TLS...")
            server.starttls(context=context)
            server.ehlo()

            # Authenticate
            logger.info(f"Authenticating as {smtp_user}...")
            try:
                server.login(smtp_user, smtp_password)
            except smtplib.SMTPAuthenticationError as e:
                raise ValueError(
                    f"❌ SMTP Authentication Failed!\n"
                    f"Error: {e}\n\n"
                    f"For Gmail:\n"
                    f"1. Make sure you're using an App Password (NOT your regular password)\n"
                    f"2. Generate one at: https://myaccount.google.com/apppasswords\n"
                    f"3. Enable 2FA first: https://myaccount.google.com/security"
                )

            # Send message
            logger.info(f"Sending email to {to_email}...")
            recipients = [to_email]
            if cc_email:
                recipients.append(cc_email)

            refused = server.sendmail(smtp_user, recipients, msg.as_string())

            if refused:
                logger.warning(f"Some recipients refused: {refused}")

            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info(f"✅ Email sent successfully in {elapsed:.2f}s")

            return {
                "success": True,
                "to": to_email,
                "cc": cc_email,
                "subject": subject,
                "size_mb": round(pdf_size_mb, 2),
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now().isoformat(),
                "refused_recipients": refused,
                "message": f"Email sent successfully to {to_email}"
            }

    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"SMTP Authentication Failed: {e}"
        logger.error(error_msg)
        raise Exception(error_msg)

    except smtplib.SMTPRecipientsRefused as e:
        error_msg = f"Recipient refused: {e}"
        logger.error(error_msg)
        raise Exception(error_msg)

    except smtplib.SMTPException as e:
        error_msg = f"SMTP error: {e}"
        logger.error(error_msg)
        raise Exception(error_msg)

    except ssl.SSLError as e:
        error_msg = f"SSL/TLS error: {e}"
        logger.error(error_msg)
        raise Exception(error_msg)

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(error_msg, exc_info=True)
        raise


# ==============================================
# TESTING UTILITY
# ==============================================

def test_smtp_connection(
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587
) -> Dict:
    """
    Test SMTP connection without sending email.

    Returns:
        Dict with test results
    """
    try:
        if not smtp_user:
            smtp_user = os.getenv('SMTP_USER') or os.getenv('PETSHEALTH_EMAIL')
        if not smtp_password:
            smtp_password = os.getenv('SMTP_PASSWORD') or os.getenv('PETSHEALTH_EMAIL_PASSWORD')

        if not smtp_user or not smtp_password:
            return {
                "success": False,
                "error": "Missing SMTP credentials (SMTP_USER and SMTP_PASSWORD)"
            }

        context = ssl.create_default_context()

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(smtp_user, smtp_password)

        return {
            "success": True,
            "message": f"✅ Successfully connected to {smtp_host}:{smtp_port}",
            "user": smtp_user
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ==============================================
# EXAMPLE USAGE
# ==============================================

if __name__ == "__main__":
    # Example: Test SMTP connection
    print("Testing SMTP connection...")
    result = test_smtp_connection()
    print(result)

    # Example: Send email (requires real PDF bytes)
    # pdf_data = open("sample_quote.pdf", "rb").read()
    # result = send_petshealth_quote(
    #     to_email="client@example.com",
    #     client_name="John Doe",
    #     pdf_bytes=pdf_data,
    #     total_premium="€450.00",
    #     language="en"
    # )
    # print(result)