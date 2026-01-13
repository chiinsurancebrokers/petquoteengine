import io
import os
import re
import html as ihtml
from datetime import date

import streamlit as st
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader, PdfWriter

from pdf_builder import build_quote_pdf

st.set_page_config(page_title="PETSHEALTH – Pet Quote Engine", page_icon="🐾", layout="wide")

# --------------------------
# CONFIG
# --------------------------
PETSHEALTH_TEAM_URL = "https://www.petshealth.gr/petshealt-team"
EUROLIFE_URL = "https://www.eurolife.gr/el-GR/proionta/idiotes/katoikidio/my-happy-pet"
INTERLIFE_URL = "https://www.interlife-programs.gr/asfalisi/eidika-programmata/#petcare"

# Put these PDFs in your repo
IPID_MAP = {
    "PET CARE PLUS (INTERLIFE)": "assets/ipid/PETCARE_PLUS_IPID.pdf",
    "EUROLIFE My Happy Pet (SAFE PET SYSTEM)": "assets/ipid/EUROLIFE_MY_HAPPY_PET_IPID.pdf",
}

PLAN_KEYS = list(IPID_MAP.keys())

# --------------------------
# HELPERS
# --------------------------
def _clean_txt(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"\s+", " ", t)
    t = ihtml.unescape(ihtml.unescape(t))  # double unescape for stubborn entities
    return t.strip()

@st.cache_data(show_spinner=False, ttl=60*60)
def fetch_highlights(url: str, max_items: int = 10) -> list[str]:
    """Extract headings/list items/meaningful paragraphs from a page (lightweight)."""
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (PETSHEALTHQuote/1.0)"})
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    candidates = []

    # Prefer structured content first
    for tag in soup.find_all(["h1", "h2", "h3", "li"]):
        txt = _clean_txt(tag.get_text(" ", strip=True))
        if 35 <= len(txt) <= 220:
            candidates.append(txt)

    # Then a few paragraphs if needed
    if len(candidates) < max_items:
        for tag in soup.find_all("p"):
            txt = _clean_txt(tag.get_text(" ", strip=True))
            if 60 <= len(txt) <= 280:
                candidates.append(txt)
            if len(candidates) >= max_items * 3:
                break

    # de-dup
    out, seen = [], set()
    for c in candidates:
        k = c.lower()
        if k in seen:
            continue
        seen.add(k)
        # filter boilerplate
        if any(b in k for b in ["cookie", "privacy", "javascript", "©", "all rights", "newsletter"]):
            continue
        out.append(c)
        if len(out) >= max_items:
            break

    return out

def lines(txt: str) -> list[str]:
    return [x.strip() for x in (txt or "").splitlines() if x.strip()]

def merge_quote_with_ipids(quote_pdf_bytes: bytes, ipid_paths: list[str]) -> bytes:
    writer = PdfWriter()

    # Quote
    quote_reader = PdfReader(io.BytesIO(quote_pdf_bytes))
    for p in quote_reader.pages:
        writer.add_page(p)

    # IPIDs (each file is already its own pages)
    for pth in ipid_paths:
        if not pth or not os.path.exists(pth):
            continue
        rdr = PdfReader(pth)
        for pg in rdr.pages:
            writer.add_page(pg)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

# --------------------------
# UI HEADER
# --------------------------
st.markdown(
    """
    <div style="padding:14px 18px;border-radius:14px;background:#111827;color:white;">
      <div style="font-size:22px;font-weight:800;">PETSHEALTH – PDF Quote Auto-Generator</div>
      <div style="opacity:0.85;">Client & Pet summary • Coverage cards • IPID pages • Greek Unicode ready</div>
    </div>
    """,
    unsafe_allow_html=True
)
st.write("")

# --------------------------
# SIDEBAR: PLAN SELECTION + IPID
# --------------------------
with st.sidebar:
    st.subheader("Quote Settings")
    selected_plans = st.multiselect(
        "Select plan(s) to include",
        PLAN_KEYS,
        default=PLAN_KEYS
    )

    include_ipid = st.toggle("Append IPID pages (recommended)", value=True)

    st.caption("IPID pages are appended at the end of the final PDF, based on selected plans.")

# --------------------------
# CLIENT / PET
# --------------------------
colA, colB = st.columns(2, gap="large")

with colA:
    st.subheader("Client Details")
    client_name = st.text_input("Client Name", value="")
    client_phone = st.text_input("Phone", value="")
    client_email = st.text_input("Email", value="")

with colB:
    st.subheader("Pet Details")
    pet_name = st.text_input("Pet Name", value="")
    pet_species = st.selectbox("Species", ["Dog", "Cat"], index=0)
    pet_breed = st.text_input("Breed", value="")
    pet_dob = st.text_input("Date of Birth (dd/mm/yyyy)", value="")
    pet_microchip = st.text_input("Microchip ID", value="")

st.divider()

# --------------------------
# PRICING (only for selected plans)
# --------------------------
st.subheader("Plans & Pricing")

pcols = st.columns(2, gap="large")

# defaults
plan_1_name = "PET CARE PLUS"
plan_1_provider = "INTERLIFE"
plan_1_price = 189.0

plan_2_name = "EUROLIFE My Happy Pet (SAFE PET SYSTEM)"
plan_2_provider = "EUROLIFE"
plan_2_price = 85.0

with pcols[0]:
    st.markdown("### Plan 1 (Insurance)")
    plan_1_name = st.text_input("Plan 1 Name", value=plan_1_name)
    plan_1_provider = st.text_input("Plan 1 Provider", value=plan_1_provider)
    plan_1_price = st.number_input("Plan 1 Annual Premium (€)", min_value=0.0, value=float(plan_1_price), step=1.0)

with pcols[1]:
    st.markdown("### Plan 2 (Network)")
    plan_2_name = st.text_input("Plan 2 Name", value=plan_2_name)
    plan_2_provider = st.text_input("Plan 2 Provider", value=plan_2_provider)
    plan_2_price = st.number_input("Plan 2 Annual Premium (€)", min_value=0.0, value=float(plan_2_price), step=1.0)

quote_date = st.date_input("Quote Date", value=date.today())

# compute total based on selection
total = 0.0
if "PET CARE PLUS (INTERLIFE)" in selected_plans:
    total += float(plan_1_price)
if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
    total += float(plan_2_price)

st.metric("Total Annual Premium", f"{total:.2f} €")

notes = st.text_area(
    "Notes / Disclaimer (Page 1)",
    value="Το παρόν αποτελεί μη δεσμευτική προσφορά. Οι τελικοί όροι, προϋποθέσεις, εξαιρέσεις και καλύψεις ισχύουν όπως αναγράφονται στα επίσημα έγγραφα των ασφαλιστικών εταιρειών (Policy Wording / IPID).",
    height=90
)

st.divider()

# --------------------------
# COVERAGE DETAILS (Page 2)
# --------------------------
st.subheader("Coverage Details (Page 2)")

with st.expander("PET CARE PLUS (INTERLIFE) – Coverage fields", expanded=("PET CARE PLUS (INTERLIFE)" in selected_plans)):
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

with st.expander("EUROLIFE My Happy Pet – Coverage fields", expanded=("EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans)):
    plan2_limit = st.text_input("Limit (Plan 2)", value="Απεριόριστο (εντός δικτύου, με συμμετοχή)")
    plan2_area = st.text_input("Geographic Area (Plan 2)", value="Αττική – Θεσσαλονίκη (συμβεβλημένο δίκτυο)")

    plan2_key_facts_txt = st.text_area(
        "Key Facts (one per line)",
        value="\n".join([
            "Αποκλειστικά συμβεβλημένο δίκτυο κτηνιάτρων & κλινικών",
            "Απαλλαγή: 0€ (λειτουργεί με συμμετοχή ανά υπηρεσία)",
            "Νοσοκομειακές δαπάνες & εξετάσεις με ειδικό εκπτωτικό τιμοκατάλογο για μέλη",
        ]),
        height=100
    )

    plan2_covers_txt = st.text_area(
        "Covers (one per line)",
        value="\n".join([
            "Νοσοκομειακές δαπάνες, ιατρικές επισκέψεις & διαγνωστικές εντός δικτύου με συμμετοχή",
            "Ετήσιο Check Up δωρεάν (περιλαμβάνει Kala-azar & Ερλίχια)",
            "Εμβολιασμοί σε ειδικό προσυμφωνημένο τιμοκατάλογο (εντός δικτύου)",
            "Οδοντιατρικές πράξεις σε ειδικό προσυμφωνημένο τιμοκατάλογο (εντός δικτύου)",
            "Προϋπάρχουσες παθήσεις: καλύπτονται",
            "Συγγενείς παθήσεις: καλύπτονται",
        ]),
        height=170
    )

    plan2_exclusions_txt = st.text_area(
        "Not Covered / Limits (one per line)",
        value="\n".join([
            "Εκτός δικτύου: δεν ισχύει κάλυψη/τιμοκατάλογος",
            "Απαιτείται ηλεκτρονική σήμανση (microchip)",
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
# PAGE 3: BIO + CREDENTIALS + OFFICIAL HIGHLIGHTS
# --------------------------
st.subheader("About & Official Highlights (Page 3)")

if "official_bio" not in st.session_state:
    st.session_state.official_bio = ""
if "official_eurolife" not in st.session_state:
    st.session_state.official_eurolife = ""
if "official_interlife" not in st.session_state:
    st.session_state.official_interlife = ""

bcol1, bcol2 = st.columns([1, 1], gap="large")

with bcol1:
    if st.button("Load official highlights", use_container_width=True):
        with st.spinner("Fetching content…"):
            try:
                bio_items = fetch_highlights(PETSHEALTH_TEAM_URL, max_items=8)
                eu_items = fetch_highlights(EUROLIFE_URL, max_items=8)
                it_items = fetch_highlights(INTERLIFE_URL, max_items=8)

                st.session_state.official_bio = "\n".join(bio_items)
                st.session_state.official_eurolife = "\n".join([f"• {x}" for x in eu_items])
                st.session_state.official_interlife = "\n".join([f"• {x}" for x in it_items])

                st.success("Loaded. You can edit before generating PDF.")
            except Exception as e:
                st.error(f"Failed to load highlights: {e}")

with bcol2:
    st.caption("Tip: Keep the Bio short (3–6 lines). Highlights work best as bullets.")

about_bio = st.text_area("Advisor Bio (editable)", value=st.session_state.official_bio, height=140)

cii_titles = st.text_area(
    "CII Titles / Credentials (one per line)",
    value="\n".join([
        "Chartered Insurance Institute – (PL4) Introduction to Pet Insurance (Unit achieved: June 2023)",
        "Chartered Insurance Institute – (W01) Award in General Insurance (English) (Unit achieved: March 2025)",
    ]),
    height=90
)

official_eurolife = st.text_area(
    "EUROLIFE official highlights (bullets, editable)",
    value=st.session_state.official_eurolife,
    height=140
)

official_interlife = st.text_area(
    "INTERLIFE official highlights (bullets, editable)",
    value=st.session_state.official_interlife,
    height=140
)

st.divider()

# --------------------------
# GENERATE
# --------------------------
generate = st.button("Generate PDF", type="primary", use_container_width=True)

if generate:
    # Build payload
    payload = {
        "client_name": client_name,
        "client_phone": client_phone,
        "client_email": client_email,
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
        "total_price": f"{total:.2f} €",
        "quote_date": quote_date.strftime("%d/%m/%Y"),
        "notes": notes,

        # plan1 fields
        "plan1_limit": locals().get("plan1_limit", ""),
        "plan1_area": locals().get("plan1_area", ""),
        "plan1_key_facts": lines(locals().get("plan1_key_facts_txt", "")),
        "plan1_covers": lines(locals().get("plan1_covers_txt", "")),
        "plan1_exclusions": lines(locals().get("plan1_exclusions_txt", "")),
        "plan1_waiting": lines(locals().get("plan1_waiting_txt", "")),

        # plan2 fields
        "plan2_limit": locals().get("plan2_limit", ""),
        "plan2_area": locals().get("plan2_area", ""),
        "plan2_key_facts": lines(locals().get("plan2_key_facts_txt", "")),
        "plan2_covers": lines(locals().get("plan2_covers_txt", "")),
        "plan2_exclusions": lines(locals().get("plan2_exclusions_txt", "")),
        "plan2_waiting": lines(locals().get("plan2_waiting_txt", "")),

        # page3
        "about_bio": about_bio,
        "cii_titles": lines(cii_titles),

        "official_eurolife": [x.lstrip("•").strip() for x in lines(official_eurolife)],
        "official_interlife": [x.lstrip("•").strip() for x in lines(official_interlife)],
    }

    # Build quote PDF
    quote_pdf_bytes = build_quote_pdf(payload)

    # IPIDs chosen by selected plans
    ipid_paths = []
    if include_ipid:
        for p in selected_plans:
            ipid_paths.append(IPID_MAP.get(p))

    final_pdf_bytes = merge_quote_with_ipids(quote_pdf_bytes, ipid_paths)

    # Warn if IPIDs missing
    missing = [p for p in ipid_paths if p and not os.path.exists(p)]
    if include_ipid and missing:
        st.warning("Some IPID files are missing in assets/ipid. Add them and redeploy:\n- " + "\n- ".join(missing))

    fname = f"PETSHEALTH_Quote_{client_name or 'Client'}_{pet_name or 'Pet'}.pdf".replace(" ", "_")

    st.success("PDF ready!")
    st.download_button(
        "Download Final PDF (Quote + IPID)",
        data=final_pdf_bytes,
        file_name=fname,
        mime="application/pdf",
        use_container_width=True
    )