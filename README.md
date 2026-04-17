# Kotolňa K6 & K7 — Streamlit dashboard

Dashboard prevádzkových parametrov kotlov K6 a K7 (výkon, teploty, prietok, spaliny). Dáta sa načítavajú z verejných Google Sheets cez CSV export, cachujú sa na 5 minút.

## Požiadavky
- Python **3.10+** (skript používa PEP 604 syntax `X | None`)

## Inštalácia
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Spustenie
```bash
streamlit run streamlit_app.py
```
Otvor `http://localhost:8501`.

## Použitie
- **Deň**: Dnes / Včera / Predvčerom
- **Hodina**: slider 1–24 (pre dnes obmedzený na aktuálnu hodinu)
- **Obnoviť dáta**: vynúti nové načítanie (vyprázdni cache)

## Nasadenie (Streamlit Community Cloud)
1. Push repo na GitHub.
2. Na [share.streamlit.io](https://share.streamlit.io) pripoj repo.
3. Entry point: `streamlit_app.py`.
