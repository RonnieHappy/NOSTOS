"""Build the compact specimen-first Small Methods v36 manuscript."""

from __future__ import annotations

import re
from pathlib import Path

import build_nostos0_methods_docx as base
import build_nostos0_small_methods_docx_v35 as v35


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V36.md"
OUTPUT = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_ready_v36.docx"
FIGURE_DIR = ROOT / "figures" / "nostos0_small_methods_v36"


FIGURE1_LEGEND = (
    "**Figure 1. NOSTOS separates structural measurement from permission to report it.** "
    "**a,** Authentic BioSR input and paired reference and an authentic FMD input, with deterministic local orientation and coherence fields; coherence uses a common 0–1 display scale. "
    "**b,** BioSR tensor-coherence response across declared physical scales for one frozen confirmation example. "
    "**c,** The conservative FMD acquisition-by-scale support matrix; circles indicate supported requests and crosses unsupported requests. "
    "**d,** An authentic FMD image is converted to a deterministic orientation field, checked against the frozen support matrix and either emitted or withheld. FMD remains pixel-relative because physical spacing is unavailable. Every biological pixel originates in the cited public archives."
)

FIGURE2_LEGEND = (
    "**Figure 2. Selective support lowers silent-invalid risk in untouched BioSR fields.** "
    "**a,** A paired F-actin reference and ordinary-resolution input, their deterministic orientation field, and a controlled four-pixel blur challenge. "
    "**b,** Valid emissions, invalid emissions and withheld measurements across the frozen perturbation panel. "
    "**c,** Invalid-emission fractions paired within each of eight independent fields under acquisition quality control and NOSTOS. "
    "**d,** Tied-score risk–coverage curves and frozen operating points. Perturbations, requested scales and signal levels remain nested within fields."
)


def replace_legend(text: str, number: int, replacement: str) -> str:
    pattern = rf"(?s)\*\*Figure {number}\..*?(?=\n\n\*\*Figure {number + 1}\.|\n\n## References)"
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not replace Figure {number} legend.")
    return updated


def move_figure_after(text: str, marker: str, anchor: str) -> str:
    """Place a figure after the prose that establishes its result.

    This mirrors the compact evidence-first flow in the supplied Small Methods
    papers and prevents a large keep-together figure from stranding the next
    result section on a new page.  It changes pagination only.
    """
    block = f"**[{marker}]**"
    if text.count(block) != 1:
        raise RuntimeError(f"Expected one figure marker: {marker}")
    text = text.replace("\n\n" + block + "\n\n", "\n\n", 1)
    position = text.find(anchor)
    if position < 0:
        raise RuntimeError(f"Could not find figure-flow anchor: {anchor}")
    position += len(anchor)
    return text[:position] + "\n\n" + block + text[position:]


def build_source() -> Path:
    v35.SOURCE = SOURCE
    text_path = v35.build_source()
    text = text_path.read_text(encoding="utf-8")
    text = replace_legend(text, 1, FIGURE1_LEGEND)
    text = replace_legend(text, 2, FIGURE2_LEGEND)
    text = text.replace(
        "BioRender was used only to explore data-free workflow layouts; those exploratory panels are not present in the final main figures.",
        "BioRender was used only to create a data-free optical-acquisition component for a separately versioned SHG workflow asset. No BioRender-generated microscopy, mask, result map or numerical output appears in the main figures.",
        1,
    )
    text = move_figure_after(
        text,
        "Figure 1 near here: measurement contract, real microscopy inputs, response coordinates, compilation and fail-closed deployment.",
        "on which the validity machinery can operate[13–26].",
    )
    text = move_figure_after(
        text,
        "Figure 2 near here: BioSR fields, controlled degradation, risk–coverage behavior and enrichment of rejected invalid measurements.",
        "preserving useful coverage.",
    )
    text = move_figure_after(
        text,
        "Figure 3 near here: FMD acquisition ladder, seven-field extension errors, four-cell failure, conservative three-cell repair and independent-field uncertainty.",
        "This is a narrowed development profile, not another confirmation.",
    )
    text = move_figure_after(
        text,
        "Figure 4 near here: authentic certified and external FMD images, deterministic coherence fields, per-field transfer failures and executable claim-boundary containment.",
        "NOSTOS therefore serializes not only a threshold, but also the domain in which that threshold is permitted to act.",
    )
    text_path.write_text(text, encoding="utf-8")
    return text_path


def configure_builder() -> None:
    v35.FIGURE_DIR = FIGURE_DIR
    v35.configure_builder()
    base.FIGURES.update(
        {
            "Figure 1 near here": FIGURE_DIR / "figure_1_measurement_contract.png",
            "Figure 2 near here": FIGURE_DIR / "figure_2_biosr_confirmation.png",
            "Figure 3 near here": FIGURE_DIR / "figure_3_falsification_and_repair.png",
            "Figure 4 near here": FIGURE_DIR / "figure_4_external_domain_failure.png",
            "Graphical abstract near here": FIGURE_DIR / "nostos_small_methods_toc.png",
        }
    )
    base.FIGURE_ALT.update(
        {
            "Figure 1": "Authentic BioSR and FMD microscopy with deterministic orientation and coherence fields, physical scale response, acquisition-by-scale support and emit-or-withhold measurement rail.",
            "Figure 2": "Authentic BioSR reference and input images, controlled blur, condition-level validity composition, paired field risk and tied-score risk-coverage curves.",
            "Figure 3": "Authentic FMD acquisition ladder, accepted errors in seven untouched fields, failed four-cell support, conservative three-cell development repair and exact field uncertainty.",
            "Figure 4": "Authentic certified and external FMD images with common-scale coherence fields, failed no-refit transfer by field and post-failure claim-boundary containment.",
        }
    )
    base.FIGURE_WIDTHS.update(
        {"Figure 1": 6.25, "Figure 2": 6.25, "Figure 3": 6.25, "Figure 4": 6.25}
    )
    base.DOC_SUBJECT = "Small Methods compact specimen-first submission candidate v36; computation-only public-data validation"


def main() -> None:
    source = build_source()
    configure_builder()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    missing = [str(path) for path in base.FIGURES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(missing)
    print(base.build(source, OUTPUT))
    print(f"abstract_words={v35.word_count(v35.ABSTRACT)}")
    print(f"toc_words={v35.word_count(v35.TOC_TEXT)}")


if __name__ == "__main__":
    main()
