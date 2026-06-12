# -*- coding: utf-8 -*-
"""Convertit Texte_soutenance_Noa.md en PDF (reportlab)."""
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "Texte_soutenance_Noa.md"
OUT = ROOT / "Texte_soutenance_Noa.pdf"

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
GREY = colors.HexColor("#555555")

st_title = ParagraphStyle("title", fontName="Arial-Bold", fontSize=17,
                          leading=21, textColor=ACCENT, spaceAfter=4)
st_intro = ParagraphStyle("intro", fontName="Arial-Italic", fontSize=9,
                          leading=12.5, textColor=GREY, leftIndent=6,
                          spaceAfter=4)
st_part = ParagraphStyle("part", fontName="Arial-Bold", fontSize=13.5,
                         leading=16, textColor=colors.white,
                         spaceBefore=4, spaceAfter=4, leftIndent=4)
st_slide = ParagraphStyle("slide", fontName="Arial-Bold", fontSize=11.5,
                          leading=14, textColor=ACCENT,
                          spaceBefore=11, spaceAfter=4, keepWithNext=1)
st_body = ParagraphStyle("body", fontName="Arial", fontSize=10, leading=14.5,
                         spaceAfter=6, alignment=4)  # justified
st_note_h = ParagraphStyle("noteh", fontName="Arial-Bold", fontSize=11.5,
                           leading=14, textColor=ACCENT,
                           spaceBefore=10, spaceAfter=5)
st_li = ParagraphStyle("li", fontName="Arial", fontSize=9.5, leading=13,
                       leftIndent=12, bulletIndent=2, spaceAfter=3)


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(t):
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+?)`", r'<font face="Consolas" size="9">\1</font>', t)
    t = t.replace("→", '<font color="#1a5276"><b>→</b></font>')
    return t


def slide_para(title):
    """Met le repere de minutage [x:xx] en gris a droite, dans un tableau."""
    m = re.search(r"\s*\[([^\]]+)\]\s*$", title)
    tc = ""
    if m:
        tc = m.group(1)
        title = title[:m.start()].rstrip()
    left = Paragraph(inline(title), st_slide)
    if not tc:
        return left
    right = Paragraph(
        f'<font color="#888888">[{esc(tc)}]</font>',
        ParagraphStyle("tc", fontName="Arial", fontSize=9, leading=14,
                       alignment=2, textColor=colors.HexColor("#888888")),
    )
    tbl = Table([[left, right]], colWidths=[150 * mm, 24 * mm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d8e0")),
    ]))
    return tbl


def part_banner(title):
    p = Paragraph(inline(title), st_part)
    tbl = Table([[p]], colWidths=[174 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tbl


def build():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    story, i = [], 0
    intro_buf = []
    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.startswith("# "):
            story.append(Paragraph(inline(ln[2:]), st_title))
            story.append(HRFlowable(width="100%", thickness=1.2,
                                    color=ACCENT, spaceAfter=8))
        elif ln.startswith("> "):
            intro_buf.append(ln[2:].strip())
        elif ln.startswith("### "):
            if intro_buf:
                for b in intro_buf:
                    story.append(Paragraph(inline(b), st_intro))
                story.append(Spacer(1, 6))
                intro_buf = []
            story.append(Paragraph(inline(ln[4:]), st_note_h))
        elif ln.startswith("## "):
            if intro_buf:
                for b in intro_buf:
                    story.append(Paragraph(inline(b), st_intro))
                story.append(Spacer(1, 6))
                intro_buf = []
            title = ln[3:]
            if "Partie" in title:
                story.append(Spacer(1, 6))
                story.append(part_banner(title))
            else:
                story.append(slide_para(title))
        elif ln.startswith("- "):
            story.append(Paragraph(inline(ln[2:]), st_li, bulletText="•"))
        elif ln.startswith("---") or not ln.strip():
            pass
        else:
            story.append(Paragraph(inline(ln), st_body))
        i += 1
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 7.5)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(18 * mm, 10 * mm,
                      "Texte de soutenance — E6 · BTS CIEL 2026 · Noa Orand")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(
    str(OUT), pagesize=A4,
    leftMargin=18 * mm, rightMargin=18 * mm,
    topMargin=16 * mm, bottomMargin=16 * mm,
    title="Texte de soutenance — E6 — Noa Orand",
    author="Noa Orand",
)
doc.build(build(), onFirstPage=footer, onLaterPages=footer)
print(f"OK -> {OUT}")
