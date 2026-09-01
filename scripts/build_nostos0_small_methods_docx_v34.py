"""Build the template-aligned Small Methods v34 submission manuscript."""

from __future__ import annotations

import re
from pathlib import Path

import build_nostos0_methods_docx as base
import build_nostos0_small_methods_docx_v33 as v33
from docx.enum.text import WD_ALIGN_PARAGRAPH


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V34.md"
OUTPUT = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_candidate_v34.docx"
TEMPLATE = ROOT / "resources" / "journal_templates" / "Small_Methods_Article_Template_2025.docx"

TITLE = "NOSTOS Prevents Silent Acquisition- and Scale-Specific Failure in Quantitative Microscopy"

RESULT_HEADING_MAP = {
    "### A validity profile is a deployable measurement object": "### 2.1. Executable validity profiles and prospective BioSR confirmation",
    "### A first prospective profile lowers tensor-coherence risk in BioSR": "",
    "### Pooled confirmation can conceal a deterministic failure": "### 2.2. Hidden FMD failure and hierarchical repair",
    "### Hierarchical support removes the unsafe cell on untouched fields": "",
    "### A frozen contract lowers invalidity in unstained PSHG tissue": "### 2.3. Selective validity in unstained PSHG tissue",
    "### Single-image structure transfers to an independent tendon pSHG acquisition": "### 2.4. Single-image structural recovery in independent tendon pSHG",
    "### The software preserves failure as part of the result": "",
}

EXPERIMENTAL_HEADINGS = [
    "Software implementation and response schema",
    "Evidence-row contract and invalidity",
    "Base-profile compilation",
    "Hierarchical conditional support",
    "Confirmation statistics",
    "BioSR v9 confirmation",
    "FMD source and selection",
    "FMD measurement and score",
    "PSHG acquisition-shift confirmation",
    "Tendon pSHG-XRD transfer",
    "Failure lineage and terminal audit",
    "Synthetic and supplementary estimator validation",
]


def reformat_source() -> Path:
    v33_source = v33.build_source()
    text = v33_source.read_text(encoding="utf-8")
    text = text.replace(
        "# NOSTOS prevents silent acquisition- and scale-specific failure in quantitative microscopy",
        f"# {TITLE}",
        1,
    )
    text = text.replace("**Yan Jun Lin**", "*Yan Jun Lin*", 1)
    funding_line = "Funding: The author received no specific funding for this work."
    text = text.replace("**Keywords:**", funding_line + "\n\n**Keywords:**", 1)
    text = text.replace(
        "**Keywords:** quantitative microscopy; measurement validity; selective prediction; abstention; uncertainty calibration; reproducible software",
        "**Keywords:** quantitative microscopy, measurement validity, selective prediction, abstention, uncertainty calibration, reproducible software",
        1,
    )
    text = text.replace("Spearman ρ=0.891", "Spearman ρ = 0.891")
    text = text.replace("`Phi2`", "φ₂").replace("`I2`", "I₂")
    text = text.replace(
        "Generative AI systems, including OpenAI Codex and Anthropic Claude Code, assisted with code review, statistical-script checks, figure-generation code, citation verification and language editing. BioRender custom-figure generation produced the text-free illustrative workflow geometry in Figures 1b, 3d and 5a. These three schematic components contain no microscopy, measurement or biological data; all microscopy, maps, plots, numerical labels and statistics derive from the cited public resources and deterministic code. The author verified the executable results and final text and accepts full responsibility for the work.",
        "Generative AI systems, including OpenAI Codex and Anthropic Claude Code, assisted with code review, statistical-script checks, deterministic figure-generation code, citation verification and language editing. No generated microscopy, biological observation or numerical result appears in the manuscript. All microscopy, maps, plots, numerical labels and statistics derive from the cited public resources and checksum-locked deterministic code. BioRender was used only to explore data-free workflow layouts; those exploratory panels are not present in the final main figures. The author verified the executable results and final text and accepts full responsibility for the work.",
        1,
    )

    text = text.replace("## Introduction", "## 1. Introduction", 1)
    text = text.replace("## Results and Discussion", "## 2. Results and Discussion", 1)
    for old, new in RESULT_HEADING_MAP.items():
        text = text.replace(old, new, 1)
    text = text.replace("\n## Discussion\n", "\n", 1)
    text = text.replace("## Conclusion", "## 3. Conclusion", 1)
    text = text.replace("## Experimental Section", "## 4. Experimental Section", 1)
    for index, heading in enumerate(EXPERIMENTAL_HEADINGS, start=1):
        text = text.replace(f"### {heading}", f"### 4.{index}. {heading}", 1)

    # The author template uses a period after the display-item number. Keep the
    # short panel clauses but remove the Nature-specific title separator.
    text = re.sub(r"\*\*(Figure \d+) \| ", r"**\1. ", text)
    text = re.sub(r"\*\*(Supplementary Figure \d+) \| ", r"**\1. ", text)
    text = re.sub(
        r"\*\*Figure 1\. NOSTOS separates computation from measurement validity\.\*\*.*?(?=\n\n\*\*Figure 2\.)",
        "**Figure 1. NOSTOS separates computation from measurement validity.** **a,** Authentic BioSR and FMD microscopy, the paired BioSR reference, deterministic orientation fields and Fourier power. FMD remains pixel-relative because spacing is unavailable. **b,** An authentic FMD image and its deterministic orientation field pass through the frozen acquisition-by-scale support lattice to an emit or abstain decision. **c,** BioSR tensor-coherence response across declared physical scales. **d,** Frozen FMD acquisition-by-scale support; white circles denote supported cells and crosses unsupported cells. **e,** Output states. Every biological pixel originates in the cited public archives; every map and summary is deterministic.",
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r"\*\*Figure 3\. Pooled validation conceals a deterministic acquisition-by-scale failure\.\*\*.*?(?=\n\n\*\*Figure 4\.)",
        "**Figure 3. Pooled validation conceals a deterministic acquisition-by-scale failure.** **a,** One FMD field across increasing capture averages and the average-of-50 reference. **b,** Development localization: every emitted average-of-8 by 8-pixel tensor-coherence measurement was invalid, whereas supported average-of-16 cells had no observed error. **c,** The same failure recurred on untouched confirmation fields. **d,** The data-bearing repair sequence: pooled support emitted 68 of 240 measurements, stratification isolated four invalid outputs in four attempts, and the frozen repair abstained from that unsafe cell. All numbers are frozen audit results.",
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r"\*\*Figure 5\. A frozen input-only contract lowers silently invalid orientation outputs in unstained PSHG tissue\.\*\*.*?(?=\n\n\*\*Figure 6\.)",
        "**Figure 5. A frozen input-only contract lowers silently invalid orientation outputs in unstained PSHG tissue.** **a,** Authentic clean forward-SHG, the severe compound shift, the deterministic NOSTOS local axial orientation field and the withheld polarization-derived reference for the first region in the frozen confirmation lock. **b,** Condition-by-policy acceptance; circle area encodes coverage, fill encodes invalidity among accepted cases and crosses denote no accepted cases. **c,** Tied-score risk-coverage curves. **d,** Invalid outputs among the same 230 accepted cases: 47 for acquisition quality control, 24 for endpoint quality control and 7 for NOSTOS. **e,** Region-bootstrap differences for matched risk and risk-coverage area; positive values favor NOSTOS. Conditions are nested within 24 independent regions.",
        text,
        count=1,
        flags=re.S,
    )

    # Place the large tendon evidence panel immediately after the acquisition
    # and label-blinding setup. This mirrors the accepted-paper rhythm of
    # question -> visual evidence -> quantitative interpretation and prevents
    # an artificial half-empty page before the display item.
    figure6_marker = "**[Figure 6 near here: authentic tendon SHG, NOSTOS and pSHG maps, organization recovery, matched invalid outputs and tied-score risk–coverage curves.]**"
    figure6_anchor = "Only the mean SHG intensity image entered NOSTOS; φ₂, I₂, zone identity and X-ray measurements were unavailable to the support decision."
    text = text.replace(figure6_marker, "", 1)
    text = text.replace(figure6_anchor, f"{figure6_anchor}\n\n{figure6_marker}", 1)

    # Keep the author-file section order explicit and acknowledge the separate
    # evidence supplement without pretending it has already been typeset.
    if "## Supporting Information" not in text:
        text = text.replace(
            "\n## Table of Contents\n",
            "\n## Supporting Information\n\nSupporting Information accompanies this article as a separate editable document and contains the extended validation tables, perturbation definitions, audit receipts and supplementary figures.\n\n## Table of Contents\n",
            1,
        )

    required = (
        "## 1. Introduction",
        "## 2. Results and Discussion",
        "## 3. Conclusion",
        "## 4. Experimental Section",
        "### 2.4. Single-image structural recovery in independent tendon pSHG",
        "## Supporting Information",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(f"Small Methods v34 reformatting failed: {missing}")
    SOURCE.write_text(text, encoding="utf-8")
    return SOURCE


def configure_builder() -> None:
    v33.configure_builder()
    base.DOCUMENT_TEMPLATE = TEMPLATE
    base.PRESERVE_TEMPLATE_GEOMETRY = True
    base.PRESERVE_TEMPLATE_PAGE_FURNITURE = False
    base.HEADER_TEXT = "WILEY-VCH"
    base.HEADER_ALIGNMENT = WD_ALIGN_PARAGRAPH.CENTER
    base.FOOTER_PREFIX = ""
    base.FIGURE_CAPTION_SEPARATOR = ". "
    base.JOURNAL_MANUSCRIPT.update(
        {
            "font": "Times New Roman",
            "body_size_pt": 9.35,
            "body_after_pt": 3.0,
            "body_line_spacing": 1.08,
            "title_size_pt": 16.0,
            "heading1_size_pt": 10.5,
            "heading2_size_pt": 9.6,
            "caption_size_pt": 7.8,
        }
    )
    base.FIGURE_WIDTHS.update(
        {
            "Figure 1": 6.25,
            "Figure 2": 6.25,
            "Figure 3": 6.25,
            "Figure 4": 6.25,
            # Figure 5 is slightly narrower so its complete evidence panel and
            # caption stay with the PSHG result instead of creating a half-empty
            # preceding page in the editable author file.
            "Figure 5": 5.75,
            "Figure 6": 6.25,
            "Graphical abstract": 4.33,
        }
    )
    base.DOC_TITLE = TITLE
    base.DOC_SUBJECT = "Small Methods template-aligned submission candidate v34; computation-only public-data validation"
    base.DOC_KEYWORDS = "quantitative microscopy; measurement validity; selective prediction; abstention; second harmonic generation; reproducible software"


def main() -> None:
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Missing official Small Methods template: {TEMPLATE}")
    source = reformat_source()
    configure_builder()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    missing = [str(path) for path in base.FIGURES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing Small Methods figure assets: {missing}")
    print(base.build(source, OUTPUT))
    print(f"abstract_words={v33.word_count(v33.ABSTRACT)}")
    print(f"toc_words={v33.word_count(v33.TOC_TEXT)}")


if __name__ == "__main__":
    main()
