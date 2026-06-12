# -*- coding: utf-8 -*-
"""Convertit la fiche d'integration Noa (markdown) en PDF mis en forme."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib import colors
import html

SRC = r"C:\Users\noaor\OneDrive\Bureau\Projet BTS 2026\ProjetDataSet2026_ModeleIA\fiches_recette\integration\integration_noa.md"
OUT = r"C:\Users\noaor\OneDrive\Bureau\Projet BTS 2026\ProjetDataSet2026_ModeleIA\fiches_recette\integration\integration_noa.pdf"

styles = getSampleStyleSheet()
h1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=18, spaceAfter=4, textColor=colors.HexColor("#1a3a5c"))
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#2563a0"))
body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10.5, leading=15, alignment=TA_JUSTIFY, spaceAfter=4)
bullet = ParagraphStyle("Bullet", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=3)


def inline(text):
    """Echappe le HTML puis applique gras (**), code (`) et conserve les accents."""
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("**", i):
            j = text.find("**", i + 2)
            if j != -1:
                out.append("<b>" + html.escape(text[i + 2:j]) + "</b>")
                i = j + 2
                continue
        if text[i] == "`":
            j = text.find("`", i + 1)
            if j != -1:
                out.append('<font face="Courier" size="9">' + html.escape(text[i + 1:j]) + "</font>")
                i = j + 1
                continue
        out.append(html.escape(text[i]))
        i += 1
    return "".join(out)


with open(SRC, encoding="utf-8") as f:
    lines = f.read().splitlines()

story = []
for raw in lines:
    line = raw.rstrip()
    if not line.strip():
        story.append(Spacer(1, 4))
    elif line.startswith("# "):
        story.append(Paragraph(inline(line[2:]), h1))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3a5c"), spaceAfter=6))
    elif line.startswith("## "):
        story.append(Paragraph(inline(line[3:]), h2))
    elif line.lstrip().startswith(("- ", "* ")):
        story.append(Paragraph(inline(line.lstrip()[2:]), bullet, bulletText="•"))
    elif line[:2].strip().isdigit() and line[1:3] in (". ", ") ") or (len(line) > 2 and line[0].isdigit() and line[1] == "."):
        story.append(Paragraph(inline(line.split(".", 1)[1].strip()), bullet, bulletText=line.split(".", 1)[0] + "."))
    else:
        story.append(Paragraph(inline(line), body))

doc = SimpleDocTemplate(OUT, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm, title="Fiche d'integration - Noa")
doc.build(story)
print("OK ->", OUT)
