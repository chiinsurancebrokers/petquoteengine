import streamlit as st
from datetime import date
import requests
import re
from pdf_builder import build_quote_pdf

st.set_page_config(page_title="PETSHEALTH PDF Generator", page_icon="🐾", layout="wide")

PETSHEALTH_TEAM_URL = "https://www.petshealth.gr/petshealt-team"
EUROLIFE_URL = "https://www.eurolife.gr/el-GR/proionta/idiotes/katoikidio/my-happy-pet"
INTERLIFE_URL = "https://www.interlife-programs.gr/asfalisi/eidika-programmata/#petcare"

def clean_text(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def extract_highlights(url: str, max_items=10):
    """
    Lightweight extractor: pulls some meaningful text chunks.
    Not perfect scraping, but good enough for 'official highlights' textareas.
    """
    r = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    html = r.text

    # Grab headings and list items roughly
    raw = re.findall(r"<h1[^>]*>(.*?)</h1>|<h2[^>]*>(.*?)</h2>|<h3[^>]*>(.*?)</h3>|<li[^>]*>(.*?)</li>|<p[^>]*>(.*?)</p>", html, flags=re.I|re.S)
    items = []
    for tup in raw:
        for part in tup:
            if part:
                txt = clean_text(part)
                # filter very short / boilerplate
                if len(txt) >= 35 and not any(b in txt.lower() for b in ["cookie", "privacy", "javascript", "©"]):
                    items.append(txt)

    # de-dup while preserving order
    seen = set()
    out = []
    for it in items:
        key = it.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
        if len(out) >= max_items:
            break
    return out

def lines(txt: str):
    return [x.strip() for x in (txt or "").splitlines() if x.strip()]

# ---------- UI Header ----------
st.markdown(
    """
    <div style="padding:14px 18px;border-radius:14px;background:#111827;color:white;">
      <div style="font-size:22px;font-weight:700;">PETSHEALTH – PDF Quote Auto-Generator</div>
      <div style="opacity:0.85;">Create branded pet insurance quotations in seconds</div>
    </div>
    """,
    unsafe_allow_html=True
)
st.write("")

# ---------- Client / Pet ----------
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

# ---------- Pricing ----------
col1, col2, col3 = st.columns([2, 2, 1], gap="large")
with col1:
    st.subheader("Plan 1 (Insurance)")
    plan_1_name = st.text_input("Plan 1 Name", value="PET CARE PLUS")
    plan_1_provider = st.text_input("Plan 1 Provider", value="INTERLIFE")
    plan_1_price = st.number_input("Plan 1 Annual Premium (€)", min_value=0.0, value=189.0, step=1.0)

with col2:
    st.subheader("Plan 2 (Network)")
    plan_2_name = st.text_input("Plan 2 Name", value="EUROLIFE My Happy Pet (SAFE PET SYSTEM)")
    plan_2_provider = st.text_input("Plan 2 Provider", value="EUROLIFE")
    plan_2_price = st.number_input("Plan 2 Annual Premium (€)", min_value=0.0, value=85.0, step=1.0)

with col3:
    st.subheader("Total")
    total_price = plan_1_price + plan_2_price
    st.metric("Total Annual Premium", f"{total_price:.2f} €")
    quote_date = st.date_input("Quote Date", value=date.today())

st.subheader("Notes / Disclaimer (Page 1)")
notes = st.text_area(
    "Shown in the PDF",
    value="Το παρόν αποτελεί μη δεσμευτική προσφορά. Οι τελικοί όροι, προϋποθέσεις, εξαιρέσεις και καλύψεις ισχύουν όπως αναγράφονται στα επίσημα έγγραφα των ασφαλιστικών εταιρειών.",
    height=80
)

st.divider()
st.subheader("Plan Coverage Descriptions (Page 2)")

left, right = st.columns(2, gap="large")

with left:
    st.markdown("### PET CARE PLUS (INTERLIFE)")
    plan1_limit = st.text_input("Limit (Plan 1)", value="2.000€ / ανά έτος")
    plan1_area = st.text_input("Geographic Area (Plan 1)", value="Ελλάδα")

    plan1_key_facts_txt = st.text_area(
        "Key Facts (one per line)",
        value="\n".join([
            "Ελεύθερη επιλογή κτηνιάτρου και κλινικής",
            "Απαλλαγή: 50€ ανά περιστατικό (όπου εφαρμόζεται)",
        ]),
        height=80
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
        height=140
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
        height=110
    )

    plan1_waiting_txt = st.text_area(
        "Waiting Periods (one per line)",
        value="\n".join([
            "Ασθένεια: 60 ημέρες από την έναρξη",
            "Απώλεια ζωής: 180 ημέρες από την έναρξη",
            "Ατύχημα: από την έναρξη του συμβολαίου",
        ]),
        height=90
    )

with right:
    st.markdown("### EUROLIFE My Happy Pet (SAFE PET SYSTEM)")
    plan2_limit = st.text_input("Limit (Plan 2)", value="Απεριόριστο (εντός δικτύου, με συμμετοχή)")
    plan2_area = st.text_input("Geographic Area (Plan 2)", value="Αττική – Θεσσαλονίκη (συμβεβλημένο δίκτυο)")

    plan2_key_facts_txt = st.text_area(
        "Key Facts (one per line)",
        value="\n".join([
            "Αποκλειστικά συμβεβλημένο δίκτυο κτηνιάτρων & κλινικών",
            "Απαλλαγή: 0€ (λειτουργεί με συμμετοχή ανά υπηρεσία)",
            "Νοσοκομειακές δαπάνες & εξετάσεις με ειδικό εκπτωτικό τιμοκατάλογο για μέλη",
        ]),
        height=90
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
        height=160
    )

    plan2_exclusions_txt = st.text_area(
        "Not Covered / Limits (one per line)",
        value="\n".join([
            "Εκτός δικτύου: δεν ισχύει κάλυψη/τιμοκατάλογος",
            "Απαιτείται ηλεκτρονική σήμανση (microchip)",
            "Φάρμακα: σύμφωνα με όρους/τιμοκατάλογο προγράμματος",
        ]),
        height=110
    )

    plan2_waiting_txt = st.text_area(
        "Waiting Periods (one per line)",
        value="\n".join([
            "Ατύχημα ή ασθένεια: από την έναρξη του συμβολαίου (σύμφωνα με όρους προγράμματος)",
        ]),
        height=80
    )

st.divider()
st.subheader("Enrich Content (optional) – Load official highlights")

if "official_eurolife" not in st.session_state:
    st.session_state.official_eurolife = ""
if "official_interlife" not in st.session_state:
    st.session_state.official_interlife = ""
if "official_bio" not in st.session_state:
    st.session_state.official_bio = ""

btn = st.button("Load official highlights", use_container_width=True)

if btn:
    try:
        eu = extract_highlights(EUROLIFE_URL, max_items=8)
        it = extract_highlights(INTERLIFE_URL, max_items=8)
        bio = extract_highlights(PETSHEALTH_TEAM_URL, max_items=8)

        st.session_state.official_eurolife = "\n".join([f"• {x}" for x in eu])
        st.session_state.official_interlife = "\n".join([f"• {x}" for x in it])
        st.session_state.official_bio = "\n".join([x for x in bio])

        st.success("Loaded official highlights. Edit them as you wish before generating PDF.")
    except Exception as e:
        st.error(f"Could not load highlights: {e}")

colx, coly = st.columns(2, gap="large")
with colx:
    official_eurolife = st.text_area("EUROLIFE official highlights (editable)", value=st.session_state.official_eurolife, height=160)
with coly:
    official_interlife = st.text_area("INTERLIFE official highlights (editable)", value=st.session_state.official_interlife, height=160)

about_bio = st.text_area("Your Bio / About (Page 3 – editable)", value=st.session_state.official_bio, height=170)

cii_titles = st.text_area(
    "CII Titles / Credentials (one per line)",
    value="\n".join([
        "Chartered Insurance Institute – (PL4) Introduction to Pet Insurance (Unit achieved: June 2023)",
        "Chartered Insurance Institute – (W01) Award in General Insurance (English) (Unit achieved: March 2025)",
    ]),
    height=90
)

st.write("")
generate = st.button("Generate PDF 🧾", use_container_width=True)

def bullet_lines(txt: str):
    out = []
    for ln in (txt or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        ln = ln.lstrip("•").strip()
        out.append(ln)
    return out

if generate:
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
        "plan_1_price": f"{plan_1_price:.2f}",

        "plan_2_name": plan_2_name,
        "plan_2_provider": plan_2_provider,
        "plan_2_price": f"{plan_2_price:.2f}",

        "total_price": f"{total_price:.2f} €",
        "quote_date": quote_date.strftime("%d/%m/%Y"),
        "notes": notes,

        "plan1_limit": plan1_limit,
        "plan1_area": plan1_area,
        "plan1_key_facts": lines(plan1_key_facts_txt),
        "plan1_covers": lines(plan1_covers_txt),
        "plan1_exclusions": lines(plan1_exclusions_txt),
        "plan1_waiting": lines(plan1_waiting_txt),

        "plan2_limit": plan2_limit,
        "plan2_area": plan2_area,
        "plan2_key_facts": lines(plan2_key_facts_txt),
        "plan2_covers": lines(plan2_covers_txt),
        "plan2_exclusions": lines(plan2_exclusions_txt),
        "plan2_waiting": lines(plan2_waiting_txt),

        # Page 3 about
        "about_bio": about_bio,
        "cii_titles": lines(cii_titles),

        # Optional official highlights for page 3
        "official_eurolife": bullet_lines(official_eurolife),
        "official_interlife": bullet_lines(official_interlife),
    }

    pdf_bytes = build_quote_pdf(payload)
    filename = f"PETSHEALTH_Quote_{client_name or 'Client'}_{pet_name or 'Pet'}.pdf".replace(" ", "_")

    st.success("PDF generated!")
    st.download_button(
        "Download PDF",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        use_container_width=True
    )