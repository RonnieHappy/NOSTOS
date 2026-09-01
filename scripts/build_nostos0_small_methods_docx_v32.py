"""Build the Small Methods v32 candidate with verified PSHG validation."""

from __future__ import annotations

import re
from pathlib import Path

import build_nostos0_methods_docx as base


ROOT = Path(__file__).resolve().parents[1]
V31_SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V31.md"
SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V32.md"
OUTPUT = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_candidate_v32.docx"
FIGURE_DIR = ROOT / "figures" / "nostos0_small_methods"
PSHG_FIGURE = ROOT / "figures" / "nostos0_pshg_acquisition_shift" / "figure_pshg_acquisition_shift.png"

TITLE = "NOSTOS prevents silent acquisition- and scale-specific failure in quantitative microscopy"
ABSTRACT = (
    "Quantitative microscopy software often reports a value whenever an algorithm can run, although image sampling "
    "may not support the requested measurement. NOSTOS is a CPU-first framework that compiles paired acquisition–reference "
    "data into input-only validity profiles for continuous measurements. Profiles combine hard preconditions, grouped risk "
    "calibration and acquisition-by-scale support; reference values are unavailable at deployment. On eight untouched BioSR "
    "F-actin fields, a frozen profile retained 95.0% of 980 eligible tensor-coherence measurements while reducing silent-invalid "
    "risk from 0.0735 under acquisition quality control to 0.0387. In the Fluorescence Microscopy Denoising archive, pooled "
    "validation concealed a reproducible condition in which every emitted measurement was invalid; a frozen hierarchical "
    "repair later emitted 64 measurements on four new fields without an observed error. In unstained polarization-resolved "
    "second-harmonic-generation tissue, 24 hash-disjoint confirmation regions yielded 77 invalid cases under 15 controlled "
    "acquisition conditions. At matched 63.9% coverage, NOSTOS retained 7 invalid outputs versus 47 for acquisition quality "
    "control and 24 for endpoint quality control; region-level bootstrap intervals excluded zero. NOSTOS makes support, "
    "abstention and failure history executable without assigning universal biological meaning or a distribution-free guarantee."
)
TOC_TEXT = (
    "NOSTOS converts microscopy algorithms into measurements that can refuse unsupported input. Across three public resources, "
    "it exposed hidden acquisition-by-scale failure and repaired it prospectively. On unstained polarization-resolved tissue, "
    "invalid outputs fell from 47 under acquisition quality control to 7 under NOSTOS at matched coverage; hash-locked auditing "
    "independently reproduced every decision."
)

PSHG_RESULTS = """### A frozen contract lowers invalidity in unstained PSHG tissue

The prior studies established selective validity in fluorescence archives, but
they did not test a label-free tissue image against a physically derived local
orientation reference. We therefore used the unstained-breast forward-SHG
subset of PSHG-TISS[30]. Each region contains ten frames acquired from 0° to
180° in 20° increments, together with a polarization-fit orientation map and
fit-quality maps. The NOSTOS endpoint was the sigma-2-pixel local axial
structure-tensor direction. A 90° instrument-to-raster offset had been frozen
on a separate skin qualification subset before the breast orientation result.

The 48 breast regions were ordered by a prespecified SHA-256 rule and divided
into 24 development and 24 confirmation regions before any shifted image was
generated. Fifteen conditions were fixed: clean input; three levels each of
blur, noise and circular inter-frame motion; two resampling levels; low
contrast; and moderate and severe compound shifts. A case was invalid when its
median axial error exceeded 15° or its 75th-percentile error exceeded 30°.
Every policy used the same orientation estimator. Policies differed only in
input-known acquisition diagnostics, coherence, scale consistency and
alternating-frame consistency. The polarization reference and its fit-quality
maps were withheld from every deployment decision.

The confirmation contained 360 cases, of which 77 were invalid. At the frozen
risk threshold, the complete contract accepted 230 cases (63.9% coverage) and
retained 7 invalid outputs (3.04% risk). At the same 230-case coverage,
acquisition quality control retained 47 invalid outputs (20.43% risk), whereas
endpoint quality control retained 24 (10.43%). Absolute risk reductions were
17.39 and 7.39 percentage points, respectively. Across 5,000 region-level
bootstrap samples, the 95% intervals were 0.131–0.245 and 0.047–0.114 for the
two matched-risk differences; both risk–coverage-area intervals also excluded
zero. Clean-input coverage was 22 of 24 regions, with 7.29° median axial error.

Removing scale consistency increased risk–coverage area by 0.0521. Removing
alternating-frame consistency improved it slightly by 0.00035, so that
component is not claimed as necessary. Acquisition quality control produced no
operating point at the frozen risk cutoff; its matched-coverage comparison is a
stable score ranking, not a deployable threshold. A separate audit
implementation verified all 312 confirmation source files and exactly
reconstructed the split, scores, decisions, summaries and 5,000 bootstraps.
This result demonstrates selective validity under programmed shifts in one
deposited PSHG acquisition family, not independent-microscope transfer or
native clinical degradation.

**[Figure 5 near here: unstained PSHG acquisition-shift challenge, local orientation reference, selective-risk comparison and region-level uncertainty.]**
"""

PSHG_METHODS = """### PSHG acquisition-shift confirmation

PSHG-TISS was obtained from OSF record UDTQP[30]. The analyzed subset comprised
all 48 unstained-breast forward-SHG regions. Each 512 × 512-pixel field spans
125 × 125 µm and contains ten polarization frames. Reference support required
finite polarization orientation and fit diagnostics, coefficient of
determination at least 0.90, signal-to-noise ratio at least 3 dB, positive mean
FSHG intensity and an eight-pixel edge exclusion. These quantities were used
only to define adjudicable reference pixels, never to accept an output.

Regions were ordered by SHA-256 of the fixed salt and region name; the first 24
formed development and the remaining 24 confirmation. Perturbations were
applied in the frozen order blur, inter-frame motion, downsample-and-restore,
contrast and additive Gaussian noise. Noise seeds were derived from the frozen
seed, region, condition and frame. The primary estimator was the local
structure tensor at sigma 2 pixels. Comparators were the identical estimator
with acquisition QC only or with acquisition QC plus coherence, and upstream
sigma-4 tensor and smoothed-gradient estimators on clean images.

Development used four region-grouped folds, six quantile bins, Jeffreys
adjustment and monotone isotonic calibration. The complete raw support score
was the maximum of acquisition-QC, minimum-coherence, sigma-2-to-sigma-4
disagreement and alternating-frame disagreement components. The common
operating cutoff was calibrated risk at most 0.15. Confirmation compared
policies at their frozen threshold and at the exact complete-contract accepted
count. Risk–coverage area grouped tied scores. Percentile intervals resampled
the 24 regions with replacement for 5,000 draws. The independent audit did not
import the confirmation summary functions; it rehashed all artifacts and
source files, reconstructed every score and decision with independent
interpolation and repeated the bootstrap from the frozen seed.
"""

FIGURE5_LEGEND = (
    "**Figure 5 | A frozen input-only contract lowers silently invalid orientation outputs in unstained PSHG tissue.** "
    "**a,** Illustrative PSHG acquisition-shift and decision geometry; this text-free BioRender panel contains no microscopy "
    "or numerical data. **b,** Authentic clean forward-SHG, the severe compound shift, the deterministic NOSTOS local axial "
    "orientation field and the withheld polarization-derived reference for the first region in the frozen confirmation lock. "
    "**c,** Condition-by-policy acceptance; circle area encodes coverage, fill encodes invalidity among accepted cases and crosses "
    "denote no accepted cases. **d,** Tied-score risk–coverage curves. **e,** Invalid outputs among the same 230 accepted cases: "
    "47 for acquisition quality control, 24 for endpoint quality control and 7 for NOSTOS. **f,** Region-bootstrap differences "
    "for matched risk and risk–coverage area; positive values favor NOSTOS. Conditions are nested within 24 independent regions."
)


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w–-]+\b", text))


def move_figure_after_heading(text: str, figure_number: int, heading: str) -> str:
    """Place a large embedded figure before its result narrative.

    This prevents Word from leaving the preceding result page half empty while
    it moves an image-plus-caption unit to the next page.
    """
    marker_re = re.compile(rf"\n?\*\*\[Figure {figure_number} near here:[^\n]+\]\*\*\n?")
    match = marker_re.search(text)
    if match is None:
        raise RuntimeError(f"Figure {figure_number} placeholder is missing")
    marker = match.group(0).strip()
    text = text[: match.start()] + "\n" + text[match.end() :]
    heading_line = f"### {heading}"
    if heading_line not in text:
        raise RuntimeError(f"Heading is missing: {heading}")
    return text.replace(heading_line, heading_line + "\n\n" + marker, 1)


def move_figure_after_text(text: str, figure_number: int, anchor: str) -> str:
    """Place a figure after a specific narrative paragraph."""
    marker_re = re.compile(rf"\n?\*\*\[Figure {figure_number} near here:[^\n]+\]\*\*\n?")
    match = marker_re.search(text)
    if match is None:
        raise RuntimeError(f"Figure {figure_number} placeholder is missing")
    marker = match.group(0).strip()
    text = text[: match.start()] + "\n" + text[match.end() :]
    anchor_re = re.compile(r"\s+".join(re.escape(token) for token in anchor.split()))
    anchor_match = anchor_re.search(text)
    if anchor_match is None:
        raise RuntimeError(f"Figure {figure_number} anchor is missing")
    return text[: anchor_match.end()] + "\n\n" + marker + text[anchor_match.end() :]


def build_source() -> Path:
    if word_count(ABSTRACT) > 200:
        raise RuntimeError(f"Small Methods abstract exceeds 200 words: {word_count(ABSTRACT)}")
    if not 50 <= word_count(TOC_TEXT) <= 60:
        raise RuntimeError(f"Table-of-contents text must contain 50–60 words: {word_count(TOC_TEXT)}")
    text = V31_SOURCE.read_text(encoding="utf-8")
    abstract_start = text.index("## Abstract")
    intro_start = text.index("## Introduction")
    text = text[:abstract_start] + "## Abstract\n\n" + ABSTRACT + "\n\n" + text[intro_start:]
    text = text.replace(
        "### The software preserves failure as part of the result",
        PSHG_RESULTS.rstrip() + "\n\n### The software preserves failure as part of the result",
        1,
    )
    text = text.replace(
        "### Failure lineage and terminal audit",
        PSHG_METHODS.rstrip() + "\n\n### Failure lineage and terminal audit",
        1,
    )
    text = text.replace(
        "Hierarchical support made the failure explicit\nand prevented its recurrence in the untouched confirmation.",
        "Hierarchical support made the failure explicit and prevented its recurrence in the untouched confirmation. "
        "The PSHG challenge then tested the same governing idea on unstained tissue: a physically adjudicated local orientation "
        "field failed under controlled acquisition shifts, and an input-only contract removed most invalid outputs without "
        "inspecting the reference.",
        1,
    )
    text = text.replace(
        "The evidence has important limits. BioSR and FMD are public archives with their\nown reference constructions.",
        "The evidence has important limits. BioSR, FMD and PSHG-TISS are public archives with their own reference constructions.",
        1,
    )
    text = text.replace(
        "These boundaries\nare stated in the serialized profiles and must travel with any output.",
        "The PSHG result uses programmed shifts in previously characterized tissue from one microscope family; it is not a "
        "second-instrument or prospectively acquired degradation series. These boundaries are stated in the serialized profiles "
        "and must travel with any output.",
        1,
    )
    old_conclusion = (
        "NOSTOS makes the validity of a requested quantitative microscopy measurement an executable, versioned decision rather than an assumption. "
        "Across two independent public resources, the framework reduced silent-invalid outputs, exposed a pooled pass that concealed deterministic subgroup "
        "failure and prospectively removed that failure from untouched fields. The result is a practical fail-closed layer for calibrated microscopy measurements, "
        "bounded to the acquisitions and measurement coordinates on which its profile was established."
    )
    new_conclusion = (
        "NOSTOS makes the validity of a requested quantitative microscopy measurement an executable, versioned decision rather than an assumption. "
        "Across three public resources, the framework reduced silent-invalid outputs, exposed a pooled pass that concealed deterministic subgroup failure, "
        "removed that failure on untouched fields and transferred the selective-validity test to unstained PSHG tissue. The result is a practical fail-closed "
        "layer bounded to the acquisitions, instruments and measurement coordinates on which each profile was established."
    )
    text = text.replace(old_conclusion, new_conclusion, 1)
    text = text.replace(
        "FMD is available under CC BY-SA 4.0 at DOI 10.7274/r0-ed2r-4052; BioSR is available at DOI 10.6084/m9.figshare.13264793.",
        "FMD is available under CC BY-SA 4.0 at DOI 10.7274/r0-ed2r-4052; BioSR is available at DOI 10.6084/m9.figshare.13264793; PSHG-TISS is available at DOI 10.17605/OSF.IO/UDTQP.",
        1,
    )
    text = text.replace(
        "BioRender custom-figure generation produced the text-free illustrative workflow geometry in Figures 1b and 3d. These two schematic components",
        "BioRender custom-figure generation produced the text-free illustrative workflow geometry in Figures 1b, 3d and 5a. These three schematic components",
        1,
    )
    text = text.replace(
        "\n## References\n",
        "\n" + FIGURE5_LEGEND + "\n\n## References\n",
        1,
    )
    text = text.replace(
        "29. Maška, M. et al. The Cell Tracking Challenge: 10 years of objective benchmarking. *Nat. Methods* **20**, 1010–1020 (2023). https://doi.org/10.1038/s41592-023-01879-y",
        "29. Maška, M. et al. The Cell Tracking Challenge: 10 years of objective benchmarking. *Nat. Methods* **20**, 1010–1020 (2023). https://doi.org/10.1038/s41592-023-01879-y\n"
        "30. Hristu, R. et al. PSHG-TISS: a collection of polarization-resolved second harmonic generation microscopy images of fixed tissues. *Sci. Data* **9**, 376 (2022). https://doi.org/10.1038/s41597-022-01477-1",
        1,
    )
    toc_start = text.index("## Table of Contents")
    graphical = text.index("**[Graphical abstract near here]**", toc_start)
    text = text[:toc_start] + "## Table of Contents\n\n" + TOC_TEXT + "\n\n" + text[graphical:]
    text = move_figure_after_heading(text, 2, "A first prospective profile lowers tensor-coherence risk in BioSR")
    text = move_figure_after_heading(text, 4, "Hierarchical support removes the unsafe cell on untouched fields")
    text = move_figure_after_text(
        text,
        5,
        "native clinical degradation.",
    )
    if "Figure 5 near here" not in text or "10.17605/OSF.IO/UDTQP" not in text:
        raise RuntimeError("PSHG integration failed")
    SOURCE.write_text(text, encoding="utf-8")
    return SOURCE


def configure_builder() -> None:
    base.FIGURES = {
        "Figure 1 near here": FIGURE_DIR / "figure_1_measurement_to_decision.png",
        "Figure 2 near here": FIGURE_DIR / "figure_2_biosr_confirmation.png",
        "Figure 3 near here": FIGURE_DIR / "figure_3_hidden_conditional_failure.png",
        "Figure 4 near here": FIGURE_DIR / "figure_4_hierarchical_confirmation.png",
        "Figure 5 near here": PSHG_FIGURE,
        "Graphical abstract near here": FIGURE_DIR / "nostos_small_methods_toc.png",
    }
    base.FIGURE_ALT = {
        "Figure 1": "Authentic BioSR and FMD microscopy and deterministic measurement maps leading through a frozen NOSTOS support profile to emission or abstention.",
        "Figure 2": "BioSR perturbation outcomes, field-paired silent-invalid risk and risk-coverage behavior under acquisition quality control and NOSTOS.",
        "Figure 3": "FMD acquisition ladder and development and untouched-confirmation matrices localizing a fully invalid average-of-eight by eight-pixel measurement condition.",
        "Figure 4": "Four untouched FMD fields, the frozen hierarchical support lattice, matched quality-control errors, risk-coverage curves and finite-sample uncertainty.",
        "Figure 5": "Unstained PSHG workflow, authentic tissue images and local orientation fields, condition-level support, matched invalid counts and ROI-bootstrap intervals.",
        "Graphical abstract": "An authentic FMD image passes through deterministic orientation measurement and acquisition-by-scale support to an emit or abstain decision.",
    }
    base.FIGURE_WIDTHS = {"Figure 1": 6.82, "Figure 2": 6.82, "Figure 3": 6.82, "Figure 4": 6.82, "Figure 5": 6.10, "Graphical abstract": 6.40}
    base.HEADER_TEXT = ""
    base.DOC_TITLE = TITLE
    base.DOC_SUBJECT = "Small Methods submission candidate v32; computation-only public-data validation"
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
