"""Build the journal-density Small Methods v37 editable manuscript."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import build_nostos0_methods_docx as base
import build_nostos0_small_methods_docx_v36 as v36
from docx import Document


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V37.md"
OUTPUT = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_ready_v37.docx"
FIGURE_DIR = ROOT / "figures" / "nostos0_small_methods_v37"


FIGURE1_LEGEND = (
    "**Figure 1. NOSTOS separates structural measurement from permission to report it.** "
    "**a,** Authentic BioSR input and paired reference with deterministic local orientation and coherence fields. "
    "**b,** Authentic FMD input with the same deterministic fields; coherence uses the common 0–1 display scale. "
    "**c,** BioSR tensor-coherence response across declared physical scales for one frozen confirmation example. "
    "**d,** Conservative FMD acquisition-by-scale support; circles indicate supported requests and crosses unsupported requests. "
    "**e,** An authentic FMD image is converted to an orientation field, checked against the frozen support matrix and either emitted or withheld. FMD remains pixel-relative because physical spacing is unavailable. Every biological pixel originates in the cited public archives."
)

FIGURE3_LEGEND = (
    "**Figure 3. Prospective falsification localizes an unsafe acquisition-by-scale cell and constrains its repair.** "
    "**a,** One authentic FMD field across the capture ladder from the raw acquisition to the average-of-50 reference. "
    "**b,** Accepted average-of-8 by 16-pixel tensor-coherence errors in seven untouched fields; the dashed line is the frozen invalidity threshold and red points are invalid emissions. "
    "**c,** Support before and after the repair. The average-of-8 by 16-pixel cell changed from supported but unsafe (red) to withheld (gray); the remaining three average-of-16 cells were retained. "
    "**d,** Exact field-event estimates: the prospective extension failed in 2 of 7 fields, whereas the narrowed development profile had 0 observed events in 19 opened fields. The latter remains development-only, not a new confirmation."
)


def replace_legend(text: str, number: int, replacement: str) -> str:
    pattern = rf"(?s)\*\*Figure {number}\..*?(?=\n\n\*\*Figure {number + 1}\.|\n\n## References)"
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not replace Figure {number} legend.")
    return updated


def build_source() -> Path:
    v36.SOURCE = SOURCE
    text_path = v36.build_source()
    text = text_path.read_text(encoding="utf-8")
    text = replace_legend(text, 1, FIGURE1_LEGEND)
    text = replace_legend(text, 3, FIGURE3_LEGEND)
    text = text.replace(
        "BioRender was used only to create a data-free optical-acquisition component for a separately versioned SHG workflow asset. No BioRender-generated microscopy, mask, result map or numerical output appears in the main figures.",
        "BioRender was used to explore a data-free composition for the Figure 1 measurement rail and to create a separately versioned optical-acquisition asset. The submitted Figure 1 rail was rebuilt deterministically with the authentic FMD image, the deterministic orientation field and the frozen support matrix. No BioRender-generated microscopy, mask, result map or numerical output appears in the manuscript.",
        1,
    )
    text_path.write_text(text, encoding="utf-8")
    return text_path


def configure_builder() -> None:
    v36.FIGURE_DIR = FIGURE_DIR
    v36.configure_builder()
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
            "Figure 1": "Authentic BioSR and FMD microscopy with deterministic orientation and coherence fields, physical-scale response, acquisition-by-scale support and a minimal emit-or-withhold measurement rail.",
            "Figure 2": "Authentic BioSR reference and input images, controlled blur, condition-level validity composition, paired field risk and tied-score risk-coverage curves.",
            "Figure 3": "Authentic FMD acquisition ladder, accepted errors in seven untouched fields, unsafe-cell removal and exact field-event intervals for prospective failure and narrowed development repair.",
            "Figure 4": "Authentic certified and external FMD images with common-scale coherence fields, failed no-refit transfer by field and post-failure claim-boundary containment.",
        }
    )
    base.FIGURE_WIDTHS.update(
        {"Figure 1": 6.25, "Figure 2": 6.25, "Figure 3": 6.25, "Figure 4": 6.25}
    )
    base.DOC_SUBJECT = "Small Methods journal-density submission candidate v37; computation-only public-data validation"


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
    print(f"abstract_words={v36.v35.word_count(v36.v35.ABSTRACT)}")
    print(f"toc_words={v36.v35.word_count(v36.v35.TOC_TEXT)}")


if __name__ == "__main__":
    main()
