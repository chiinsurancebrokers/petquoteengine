"""
PETSHEALTH Quote Engine - Secure Main Application
Professional pet insurance quote generation with comprehensive security
UPDATED: New email system with professional HTML templates + HOOLIE INTEGRATION
"""
import logging
from datetime import date
from typing import Optional

import streamlit as st

# Import secure utilities
from config import (
    APP_TITLE, APP_ICON, PLAN_KEYS, ADVISOR_EMAIL,
    PETSHEALTH_HOME_URL, PETSHEALTH_TEAM_URL, EUROLIFE_URL, INTERLIFE_URL,
    HOOLIE_DOG_URL, HOOLIE_CAT_URL,
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
from hoolie_config import (
    HOOLIE_DOG_PLANS, HOOLIE_CAT_PLANS,
    HOOLIE_DOG_BREED_SURCHARGES, HOOLIE_INFO,
    get_hoolie_price
)

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
    st.session_state.official_eurolife = []
if "official_interlife" not in st.session_state:
    st.session_state.official_interlife = []
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
        default=PLAN_KEYS[:2],  # Default to first 2 plans
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

    # Weight for Hoolie pricing
    pet_weight = st.number_input(
        "Weight (kg)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.5,
        help="Required for Hoolie plans"
    )

st.divider()

# --------------------------
# PLANS & PRICING
# --------------------------
st.subheader("💶 Plans & Pricing")

# Dynamic plan pricing based on selection
plan_prices = {}
hoolie_warnings = []

# Check if any Hoolie plans are selected
has_hoolie = any("HOOLIE" in plan for plan in selected_plans)

if has_hoolie:
    st.info("💡 **Hoolie Plans Selected**: Prices calculated based on pet weight and breed")

    for plan_key in selected_plans:
        if "HOOLIE" in plan_key:
            # Determine pet type and plan tier
            pet_type_hoolie = "dog" if "Dog" in plan_key else "cat"

            if "Silver" in plan_key:
                plan_tier = "Silver"
            elif "Gold" in plan_key:
                plan_tier = "Gold"
            else:
                plan_tier = "Platinum Dynasty"

            # Determine weight category
            if pet_weight > 0:
                if pet_type_hoolie == "dog":
                    if pet_weight <= 10:
                        weight_cat = "έως 10 κιλά"
                    elif pet_weight <= 20:
                        weight_cat = "10-20 κιλά"
                    elif pet_weight <= 40:
                        weight_cat = "20-40 κιλά"
                    else:
                        weight_cat = ">40 κιλά"
                else:  # cat
                    if pet_weight <= 10:
                        weight_cat = "έως 10 κιλά"
                    else:
                        weight_cat = "10-20 κιλά"

                try:
                    price = get_hoolie_price(pet_type_hoolie, plan_tier, weight_cat, pet_breed if pet_type_hoolie == "dog" else None)
                    plan_prices[plan_key] = price

                    # Check for breed surcharge
                    if pet_type_hoolie == "dog" and pet_breed:
                        if pet_breed in HOOLIE_DOG_BREED_SURCHARGES["5%"]:
                            hoolie_warnings.append(f"⚠️ {plan_key}: 5% breed surcharge applied for {pet_breed}")
                        elif pet_breed in HOOLIE_DOG_BREED_SURCHARGES["20%"]:
                            hoolie_warnings.append(f"⚠️ {plan_key}: 20% breed surcharge applied for {pet_breed}")
                except Exception as e:
                    st.error(f"❌ Error calculating {plan_key} price: {e}")
                    plan_prices[plan_key] = 0.0
            else:
                st.warning(f"⚠️ {plan_key}: Please enter pet weight to calculate price")
                plan_prices[plan_key] = 0.0

# Display breed surcharge warnings
for warning in hoolie_warnings:
    st.warning(warning)

pc1, pc2 = st.columns(2, gap="large")

with pc1:
    st.markdown("### 🏥 Plan 1 (Insurance)")
    plan_1_name = st.text_input("Plan 1 Name", value="PET CARE PLUS", max_chars=200)
    plan_1_provider = st.text_input("Plan 1 Provider", value="INTERLIFE", max_chars=200)

    # Check if it's a Hoolie plan
    plan_1_key = "PET CARE PLUS (INTERLIFE)"
    if plan_1_key in plan_prices:
        plan_1_price = plan_prices[plan_1_key]
        st.number_input(
            "Plan 1 Annual Premium (€)",
            value=float(plan_1_price),
            disabled=True,
            help="Auto-calculated for Hoolie"
        )
    else:
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

    # Check if it's a Hoolie plan
    plan_2_key = "EUROLIFE My Happy Pet (SAFE PET SYSTEM)"
    if plan_2_key in plan_prices:
        plan_2_price = plan_prices[plan_2_key]
        st.number_input(
            "Plan 2 Annual Premium (€)",
            value=float(plan_2_price),
            disabled=True,
            help="Auto-calculated for Hoolie"
        )
    else:
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

for plan_key in selected_plans:
    if plan_key in plan_prices:
        total += float(plan_prices[plan_key]) * mult
    elif "PET CARE PLUS (INTERLIFE)" == plan_key:
        total += float(plan_1_price) * mult
    elif "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" == plan_key:
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

# For each selected plan, show appropriate expander
for plan_key in selected_plans:
    if "HOOLIE" in plan_key:
        # Hoolie plan - auto-populate from hoolie_config
        pet_type_config = "dog" if "Dog" in plan_key else "cat"
        plans_config = HOOLIE_DOG_PLANS if pet_type_config == "dog" else HOOLIE_CAT_PLANS

        if "Silver" in plan_key:
            plan_tier_config = "Silver"
        elif "Gold" in plan_key:
            plan_tier_config = "Gold"
        else:
            plan_tier_config = "Platinum Dynasty"

        plan_data = plans_config[plan_tier_config]

        with st.expander(f"🐾 {plan_key} – Coverage (Auto-populated)", expanded=False):
            st.info(f"✅ Hoolie plan coverage auto-loaded from configuration")
            st.caption(f"**Capital**: {plan_data['capital']}")
            st.caption(f"**Medicines**: {plan_data['coverage']['Φάρμακα (Συνταγογραφούμενα)']}")
            st.caption(f"**AI Diagnosis**: {plan_data['coverage']['Διάγνωση με Hoolie AI']}")
            st.caption(f"**Legal Protection**: {plan_data['coverage']['Νομική προστασία (διοίκητη)']}")

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

# Rest of the app continues with original code...
# (Continue with polaroid images section and beyond - keeping same as original)

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

with b:
    uploaded_files = st.file_uploader(
        "Or upload images (JPG, PNG, WebP)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        help=f"Max {MAX_POLAROID_IMAGES} images, 10MB each"
    )

    if uploaded_files:
        valid_images = []
        for uploaded_file in uploaded_files[:MAX_POLAROID_IMAGES]:
            try:
                validate_image_file(uploaded_file)
                img_bytes = uploaded_file.read()
                valid_images.append((uploaded_file.name, img_bytes))
            except ValidationError as ve:
                st.error(f"❌ {uploaded_file.name}: {ve}")
            except Exception as e:
                st.error(f"❌ {uploaded_file.name}: Unexpected error")

        if valid_images:
            st.session_state.site_images = valid_images
            st.success(f"✅ {len(valid_images)} image(s) validated and ready")

if st.session_state.site_images:
    st.info(f"📷 {len(st.session_state.site_images)} image(s) loaded for polaroids")

st.divider()

# --------------------------
# OFFICIAL HIGHLIGHTS (Page 3)
# --------------------------
st.subheader("🌟 Official Highlights (Page 3)")

h1, h2 = st.columns(2, gap="large")

with h1:
    if st.button("📄 Load Eurolife official info", use_container_width=True):
        with st.spinner("Fetching Eurolife data..."):
            try:
                eur_highlights = fetch_highlights(EUROLIFE_URL)
                st.session_state.official_eurolife = eur_highlights
                st.success(f"✅ Eurolife info loaded ({len(eur_highlights)} highlights)")
            except WebScrapingError as e:
                st.error(f"❌ Failed: {e}")
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")

with h2:
    if st.button("📄 Load Interlife official info", use_container_width=True):
        with st.spinner("Fetching Interlife data..."):
            try:
                int_highlights = fetch_highlights(INTERLIFE_URL)
                st.session_state.official_interlife = int_highlights
                st.success(f"✅ Interlife info loaded ({len(int_highlights)} highlights)")
            except WebScrapingError as e:
                st.error(f"❌ Failed: {e}")
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")

custom_highlights = st.text_area(
    "Custom highlights (optional – override defaults)",
    value="",
    max_chars=5000,
    height=120,
    placeholder="One highlight per line..."
)

st.divider()

# --------------------------
# ABOUT US BIO (Page 3)
# --------------------------
st.subheader("📖 About Us Bio (Page 3)")

ab1, ab2 = st.columns([1, 1], gap="large")

with ab1:
    if st.button("🌐 Load bio from petshealth.gr/team", use_container_width=True):
        with st.spinner("Fetching bio..."):
            try:
                bio_items = fetch_highlights(PETSHEALTH_TEAM_URL)
                st.session_state.official_bio = "\n\n".join(bio_items)
                st.success("✅ Bio loaded from website")
            except WebScrapingError as e:
                st.error(f"❌ Failed: {e}")
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")

with ab2:
    st.caption("Or paste/edit custom bio below")

custom_bio = st.text_area(
    "Custom 'About Us' text (optional – override default)",
    value="",
    max_chars=30000,
    height=150,
    placeholder="Paste or type a custom bio here..."
)

st.divider()

# --------------------------
# GENERATE & SEND
# --------------------------
st.subheader("🚀 Generate & Send Quote")

col_gen, col_send = st.columns(2, gap="large")

with col_gen:
    if st.button("📄 Generate PDF Quote", type="primary", use_container_width=True):
        # Validation
        errors = []

        if not client_name.strip():
            errors.append("Client name is required")

        try:
            validate_client_data({
                "client_email": client_email,
                "client_phone": client_phone,
                "plan_1_price": plan_1_price,
                "plan_2_price": plan_2_price,
                "pet_count": pet_count,
                "pet_dob": pet_dob,
            })
        except ValidationError as ve:
            errors.append(str(ve))

        if not selected_plans:
            errors.append("Please select at least one plan in the sidebar")

        if errors:
            for err in errors:
                st.error(f"❌ {err}")
        else:
            with st.spinner("Generating PDF..."):
                try:
                    # Determine final bio and highlights
                    final_bio = sanitize_text_area(custom_bio) if custom_bio.strip() else st.session_state.official_bio
                    final_highlights = []

                    if custom_highlights.strip():
                        final_highlights = lines(custom_highlights)
                    else:
                        if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans and st.session_state.official_eurolife:
                            final_highlights.extend(st.session_state.official_eurolife)
                        if "PET CARE PLUS (INTERLIFE)" in selected_plans and st.session_state.official_interlife:
                            final_highlights.extend(st.session_state.official_interlife)

                    # Prepare plan data
                    plans_for_pdf = []
                    for plan_key in selected_plans:
                        if "HOOLIE" in plan_key:
                            # Hoolie plan - get from config
                            pet_type_pdf = "dog" if "Dog" in plan_key else "cat"
                            plans_pdf_config = HOOLIE_DOG_PLANS if pet_type_pdf == "dog" else HOOLIE_CAT_PLANS

                            if "Silver" in plan_key:
                                plan_tier_pdf = "Silver"
                            elif "Gold" in plan_key:
                                plan_tier_pdf = "Gold"
                            else:
                                plan_tier_pdf = "Platinum Dynasty"

                            hoolie_plan_data = plans_pdf_config[plan_tier_pdf]

                            plans_for_pdf.append({
                                "name": plan_key,
                                "provider": "HOOLIE",
                                "price": plan_prices.get(plan_key, 0.0),
                                "limit": hoolie_plan_data['capital'],
                                "area": "Ελλάδα",
                                "key_facts": [f"✅ {k}" for k in list(hoolie_plan_data['coverage'].keys())[:5]],
                                "covers": [f"{k}: {v}" for k, v in list(hoolie_plan_data['coverage'].items())[:8]],
                                "exclusions": ["Προϋπάρχουσες παθήσεις", "Εκτροφή"],
                                "waiting": ["Ασθένεια: 60 ημέρες", "Ατύχημα: 15 ημέρες"]
                            })
                        elif "PET CARE PLUS" in plan_key:
                            plans_for_pdf.append({
                                "name": plan_1_name,
                                "provider": plan_1_provider,
                                "price": plan_1_price,
                                "limit": plan1_limit,
                                "area": plan1_area,
                                "key_facts": lines(plan1_key_facts_txt),
                                "covers": lines(plan1_covers_txt),
                                "exclusions": lines(plan1_exclusions_txt),
                                "waiting": lines(plan1_waiting_txt),
                            })
                        elif "EUROLIFE" in plan_key:
                            plans_for_pdf.append({
                                "name": plan_2_name,
                                "provider": plan_2_provider,
                                "price": plan_2_price,
                                "limit": plan2_limit,
                                "area": plan2_area,
                                "key_facts": lines(plan2_key_facts_txt),
                                "covers": lines(plan2_covers_txt),
                                "exclusions": lines(plan2_exclusions_txt),
                                "waiting": lines(plan2_waiting_txt),
                            })

                    if any("HOOLIE" in pk for pk in selected_plans):
                        st.warning(
                            "⚠️ Note: the current PDF layout only renders dedicated coverage "
                            "cards for PET CARE PLUS (INTERLIFE) and EUROLIFE My Happy Pet. "
                            "Hoolie plan(s) are included in the price total but won't get their "
                            "own coverage page yet."
                        )

                    # site_images may contain URL strings (from petshealth.gr scrape)
                    # or (filename, bytes) tuples (from manual upload). Normalize to bytes.
                    polaroid_bytes = []
                    for item in st.session_state.site_images[:MAX_POLAROID_IMAGES]:
                        if isinstance(item, (tuple, list)) and len(item) == 2:
                            _, img_bytes = item
                            if img_bytes:
                                polaroid_bytes.append(img_bytes)
                        elif isinstance(item, (bytes, bytearray)):
                            polaroid_bytes.append(bytes(item))
                        elif isinstance(item, str):
                            try:
                                img_bytes = download_image_bytes(item)
                                if img_bytes:
                                    polaroid_bytes.append(img_bytes)
                            except Exception:
                                pass

                    # Build the flat data dict expected by build_quote_pdf()
                    pdf_data = {
                        "client_name": sanitize_text_input(client_name),
                        "client_phone": sanitize_text_input(client_phone),
                        "client_email": sanitize_text_input(client_email),
                        "location": sanitize_text_input(location),
                        "quote_date": quote_date.strftime("%d/%m/%Y") if hasattr(quote_date, "strftime") else str(quote_date),
                        "quote_mode": quote_mode,
                        "pet_count": pet_count,
                        "bulk_summary": sanitize_text_area(bulk_summary),
                        "pet_name": sanitize_text_input(pet_name),
                        "pet_species": pet_species,
                        "pet_breed": sanitize_text_input(pet_breed),
                        "pet_dob": sanitize_text_input(pet_dob),
                        "pet_microchip": sanitize_text_input(pet_microchip),
                        "marketing_hook": sanitize_text_input(marketing_hook),
                        "notes": sanitize_text_area(notes),
                        "selected_plans": selected_plans,

                        "plan_1_name": plan_1_name,
                        "plan_1_provider": plan_1_provider,
                        "plan_1_price": f"{plan_1_price:.2f}",
                        "plan_1_price_total": f"€{(plan_1_price * mult):.2f}",
                        "plan1_limit": plan1_limit,
                        "plan1_area": plan1_area,
                        "plan1_key_facts": lines(plan1_key_facts_txt),
                        "plan1_covers": lines(plan1_covers_txt),
                        "plan1_exclusions": lines(plan1_exclusions_txt),
                        "plan1_waiting": lines(plan1_waiting_txt),

                        "plan_2_name": plan_2_name,
                        "plan_2_provider": plan_2_provider,
                        "plan_2_price": f"{plan_2_price:.2f}",
                        "plan_2_price_total": f"€{(plan_2_price * mult):.2f}",
                        "plan2_limit": plan2_limit,
                        "plan2_area": plan2_area,
                        "plan2_key_facts": lines(plan2_key_facts_txt),
                        "plan2_covers": lines(plan2_covers_txt),
                        "plan2_exclusions": lines(plan2_exclusions_txt),
                        "plan2_waiting": lines(plan2_waiting_txt),

                        "total_price": f"€{total:.2f}",
                        "polaroid_images": polaroid_bytes,
                        "official_eurolife": st.session_state.official_eurolife,
                        "official_interlife": st.session_state.official_interlife,
                        "about_bio": final_bio,
                    }

                    if final_highlights:
                        if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
                            pdf_data["official_eurolife"] = final_highlights[:18]
                        if "PET CARE PLUS (INTERLIFE)" in selected_plans:
                            pdf_data["official_interlife"] = final_highlights[:18]

                    # Build quote PDF
                    quote_pdf_bytes = build_quote_pdf(pdf_data)

                    # Merge with IPIDs if requested
                    if include_ipid:
                        try:
                            merged_bytes = merge_quote_with_ipids(quote_pdf_bytes, selected_plans)
                            st.session_state.final_pdf_bytes = merged_bytes
                            logger.info("✅ PDF merged with IPIDs successfully")
                        except PDFError as pe:
                            st.warning(f"⚠️ IPID merge issue: {pe}. Using quote PDF only.")
                            st.session_state.final_pdf_bytes = quote_pdf_bytes
                    else:
                        st.session_state.final_pdf_bytes = quote_pdf_bytes

                    st.session_state.pdf_generated = True
                    st.session_state.final_filename = f"PETSHEALTH_Quote_{client_name.replace(' ', '_')}_{quote_date}.pdf"

                    st.success("✅ PDF generated successfully!")
                    logger.info(f"✅ Quote generated for {client_name}")

                except Exception as e:
                    st.error(f"❌ Failed to generate PDF: {e}")
                    logger.error(f"❌ PDF generation error: {e}")

with col_send:
    if st.session_state.pdf_generated and st.session_state.final_pdf_bytes:
        st.download_button(
            label="⬇️ Download PDF",
            data=st.session_state.final_pdf_bytes,
            file_name=st.session_state.final_filename,
            mime="application/pdf",
            use_container_width=True
        )

        if st.button("📧 Send via Email", use_container_width=True):
            with st.spinner("Sending email..."):
                try:
                    send_petshealth_quote(
                        to_email=client_email,
                        client_name=client_name,
                        pdf_bytes=st.session_state.final_pdf_bytes,
                        pdf_filename=st.session_state.final_filename,
                        plans_list=[p["name"] for p in plans_for_pdf],
                    )
                    st.success(f"✅ Email sent successfully to {client_email}")
                    logger.info(f"✅ Email sent to {client_email}")
                except Exception as e:
                    st.error(f"❌ Failed to send email: {e}")
                    logger.error(f"❌ Email sending error: {e}")
    else:
        st.info("Generate PDF first to enable download/email")

st.divider()
st.caption("🐾 PETSHEALTH Quote Engine v2.0 – Secure • Professional • Complete")
