"""Build the final visually audited Small Methods v38 editable manuscript."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from docx import Document

import build_nostos0_methods_docx as base
import build_nostos0_small_methods_docx_v37 as v37


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V38.md"
OUTPUT = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_ready_v38.docx"
FIGURE_DIR = ROOT / "figures" / "nostos0_small_methods_v38"


FIGURE1_LEGEND = (
    "**Figure 1. NOSTOS separates structural measurement from permission to report it.** "
    "**a,** Authentic BioSR input and paired reference with deterministic local orientation and coherence fields. "
    "**b,** Authentic FMD input with the same deterministic fields; coherence uses the common 0–1 display scale. "
    "**c,** BioSR tensor-coherence response across declared physical scales for one frozen confirmation example. "
    "**d,** Conservative FMD acquisition-by-scale support; circles indicate supported requests and crosses unsupported requests. "
    "**e,** An authentic FMD image is converted to an orientation field, checked against the frozen support matrix and either emitted or withheld. "
    "Scale bars in the calibrated BioSR reference panels are 10 µm. FMD remains pixel-relative because physical spacing is unavailable. "
    "Every biological pixel originates in the cited public archives."
)

FIGURE2_LEGEND = (
    "**Figure 2. Selective support lowers silent-invalid risk in untouched BioSR fields.** "
    "**a,** A paired F-actin reference and ordinary-resolution input, their deterministic orientation field, and a controlled four-pixel blur challenge; scale bars are 10 µm. "
    "**b,** Valid emissions, invalid emissions and withheld measurements across the frozen perturbation panel. "
    "**c,** Invalid-emission fractions paired within each of eight independent fields under acquisition quality control and NOSTOS. "
    "**d,** Tied-score risk–coverage curves and frozen operating points. Perturbations, requested scales and signal levels remain nested within fields."
)


def replace_legend(text: str, number: int, replacement: str) -> str:
    pattern = rf"(?s)\*\*Figure {number}\..*?(?=\n\n\*\*Figure {number + 1}\. |\n\n## References)"
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not replace Figure {number} legend.")
    return updated


def build_source() -> Path:
    # Reuse the evidence-locked v37 prose, then create a new source rather than
    # mutating the prior release candidate.
    source_v37 = v37.build_source()
    text = source_v37.read_text(encoding="utf-8")
    text = replace_legend(text, 1, FIGURE1_LEGEND)
    text = replace_legend(text, 2, FIGURE2_LEGEND)
    text = text.replace(
        "BioRender was used to explore a data-free composition for the Figure 1 measurement rail and to create a separately versioned optical-acquisition asset.",
        "BioRender was used only to explore a data-free composition for the Figure 1 measurement rail and to create a separately versioned optical-acquisition asset.",
        1,
    )
    SOURCE.write_text(text, encoding="utf-8")
    return SOURCE


def configure_builder() -> None:
    v37.FIGURE_DIR = FIGURE_DIR
    v37.configure_builder()
    base.FIGURES.update(
        {
            "Figure 1 near here": FIGURE_DIR / "figure_1_measurement_contract.png",
            "Figure 2 near here": FIGURE_DIR / "figure_2_biosr_confirmation.png",
            "Figure 3 near here": FIGURE_DIR / "figure_3_falsification_and_repair.png",
            "Figure 4 near here": FIGURE_DIR / "figure_4_external_domain_failure.png",
            "Figure 5 near here": FIGURE_DIR / "figure_5_pshg_acquisition_shift.png",
            "Figure 6 near here": FIGURE_DIR / "figure_6_tendon_pshg_transfer.png",
            "Graphical abstract near here": FIGURE_DIR / "nostos_small_methods_toc.png",
        }
    )
    base.FIGURE_ALT.update(
        {
            "Figure 1": "Authentic BioSR and FMD microscopy with deterministic orientation and coherence fields, calibrated physical-scale response, acquisition-by-scale support and an emit-or-withhold measurement rail.",
            "Figure 2": "Authentic calibrated BioSR reference and input images, controlled blur, condition-level validity composition, paired field risk and tied-score risk-coverage curves.",
            "Figure 3": "Authentic FMD acquisition ladder, accepted errors in seven untouched fields, unsafe-cell removal and exact field-event intervals for prospective failure and narrowed development repair.",
            "Figure 4": "Authentic certified and external FMD images with common-scale coherence fields, failed no-refit transfer by field and post-failure claim-boundary containment.",
            "Figure 5": "Authentic forward-SHG tissue, controlled acquisition shift, NOSTOS and polarization-derived orientation maps, condition-by-policy support, matched invalid outputs and bootstrap comparisons.",
            "Figure 6": "Authentic tendon SHG, NOSTOS orientation and coherence, polarization-resolved reference maps, organization recovery, matched invalid outputs and tied-score risk-coverage curves.",
            "Graphical abstract": "An authentic FMD image passes through deterministic orientation measurement and acquisition-by-scale support to an emit or abstain decision.",
        }
    )
    base.FIGURE_WIDTHS.update(
        {
            "Figure 1": 6.25,
            "Figure 2": 6.25,
            "Figure 3": 6.25,
            "Figure 4": 6.25,
            "Figure 5": 5.75,
            "Figure 6": 6.25,
            "Graphical abstract": 4.33,
        }
    )
    base.DOC_SUBJECT = "Small Methods final visually audited submission candidate v38; computation-only public-data validation"


def main() -> None:
    source = build_source()
    configure_builder()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    missing = [str(path) for path in base.FIGURES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(missing)
    built = base.build(source, OUTPUT)
    doc = Document(built)
    props = doc.core_properties
    props.last_modified_by = base.DOC_AUTHOR
    props.revision = 1
    props.created = datetime(2026, 8, 31, tzinfo=timezone.utc)
    props.modified = datetime(2026, 8, 31, tzinfo=timezone.utc)
    doc.save(built)
    print(built)
    print(f"abstract_words={v37.v36.v35.word_count(v37.v36.v35.ABSTRACT)}")
    print(f"toc_words={v37.v36.v35.word_count(v37.v36.v35.TOC_TEXT)}")


if __name__ == "__main__":
    main()
