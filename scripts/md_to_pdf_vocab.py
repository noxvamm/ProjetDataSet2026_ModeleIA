# -*- coding: utf-8 -*-
"""Convertit Fiche_technique_vocabulaire.md en PDF (reportlab)."""
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "Fiche_technique_vocabulaire.md"
OUT = ROOT / "Fiche_technique_vocabulaire.pdf"

# Polices Windows avec support Unicode (fleches, etc.)
FONTS = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("Arial", str(FONTS / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Bold", str(FONTS / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Italic", str(FONTS / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Arial-BoldItalic", str(FONTS / "arialbi.ttf")))
pdfmetrics.registerFont(TTFont("Consolas", str(FONTS / "consola.ttf")))
pdfmetrics.registerFontFamily(
    "Arial", normal="Arial", bold="Arial-Bold",
    italic="Arial-Italic", boldItalic="Arial-BoldItalic",
)

ACCENT = colors.HexColor("#1a5276")

st_title = ParagraphStyle("title", fontName="Arial-Bold", fontSize=17,
                          leading=21, textColor=ACCENT, spaceAfter=4)
st_intro = ParagraphStyle("intro", fontName="Arial-Italic", fontSize=9,
                          leading=12.5, textColor=colors.HexColor("#555555"),
                          leftIndent=6, spaceAfter=10,
                          borderPadding=(4, 6, 4, 6))
st_h2 = ParagraphStyle("h2", fontName="Arial-Bold", fontSize=12.5,
                       leading=15, textColor=ACCENT,
                       spaceBefore=12, spaceAfter=5, keepWithNext=1)
st_li = ParagraphStyle("li", fontName="Arial", fontSize=9.3, leading=12.6,
                       leftIndent=12, bulletIndent=2, spaceAfter=2.2)
st_cell = ParagraphStyle("cell", fontName="Arial", fontSize=9, leading=11.5)
st_cell_b = ParagraphStyle("cellb", parent=st_cell, fontName="Arial-Bold",
                           textColor=colors.white)


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(t):
    """Markdown inline -> balises reportlab."""
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+?)`", r'<font face="Consolas" size="8.6">\1</font>', t)
    t = t.replace("→", '<font color="#1a5276"><b>→</b></font>')
    return t


def build():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    story, i = [], 0
    intro_buf = []
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            story.append(Paragraph(inline(ln[2:]), st_title))
            story.append(HRFlowable(width="100%", thickness=1.2,
                                    color=ACCENT, spaceAfter=8))
        elif ln.startswith("> "):
            intro_buf.append(ln[2:].strip())
        elif ln.startswith("## "):
            if intro_buf:
                story.append(Paragraph(inline(" ".join(intro_buf)), st_intro))
                intro_buf = []
            story.append(Paragraph(inline(ln[3:]), st_h2))
        elif ln.startswith("- "):
            story.append(Paragraph(inline(ln[2:]), st_li,
                                   bulletText="•"))
        elif ln.startswith("|"):
            if intro_buf:
                story.append(Paragraph(inline(" ".join(intro_buf)), st_intro))
                intro_buf = []
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            i -= 1
            data = [[Paragraph(inline(c), st_cell_b) for c in rows[0]]]
            for r in rows[1:]:
                data.append([Paragraph(inline(c), st_cell) for c in r])
            tbl = Table(data, colWidths=[28 * mm, 95 * mm, 38 * mm],
                        repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#eef3f7")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0bec5")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]))
            story.append(Spacer(1, 3))
            story.append(tbl)
        i += 1
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 7.5)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(18 * mm, 10 * mm,
                      "Fiche technique — Vocabulaire du projet · BTS CIEL 2026 · Noa Orand")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(
    str(OUT), pagesize=A4,
    leftMargin=18 * mm, rightMargin=18 * mm,
    topMargin=16 * mm, bottomMargin=16 * mm,
    title="Fiche technique — Vocabulaire du projet",
    author="Noa Orand",
)
doc.build(build(), onFirstPage=footer, onLaterPages=footer)
print(f"OK -> {OUT}")
