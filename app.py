"""
PETSHEALTH Quote Engine - Secure Main Application
Professional pet insurance quote generation with comprehensive security
UPDATED: New email system with professional HTML templates
"""
import logging
from datetime import date
from typing import Optional

import streamlit as st

# Import secure utilities
from config import (
    APP_TITLE, APP_ICON, PLAN_KEYS, ADVISOR_EMAIL,
    PETSHEALTH_HOME_URL, PETSHEALTH_TEAM_URL, EUROLIFE_URL, INTERLIFE_URL,
    MAX_POLAROID_IMAGES,
)
from input_validators import (
    validate_email, validate_phone, validate_date, validate_price, validate_count,
    validate_client_data, sanitize_text_input, sanitize_text_area,
    ValidationError, validate_image_file,
)
from petshealth_email_standalone import send_petshealth_quote
from web_utils import fetch_highlights, fetch_site_images, download_image_bytes, WebScrapingError
from pdf_utils import merge_quote_with_ipids, get_ipid_status, PDFError
from pdf_builder import build_quote_pdf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --------------------------
# PAGE CONFIG
# --------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better security indicators
st.markdown("""
<style>
.security-indicator {
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
}
.security-ok {
    background: #D1FAE5;
    color: #065F46;
    border-left: 4px solid #10B981;
}
.security-warning {
    background: #FEF3C7;
    color: #92400E;
    border-left: 4px solid #F59E0B;
}
.security-error {
    background: #FEE2E2;
    color: #991B1B;
    border-left: 4px solid #EF4444;
}
</style>
""", unsafe_allow_html=True)

# --------------------------
# SESSION STATE INITIALIZATION
# --------------------------
if "site_images" not in st.session_state:
    st.session_state.site_images = []
if "official_bio" not in st.session_state:
    st.session_state.official_bio = ""
if "official_eurolife" not in st.session_state:
    st.session_state.official_eurolife = ""
if "official_interlife" not in st.session_state:
    st.session_state.official_interlife = ""
if "pdf_generated" not in st.session_state:
    st.session_state.pdf_generated = False
if "final_pdf_bytes" not in st.session_state:
    st.session_state.final_pdf_bytes = None
if "final_filename" not in st.session_state:
    st.session_state.final_filename = None

# --------------------------
# HEADER UI
# --------------------------
st.markdown(
    """
    <div style="padding:20px 24px;border-radius:16px;background:linear-gradient(135deg,#111827 0%,#1E4FA8 100%);color:white;box-shadow:0 4px 12px rgba(0,0,0,0.15);">
      <div style="font-size:28px;font-weight:900;letter-spacing:0.3px;margin-bottom:8px;">
        🐾 PETSHEALTH – Pet Insurance Quote Engine
      </div>
      <div style="opacity:0.95;font-size:15px;line-height:1.5;">
        Επαγγελματική δημιουργία προσφορών • Σύγκριση προγραμμάτων • IPID pages • Αυτόματη αποστολή email
      </div>
      <div style="margin-top:12px;padding:10px 16px;background:rgba(255,255,255,0.15);border-radius:8px;font-size:13px;">
        <strong>🛡️ Secure Quote Engine</strong> – Enterprise-grade security with input validation and professional HTML emails
      </div>
    </div>
    """,
    unsafe_allow_html=True
)
st.write("")

# --------------------------
# SIDEBAR
# --------------------------
with st.sidebar:
    st.subheader("⚙️ Output Settings")

    selected_plans = st.multiselect(
        "Select plan(s)",
        PLAN_KEYS,
        default=PLAN_KEYS,
        help="Choose which plans to include in the quote"
    )

    include_ipid = st.toggle("📄 Append IPID pages (recommended)", value=True)

    st.divider()

    # IPID status
    if selected_plans:
        st.caption("📋 **IPID Status**")
        ipid_status = get_ipid_status(selected_plans)

        if ipid_status["missing"]:
            st.warning(f"⚠️ {len(ipid_status['missing'])} IPID(s) missing")
            with st.expander("View missing IPIDs"):
                for item in ipid_status["missing"]:
                    st.text(f"• {item['plan']}: {item['reason']}")
        else:
            st.success(f"✅ All {len(ipid_status['available'])} IPIDs available")

    st.divider()
    st.caption(f"🔒 **Security**: Auto CC to {ADVISOR_EMAIL}")
    st.caption("📧 **Email**: Professional HTML templates")


# --------------------------
# HELPER FUNCTIONS
# --------------------------

def safe_input(
        label: str,
        value: str = "",
        placeholder: str = "",
        validation_func: Optional[callable] = None,
        error_message: str = "Invalid input",
        max_length: int = 500,
) -> tuple[str, bool]:
    """
    Create a text input with validation feedback.

    Returns:
        (value, is_valid)
    """
    input_value = st.text_input(label, value=value, placeholder=placeholder, max_chars=max_length)

    if input_value and validation_func:
        is_valid = validation_func(input_value)
        if not is_valid:
            st.error(f"❌ {error_message}")
            return input_value, False

    return input_value, True


def lines(txt: str) -> list[str]:
    """Split text into non-empty lines"""
    return [x.strip() for x in (txt or "").splitlines() if x.strip()]


# --------------------------
# CLIENT & PET INFORMATION
# --------------------------
st.subheader("👤 Client & Pet Information")

c1, c2 = st.columns([1, 1], gap="large")

with c1:
    st.markdown("#### Client Details")

    client_name = st.text_input(
        "Client Name *",
        value="",
        placeholder="e.g. Γιώργος Παπαδόπουλος",
        max_chars=200,
        help="Required field"
    )

    client_phone = st.text_input(
        "Phone *",
        value="",
        placeholder="e.g. +30 210 123 4567",
        max_chars=20,
        help="Required field"
    )
    # Validate phone
    if client_phone and not validate_phone(client_phone):
        st.error("❌ Invalid phone number format")

    client_email = st.text_input(
        "Email *",
        value="",
        placeholder="e.g. client@example.com",
        max_chars=254,
        help="Required field - will be validated"
    )
    # Validate email in real-time
    if client_email:
        if validate_email(client_email):
            st.success("✅ Valid email address")
        else:
            st.error("❌ Invalid email address")

    location = st.text_input(
        "Location (optional)",
        value="",
        placeholder="e.g. Αθήνα, Κέντρο",
        max_chars=200
    )

with c2:
    st.markdown("#### Quote Mode")

    quote_mode = st.radio(
        "Mode",
        ["Detailed (single pet)", "Bulk (number of pets)"],
        horizontal=True
    )

    pet_count = 1
    bulk_summary = ""

    if quote_mode == "Bulk (number of pets)":
        pet_count = int(st.number_input(
            "Number of pets *",
            min_value=1,
            max_value=50,
            value=2,
            step=1,
            help="Maximum 50 pets per quote"
        ))

        bulk_summary = st.text_area(
            "Bulk description (optional)",
            value="",
            max_chars=2000,
            height=120,
            placeholder="e.g. 6 dogs, mixed breeds, 20-40kg, ages 2-5 years, Athens location"
        )

st.write("")
st.markdown("#### 🐕 Pet Details (for Detailed mode)")

p1, p2, p3 = st.columns(3, gap="large")

with p1:
    pet_name = st.text_input(
        "Pet Name",
        value="",
        placeholder="e.g. Max",
        max_chars=100
    )
    pet_species = st.selectbox("Species", ["Dog", "Cat"], index=0)

with p2:
    pet_breed = st.text_input(
        "Breed",
        value="",
        placeholder="e.g. Λαμπραντόρ",
        max_chars=100
    )
    pet_dob = st.text_input(
        "Date of Birth (dd/mm/yyyy)",
        value="",
        placeholder="e.g. 15/03/2020",
        max_chars=10
    )
    # Validate date format
    if pet_dob and not validate_date(pet_dob):
        st.error("❌ Invalid date format (use dd/mm/yyyy)")

with p3:
    pet_microchip = st.text_input(
        "Microchip ID",
        value="",
        placeholder="e.g. 977200...",
        max_chars=50
    )

st.divider()

# --------------------------
# PLANS & PRICING
# --------------------------
st.subheader("💶 Plans & Pricing")

pc1, pc2 = st.columns(2, gap="large")

with pc1:
    st.markdown("### 🏥 Plan 1 (Insurance)")
    plan_1_name = st.text_input("Plan 1 Name", value="PET CARE PLUS", max_chars=200)
    plan_1_provider = st.text_input("Plan 1 Provider", value="INTERLIFE", max_chars=200)
    plan_1_price = st.number_input(
        "Plan 1 Annual Premium (€)",
        min_value=0.0,
        max_value=10000.0,
        value=189.0,
        step=1.0,
        help="Maximum €10,000"
    )

with pc2:
    st.markdown("### 🏨 Plan 2 (Network)")
    plan_2_name = st.text_input(
        "Plan 2 Name",
        value="EUROLIFE My Happy Pet (SAFE PET SYSTEM)",
        max_chars=200
    )
    plan_2_provider = st.text_input("Plan 2 Provider", value="EUROLIFE", max_chars=200)
    plan_2_price = st.number_input(
        "Plan 2 Annual Premium (€)",
        min_value=0.0,
        max_value=10000.0,
        value=85.0,
        step=1.0,
        help="Maximum €10,000"
    )

quote_date = st.date_input("Quote Date", value=date.today())

# Calculate total
mult = int(pet_count) if "Bulk" in quote_mode else 1
total = 0.0
if "PET CARE PLUS (INTERLIFE)" in selected_plans:
    total += float(plan_1_price) * mult
if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
    total += float(plan_2_price) * mult

st.metric("💰 Total Annual Premium", f"{total:.2f} €", help="Total cost for all selected plans")

marketing_hook = st.text_input(
    "Marketing headline (Page 1)",
    value="Προστασία υγείας για τα κατοικίδια – χωρίς άγχος κόστους.",
    max_chars=150,
    help="Keep it short and impactful"
)

notes = st.text_area(
    "Notes / Disclaimer (Page 1)",
    value=(
        "Το παρόν αποτελεί μη δεσμευτική προσφορά. Οι τελικοί όροι, προϋποθέσεις, εξαιρέσεις και καλύψεις ισχύουν "
        "όπως αναγράφονται στα επίσημα έγγραφα των ασφαλιστικών εταιρειών (Policy Wording / IPID). "
        "Υπάρχει η δυνατότητα τα προγράμματα να δοθούν μεμονωμένα."
    ),
    max_chars=2000,
    height=90
)

st.divider()

# --------------------------
# COVERAGE DETAILS (Page 2)
# --------------------------
st.subheader("📋 Coverage Details (Page 2)")

with st.expander(
        "🏥 PET CARE PLUS (INTERLIFE) – Coverage fields",
        expanded=("PET CARE PLUS (INTERLIFE)" in selected_plans)
):
    plan1_limit = st.text_input("Limit", value="2.000€ / ανά έτος", max_chars=200)
    plan1_area = st.text_input("Geographic Area", value="Ελλάδα", max_chars=200)

    plan1_key_facts_txt = st.text_area(
        "Key Facts (one per line)",
        value="\n".join([
            "Ελεύθερη επιλογή κτηνιάτρου και κλινικής",
            "Απαλλαγή: 50€ ανά περιστατικό (όπου εφαρμόζεται)",
        ]),
        max_chars=2000,
        height=90
    )

    plan1_covers_txt = st.text_area(
        "Covers (one per line)",
        value="\n".join([
            "2.000€ για δαπάνες νοσηλείας (προϋπόθεση διανυκτέρευση, max 5 διανυκτερεύσεις)",
            "500€ για ιατρικές επισκέψεις & διαγνωστικές εξετάσεις",
            "Απώλεια ζωής: έως 250€ (αφαιρούνται τυχόν νοσοκομειακές δαπάνες από το κεφάλαιο θανάτου)",
            "Αστική ευθύνη κηδεμόνα: 10.000€ / έτος (απαλλαγή 50€ ανά απαίτηση)",
            "Νομική προστασία κηδεμόνα: 5.000€ (απαλλαγή 50€ ανά περιστατικό)",
        ]),
        max_chars=3000,
        height=150
    )

    plan1_exclusions_txt = st.text_area(
        "Not Covered (one per line)",
        value="\n".join([
            "Check up",
            "Εμβολιασμοί",
            "Οδοντιατρικές πράξεις (πλην ατύχημα όπου προβλέπεται)",
            "Προϋπάρχουσες παθήσεις",
            "Συγγενείς παθήσεις",
        ]),
        max_chars=2000,
        height=120
    )

    plan1_waiting_txt = st.text_area(
        "Waiting Periods (one per line)",
        value="\n".join([
            "Ασθένεια: 60 ημέρες από την έναρξη",
            "Απώλεια ζωής: 180 ημέρες από την έναρξη",
            "Ατύχημα: από την έναρξη του συμβολαίου",
        ]),
        max_chars=2000,
        height=100
    )

with st.expander(
        "🏨 EUROLIFE My Happy Pet – Coverage fields",
        expanded=("EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans)
):
    plan2_limit = st.text_input("Limit (Plan 2)", value="Απεριόριστο (εντός δικτύου, με συμμετοχή)", max_chars=200)
    plan2_area = st.text_input("Geographic Area (Plan 2)", value="Αττική – Θεσσαλονίκη (συμβεβλημένο δίκτυο)",
                               max_chars=200)

    plan2_key_facts_txt = st.text_area(
        "Key Facts (one per line)",
        value="\n".join([
            "Αποκλειστικά συμβεβλημένο δίκτυο κτηνιάτρων & κλινικών",
            "Απαλλαγή: 0€ (λειτουργεί με συμμετοχή ανά υπηρεσία)",
            "Ειδικός εκπτωτικός τιμοκατάλογος για μέλη του δικτύου",
        ]),
        max_chars=2000,
        height=100
    )

    plan2_covers_txt = st.text_area(
        "Covers (one per line)",
        value="\n".join([
            "Νοσοκομειακές δαπάνες, ιατρικές επισκέψεις & διαγνωστικές εντός δικτύου με συμμετοχή",
            "Ετήσιο Check Up δωρεάν (Kala-azar & Ερλίχια)",
            "Εμβολιασμοί/Οδοντιατρικά σε ειδικό τιμοκατάλογο (εντός δικτύου)",
            "Προϋπάρχουσες παθήσεις: καλύπτονται",
            "Συγγενείς παθήσεις: καλύπτονται",
        ]),
        max_chars=3000,
        height=160
    )

    plan2_exclusions_txt = st.text_area(
        "Not Covered / Limits (one per line)",
        value="\n".join([
            "Εκτός δικτύου: δεν ισχύει κάλυψη/τιμοκατάλογος",
            "Απαιτείται microchip",
            "Φάρμακα: σύμφωνα με όρους/τιμοκατάλογο προγράμματος",
        ]),
        max_chars=2000,
        height=120
    )

    plan2_waiting_txt = st.text_area(
        "Waiting Periods (one per line)",
        value="\n".join([
            "Ατύχημα ή ασθένεια: από την έναρξη του συμβολαίου (σύμφωνα με όρους προγράμματος)",
        ]),
        max_chars=2000,
        height=90
    )

st.divider()

# --------------------------
# POLAROID IMAGES
# --------------------------
st.subheader("📸 Happy Photos (Polaroids – 2 per page)")

a, b = st.columns([1, 1], gap="large")

with a:
    if st.button("🌐 Load images from petshealth.gr", use_container_width=True):
        with st.spinner("Fetching images..."):
            try:
                images = fetch_site_images(PETSHEALTH_HOME_URL, limit=18)
                st.session_state.site_images = images
                st.success(f"✅ Loaded {len(images)} images from site")
            except WebScrapingError as e:
                st.error(f"❌ Failed to load images: {e}")
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")
                logger.error(f"Image fetch error: {e}", exc_info=True)

with b:
    st.caption(f"Pick 2–{MAX_POLAROID_IMAGES} images (rotated across pages)")

# Site image selection
site_images = st.session_state.get("site_images", [])
selected_image_urls = []

if site_images:
    selected_image_urls = st.multiselect(
        f"Select site images (2–{MAX_POLAROID_IMAGES})",
        site_images,
        default=site_images[:2] if len(site_images) >= 2 else site_images
    )

# File upload
uploaded = st.file_uploader(
    "Or upload your own images (JPG/PNG/WebP)",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    help=f"Maximum {MAX_POLAROID_IMAGES} images total"
)

st.divider()

# --------------------------
# ABOUT & HIGHLIGHTS (Page 3)
# --------------------------
st.subheader("ℹ️ About & Official Highlights (Page 3)")

x1, x2 = st.columns([1, 1], gap="large")

with x1:
    if st.button("🌐 Load official highlights from web", use_container_width=True):
        with st.spinner("Fetching content from PETSHEALTH, EUROLIFE, INTERLIFE..."):
            try:
                from web_utils import fetch_all_content

                urls = {
                    "bio": PETSHEALTH_TEAM_URL,
                    "eurolife": EUROLIFE_URL,
                    "interlife": INTERLIFE_URL,
                }

                results = fetch_all_content(urls, max_highlights=8)

                st.session_state.official_bio = "\n".join(results.get("bio", []))
                st.session_state.official_eurolife = "\n".join([f"• {x}" for x in results.get("eurolife", [])])
                st.session_state.official_interlife = "\n".join([f"• {x}" for x in results.get("interlife", [])])

                st.success("✅ Content loaded. Review and edit before generating PDF.")

            except Exception as e:
                st.error(f"❌ Failed to load highlights: {e}")
                logger.error(f"Highlights fetch error: {e}", exc_info=True)

with x2:
    st.caption("Keep it short & trust-based (marketing)")

about_bio = st.text_area(
    "Advisor Bio (editable – recommended 5–7 lines)",
    value=st.session_state.official_bio,
    max_chars=3000,
    height=150,
    help="Brief professional bio to build trust"
)

cii_titles = st.text_area(
    "CII Titles / Credentials (one per line)",
    value="\n".join([
        "CII – (PL4) Introduction to Pet Insurance (Unit achieved: June 2023)",
        "CII – (W01) Award in General Insurance (English) (Unit achieved: March 2025)",
    ]),
    max_chars=1000,
    height=90
)

official_eurolife = st.text_area(
    "EUROLIFE highlights (bullets)",
    value=st.session_state.official_eurolife,
    max_chars=3000,
    height=140
)

official_interlife = st.text_area(
    "INTERLIFE highlights (bullets)",
    value=st.session_state.official_interlife,
    max_chars=3000,
    height=140
)

st.divider()

# --------------------------
# GENERATE PDF
# --------------------------
st.subheader("🎨 Generate PDF Quote")

# Pre-generation validation
validation_errors = []

if not client_name.strip():
    validation_errors.append("Client name is required")
if not client_email.strip():
    validation_errors.append("Client email is required")
elif not validate_email(client_email):
    validation_errors.append("Client email is invalid")
if not client_phone.strip():
    validation_errors.append("Client phone is required")
elif not validate_phone(client_phone):
    validation_errors.append("Client phone format is invalid")

if pet_dob and not validate_date(pet_dob):
    validation_errors.append("Pet date of birth format is invalid (use dd/mm/yyyy)")

if not selected_plans:
    validation_errors.append("At least one plan must be selected")

if validation_errors:
    st.error("❌ **Please fix the following errors before generating PDF:**")
    for err in validation_errors:
        st.error(f"  • {err}")

generate = st.button(
    "✨ Generate Professional PDF Quote",
    type="primary",
    use_container_width=True,
    disabled=(len(validation_errors) > 0)
)

if generate:
    try:
        with st.spinner("🎨 Building professional PDF quote..."):

            # Sanitize all inputs
            sanitized_data = {
                "marketing_hook": sanitize_text_input(marketing_hook, 150),
                "client_name": sanitize_text_input(client_name),
                "client_phone": sanitize_text_input(client_phone, 20),
                "client_email": sanitize_text_input(client_email, 254),
                "location": sanitize_text_input(location),
                "quote_mode": quote_mode,
                "pet_count": int(pet_count),
                "bulk_summary": sanitize_text_area(bulk_summary),
                "pet_name": sanitize_text_input(pet_name),
                "pet_species": pet_species,
                "pet_breed": sanitize_text_input(pet_breed),
                "pet_dob": sanitize_text_input(pet_dob, 10),
                "pet_microchip": sanitize_text_input(pet_microchip, 50),
                "plan_1_name": sanitize_text_input(plan_1_name),
                "plan_1_provider": sanitize_text_input(plan_1_provider),
                "plan_1_price": f"{float(plan_1_price):.2f}",
                "plan_2_name": sanitize_text_input(plan_2_name),
                "plan_2_provider": sanitize_text_input(plan_2_provider),
                "plan_2_price": f"{float(plan_2_price):.2f}",
                "selected_plans": selected_plans,
                "price_multiplier": int(mult),
                "plan_1_price_total": f"{float(plan_1_price) * mult:.2f}",
                "plan_2_price_total": f"{float(plan_2_price) * mult:.2f}",
                "total_price": f"{total:.2f} €",
                "quote_date": quote_date.strftime("%d/%m/%Y"),
                "notes": sanitize_text_area(notes),
                "plan1_limit": sanitize_text_input(locals().get("plan1_limit", "")),
                "plan1_area": sanitize_text_input(locals().get("plan1_area", "")),
                "plan1_key_facts": lines(locals().get("plan1_key_facts_txt", "")),
                "plan1_covers": lines(locals().get("plan1_covers_txt", "")),
                "plan1_exclusions": lines(locals().get("plan1_exclusions_txt", "")),
                "plan1_waiting": lines(locals().get("plan1_waiting_txt", "")),
                "plan2_limit": sanitize_text_input(locals().get("plan2_limit", "")),
                "plan2_area": sanitize_text_input(locals().get("plan2_area", "")),
                "plan2_key_facts": lines(locals().get("plan2_key_facts_txt", "")),
                "plan2_covers": lines(locals().get("plan2_covers_txt", "")),
                "plan2_exclusions": lines(locals().get("plan2_exclusions_txt", "")),
                "plan2_waiting": lines(locals().get("plan2_waiting_txt", "")),
                "about_bio": sanitize_text_area(about_bio),
                "cii_titles": lines(cii_titles),
                "official_eurolife": [x.lstrip("•").strip() for x in lines(official_eurolife)],
                "official_interlife": [x.lstrip("•").strip() for x in lines(official_interlife)],
            }

            # Process polaroid images
            polaroid_bytes = []

            # Download selected site images
            for url in (selected_image_urls or [])[:MAX_POLAROID_IMAGES]:
                try:
                    img_bytes = download_image_bytes(url)
                    if img_bytes:
                        polaroid_bytes.append(img_bytes)
                except Exception as e:
                    logger.warning(f"Failed to download image {url}: {e}")

            # Add uploaded images
            if uploaded:
                for uploaded_file in uploaded[:MAX_POLAROID_IMAGES]:
                    try:
                        img_bytes = uploaded_file.read()
                        # Validate image
                        validate_image_file(img_bytes, uploaded_file.name)
                        polaroid_bytes.append(img_bytes)
                    except ValidationError as e:
                        st.warning(f"⚠️ Skipped {uploaded_file.name}: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to process uploaded image: {e}")

            # Limit total images
            polaroid_bytes = polaroid_bytes[:MAX_POLAROID_IMAGES]
            sanitized_data["polaroid_images"] = polaroid_bytes

            logger.info(f"Building PDF with {len(polaroid_bytes)} polaroid images")

            # Generate quote PDF
            quote_pdf_bytes = build_quote_pdf(sanitized_data)
            logger.info("Quote PDF generated successfully")

            # Merge with IPIDs
            if include_ipid:
                final_pdf_bytes = merge_quote_with_ipids(quote_pdf_bytes, selected_plans)
                logger.info("PDFs merged successfully")
            else:
                final_pdf_bytes = quote_pdf_bytes

            # Generate safe filename
            from input_validators import sanitize_filename

            safe_client = sanitize_filename(client_name or "Client")
            safe_pet = sanitize_filename(pet_name or ("Bulk" if "Bulk" in quote_mode else "Pet"))
            filename = f"PETSHEALTH_Quote_{safe_client}_{safe_pet}_{quote_date.strftime('%Y%m%d')}.pdf"

            # Store in session state
            st.session_state.pdf_generated = True
            st.session_state.final_pdf_bytes = final_pdf_bytes
            st.session_state.final_filename = filename

            st.success("✅ PDF generated successfully!")

            # Download button
            st.download_button(
                "📥 Download Final PDF (Quote + IPID)",
                data=final_pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True
            )

    except PDFError as e:
        st.error(f"❌ PDF generation failed: {e}")
        logger.error(f"PDF error: {e}", exc_info=True)
    except ValidationError as e:
        st.error(f"❌ Validation error: {e}")
        logger.error(f"Validation error: {e}")
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")
        logger.error(f"Unexpected error generating PDF: {e}", exc_info=True)

st.divider()

# --------------------------
# SEND EMAIL
# --------------------------
st.subheader("📧 Send Quote via Email")

st.markdown("""
<div class="security-indicator security-ok" style="margin-bottom:16px;">
<strong>📬 Secure Email Delivery</strong><br>
• Professional HTML email template (Greek/English)<br>
• Automatically CC'd to <strong>""" + ADVISOR_EMAIL + """</strong><br>
• TLS encrypted transmission
</div>
""", unsafe_allow_html=True)

# Check if PDF is generated
if not st.session_state.pdf_generated:
    st.warning("⚠️ Please generate the PDF first before sending email")
else:
    recipient = st.text_input(
        "📧 Recipient email *",
        value=client_email.strip() if client_email else "",
        placeholder="client@example.com",
        max_chars=254
    )

    # Real-time email validation
    email_valid = False
    if recipient:
        if validate_email(recipient):
            st.success("✅ Valid email address")
            email_valid = True
        else:
            st.error("❌ Invalid email address format")

    # Language selection
    email_language = st.radio(
        "Email language:",
        ["🇬🇷 Greek", "🇬🇧 English"],
        horizontal=True,
        index=0
    )

    lang_code = "el" if "Greek" in email_language else "en"

    # Custom subject (optional)
    with st.expander("✏️ Customize email subject (optional)"):
        custom_subject = st.text_input(
            "Custom subject line",
            value="",
            placeholder="Leave empty for auto-generated subject",
            max_chars=200
        )

    # Show preview
    with st.expander("👀 Preview email content"):
        if lang_code == "el":
            st.markdown(f"""
**Subject:** Προσφορά Ασφάλισης Κατοικιδίου - {client_name or 'Client'}

**Email Body Preview:**
- Professional HTML design with PETSHEALTH branding
- Quote summary box showing: **{total:.2f} €**
- Coverage highlights
- Contact information
- Tagline: "Επειδή νοιαζόμαστε για τα κατοικίδιά σας όσο κι εσείς."
            """)
        else:
            st.markdown(f"""
**Subject:** Pet Insurance Quote - {client_name or 'Client'}

**Email Body Preview:**
- Professional HTML design with PETSHEALTH branding
- Quote summary box showing: **€{total:.2f}**
- Coverage highlights
- Contact information
- Tagline: "Because we care for your pets as much as you do."
            """)

        st.info("📧 Email body is auto-generated. Professional HTML formatting included.")

    # Send button
    send_btn = st.button(
        "🚀 Send Professional Quote Email",
        type="primary",
        use_container_width=True,
        disabled=(not email_valid or not st.session_state.pdf_generated)
    )

    if send_btn:
        try:
            with st.spinner("📤 Sending professional quote email..."):
                result = send_petshealth_quote(
                    to_email=recipient,
                    client_name=client_name or "Valued Customer",
                    pdf_bytes=st.session_state.final_pdf_bytes,
                    total_premium=f"€{total:.2f}",
                    subject=custom_subject.strip() if custom_subject.strip() else None,
                    cc_email=ADVISOR_EMAIL,
                    language=lang_code,
                    filename=st.session_state.final_filename,
                    use_html=True
                )

            if result["success"]:
                st.success(f"""
✅ **Email sent successfully!**

📧 **To:** {result['to']}  
📋 **CC:** {result['cc']}  
📦 **Size:** {result['size_mb']}MB  
⏱️ **Time:** {result['elapsed_seconds']}s
                """)
                st.balloons()
            else:
                st.error("❌ Email sending failed")

        except Exception as e:
            st.error(f"❌ **Error sending email:**\n\n{str(e)}")

            # Show helpful error message
            if "Authentication" in str(e) or "SMTP" in str(e):
                st.info("""
💡 **SMTP Authentication Issue?**

For Gmail:
1. Go to https://myaccount.google.com/apppasswords
2. Generate App Password (16 characters)
3. Set in Streamlit secrets (.streamlit/secrets.toml):
   ```toml
   SMTP_USER = "your@gmail.com"
   SMTP_PASSWORD = "your_16char_app_password"
   ```
                """)

            logger.error(f"Email error: {e}", exc_info=True)

# --------------------------
# FOOTER
# --------------------------
st.divider()
st.caption("🛡️ **PETSHEALTH Quote Engine v1.0** | Secure • Professional • Compliant")
st.caption("🚀 Powered by professional HTML email delivery")