"""Generate A4 landscape PDF schedule with Greek month grid (Sun-Sat)."""
import io
from datetime import date
from calendar import monthrange

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm

from holidays_gr import holiday_name, is_holiday

# Register DejaVu Sans (Greek-capable Unicode font)
DEJAVU_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
try:
    pdfmetrics.registerFont(TTFont("DejaVu", DEJAVU_REGULAR))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", DEJAVU_BOLD))
except Exception:
    pass

GREEK_MONTHS = [
    "", "Ιανουάριος", "Φεβρουάριος", "Μάρτιος", "Απρίλιος", "Μάιος", "Ιούνιος",
    "Ιούλιος", "Αύγουστος", "Σεπτέμβριος", "Οκτώβριος", "Νοέμβριος", "Δεκέμβριος",
]
# Sun=0..Sat=6
GREEK_DAY_NAMES = ["Κυριακή", "Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο"]


def build_schedule_pdf(
    year: int,
    month: int,
    day_definitions: list[dict],  # [{date, type}]
    shifts: list[dict],  # [{date, doctors:[ids]}]
    doctors: list[dict],
) -> bytes:
    """Return PDF bytes for the schedule."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    doc_map = {d["id"]: d["full_name"] for d in doctors}
    type_map = {d["date"]: d["type"] for d in day_definitions}
    shift_map = {s["date"]: s["doctors"] for s in shifts}

    # Build calendar grid: rows of weeks, columns Sun..Sat
    n_days = monthrange(year, month)[1]
    first_day = date(year, month, 1)
    # In python weekday(): Mon=0..Sun=6. We want Sun=0..Sat=6
    def week_col(d: date) -> int:
        return (d.weekday() + 1) % 7

    leading = week_col(first_day)
    weeks: list[list] = [[None] * 7]
    for d_num in range(1, n_days + 1):
        d = date(year, month, d_num)
        col = week_col(d)
        if col == 0 and d_num != 1:
            weeks.append([None] * 7)
        weeks[-1][col] = d
    # pad first week
    if leading > 0:
        weeks[0] = [None] * leading + weeks[0][leading:]

    # Header row: Greek day names
    header = GREEK_DAY_NAMES[:]
    table_data = [header]

    cell_styles = []  # collect (row, col, color)

    weekend_red = colors.HexColor("#FEE2E2")
    holiday_yellow = colors.HexColor("#FEF3C7")
    open_blue = colors.HexColor("#DBEAFE")

    for w_idx, wk in enumerate(weeks, start=1):
        row = []
        for c_idx, d in enumerate(wk):
            if d is None:
                row.append("")
                continue
            iso = d.isoformat()
            t = type_map.get(iso, "")
            doctors_ids = shift_map.get(iso, [])
            doc_names = "\n".join(doc_map.get(i, "?") for i in doctors_ids)
            label_type = ""
            if t == "open":
                label_type = "Α"  # Ανοιχτή - ΠΑΓΝΗ
            elif t == "closed":
                label_type = "Κ"  # Κλειστή - ΒΕΝΙΖΕΛΕΙΟ
            hname = holiday_name(d)
            top_line = f"{d.day}"
            if label_type:
                top_line += f"  [{label_type}]"
            cell_text = top_line
            if hname:
                cell_text += f"\n*{hname[:20]}*"
            if doc_names:
                cell_text += f"\n{doc_names}"
            row.append(cell_text)

            # Determine bg color
            if is_holiday(d):
                cell_styles.append(("BACKGROUND", (c_idx, w_idx), (c_idx, w_idx), holiday_yellow))
            elif d.weekday() >= 5:
                cell_styles.append(("BACKGROUND", (c_idx, w_idx), (c_idx, w_idx), weekend_red))
            elif t == "open":
                cell_styles.append(("BACKGROUND", (c_idx, w_idx), (c_idx, w_idx), open_blue))
        table_data.append(row)

    # Determine column widths to use full page
    available = landscape(A4)[0] - 20 * mm
    col_w = available / 7
    row_h = (landscape(A4)[1] - 50 * mm) / max(1, len(weeks))

    table = Table(
        table_data,
        colWidths=[col_w] * 7,
        rowHeights=[10 * mm] + [row_h] * len(weeks),
    )
    style = TableStyle(
        [
            ("FONT", (0, 0), (-1, 0), "DejaVu-Bold", 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONT", (0, 1), (-1, -1), "DejaVu", 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        + cell_styles
    )
    table.setStyle(style)

    title_style = ParagraphStyle(
        name="Title",
        fontName="DejaVu-Bold",
        fontSize=18,
        textColor=colors.HexColor("#0A0D0A"),
        alignment=1,
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        name="Sub",
        fontName="DejaVu",
        fontSize=10,
        textColor=colors.HexColor("#4B5563"),
        alignment=1,
        spaceAfter=8,
    )
    legend_style = ParagraphStyle(
        name="Legend",
        fontName="DejaVu",
        fontSize=8,
        textColor=colors.HexColor("#4B5563"),
        alignment=1,
        spaceBefore=8,
    )

    elements = [
        Paragraph(f"Πρόγραμμα Εφημεριών — {GREEK_MONTHS[month]} {year}", title_style),
        Paragraph("ΠΑΓΝΗ (Ανοιχτή) / ΒΕΝΙΖΕΛΕΙΟ (Κλειστή)", sub_style),
        table,
        Spacer(1, 4 * mm),
        Paragraph(
            "[Α] = Ανοιχτή Εφημερία (ΠΑΓΝΗ) — 2 γιατροί &nbsp;&nbsp;|&nbsp;&nbsp; "
            "[Κ] = Κλειστή Εφημερία (ΒΕΝΙΖΕΛΕΙΟ) — 1 γιατρός &nbsp;&nbsp;|&nbsp;&nbsp; "
            "Κίτρινο = Αργία &nbsp;&nbsp;|&nbsp;&nbsp; Κόκκινο = Σ/Κ",
            legend_style,
        ),
    ]
    doc.build(elements)
    return buffer.getvalue()
