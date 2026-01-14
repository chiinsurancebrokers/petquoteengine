"""
PETSHEALTH Email Testing Script
Test your SMTP configuration and email sending
"""
import os
from petshealth_email_standalone import (
    test_smtp_connection,
    send_petshealth_quote,
    validate_email
)


# ==============================================
# TEST 1: Validate Email Addresses
# ==============================================

def test_email_validation():
    """Test email validation"""
    print("\n" + "=" * 60)
    print("TEST 1: EMAIL VALIDATION")
    print("=" * 60)

    test_emails = [
        ("client@example.com", True),
        ("test.user+tag@domain.co.uk", True),
        ("invalid@", False),
        ("@invalid.com", False),
        ("no-at-sign.com", False),
        ("spaces in@email.com", False),
    ]

    for email, should_be_valid in test_emails:
        is_valid = validate_email(email)
        status = "✅" if is_valid == should_be_valid else "❌"
        print(f"{status} {email:30} -> {is_valid}")


# ==============================================
# TEST 2: SMTP Connection
# ==============================================

def test_smtp():
    """Test SMTP connection without sending email"""
    print("\n" + "=" * 60)
    print("TEST 2: SMTP CONNECTION")
    print("=" * 60)

    print("\nTesting SMTP connection...")
    print("This will verify your credentials without sending an email.\n")

    # Get credentials from environment
    smtp_user = os.getenv('SMTP_USER') or input("Enter SMTP_USER (your Gmail): ").strip()
    smtp_password = os.getenv('SMTP_PASSWORD') or input("Enter SMTP_PASSWORD (App Password): ").strip()

    if not smtp_user or not smtp_password:
        print("❌ Missing credentials!")
        return

    result = test_smtp_connection(smtp_user, smtp_password)

    if result["success"]:
        print(f"✅ {result['message']}")
        print(f"   User: {result['user']}")
    else:
        print(f"❌ Connection failed!")
        print(f"   Error: {result['error']}")
        print("\n💡 Troubleshooting tips:")
        print("   1. For Gmail, use App Password (NOT regular password)")
        print("   2. Generate at: https://myaccount.google.com/apppasswords")
        print("   3. Enable 2FA first: https://myaccount.google.com/security")


# ==============================================
# TEST 3: Send Test Email
# ==============================================

def test_send_email():
    """Send a test email with dummy PDF"""
    print("\n" + "=" * 60)
    print("TEST 3: SEND TEST EMAIL")
    print("=" * 60)

    print("\n⚠️  This will actually send an email!")
    confirm = input("Continue? (yes/no): ").strip().lower()

    if confirm != "yes":
        print("Test cancelled.")
        return

    # Get credentials
    smtp_user = os.getenv('SMTP_USER') or input("\nEnter SMTP_USER (your Gmail): ").strip()
    smtp_password = os.getenv('SMTP_PASSWORD') or input("Enter SMTP_PASSWORD (App Password): ").strip()
    to_email = input("Enter recipient email: ").strip()

    if not smtp_user or not smtp_password or not to_email:
        print("❌ Missing required information!")
        return

    # Create dummy PDF (minimal valid PDF)
    dummy_pdf = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Count 1
/Kids [3 0 R]
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 24 Tf
100 700 Td
(TEST PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000015 00000 n 
0000000068 00000 n 
0000000125 00000 n 
0000000324 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
416
%%EOF"""

    print("\nSending test email...")

    try:
        result = send_petshealth_quote(
            to_email=to_email,
            client_name="Test Client",
            pdf_bytes=dummy_pdf,
            total_premium="€123.45",
            subject="[TEST] PETSHEALTH Quote",
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            language="en",
            use_html=True
        )

        if result["success"]:
            print(f"\n✅ Email sent successfully!")
            print(f"   To: {result['to']}")
            print(f"   Subject: {result['subject']}")
            print(f"   Size: {result['size_mb']}MB")
            print(f"   Time: {result['elapsed_seconds']}s")
        else:
            print(f"\n❌ Email failed!")

    except Exception as e:
        print(f"\n❌ Error sending email:")
        print(f"   {e}")


# ==============================================
# MAIN MENU
# ==============================================

def main():
    """Main testing menu"""
    print("\n" + "=" * 60)
    print("PETSHEALTH EMAIL TESTING")
    print("=" * 60)
    print("\nWhat would you like to test?\n")
    print("1. Test email validation")
    print("2. Test SMTP connection (no email sent)")
    print("3. Send test email (actual email)")
    print("4. Run all tests")
    print("0. Exit")

    choice = input("\nEnter choice (0-4): ").strip()

    if choice == "1":
        test_email_validation()
    elif choice == "2":
        test_smtp()
    elif choice == "3":
        test_send_email()
    elif choice == "4":
        test_email_validation()
        test_smtp()
        test_send_email()
    elif choice == "0":
        print("Goodbye!")
        return
    else:
        print("Invalid choice!")

    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
