"""Assemble the terminal NOSTOS-0 claim, release and submission audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROTOCOL_VERSION = "nostos-final-max-audit/1.0"
AUDIT_DATE = "2026-08-28"
REQUIRED_RECEIPTS = {
    "evidence_index": "outputs/nostos0-evidence-bundle-v27/evidence_index.json",
    "bone_program": "outputs/nostos0-bone-contract-summary/bone_contract_program_summary.json",
    "bone_integrity": "outputs/nostos0-bone-download-integrity/integrity_verification.json",
    "manuscript_qa": "outputs/nostos0-manuscript-qa-v1/manuscript_qa.json",
    "release_receipt": "outputs/nostos0-release-candidate-v27/release_receipt.json",
    "release_manifest": "outputs/nostos0-release-candidate-v27/release_manifest.json",
    "cleanroom_initial_failure": "outputs/nostos0-release-candidate-v27/cleanroom_initial_failure.json",
    "cleanroom_verification": "outputs/nostos0-release-candidate-v27/cleanroom_verification.json",
    "bone_figure_manifest": "figures/nostos0/supplementary_figure_1_bone_contract_stress.manifest.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def derive_audit_status(checks: dict[str, bool]) -> str:
    """Fail closed if a technical audit prerequisite is absent."""
    return "complete_with_external_blockers" if checks and all(checks.values()) else "failed"


def _receipt_record(root: Path, relative: str) -> dict:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"Missing terminal-audit receipt: {relative}")
    return {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build_final_audit(project_root: Path, json_output: Path, markdown_output: Path) -> dict:
    root = project_root.resolve()
    receipts = {
        name: _receipt_record(root, relative)
        for name, relative in REQUIRED_RECEIPTS.items()
    }
    payloads = {
        name: _load(root / record["path"])
        for name, record in receipts.items()
    }
    evidence = payloads["evidence_index"]
    bone = payloads["bone_program"]
    integrity = payloads["bone_integrity"]
    manuscript = payloads["manuscript_qa"]
    release = payloads["release_receipt"]
    release_manifest = payloads["release_manifest"]
    cleanroom_failure = payloads["cleanroom_initial_failure"]
    cleanroom = payloads["cleanroom_verification"]
    figure_manifest = payloads["bone_figure_manifest"]
    cleanroom_verification = cleanroom.get("verification", {})
    cleanroom_pytest = cleanroom_verification.get("pytest", {})
    cleanroom_passed = int(cleanroom_pytest.get("passed", 0))
    cleanroom_skipped = int(cleanroom_pytest.get("skipped", 0))

    checks = {
        "evidence_index_complete": (
            evidence.get("status") == "complete_index"
            and len(evidence.get("entries", [])) == 79
            and not evidence.get("missing")
        ),
        "evidence_index_retains_not_ready_boundary": (
            evidence.get("nature_readiness") == "not_ready"
        ),
        "bone_source_integrity_passed": integrity.get("status") == "pass",
        "bone_program_complete_with_failed_primary_gates": (
            bone.get("status") == "complete_with_failed_primary_gates"
            and bone.get("nature_methods_readiness") == "not_ready"
            and bone.get("clinical_readiness") == "not_ready"
        ),
        "manuscript_production_qa_passed": manuscript.get("status") == "pass",
        "manuscript_submission_blockers_retained": (
            manuscript.get("submission_readiness")
            == "blocked_external_and_administrative"
            and len(manuscript.get("administrative_blockers", [])) == 4
        ),
        "release_audit_passed": (
            release.get("status") == "pass"
            and release_manifest.get("status") == "pass"
            and not release_manifest.get("audit_findings")
            and release_manifest.get("data_included") is False
        ),
        "release_build_is_deterministic": (
            cleanroom.get("verification", {}).get("deterministic_second_build_sha256")
            == release.get("archive_sha256")
        ),
        "initial_cleanroom_failure_retained": cleanroom_failure.get("status") == "fail",
        "rebuilt_cleanroom_passed": (
            cleanroom.get("status") == "pass"
            and cleanroom_passed == 180
            and cleanroom_skipped == 4
            and cleanroom_pytest.get("exit_code") == 0
            and cleanroom_verification.get("nostos_doctor", {}).get("status")
            == "ready"
        ),
        "runtime_version_matches_installed_metadata": (
            cleanroom_verification.get("runtime_version_matches_installed_metadata")
            == release_manifest.get("software_version")
            == "0.3.0"
        ),
        "bone_figure_is_traceable_and_non_generative": (
            figure_manifest.get("status") == "complete"
            and "no generative imagery"
            in str(figure_manifest.get("scientific_image_policy", "")).lower()
        ),
    }
    status = derive_audit_status(checks)

    supported_claims = [
        {
            "claim": "NOSTOS exposes calibrated structural estimators through a typed, provenance-preserving and failure-aware measurement contract.",
            "scope": "software architecture and output schema",
            "evidence": ["public_tool_workflows", "replication_reference_attested"],
        },
        {
            "claim": "Registered analytic operating envelopes passed all 24 required module-by-perturbation tests.",
            "scope": "synthetic truth only",
            "evidence": ["synthetic_truth", "module_perturbations"],
        },
        {
            "claim": "A declared local structure-tensor orientation endpoint reproduced an instrument-derived raster axis in the frozen PSHG breast confirmation.",
            "scope": "48 ROIs, 1,367,747 eligible pixels; median axial error 7.59 degrees and axial alignment 0.877 after a frozen 90-degree transform",
            "evidence": ["pshg_breast_orientation", "structure_tensor_comparator"],
        },
        {
            "claim": "Reference-mask vascular network responses were sampling-stable on STARE.",
            "scope": "20 supplied manual masks; survival-area and skeleton-length Spearman correlations 0.988 and 0.995",
            "evidence": ["stare_network_confirmation"],
        },
        {
            "claim": "Local thickness numerically agrees with archived maps and BoneJ on one public trabecular-bone archive.",
            "scope": "eight matched volumes; median voxelwise Spearman correlation 0.927, BoneJ concordance correlation coefficient 0.926 and median relative difference 7.14%",
            "evidence": ["bone", "bonej_thickness"],
        },
        {
            "claim": "The complete public bone stress program and all source archives are reproducibly indexed.",
            "scope": "73 verified files, 54,948,569,793 bytes; eight staged analyses; primary cross-program gates failed",
            "evidence": ["bone_download_integrity", "bone_contract_program_summary"],
        },
        {
            "claim": "The data-free software release installs and executes in a fresh environment.",
            "scope": f"{cleanroom_passed} passed tests, {cleanroom_skipped} skipped tests, matching runtime/package version, compatible dependency set and ready doctor report; author-operated clean room, not external replication",
            "evidence": ["release_receipt", "cleanroom_verification"],
        },
    ]
    rejected_or_unsupported = [
        "universal phenotype representation or universal specimen-identity fingerprint",
        "universal validity or abstention advantage at useful coverage",
        "automatic segmentation validity from perturbation stability",
        "validated cartilage segmentation or definitive cartilage biological inference",
        "population-level bone biology, disease discrimination or diagnostic performance",
        "tissue stiffness, strain, mechanics, treatment response or patient outcome",
        "clinical, intraoperative or surgical decision support",
        "Nature Methods or Nature Biomedical Engineering readiness",
    ]
    blockers = [
        {
            "category": "submission administration",
            "blocker": "The frozen release lacks an archival DOI.",
            "closure": "Archive the tagged release in Zenodo or an equivalent repository and replace the manuscript placeholder with the DOI.",
            "requires_external_authority": True,
        },
        {
            "category": "external reproducibility",
            "blocker": "No unaided external-operator replication receipt has been received.",
            "closure": "An identified external operator must run the frozen replication challenge from a fresh clone or release archive and return the unedited receipt.",
            "requires_external_authority": True,
        },
        {
            "category": "institutional and author declarations",
            "blocker": "Secondary-analysis determination, affiliation, funding, acknowledgements and competing-interest declarations are not finalized.",
            "closure": "The corresponding author and institution must provide the final determinations and text.",
            "requires_external_authority": True,
        },
        {
            "category": "flagship scientific evidence",
            "blocker": "The frozen bone support contract did not lower silent-invalid risk at matched useful coverage across acquisition strata.",
            "closure": "Prospectively freeze and pass a support contract on an untouched acquisition family at the prespecified coverage and risk gates.",
            "requires_external_authority": False,
        },
        {
            "category": "flagship external validity",
            "blocker": "Independent multi-laboratory or acquisition-family confirmation is absent.",
            "closure": "Obtain prospectively acquired or truly unseen data with independent experimental units and endpoint-appropriate references.",
            "requires_external_authority": True,
        },
        {
            "category": "clinical translation",
            "blocker": "No prospective intraoperative acquisition, clinical reference, decision-impact or outcome study exists.",
            "closure": "Run a separately governed prospective clinical study; public archives cannot close this gate.",
            "requires_external_authority": True,
        },
    ]
    sample_assessment = {
        "verdict": "The limiting issue is independent-unit and acquisition-family breadth, not raw image count.",
        "details": [
            "Thousands of tiles, sections or perturbations are technical observations and do not replace specimen-, mouse-, donor- or acquisition-level replication.",
            "The positive local-orientation, network and thickness endpoints are bounded to 48 ROIs, 20 masks and eight volumes, respectively.",
            "The five-record bone program is large in bytes and images but failed its primary useful-coverage and matched-risk gates.",
            "Current analyses preserve the highest available independent unit and explicitly label uncertain repository hierarchies; that is appropriate, but it cannot manufacture missing biological replication.",
        ],
    }

    audit = {
        "protocol_version": PROTOCOL_VERSION,
        "audit_date": AUDIT_DATE,
        "status": status,
        "terminal_verdict": {
            "software_release_candidate": "technical_pass",
            "manuscript_production": "pass",
            "current_scientific_resource": "bounded_and_auditable",
            "journal_submission": "blocked",
            "nature_methods_or_nature_biomedical_engineering": "not_ready",
            "clinical_or_intraoperative_use": "not_ready",
        },
        "technical_checks": checks,
        "receipts": receipts,
        "release_identity": {
            "software_version": "0.3.0",
            "planned_public_tag": "v0.3.0-rc16",
            "archive": release.get("archive"),
            "archive_bytes": release.get("archive_bytes"),
            "archive_sha256": release.get("archive_sha256"),
            "file_count": release.get("file_count"),
            "publication_state_at_audit": "prepared_for_public_push",
        },
        "evidence_index": {
            "entries": len(evidence.get("entries", [])),
            "missing": evidence.get("missing", []),
            "nature_readiness": evidence.get("nature_readiness"),
        },
        "supported_claims": supported_claims,
        "rejected_or_unsupported_claims": rejected_or_unsupported,
        "sample_assessment": sample_assessment,
        "blocking_requirements": blockers,
        "decision_rule": (
            "Do not submit the manuscript, claim Nature readiness or describe NOSTOS as clinically usable until every applicable external and administrative blocker is closed with a new immutable receipt. The current artifact may be shared as an explicitly labeled research-software release candidate."
        ),
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )

    claim_lines = "\n".join(
        f"- **Supported:** {item['claim']} Scope: {item['scope']}"
        for item in supported_claims
    )
    rejected_lines = "\n".join(f"- {claim}" for claim in rejected_or_unsupported)
    blocker_rows = "\n".join(
        f"| {item['category']} | {item['blocker']} | {item['closure']} |"
        for item in blockers
    )
    check_rows = "\n".join(
        f"| `{name}` | {'PASS' if passed else 'FAIL'} |" for name, passed in checks.items()
    )
    receipt_rows = "\n".join(
        f"| `{name}` | `{record['path']}` | `{record['sha256']}` |"
        for name, record in receipts.items()
    )
    markdown = f"""# NOSTOS-0 final maximum-rigor audit

**Audit date:** {AUDIT_DATE}  
**Protocol:** `{PROTOCOL_VERSION}`  
**Status:** `{status}`

## Executive verdict

The NOSTOS 0.3.0 release candidate is technically reproducible in an author-operated fresh environment, and the eight-page Word manuscript passes production QA. The scientific resource is bounded and auditable. It is **not submission-ready**, **not Nature Methods/Nature Biomedical Engineering-ready**, and **not clinically or intraoperatively validated**.

This distinction is deliberate. A technically clean release does not convert failed biological gates into positive evidence. The current contribution is a calibrated, provenance-preserving and failure-aware measurement contract around established estimators. The strongest positive external endpoints are local PSHG orientation, reference-mask vascular-network responses and same-mask local-thickness concordance. The larger public bone contract program is complete but failed its primary useful-coverage and matched-risk requirements.

## Terminal disposition

| Object | Disposition |
| --- | --- |
| Data-free software release | Technical pass; deterministic archive; no bundled source data or release-audit findings |
| Fresh-extraction verification | Pass after one retained dependency-declaration failure; {cleanroom_passed} tests passed, {cleanroom_skipped} skipped; runtime and installed package both report 0.3.0 |
| Manuscript production | Pass; 8 pages, 5 embedded figures, Times New Roman, visual and machine QA complete |
| Evidence index | Complete; 79 entries, zero missing; explicitly reports `not_ready` for Nature |
| Five-record public bone program | Complete with failed primary gates |
| Current journal submission | Blocked by DOI, unaided external execution and author/institutional declarations |
| Flagship high-impact claim | Blocked by failed useful-coverage/matched-risk evidence and absent multi-acquisition confirmation |
| Clinical or intraoperative use | Unsupported |

## What the evidence supports

{claim_lines}

## Claims the current evidence rejects or does not support

{rejected_lines}

## Sample and analysis sufficiency

The limiting issue is independent-unit and acquisition-family breadth, not raw image count. Thousands of tiles, sections and perturbations are technical observations. They do not replace independent mice, specimens, donors, laboratories or acquisitions. NOSTOS now preserves the highest available unit and does not treat patches as biological replicates. That analysis choice is appropriate; it also exposes why the current sample base cannot support a universal or clinical claim.

The five-record bone program verified 73 files totaling 54,948,569,793 bytes and executed eight staged analyses. Its full-contract coverage was 0.358 in paired SHG, 0.538 in the escalated rat-network stress test, 0.365 at 0.4 µm and 0.399 at 0.8 µm in human nanoCT. The narrow UV-PAM abstention control passed by withholding all 144 unsupported physical-collagen requests, but this is governance evidence rather than accuracy validation.

## Blocking requirements

| Category | Open blocker | Required closure evidence |
| --- | --- | --- |
{blocker_rows}

## Technical audit checks

| Check | Result |
| --- | --- |
{check_rows}

## Immutable receipt index

| Receipt | Path | SHA-256 |
| --- | --- | --- |
{receipt_rows}

## Release identity

- Planned public tag: `v0.3.0-rc16`
- Archive: `{release.get('archive')}`
- Archive size: {release.get('archive_bytes'):,} bytes
- Archive SHA-256: `{release.get('archive_sha256')}`
- Packaged file count: {release.get('file_count')}
- Public-release state at audit: prepared for push; the release URL and tag must be verified after publication.

## Final decision rule

Do not submit this manuscript, claim Nature readiness or describe NOSTOS as clinically usable until every applicable blocker above is closed with a new immutable receipt. The current artifact may be shared as an explicitly labeled research-software release candidate. Public data can finish the software and methods-resource layer; prospective independent and clinical evidence requires external specimens, operators and institutional authority.
"""
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(markdown, encoding="utf-8")
    return audit
