import streamlit as st
import datetime
import io
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF

st.set_page_config(page_title="HE · Kotolňa K6 & K7", layout="wide", page_icon="🟡")

# ── HE BRAND FARBY ──────────────────────────────────────────────
HE_YELLOW = "#F0DC00"
HE_GREEN  = "#28A028"
HE_BLACK  = "#111111"
K6_COLOR  = HE_GREEN       # kotol K6 – brand zelená
K7_COLOR  = "#2980b9"      # kotol K7 – modrá (pre kontrast)

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
        return ("↑", HE_GREEN)
    if curr < prev - threshold:
        return ("↓", "#e74c3c")
    return ("→", "#aaa")


def get_day_df(df: pd.DataFrame, den: int, max_hour: int) -> pd.DataFrame:
    rows = []
    for h in range(max_hour):
        v = get_values(df, den, h)
        v["hodina"] = h + 1
        rows.append(v)
    return pd.DataFrame(rows)


def make_vykon_chart(day_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=day_df["hodina"], y=day_df["k6_vykon"],
        name="K6", line=dict(color=K6_COLOR, width=2.5),
        mode="lines+markers", marker=dict(size=5),
    ))
    fig.add_trace(go.Scatter(
        x=day_df["hodina"], y=day_df["k7_vykon"],
        name="K7", line=dict(color=K7_COLOR, width=2.5),
        mode="lines+markers", marker=dict(size=5),
    ))
    fig.update_layout(
        title=dict(text="Výkon kotlov (MW)", font=dict(size=15)),
        xaxis=dict(title="Hodina", tickmode="linear", tick0=1, dtick=1, gridcolor="#eee"),
        yaxis=dict(title="MW", gridcolor="#eee"),
        height=320,
        margin=dict(t=50, b=40, l=50, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#fafafa",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def make_teploty_chart(day_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=day_df["hodina"], y=day_df["vystup"],
        name="Výstupná", line=dict(color="#e67e22", width=2),
        mode="lines+markers", marker=dict(size=5), yaxis="y1",
    ))
    fig.add_trace(go.Scatter(
        x=day_df["hodina"], y=day_df["vratna"],
        name="Vratná", line=dict(color="#8e44ad", width=2),
        mode="lines+markers", marker=dict(size=5), yaxis="y1",
    ))
    fig.add_trace(go.Scatter(
        x=day_df["hodina"], y=day_df["k6_spaliny"],
        name="Spaliny K6", line=dict(color=K6_COLOR, width=1.5, dash="dot"),
        mode="lines+markers", marker=dict(size=4), yaxis="y2",
    ))
    fig.add_trace(go.Scatter(
        x=day_df["hodina"], y=day_df["k7_spaliny"],
        name="Spaliny K7", line=dict(color=K7_COLOR, width=1.5, dash="dot"),
        mode="lines+markers", marker=dict(size=4), yaxis="y2",
    ))
    fig.update_layout(
        title=dict(text="Teploty (°C)", font=dict(size=15)),
        xaxis=dict(title="Hodina", tickmode="linear", tick0=1, dtick=1, gridcolor="#eee"),
        yaxis=dict(title="Výst./Vratn. (°C)", gridcolor="#eee", side="left"),
        yaxis2=dict(title="Spaliny (°C)", overlaying="y", side="right", showgrid=False),
        height=320,
        margin=dict(t=50, b=40, l=50, r=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#fafafa",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def generate_pdf(export_df: pd.DataFrame, date: datetime.date) -> bytes:
    """Brandovany PDF report v HE style: zlta hlavicka, tmavy header tabulky,
    cierny summary bar so zltou totalnou hodnotou. Core PDF fonty nepodporuju
    vsetky SK znaky, preto bez diakritiky."""

    # HE brand farby v RGB
    HE_Y = (240, 220, 0)      # #F0DC00 – žltá
    HE_K = (17, 17, 17)       # #111111 – čierna
    HE_G = (40, 160, 40)      # #28A028 – zelená (K6 accent)
    HE_MUTED = (110, 110, 110)
    HE_ZEBRA = (248, 246, 230)  # veľmi jemná žltkastá pre striedavé riadky

    class HEReportPDF(FPDF):
        """FPDF s pevnou HE pätou, ktorá sa volá automaticky na každej stránke."""
        def footer(self):
            self.set_y(-14)
            # Žltý tenký prúžok
            self.set_fill_color(*HE_Y)
            self.rect(10, self.get_y(), self.w - 20, 0.7, style="F")
            self.set_y(-11)
            self.set_x(10)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*HE_MUTED)
            half = (self.w - 20) / 2
            self.cell(half, 4,
                      f"Vystavil: Hluchan   |   Vygenerovane: "
                      f"{datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}",
                      align="L")
            self.cell(half, 4,
                      "HANDLOVSKA ENERGETIKA, s.r.o.  -  Strajkova 1, 972 51 Handlova  -  ICO: 36 297 747",
                      align="R")

    pdf = HEReportPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(10, 10, 10)
    pdf.add_page()

    # ─── ŽLTÁ HLAVIČKA (brand) ───────────────────────────────────
    pdf.set_fill_color(*HE_Y)
    pdf.rect(0, 0, pdf.w, 16, style="F")

    # Logo text vľavo
    pdf.set_xy(10, 3.5)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*HE_K)
    pdf.cell(120, 9, "HANDLOVSKA ENERGETIKA", ln=0)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(10, 8.5)
    pdf.set_text_color(*HE_K)
    pdf.cell(40, 5, "s.r.o.", ln=0)

    # Adresa a IČO vpravo
    pdf.set_xy(pdf.w - 90, 5)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*HE_K)
    pdf.cell(80, 5, "Strajkova 1, 972 51 Handlova", align="R", ln=True)
    pdf.set_xy(pdf.w - 90, 10)
    pdf.cell(80, 4, "ICO: 36 297 747", align="R")

    # Tenký čierny pruh pod žltou hlavičkou
    pdf.set_fill_color(*HE_K)
    pdf.rect(0, 16, pdf.w, 1.2, style="F")

    # ─── TITULOK ─────────────────────────────────────────────────
    pdf.set_xy(0, 22)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*HE_K)
    pdf.cell(pdf.w, 8, "DENNY VYKAZ - KOTOLNA K6 & K7", align="C", ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*HE_MUTED)
    pdf.cell(pdf.w, 5, "PREVADZKOVE PARAMETRE", align="C", ln=True)

    # ─── METADATA BLOK ───────────────────────────────────────────
    pdf.ln(2)
    pdf.set_x(10)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*HE_K)
    pdf.cell(28, 6, "Datum:", ln=0)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(55, 6, date.strftime("%d.%m.%Y"), ln=0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(28, 6, "Prevadzka:", ln=0)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(55, 6, "Handlova", ln=0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(32, 6, "Pocet hodin:", ln=0)
    pdf.set_font("Helvetica", "", 10)
    n_hours = len(export_df)
    pdf.cell(40, 6, f"{n_hours} / 24", ln=True)

    pdf.ln(2)

    # ─── TABUĽKA ─────────────────────────────────────────────────
    headers = [
        "Hodina", "K6 Vykon (MW)", "K7 Vykon (MW)",
        "Vystupna (C)", "Vratna (C)", "Prietok (m3/h)",
        "Spaliny K6 (C)", "Spaliny K7 (C)",
    ]
    col_w = [20, 34, 34, 32, 28, 34, 32, 32]
    total_w = sum(col_w)
    start_x = (pdf.w - total_w) / 2  # centrovaná tabuľka

    # Dark header riadok so žltým textom
    pdf.set_x(start_x)
    pdf.set_fill_color(*HE_K)
    pdf.set_text_color(*HE_Y)
    pdf.set_font("Helvetica", "B", 9)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=0, align="C", fill=True)
    pdf.ln()

    # Riadky so zebra striping
    pdf.set_text_color(*HE_K)
    pdf.set_font("Helvetica", "", 9)
    # Dynamická výška riadku podľa počtu hodín (aby sa zmestili všetky)
    row_h_tbl = 5.0 if n_hours <= 20 else 4.5
    for idx, (_, row) in enumerate(export_df.iterrows()):
        pdf.set_x(start_x)
        fill = (idx % 2 == 0)
        if fill:
            pdf.set_fill_color(*HE_ZEBRA)
        values = list(row)
        for i, val in enumerate(values):
            text = str(int(val)) if i == 0 else f"{val:.2f}".replace(".", ",")
            pdf.cell(col_w[i], row_h_tbl, text, border="B", align="C", fill=fill)
        pdf.ln()

    # ─── SÚHRN ZA DEŇ ────────────────────────────────────────────
    pdf.ln(3)

    def safe_avg(series):
        nz = series[series > 0]
        return float(nz.mean()) if len(nz) > 0 else 0.0

    def hours_running(series):
        return int((series > 0).sum())

    k6_ser = export_df["K6 Výkon (MW)"]
    k7_ser = export_df["K7 Výkon (MW)"]

    prod_k6 = float(k6_ser.sum())
    prod_k7 = float(k7_ser.sum())
    prod_total = prod_k6 + prod_k7
    avg_k6 = safe_avg(k6_ser)
    avg_k7 = safe_avg(k7_ser)
    max_k6 = float(k6_ser.max())
    max_k7 = float(k7_ser.max())
    h_k6 = hours_running(k6_ser)
    h_k7 = hours_running(k7_ser)

    # Nadpis sekcie
    pdf.set_x(10)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*HE_K)
    pdf.cell(0, 6, "SUHRN ZA DEN", ln=True)

    col_lx = 10
    col_rx = pdf.w / 2 + 5
    row_h = 5.0

    def sum_row(y, label, v_k6, v_k7, unit):
        pdf.set_xy(col_lx, y)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*HE_MUTED)
        pdf.cell(65, row_h, label, ln=0)
        pdf.set_text_color(*HE_K)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(40, row_h, f"{v_k6:.2f} {unit}".replace(".", ","), ln=0)

        pdf.set_xy(col_rx, y)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*HE_MUTED)
        pdf.cell(65, row_h, label, ln=0)
        pdf.set_text_color(*HE_K)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(40, row_h, f"{v_k7:.2f} {unit}".replace(".", ","), ln=True)

    # Hlavičky stĺpcov K6 / K7
    y = pdf.get_y()
    pdf.set_xy(col_lx, y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*HE_G)
    pdf.cell(105, row_h + 1, "Kotol K6", ln=0)
    pdf.set_xy(col_rx, y)
    pdf.set_text_color(41, 128, 185)  # K7 modrá
    pdf.cell(105, row_h + 1, "Kotol K7", ln=True)

    sum_row(pdf.get_y(), "Produkcia tepla:", prod_k6, prod_k7, "MWh")
    sum_row(pdf.get_y(), "Priemerny vykon:", avg_k6, avg_k7, "MW")
    sum_row(pdf.get_y(), "Maximalny vykon:", max_k6, max_k7, "MW")

    # Hodiny v prevádzke (celé čísla)
    y = pdf.get_y()
    pdf.set_xy(col_lx, y)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*HE_MUTED)
    pdf.cell(65, row_h, "Hodin v prevadzke:", ln=0)
    pdf.set_text_color(*HE_K)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(40, row_h, f"{h_k6} h", ln=0)
    pdf.set_xy(col_rx, y)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*HE_MUTED)
    pdf.cell(65, row_h, "Hodin v prevadzke:", ln=0)
    pdf.set_text_color(*HE_K)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(40, row_h, f"{h_k7} h", ln=True)

    # ─── VEĽKÝ SUMMARY BAR ──────────────────────────────────────
    pdf.ln(2)
    bar_y = pdf.get_y()
    bar_h = 11
    pdf.set_fill_color(*HE_K)
    pdf.rect(10, bar_y, pdf.w - 20, bar_h, style="F")

    pdf.set_xy(14, bar_y + 2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(120, 7, "PRODUKCIA TEPLA SPOLU:", ln=0)

    pdf.set_xy(pdf.w - 14 - 100, bar_y + 1.5)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*HE_Y)
    pdf.cell(100, 8, f"{prod_total:.2f} MWh".replace(".", ","), ln=0, align="R")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()



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

# Globálne štýly + HE brand hlavička
st.markdown(f"""
<style>
.block-container {{ padding-top: 1rem; }}

/* HE hlavička */
.he-header {{
    background: {HE_BLACK};
    padding: 16px 22px;
    border-bottom: 5px solid {HE_YELLOW};
    border-radius: 6px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}}
.he-logo-svg {{ width: 52px; height: 52px; flex-shrink: 0; }}
.he-text-block {{ display: flex; flex-direction: column; justify-content: center; }}
.he-company {{
    color: {HE_YELLOW};
    font-size: 22px;
    font-weight: 900;
    letter-spacing: 0.5px;
    line-height: 1.1;
}}
.he-company-suffix {{
    color: #ffffff;
    font-weight: 500;
    font-size: 14px;
    opacity: 0.85;
    margin-left: 6px;
}}
.he-subtitle {{
    color: #cfcfcf;
    font-size: 11px;
    margin-top: 4px;
    letter-spacing: 2px;
    text-transform: uppercase;
}}

/* Aktívna hodina = HE žltá */
div[data-testid="column"] button[kind="primary"] {{
    background-color: {HE_YELLOW} !important;
    color: {HE_BLACK} !important;
    border-color: {HE_YELLOW} !important;
    font-weight: 700 !important;
}}
div[data-testid="column"] button[kind="primary"]:hover {{
    background-color: #d4c300 !important;
    color: {HE_BLACK} !important;
    border-color: #d4c300 !important;
}}
/* Kompaktnejšie tlačidlá v mriežke hodín */
div[data-testid="column"] button[kind="secondary"],
div[data-testid="column"] button[kind="primary"] {{
    padding: 0.25rem 0.1rem;
    font-size: 0.85rem;
    font-weight: 600;
    min-height: 2.1rem;
}}

/* Päta */
.he-footer {{
    margin-top: 30px;
    padding: 12px 18px;
    background: {HE_BLACK};
    color: #cfcfcf;
    font-size: 11px;
    border-top: 3px solid {HE_YELLOW};
    border-radius: 4px;
    text-align: center;
    letter-spacing: 0.5px;
}}
.he-footer b {{ color: {HE_YELLOW}; }}
</style>

<div class="he-header">
    <svg class="he-logo-svg" viewBox="0 0 50 50" xmlns="http://www.w3.org/2000/svg">
        <!-- kotolňa silueta -->
        <rect x="4"  y="30" width="8" height="16" fill="{HE_YELLOW}"/>
        <rect x="14" y="22" width="8" height="24" fill="{HE_YELLOW}"/>
        <rect x="24" y="12" width="8" height="34" fill="{HE_YELLOW}"/>
        <rect x="34" y="24" width="8" height="22" fill="{HE_YELLOW}"/>
        <!-- dym / para -->
        <circle cx="28" cy="8"  r="2"   fill="{HE_YELLOW}" opacity="0.7"/>
        <circle cx="32" cy="4"  r="1.5" fill="{HE_YELLOW}" opacity="0.5"/>
        <circle cx="18" cy="18" r="1.5" fill="{HE_YELLOW}" opacity="0.6"/>
    </svg>
    <div class="he-text-block">
        <div class="he-company">HANDLOVSKÁ ENERGETIKA<span class="he-company-suffix">s.r.o.</span></div>
        <div class="he-subtitle">Prevádzkové parametre · Kotolňa K6 & K7</div>
    </div>
</div>
""", unsafe_allow_html=True)

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

# ── VÝBER HODINY (mriežka tlačidiel 12 × 2) ─────────────────────

if st.session_state.get("last_sel_date") != sel_date:
    st.session_state.selected_hour = min(now_h, max_h)
    st.session_state.last_sel_date = sel_date

if st.session_state.get("selected_hour", 1) > max_h:
    st.session_state.selected_hour = max_h

st.markdown(
    f"<div style='font-size:13px;color:#666;margin-bottom:6px;'>"
    f"Hodina: <b style='color:{HE_BLACK};'>{st.session_state.selected_hour}:00</b></div>",
    unsafe_allow_html=True,
)

for r in range(2):
    cols = st.columns(12, gap="small")
    for c in range(12):
        h = r * 12 + c + 1
        is_active   = (h == st.session_state.selected_hour)
        is_disabled = h > max_h
        if cols[c].button(
            f"{h:02d}",
            key=f"hour_btn_{h}",
            type="primary" if is_active else "secondary",
            disabled=is_disabled,
            use_container_width=True,
        ):
            st.session_state.selected_hour = h
            st.rerun()

hour     = st.session_state.selected_hour
hour_idx = hour - 1

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
    st.markdown(f"<h3 style='text-align:center;color:{K6_COLOR};'>Kotol K6</h3>",
                unsafe_allow_html=True)
    st.plotly_chart(make_gauge(vals["k6_vykon"], "Výkon K6", K6_COLOR),
                    width='stretch')
    sym, col = tr("k6_vykon", 0.05)
    if sym:
        st.markdown(
            f'<div style="text-align:center;font-size:28px;color:{col};margin-top:-10px;">{sym}</div>',
            unsafe_allow_html=True)

with gc7:
    st.markdown(f"<h3 style='text-align:center;color:{K7_COLOR};'>Kotol K7</h3>",
                unsafe_allow_html=True)
    st.plotly_chart(make_gauge(vals["k7_vykon"], "Výkon K7", K7_COLOR),
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
    mcard("Teplota spalín K6", vals["k6_spaliny"], "°C", K6_COLOR, tr("k6_spaliny", 0.5))
with s2:
    mcard("Teplota spalín K7", vals["k7_spaliny"], "°C", K7_COLOR, tr("k7_spaliny", 0.5))

# ── DENNÝ TREND ─────────────────────────────────────────────────
st.divider()
st.subheader("Denný trend")

day_df = get_day_df(df, sel_date.day, max_h)

t1, t2 = st.columns(2)
with t1:
    st.plotly_chart(make_vykon_chart(day_df), use_container_width=True)
with t2:
    st.plotly_chart(make_teploty_chart(day_df), use_container_width=True)

# ── EXPORT CSV / PDF ────────────────────────────────────────────
st.divider()
export_df = pd.DataFrame({
    "Hodina": day_df["hodina"],
    "K6 Výkon (MW)": day_df["k6_vykon"],
    "K7 Výkon (MW)": day_df["k7_vykon"],
    "Výstupná teplota (°C)": day_df["vystup"],
    "Vratná teplota (°C)": day_df["vratna"],
    "Prietok (m³/h)": day_df["prietok"],
    "Spaliny K6 (°C)": day_df["k6_spaliny"],
    "Spaliny K7 (°C)": day_df["k7_spaliny"],
})
csv_str = export_df.to_csv(index=False, sep=";", decimal=",")
dl1, dl2 = st.columns([1, 1])
with dl1:
    st.download_button(
        label="💾 Stiahnuť denný report (CSV)",
        data=csv_str,
        file_name=f"kotolna_{sel_date.strftime('%Y-%m-%d')}.csv",
        mime="text/csv",
    )
with dl2:
    pdf_bytes = generate_pdf(export_df, sel_date)
    st.download_button(
        label="💾 Stiahnuť denný report (PDF)",
        data=pdf_bytes,
        file_name=f"kotolna_{sel_date.strftime('%Y-%m-%d')}.pdf",
        mime="application/pdf",
    )

# ── REFRESH ─────────────────────────────────────────────────────
st.markdown("")
if st.button("Obnoviť dáta", type="secondary"):
    st.cache_data.clear()
    st.rerun()

# ── PÄTA ────────────────────────────────────────────────────────
st.markdown(f"""
<div class="he-footer">
    <b>HANDLOVSKÁ ENERGETIKA, s.r.o.</b> · Štrajková 1, 972 51 Handlová · IČO: 36 297 747
</div>
""", unsafe_allow_html=True)
