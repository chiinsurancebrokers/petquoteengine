import os
import ssl
import smtplib
from email.message import EmailMessage

def send_quote_email(
    to_email: str,
    subject: str,
    body_text: str,
    pdf_bytes: bytes,
    filename: str = "PETSHEALTH_Quote.pdf",
    cc_email: str | None = None,
):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        raise RuntimeError("Missing SMTP credentials. Set SMTP_USER / SMTP_PASS in Streamlit Secrets or env vars.")

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = to_email
    if cc_email:
        msg["Cc"] = cc_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=filename
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
