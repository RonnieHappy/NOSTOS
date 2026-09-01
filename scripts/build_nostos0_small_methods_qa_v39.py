"""Build machine-readable production QA receipts for Small Methods v39."""

from __future__ import annotations

from pathlib import Path

from nostos.validation.manuscript_qa import build_manuscript_qa

import build_nostos0_small_methods_qa_v38 as v38


ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "docs" / "audits"


def build_one(*, source: Path, docx: Path, render_dir: Path, pdf: Path, output: Path,
              pages: int, media: int, required_text: tuple[str, ...]) -> None:
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
        source=ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V39.md",
        docx=ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_ready_v39.docx",
        render_dir=ROOT / "manuscripts" / "NOSTOS_Small_Methods_v39_visual_qa",
        pdf=ROOT / "manuscripts" / "NOSTOS_Small_Methods_v39_visual_qa" / "NOSTOS_Small_Methods_submission_ready_v39.pdf",
        output=AUDITS / "nostos_small_methods_v39_manuscript_qa.json",
        pages=13,
        media=8,
        required_text=v38.MAIN_REQUIRED,
    )
    build_one(
        source=ROOT / "scripts" / "build_nostos0_small_methods_si_v39.py",
        docx=ROOT / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v39.docx",
        render_dir=ROOT / "manuscripts" / "NOSTOS_Small_Methods_SI_v39_visual_qa",
        pdf=ROOT / "manuscripts" / "NOSTOS_Small_Methods_SI_v39_visual_qa" / "NOSTOS_Small_Methods_Supporting_Information_v39.pdf",
        output=AUDITS / "nostos_small_methods_v39_si_qa.json",
        pages=5,
        media=4,
        required_text=v38.SI_REQUIRED,
    )
    print("v39 manuscript and Supporting Information production QA: pass")


if __name__ == "__main__":
    main()
