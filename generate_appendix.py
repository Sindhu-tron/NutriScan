from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable
import os

FILES = [
    "pipeline/scoring.py",
    "pipeline/frida_matcher.py",
    "pipeline/nutrient_lookup.py",
    "pipeline/menu_parser.py",
    "pipeline/pdf_extractor.py",
    "pipeline/build_db.py",
    "api/main.py",
    "frontend/dashboard.py",
    "main.py",
    "tests/test_scoring.py",
    "tests/test_frida_matcher.py",
    "tests/test_nutrient_lookup.py",
    "tests/test_menu_parser.py",
    "tests/test_pdf_extractor.py",
    "requirements.txt",
]

def escape(text):
    return text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

header_style = ParagraphStyle("H", fontName="Helvetica-Bold", fontSize=11,
                               spaceBefore=10, spaceAfter=4)
code_style   = ParagraphStyle("C", fontName="Courier", fontSize=7.5,
                               leading=10, wordWrap="CJK")

story = []
for filepath in FILES:
    if not os.path.exists(filepath):
        continue
    story.append(Paragraph(escape(filepath), header_style))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.grey, spaceAfter=4))
    with open(filepath, encoding="utf-8", errors="replace") as f:
        for line in f.read().splitlines():
            story.append(Paragraph(escape(line.replace("\t","    ")) or "&nbsp;",
                                   code_style))
    story.append(PageBreak())

doc = SimpleDocTemplate("NutriScan_Code_Appendix.pdf", pagesize=A4,
                         leftMargin=2*cm, rightMargin=2*cm,
                         topMargin=2*cm, bottomMargin=2*cm)
doc.build(story)
print("Done — NutriScan_Code_Appendix.pdf")