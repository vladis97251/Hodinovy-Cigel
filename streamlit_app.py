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
HE_SURFACE = "#FFFDF8"
HE_SURFACE_ALT = "#F6F1E5"
HE_BORDER = "#D7CDB3"
HE_TEXT_MUTED = "#676050"

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


def _find_dejavu_fonts() -> tuple[str | None, str | None]:
    """Najdi DejaVuSans.ttf + DejaVuSans-Bold.ttf na systéme.
    Vracia (regular_path, bold_path) alebo (None, None). DejaVu je potrebný
    aby PDF vedelo zobraziť slovenskú diakritiku."""
    from pathlib import Path

    search_dirs: list[Path] = []

    # matplotlib bundles these — najspoľahlivejší zdroj
    try:
        import matplotlib
        search_dirs.append(Path(matplotlib.get_data_path()) / "fonts" / "ttf")
    except Exception:
        pass

    # Bundled vedľa skriptu
    try:
        search_dirs.append(Path(__file__).parent / "fonts")
    except NameError:
        pass

    # Systémové lokácie (Windows / Linux / macOS)
    search_dirs.extend([
        Path("C:/Windows/Fonts"),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/TTF"),
        Path("/usr/share/fonts/dejavu"),
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
    ])

    for d in search_dirs:
        try:
            reg = d / "DejaVuSans.ttf"
            bold = d / "DejaVuSans-Bold.ttf"
            if reg.exists() and bold.exists():
                return str(reg), str(bold)
        except Exception:
            continue
    return None, None


def _strip_diacritics(s: str) -> str:
    """Fallback pre Helvetica core font: nahraď non-Latin1 znaky ASCII
    ekvivalentami, potom odstráň diakritiku. Safety net na konci mapuje
    čokoľvek nepodporované na '?' aby fpdf2 nespadol.

    Helvetica core font vie len Latin-1 (resp. WinAnsi). Znaky ako en-dash
    '–', curly quotes, middle dot '·', ellipsis '…' Latin-1 nevie — musíme
    ich ručne nahradiť skôr než odstránime diakritiku."""
    import unicodedata

    # Non-Latin1 typografické znaky → ASCII ekvivalenty
    replacements = {
        "–": "-",    # en-dash U+2013
        "—": "-",    # em-dash U+2014
        "−": "-",    # minus sign U+2212
        "…": "...",  # horizontal ellipsis U+2026
        "\u00A0": " ",  # non-breaking space
        "\u202F": " ",  # narrow no-break space
        "\u2009": " ",  # thin space
        "\u200B": "",   # zero-width space
        "„": '"',    # SK dolné úvodzovky U+201E
        "“": '"',    # left double quote U+201C
        "”": '"',    # right double quote U+201D
        "‘": "'",    # left single quote U+2018
        "’": "'",    # right single quote U+2019
        "‚": ",",    # single low quote U+201A
        "«": '"',    # left guillemet
        "»": '"',    # right guillemet
        "•": "*",    # bullet U+2022
        "→": "->",   # right arrow U+2192
        "←": "<-",   # left arrow U+2190
        "↑": "^",    # up arrow U+2191
        "↓": "v",    # down arrow U+2193
    }
    for k, v in replacements.items():
        s = s.replace(k, v)

    # Odstráň diakritiku cez NFD dekompozíciu (ľ → l, š → s, á → a, ...)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if not unicodedata.combining(c)
    )

    # Safety net: čokoľvek ešte mimo Latin-1 nahraď '?' aby fpdf nespadol
    return "".join(c if ord(c) < 256 else "?" for c in s)


def generate_pdf(export_df: pd.DataFrame, date: datetime.date) -> bytes:
    """Brandovaný PDF report v HE štýle: žltá hlavička so zeleným akcentom,
    tmavý header tabuľky, čierny summary bar so žltou totálnou hodnotou.
    Ak je dostupný DejaVu Sans, použije sa plná slovenská diakritika."""

    # HE brand farby v RGB
    HE_Y = (240, 220, 0)        # #F0DC00 – žltá
    HE_K = (17, 17, 17)         # #111111 – čierna
    HE_G = (40, 160, 40)        # #28A028 – HE zelená
    HE_MUTED = (110, 110, 110)
    HE_ZEBRA = (248, 246, 230)  # veľmi jemná žltkastá pre striedavé riadky
    K7_BLUE = (41, 128, 185)    # K7 modrá

    # Pokús sa načítať DejaVu – inak fallback na Helvetica bez diakritiky
    reg_path, bold_path = _find_dejavu_fonts()

    class HEReportPDF(FPDF):
        """FPDF s pevnou HE pätou. Päta obsahuje dvojfarebný pás
        (žltá nad zelenou) – rovnako ako vo webovej päte."""
        def footer(self):
            # Žltá + zelená (dvojpás) — mirror webu
            self.set_y(-14)
            self.set_fill_color(*HE_Y)
            self.rect(10, self.get_y(), self.w - 20, 0.7, style="F")
            self.set_fill_color(*HE_G)
            self.rect(10, self.get_y() + 0.7, self.w - 20, 0.7, style="F")

            self.set_y(-11)
            self.set_x(10)
            self.set_font(font_family, "", 8)
            self.set_text_color(*HE_MUTED)
            half = (self.w - 20) / 2
            self.cell(half, 4,
                      txt(f"Vystavil: Hluchaň   |   Vygenerované: "
                          f"{datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"),
                      align="L")
            self.cell(half, 4,
                      txt("HANDLOVSKÁ ENERGETIKA, s.r.o.  ·  Štrajková 1, 972 51 Handlová  ·  IČO: 36 314 439"),
                      align="R")

    pdf = HEReportPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(10, 10, 10)

    # Font: DejaVu (plná diakritika) alebo Helvetica (fallback)
    if reg_path and bold_path:
        pdf.add_font("DejaVu", "", reg_path)
        pdf.add_font("DejaVu", "B", bold_path)
        font_family = "DejaVu"
        def txt(s: str) -> str:
            return s
    else:
        font_family = "Helvetica"
        def txt(s: str) -> str:
            return _strip_diacritics(s)

    pdf.add_page()

    # ─── ŽLTÁ HLAVIČKA (brand) + ZELENÝ AKCENT ───────────────────
    pdf.set_fill_color(*HE_Y)
    pdf.rect(0, 0, pdf.w, 16, style="F")

    # Zelený tenký pás pod žltou hlavičkou — mirror webu (inset green)
    pdf.set_fill_color(*HE_G)
    pdf.rect(0, 16, pdf.w, 1.0, style="F")

    # Tenký čierny pruh pod zeleným pásom
    pdf.set_fill_color(*HE_K)
    pdf.rect(0, 17.0, pdf.w, 0.6, style="F")

    # Logo text vľavo
    pdf.set_xy(10, 3.5)
    pdf.set_font(font_family, "B", 15)
    pdf.set_text_color(*HE_K)
    pdf.cell(120, 9, txt("HANDLOVSKÁ ENERGETIKA"), ln=0)
    pdf.set_font(font_family, "", 10)
    pdf.set_xy(10, 8.5)
    pdf.set_text_color(*HE_K)
    pdf.cell(40, 5, "s.r.o.", ln=0)

    # Adresa a IČO vpravo
    pdf.set_xy(pdf.w - 90, 5)
    pdf.set_font(font_family, "", 9)
    pdf.set_text_color(*HE_K)
    pdf.cell(80, 5, txt("Štrajková 1, 972 51 Handlová"), align="R", ln=True)
    pdf.set_xy(pdf.w - 90, 10)
    pdf.cell(80, 4, txt("IČO: 36 314 439"), align="R")

    # ─── TITULOK ─────────────────────────────────────────────────
    pdf.set_xy(0, 21)
    pdf.set_font(font_family, "B", 17)
    pdf.set_text_color(*HE_K)
    pdf.cell(pdf.w, 8, txt("DENNÝ VÝKAZ – KOTOLŇA K6 & K7"), align="C", ln=True)

    # Podtitulok v HE zelenej
    pdf.set_font(font_family, "B", 8.5)
    pdf.set_text_color(*HE_G)
    pdf.cell(pdf.w, 4, txt("PREVÁDZKOVÉ PARAMETRE"), align="C", ln=True)

    # ─── METADATA BLOK ───────────────────────────────────────────
    pdf.ln(2)
    pdf.set_x(10)
    pdf.set_font(font_family, "B", 10)
    pdf.set_text_color(*HE_K)
    pdf.cell(28, 6, txt("Dátum:"), ln=0)
    pdf.set_font(font_family, "", 10)
    pdf.cell(55, 6, date.strftime("%d.%m.%Y"), ln=0)
    pdf.set_font(font_family, "B", 10)
    pdf.cell(28, 6, txt("Prevádzka:"), ln=0)
    pdf.set_font(font_family, "", 10)
    pdf.cell(55, 6, txt("Handlová"), ln=0)
    pdf.set_font(font_family, "B", 10)
    pdf.cell(32, 6, txt("Počet hodín:"), ln=0)
    pdf.set_font(font_family, "", 10)
    n_hours = len(export_df)
    pdf.cell(40, 6, f"{n_hours} / 24", ln=True)

    pdf.ln(2)

    # ─── TABUĽKA ─────────────────────────────────────────────────
    headers = [
        "Hodina", "K6 Výkon (MW)", "K7 Výkon (MW)",
        "Výstupná (°C)", "Vratná (°C)", "Prietok (m³/h)",
        "Spaliny K6 (°C)", "Spaliny K7 (°C)",
    ]
    col_w = [20, 34, 34, 32, 28, 34, 32, 32]
    total_w = sum(col_w)
    start_x = (pdf.w - total_w) / 2  # centrovaná tabuľka

    # Dark header riadok so žltým textom
    pdf.set_x(start_x)
    pdf.set_fill_color(*HE_K)
    pdf.set_text_color(*HE_Y)
    pdf.set_font(font_family, "B", 9)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, txt(h), border=0, align="C", fill=True)
    pdf.ln()

    # Tenký zelený akcent pod hlavičkou tabuľky
    pdf.set_fill_color(*HE_G)
    pdf.rect(start_x, pdf.get_y(), total_w, 0.6, style="F")
    pdf.ln(0.6)

    # Riadky so zebra striping
    pdf.set_text_color(*HE_K)
    pdf.set_font(font_family, "", 9)
    # Dynamická výška riadku podľa počtu hodín (aby sa zmestili všetky)
    if n_hours <= 16:
        row_h_tbl = 5.0
    elif n_hours <= 20:
        row_h_tbl = 4.3
    else:
        row_h_tbl = 4.0
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

    # Nadpis sekcie — so zeleným akcentom vľavo (mirror webu)
    section_y = pdf.get_y()
    pdf.set_fill_color(*HE_G)
    pdf.rect(10, section_y + 0.8, 1.5, 5.5, style="F")
    pdf.set_xy(13, section_y)
    pdf.set_font(font_family, "B", 10)
    pdf.set_text_color(*HE_K)
    pdf.cell(0, 6, txt("SÚHRN ZA DEŇ"), ln=True)

    col_lx = 10
    col_rx = pdf.w / 2 + 5
    row_h = 5.0

    def sum_row(y, label, v_k6, v_k7, unit):
        pdf.set_xy(col_lx, y)
        pdf.set_font(font_family, "", 9)
        pdf.set_text_color(*HE_MUTED)
        pdf.cell(65, row_h, txt(label), ln=0)
        pdf.set_text_color(*HE_K)
        pdf.set_font(font_family, "B", 9)
        pdf.cell(40, row_h, f"{v_k6:.2f} {unit}".replace(".", ","), ln=0)

        pdf.set_xy(col_rx, y)
        pdf.set_font(font_family, "", 9)
        pdf.set_text_color(*HE_MUTED)
        pdf.cell(65, row_h, txt(label), ln=0)
        pdf.set_text_color(*HE_K)
        pdf.set_font(font_family, "B", 9)
        pdf.cell(40, row_h, f"{v_k7:.2f} {unit}".replace(".", ","), ln=True)

    # Hlavičky stĺpcov K6 / K7
    y = pdf.get_y()
    pdf.set_xy(col_lx, y)
    pdf.set_font(font_family, "B", 10)
    pdf.set_text_color(*HE_G)
    pdf.cell(105, row_h + 1, "Kotol K6", ln=0)
    pdf.set_xy(col_rx, y)
    pdf.set_text_color(*K7_BLUE)
    pdf.cell(105, row_h + 1, "Kotol K7", ln=True)

    sum_row(pdf.get_y(), "Produkcia tepla:", prod_k6, prod_k7, "MWh")
    sum_row(pdf.get_y(), "Priemerný výkon:", avg_k6, avg_k7, "MW")
    sum_row(pdf.get_y(), "Maximálny výkon:", max_k6, max_k7, "MW")

    # Hodiny v prevádzke (celé čísla)
    y = pdf.get_y()
    pdf.set_xy(col_lx, y)
    pdf.set_font(font_family, "", 9)
    pdf.set_text_color(*HE_MUTED)
    pdf.cell(65, row_h, txt("Hodín v prevádzke:"), ln=0)
    pdf.set_text_color(*HE_K)
    pdf.set_font(font_family, "B", 9)
    pdf.cell(40, row_h, f"{h_k6} h", ln=0)
    pdf.set_xy(col_rx, y)
    pdf.set_font(font_family, "", 9)
    pdf.set_text_color(*HE_MUTED)
    pdf.cell(65, row_h, txt("Hodín v prevádzke:"), ln=0)
    pdf.set_text_color(*HE_K)
    pdf.set_font(font_family, "B", 9)
    pdf.cell(40, row_h, f"{h_k7} h", ln=True)

    # ─── VEĽKÝ SUMMARY BAR ──────────────────────────────────────
    pdf.ln(2)
    bar_y = pdf.get_y()
    bar_h = 11
    # Čierny bar
    pdf.set_fill_color(*HE_K)
    pdf.rect(10, bar_y, pdf.w - 20, bar_h, style="F")
    # Zelený akcent na ľavej hrane
    pdf.set_fill_color(*HE_G)
    pdf.rect(10, bar_y, 2.2, bar_h, style="F")

    pdf.set_xy(16, bar_y + 2)
    pdf.set_font(font_family, "B", 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(120, 7, txt("PRODUKCIA TEPLA SPOLU:"), ln=0)

    pdf.set_xy(pdf.w - 14 - 100, bar_y + 1.5)
    pdf.set_font(font_family, "B", 15)
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


def render_section(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="he-section-copy">
            <div class="he-section-title">{title}</div>
            <div class="he-section-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
:root {{
    --he-yellow: {HE_YELLOW};
    --he-black: {HE_BLACK};
    --he-surface: {HE_SURFACE};
    --he-surface-alt: {HE_SURFACE_ALT};
    --he-border: {HE_BORDER};
    --he-text-muted: {HE_TEXT_MUTED};
    --he-shadow: 0 16px 38px rgba(17, 17, 17, 0.08);
    --he-radius-lg: 18px;
    --he-radius-md: 12px;
}}

.stApp {{
    background:
        radial-gradient(circle at top left, rgba(240, 220, 0, 0.28), rgba(240, 220, 0, 0) 28%),
        linear-gradient(180deg, #f5efe2 0%, #ece5d5 100%);
}}

[data-testid="stHeader"],
[data-testid="stToolbar"] {{
    background: transparent;
}}

.block-container {{
    max-width: 1260px;
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}}

/* HE hlavička */
.he-header {{
    background: {HE_BLACK};
    padding: 18px 24px;
    border-bottom: 5px solid {HE_YELLOW};
    border-radius: 8px;
    margin-bottom: 1.1rem;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow:
        inset 0 -3px 0 {HE_GREEN},
        0 18px 36px rgba(17, 17, 17, 0.18);
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

/* Nadpisy sekcií */
.he-section-copy {{
    margin: 1.15rem 0 0.85rem;
}}
.he-section-title {{
    color: {HE_BLACK};
    font-size: 1.25rem;
    font-weight: 800;
    letter-spacing: 0.01em;
    position: relative;
    padding-left: 0.85rem;
}}
.he-section-title::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 0.22em;
    bottom: 0.22em;
    width: 4px;
    border-radius: 2px;
    background: {HE_GREEN};
}}
.he-section-subtitle {{
    color: {HE_TEXT_MUTED};
    font-size: 0.95rem;
    margin-top: 0.2rem;
    padding-left: 0.85rem;
}}

/* Malý uppercase label pre ovládače (DEŇ, HODINA...) */
.he-control-label {{
    margin: 0.2rem 0 0.45rem;
    color: {HE_TEXT_MUTED};
    font-size: 0.84rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}}

/* Radio ako pill tlačidlá (pre výber dňa) */
div[data-testid="stRadio"] > label {{
    display: none;
}}
div[role="radiogroup"] {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    margin-bottom: 0.85rem;
}}
div[role="radiogroup"] label[data-baseweb="radio"] {{
    margin: 0;
    border: 1px solid {HE_BORDER};
    border-radius: 999px;
    background: rgba(255, 253, 248, 0.82);
    padding: 0.22rem 0.78rem;
    min-height: auto;
    box-shadow: 0 6px 18px rgba(17, 17, 17, 0.04);
}}
div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child {{
    display: none;
}}
div[role="radiogroup"] label[data-baseweb="radio"] p {{
    margin: 0;
    color: {HE_TEXT_MUTED};
    font-size: 0.95rem;
    font-weight: 600;
}}
div[role="radiogroup"] label[data-baseweb="radio"]:hover {{
    border-color: {HE_GREEN};
}}
div[role="radiogroup"] label[data-baseweb="radio"]:hover p {{
    color: {HE_GREEN};
}}
div[role="radiogroup"] label[data-baseweb="radio"][aria-checked="true"] {{
    background: {HE_BLACK};
    border-color: {HE_BLACK};
}}
div[role="radiogroup"] label[data-baseweb="radio"][aria-checked="true"] p {{
    color: white;
}}

/* Tlačidlá všeobecne (hodinový grid) */
div[data-testid="stButton"] > button {{
    width: 100%;
    background: rgba(255, 253, 248, 0.88);
    border: 1px solid {HE_BORDER};
    color: {HE_BLACK};
    border-radius: 10px;
    min-height: 2.45rem;
    font-weight: 700;
    font-size: 0.92rem;
    box-shadow: none;
}}
div[data-testid="stButton"] > button:hover {{
    border-color: {HE_GREEN};
    color: {HE_GREEN};
}}
div[data-testid="stButton"] > button[kind="primary"] {{
    background: {HE_YELLOW};
    border-color: {HE_YELLOW};
    color: {HE_BLACK};
}}
div[data-testid="stButton"] > button[kind="primary"]:hover {{
    background: #dac900;
    border-color: #dac900;
    color: {HE_BLACK};
}}

/* Download tlačidlá */
div[data-testid="stDownloadButton"] button {{
    width: 100%;
    background: {HE_SURFACE};
    border: 1px solid {HE_BORDER};
    color: {HE_BLACK};
    border-radius: 14px;
    min-height: 3.1rem;
    font-weight: 700;
    box-shadow: var(--he-shadow);
}}
div[data-testid="stDownloadButton"] button:hover {{
    border-color: {HE_GREEN};
    color: {HE_GREEN};
}}

/* Päta */
.he-footer {{
    margin-top: 30px;
    padding: 12px 18px;
    background: {HE_BLACK};
    color: #cfcfcf;
    font-size: 11px;
    border-top: 3px solid {HE_YELLOW};
    box-shadow: inset 0 3px 0 {HE_GREEN};
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
        <rect x="24" y="12" width="8" height="34" fill="{HE_GREEN}"/>
        <rect x="34" y="24" width="8" height="22" fill="{HE_YELLOW}"/>
        <!-- dym / para -->
        <circle cx="28" cy="8"  r="2"   fill="{HE_YELLOW}" opacity="0.7"/>
        <circle cx="32" cy="4"  r="1.5" fill="{HE_YELLOW}" opacity="0.5"/>
        <circle cx="18" cy="18" r="1.5" fill="{HE_GREEN}" opacity="0.7"/>
    </svg>
    <div class="he-text-block">
        <div class="he-company">HANDLOVSKÁ ENERGETIKA<span class="he-company-suffix">s.r.o.</span></div>
        <div class="he-subtitle">Prevádzkové parametre · Kotolňa K6 & K7</div>
    </div>
</div>
""", unsafe_allow_html=True)

today = datetime.date.today()
day_labels = [
    f"Dnes ({today.strftime('%d.%m.%Y')})",
    f"Včera ({(today - datetime.timedelta(days=1)).strftime('%d.%m.%Y')})",
    f"Predvčerom ({(today - datetime.timedelta(days=2)).strftime('%d.%m.%Y')})",
]
day_dates = [today, today - datetime.timedelta(days=1), today - datetime.timedelta(days=2)]

render_section(
    "Výber obdobia",
    "Vyber deň a hodinu, ktorú chceš porovnať. Horná časť dashboardu kopíruje rýchly prehľad z referenčného návrhu."
)

st.markdown('<div class="he-control-label">Deň</div>', unsafe_allow_html=True)
sel_label = st.radio(
    "Deň",
    day_labels,
    horizontal=True,
    label_visibility="collapsed",
)
sel_date = day_dates[day_labels.index(sel_label)]

now_h = min(datetime.datetime.now().hour + 1, 24)   # aktuálna hodina (1-based)
max_h = now_h if sel_date == today else 24

# ── VÝBER HODINY (mriežka tlačidiel 12 × 2) ─────────────────────

if st.session_state.get("last_sel_date") != sel_date:
    st.session_state.selected_hour = min(now_h, max_h)
    st.session_state.last_sel_date = sel_date

if st.session_state.get("selected_hour", 1) > max_h:
    st.session_state.selected_hour = max_h

st.markdown(
    f'<div class="he-control-label">Hodina: {st.session_state.selected_hour:02d}:00</div>',
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
    _k6_on = vals["k6_vykon"] > 0.05
    _k6_status_txt = "● V PREVÁDZKE" if _k6_on else "○ ODSTAVENÝ"
    _k6_status_col = K6_COLOR if _k6_on else "#999"
    st.markdown(f"""
    <div style="background: linear-gradient(to right, rgba(40,160,40,0.16), rgba(40,160,40,0.02));
                border-left: 6px solid {K6_COLOR};
                padding: 11px 18px; margin-bottom: 10px; border-radius: 4px;
                display: flex; align-items: center; justify-content: space-between;">
        <div style="font-size: 20px; font-weight: 800; color: {K6_COLOR}; letter-spacing: 0.8px;">
            KOTOL K6
        </div>
        <div style="font-size: 11px; color: {_k6_status_col}; font-weight: 700; letter-spacing: 0.6px;">
            {_k6_status_txt}
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.plotly_chart(make_gauge(vals["k6_vykon"], "Výkon K6", K6_COLOR),
                    width='stretch')
    sym, col = tr("k6_vykon", 0.05)
    if sym:
        st.markdown(
            f'<div style="text-align:center;font-size:28px;color:{col};margin-top:-10px;">{sym}</div>',
            unsafe_allow_html=True)

with gc7:
    _k7_on = vals["k7_vykon"] > 0.05
    _k7_status_txt = "● V PREVÁDZKE" if _k7_on else "○ ODSTAVENÝ"
    _k7_status_col = K7_COLOR if _k7_on else "#999"
    st.markdown(f"""
    <div style="background: linear-gradient(to right, rgba(41,128,185,0.16), rgba(41,128,185,0.02));
                border-left: 6px solid {K7_COLOR};
                padding: 11px 18px; margin-bottom: 10px; border-radius: 4px;
                display: flex; align-items: center; justify-content: space-between;">
        <div style="font-size: 20px; font-weight: 800; color: {K7_COLOR}; letter-spacing: 0.8px;">
            KOTOL K7
        </div>
        <div style="font-size: 11px; color: {_k7_status_col}; font-weight: 700; letter-spacing: 0.6px;">
            {_k7_status_txt}
        </div>
    </div>
    """, unsafe_allow_html=True)
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
render_section(
    "Denný trend",
    "Priebeh výkonu a teplôt za zvolený deň."
)

day_df = get_day_df(df, sel_date.day, max_h)

t1, t2 = st.columns(2)
with t1:
    st.plotly_chart(make_vykon_chart(day_df), use_container_width=True)
with t2:
    st.plotly_chart(make_teploty_chart(day_df), use_container_width=True)

# ── EXPORT CSV / PDF ────────────────────────────────────────────
render_section(
    "Reporty a servis",
    "Stiahni denný výkaz alebo obnov dáta z Google Sheets."
)

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
if st.button("♻️ Obnoviť dáta", type="secondary"):
    st.cache_data.clear()
    st.rerun()

# ── PÄTA ────────────────────────────────────────────────────────
st.markdown(f"""
<div class="he-footer">
    <b>HANDLOVSKÁ ENERGETIKA, s.r.o.</b> · Štrajková 1, 972 51 Handlová · IČO: 36 314 439
</div>
""", unsafe_allow_html=True)
