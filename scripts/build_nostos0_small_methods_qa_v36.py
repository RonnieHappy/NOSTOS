"""Build machine-readable production QA receipts for Small Methods v36."""

from __future__ import annotations

from pathlib import Path

from nostos.validation.manuscript_qa import build_manuscript_qa


ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "docs" / "audits"


MAIN_REQUIRED = (
    "NOSTOS Exposes and Contains Acquisition-, Scale- and Sample-Specific Failure in Quantitative Microscopy",
    "Abstract",
    "1. Introduction",
    "2. Results and Discussion",
    "3. Conclusion",
    "4. Experimental Section",
    "Figure 1.",
    "Figure 2.",
    "Figure 3.",
    "Figure 4.",
    "Figure 5.",
    "Figure 6.",
    "Data Availability Statement",
    "Author Contributions",
    "Conflict of Interest",
    "References",
    "Table of Contents",
)

SI_REQUIRED = (
    "Supporting Information",
    "S1. Synthetic truth and perturbation validation",
    "Figure S1.",
    "S2. External network measurement on STARE reference masks",
    "S3. External trabecular-bone local thickness",
    "Figure S2.",
    "S4. Dynamic deformation and spatial-response confirmations",
    "S5. Label-free and three-dimensional bone stress tests",
    "Figure S3.",
    "S6. Frozen receipt index",
    "S7. Resource identifiers and scope",
)


def build_one(
    *,
    source: Path,
    docx: Path,
    render_dir: Path,
    pdf: Path,
    output: Path,
    pages: int,
    media: int,
    required_text: tuple[str, ...],
) -> None:
    payload = build_manuscript_qa(
        project_root=ROOT,
        manuscript_source=source,
        docx_path=docx,
        render_dir=render_dir,
        pdf_path=pdf,
        output_path=output,
        expected_pages=pages,
        expected_media=media,
        visual_review_passed=True,
        visual_review_date="2026-08-31",
        required_text=required_text,
    )
    if payload["status"] != "pass":
        raise RuntimeError(f"Production QA failed: {output}")


def main() -> None:
    AUDITS.mkdir(parents=True, exist_ok=True)
    build_one(
        source=ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V36.md",
        docx=ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_ready_v36.docx",
        render_dir=ROOT / "manuscripts" / "NOSTOS_Small_Methods_v36_visual_qa2",
        pdf=ROOT / "manuscripts" / "NOSTOS_Small_Methods_v36_visual_qa2" / "NOSTOS_Small_Methods_submission_ready_v36.pdf",
        output=AUDITS / "nostos_small_methods_v36_manuscript_qa.json",
        pages=13,
        media=8,
        required_text=MAIN_REQUIRED,
    )
    build_one(
        source=ROOT / "scripts" / "build_nostos0_small_methods_si_v36.py",
        docx=ROOT / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v36.docx",
        render_dir=ROOT / "manuscripts" / "NOSTOS_Small_Methods_SI_v36_visual_qa1",
        pdf=ROOT / "manuscripts" / "NOSTOS_Small_Methods_SI_v36_visual_qa1" / "NOSTOS_Small_Methods_Supporting_Information_v36.pdf",
        output=AUDITS / "nostos_small_methods_v36_si_qa.json",
        pages=5,
        media=4,
        required_text=SI_REQUIRED,
    )
    print("v36 manuscript and Supporting Information production QA: pass")


if __name__ == "__main__":
    main()
