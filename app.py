import io
import os
import re
import html as ihtml
from datetime import date
from urllib.parse import urljoin

import streamlit as st
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader, PdfWriter

from pdf_builder import build_quote_pdf

# --------------------------
# PAGE CONFIG
# --------------------------
st.set_page_config(page_title="PETSHEALTH – Pet Quote Engine", page_icon="🐾", layout="wide")

# --------------------------
# URLs
# --------------------------
PETSHEALTH_HOME_URL = "https://www.petshealth.gr/"
PETSHEALTH_TEAM_URL = "https://www.petshealth.gr/petshealt-team"
EUROLIFE_URL = "https://www.eurolife.gr/el-GR/proionta/idiotes/katoikidio/my-happy-pet"
INTERLIFE_URL = "https://www.interlife-programs.gr/asfalisi/eidika-programmata/#petcare"

# --------------------------
# IPID paths (must exist in repo)
# --------------------------
IPID_MAP = {
    "PET CARE PLUS (INTERLIFE)": "assets/ipid/PETCARE_PLUS_IPID.pdf",
    "EUROLIFE My Happy Pet (SAFE PET SYSTEM)": "assets/ipid/EUROLIFE_MY_HAPPY_PET_IPID.pdf",
}
PLAN_KEYS = list(IPID_MAP.keys())

# --------------------------
# Helpers
# --------------------------
def _clean_txt(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = ihtml.unescape(ihtml.unescape(t))  # decode &alpha; etc if present
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
        # keep only likely renderable formats
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
        if not pth:
            continue
        if not os.path.exists(pth):
            continue
        rdr = PdfReader(pth)
        for pg in rdr.pages:
            writer.add_page(pg)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

# --------------------------
# Header
# --------------------------
st.markdown(
    """
    <div style="padding:14px 18px;border-radius:14px;background:#111827;color:white;">
      <div style="font-size:22px;font-weight:800;">PETSHEALTH – PDF Quote Auto-Generator</div>
      <div style="opacity:0.85;">Client & Pet summary • Coverage cards • Bulk quotes • Polaroids • IPID pages</div>
    </div>
    """,
    unsafe_allow_html=True
)
st.write("")

# --------------------------
# Sidebar Settings
# --------------------------
with st.sidebar:
    st.subheader("Quote Settings")

    selected_plans = st.multiselect(
        "Select plan(s) to include",
        PLAN_KEYS,
        default=PLAN_KEYS
    )

    include_ipid = st.toggle("Append IPID pages (recommended)", value=True)
    st.caption("IPID pages are appended at the end based on selected plans.")

# --------------------------
# Client / Pets
# --------------------------
st.subheader("Client & Pets")

c1, c2 = st.columns([1, 1], gap="large")
with c1:
    st.markdown("#### Client Details")
    client_name = st.text_input("Client Name", value="")
    client_phone = st.text_input("Phone", value="")
    client_email = st.text_input("Email", value="")

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
        pet_count = int(st.number_input("Number of pets", min_value=1, value=2, step=1))
        bulk_summary = st.text_area(
            "Bulk description (optional)",
            value="• Έχω 6 σκυλιά\n• Όλα είναι ημίαιμα\n• Βάρος: 20–40 κιλά\n• Ηλικίες: 2 έως 5 ετών\n• Τοποθεσία: Αθήνα\n• Όλα έχουν microchip",
            height=120
        )
    else:
        pet_count = 1

st.write("")
st.markdown("#### Pet Details (for Detailed mode)")
p1, p2, p3 = st.columns(3, gap="large")
with p1:
    pet_name = st.text_input("Pet Name", value="")
    pet_species = st.selectbox("Species", ["Dog", "Cat"], index=0)
with p2:
    pet_breed = st.text_input("Breed", value="")
    pet_dob = st.text_input("Date of Birth (dd/mm/yyyy)", value="")
with p3:
    pet_microchip = st.text_input("Microchip ID", value="")

st.divider()

# --------------------------
# Plans & Pricing
# --------------------------
st.subheader("Plans & Pricing")

pc1, pc2 = st.columns(2, gap="large")

with pc1:
    st.markdown("### Plan 1 (Insurance)")
    plan_1_name = st.text_input("Plan 1 Name", value="PET CARE PLUS")
    plan_1_provider = st.text_input("Plan 1 Provider", value="INTERLIFE")
    plan_1_price = st.number_input("Plan 1 Annual Premium (€)", min_value=0.0, value=189.0, step=1.0)

with pc2:
    st.markdown("### Plan 2 (Network)")
    plan_2_name = st.text_input("Plan 2 Name", value="EUROLIFE My Happy Pet (SAFE PET SYSTEM)")
    plan_2_provider = st.text_input("Plan 2 Provider", value="EUROLIFE")
    plan_2_price = st.number_input("Plan 2 Annual Premium (€)", min_value=0.0, value=85.0, step=1.0)

quote_date = st.date_input("Quote Date", value=date.today())

mult = int(pet_count) if quote_mode == "Bulk (number of pets)" else 1

total = 0.0
if "PET CARE PLUS (INTERLIFE)" in selected_plans:
    total += float(plan_1_price) * mult
if "EUROLIFE My Happy Pet (SAFE PET SYSTEM)" in selected_plans:
    total += float(plan_2_price) * mult

st.metric("Total Annual Premium", f"{total:.2f} €")

notes = st.text_area(
    "Notes / Disclaimer (Page 1)",
    value="Το παρόν αποτελεί μη δεσμευτική προσφορά. Οι τελικοί όροι, προϋποθέσεις, εξαιρέσεις και καλύψεις ισχύουν όπως αναγράφονται στα επίσημα έγγραφα των ασφαλιστικών εταιρειών (Policy Wording / IPID).",
    height=90
)

st.divider()

# --------------------------
# Coverage Details (Page 2)
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
# Polaroids (2 per page)
# --------------------------
st.subheader("Happy Polaroids (2 per page)")

if "site_images" not in st.session_state:
    st.session_state["site_images"] = []

colA, colB = st.columns([1, 1], gap="large")

with colA:
    if st.button("Load images from petshealth.gr", use_container_width=True):
        try:
            st.session_state["site_images"] = fetch_site_images(PETSHEALTH_HOME_URL, limit=18)
            st.success("Loaded images from site.")
        except Exception as e:
            st.error(f"Failed to load images: {e}")

with colB:
    st.caption("Pick 2–4 images. PDF will place 2 per page automatically.")

site_images = st.session_state.get("site_images", [])
selected_image_urls = []
if site_images:
    selected_image_urls = st.multiselect(
        "Select 2–4 site images (recommended)",
        site_images,
        default=site_images[:2] if len(site_images) >= 2 else site_images
    )
    preview_cols = st.columns(4)
    for i, u in enumerate((selected_image_urls or [])[:4]):
        with preview_cols[i]:
            st.image(u, use_column_width=True)

uploaded = st.file_uploader(
    "Or upload your own images (JPG/PNG/WebP) – optional",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True
)

st.divider()

# --------------------------
# About & Official Highlights (Page 3)
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
                bio_items = fetch_highlights(PETSHEALTH_TEAM_URL, max_items=6)
                eu_items = fetch_highlights(EUROLIFE_URL, max_items=8)
                it_items = fetch_highlights(INTERLIFE_URL, max_items=8)

                st.session_state.official_bio = "\n".join(bio_items)
                st.session_state.official_eurolife = "\n".join([f"• {x}" for x in eu_items])
                st.session_state.official_interlife = "\n".join([f"• {x}" for x in it_items])

                st.success("Loaded. You can edit before generating PDF.")
            except Exception as e:
                st.error(f"Failed to load highlights: {e}")

with bcol2:
    st.caption("Tip: Bio 3–6 lines. Highlights as bullets work best.")

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
# Generate / Download
# --------------------------
generate = st.button("Generate PDF", type="primary", use_container_width=True)

if generate:
    # Build polaroid bytes list:
    polaroid_bytes = []

    # 1) from selected site urls
    for u in (selected_image_urls or [])[:4]:
        try:
            polaroid_bytes.append(download_image_bytes(u))
        except Exception:
            pass

    # 2) from uploads
    if uploaded:
        for f in uploaded[:4]:
            try:
                polaroid_bytes.append(f.read())
            except Exception:
                pass

    # Keep max 6 (enough rotation)
    polaroid_bytes = polaroid_bytes[:6]

    payload = {
        # client
        "client_name": client_name,
        "client_phone": client_phone,
        "client_email": client_email,

        # quote mode
        "quote_mode": quote_mode,
        "pet_count": int(pet_count),
        "bulk_summary": bulk_summary,

        # pet (for detailed)
        "pet_name": pet_name,
        "pet_species": pet_species,
        "pet_breed": pet_breed,
        "pet_dob": pet_dob,
        "pet_microchip": pet_microchip,

        # plans + pricing
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

        # coverage details
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

        # page 3
        "about_bio": about_bio,
        "cii_titles": lines(cii_titles),
        "official_eurolife": [x.lstrip("•").strip() for x in lines(official_eurolife)],
        "official_interlife": [x.lstrip("•").strip() for x in lines(official_interlife)],

        # polaroids
        "polaroid_images": polaroid_bytes,
    }

    quote_pdf_bytes = build_quote_pdf(payload)

    # IPIDs chosen by selected plans
    ipid_paths = []
    if include_ipid:
        for p in selected_plans:
            ipid_paths.append(IPID_MAP.get(p))

    final_pdf_bytes = merge_quote_with_ipids(quote_pdf_bytes, ipid_paths)

    missing = [p for p in ipid_paths if p and not os.path.exists(p)]
    if include_ipid and missing:
        st.warning("Some IPID files are missing in assets/ipid. Add them and redeploy:\n- " + "\n- ".join(missing))

    safe_client = (client_name or "Client").replace(" ", "_")
    safe_pet = (pet_name or ("Bulk" if "Bulk" in quote_mode else "Pet")).replace(" ", "_")
    fname = f"PETSHEALTH_Quote_{safe_client}_{safe_pet}.pdf"

    st.success("PDF ready!")
    st.download_button(
        "Download Final PDF (Quote + IPID)",
        data=final_pdf_bytes,
        file_name=fname,
        mime="application/pdf",
        use_container_width=True
    )