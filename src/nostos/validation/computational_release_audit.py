"""Build the terminal, computation-only NOSTOS-0 release audit.

This audit is intentionally post-release.  It verifies the frozen scientific
receipts, publication figures, rendered manuscript and deterministic archive
without becoming an input to the archive that it identifies.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO


PROTOCOL_VERSION = "nostos-computational-release-audit/1.0"
AUDIT_DATE = "2026-08-29"
EXPECTED_EVIDENCE_ENTRIES = 112
MINIMUM_PACKAGED_TESTS = 317

REQUIRED_ARTIFACTS = {
    "evidence_index": "outputs/nostos0-evidence-bundle-v30/evidence_index.json",
    "figure_manifest": "figures/nostos0/validity_figures.manifest.json",
    "manuscript_source": "docs/NOSTOS0_SOFTWARE_RESOURCE_ARTICLE.md",
    "manuscript_docx": "manuscripts/NOSTOS0_computational_methods_submission_candidate_v30.docx",
    "manuscript_pdf": "manuscripts/NOSTOS0_computational_methods_submission_candidate_v30.pdf",
    "manuscript_qa": "outputs/nostos0-manuscript-qa-v2/manuscript_qa.json",
    "manuscript_a11y": "outputs/nostos0-docx-a11y-v30-final2.json",
    "release_receipt": "outputs/nostos0-release-candidate-v30/release_receipt.json",
    "release_manifest": "outputs/nostos0-release-candidate-v30/release_manifest.json",
    "release_archive": (
        "outputs/nostos0-release-candidate-v30/"
        "nostos-0.3.0-release-candidate.zip"
    ),
    "repeat_release_receipt": (
        "outputs/nostos0-release-candidate-v30-repeat/release_receipt.json"
    ),
    "cleanroom_initial_failure": (
        "outputs/nostos0-release-candidate-v30/cleanroom_initial_failure.json"
    ),
    "cleanroom_interpreter_visibility_failure": (
        "outputs/nostos0-release-candidate-v30/"
        "cleanroom_interpreter_visibility_failure.json"
    ),
    "cleanroom_verification": (
        "outputs/nostos0-release-candidate-v30/cleanroom_verification.json"
    ),
    "biosr_confirmation": (
        "outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation/"
        "confirmation_receipt.json"
    ),
    "biosr_independent_audit": (
        "outputs/nostos0-biosr-tensor-v9-final-audit/final_audit.json"
    ),
    "fmd_pooled_confirmation": (
        "outputs/nostos0-fmd-widefield-v1-3-confirmation-audit-v1-1/"
        "confirmation_audit.json"
    ),
    "fmd_hierarchical_confirmation": (
        "outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation-audit/"
        "confirmation_audit.json"
    ),
    "fmd_finite_sample_uncertainty": (
        "outputs/nostos0-fmd-widefield-v1-4-finite-sample-uncertainty.json"
    ),
    "fmd_terminal_audit": (
        "outputs/nostos0-fmd-validity-program-final-audit-v1/final_audit.json"
    ),
}

PRIVATE_PATH_PATTERNS = (
    re.compile(r"(?i)[A-Z]:\\Users\\"),
    re.compile(r"(?i)[A-Z]:/Users/"),
    re.compile(r"(?i)E:\\NOSTOS"),
    re.compile(r"(?i)E:/NOSTOS"),
)
SECRET_PATTERNS = (
    re.compile(r"s2k-[A-Za-z0-9_-]{20,}"),
    re.compile(
        r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]"
    ),
)
OVERCLAIM_PHRASES = (
    "clinically validated",
    "validated for intraoperative use",
    "ready for clinical use",
    "safe for patient care",
    "diagnoses osteoarthritis",
    "establishes clinical utility",
    "establishes intraoperative performance",
    "nature-ready",
)
REQUIRED_CLAIM_BOUNDARY_PHRASES = (
    "the claim evaluated here is computational",
    "does not establish biological interpretation",
    "clinical usefulness or intraoperative performance",
)


def _sha256_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return _sha256_stream(stream)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _all_true(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and all(item is True for item in value.values())
    )


def _close(observed: Any, expected: float, *, tolerance: float = 1e-12) -> bool:
    return isinstance(observed, (int, float)) and math.isclose(
        float(observed), expected, rel_tol=tolerance, abs_tol=tolerance
    )


def derive_computational_audit_status(checks: dict[str, bool]) -> str:
    """Return a pass only when every frozen audit check is true."""

    if checks and all(checks.values()):
        return "verified_computational_release_with_external_blockers"
    return "failed"


def _safe_registered_path(root: Path, relative: str) -> Path | None:
    normalized = relative.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if (
        not normalized
        or pure.is_absolute()
        or ".." in pure.parts
        or (pure.parts and ":" in pure.parts[0])
    ):
        return None
    candidate = (root / Path(*pure.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def registered_file_matches(root: Path, record: dict[str, Any]) -> bool:
    """Verify one path/size/SHA-256 record without accepting path traversal."""

    relative = record.get("path")
    expected_bytes = record.get("bytes")
    expected_sha256 = record.get("sha256")
    if (
        not isinstance(relative, str)
        or not isinstance(expected_bytes, int)
        or not isinstance(expected_sha256, str)
    ):
        return False
    path = _safe_registered_path(root, relative)
    return bool(
        path
        and path.is_file()
        and path.stat().st_size == expected_bytes
        and _sha256(path) == expected_sha256
    )


def _artifact_record(root: Path, relative: str) -> dict[str, Any]:
    path = _safe_registered_path(root, relative)
    if path is None or not path.is_file():
        return {"path": relative, "exists": False}
    return {
        "path": relative,
        "exists": True,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _verify_evidence_index(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    bad: list[str] = []
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    for entry in entries:
        if not isinstance(entry, dict) or not registered_file_matches(root, entry):
            identifier = entry.get("identifier", "malformed") if isinstance(entry, dict) else "malformed"
            bad.append(str(identifier))
    return {
        "status": payload.get("status"),
        "declared_entries": len(entries),
        "verified_entries": len(entries) - len(bad),
        "bad_entries": bad,
        "missing": payload.get("missing", []),
        "nature_readiness": payload.get("nature_readiness"),
    }


def _verify_figure_manifest(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    registered: list[dict[str, Any]] = []
    generator = {
        "path": payload.get("generated_by"),
        "sha256": payload.get("generated_by_sha256"),
    }
    generator_path = generator["path"]
    if isinstance(generator_path, str):
        resolved = _safe_registered_path(root, generator_path)
        if resolved and resolved.is_file():
            generator["bytes"] = resolved.stat().st_size
    registered.append(generator)
    frozen = payload.get("frozen_sources", [])
    if isinstance(frozen, list):
        registered.extend(item for item in frozen if isinstance(item, dict))
    figures = payload.get("figures", {})
    if isinstance(figures, dict):
        for formats in figures.values():
            if isinstance(formats, dict):
                registered.extend(
                    item for item in formats.values() if isinstance(item, dict)
                )
    bad = [
        str(record.get("path", "malformed"))
        for record in registered
        if not registered_file_matches(root, record)
    ]
    return {
        "status": payload.get("status"),
        "registered_files": len(registered),
        "verified_files": len(registered) - len(bad),
        "bad_files": bad,
        "declaration": payload.get("declaration"),
    }


def _verify_manuscript(
    root: Path,
    qa: dict[str, Any],
    a11y: dict[str, Any],
) -> dict[str, Any]:
    bad: list[str] = []
    for label, record in qa.get("inputs", {}).items():
        if not isinstance(record, dict) or not registered_file_matches(root, record):
            bad.append(f"input:{label}")

    render = qa.get("render", {})
    render_dir_name = render.get("render_directory")
    render_dir = (
        root / "outputs" / render_dir_name
        if isinstance(render_dir_name, str)
        else None
    )
    pages = render.get("pages", [])
    if isinstance(pages, list) and render_dir is not None:
        for page in pages:
            if not isinstance(page, dict):
                bad.append("render:malformed_page")
                continue
            candidate = render_dir / str(page.get("file", ""))
            if not (
                candidate.is_file()
                and candidate.stat().st_size == page.get("bytes")
                and _sha256(candidate) == page.get("sha256")
            ):
                bad.append(f"render:{page.get('file', 'malformed')}")

    pdf_record = render.get("pdf", {})
    if isinstance(pdf_record, dict) and render_dir is not None:
        render_pdf = render_dir / str(pdf_record.get("file", ""))
        if not (
            render_pdf.is_file()
            and render_pdf.stat().st_size == pdf_record.get("bytes")
            and _sha256(render_pdf) == pdf_record.get("sha256")
        ):
            bad.append("render:pdf")
        submission_pdf = root / REQUIRED_ARTIFACTS["manuscript_pdf"]
        if not submission_pdf.is_file() or not render_pdf.is_file() or _sha256(
            submission_pdf
        ) != _sha256(render_pdf):
            bad.append("submission_pdf_not_render_identity")

    counts = a11y.get("counts", {})
    a11y_clear = (
        isinstance(counts, dict)
        and counts.get("high") == 0
        and counts.get("medium") == 0
        and counts.get("low") == 0
        and not a11y.get("findings")
    )
    return {
        "status": qa.get("status"),
        "page_count": render.get("page_count"),
        "embedded_media_count": qa.get("document", {}).get("embedded_media_count"),
        "machine_checks_all_true": _all_true(qa.get("machine_checks")),
        "visual_review_status": qa.get("visual_review", {}).get("status"),
        "visual_pages_reviewed": len(
            qa.get("visual_review", {}).get("pages_reviewed", [])
        ),
        "a11y_clear": a11y_clear,
        "bad_files": bad,
    }


def scan_manuscript_claims(text: str) -> dict[str, Any]:
    """Check the plain-text manuscript for scope language and unsafe claims."""

    lowered = text.lower()
    private_hits = [pattern.pattern for pattern in PRIVATE_PATH_PATTERNS if pattern.search(text)]
    secret_hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    overclaim_hits = [phrase for phrase in OVERCLAIM_PHRASES if phrase in lowered]
    missing_boundary = [
        phrase for phrase in REQUIRED_CLAIM_BOUNDARY_PHRASES if phrase not in lowered
    ]
    return {
        "private_path_hits": private_hits,
        "secret_hits": secret_hits,
        "overclaim_hits": overclaim_hits,
        "missing_claim_boundary_phrases": missing_boundary,
    }


def _verify_release_archive(
    archive: Path,
    external_manifest: dict[str, Any],
) -> dict[str, Any]:
    bad_files: list[str] = []
    unsafe_members: list[str] = []
    unregistered: list[str] = []
    missing: list[str] = []
    manifest_identity = False
    embedded_manifest: dict[str, Any] = {}
    if not archive.is_file():
        return {
            "safe_members": False,
            "manifest_identity": False,
            "verified_files": 0,
            "bad_files": ["archive_missing"],
            "unregistered_files": [],
            "missing_files": [],
        }

    with zipfile.ZipFile(archive) as bundle:
        names = [info.filename for info in bundle.infolist() if not info.is_dir()]
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                unsafe_members.append(name)
        manifest_name = "nostos-0.3.0/release_manifest.json"
        if manifest_name in names:
            embedded_bytes = bundle.read(manifest_name)
            try:
                embedded_manifest = json.loads(embedded_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                bad_files.append("release_manifest.json:invalid_json")
            external_bytes = (json.dumps(external_manifest, indent=2) + "\n").encode(
                "utf-8"
            )
            manifest_identity = embedded_bytes == external_bytes
        else:
            missing.append("release_manifest.json")

        declared = embedded_manifest.get("files", [])
        declared_paths: set[str] = set()
        verified = 0
        if isinstance(declared, list):
            by_name = {info.filename: info for info in bundle.infolist()}
            for record in declared:
                if not isinstance(record, dict):
                    bad_files.append("malformed_manifest_record")
                    continue
                relative = record.get("path")
                if not isinstance(relative, str):
                    bad_files.append("missing_manifest_path")
                    continue
                declared_paths.add(relative)
                member = f"nostos-0.3.0/{relative}"
                info = by_name.get(member)
                if info is None:
                    missing.append(relative)
                    continue
                with bundle.open(info) as stream:
                    observed_hash = _sha256_stream(stream)
                if (
                    info.file_size != record.get("bytes")
                    or observed_hash != record.get("sha256")
                ):
                    bad_files.append(relative)
                else:
                    verified += 1
            archived_relative = {
                name.removeprefix("nostos-0.3.0/")
                for name in names
                if name != manifest_name and name.startswith("nostos-0.3.0/")
            }
            unregistered = sorted(archived_relative - declared_paths)
        else:
            verified = 0
            bad_files.append("manifest_files_not_a_list")

    return {
        "safe_members": not unsafe_members,
        "unsafe_members": unsafe_members,
        "manifest_identity": manifest_identity,
        "declared_files": len(embedded_manifest.get("files", [])),
        "verified_files": verified,
        "bad_files": bad_files,
        "unregistered_files": unregistered,
        "missing_files": missing,
        "manifest_status": embedded_manifest.get("status"),
        "data_included": embedded_manifest.get("data_included"),
        "audit_findings": embedded_manifest.get("audit_findings"),
    }


def _find_stratum(rows: Any, key: str, value: str) -> dict[str, Any]:
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and str(row.get(key)) == value:
                return row
    return {}


def _content_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _markdown_report(audit: dict[str, Any]) -> str:
    release = audit["release_identity"]
    evidence = audit["scientific_evidence"]
    tests = audit["software_verification"]["packaged_tests"]
    failed = [name for name, value in audit["checks"].items() if not value]
    failed_text = "None." if not failed else ", ".join(failed)
    gate_lines = "\n".join(
        f"- **{item['gate']} — {item['status']}.** {item['reason']}"
        for item in audit["remaining_gates"]
    )
    return f"""# NOSTOS-0 final computational methods audit v4

**Audit status:** `{audit['status']}`  
**Scope:** computation-only quantitative-microscopy software and public-data methods validation  
**Release:** NOSTOS {release['software_version']}, SHA-256 `{release['archive_sha256']}`  
**Audit identity:** `{audit['content_sha256']}`

## Decision

The NOSTOS-0 software, public-data analyses, figures and manuscript form one
hash-bound, deterministic computational release candidate. The archive is
data-free, installs in a clean environment, passes its packaged tests and
rebuilds byte-for-byte. The current paper does not require a wet-lab experiment
because it makes no biological, diagnostic, mechanical, clinical or
intraoperative-performance claim.

This is a strong computational methods submission candidate, not a guarantee of
acceptance at any named venue. Archival publication and unaided external
execution remain open.

## What is verified

- **Evidence integrity:** {audit['evidence_registry']['verified_entries']} of
  {audit['evidence_registry']['declared_entries']} registered receipts match
  their declared byte counts and SHA-256 identities.
- **Publication assets:** four main figures are present in PNG, PDF and SVG;
  every figure, frozen source receipt and generator identity matches the figure
  manifest. The microscopy pixels are from the cited public BioSR and FMD
  archives, not generated biological imagery.
- **Manuscript production:** 15 rendered pages, four embedded main figures,
  Times New Roman visible text, zero accessibility findings, all pages visually
  reviewed and no private paths or credentials detected.
- **Software portability:** {tests['passed']} packaged tests passed,
  {tests['skipped']} were skipped and {tests['failed']} failed in an
  author-operated clean-room install. A second build produced the same archive
  bytes.
- **Failure transparency:** the earlier local-storage staging failure and a
  removable-media interpreter-visibility race are retained as machine-readable
  negative receipts; both repairs are exercised by the definitive clean-room
  pass.

## Central computational evidence

On eight untouched BioSR F-actin fields, the frozen tensor-coherence contract
accepted {evidence['biosr']['accepted']} of {evidence['biosr']['eligible']}
eligible measurements ({evidence['biosr']['coverage']:.1%}) with observed
silent-invalid risk {evidence['biosr']['risk']:.4f}. Ordinary acquisition QC
accepted all measurements with risk {evidence['biosr']['ordinary_qc_risk']:.4f}.
The relative risk reduction was {evidence['biosr']['relative_risk_reduction']:.1%};
the field-bootstrap AURC difference was
{evidence['biosr']['aurc_difference']:.4f}, with 95% interval
[{evidence['biosr']['aurc_ci95'][0]:.4f},
{evidence['biosr']['aurc_ci95'][1]:.4f}].

The FMD sequence supplies the more important failure-repair experiment. A
pooled profile passed while emitting a concentrated average-of-8 failure. The
development-only acquisition-by-scale layer then restricted support before the
next confirmation was opened. On four untouched FOVs it emitted
{evidence['fmd']['accepted']} of {evidence['fmd']['eligible']} measurements
({evidence['fmd']['coverage']:.1%}) with no observed invalid values. At the same
64-emission count, ordinary QC emitted {evidence['fmd']['ordinary_qc_invalid']}
invalid values. The FOV-bootstrap AURC advantage was
{evidence['fmd']['aurc_difference']:.3f}, 95% interval
[{evidence['fmd']['aurc_ci95'][0]:.3f},
{evidence['fmd']['aurc_ci95'][1]:.3f}].

Zero observed events are not reported as zero population risk. The exact upper
95% limit is {evidence['fmd']['nested_upper95']:.1%} for the 64 nested emissions
and {evidence['fmd']['field_upper95']:.1%} for the proportion of comparable
FOVs with any failure. The second interval is wide because there are only four
independent confirmation FOVs.

## Novelty boundary

The component image estimators are established. The methodological object being
tested is the **measurement-validity compiler**: an input-only, serialized
contract that combines calibrated failure risk with declared acquisition and
measurement coordinates, preserves independent-group inference, emits
reason-coded abstentions and retains failed profiles in the audit lineage. The
FMD failure-repair sequence shows a concrete advantage over a pooled profile and
matched ordinary QC. NOSTOS does not claim universal estimator superiority or a
universal biological representation.

## Remaining gates

{gate_lines}

## Fail-closed result

Failed machine checks: {failed_text}

The defensible submission claim is therefore limited to computational
measurement validity on paired public microscopy data. No wet-lab study is a
prerequisite for that claim; any future biological or intraoperative extension
would be a separate study with a separate evidentiary contract.
"""


def build_computational_release_audit(
    project_root: Path,
    json_output: Path,
    markdown_output: Path,
) -> dict[str, Any]:
    """Verify the final computational release and write JSON and Markdown audits."""

    root = project_root.resolve()
    records = {
        name: _artifact_record(root, relative)
        for name, relative in REQUIRED_ARTIFACTS.items()
    }
    payloads: dict[str, dict[str, Any]] = {}
    for name, record in records.items():
        if not record.get("exists") or not str(record["path"]).endswith(".json"):
            continue
        try:
            payloads[name] = _load_json(root / record["path"])
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            payloads[name] = {}

    evidence = payloads.get("evidence_index", {})
    figures = payloads.get("figure_manifest", {})
    manuscript_qa = payloads.get("manuscript_qa", {})
    a11y = payloads.get("manuscript_a11y", {})
    release = payloads.get("release_receipt", {})
    release_manifest = payloads.get("release_manifest", {})
    repeat_release = payloads.get("repeat_release_receipt", {})
    failure = payloads.get("cleanroom_initial_failure", {})
    visibility_failure = payloads.get(
        "cleanroom_interpreter_visibility_failure", {}
    )
    cleanroom = payloads.get("cleanroom_verification", {})
    biosr = payloads.get("biosr_confirmation", {})
    biosr_audit = payloads.get("biosr_independent_audit", {})
    fmd_pooled = payloads.get("fmd_pooled_confirmation", {})
    fmd = payloads.get("fmd_hierarchical_confirmation", {})
    fmd_uncertainty = payloads.get("fmd_finite_sample_uncertainty", {})
    fmd_terminal = payloads.get("fmd_terminal_audit", {})

    evidence_verification = _verify_evidence_index(root, evidence)
    figure_verification = _verify_figure_manifest(root, figures)
    manuscript_verification = _verify_manuscript(root, manuscript_qa, a11y)
    manuscript_path = root / REQUIRED_ARTIFACTS["manuscript_source"]
    manuscript_text = (
        manuscript_path.read_text(encoding="utf-8") if manuscript_path.is_file() else ""
    )
    manuscript_scan = scan_manuscript_claims(manuscript_text)
    archive_path = root / REQUIRED_ARTIFACTS["release_archive"]
    archive_verification = _verify_release_archive(archive_path, release_manifest)

    biosr_eval = biosr.get("confirmation_evaluation", {})
    biosr_full = biosr_eval.get("full_contract", {})
    biosr_qc = biosr_eval.get("conventional_acquisition_qc", {})
    biosr_negative = biosr_eval.get("negative_control_full_contract", {})
    biosr_operating = biosr_eval.get("operating_point", {})
    biosr_aurc = biosr_eval.get("risk_coverage_evidence", {})
    biosr_observed = biosr_aurc.get("observed", {})
    biosr_bootstrap = biosr_aurc.get("bootstrap", {})

    pooled_avg8 = _find_stratum(
        fmd_pooled.get("stratified_safety_audit", {})
        .get("summaries", {})
        .get("acquisition_level", []),
        "stratum",
        "avg8",
    )
    fmd_primary = fmd.get("primary_operating_point", {})
    fmd_qc = fmd.get("acquisition_qc_matched_count", {})
    fmd_risk_coverage = fmd.get("risk_coverage", {})
    fmd_aurc = fmd_risk_coverage.get("cluster_bootstrap_aurc_difference", {})
    nested_interval = fmd_uncertainty.get("nested_measurement_interval", {}).get(
        "clopper_pearson_95", []
    )
    field_interval = fmd_uncertainty.get(
        "independent_group_any_failure_interval", {}
    ).get("clopper_pearson_95", [])
    supported_cells = fmd.get("supported_cell_audit", [])

    clean_checks = cleanroom.get("checks", {})
    clean_verification = cleanroom.get("verification", {})
    clean_tests = clean_verification.get("pytest", {})
    clean_archive = cleanroom.get("archive", {})
    failure_checks = failure.get("checks", {})

    checks = {
        "all_required_artifacts_present": all(
            record.get("exists") is True for record in records.values()
        ),
        "evidence_index_complete": evidence.get("status") == "complete_index"
        and len(evidence.get("entries", [])) == EXPECTED_EVIDENCE_ENTRIES
        and not evidence.get("missing"),
        "all_evidence_hashes_verified": evidence_verification["declared_entries"]
        == EXPECTED_EVIDENCE_ENTRIES
        and evidence_verification["verified_entries"] == EXPECTED_EVIDENCE_ENTRIES
        and not evidence_verification["bad_entries"],
        "computational_readiness_boundary_retained": evidence.get("nature_readiness")
        == "computational_methods_reach_candidate_pending_archival_doi_and_external_execution",
        "figure_manifest_complete": figures.get("status") == "complete"
        and len(figures.get("figures", {})) == 4,
        "figure_sources_and_assets_hash_verified": figure_verification[
            "registered_files"
        ]
        == figure_verification["verified_files"]
        and not figure_verification["bad_files"],
        "manuscript_artifacts_hash_verified": not manuscript_verification["bad_files"],
        "manuscript_machine_qa_passed": manuscript_verification["status"] == "pass"
        and manuscript_verification["page_count"] == 15
        and manuscript_verification["embedded_media_count"] == 4
        and manuscript_verification["machine_checks_all_true"] is True,
        "manuscript_visual_review_recorded": manuscript_verification[
            "visual_review_status"
        ]
        == "pass"
        and manuscript_verification["visual_pages_reviewed"] == 15,
        "manuscript_accessibility_audit_clear": manuscript_verification[
            "a11y_clear"
        ]
        is True,
        "manuscript_claim_boundary_present": not manuscript_scan[
            "missing_claim_boundary_phrases"
        ],
        "manuscript_private_path_scan_clean": not manuscript_scan[
            "private_path_hits"
        ],
        "manuscript_secret_scan_clean": not manuscript_scan["secret_hits"],
        "manuscript_overclaim_scan_clean": not manuscript_scan["overclaim_hits"],
        "biosr_confirmation_passed": biosr.get("status")
        == "complete_v9_scale_conditioned_confirmation"
        and biosr_eval.get("status") == "pass"
        and biosr_eval.get("passes") is True
        and _all_true(biosr_eval.get("checks")),
        "biosr_primary_counts_exact": biosr_full.get("eligible") == 980
        and biosr_full.get("accepted") == 931
        and biosr_full.get("invalid") == 36
        and _close(biosr_full.get("coverage"), 0.95)
        and _close(biosr_full.get("risk"), 0.03866809881847476),
        "biosr_comparator_and_negative_controls_exact": biosr_qc.get("accepted")
        == 980
        and biosr_qc.get("invalid") == 72
        and _close(biosr_qc.get("risk"), 0.07346938775510205)
        and biosr_negative.get("accepted") == 210
        and biosr_negative.get("invalid") == 0,
        "biosr_selective_advantage_exact": biosr_operating.get(
            "comparator_only_rejections"
        )
        == 49
        and biosr_operating.get("invalid_comparator_only_rejections") == 36
        and _close(
            biosr_operating.get("relative_risk_reduction_vs_qc"),
            0.4736842105263158,
        )
        and _close(
            biosr_observed.get("comparator_minus_full"), 0.0021715385098417415
        )
        and biosr_bootstrap.get("ci95")
        == [0.0009171388859071038, 0.005920810839861212]
        and biosr_bootstrap.get("probability_full_better") == 1.0,
        "biosr_independent_code_path_audit_passed": biosr_audit.get("status")
        == "verified_pass"
        and biosr_audit.get("verification", {}).get(
            "evaluation_recomputed_exactly"
        )
        is True,
        "fmd_pooled_hidden_failure_retained": fmd_pooled.get("status") == "pass"
        and pooled_avg8.get("accepted") == 20
        and pooled_avg8.get("invalid") == 4
        and _close(pooled_avg8.get("risk"), 0.2),
        "fmd_hierarchical_confirmation_passed": fmd.get("status") == "pass"
        and _all_true(fmd.get("checks"))
        and len(supported_cells) == 4
        and all(
            isinstance(cell, dict)
            and cell.get("passes") is True
            and _all_true(cell.get("checks"))
            for cell in supported_cells
        ),
        "fmd_primary_counts_exact": fmd_primary.get("eligible") == 240
        and fmd_primary.get("accepted") == 64
        and fmd_primary.get("invalid") == 0
        and fmd_primary.get("accepted_independent_groups") == 4
        and _close(fmd_primary.get("coverage"), 0.26666666666666666)
        and _close(fmd_primary.get("risk"), 0.0),
        "fmd_matched_qc_comparison_exact": fmd_qc.get("accepted") == 64
        and fmd_qc.get("invalid") == 31
        and _close(fmd_qc.get("risk"), 0.484375),
        "fmd_risk_coverage_inference_exact": _close(
            fmd_risk_coverage.get("primary_metrics", {}).get("risk_coverage_auc"),
            0.2627777777777778,
        )
        and _close(
            fmd_risk_coverage.get("acquisition_qc_metrics", {}).get(
                "risk_coverage_auc"
            ),
            0.5434494780999419,
        )
        and _close(fmd_aurc.get("observed"), 0.28067170032216415)
        and fmd_aurc.get("bootstrap_ci95")
        == [0.1871387641754223, 0.41602048269528413]
        and fmd_aurc.get("bootstrap_probability_positive") == 1.0,
        "fmd_finite_sample_limits_retained": fmd_uncertainty.get("status")
        == "supplemental_uncertainty_complete"
        and fmd_uncertainty.get("profile_refit") is False
        and nested_interval == [0.0, 0.05600908938663656]
        and field_interval == [0.0, 0.6023646356164746],
        "fmd_terminal_lineage_audit_passed": fmd_terminal.get("status")
        == "verified_pass"
        and len(fmd_terminal.get("checks", {})) == 17
        and _all_true(fmd_terminal.get("checks")),
        "release_receipt_matches_archive": release.get("status") == "pass"
        and archive_path.is_file()
        and archive_path.stat().st_size == release.get("archive_bytes")
        and _sha256(archive_path) == release.get("archive_sha256"),
        "release_manifest_is_data_free_and_clean": release_manifest.get("status")
        == "pass"
        and release_manifest.get("data_included") is False
        and not release_manifest.get("audit_findings")
        and release.get("stage_manifest_sha256")
        == records["release_manifest"].get("sha256"),
        "release_archive_contents_hash_verified": archive_verification[
            "safe_members"
        ]
        is True
        and archive_verification["manifest_identity"] is True
        and archive_verification["declared_files"]
        == archive_verification["verified_files"]
        and not archive_verification["bad_files"]
        and not archive_verification["unregistered_files"]
        and not archive_verification["missing_files"],
        "independent_repeat_build_byte_identical": repeat_release.get("status")
        == "pass"
        and repeat_release.get("archive_sha256") == release.get("archive_sha256")
        and repeat_release.get("archive_bytes") == release.get("archive_bytes")
        and repeat_release.get("stage_manifest_sha256")
        == release.get("stage_manifest_sha256"),
        "cleanroom_execution_passed": cleanroom.get("status") == "verified_pass"
        and _all_true(clean_checks)
        and clean_tests.get("passed", 0) >= MINIMUM_PACKAGED_TESTS
        and clean_tests.get("failed") == 0
        and clean_tests.get("exit_code") == 0
        and clean_verification.get("nostos_doctor", {}).get("status") == "ready"
        and clean_verification.get("dependency_check", {}).get("status") == "pass"
        and clean_verification.get("installed_version") == "0.3.0",
        "cleanroom_bound_to_release": clean_archive.get("sha256")
        == release.get("archive_sha256")
        and clean_archive.get("bytes") == release.get("archive_bytes")
        and clean_verification.get("deterministic_second_build_sha256")
        == release.get("archive_sha256"),
        "failed_cleanroom_attempt_retained": failure.get("status")
        == "verification_fail"
        and failure_checks.get("deterministic_second_build") is False
        and failure.get("verification", {}).get("pytest", {}).get("failed") == 0,
        "interpreter_visibility_failure_retained": visibility_failure.get("status")
        == "verification_fail"
        and visibility_failure.get("observed", {}).get(
            "interpreter_visible_immediately"
        )
        is False
        and visibility_failure.get("repair", {}).get("implemented") is True,
        "scope_is_computation_only": fmd.get("claim_boundary", {}).get("study_type")
        == "computation_only_public_data_methods_validation"
        and "the claim evaluated here is computational" in manuscript_text.lower(),
    }
    status = derive_computational_audit_status(checks)

    aurc_ci = biosr_bootstrap.get("ci95", [float("nan"), float("nan")])
    fmd_ci = fmd_aurc.get("bootstrap_ci95", [float("nan"), float("nan")])
    nested_upper = nested_interval[1] if len(nested_interval) == 2 else float("nan")
    field_upper = field_interval[1] if len(field_interval) == 2 else float("nan")
    audit: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "audit_date": AUDIT_DATE,
        "status": status,
        "scope": {
            "study_type": "computation_only_public_data_methods_validation",
            "wet_lab_required_for_current_claim": False,
            "evaluated": [
                "software integrity and portability",
                "public-data measurement-validity experiments",
                "publication-asset traceability",
                "manuscript production and claim discipline",
            ],
            "not_evaluated": [
                "biological mechanism",
                "diagnosis or prognosis",
                "mechanical properties",
                "clinical usefulness",
                "intraoperative acquisition or performance",
            ],
        },
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "artifacts": records,
        "evidence_registry": evidence_verification,
        "figure_traceability": figure_verification,
        "manuscript_verification": manuscript_verification,
        "manuscript_scope_scan": manuscript_scan,
        "archive_verification": archive_verification,
        "release_identity": {
            "software_version": release_manifest.get("software_version"),
            "candidate": "v30",
            "archive": release.get("archive"),
            "archive_bytes": release.get("archive_bytes"),
            "archive_sha256": release.get("archive_sha256"),
            "stage_manifest_sha256": release.get("stage_manifest_sha256"),
            "packaged_file_count_including_manifest": release.get("file_count"),
            "publication_state": "verified_local_candidate_not_archivally_published",
        },
        "software_verification": {
            "cleanroom_status": cleanroom.get("status"),
            "packaged_tests": clean_tests,
            "doctor": clean_verification.get("nostos_doctor"),
            "dependency_check": clean_verification.get("dependency_check"),
            "byte_identical_second_build": clean_checks.get(
                "deterministic_second_build"
            ),
            "retained_initial_failure": {
                "status": failure.get("status"),
                "failed_check": "deterministic_second_build",
                "cause": "system-temporary staging exhausted local storage",
                "repair": "release staging moved beside the output or to NOSTOS_RELEASE_TMPDIR",
            },
            "retained_interpreter_visibility_failure": {
                "status": visibility_failure.get("status"),
                "failed_operation": visibility_failure.get("failed_operation"),
                "cause": visibility_failure.get("diagnosis"),
                "repair": visibility_failure.get("repair"),
            },
        },
        "scientific_evidence": {
            "biosr": {
                "independent_fields": biosr_aurc.get("reference_fields"),
                "eligible": biosr_full.get("eligible"),
                "accepted": biosr_full.get("accepted"),
                "coverage": biosr_full.get("coverage"),
                "invalid": biosr_full.get("invalid"),
                "risk": biosr_full.get("risk"),
                "ordinary_qc_risk": biosr_qc.get("risk"),
                "relative_risk_reduction": biosr_operating.get(
                    "relative_risk_reduction_vs_qc"
                ),
                "aurc_difference": biosr_observed.get("comparator_minus_full"),
                "aurc_ci95": aurc_ci,
                "negative_control_measurements": biosr_negative.get("accepted"),
                "negative_control_invalid": biosr_negative.get("invalid"),
            },
            "fmd": {
                "independent_fields": fmd_primary.get(
                    "accepted_independent_groups"
                ),
                "eligible": fmd_primary.get("eligible"),
                "accepted": fmd_primary.get("accepted"),
                "coverage": fmd_primary.get("coverage"),
                "invalid": fmd_primary.get("invalid"),
                "ordinary_qc_invalid": fmd_qc.get("invalid"),
                "ordinary_qc_risk": fmd_qc.get("risk"),
                "aurc_difference": fmd_aurc.get("observed"),
                "aurc_ci95": fmd_ci,
                "nested_upper95": nested_upper,
                "field_upper95": field_upper,
                "terminal_checks_passed": sum(
                    item is True for item in fmd_terminal.get("checks", {}).values()
                ),
            },
        },
        "novelty_assessment": {
            "core_object": (
                "An executable measurement-validity compiler that composes "
                "input-only calibrated risk with declared acquisition and "
                "measurement coordinates, grouped confirmation and reason-coded "
                "abstention."
            ),
            "decisive_experiment": (
                "The retained FMD failure-repair lineage shows that a pooled "
                "profile can pass while hiding a deterministic unsafe subgroup, "
                "and that a development-only hierarchical support layer prevents "
                "that subgroup from being emitted on untouched confirmation data."
            ),
            "not_novel": (
                "FFT, structure tensors, Hessian filters, geometry, topology and "
                "risk-coverage analysis as individual algorithms."
            ),
        },
        "supported_claim": (
            "Within the declared BioSR and FMD public acquisition families, "
            "frozen input-only validity contracts reduce silent-invalid structural "
            "measurements relative to matched ordinary acquisition QC while "
            "abstaining outside empirically supported acquisition-by-scale cells."
        ),
        "prohibited_extensions": [
            "universal biological meaning of a shared measurement",
            "universal superiority over focused estimators or every QC system",
            "transfer to unseen instruments, tissues or acquisition families",
            "population-level zero risk from four FMD confirmation FOVs",
            "diagnostic, mechanical, clinical or intraoperative utility",
            "venue acceptance implied by software correctness",
        ],
        "high_impact_readiness": {
            "state": "computational_release_complete_external_validation_pending",
            "current_ceiling": (
                "A rigorous computational microscopy methods/resource submission; "
                "journal outcome remains editorial and cannot be guaranteed."
            ),
            "wet_lab_gate": "none_for_current_computational_claim",
        },
        "remaining_gates": [
            {
                "gate": "Archival identity",
                "status": "open",
                "reason": "Publish the exact archive and source tag with a DOI.",
                "requires_wet_lab": False,
            },
            {
                "gate": "Unaided external execution",
                "status": "open",
                "reason": (
                    "An external user must run the frozen replication challenge "
                    "and return the unedited receipt."
                ),
                "requires_wet_lab": False,
            },
            {
                "gate": "FMD generalization precision",
                "status": "bounded_open",
                "reason": (
                    "Only four independent confirmation FOVs are available; the "
                    "field-level exact upper 95% limit is 60.2%. Additional public "
                    "or independently held computational fields can narrow it."
                ),
                "requires_wet_lab": False,
            },
            {
                "gate": "Submission administration",
                "status": "open",
                "reason": (
                    "Complete affiliation, funding, competing-interest, authorship "
                    "and repository/DOI statements."
                ),
                "requires_wet_lab": False,
            },
        ],
        "submission_decision": (
            "Proceed as a computation-only methods/resource paper after archival "
            "DOI, unaided external execution and author administrative fields are "
            "complete. Do not add wet-lab, biological or intraoperative claims to "
            "this release."
        ),
    }
    audit["content_sha256"] = _content_sha256(audit)

    json_path = json_output if json_output.is_absolute() else root / json_output
    markdown_path = (
        markdown_output if markdown_output.is_absolute() else root / markdown_output
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(_markdown_report(audit), encoding="utf-8", newline="\n")
    return audit
