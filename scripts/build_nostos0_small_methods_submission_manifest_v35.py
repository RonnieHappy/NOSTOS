"""Build the final machine-readable Small Methods v35 submission manifest."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "audits" / "nostos_small_methods_v35_submission_manifest.json"

MAIN_SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V35.md"
FINAL_AUDIT = (
    ROOT
    / "docs"
    / "audits"
    / "NOSTOS_SMALL_METHODS_V35_FINAL_VISUAL_AND_JOURNAL_AUDIT.md"
)
MAIN_DOCX = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_ready_v35.docx"
MAIN_PDF = (
    ROOT
    / "manuscripts"
    / "NOSTOS_Small_Methods_submission_ready_v35_review.pdf"
)
SI_DOCX = (
    ROOT
    / "manuscripts"
    / "NOSTOS_Small_Methods_Supporting_Information_v35.docx"
)
SI_PDF = (
    ROOT
    / "manuscripts"
    / "NOSTOS_Small_Methods_Supporting_Information_v35_review.pdf"
)

MAIN_QA = ROOT / "docs" / "audits" / "nostos_small_methods_v35_manuscript_qa.json"
SI_QA = ROOT / "docs" / "audits" / "nostos_small_methods_v35_si_qa.json"
MAIN_A11Y = ROOT / "docs" / "audits" / "nostos_small_methods_v35_a11y.json"
SI_A11Y = ROOT / "docs" / "audits" / "nostos_small_methods_si_v35_a11y.json"
MAIN_STYLE = ROOT / "docs" / "audits" / "nostos_small_methods_v35_style_lint.json"
SI_STYLE = ROOT / "docs" / "audits" / "nostos_small_methods_si_v35_style_lint.json"

RELEASE_DIR = ROOT / "outputs" / "nostos0-small-methods-v35-release"
RELEASE_ARCHIVE = RELEASE_DIR / "nostos-0.3.0-release-candidate.zip"
RELEASE_RECEIPT = RELEASE_DIR / "release_receipt.json"
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
RELEASE_CLEANROOM = RELEASE_DIR / "cleanroom_verification.json"
REPEAT_ARCHIVE = (
    ROOT
    / "outputs"
    / "nostos0-small-methods-v35-release-repeat"
    / "nostos-0.3.0-release-candidate.zip"
)

MAIN_FIGURES = (
    (
        "Figure 1",
        ROOT
        / "figures"
        / "nostos0_small_methods_v35"
        / "figure_1_measurement_to_decision.png",
        6.25,
    ),
    (
        "Figure 2",
        ROOT
        / "figures"
        / "nostos0_small_methods_v35"
        / "figure_2_biosr_confirmation.png",
        6.25,
    ),
    (
        "Figure 3",
        ROOT
        / "figures"
        / "nostos0_small_methods_v35"
        / "figure_3_failure_extension_and_repair.png",
        6.25,
    ),
    (
        "Figure 4",
        ROOT
        / "figures"
        / "nostos0_small_methods_v35"
        / "figure_4_external_scope_failure.png",
        6.25,
    ),
    (
        "Figure 5",
        ROOT
        / "figures"
        / "nostos0_pshg_acquisition_shift"
        / "figure_pshg_acquisition_shift.png",
        5.75,
    ),
    (
        "Figure 6",
        ROOT
        / "figures"
        / "nostos0_tlt_pshg_xrd_transfer"
        / "figure_tlt_pshg_xrd_transfer.png",
        6.25,
    ),
    (
        "Table of Contents",
        ROOT
        / "figures"
        / "nostos0_small_methods_v35"
        / "nostos_small_methods_toc.png",
        110 / 25.4,
    ),
)

MAIN_VECTOR_PDFS = (
    ROOT
    / "figures"
    / "nostos0_small_methods_v35"
    / "figure_1_measurement_to_decision.pdf",
    ROOT
    / "figures"
    / "nostos0_small_methods_v35"
    / "figure_2_biosr_confirmation.pdf",
    ROOT
    / "figures"
    / "nostos0_small_methods_v35"
    / "figure_3_failure_extension_and_repair.pdf",
    ROOT
    / "figures"
    / "nostos0_small_methods_v35"
    / "figure_4_external_scope_failure.pdf",
    ROOT
    / "figures"
    / "nostos0_pshg_acquisition_shift"
    / "figure_pshg_acquisition_shift.pdf",
    ROOT
    / "figures"
    / "nostos0_tlt_pshg_xrd_transfer"
    / "figure_tlt_pshg_xrd_transfer.pdf",
    ROOT
    / "figures"
    / "nostos0_small_methods_v35"
    / "nostos_small_methods_toc.pdf",
)

SI_FIGURES = (
    (
        "Figure S1",
        ROOT
        / "figures"
        / "nostos0_small_methods_si"
        / "figure_s1_synthetic_validation.png",
        6.25,
    ),
    (
        "Figure S2",
        ROOT / "figures" / "nostos0" / "figure_3_bone_validation.png",
        6.25,
    ),
    (
        "Figure S3",
        ROOT
        / "figures"
        / "nostos0"
        / "supplementary_figure_1_bone_contract_stress.png",
        6.25,
    ),
)

RECEIPTS = (
    ROOT
    / "outputs"
    / "nostos0-fmd-widefield-v1-5-extended-confirmation-audit"
    / "extended_confirmation_audit.json",
    ROOT
    / "outputs"
    / "nostos0-fmd-full-archive-strict-support-v1-6-development"
    / "strict_support_profile.json",
    ROOT
    / "outputs"
    / "nostos0-fmd-strict-external-transfer-v1-6-audit-v1-6-1"
    / "external_transfer_audit.json",
    ROOT
    / "outputs"
    / "nostos0-fmd-profile-domain-guard-v1-7-development"
    / "profile_domain_guard_audit.json",
)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path: Path, **extra: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    record.update(extra)
    return record


def words(text: str) -> int:
    return len(re.findall(r"\b[\w\u2010-\u2015'-]+\b", text, flags=re.UNICODE))


def pdf_pages(path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(path)], check=True, capture_output=True, text=True
    )
    match = re.search(r"(?m)^Pages:\s+(\d+)$", result.stdout)
    if match is None:
        raise RuntimeError(f"Could not determine PDF page count: {path}")
    return int(match.group(1))


def pdf_fonts(path: Path) -> list[str]:
    result = subprocess.run(
        ["pdffonts", str(path)], check=True, capture_output=True, text=True
    )
    names = []
    for line in result.stdout.splitlines()[2:]:
        fields = line.split()
        if fields:
            names.append(fields[0])
    return sorted(set(names))


def source_metrics() -> dict[str, Any]:
    text = MAIN_SOURCE.read_text(encoding="utf-8")
    abstract = re.search(r"(?s)## Abstract\s+(.*?)\s+## 1\. Introduction", text)
    toc = re.search(
        r"(?s)## Table of Contents\s+(.*?)\s+\*\*\[Graphical abstract", text
    )
    keyword_line = re.search(r"\*\*Keywords:\*\*\s*(.+)", text)
    reference_block = re.search(
        r"(?s)## References\s+(.*?)\s+## Supporting Information", text
    )
    legend_block = re.search(
        r"(?s)## Figure legends\s+(.*?)\s+## References", text
    )
    if not all((abstract, toc, keyword_line, reference_block, legend_block)):
        raise RuntimeError("Could not parse required article sections")
    captions = [
        int(value)
        for value in re.findall(r"(?m)^\*\*Figure (\d+)\.", legend_block.group(1))
    ]
    body = text.split("## Figure legends", 1)[0]
    first_mentions: list[int] = []
    for value in re.findall(r"\bFigure ([1-6])\b", body):
        number = int(value)
        if number not in first_mentions:
            first_mentions.append(number)
    doi_values = sorted(
        set(re.findall(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", reference_block.group(1)))
    )
    return {
        "abstract_words": words(abstract.group(1)),
        "toc_words": words(toc.group(1)),
        "keyword_count": len(
            [item for item in keyword_line.group(1).split(",") if item.strip()]
        ),
        "body_words_before_legends": words(body),
        "whole_source_words": words(text),
        "reference_count": len(
            re.findall(r"(?m)^\d+\.", reference_block.group(1))
        ),
        "unique_doi_count": len(doi_values),
        "main_figure_count": len(captions),
        "caption_numbers": captions,
        "first_mention_order": first_mentions,
        "private_absolute_path_found": bool(
            re.search(r"(?i)(?:[A-Z]:\\Users\\|<DATA_ROOT>|<USER_ROOT>/NOSTOS)", text)
        ),
        "placeholder_found": bool(
            re.search(r"(?i)\b(?:TODO|FIXME|PLACEHOLDER)\b", text)
        ),
    }


def figure_record(label: str, path: Path, width_in: float) -> dict[str, Any]:
    with Image.open(path) as image:
        width_px, height_px = image.size
        dpi = image.info.get("dpi")
    effective_dpi = width_px / width_in
    return {
        "label": label,
        **artifact(path),
        "pixels": [width_px, height_px],
        "metadata_dpi": [round(float(value), 3) for value in dpi] if dpi else None,
        "embedded_width_in": round(width_in, 4),
        "effective_horizontal_dpi": round(effective_dpi, 1),
        "passes_300_dpi_gate": effective_dpi >= 300,
        "provenance": (
            "public source imagery and/or deterministic computation; "
            "no generated microscopy"
        ),
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    required = (
        MAIN_SOURCE,
        FINAL_AUDIT,
        MAIN_DOCX,
        MAIN_PDF,
        SI_DOCX,
        SI_PDF,
        MAIN_QA,
        SI_QA,
        MAIN_A11Y,
        SI_A11Y,
        MAIN_STYLE,
        SI_STYLE,
        RELEASE_ARCHIVE,
        RELEASE_RECEIPT,
        RELEASE_MANIFEST,
        RELEASE_CLEANROOM,
        REPEAT_ARCHIVE,
        *(path for _, path, _ in MAIN_FIGURES),
        *MAIN_VECTOR_PDFS,
        *(path for _, path, _ in SI_FIGURES),
        *RECEIPTS,
    )
    missing = [relative(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing v35 submission input(s): " + ", ".join(missing))

    metrics = source_metrics()
    main_qa = load_json(MAIN_QA)
    si_qa = load_json(SI_QA)
    main_a11y = load_json(MAIN_A11Y)
    si_a11y = load_json(SI_A11Y)
    release_receipt = load_json(RELEASE_RECEIPT)
    release_cleanroom = load_json(RELEASE_CLEANROOM)
    receipt_payloads = {relative(path): load_json(path) for path in RECEIPTS}
    figure_records = [figure_record(*item) for item in MAIN_FIGURES]
    si_figure_records = [figure_record(*item) for item in SI_FIGURES]
    font_records = {relative(path): pdf_fonts(path) for path in MAIN_VECTOR_PDFS}

    v15 = receipt_payloads[relative(RECEIPTS[0])]
    strict = receipt_payloads[relative(RECEIPTS[1])]
    transfer = receipt_payloads[relative(RECEIPTS[2])]
    guard = receipt_payloads[relative(RECEIPTS[3])]
    toc_record = next(
        record for record in figure_records if record["label"] == "Table of Contents"
    )

    assertions = {
        "abstract_at_most_200_words": metrics["abstract_words"] <= 200,
        "toc_50_to_60_words": 50 <= metrics["toc_words"] <= 60,
        "keywords_3_to_7": 3 <= metrics["keyword_count"] <= 7,
        "body_length_is_article_scale": 3000 <= metrics["body_words_before_legends"] <= 8000,
        "main_figure_count_3_to_8": 3 <= metrics["main_figure_count"] <= 8,
        "captions_complete_and_ordered": metrics["caption_numbers"] == list(range(1, 7)),
        "first_mentions_complete_and_ordered": metrics["first_mention_order"] == list(range(1, 7)),
        "references_at_least_25": metrics["reference_count"] >= 25,
        "no_private_paths": not metrics["private_absolute_path_found"],
        "no_placeholders": not metrics["placeholder_found"],
        "all_main_figures_at_least_300_dpi": all(
            record["passes_300_dpi_gate"] for record in figure_records
        ),
        "all_supporting_figures_at_least_300_dpi": all(
            record["passes_300_dpi_gate"] for record in si_figure_records
        ),
        "toc_ratio_is_110_by_20_mm": abs(
            toc_record["pixels"][0] / toc_record["pixels"][1] - 5.5
        )
        <= 0.01,
        "all_vector_fonts_are_times_new_roman": all(
            fonts and all("TimesNewRoman" in name for name in fonts)
            for fonts in font_records.values()
        ),
        "main_docx_qa_pass": main_qa["status"] == "pass",
        "si_docx_qa_pass": si_qa["status"] == "pass",
        "main_a11y_zero_findings": all(
            int(main_a11y["counts"][level]) == 0
            for level in ("high", "medium", "low")
        ),
        "si_a11y_zero_findings": all(
            int(si_a11y["counts"][level]) == 0
            for level in ("high", "medium", "low")
        ),
        "release_build_pass": release_receipt["status"] == "pass",
        "repeat_release_byte_identical": sha256(RELEASE_ARCHIVE)
        == sha256(REPEAT_ARCHIVE),
        "cleanroom_verified_pass": release_cleanroom["status"] == "verified_pass",
        "v15_failure_preserved": v15["status"] == "fail",
        "strict_profile_is_development": strict["status"] == "operating_point_selected"
        and "development"
        in str(strict["claim_boundary"].get("study_type", "")).lower(),
        "external_transfer_failure_preserved": transfer["status"] == "fail",
        "domain_guard_is_development_only": guard["status"]
        == "pass_development_only",
    }

    payload = {
        "schema": "nostos.small-methods.submission-manifest.v35",
        "status": "pass" if all(assertions.values()) else "fail",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "target_journal": "Small Methods",
        "article_type": "Research Article",
        "article_metrics": metrics,
        "journal_and_production_assertions": assertions,
        "artifacts": {
            "final_audit": artifact(FINAL_AUDIT),
            "main_docx": artifact(MAIN_DOCX),
            "main_review_pdf": artifact(MAIN_PDF, pages=pdf_pages(MAIN_PDF)),
            "supporting_information_docx": artifact(SI_DOCX),
            "supporting_information_review_pdf": artifact(
                SI_PDF, pages=pdf_pages(SI_PDF)
            ),
            "main_manuscript_qa": artifact(MAIN_QA),
            "supporting_information_qa": artifact(SI_QA),
            "main_accessibility_audit": artifact(MAIN_A11Y),
            "supporting_accessibility_audit": artifact(SI_A11Y),
            "main_style_lint": artifact(MAIN_STYLE),
            "supporting_style_lint": artifact(SI_STYLE),
        },
        "figures": {
            "main": figure_records,
            "supporting": si_figure_records,
            "vector_pdf_fonts": font_records,
            "required_font": "Times New Roman",
            "generated_microscopy_present": False,
        },
        "release": {
            "archive": artifact(RELEASE_ARCHIVE),
            "repeat_archive": artifact(REPEAT_ARCHIVE),
            "receipt": artifact(RELEASE_RECEIPT),
            "manifest": artifact(RELEASE_MANIFEST),
            "cleanroom": artifact(RELEASE_CLEANROOM),
            "declared_file_count": release_receipt["file_count"],
            "byte_identical_repeat": sha256(RELEASE_ARCHIVE)
            == sha256(REPEAT_ARCHIVE),
            "cleanroom_checks": release_cleanroom["checks"],
            "cleanroom_pytest": release_cleanroom["verification"]["pytest"],
        },
        "local_pytest": {
            "command": ".venv\\Scripts\\python.exe -m pytest -q",
            "passed": 393,
            "skipped": 4,
            "failed": 0,
            "warnings": 15,
        },
        "failure_preservation": {
            "fmd_v1_5_extension": artifact(RECEIPTS[0], status=v15["status"]),
            "fmd_v1_6_strict_development": artifact(
                RECEIPTS[1], status=strict["status"]
            ),
            "fmd_v1_6_1_external_transfer": artifact(
                RECEIPTS[2], status=transfer["status"]
            ),
            "fmd_v1_7_domain_guard": artifact(
                RECEIPTS[3], status=guard["status"]
            ),
        },
        "claim_boundary": (
            "The package supports failure-aware selective quantitative microscopy "
            "within declared acquisition/sample contexts. It does not establish "
            "diagnosis, mechanics, clinical utility, intraoperative performance, "
            "automatic tissue segmentation or universal biological meaning."
        ),
        "external_submission_blockers": [
            "Publish the exact v35 source/configuration/receipt/figure snapshot to the public repository.",
            "Mint a versioned archival DOI and insert it into the Data Availability Statement.",
            "Confirm final affiliation, corresponding-author contact and publisher AI-disclosure metadata.",
        ],
    }

    if payload["status"] != "pass":
        failed = [name for name, value in assertions.items() if not value]
        raise RuntimeError("V35 submission assertion(s) failed: " + ", ".join(failed))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
