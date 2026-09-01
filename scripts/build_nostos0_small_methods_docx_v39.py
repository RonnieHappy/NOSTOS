"""Build the journal-polished Small Methods v39 editable manuscript."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

import build_nostos0_methods_docx as base
import build_nostos0_small_methods_docx_v38 as v38


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V39.md"
OUTPUT = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_ready_v39.docx"
FIGURE_DIR = ROOT / "figures" / "nostos0_small_methods_v39"


def _set_rfonts(rfonts) -> None:
    for name in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(qn(f"w:{name}"), "Times New Roman")
    for name in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        rfonts.attrib.pop(qn(f"w:{name}"), None)


def normalize_all_style_fonts(doc: Document) -> None:
    """Remove dormant template font drift, including styles not yet visible."""
    for style in doc.styles:
        rpr = style._element.get_or_add_rPr()
        _set_rfonts(rpr.get_or_add_rFonts())
    defaults = doc.styles.element.xpath("./w:docDefaults/w:rPrDefault/w:rPr/w:rFonts")
    for rfonts in defaults:
        _set_rfonts(rfonts)


def build_source() -> Path:
    prior = v38.build_source()
    SOURCE.write_text(prior.read_text(encoding="utf-8"), encoding="utf-8")
    return SOURCE


def configure_builder() -> None:
    v38.FIGURE_DIR = FIGURE_DIR
    v38.configure_builder()
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
    base.DOC_SUBJECT = "Small Methods final journal-polished submission candidate v39; computation-only public-data validation"


def main() -> None:
    source = build_source()
    configure_builder()
    missing = [str(path) for path in base.FIGURES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(missing)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    built = base.build(source, OUTPUT)
    doc = Document(built)
    normalize_all_style_fonts(doc)
    props = doc.core_properties
    props.last_modified_by = base.DOC_AUTHOR
    props.revision = 1
    props.created = datetime(2026, 8, 31, tzinfo=timezone.utc)
    props.modified = datetime(2026, 8, 31, tzinfo=timezone.utc)
    doc.save(built)
    print(built)


if __name__ == "__main__":
    main()
