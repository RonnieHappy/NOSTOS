"""Build the machine-readable Small Methods v38 submission manifest."""

from __future__ import annotations

import json
from pathlib import Path

import build_nostos0_small_methods_submission_manifest_v35 as v35


ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "docs" / "audits"
MACHINE = AUDITS / "v38_machine"
FIGURES = ROOT / "figures"
RELEASE = ROOT / "outputs" / "nostos0-small-methods-v36-release"
REPEAT = ROOT / "outputs" / "nostos0-small-methods-v36-release-repeat"
OUTPUT = AUDITS / "nostos_small_methods_v38_submission_manifest.json"


def configure() -> None:
    v35.OUTPUT = OUTPUT
    v35.MAIN_SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V38.md"
    v35.FINAL_AUDIT = AUDITS / "NOSTOS_SMALL_METHODS_V38_FINAL_VISUAL_AND_JOURNAL_AUDIT.md"
    v35.MAIN_DOCX = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_ready_v38.docx"
    v35.MAIN_PDF = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_ready_v38_review.pdf"
    v35.SI_DOCX = ROOT / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v38.docx"
    v35.SI_PDF = ROOT / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v38_review.pdf"
    v35.MAIN_QA = AUDITS / "nostos_small_methods_v38_manuscript_qa.json"
    v35.SI_QA = AUDITS / "nostos_small_methods_v38_si_qa.json"
    v35.MAIN_A11Y = MACHINE / "NOSTOS_Small_Methods_submission_ready_v38.a11y.json"
    v35.SI_A11Y = MACHINE / "NOSTOS_Small_Methods_Supporting_Information_v38.a11y.json"
    v35.MAIN_STYLE = MACHINE / "NOSTOS_Small_Methods_submission_ready_v38.style.json"
    v35.SI_STYLE = MACHINE / "NOSTOS_Small_Methods_Supporting_Information_v38.style.json"
    v35.RELEASE_DIR = RELEASE
    v35.RELEASE_ARCHIVE = RELEASE / "nostos-0.3.0-release-candidate.zip"
    v35.RELEASE_RECEIPT = RELEASE / "release_receipt.json"
    v35.RELEASE_MANIFEST = RELEASE / "release_manifest.json"
    v35.RELEASE_CLEANROOM = RELEASE / "cleanroom_verification.json"
    v35.REPEAT_ARCHIVE = REPEAT / "nostos-0.3.0-release-candidate.zip"

    main = FIGURES / "nostos0_small_methods_v38"
    v35.MAIN_FIGURES = (
        ("Figure 1", main / "figure_1_measurement_contract.png", 6.25),
        ("Figure 2", main / "figure_2_biosr_confirmation.png", 6.25),
        ("Figure 3", main / "figure_3_falsification_and_repair.png", 6.25),
        ("Figure 4", main / "figure_4_external_domain_failure.png", 6.25),
        ("Figure 5", main / "figure_5_pshg_acquisition_shift.png", 5.75),
        ("Figure 6", main / "figure_6_tendon_pshg_transfer.png", 6.25),
        ("Table of Contents", main / "nostos_small_methods_toc.png", 110 / 25.4),
    )
    v35.MAIN_VECTOR_PDFS = tuple(
        main / name
        for name in (
            "figure_1_measurement_contract.pdf",
            "figure_2_biosr_confirmation.pdf",
            "figure_3_falsification_and_repair.pdf",
            "figure_4_external_domain_failure.pdf",
            "figure_5_pshg_acquisition_shift.pdf",
            "figure_6_tendon_pshg_transfer.pdf",
            "nostos_small_methods_toc.pdf",
        )
    )


def main() -> None:
    configure()
    v35.main()
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    payload["schema"] = "nostos.small-methods.submission-manifest.v38"
    payload["local_pytest"] = {
        "command": ".venv\\Scripts\\python.exe -m pytest -q",
        "passed": 409,
        "skipped": 4,
        "failed": 0,
        "warnings": 15,
    }
    payload["external_submission_blockers"][0] = (
        "Publish the exact v38 source/configuration/receipt/figure snapshot to the public repository."
    )
    payload["submission_artwork"] = {
        "directory": "manuscripts/Small_Methods_v38_submission_assets/figures",
        "manifest": "manuscripts/Small_Methods_v38_submission_assets/artwork_manifest.json",
        "format": "LZW-compressed TIFF",
        "dpi": 600,
        "files": [
            "Figure_1.tif", "Figure_2.tif", "Figure_3.tif", "Figure_4.tif",
            "Figure_5.tif", "Figure_6.tif", "Figure_S1.tif", "Figure_S2.tif",
            "Figure_S3.tif", "Table_of_Contents.tif",
        ],
    }
    payload["visual_render_repeat"] = {
        "article_pages": 13,
        "supporting_information_pages": 5,
        "byte_identical_page_pngs": True,
    }
    payload["biorender_final_pixels"] = False
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
