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
HE_ORANGE = "#D97A1F"
HE_PURPLE = "#7257A8"
HE_TEAL   = "#1D8B76"

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


def _find_unicode_ttf_pair() -> tuple[str | None, str | None]:
    """Najdi regular+bold Unicode TTF font vhodny pre slovensku diakritiku."""
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

    font_candidates = [
        ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf"),
        ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
        ("Arial.ttf", "Arialbd.ttf"),
    ]

    for d in search_dirs:
        for regular_name, bold_name in font_candidates:
            try:
                reg = d / regular_name
                bold = d / bold_name
                if reg.exists() and bold.exists():
                    return str(reg), str(bold)
            except Exception:
                continue
    return None, None


def _add_ttf_font_compat(pdf: FPDF, family: str, style: str, path: str) -> None:
    """pyfpdf vyzaduje `uni=True`, fpdf2 parameter ignoruje."""
    try:
        pdf.add_font(family, style, path, uni=True)
    except TypeError:
        pdf.add_font(family, style, path)


def generate_pdf(export_df: pd.DataFrame, date: datetime.date) -> bytes:
    """Vizuálne vylepšený HE PDF report: výrazná brand hlavička,
    čitateľná tabuľka a prehľadnejší súhrn K6/K7."""

    HE_Y = (240, 220, 0)
    HE_K = (17, 17, 17)
    HE_G = (40, 160, 40)
    K7_ACCENT = HE_Y
    HE_BG = (250, 246, 236)
    HE_CARD = (255, 255, 255)
    HE_LINE = (216, 208, 189)
    HE_TEXT = (70, 66, 58)
    HE_MUTED = (112, 104, 91)
    HE_ZEBRA = (247, 242, 229)
    K6_SOFT = (236, 248, 236)
    K7_SOFT = (255, 250, 224)

    reg_path, bold_path = _find_unicode_ttf_pair()

    class HEReportPDF(FPDF):
        def footer(self):
            self.set_y(-12.5)
            self.set_draw_color(*HE_LINE)
            self.set_line_width(0.2)
            self.line(10, self.get_y(), self.w - 10, self.get_y())

            self.set_fill_color(*HE_Y)
            self.rect(10, self.h - 7.3, self.w - 20, 0.8, style="F")
            self.set_fill_color(*HE_G)
            self.rect(10, self.h - 6.5, self.w - 20, 0.5, style="F")

            self.set_y(-10.0)
            self.set_font(font_family, "", 7.5)
            self.set_text_color(*HE_MUTED)
            self.cell(
                self.w - 40,
                4,
                txt(
                    f"Vystavil: Hluchan | Vygenerované: "
                    f"{datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
                ),
                align="L",
            )
            self.set_xy(self.w - 30, self.h - 10.0)
            self.cell(20, 4, txt(f"Strana {self.page_no()}"), align="R")

    pdf = HEReportPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(10, 10, 10)

    if not (reg_path and bold_path):
        raise RuntimeError(
            "Nenašiel sa Unicode font pre PDF (DejaVu/Noto/Liberation). "
            "Pridaj TTF fonty do priečinka 'fonts' vedľa appky."
        )

    _add_ttf_font_compat(pdf, "HEUnicode", "", reg_path)
    _add_ttf_font_compat(pdf, "HEUnicode", "B", bold_path)
    font_family = "HEUnicode"

    def txt(s: str) -> str:
        return s

    def fmt_num(v: float, decimals: int = 2) -> str:
        return f"{v:.{decimals}f}".replace(".", ",")

    def draw_logo_mark(x: float, y: float) -> None:
        bar_w = 2.8
        gap = 1.15
        bars = [7.5, 10.5, 14.5, 9.5]
        colors = [HE_Y, HE_Y, HE_G, HE_Y]
        baseline = y + 14.8
        for idx, h in enumerate(bars):
            pdf.set_fill_color(*colors[idx])
            pdf.rect(x + idx * (bar_w + gap), baseline - h, bar_w, h, style="F")
        pdf.set_fill_color(*HE_Y)
        pdf.rect(x + 10.8, y + 1.6, 0.9, 0.9, style="F")
        pdf.rect(x + 12.2, y + 0.6, 0.65, 0.65, style="F")
        pdf.set_fill_color(*HE_G)
        pdf.rect(x + 6.7, y + 3.0, 0.8, 0.8, style="F")

    pdf.add_page()
    pdf.set_fill_color(*HE_BG)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")

    # Header panel
    header_x = 10
    header_y = 8
    header_w = pdf.w - 20
    header_h = 22

    pdf.set_fill_color(*HE_K)
    pdf.rect(header_x, header_y, header_w, header_h, style="F")
    pdf.set_fill_color(*HE_Y)
    pdf.rect(header_x, header_y + header_h - 1.2, header_w, 0.8, style="F")
    pdf.set_fill_color(*HE_G)
    pdf.rect(header_x, header_y + header_h - 0.4, header_w, 0.5, style="F")

    draw_logo_mark(header_x + 4.5, header_y + 2.7)

    pdf.set_xy(header_x + 18, header_y + 3.8)
    pdf.set_font(font_family, "B", 14)
    pdf.set_text_color(*HE_Y)
    pdf.cell(125, 6, txt("HANDLOVSKÁ ENERGETIKA"), ln=0)
    pdf.set_xy(header_x + 18, header_y + 10.2)
    pdf.set_font(font_family, "", 8.2)
    pdf.set_text_color(226, 226, 226)
    pdf.cell(140, 4.2, txt("PREVÁDZKOVÉ PARAMETRE - KOTOLŇA K6 & K7"), ln=0)

    pdf.set_xy(header_x + header_w - 84, header_y + 3.8)
    pdf.set_font(font_family, "", 8.0)
    pdf.set_text_color(220, 220, 220)
    pdf.cell(78, 4.0, txt("Štrajková 1, 972 51 Cigeľ"), align="R", ln=True)
    pdf.set_xy(header_x + header_w - 84, header_y + 8.8)
    pdf.cell(78, 4.0, txt("IČO: 36 314 439"), align="R", ln=True)
    pdf.set_xy(header_x + header_w - 84, header_y + 13.8)
    pdf.cell(78, 4.0, txt(f"Dátum reportu: {date.strftime('%d.%m.%Y')}"), align="R")

    # Title + compact meta cards
    pdf.set_xy(10, header_y + header_h + 2.3)
    pdf.set_font(font_family, "B", 13.5)
    pdf.set_text_color(*HE_K)
    pdf.cell(0, 6.2, txt("DENNÝ REPORT - KOTOLŇA K6 & K7"), ln=True)

    n_hours = len(export_df)
    chip_y = pdf.get_y() + 0.7
    chip_gap = 4
    chip_w = (pdf.w - 20 - 2 * chip_gap) / 3
    chip_h = 7.2
    chips = [
        ("Dátum", date.strftime("%d.%m.%Y"), HE_G),
        ("Prevádzka", "Cigeľ", K7_ACCENT),
        ("Pokrytie dát", f"{n_hours}/24 hodín", HE_Y),
    ]
    for idx, (label, value, accent) in enumerate(chips):
        x = 10 + idx * (chip_w + chip_gap)
        pdf.set_draw_color(*HE_LINE)
        pdf.set_fill_color(*HE_CARD)
        pdf.rect(x, chip_y, chip_w, chip_h, style="DF")
        pdf.set_fill_color(*accent)
        pdf.rect(x, chip_y, chip_w, 0.9, style="F")
        pdf.set_xy(x + 2.3, chip_y + 1.45)
        pdf.set_font(font_family, "", 7.2)
        pdf.set_text_color(*HE_MUTED)
        pdf.cell(24, 3.0, txt(label), ln=0)
        pdf.set_font(font_family, "B", 8.2)
        pdf.set_text_color(*HE_TEXT)
        pdf.cell(chip_w - 28, 3.0, txt(value), align="R")

    # Data table
    table_title_y = chip_y + chip_h + 2.6
    pdf.set_fill_color(*HE_G)
    pdf.rect(10, table_title_y + 0.9, 1.7, 5.0, style="F")
    pdf.set_xy(13, table_title_y)
    pdf.set_font(font_family, "B", 10.5)
    pdf.set_text_color(*HE_K)
    pdf.cell(0, 6.0, txt("HODINOVÉ MERANIA"), ln=True)

    headers = [
        "Hod", "K6 MW", "K7 MW",
        "Výstup (°C)", "Vratná (°C)", "Prietok (m³/h)",
        "Spaliny K6 (°C)", "Spaliny K7 (°C)",
    ]
    col_w = [18, 31, 31, 31, 31, 36, 49, 50]  # total 277 mm
    start_x = 10

    header_styles = [
        (HE_K, HE_Y),
        (HE_G, (255, 255, 255)),
        (K7_ACCENT, HE_K),
        (HE_K, (255, 255, 255)),
        (HE_K, (255, 255, 255)),
        (HE_K, (255, 255, 255)),
        (HE_G, (255, 255, 255)),
        (K7_ACCENT, HE_K),
    ]

    pdf.set_x(start_x)
    pdf.set_font(font_family, "B", 8.3)
    pdf.set_line_width(0.2)
    for i, head in enumerate(headers):
        bg, fg = header_styles[i]
        pdf.set_fill_color(*bg)
        pdf.set_text_color(*fg)
        pdf.cell(col_w[i], 6.5, txt(head), border=0, align="C", fill=True)
    pdf.ln()

    pdf.set_fill_color(*HE_G)
    pdf.rect(start_x, pdf.get_y(), sum(col_w), 0.6, style="F")
    pdf.ln(0.8)

    if n_hours <= 16:
        row_h_tbl = 4.9
    elif n_hours <= 20:
        row_h_tbl = 4.3
    else:
        row_h_tbl = 3.9

    pdf.set_font(font_family, "", 8.2)
    pdf.set_draw_color(*HE_LINE)
    for idx, (_, row) in enumerate(export_df.iterrows()):
        pdf.set_x(start_x)
        row_base = HE_CARD if idx % 2 == 0 else HE_ZEBRA
        values = list(row)
        for i, val in enumerate(values):
            if i in (1, 6):
                fill_color = K6_SOFT if idx % 2 == 0 else HE_ZEBRA
            elif i in (2, 7):
                fill_color = K7_SOFT if idx % 2 == 0 else HE_ZEBRA
            else:
                fill_color = row_base

            if i == 0:
                try:
                    text = f"{int(float(val)):02d}"
                except Exception:
                    text = str(val)
                align = "C"
            else:
                try:
                    text = fmt_num(float(val), 2)
                except Exception:
                    text = str(val)
                align = "R"

            pdf.set_fill_color(*fill_color)
            pdf.set_text_color(*HE_TEXT)
            pdf.cell(col_w[i], row_h_tbl, txt(text), border=1, align=align, fill=True)
        pdf.ln()

    def safe_avg(series):
        nz = series[series > 0]
        return float(nz.mean()) if len(nz) > 0 else 0.0

    def hours_running(series):
        return int((series > 0).sum())

    # Použi indexy stĺpcov pre istotu (nezávisle od kódovania diakritiky).
    k6_ser = export_df.iloc[:, 1]
    k7_ser = export_df.iloc[:, 2]

    prod_k6 = float(k6_ser.sum())
    prod_k7 = float(k7_ser.sum())
    prod_total = prod_k6 + prod_k7
    avg_k6 = safe_avg(k6_ser)
    avg_k7 = safe_avg(k7_ser)
    max_k6 = float(k6_ser.max())
    max_k7 = float(k7_ser.max())
    h_k6 = hours_running(k6_ser)
    h_k7 = hours_running(k7_ser)

    if pdf.get_y() + 40 > pdf.h - 20:
        pdf.add_page()
        pdf.set_fill_color(*HE_BG)
        pdf.rect(0, 0, pdf.w, pdf.h, style="F")
        pdf.set_xy(10, 12)

    pdf.ln(2.4)
    section_y = pdf.get_y()
    pdf.set_fill_color(*HE_G)
    pdf.rect(10, section_y + 0.9, 1.7, 5.0, style="F")
    pdf.set_xy(13, section_y)
    pdf.set_font(font_family, "B", 10.5)
    pdf.set_text_color(*HE_K)
    pdf.cell(0, 6.0, txt("PREVÁDZKOVÝ SÚHRN"), ln=True)

    card_y = pdf.get_y() + 0.6
    card_gap = 6
    card_w = (pdf.w - 20 - card_gap) / 2
    card_h = 23.5

    def draw_summary_card(
        x: float,
        title: str,
        accent: tuple[int, int, int],
        bg: tuple[int, int, int],
        values: list[tuple[str, str]],
        title_color: tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        pdf.set_draw_color(*HE_LINE)
        pdf.set_fill_color(*bg)
        pdf.rect(x, card_y, card_w, card_h, style="DF")
        pdf.set_fill_color(*accent)
        pdf.rect(x, card_y, card_w, 4.8, style="F")

        pdf.set_xy(x + 3, card_y + 1.0)
        pdf.set_font(font_family, "B", 9)
        pdf.set_text_color(*title_color)
        pdf.cell(card_w - 6, 3.2, txt(title), align="L")

        y = card_y + 6.5
        for label, val in values:
            pdf.set_xy(x + 3, y)
            pdf.set_font(font_family, "", 8.1)
            pdf.set_text_color(*HE_MUTED)
            pdf.cell(card_w * 0.58, 3.8, txt(label), align="L")
            pdf.set_font(font_family, "B", 8.6)
            pdf.set_text_color(*HE_TEXT)
            pdf.cell(card_w * 0.37, 3.8, txt(val), align="R")
            y += 4.1

    draw_summary_card(
        10,
        "KOTOL K6",
        HE_G,
        K6_SOFT,
        [
            ("Produkcia tepla", f"{fmt_num(prod_k6)} MWh"),
            ("Priemerný výkon", f"{fmt_num(avg_k6)} MW"),
            ("Maximálny výkon", f"{fmt_num(max_k6)} MW"),
            ("Hodín v prevádzke", f"{h_k6} h"),
        ],
    )
    draw_summary_card(
        10 + card_w + card_gap,
        "KOTOL K7",
        K7_ACCENT,
        K7_SOFT,
        [
            ("Produkcia tepla", f"{fmt_num(prod_k7)} MWh"),
            ("Priemerný výkon", f"{fmt_num(avg_k7)} MW"),
            ("Maximálny výkon", f"{fmt_num(max_k7)} MW"),
            ("Hodín v prevádzke", f"{h_k7} h"),
        ],
        title_color=HE_K,
    )

    bar_y = card_y + card_h + 3.2
    bar_h = 10.5
    pdf.set_fill_color(*HE_K)
    pdf.rect(10, bar_y, pdf.w - 20, bar_h, style="F")
    pdf.set_fill_color(*HE_Y)
    pdf.rect(10, bar_y, 2.0, bar_h, style="F")
    pdf.set_fill_color(*HE_G)
    pdf.rect(12.0, bar_y, 1.2, bar_h, style="F")

    pdf.set_xy(16, bar_y + 2.1)
    pdf.set_font(font_family, "B", 11.8)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(130, 6.0, txt("CELKOVÁ PRODUKCIA TEPLA"), ln=0)

    pdf.set_xy(pdf.w - 112, bar_y + 1.4)
    pdf.set_font(font_family, "B", 15.5)
    pdf.set_text_color(*HE_Y)
    pdf.cell(100, 7.2, txt(f"{fmt_num(prod_total)} MWh"), align="R")

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


def format_value(value: float, unit: str = "", decimals: int = 2,
                 zero_as_dash: bool = False) -> str:
    if zero_as_dash and value == 0.0:
        return "—"
    rendered = f"{value:.{decimals}f}".replace(".", ",")
    return f"{rendered} {unit}".strip()


def trend_badge(trend: tuple[str, str] | None) -> str:
    if not trend or not trend[0]:
        return '<span class="he-trend-note">bez porovnania</span>'

    arrow = trend[0]
    color = trend[1]
    return (
        f'<span class="he-trend-badge" '
        f'style="color:{color};border-color:{color}33;background:{color}12;">'
        f'{arrow}</span>'
    )


def render_stat_card(label: str, value: float, unit: str, color: str,
                     helper: str, trend: tuple[str, str] | None = None,
                     decimals: int = 1, zero_as_dash: bool = True) -> None:
    st.markdown(
        f"""
        <div class="he-stat-card" style="border-top: 4px solid {color};">
            <div class="he-stat-top">
                <div class="he-stat-label">{label}</div>
                {trend_badge(trend)}
            </div>
            <div class="he-stat-value">{format_value(value, unit, decimals, zero_as_dash)}</div>
            <div class="he-stat-helper">{helper}</div>
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

/* Stat karty (CELKOVÝ VÝKON / VÝSTUPNÁ / VRATNÁ / PRIETOK / SPALINY K6 / K7) */
.he-stat-card {{
    background: {HE_SURFACE};
    border: 1px solid {HE_BORDER};
    border-radius: var(--he-radius-lg);
    box-shadow: var(--he-shadow);
    padding: 0.95rem 1rem;
    min-height: 142px;
    margin-bottom: 0.9rem;
}}
.he-stat-top {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.8rem;
}}
.he-stat-label {{
    color: {HE_TEXT_MUTED};
    font-size: 0.84rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
}}
.he-stat-value {{
    color: {HE_BLACK};
    font-size: 1.72rem;
    font-weight: 800;
    margin-top: 0.95rem;
    line-height: 1.1;
}}
.he-stat-helper {{
    color: {HE_TEXT_MUTED};
    font-size: 0.9rem;
    margin-top: 0.65rem;
}}
.he-trend-badge,
.he-trend-note {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    padding: 0.28rem 0.6rem;
    font-size: 0.75rem;
    font-weight: 700;
    white-space: nowrap;
}}
.he-trend-note {{
    background: {HE_SURFACE_ALT};
    color: {HE_TEXT_MUTED};
    border: 1px solid {HE_BORDER};
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
    "Vyberte deň a hodinu, ktorú chcete porovnať."
)

st.markdown('<div class="he-control-label">Deň</div>', unsafe_allow_html=True)
day_lookup = dict(zip(day_labels, day_dates))
if st.session_state.get("selected_day_label") not in day_lookup:
    st.session_state.selected_day_label = day_labels[0]

day_cols = st.columns(len(day_labels), gap="small")
for idx, label in enumerate(day_labels):
    is_active_day = (label == st.session_state.selected_day_label)
    if day_cols[idx].button(
        label,
        key=f"day_btn_{idx}",
        type="primary" if is_active_day else "secondary",
        use_container_width=True,
    ):
        st.session_state.selected_day_label = label
        st.rerun()

sel_label = st.session_state.selected_day_label
sel_date = day_lookup[sel_label]

now_dt = datetime.datetime.now()
now_h = now_dt.hour
max_h = now_h if sel_date == today else 24

if sel_date == today and max_h < 1:
    st.info("Dnes este nie je uzavreta ziadna hodina. Prva bude dostupna po 01:00:00.")
    st.stop()

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

# ── PREHĽADOVÉ KARTY (3 × 2 mriežka) ────────────────────────────
total_output = vals["k6_vykon"] + vals["k7_vykon"]

stat_a, stat_b, stat_c = st.columns(3, gap="large")
with stat_a:
    render_stat_card(
        "Celkový výkon",
        total_output,
        "MW",
        HE_BLACK,
        "Súčet výkonu oboch kotlov.",
        decimals=2,
        zero_as_dash=False,
    )
with stat_b:
    render_stat_card(
        "Výstupná teplota",
        vals["vystup"],
        "°C",
        HE_ORANGE,
        "Priemer aktívnych kotlov.",
        tr("vystup", 0.5),
    )
with stat_c:
    render_stat_card(
        "Vratná teplota",
        vals["vratna"],
        "°C",
        HE_PURPLE,
        "Návratová voda do systému.",
        tr("vratna", 0.5),
    )

stat_d, stat_e, stat_f = st.columns(3, gap="large")
with stat_d:
    render_stat_card(
        "Priemerný prietok",
        vals["prietok"],
        "m³/h",
        HE_TEAL,
        "Priemer prietoku bežiacich kotlov.",
        tr("prietok", 0.5),
    )
with stat_e:
    render_stat_card(
        "Spaliny K6",
        vals["k6_spaliny"],
        "°C",
        K6_COLOR,
        "Aktuálna teplota spalín kotla K6.",
        tr("k6_spaliny", 0.5),
    )
with stat_f:
    render_stat_card(
        "Spaliny K7",
        vals["k7_spaliny"],
        "°C",
        K7_COLOR,
        "Aktuálna teplota spalín kotla K7.",
        tr("k7_spaliny", 0.5),
    )

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
    "Reporty",
    "Stiahnite si denný výkaz alebo obnovte dáta z databázy."
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
    try:
        pdf_bytes = generate_pdf(export_df, sel_date)
        st.download_button(
            label="💾 Stiahnuť denný report (PDF)",
            data=pdf_bytes,
            file_name=f"kotolna_{sel_date.strftime('%Y-%m-%d')}.pdf",
            mime="application/pdf",
        )
    except Exception as e:
        st.error(f"PDF report sa nepodarilo vytvorit: {e}")

# ── REFRESH ─────────────────────────────────────────────────────
st.markdown("")
if st.button("♻️ Obnoviť dáta", type="secondary"):
    st.cache_data.clear()
    st.rerun()

# ── PÄTA ────────────────────────────────────────────────────────
st.markdown(f"""
<div class="he-footer">
    <b>HANDLOVSKÁ ENERGETIKA, s.r.o.</b> · Štrajková 1, 972 51 Cigeľ · IČO: 36 314 439
</div>
""", unsafe_allow_html=True)
