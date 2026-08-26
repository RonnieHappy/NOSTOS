"""Build the evidence-locked NOSTOS-0 methods article as a rendered Word draft."""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "NOSTOS0_METHODS_ARTICLE.md"
OUTPUT = ROOT / "docs" / "NOSTOS0_methods_article_evidence_locked.docx"
FIGURES = {
    "Figure 1 near here": ROOT / "figures/nostos0/figure_1_response_geometry_reference.png",
    "Figure 2 near here": ROOT / "figures/nostos0/figure_2_synthetic_validation.png",
    "Figure 3 near here": ROOT / "figures/nostos0/figure_3_bone_validation.png",
    "Figure 4 near here": ROOT / "figures/nostos0/figure_4_cross_domain_boundaries.png",
}


def set_font(run, size=None, bold=None, italic=None, color=None):
    run.font.name = "Times New Roman"
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Times New Roman")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Times New Roman")
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Times New Roman")
    if size is not None: run.font.size = Pt(size)
    if bold is not None: run.bold = bold
    if italic is not None: run.italic = italic
    if color is not None: run.font.color.rgb = RGBColor(*color)


def add_page_field(paragraph):
    run = paragraph.add_run()
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run._r.addnext(fld)


def configure(doc: Document) -> None:
    section = doc.sections[0]
    section.top_margin = Inches(.72); section.bottom_margin = Inches(.72)
    section.left_margin = Inches(.78); section.right_margin = Inches(.78)
    section.header_distance = Inches(.3); section.footer_distance = Inches(.3)
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"; normal.font.size = Pt(10)
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.06
    for name, size, before, after in (("Title", 18, 0, 8), ("Heading 1", 13, 11, 4), ("Heading 2", 11, 8, 3)):
        style = doc.styles[name]
        style.font.name = "Times New Roman"; style.font.size = Pt(size)
        style.font.bold = True; style.font.color.rgb = RGBColor(0, 0, 0)
        style._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
        style.paragraph_format.space_before = Pt(before); style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
    caption = doc.styles["Caption"]
    caption.font.name = "Times New Roman"; caption.font.size = Pt(8.5)
    caption.font.bold = False; caption.font.italic = False
    caption.font.color.rgb = RGBColor(0, 0, 0)
    caption._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    caption._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    caption.paragraph_format.space_before = Pt(3); caption.paragraph_format.space_after = Pt(7)
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_font(header.add_run("NOSTOS-0 | evidence-locked development article"), 8, italic=True, color=(95, 95, 95))
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(footer.add_run("Page "), 8, color=(95, 95, 95)); add_page_field(footer)


def add_inline(paragraph, text: str) -> None:
    text = (text.replace("\\(", "").replace("\\)", "")
            .replace("\\rho", "ρ").replace("\\Delta", "Δ")
            .replace("\\theta", "θ").replace("\\tau", "τ")
            .replace("\\ell", "ℓ").replace("\\Phi", "Φ")
            .replace("\\mu", "µ").replace("\\", ""))
    token = re.compile(r"(\*\*.*?\*\*|\*.*?\*|`.*?`)")
    for part in token.split(text):
        if not part: continue
        if part.startswith("**") and part.endswith("**"):
            set_font(paragraph.add_run(part[2:-2]), bold=True)
        elif part.startswith("*") and part.endswith("*"):
            set_font(paragraph.add_run(part[1:-1]), italic=True)
        elif part.startswith("`") and part.endswith("`"):
            set_font(paragraph.add_run(part[1:-1]), 9, color=(55, 55, 55))
        else:
            set_font(paragraph.add_run(part))


def build() -> Path:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    legends: dict[str, str] = {}
    for line in lines:
        match = re.match(r"\*\*Figure (\d+) \| (.+?)\.\*\*\s*(.*)", line)
        if match:
            legends[match.group(1)] = f"Figure {match.group(1)} | {match.group(2)}. {match.group(3)}"

    doc = Document(); configure(doc)
    in_legend_section = False; in_references = False; in_equation = False; equation_lines = []
    for raw in lines:
        line = raw.strip()
        if line == "## Figure legends":
            in_legend_section = True
            continue
        if in_legend_section:
            if line == "## References":
                in_legend_section = False
                doc.add_heading("References", level=1)
                in_references = True
                continue
            else:
                continue
        if not line: continue
        if line == "\\[": in_equation = True; equation_lines = []; continue
        if line == "\\]":
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(6)
            set_font(p.add_run("Φ(I, M, Δ) = {Φₘ(ℓ, θ, τ, r)}ₘ₌₁ᴹ"), 10, italic=True)
            in_equation = False; continue
        if in_equation: equation_lines.append(line); continue
        if line.startswith("# "):
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.keep_with_next = True
            set_font(p.add_run(line[2:]), 18, bold=True)
            continue
        if line.startswith("### "):
            doc.add_heading(line[4:], level=2); continue
        if line.startswith("## "):
            doc.add_heading(line[3:], level=1); continue
        figure_key = next((key for key in FIGURES if key in line), None)
        if figure_key:
            number = figure_key.split()[1]
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True; p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(1)
            p.add_run().add_picture(str(FIGURES[figure_key]), width=Inches(6.9))
            cap = doc.add_paragraph(style="Caption"); cap.paragraph_format.keep_together = True
            add_inline(cap, legends[number])
            continue
        if line == "---": continue
        p = doc.add_paragraph()
        if line.startswith("**Article type:**") or line.startswith("**Target:**") or line.startswith("**Version:**") or line.startswith("**Status:**"):
            p.paragraph_format.space_after = Pt(1)
        if re.match(r"^\d+\. ", line):
            p.paragraph_format.left_indent = Inches(.18)
            p.paragraph_format.first_line_indent = Inches(-.18)
            p.paragraph_format.space_after = Pt(1 if in_references else 2)
            if in_references:
                p.paragraph_format.line_spacing = 1.0
        add_inline(p, line)
        if in_references:
            p.paragraph_format.space_after = Pt(0)
            for run in p.runs:
                set_font(run, 8)

    props = doc.core_properties
    props.title = "NOSTOS represents multiscale structure across biological images in physical coordinates"
    props.subject = "Evidence-locked NOSTOS-0 methods article"
    props.author = "NOSTOS contributors"
    props.keywords = "computational microscopy; image analysis; morphology; validation"
    doc.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build())
