mport
io
import os
import re
import ssl
import html as ihtml
import smtplib
from datetime import date
from email.message import EmailMessage
from urllib.parse import urljoin

import streamlit as st
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader, PdfWriter

from pdf_builder import build_quote_pdf

# --------------------------
# PAGE CONFIG
# --------------------------
st.set_page_config(
    page_title="PETSHEALTH – Pet Quote Engine",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------
# URLs
# --------------------------
PETSHEALTH_HOME_URL = "https://www.petshealth.gr/"
PETSHEALTH_TEAM_URL = "https://www.petshealth.gr/petshealt-team"
EUROLIFE_URL = "https://www.eurolife.gr/el-GR/proionta/idiotes/katoikidio/my-happy-pet"
INTERLIFE_URL = "https://www.interlife-programs.gr/asfalisi/eidika-programmata/#petcare"

# --------------------------
# IPID paths (must exist)
# --------------------------
IPID_MAP = {
    "PET CARE PLUS (INTERLIFE)": "assets/ipid/PETCARE_PLUS_IPID.pdf",
    "EUROLIFE My Happy Pet (SAFE PET SYSTEM)": "assets/ipid/EUROLIFE_MY_HAPPY_PET_IPID.pdf",
}
PLAN_KEYS = list(IPID_MAP.keys())

# --------------------------
# EMAIL SETTINGS
# --------------------------
ADVISOR_CC = "xiatropoulos@gmail.com"  # Always CC to advisor


def _get_secret(key: str, default: str = "") -> str:
    """Get secret from Streamlit Cloud or environment variable"""
    if hasattr(st, "secrets") and key in st.secrets:
        return str(st.secrets.get(key, default))
    return os.getenv(key, default)


def is_valid_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def send_quote_email(
        to_email: str,
        subject: str,
        body_text: str,
        pdf_bytes: bytes,
        filename: str,
        cc_email: str = ADVISOR_CC,
):
    """Send professional quote email with PDF attachment"""
    smtp_host = _get_secret("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(_get_secret("SMTP_PORT", "587"))
    smtp_user = _get_secret("SMTP_USER", "")
    smtp_pass = _get_secret("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        raise RuntimeError("Missing SMTP credentials. Please configure SMTP_USER and SMTP_PASS in Streamlit Secrets.")

    msg = EmailMessage()
    msg["From"] = f"PETSHEALTH <{smtp_user}>"
    msg["To"] = to_email
    if cc_email:
        msg["Cc"] = cc_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


# --------------------------
# Helpers
# --------------------------
def _clean_txt(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = ihtml.unescape(ihtml.unescape(t))
    return t.strip()


@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_highlights(url: str, max_items: int = 8) -> list[str]:
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (PETSHEALTHQuote/1.0)"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    candidates = []
    for tag in soup.find_all(["h1", "h2", "h3", "li"]):
        txt = _clean_txt(tag.get_text(" ", strip=True))
        if 28 <= len(txt) <= 240:
            candidates.append(txt)

    if len(candidates) < max_items:
        for tag in soup.find_all("p"):
            txt = _clean_txt(tag.get_text(" ", strip=True))
            if 60 <= len(txt) <= 300:
                candidates.append(txt)
            if len(candidates) >= max_items * 3:
                break

    out, seen = [], set()
    for c in candidates:
        k = c.lower()
        if k in seen:
            continue
        seen.add(k)
        if any(b in k for b in ["cookie", "privacy", "javascript", "newsletter", "©", "all rights"]):
            continue
        out.append(c)
        if len(out) >= max_items:
            break
    return out


@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_site_images(url: str, limit: int = 18) -> list[str]:
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    imgs = []
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        full = urljoin(url, src)
        low = full.lower()
        if any(ext in low for ext in [".png", ".jpg", ".jpeg", ".webp"]):
            imgs.append(full)

    out, seen = [], set()
    for u in imgs:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= limit:
            break
    return out


@st.cache_data(show_spinner=False, ttl=60 * 60)
def download_image_bytes(url: str) -> bytes:
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.content


def lines(txt: str) -> list[str]:
    return [x.strip() for x in (txt or "").splitlines() if x.strip()]


def merge_quote_with_ipids(quote_pdf_bytes: bytes, ipid_paths: list[str]) -> bytes:
    writer = PdfWriter()
    quote_reader = PdfReader(io.BytesIO(quote_pdf_bytes))
    for p in quote_reader.pages:
        writer.add_page(p)

    for pth in ipid_paths:
        if not pth or not os.path.exists(pth):
            continue
        rdr = PdfReader(pth)
        for pg in rdr.pages:
            writer.add_page(pg)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def plan_names_for_email(selected_plans: list[str]) -> str:
    if not selected_plans:
        return "—"
    if len(selected_plans) == 1:
        if "INTERLIFE" in selected_plans[0]:
            return "PET CARE PLUS (INTERLIFE)"
        else:
            return "EUROLIFE My Happy Pet"
    return "PET CARE PLUS + EUROLIFE My Happy Pet (Combined Protection)"


def sales_email_body_gr(
        client_name: str,
        pet_mode: str,
        pet_name: str,
        pet_count: int,
        total_price: str,
        selected_plans: list[str],
) -> str:
    """PROFESSIONAL SALES-DRIVEN EMAIL TEMPLATE"""

    client_display = client_name.strip() or "Αγαπητέ/ή"

    # Pet-specific intro
    if "Bulk" in pet_mode:
        pet_intro = f"Χαίρομαι που εμπιστεύεστε την PETSHEALTH για την προστασία των {pet_count} κατοικιδίων σας."
        coverage_line = f"📋 **Συνολικό ετήσιο κόστος:** {total_price}"
    else:
        pet_display = pet_name.strip() or "το αγαπημένο σας κατοικίδιο"
        pet_intro = f"Χαίρομαι που εμπιστεύεστε την PETSHEALTH για την προστασία του {pet_display}."
        coverage_line = f"📋 **Ετήσιο κόστος για τον/την {pet_display}:** {total_price}"

    # Plans display
    plans_display = plan_names_for_email(selected_plans)

    # Value proposition based on plan selection
    if len(selected_plans) == 2:
        value_prop = """
✅ **Συνδυασμένη κάλυψη** – Το καλύτερο και από τους δύο κόσμους:
   • Ελεύθερη επιλογή κτηνιάτρου (INTERLIFE) για απόλυτη ευελιξία
   • Προνομιακό δίκτυο με ειδικές τιμές (EUROLIFE) για οικονομία στις καθημερινές επισκέψεις
   • Καλύπτει ατυχήματα, ασθένειες, check-ups και πολλά άλλα
"""
    elif "INTERLIFE" in selected_plans[0]:
        value_prop = """
✅ **Ελεύθερη επιλογή κτηνιάτρου** – Πλήρης ευελιξία:
   • Επιλέγετε ελεύθερα κτηνίατρο και κλινική σε όλη την Ελλάδα
   • Κάλυψη νοσοκομειακών δαπανών, ιατρικών επισκέψεων & διαγνωστικών
   • Αστική ευθύνη & νομική προστασία κηδεμόνα συμπεριλαμβάνονται
"""
    else:
        value_prop = """
✅ **Συμβεβλημένο δίκτυο με ειδικές τιμές** – Μέγιστη οικονομία:
   • Προνομιακό δίκτυο κτηνιάτρων με απευθείας χρέωση
   • Δωρεάν ετήσιο check-up (Kala-azar & Ερλίχια)
   • Καλύπτει ακόμα και προϋπάρχουσες και συγγενείς παθήσεις
"""

    email_body = f"""Καλησπέρα {client_display},

{pet_intro}

Επισυνάπτω την προσωπική σας προσφορά με όλες τις λεπτομέρειες κάλυψης.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **Η ΠΡΟΤΑΣΗ ΣΑΣ**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 **Επιλεγμένα προγράμματα:** {plans_display}
{coverage_line}
{value_prop}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📎 **ΣΤΟ ΕΠΙΣΥΝΑΠΤΟΜΕΝΟ PDF:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Αναλυτική κάλυψη κάθε προγράμματος
• Τι καλύπτεται & τι όχι (με πλήρη διαφάνεια)
• Περίοδοι αναμονής & όροι ασφάλισης
• Επίσημα έγγραφα IPID (Information Document)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 **ΕΠΟΜΕΝΑ ΒΗΜΑΤΑ ΓΙΑ ΕΝΕΡΓΟΠΟΙΗΣΗ:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ **Επιβεβαιώστε τα στοιχεία microchip**
   → Στείλτε μας τον/τους αριθμό/ούς microchip (απαραίτητο για όλα τα προγράμματα)

2️⃣ **Επιλέξτε το πρόγραμμα που σας ταιριάζει**
   → Μεμονωμένο ή συνδυασμένο; Μπορώ να σας συμβουλεύσω ανάλογα με τις ανάγκες σας

3️⃣ **Ολοκληρώστε την αίτηση online ή με τη βοήθειά μας**
   → Η κάλυψη ενεργοποιείται άμεσα μετά την έγκριση

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 **ΓΙΑΤΙ ΝΑ ΕΝΕΡΓΟΠΟΙΗΣΕΤΕ ΤΩΡΑ:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ Οι προϋπάρχουσες παθήσεις δεν καλύπτονται – όσο νωρίτερα ξεκινήσετε, τόσο καλύτερα
💰 Μια επέμβαση στο ισχίο μπορεί να κοστίσει €2.000+ – η ασφάλιση κοστίζει κλάσματα αυτού
🛡️ Ηρεμία & οικονομική ασφάλεια για απρόβλεπτα περιστατικά

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Είμαι στη διάθεσή σας για οποιαδήποτε ερώτηση ή διευκρίνιση.
Απλά απαντήστε σε αυτό το email ή καλέστε με στο τηλέφωνο παρακάτω.

**Με εκτίμηση,**

**Chris Iatropoulos**  
*Pet Insurance Advisor | CII Certified (PL4, W01)*

📧 info@petshealth.gr  
📱 +30 211 700 533  
🌐 www.petshealth.gr

*"Because we care for your pets as much as you do"* 🐾

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

P.S. Έχετε ερωτήσεις; Μη διστάσετε να με ρωτήσετε οτιδήποτε. Ο στόχος μου είναι να βρούμε την ιδανική λύση για εσάς και το κατοικίδιό σας – όχι απλά να πουλήσω μια ασφάλεια. 💚
"""

    return email_body.strip()


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
        <strong>🎯 Sales-Driven Quote Engine</strong> – Designed to convert prospects into clients
      </div>
    </div>
    """,
    unsafe_allow_html=True
)
st.write("")

# --------------------------
# Sidebar
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
    st.caption("📧 **Email Settings**")
    st.info(f"✅ All quotes are automatically CC'd to:\n**{ADVISOR_CC}**", icon="ℹ️")

# --------------------------
# Client / Pets
# --------------------------
st.subheader("👤 Client & Pet Information")

c1, c2 = st.columns([1, 1], gap="large")
with c1:
    st.markdown("#### Client Details")
    client_name = st.text_input("Client Name", value="", placeholder="e.g. Γιώργος Παπαδόπουλος")
    client_phone = st.text_input("Phone", value="", placeholder="e.g. +30 210 123 4567")
    client_email = st.text_input("Email", value="", placeholder="e.g. client@example.com")
    location = st.text_input("Location (optional)", value="", placeholder="e.g. Αθήνα, Κέντρο")

with c2:
    st.markdown("#### Quote Mode")
    quote_mode = st.radio("Mode", ["Detailed (single pet)", "Bulk (number of pets)"], horizontal=True)
    pet_count = 1
    bulk_summary = ""
    if quote_mode == "Bulk (number of pets)":
        pet_count = int(st.number_input("Number of pets", min_value=1, value=2, step=1))
        bulk_summary = st.text_area(
            "Bulk description (optional)",
            value="• Έχω 6 σκυλιά\n• Όλα είναι ημίαιμα\n• Βάρος: 20–40 κιλά\n• Ηλικίες: 2 έως 5 ετών\n• Τοποθεσία: Αθήνα\n• Όλα έχουν microchip",
            height=120
        )

st.write("")
st.markdown("#### 🐕 Pet Details (for Detailed mode)")
p1, p2, p3 = st.columns(3, gap="large")
with p1:
    pet_name = st.text_input("Pet Name", value="", placeholder="e.g. Max")
    pet_species = st.selectbox("Species", ["Dog", "Cat"], index=0)
with p2:
    pet_breed = st.text_input("Breed", value="", placeholder="e.g. Λαμπραντόρ")
    pet_dob = st.text_input("Date of Birth (dd/mm/yyyy)", value="", placeholder="e.g. 15/03/2020")
with p3:
    pet_microchip = st.text_input("Microchip ID", value="", placeholder="e.g. 977200...")

st.divider()

# --------------------------
# Plans & Pricing
# --------------------------
st.subheader("💶 Plans & Pricing")

pc1, pc2 = st.columns(2, gap="large")
with pc1:
    st.markdown("### 🏥 Plan 1 (Insurance)")
    plan_1_name = st.text_input("Plan 1 Name", value="PET CARE PLUS")
    plan_1_provider = st.text_input("Plan 1 Provider", value="INTERLIFE")
    plan_1_price = st.number_input("Plan 1 Annual Premium (€)", min_value=0.0, value=189.0, step=1.0)
with pc2:
    st.markdown("### 🏨 Plan 2 (Network)")
    plan_2_name = st.text_input("Plan 2 Name", value="EUROLIFE My Happy Pet (SAFE PET SYSTEM)")
    plan_2_provider = st.text_input("Plan 2 Provider", value="EUROLIFE")
    plan_2_price = st.number_input("Plan 2 Annual Premium (€)", min_value=0.0, value=85.0, step=1.0)

quote_date = st.date_input("Quote Date", value=date.today())

mult = int(pet_count) if "Bulk" in quote_mode else 1
total = 0.0
if "PET CARE PLUS (INTERLIFE)" in selected_plans:
    total += float(plan_1_price) * mult
if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
    total += float(plan_2_price) * mult

st.metric("💰 Total Annual Premium", f"{total:.2f} €", help="Total cost for all selected plans")

marketing_hook = st.text_input(
    "Marketing headline (Page 1)",
    value="Προστασία υγείας για τα κατοικίδια – χωρίς άγχος κόστους."
)

notes = st.text_area(
    "Notes / Disclaimer (Page 1)",
    value=(
        "Το παρόν αποτελεί μη δεσμευτική προσφορά. Οι τελικοί όροι, προϋποθέσεις, εξαιρέσεις και καλύψεις ισχύουν "
        "όπως αναγράφονται στα επίσημα έγγραφα των ασφαλιστικών εταιρειών (Policy Wording / IPID). "
        "Υπάρχει η δυνατότητα τα προγράμματα να δοθούν μεμονωμένα."
    ),
    height=90
)

st.divider()

# --------------------------
# Coverage (Page 2)
# --------------------------
st.subheader("📋 Coverage Details (Page 2)")

with st.expander("🏥 PET CARE PLUS (INTERLIFE) – Coverage fields",
                 expanded=("PET CARE PLUS (INTERLIFE)" in selected_plans)):
    plan1_limit = st.text_input("Limit", value="2.000€ / ανά έτος")
    plan1_area = st.text_input("Geographic Area", value="Ελλάδα")

    plan1_key_facts_txt = st.text_area(
        "Key Facts (one per line)",
        value="\n".join([
            "Ελεύθερη επιλογή κτηνιάτρου και κλινικής",
            "Απαλλαγή: 50€ ανά περιστατικό (όπου εφαρμόζεται)",
        ]),
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
        height=120
    )

    plan1_waiting_txt = st.text_area(
        "Waiting Periods (one per line)",
        value="\n".join([
            "Ασθένεια: 60 ημέρες από την έναρξη",
            "Απώλεια ζωής: 180 ημέρες από την έναρξη",
            "Ατύχημα: από την έναρξη του συμβολαίου",
        ]),
        height=100
    )

with st.expander("🏨 EUROLIFE My Happy Pet – Coverage fields",
                 expanded=("EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans)):
    plan2_limit = st.text_input("Limit (Plan 2)", value="Απεριόριστο (εντός δικτύου, με συμμετοχή)")
    plan2_area = st.text_input("Geographic Area (Plan 2)", value="Αττική – Θεσσαλονίκη (συμβεβλημένο δίκτυο)")

    plan2_key_facts_txt = st.text_area(
        "Key Facts (one per line)",
        value="\n".join([
            "Αποκλειστικά συμβεβλημένο δίκτυο κτηνιάτρων & κλινικών",
            "Απαλλαγή: 0€ (λειτουργεί με συμμετοχή ανά υπηρεσία)",
            "Ειδικός εκπτωτικός τιμοκατάλογος για μέλη του δικτύου",
        ]),
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
        height=160
    )

    plan2_exclusions_txt = st.text_area(
        "Not Covered / Limits (one per line)",
        value="\n".join([
            "Εκτός δικτύου: δεν ισχύει κάλυψη/τιμοκατάλογος",
            "Απαιτείται microchip",
            "Φάρμακα: σύμφωνα με όρους/τιμοκατάλογο προγράμματος",
        ]),
        height=120
    )

    plan2_waiting_txt = st.text_area(
        "Waiting Periods (one per line)",
        value="\n".join([
            "Ατύχημα ή ασθένεια: από την έναρξη του συμβολαίου (σύμφωνα με όρους προγράμματος)",
        ]),
        height=90
    )

st.divider()

# --------------------------
# Polaroids
# --------------------------
st.subheader("📸 Happy Photos (Polaroids – 2 per page)")

if "site_images" not in st.session_state:
    st.session_state["site_images"] = []

a, b = st.columns([1, 1], gap="large")
with a:
    if st.button("🌐 Load images from petshealth.gr", use_container_width=True):
        try:
            st.session_state["site_images"] = fetch_site_images(PETSHEALTH_HOME_URL, limit=18)
            st.success(f"✅ Loaded {len(st.session_state['site_images'])} images from site.")
        except Exception as e:
            st.error(f"❌ Failed to load images: {e}")

with b:
    st.caption("Pick 2–6 images (we rotate them across pages). Upload works as fallback.")

site_images = st.session_state.get("site_images", [])
selected_image_urls = []
if site_images:
    selected_image_urls = st.multiselect(
        "Select site images (2–6)",
        site_images,
        default=site_images[:2] if len(site_images) >= 2 else site_images
    )

uploaded = st.file_uploader(
    "Or upload your own images (JPG/PNG/WebP)",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True
)

st.divider()

# --------------------------
# About & Highlights
# --------------------------
st.subheader("ℹ️ About & Official Highlights (Page 3)")

if "official_bio" not in st.session_state:
    st.session_state.official_bio = ""
if "official_eurolife" not in st.session_state:
    st.session_state.official_eurolife = ""
if "official_interlife" not in st.session_state:
    st.session_state.official_interlife = ""

x1, x2 = st.columns([1, 1], gap="large")
with x1:
    if st.button("🌐 Load official highlights from web", use_container_width=True):
        with st.spinner("Fetching content from PETSHEALTH, EUROLIFE, INTERLIFE..."):
            try:
                bio_items = fetch_highlights(PETSHEALTH_TEAM_URL, max_items=6)
                eu_items = fetch_highlights(EUROLIFE_URL, max_items=8)
                it_items = fetch_highlights(INTERLIFE_URL, max_items=8)

                st.session_state.official_bio = "\n".join(bio_items)
                st.session_state.official_eurolife = "\n".join([f"• {x}" for x in eu_items])
                st.session_state.official_interlife = "\n".join([f"• {x}" for x in it_items])
                st.success("✅ Loaded. Edit before generating PDF.")
            except Exception as e:
                st.error(f"❌ Failed to load highlights: {e}")

with x2:
    st.caption("Keep it short & trust-based (marketing).")

about_bio = st.text_area("Advisor Bio (editable – recommended 5–7 lines)", value=st.session_state.official_bio,
                         height=150)

cii_titles = st.text_area(
    "CII Titles / Credentials (one per line)",
    value="\n".join([
        "CII – (PL4) Introduction to Pet Insurance (Unit achieved: June 2023)",
        "CII – (W01) Award in General Insurance (English) (Unit achieved: March 2025)",
    ]),
    height=90
)

official_eurolife = st.text_area("EUROLIFE highlights (bullets)", value=st.session_state.official_eurolife, height=140)
official_interlife = st.text_area("INTERLIFE highlights (bullets)", value=st.session_state.official_interlife,
                                  height=140)

st.divider()

# --------------------------
# Generate PDF
# --------------------------
st.subheader("🎨 Generate PDF Quote")
generate = st.button("✨ Generate Professional PDF Quote", type="primary", use_container_width=True)

final_pdf_bytes = None
filename = None
missing_ipids = []

if generate:
    polaroid_bytes = []

    # Download selected site images
    for u in (selected_image_urls or [])[:6]:
        try:
            polaroid_bytes.append(download_image_bytes(u))
        except Exception:
            pass

    # Add uploaded images
    if uploaded:
        for f in uploaded[:6]:
            try:
                polaroid_bytes.append(f.read())
            except Exception:
                pass

    polaroid_bytes = polaroid_bytes[:10]

    payload = {
        "marketing_hook": marketing_hook,

        "client_name": client_name,
        "client_phone": client_phone,
        "client_email": client_email,
        "location": location,

        "quote_mode": quote_mode,
        "pet_count": int(pet_count),
        "bulk_summary": bulk_summary,

        "pet_name": pet_name,
        "pet_species": pet_species,
        "pet_breed": pet_breed,
        "pet_dob": pet_dob,
        "pet_microchip": pet_microchip,

        "plan_1_name": plan_1_name,
        "plan_1_provider": plan_1_provider,
        "plan_1_price": f"{float(plan_1_price):.2f}",
        "plan_2_name": plan_2_name,
        "plan_2_provider": plan_2_provider,
        "plan_2_price": f"{float(plan_2_price):.2f}",

        "selected_plans": selected_plans,
        "price_multiplier": int(mult),
        "plan_1_price_total": f"{float(plan_1_price) * mult:.2f}",
        "plan_2_price_total": f"{float(plan_2_price) * mult:.2f}",
        "total_price": f"{total:.2f} €",
        "quote_date": quote_date.strftime("%d/%m/%Y"),
        "notes": notes,

        "plan1_limit": locals().get("plan1_limit", ""),
        "plan1_area": locals().get("plan1_area", ""),
        "plan1_key_facts": lines(locals().get("plan1_key_facts_txt", "")),
        "plan1_covers": lines(locals().get("plan1_covers_txt", "")),
        "plan1_exclusions": lines(locals().get("plan1_exclusions_txt", "")),
        "plan1_waiting": lines(locals().get("plan1_waiting_txt", "")),

        "plan2_limit": locals().get("plan2_limit", ""),
        "plan2_area": locals().get("plan2_area", ""),
        "plan2_key_facts": lines(locals().get("plan2_key_facts_txt", "")),
        "plan2_covers": lines(locals().get("plan2_covers_txt", "")),
        "plan2_exclusions": lines(locals().get("plan2_exclusions_txt", "")),
        "plan2_waiting": lines(locals().get("plan2_waiting_txt", "")),

        "about_bio": about_bio,
        "cii_titles": lines(cii_titles),
        "official_eurolife": [x.lstrip("•").strip() for x in lines(official_eurolife)],
        "official_interlife": [x.lstrip("•").strip() for x in lines(official_interlife)],

        "polaroid_images": polaroid_bytes,
    }

    with st.spinner("🎨 Building professional PDF quote..."):
        quote_pdf_bytes = build_quote_pdf(payload)

    ipid_paths = []
    if include_ipid:
        for p in selected_plans:
            ipid_paths.append(IPID_MAP.get(p))

    missing_ipids = [p for p in ipid_paths if p and not os.path.exists(p)]
    final_pdf_bytes = merge_quote_with_ipids(quote_pdf_bytes, ipid_paths)

    safe_client = (client_name or "Client").replace(" ", "_")
    safe_pet = (pet_name or ("Bulk" if "Bulk" in quote_mode else "Pet")).replace(" ", "_")
    filename = f"PETSHEALTH_Quote_{safe_client}_{safe_pet}_{quote_date.strftime('%Y%m%d')}.pdf"

    if missing_ipids:
        st.warning("⚠️ Missing IPID files in assets/ipid:\n- " + "\n- ".join(missing_ipids))

    st.success("✅ PDF ready! Download or send via email below.")
    st.download_button(
        "📥 Download Final PDF (Quote + IPID)",
        data=final_pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        use_container_width=True
    )

st.divider()

# --------------------------
# Send Email
# --------------------------
st.subheader("📧 Send Quote via Email (Professional Sales Email)")

st.markdown("""
<div style="padding:14px;background:#EFF6FF;border-left:4px solid #1E4FA8;border-radius:8px;margin-bottom:16px;">
<strong>📬 Email Strategy:</strong><br>
• Sent to client email (from client data above)<br>
• Automatically CC'd to <strong>xiatropoulos@gmail.com</strong><br>
• Professional sales-driven template designed to convert<br>
• Includes clear next steps and value propositions
</div>
""", unsafe_allow_html=True)

recipient = st.text_input("📧 Recipient email", value=(client_email or "").strip(), placeholder="client@example.com")

default_subject = f"🐾 PETSHEALTH – Η Προσωπική σας Προσφορά Ασφάλισης ({client_name or 'Client'})"
subject = st.text_input("📋 Subject", value=default_subject)

default_body = sales_email_body_gr(
    client_name=client_name,
    pet_mode=quote_mode,
    pet_name=pet_name,
    pet_count=int(pet_count),
    total_price=f"{total:.2f} €",
    selected_plans=selected_plans,
)
body = st.text_area("📝 Email body (SALES-DRIVEN – editable)", value=default_body, height=350)

send_btn = st.button("🚀 Send Professional Quote Email", type="primary", use_container_width=True,
                     disabled=(final_pdf_bytes is None))

if send_btn:
    if not recipient or not is_valid_email(recipient):
        st.error("❌ Please enter a valid recipient email address.")
    elif final_pdf_bytes is None or filename is None:
        st.error("❌ Generate the PDF first before sending.")
    else:
        try:
            with st.spinner("📤 Sending professional quote email..."):
                send_quote_email(
                    to_email=recipient,
                    subject=subject.strip(),
                    body_text=body.strip(),
                    pdf_bytes=final_pdf_bytes,
                    filename=filename,
                    cc_email=ADVISOR_CC,
                )
            st.success(f"✅ Email sent successfully!\n\n📧 **To:** {recipient}\n📋 **CC:** {ADVISOR_CC}")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Email send failed: {e}\n\nPlease check your SMTP settings in Streamlit Secrets.")
