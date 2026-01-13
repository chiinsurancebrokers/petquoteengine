🐾 PETSHEALTH Quote Engine
Enterprise-grade pet insurance quotation system with comprehensive security

🛡️ Security Features
✅ Implemented Security Measures
Input Validation & Sanitization

Email header injection prevention
XSS protection through HTML escaping
SQL injection prevention (no database, but patterns implemented)
Path traversal protection in filenames
File type validation with magic bytes checking
Rate Limiting

20 emails per hour limit (configurable)
In-memory rate limiter with timestamp tracking
Prevents abuse and spam
Email Security

TLS encryption for all SMTP connections
Certificate verification enabled
App Password support (no plain passwords)
Header injection protection
Attachment size validation
File Upload Security

Magic bytes validation for uploaded images
File size limits (10MB for images, 25MB for PDFs)
Extension whitelist enforcement
Filename sanitization
PDF Security

PDF signature validation
Size limit enforcement
Corruption detection
Page count sanity checks
Web Scraping Security

HTTPS enforcement
Content sanitization
Timeout protection
Domain whitelisting support
XSS prevention from scraped content
Comprehensive Logging

Security events tracked
Error logging with context
Audit trail for email sends
📋 Prerequisites
System Requirements
Python 3.10+
2GB RAM minimum
Internet connection for web scraping & email
Gmail App Password Setup
Enable 2-Factor Authentication on your Gmail account
Go to Google Account Security
Navigate to "App passwords"
Generate a new app password for "Mail"
Copy the 16-character password
🚀 Installation
1. Clone Repository
git clone <your-repo-url>
cd petshealth-quote-engine
2. Install Dependencies
pip install -r requirements.txt
Note for Windows users:

# Use python-magic-bin instead of python-magic
pip uninstall python-magic
pip install python-magic-bin==0.4.14
3. Configure Secrets
For Local Development
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your credentials
For Streamlit Cloud
Go to your app settings
Navigate to "Secrets"
Copy content from secrets.toml.template
Replace with your actual credentials
4. Prepare Assets
# Create required directories
mkdir -p assets/ipid
mkdir -p assets/fonts
mkdir -p assets/logo

# Add your IPID PDFs to assets/ipid/
# Add NotoSans fonts to assets/fonts/
# Add logo to assets/logo/petshealth_logo.png
Required IPID files:

assets/ipid/PETCARE_PLUS_IPID.pdf
assets/ipid/EUROLIFE_MY_HAPPY_PET_IPID.pdf
Required fonts (for Greek support):

assets/fonts/NotoSans-Regular.ttf
assets/fonts/NotoSans-Bold.ttf
🏃 Running the Application
Local Development
streamlit run app.py
Production Deployment (Streamlit Cloud)
Push code to GitHub
Connect repository to Streamlit Cloud
Add secrets in Streamlit Cloud dashboard
Deploy!
🔧 Configuration
Email Settings (config.py)
# Change advisor email
ADVISOR_EMAIL = "your-email@example.com"

# Adjust rate limits
MAX_EMAILS_PER_HOUR = 20  # Default: 20

# PDF size limits
MAX_PDF_SIZE_MB = 25  # Default: 25MB
Security Limits
# Input length limits
MAX_TEXT_INPUT_LENGTH = 500  # Default: 500 chars
MAX_TEXT_AREA_LENGTH = 5000  # Default: 5000 chars
MAX_EMAIL_LENGTH = 254  # RFC 5321 standard
🧪 Testing
Test Email Configuration
from email_utils import test_smtp_connection

result = test_smtp_connection()
print(result)
# {"success": True, "message": "Successfully connected to smtp.gmail.com:587"}
Test Input Validation
from validators import validate_email, validate_phone

# Should return True
assert validate_email("client@example.com") == True

# Should return False
assert validate_email("invalid@") == False
assert validate_phone("abc") == False
Test Rate Limiting
from email_utils import get_rate_limit_status

status = get_rate_limit_status()
print(status)
# {"max_per_hour": 20, "remaining": 20, "used": 0}
📁 Project Structure
petshealth-quote-engine/
├── app.py                    # Main Streamlit application (SECURE)
├── config.py                 # Centralized configuration
├── validators.py             # Input validation & sanitization
├── email_utils.py            # Secure email sending with rate limiting
├── web_utils.py              # Secure web scraping
├── pdf_utils.py              # Secure PDF operations
├── pdf_builder.py            # PDF generation (your existing file)
├── requirements.txt          # Python dependencies
├── .streamlit/
│   └── secrets.toml.template # Secrets template
├── assets/
│   ├── ipid/                # IPID PDF documents
│   ├── fonts/               # NotoSans fonts for Greek
│   └── logo/                # PETSHEALTH logo
└── README.md                # This file
🔒 Security Best Practices
DO's ✅
✅ Use App Passwords, never real passwords
✅ Enable 2FA on email accounts
✅ Rotate credentials regularly
✅ Monitor rate limit usage
✅ Review logs for suspicious activity
✅ Keep dependencies updated
✅ Use HTTPS for all external requests
✅ Validate all user inputs
✅ Sanitize scraped content
DON'Ts ❌
❌ Never commit secrets to Git
❌ Never share credentials in plaintext
❌ Never disable SSL/TLS verification
❌ Never skip input validation
❌ Never trust user inputs
❌ Never hardcode sensitive data
❌ Never use personal email for production
🐛 Troubleshooting
Email Not Sending
Error: SMTP authentication failed
Solution: 
1. Check App Password is correct (16 characters)
2. Verify 2FA is enabled
3. Check SMTP_USER matches the email generating the App Password
Rate Limit Exceeded
Error: Rate limit exceeded (20 per hour)
Solution:
1. Wait for the rate limit window to expire (60 minutes)
2. Or increase MAX_EMAILS_PER_HOUR in config.py
PDF Validation Failed
Error: Invalid PDF file (missing PDF signature)
Solution:
1. Ensure IPID files are valid PDFs
2. Check file corruption
3. Re-download IPID documents
Image Upload Failed
Error: File content doesn't match extension
Solution:
1. Ensure file is actually an image (not renamed)
2. Use supported formats: JPG, PNG, WebP
3. Check file isn't corrupted
📊 Monitoring & Logs
View Logs (Local)
streamlit run app.py --logger.level=debug
Log Locations
Streamlit Cloud: View in Cloud dashboard under "Logs"
Local: Terminal output
Key Metrics to Monitor
Email send success rate
Rate limit hits
PDF generation failures
Validation errors
SMTP connection issues
🔄 Updates & Maintenance
Updating Dependencies
pip install --upgrade -r requirements.txt
Security Updates
# Check for vulnerabilities
pip install safety
safety check

# Update critical packages
pip install --upgrade requests beautifulsoup4 reportlab pypdf
📞 Support
For security issues or bugs:

Check logs for error details
Review troubleshooting section
Contact: xiatropoulos@gmail.com
📄 License
Proprietary - PETSHEALTH Internal Use Only

Built with security in mind 🛡️
Version 1.0 - January 2026