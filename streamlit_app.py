import streamlit as st
import datetime
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Kotolňa K6 & K7", layout="wide")

# ── KONFIGURÁCIA ────────────────────────────────────────────────
PREVADZKA_SHEETS = {
    2:  {"sheet_id": "1FXmRJwlRr6N2u_aZzuzjnn0HHgNEBTem64B1phXl_NM", "denny_gid": "759527346"},
    3:  {"sheet_id": "1YSYltBW8uw3whOxNr3w8KLgvMkE-vqAV1cCeIn8Ymp0", "denny_gid": "737601644"},
    4:  {"sheet_id": "1E2gxstdMVwj5X__5qrPuRJgkV5GtqLK6BtmmCc3GE00", "denny_gid": "737601644"},
    5:  {"sheet_id": "1i2T90bUbEcT79gboX-c_Nc1LMpwVkm5IwDbEvsupyew",  "denny_gid": "737601644"},
    6:  {"sheet_id": "1ZeCtlKJvpm3Wh0R42xD4DTbS_IZBknEI1d3jyB6rFyE",  "denny_gid": "737601644"},
    7:  {"sheet_id": "17PRL6X_H2v5kRZG_GrNnrRr5GycmAy0bixiz22pfjCo",  "denny_gid": "737601644"},
    8:  {"sheet_id": "1HDOPn1JXyCOpVqEdhS72dStUnbe0EL2oY7x3UUukEQE",  "denny_gid": "737601644"},
    9:  {"sheet_id": "1mcnJs9YnDJF24cnrkXgxty6Zj_8qvG6Az7IGl_KT6fc",  "denny_gid": "737601644"},
    10: {"sheet_id": "1KfLEUiG6HDvNwYS2Igve_5-OWG-UV2tXWqJbtTkNu1A",  "denny_gid": "737601644"},
    11: {"sheet_id": "1E5jaZULw9sOUTMYoDtsjbcH6YkX79Abnx9ueZ1mEj_g",  "denny_gid": "737601644"},
    12: {"sheet_id": "1Mca2EkHACVktZaw2FrtaDwsvW6nCn5P0Gm-bl-NQB50",  "denny_gid": "737601644"},
}

# Stĺpce v dennom zázname (0-indexované)
DZ_K6         = 13   # N  – Výkon K6 (MW)
DZ_K7         = 30   # AE – Výkon K7 (MW)
DZ_K6_PRIETOK = 14   # O  – Prietok K6 (m³/h)
DZ_K7_PRIETOK = 31   # AF – Prietok K7 (m³/h)
DZ_K6_VYSTUP  = 2    # C  – Výstupná teplota K6 (°C)
DZ_K6_VRATNA  = 3    # D  – Vratná teplota K6 (°C)
DZ_K6_SPALINY = 5    # F  – Teplota spalín K6 (°C)
DZ_K7_VYSTUP  = 19   # T  – Výstupná teplota K7 (°C)
DZ_K7_VRATNA  = 20   # U  – Vratná teplota K7 (°C)
DZ_K7_SPALINY = 22   # W  – Teplota spalín K7 (°C)


# ── POMOCNÉ FUNKCIE ─────────────────────────────────────────────

def gs_url(sheet_id: str, gid: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


@st.cache_data(ttl=300)
def load_sheet(sheet_id: str, gid: str) -> pd.DataFrame | None:
    try:
        return pd.read_csv(gs_url(sheet_id, gid), header=None, dtype=str)
    except Exception as e:
        st.error(f"Chyba pri načítaní dát: {e}")
        return None


def safe_float(df: pd.DataFrame, row: int, col: int) -> float | None:
    try:
        if row >= len(df) or col >= len(df.columns):
            return None
        v = df.iloc[row, col]
        if pd.isna(v) or str(v).strip() in ("", "-", "—"):
            return None
        return float(str(v).replace(",", ".").replace("\xa0", "").strip())
    except Exception:
        return None


def get_values(df: pd.DataFrame, den: int, hour_idx: int) -> dict:
    ri = 5 + (den - 1) * 35 + hour_idx

    def gv(col: int) -> float:
        v = safe_float(df, ri, col)
        return v if v is not None else 0.0

    d = {
        "k6_vykon":   gv(DZ_K6),
        "k7_vykon":   gv(DZ_K7),
        "k6_prietok": gv(DZ_K6_PRIETOK),
        "k7_prietok": gv(DZ_K7_PRIETOK),
        "k6_vystup":  gv(DZ_K6_VYSTUP),
        "k7_vystup":  gv(DZ_K7_VYSTUP),
        "k6_vratna":  gv(DZ_K6_VRATNA),
        "k7_vratna":  gv(DZ_K7_VRATNA),
        "k6_spaliny": gv(DZ_K6_SPALINY),
        "k7_spaliny": gv(DZ_K7_SPALINY),
    }

    # Korekcia: keď oba kotle bežia a výkon je nereálne vysoký
    if d["k6_vykon"] > 0 and d["k7_vykon"] > 0:
        if d["k6_vykon"] > 3.3:
            d["k6_vykon"] /= 2
        if d["k7_vykon"] > 3.3:
            d["k7_vykon"] /= 2

    # Spoločné hodnoty: priemer z bežiacich kotlov
    def avg_nonzero(*vals):
        nz = [v for v in vals if v > 0]
        return sum(nz) / len(nz) if nz else 0.0

    d["vystup"]  = avg_nonzero(d["k6_vystup"],  d["k7_vystup"])
    d["vratna"]  = avg_nonzero(d["k6_vratna"],  d["k7_vratna"])
    d["prietok"] = avg_nonzero(d["k6_prietok"], d["k7_prietok"])
    return d


def get_trend(curr: float, prev: float, threshold: float) -> tuple[str, str]:
    if curr == 0.0 or prev == 0.0:
        return ("", "")
    if curr > prev + threshold:
        return ("↑", "#27ae60")
    if curr < prev - threshold:
        return ("↓", "#e74c3c")
    return ("→", "#aaa")


def make_gauge(value: float, title: str, bar_color: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 16, "color": "#333"}},
        number={
            "suffix": " MW",
            "font": {"size": 34, "color": "#111"},
            "valueformat": ".2f",
        },
        gauge={
            "axis": {
                "range": [0, 3.5],
                "tickvals": [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
                "ticktext": ["0", "0,5", "1,0", "1,5", "2,0", "2,5", "3,0", "3,5"],
                "tickfont": {"size": 11},
                "tickcolor": "#555",
                
            },
            "bar": {"color": bar_color, "thickness": 0.28},
            "bgcolor": "white",
            "borderwidth": 1,
            "bordercolor": "#ddd",
            "steps": [
                {"range": [0.0, 3.0], "color": "#f3f3f3"},
                {"range": [3.0, 3.5], "color": "#ffe4e4"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 5},
                "thickness": 0.85,
                "value": 3.0,
            },
        },
    ))
    fig.update_layout(
        height=300,
        margin=dict(t=65, b=20, l=15, r=15),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def mcard(label: str, value: float, unit: str, color: str,
          trend: tuple[str, str] | None = None) -> None:
    if value == 0.0:
        display, val_color = "—", "#bbb"
    else:
        display = f"{value:.1f}&nbsp;{unit}".replace(".", ",")
        val_color = "#111"
    trend_html = ""
    if trend and trend[0]:
        trend_html = (
            f'<span style="font-size:18px;color:{trend[1]};'
            f'margin-left:8px;vertical-align:middle;">{trend[0]}</span>'
        )
    st.markdown(
        f"""<div style="background:white;border-radius:8px;padding:13px 17px;
            margin-bottom:9px;border-left:4px solid {color};
            box-shadow:0 1px 4px rgba(0,0,0,0.09);">
            <div style="font-size:12px;color:#888;margin-bottom:3px;">{label}</div>
            <div style="font-size:22px;font-weight:700;color:{val_color};">{display}{trend_html}</div>
        </div>""",
        unsafe_allow_html=True,
    )


# ── STREAMLIT UI ────────────────────────────────────────────────

st.markdown("<style>.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st.title("Prevádzkové parametre kotlov K6 a K7")

today = datetime.date.today()
day_labels = [
    f"Dnes  ({today.strftime('%d.%m.%Y')})",
    f"Včera  ({(today - datetime.timedelta(1)).strftime('%d.%m.%Y')})",
    f"Predvčerom  ({(today - datetime.timedelta(2)).strftime('%d.%m.%Y')})",
]
day_dates = [today, today - datetime.timedelta(1), today - datetime.timedelta(2)]

sel_label = st.radio("Deň:", day_labels, horizontal=True)
sel_date  = day_dates[day_labels.index(sel_label)]

now_h = datetime.datetime.now().hour + 1   # aktuálna hodina (1-based)
max_h = now_h if sel_date == today else 24
hour  = st.slider("Hodina", 1, max_h, min(now_h, max_h))
hour_idx = hour - 1   # 0-based pre indexovanie

# ── NAČÍTANIE DÁT ───────────────────────────────────────────────
cfg = PREVADZKA_SHEETS.get(sel_date.month)
if cfg is None:
    st.error(f"Mesiac {sel_date.month} nie je nakonfigurovaný v PREVADZKA_SHEETS.")
    st.stop()

with st.spinner("Načítavam dáta z Google Sheets..."):
    df = load_sheet(cfg["sheet_id"], cfg["denny_gid"])

if df is None:
    st.stop()

vals = get_values(df, sel_date.day, hour_idx)
prev_vals = get_values(df, sel_date.day, hour_idx - 1) if hour_idx > 0 else None

def tr(key: str, threshold: float) -> tuple[str, str]:
    if prev_vals is None:
        return ("", "")
    return get_trend(vals[key], prev_vals[key], threshold)

st.caption(
    f"Dátum: **{sel_date.strftime('%d.%m.%Y')}** | "
    f"Hodina: **{hour}:00** | "
    f"Dáta sú cachované na 5 min."
)
st.divider()

# ── VÝKON – GAUGES ──────────────────────────────────────────────
gc6, gc7 = st.columns(2)
with gc6:
    st.markdown("<h3 style='text-align:center;color:#27ae60;'>Kotol K6</h3>",
                unsafe_allow_html=True)
    st.plotly_chart(make_gauge(vals["k6_vykon"], "Výkon K6", "#27ae60"),
                    width='stretch')
    sym, col = tr("k6_vykon", 0.05)
    if sym:
        st.markdown(
            f'<div style="text-align:center;font-size:28px;color:{col};margin-top:-10px;">{sym}</div>',
            unsafe_allow_html=True)

with gc7:
    st.markdown("<h3 style='text-align:center;color:#2980b9;'>Kotol K7</h3>",
                unsafe_allow_html=True)
    st.plotly_chart(make_gauge(vals["k7_vykon"], "Výkon K7", "#2980b9"),
                    width='stretch')
    sym, col = tr("k7_vykon", 0.05)
    if sym:
        st.markdown(
            f'<div style="text-align:center;font-size:28px;color:{col};margin-top:-10px;">{sym}</div>',
            unsafe_allow_html=True)

st.divider()

# ── SPOLOČNÉ PARAMETRE ──────────────────────────────────────────
p1, p2, p3 = st.columns(3)
with p1:
    mcard("Výstupná teplota", vals["vystup"], "°C", "#e67e22", tr("vystup", 0.5))
with p2:
    mcard("Vratná teplota", vals["vratna"], "°C", "#8e44ad", tr("vratna", 0.5))
with p3:
    mcard("Priemerný prietok", vals["prietok"], "m³/h", "#16a085", tr("prietok", 0.5))

# ── TEPLOTA SPALÍN ──────────────────────────────────────────────
s1, s2 = st.columns(2)
with s1:
    mcard("Teplota spalín K6", vals["k6_spaliny"], "°C", "#27ae60", tr("k6_spaliny", 0.5))
with s2:
    mcard("Teplota spalín K7", vals["k7_spaliny"], "°C", "#2980b9", tr("k7_spaliny", 0.5))

# ── REFRESH ─────────────────────────────────────────────────────
st.markdown("")
if st.button("Obnoviť dáta", type="secondary"):
    st.cache_data.clear()
    st.rerun()
