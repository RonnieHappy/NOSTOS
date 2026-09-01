"""Build the NOSTOS Small Methods submission candidate without altering v30."""
from __future__ import annotations

import re
from pathlib import Path

import build_nostos0_methods_docx as base


ROOT = Path(__file__).resolve().parents[1]
V30_SOURCE = ROOT / "docs" / "NOSTOS0_SOFTWARE_RESOURCE_ARTICLE.md"
SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V31.md"
OUTPUT = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_candidate_v31.docx"
FIGURE_DIR = ROOT / "figures" / "nostos0_small_methods"

TITLE = "NOSTOS prevents silent acquisition- and scale-specific failure in quantitative microscopy"
ABSTRACT = (
    "Quantitative microscopy software usually reports a value whenever an algorithm can run, although image "
    "sampling may not support the requested measurement. NOSTOS is a CPU-first framework that compiles paired "
    "acquisition–reference data into input-only validity profiles for continuous measurements. Profiles combine "
    "hard preconditions, group-cross-fitted risk calibration and acquisition-by-scale support; reference values "
    "are unavailable at deployment. On eight untouched BioSR F-actin fields, a frozen profile retained 95.0% of "
    "980 eligible tensor-coherence measurements while reducing silent-invalid risk from 0.0735 under acquisition "
    "quality control to 0.0387. In the Fluorescence Microscopy Denoising archive, pooled validation passed despite "
    "a reproducible average-of-8 by 8-pixel condition in which every emitted measurement was invalid. A frozen "
    "hierarchical repair then emitted 64 of 240 measurements on four new fields with no observed errors, whereas "
    "matched acquisition quality control emitted 31 errors. The field-bootstrap difference in risk–coverage area "
    "was 0.281 (95% interval, 0.187–0.416); exact intervals expose the four-field limit. NOSTOS makes support, "
    "abstention and failure history executable for calibrated microscopy measurements without assigning universal "
    "biological meaning or a distribution-free guarantee."
)
TOC_TEXT = (
    "NOSTOS converts microscopy algorithms into measurements that can refuse unsupported input. Across two public "
    "microscopy resources, pooled quality control concealed a fully invalid acquisition-by-scale condition. A frozen "
    "hierarchical validity profile removed that failure on untouched fields, reducing matched quality-control errors "
    "from 31 of 64 emissions to none while preserving explicit finite-sample uncertainty."
)

LEGENDS = """## Figure legends

**Figure 1 | NOSTOS separates computation from measurement validity.** **a,** Authentic BioSR and FMD microscopy, a paired BioSR reference, deterministic orientation fields and Fourier power. FMD remains pixel-relative because spacing is unavailable. **b,** Illustrative workflow geometry: an image is measured, evaluated against frozen acquisition-by-scale support and either emitted or rejected. The text-free schematic was generated in BioRender; labels were overlaid deterministically in Times New Roman. **c,** The real BioSR tensor-coherence response across declared physical scales. **d,** Frozen FMD acquisition-by-scale support; white circles are supported cells and crosses are unsupported cells. **e,** Schematic output states. Biological image pixels originate from the cited public archives; every map and summary is deterministic; panel b contains no biological or quantitative data.

**Figure 2 | Selective support lowers silent-invalid risk in untouched BioSR fields.** **a,** A paired F-actin reference and ordinary-resolution input, their deterministic orientation field, and a controlled blur challenge. **b,** Valid emissions, invalid emissions and abstentions across the frozen perturbation panel. **c,** Invalid-emission risk paired by each of eight independent fields under acquisition quality control and NOSTOS. **d,** Tied-score risk–coverage curves; 36 of the 49 measurements rejected only by NOSTOS were invalid. Perturbations, scales and signal levels remain nested within fields.

**Figure 3 | Pooled validation conceals a deterministic acquisition-by-scale failure.** **a,** One FMD field across increasing capture averages and the average-of-50 reference. **b,** Development localization: every emitted average-of-8 by 8-pixel tensor-coherence measurement was invalid, whereas supported average-of-16 cells had no observed error. **c,** The same failure recurred on untouched confirmation fields. **d,** Pooled validation reported only 4 invalid values among 68 emissions, but stratification exposed 4 of 4 invalid values in the failed cell and motivated a frozen conditional support table. The text-free BioRender geometry is illustrative; the numerical labels are frozen audit results overlaid by deterministic code, and the schematic objects encode no observed image data.

**Figure 4 | Frozen hierarchical support prevents recurrence on new fields.** **a,** Average-of-16 images from the four untouched confirmation fields. **b,** Development-only support lattice. **c,** Each supported capture-by-scale cell emitted four measurements in each field. **d,** At matched coverage, acquisition quality control emitted 31 invalid values among 64; NOSTOS emitted none. **e,** Risk–coverage curves. **f,** Field-bootstrap difference in risk–coverage area, acquisition quality control minus NOSTOS, with the 95% interval. **g,** Exact two-sided 95% upper limits for 64 nested measurements and four independent field-level any-failure events.
"""

ADMIN = """## Data Availability Statement

All microscopy data remain in their originating public repositories. FMD is available under CC BY-SA 4.0 at DOI 10.7274/r0-ed2r-4052; BioSR is available at DOI 10.6084/m9.figshare.13264793. Dataset identifiers, licences, archive and member hashes, frozen selection rules and exact commands are included in the software evidence record. Source code is publicly available at https://github.com/RonnieHappy/NOSTOS under the BSD 3-Clause License. A versioned archival DOI will be added to the accepted manuscript when the submission snapshot is deposited.

## Author Contributions

Yan Jun Lin conceived the framework, implemented the software and analyses, curated the evidence record, interpreted the results, generated the figures and wrote the manuscript.

## Acknowledgements

Generative AI systems, including OpenAI Codex and Anthropic Claude Code, assisted with code review, statistical-script checks, figure-generation code, citation verification and language editing. BioRender custom-figure generation produced the text-free illustrative workflow geometry in Figures 1b and 3d. These two schematic components contain no microscopy, measurement or biological data; all microscopy, maps, plots, numerical labels and statistics derive from the cited public resources and deterministic code. The author verified the executable results and final text and accepts full responsibility for the work.

## Conflict of Interest

The author declares no conflict of interest.

## Funding

The author received no specific grant funding for this work.

## Ethics Statement

This study is a secondary computational analysis of public de-identified images and analytic data. No participants, specimens or new acquisitions were added.
"""


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w–-]+\b", text))


def build_source() -> Path:
    if word_count(ABSTRACT) > 200:
        raise RuntimeError(f"Small Methods abstract exceeds 200 words: {word_count(ABSTRACT)}")
    if not 50 <= word_count(TOC_TEXT) <= 60:
        raise RuntimeError(f"Table-of-contents text must contain 50–60 words: {word_count(TOC_TEXT)}")

    original = V30_SOURCE.read_text(encoding="utf-8")
    abstract_start = original.index("## Abstract")
    main_start = original.index("## Main")
    body = original[main_start:]
    body = body.replace("## Main", "## Introduction", 1)
    body = body.replace(
        "### A validity profile is a deployable measurement object",
        "## Results and Discussion\n\n### A validity profile is a deployable measurement object",
        1,
    )
    body = body.replace(
        "## Methods",
        "## Conclusion\n\nNOSTOS makes the validity of a requested quantitative microscopy measurement "
        "an executable, versioned decision rather than an assumption. Across two independent public resources, "
        "the framework reduced silent-invalid outputs, exposed a pooled pass that concealed deterministic subgroup "
        "failure and prospectively removed that failure from untouched fields. The result is a practical fail-closed "
        "layer for calibrated microscopy measurements, bounded to the acquisitions and measurement coordinates on "
        "which its profile was established.\n\n## Experimental Section",
        1,
    )

    data_start = body.index("## Data and code availability")
    legends_start = body.index("## Figure legends")
    references_start = body.index("## References")
    body_before_admin = body[:data_start].rstrip()
    references = body[references_start:].rstrip()

    front = (
        f"# {TITLE}\n\n"
        "**Yan Jun Lin**\n\n"
        "Department of Orthopaedic Surgery, University of Pittsburgh Medical Center, Pittsburgh, Pennsylvania, USA\n\n"
        "Correspondence: Yan Jun Lin, Linyj2@upmc.edu\n\n"
        "**Keywords:** quantitative microscopy; measurement validity; selective prediction; abstention; uncertainty calibration; reproducible software\n\n"
        "## Abstract\n\n"
        f"{ABSTRACT}\n\n"
    )
    text = (
        front
        + body_before_admin
        + "\n\n"
        + ADMIN.rstrip()
        + "\n\n"
        + LEGENDS.rstrip()
        + "\n\n"
        + references
        + "\n\n## Table of Contents\n\n"
        + TOC_TEXT
        + "\n\n**[Graphical abstract near here]**\n"
    )
    if "Nature Methods" in text or "candidate v30" in text:
        raise RuntimeError("Stale target/version language remains in Small Methods source")
    SOURCE.write_text(text, encoding="utf-8")
    return SOURCE


def configure_builder() -> None:
    base.FIGURES = {
        "Figure 1 near here": FIGURE_DIR / "figure_1_measurement_to_decision.png",
        "Figure 2 near here": FIGURE_DIR / "figure_2_biosr_confirmation.png",
        "Figure 3 near here": FIGURE_DIR / "figure_3_hidden_conditional_failure.png",
        "Figure 4 near here": FIGURE_DIR / "figure_4_hierarchical_confirmation.png",
        "Graphical abstract near here": FIGURE_DIR / "nostos_small_methods_toc.png",
    }
    base.FIGURE_ALT = {
        "Figure 1": "Authentic BioSR and FMD microscopy and deterministic measurement maps leading through a frozen NOSTOS support profile to emission or abstention.",
        "Figure 2": "BioSR perturbation outcomes, field-paired silent-invalid risk and risk-coverage behavior under acquisition quality control and NOSTOS.",
        "Figure 3": "FMD acquisition ladder and development and untouched-confirmation matrices localizing a fully invalid average-of-eight by eight-pixel measurement condition.",
        "Figure 4": "Four untouched FMD fields, the frozen hierarchical support lattice, matched quality-control errors, risk-coverage curves and finite-sample uncertainty.",
        "Graphical abstract": "An authentic FMD image passes through deterministic orientation measurement and acquisition-by-scale support to an emit or abstain decision.",
    }
    base.FIGURE_WIDTHS = {
        "Figure 1": 6.82,
        "Figure 2": 6.82,
        "Figure 3": 6.82,
        "Figure 4": 6.82,
        "Graphical abstract": 6.40,
    }
    base.HEADER_TEXT = ""
    base.DOC_TITLE = TITLE
    base.DOC_SUBJECT = "Small Methods submission candidate v31; computation-only public-data validation"
    base.DOC_AUTHOR = "Yan Jun Lin"
    base.DOC_KEYWORDS = "quantitative microscopy; measurement validity; selective prediction; abstention; uncertainty calibration; reproducible software"


def main() -> None:
    source = build_source()
    configure_builder()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    missing = [str(path) for path in base.FIGURES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing Small Methods figure assets: {missing}")
    print(base.build(source, OUTPUT))
    print(f"abstract_words={word_count(ABSTRACT)}")
    print(f"toc_words={word_count(TOC_TEXT)}")


if __name__ == "__main__":
    main()
