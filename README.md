# petquoteengine – PETSHEALTH

Streamlit PDF auto-generator for Pet Insurance quotations.

## Features
- Branded PETSHEALTH PDF
- Page 1: Client & Pet Summary + Pricing
- Page 2: Coverage cards (PET CARE PLUS / EUROLIFE)
- Page 3: Advisor Bio + CII credentials + official highlights
- Full Greek Unicode support (Noto Sans fonts)

## Run locally
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py

## Deploy
Use Streamlit Community Cloud:
- Repo: chiinsurancebrokers/petquoteengine
- Branch: main
- Main file: app.py



