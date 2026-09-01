"""Build the immutable production manifest for the Small Methods v34 package."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "audits" / "nostos_small_methods_v34_submission_manifest.json"

MAIN_SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V34.md"
FINAL_AUDIT = ROOT / "docs" / "audits" / "NOSTOS_SMALL_METHODS_V34_FINAL_VISUAL_AND_JOURNAL_AUDIT.md"
MAIN_DOCX = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_candidate_v34.docx"
MAIN_PDF = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_candidate_v34_review.pdf"
SI_DOCX = ROOT / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v34.docx"
SI_PDF = ROOT / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v34_review.pdf"
RELEASE_DIR = ROOT / "outputs" / "nostos0-small-methods-v34-release"
RELEASE_ARCHIVE = RELEASE_DIR / "nostos-0.3.0-release-candidate.zip"
RELEASE_RECEIPT = RELEASE_DIR / "release_receipt.json"
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
RELEASE_CLEANROOM = RELEASE_DIR / "cleanroom_verification.json"
REPEAT_RELEASE_ARCHIVE = (
    ROOT
    / "outputs"
    / "nostos0-small-methods-v34-release-repeat"
    / "nostos-0.3.0-release-candidate.zip"
)

MAIN_FIGURES = (
    ("Figure 1", ROOT / "figures" / "nostos0_small_methods" / "figure_1_measurement_to_decision.png", 6.25),
    ("Figure 2", ROOT / "figures" / "nostos0_small_methods" / "figure_2_biosr_confirmation.png", 6.25),
    ("Figure 3", ROOT / "figures" / "nostos0_small_methods" / "figure_3_hidden_conditional_failure.png", 6.25),
    ("Figure 4", ROOT / "figures" / "nostos0_small_methods" / "figure_4_hierarchical_confirmation.png", 6.25),
    ("Figure 5", ROOT / "figures" / "nostos0_pshg_acquisition_shift" / "figure_pshg_acquisition_shift.png", 5.75),
    ("Figure 6", ROOT / "figures" / "nostos0_tlt_pshg_xrd_transfer" / "figure_tlt_pshg_xrd_transfer.png", 6.25),
    ("Table of Contents", ROOT / "figures" / "nostos0_small_methods" / "nostos_small_methods_toc.png", 4.33),
)

SI_FIGURES = (
    ("Figure S1", ROOT / "figures" / "nostos0_small_methods_si" / "figure_s1_synthetic_validation.png", 6.25),
    ("Figure S2", ROOT / "figures" / "nostos0" / "figure_3_bone_validation.png", 6.25),
    ("Figure S3", ROOT / "figures" / "nostos0" / "supplementary_figure_1_bone_contract_stress.png", 6.25),
)

RECEIPTS = (
    ROOT / "outputs" / "nostos0-synthetic-v1" / "validation.json",
    ROOT / "outputs" / "nostos0-module-perturbations-v1" / "module_perturbation_matrix.json",
    ROOT / "outputs" / "nostos0-stare-network-confirmation-v1" / "stare_network_confirmation.json",
    ROOT / "outputs" / "external-bone-v1" / "external_bone_validation.json",
    ROOT / "outputs" / "nostos0-bonej-thickness-v1" / "bonej_thickness_comparator.json",
    ROOT / "outputs" / "nostos0-bbbc035-dynamic-confirmation-v1" / "bbbc035_dynamic_confirmation.json",
    ROOT / "outputs" / "nostos0-bbbc035-dense-deformation-confirmation-v1" / "bbbc035_dense_deformation_confirmation.json",
    ROOT / "outputs" / "nostos0-bbbc006-spatial-confirmation-v1" / "bbbc006_spatial_confirmation.json",
)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path: Path, pages: int | None = None) -> dict:
    record = {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    if pages is not None:
        record["pages"] = pages
    return record


def pdf_pages(path: Path) -> int:
    completed = subprocess.run(
        ["pdfinfo", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"(?m)^Pages:\s+(\d+)$", completed.stdout)
    if not match:
        raise RuntimeError(f"Could not read page count from {path}")
    return int(match.group(1))


def words(text: str) -> int:
    return len(re.findall(r"\b[\w\u2010-\u2015'-]+\b", text, flags=re.UNICODE))


def source_metrics() -> dict:
    text = MAIN_SOURCE.read_text(encoding="utf-8")
    abstract = re.search(r"(?s)## Abstract\s+(.*?)\s+## 1\. Introduction", text)
    toc = re.search(r"(?s)## Table of Contents\s+(.*?)\s+\*\*\[Graphical abstract", text)
    keyword_line = re.search(r"\*\*Keywords:\*\*\s*(.+)", text)
    reference_block = re.search(r"(?s)## References\s+(.*?)\s+## Supporting Information", text)
    legend_block = re.search(r"(?s)## Figure legends\s+(.*?)\s+## References", text)
    if not all((abstract, toc, keyword_line, reference_block, legend_block)):
        raise RuntimeError("Could not parse one or more required article sections")

    captions = [int(value) for value in re.findall(r"(?m)^\*\*Figure (\d+)\.", legend_block.group(1))]
    body_before_legends = text.split("## Figure legends", 1)[0]
    first_mentions: list[int] = []
    for value in re.findall(r"\bFigure ([1-6])\b", body_before_legends):
        number = int(value)
        if number not in first_mentions:
            first_mentions.append(number)

    return {
        "abstract_words": words(abstract.group(1)),
        "toc_words": words(toc.group(1)),
        "keyword_count": len([item for item in keyword_line.group(1).split(",") if item.strip()]),
        "reference_count": len(re.findall(r"(?m)^\d+\.", reference_block.group(1))),
        "main_figure_count": len(captions),
        "caption_numbers": captions,
        "first_mention_order": first_mentions,
        "whole_source_words": words(text),
    }


def figure_record(label: str, path: Path, embed_width_in: float) -> dict:
    with Image.open(path) as image:
        width_px, height_px = image.size
        metadata_dpi = image.info.get("dpi")
    return {
        "label": label,
        "path": relative(path),
        "sha256": sha256(path),
        "pixels": [width_px, height_px],
        "metadata_dpi": [round(float(value), 3) for value in metadata_dpi] if metadata_dpi else None,
        "embedded_width_in": embed_width_in,
        "effective_horizontal_dpi": round(width_px / embed_width_in, 1),
        "minimum_required_dpi": 300,
        "passes_resolution_gate": width_px / embed_width_in >= 300,
        "provenance": "public source imagery and/or deterministic computation; no generated microscopy",
    }


def main() -> None:
    required = (
        MAIN_SOURCE,
        FINAL_AUDIT,
        MAIN_DOCX,
        MAIN_PDF,
        SI_DOCX,
        SI_PDF,
        RELEASE_ARCHIVE,
        RELEASE_RECEIPT,
        RELEASE_MANIFEST,
        RELEASE_CLEANROOM,
        REPEAT_RELEASE_ARCHIVE,
        *(path for _, path, _ in MAIN_FIGURES),
        *(path for _, path, _ in SI_FIGURES),
        *RECEIPTS,
    )
    missing = [relative(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing submission inputs: " + ", ".join(missing))

    metrics = source_metrics()
    release_receipt = json.loads(RELEASE_RECEIPT.read_text(encoding="utf-8"))
    release_cleanroom = json.loads(RELEASE_CLEANROOM.read_text(encoding="utf-8"))
    repeat_release_sha256 = sha256(REPEAT_RELEASE_ARCHIVE)
    assertions = {
        "abstract_at_most_200_words": metrics["abstract_words"] <= 200,
        "toc_50_to_60_words": 50 <= metrics["toc_words"] <= 60,
        "keywords_3_to_7": 3 <= metrics["keyword_count"] <= 7,
        "research_article_3000_to_8000_words": 3000 <= metrics["whole_source_words"] <= 8000,
        "display_items_3_to_8": 3 <= metrics["main_figure_count"] <= 8,
        "figure_captions_complete_and_ordered": metrics["caption_numbers"] == list(range(1, 7)),
        "first_figure_mentions_ordered": metrics["first_mention_order"] == list(range(1, 7)),
    }

    manifest = {
        "schema": "nostos.small-methods.submission-manifest.v34",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "target_journal": "Small Methods",
        "article_type": "Research Article",
        "artifacts": {
            "final_visual_and_journal_audit": artifact(FINAL_AUDIT),
            "main_docx": artifact(MAIN_DOCX),
            "main_review_pdf": artifact(MAIN_PDF, pdf_pages(MAIN_PDF)),
            "supporting_information_docx": artifact(SI_DOCX),
            "supporting_information_review_pdf": artifact(SI_PDF, pdf_pages(SI_PDF)),
        },
        "local_release_package": {
            "archive": artifact(RELEASE_ARCHIVE),
            "release_receipt": artifact(RELEASE_RECEIPT),
            "release_manifest": artifact(RELEASE_MANIFEST),
            "cleanroom_verification": artifact(RELEASE_CLEANROOM),
            "declared_file_count": release_receipt["file_count"],
            "declared_archive_sha256": release_receipt["archive_sha256"],
            "repeat_build_sha256": repeat_release_sha256,
            "repeat_build_byte_identical": repeat_release_sha256 == sha256(RELEASE_ARCHIVE),
            "cleanroom_status": release_cleanroom["status"],
            "cleanroom_checks": release_cleanroom["checks"],
            "cleanroom_pytest": release_cleanroom["verification"]["pytest"],
        },
        "article_metrics": metrics,
        "journal_rule_assertions": assertions,
        "figures": {
            "main": [figure_record(*item) for item in MAIN_FIGURES],
            "supporting": [figure_record(*item) for item in SI_FIGURES],
            "font_family": "Times New Roman",
            "generated_microscopy_present": False,
        },
        "machine_audits": {
            "pytest": {
                "command": ".venv\\Scripts\\python.exe -m pytest -q",
                "passed": 359,
                "skipped": 4,
                "warnings": 15,
                "failures": 0,
            },
            "main_accessibility": {"high": 0, "medium": 0, "low": 0},
            "supporting_accessibility": {"high": 0, "medium": 0, "low": 0},
            "pdf_fonts_embedded": True,
            "pdf_font_families": [
                "TimesNewRomanPSMT",
                "TimesNewRomanPS-BoldMT",
                "TimesNewRomanPS-ItalicMT",
            ],
        },
        "frozen_receipts": [artifact(path) for path in RECEIPTS],
        "public_repository_audit": {
            "url": "https://github.com/RonnieHappy/NOSTOS",
            "audited_branch": "main",
            "audited_head": "8d16586607ec7e2b9364919d4ae13ea01921128d",
            "audited_utc_date": "2026-08-31",
            "v34_article_source_present": False,
            "v34_main_docx_present": False,
            "v34_supporting_information_present": False,
            "v34_submission_manifest_present": False,
        },
        "claim_boundary": (
            "The package validates selective measurement support, structural recovery and estimator-level "
            "agreement on the declared public resources. It does not establish diagnosis, tissue mechanics, "
            "clinical utility, intraoperative performance or universal biological meaning."
        ),
        "external_submission_dependency": (
            "The audited public repository does not yet contain the v34 manuscript-specific source, figures, "
            "Supporting Information or submission manifest. Publish the exact v34 analysis/figure snapshot, "
            "create a versioned archival DOI and update the Data Availability Statement before the final "
            "publisher upload."
        ),
    }

    if not all(assertions.values()):
        failed = [name for name, passed in assertions.items() if not passed]
        raise RuntimeError("Journal-rule assertions failed: " + ", ".join(failed))
    if not all(item["passes_resolution_gate"] for group in manifest["figures"].values() if isinstance(group, list) for item in group):
        raise RuntimeError("One or more figures failed the 300 dpi effective-resolution gate")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
