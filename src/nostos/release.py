"""Build and audit a deterministic, data-free NOSTOS release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


PROTOCOL = "nostos-release-candidate/1.3"
ROOT_FILES = (
    ".gitattributes", ".gitignore", "README.md", "LICENSE", "CITATION.cff", "pyproject.toml",
    "uv.lock", "requirements-lock.txt", "requirements-comparators.lock.txt",
    "requirements-network-comparator.lock.txt",
    "requirements-segmentation-cu128.txt",
)
TREES = ("src", "tests", "configs", "manifests", "scripts", ".github", "microscopy_app")
SMALL_METHODS_V34_TREES = (
    "figures/nostos0_small_methods",
    "figures/nostos0_pshg_acquisition_shift",
    "figures/nostos0_tlt_pshg_xrd_transfer",
    "figures/nostos0_small_methods_si",
)
SMALL_METHODS_V34_FILES = (
    "docs/NOSTOS_SMALL_METHODS_ARTICLE_V34.md",
    "manuscripts/NOSTOS_Small_Methods_submission_candidate_v34.docx",
    "manuscripts/NOSTOS_Small_Methods_submission_candidate_v34_review.pdf",
    "manuscripts/NOSTOS_Small_Methods_Supporting_Information_v34.docx",
    "manuscripts/NOSTOS_Small_Methods_Supporting_Information_v34_review.pdf",
    "resources/journal_templates/Small_Methods_Article_Template_2025.docx",
)
FIGURES = (
    "figures/nostos0/figure_1_validity_contract_atlas.png",
    "figures/nostos0/figure_1_validity_contract_atlas.pdf",
    "figures/nostos0/figure_1_validity_contract_atlas.svg",
    "figures/nostos0/figure_2_biosr_selective_validity.png",
    "figures/nostos0/figure_2_biosr_selective_validity.pdf",
    "figures/nostos0/figure_2_biosr_selective_validity.svg",
    "figures/nostos0/figure_3_fmd_hidden_failure.png",
    "figures/nostos0/figure_3_fmd_hidden_failure.pdf",
    "figures/nostos0/figure_3_fmd_hidden_failure.svg",
    "figures/nostos0/figure_4_fmd_hierarchical_confirmation.png",
    "figures/nostos0/figure_4_fmd_hierarchical_confirmation.pdf",
    "figures/nostos0/figure_4_fmd_hierarchical_confirmation.svg",
    "figures/nostos0/validity_figures.manifest.json",
    "figures/nostos0/figure_1_response_geometry_reference.png",
    "figures/nostos0/figure_1_response_geometry_reference.svg",
    "figures/nostos0/figure_1_response_geometry_reference.manifest.json",
    "figures/nostos0/figure_2_synthetic_validation.png",
    "figures/nostos0/figure_2_synthetic_validation.svg",
    "figures/nostos0/figure_3_bone_validation.png",
    "figures/nostos0/figure_3_bone_validation.svg",
    "figures/nostos0/figure_4_cross_domain_boundaries.png",
    "figures/nostos0/figure_4_cross_domain_boundaries.svg",
    "figures/nostos0/supplementary_figure_1_bone_contract_stress.png",
    "figures/nostos0/supplementary_figure_1_bone_contract_stress.svg",
    "figures/nostos0/supplementary_figure_1_bone_contract_stress.manifest.json",
)
SCRIPTS = (
    "benchmark_kymatio.py", "benchmark_pyradiomics.py",
    "benchmark_pyradiomics_ibsi_texture.py",
    "audit_comparator_environments.py",
    "build_nostos0_main_figures.py",
    "build_nostos0_figure1.py",
    "build_nostos0_validity_figures.py",
    "fetch_bbbc039_reference.ps1",
    "fetch_bbbc007_reference.ps1",
    "fetch_bbbc020_reference.ps1",
    "run_response_benchmark_v2.py",
    "run_canonical_development.py",
    "run_canonical_confirmation_v3.py",
    "run_stability_weighting_development.py",
    "run_selective_fft_development.py",
    "run_selective_fft_confirmation.py",
    "run_selective_filament_transfer.py",
    "run_selective_shg_transfer.py",
    "run_consensus_reliability.py",
    "run_local_orientation_validation.py",
    "run_local_orientation_external_test.py",
    "run_pshg_external_orientation.py",
    "download_pshg_tiss.py",
    "run_osteochondral_learned_adapter.py",
    "audit_osteochondral_reference_definition.py",
    "validate_dynamic_synthetic.py",
    "validate_hrf_network.py",
    "develop_network_resampling.py",
    "confirm_stare_network.py",
    "confirm_bbbc035_dynamic.py",
    "prepare_bonej_inputs.py",
    "audit_bonej_thickness.py",
    "run_bonej_thickness.ijm",
    "prepare_bbbc006_spatial.py",
    "confirm_bbbc006_spatial.py",
    "run_public_tool_workflows.py",
    "audit_structure_tensor_comparator.py",
    "validate_bbbc006_qc.py",
    "develop_focus_metric.py",
    "confirm_bbbc006_qc.py",
    "validate_dense_deformation.py",
    "develop_dense_uncertainty.py",
    "confirm_dense_deformation_analytic.py",
    "confirm_bbbc035_dense_deformation.py",
    "run_dense_tool_workflow.py",
    "develop_ctc_tracking.py",
    "audit_ctc_division_geometry.py",
    "develop_ctc_division_rule.py",
    "confirm_ctc_tracking.py",
    "confirm_ctc_tracking_hela02.py",
    "run_ctc_tracking_tool_workflow.py",
    "dry_run_cartilage_review_evaluator.py",
    "build_bone_contract_figure.py",
    "build_bone_contract_summary.py",
    "build_manuscript_qa_receipt.py",
    "build_nostos0_methods_docx.py",
    "download_bone_contract_datasets.ps1",
    "verify_bone_contract_downloads.ps1",
    "run_bone_contract_program.ps1",
    "run_bone_contract_orientation.py",
    "run_bone_orientation_v2.py",
    "run_bone_network_3d.py",
)
DOCS = (
    "NOSTOS0_REPRODUCIBILITY_AND_METHODS.md",
    "NOSTOS0_CLAIM_EVIDENCE_LEDGER.md",
    "NOSTOS0_NOVELTY_POSITIONING.md",
    "NOSTOS0_FINAL_COMPUTATIONAL_METHODS_AUDIT_V3.md",
    "NOSTOS0_VALIDITY_PROFILE_COMPILER.md",
    "NOSTOS0_FIGURE_SOURCE_TABLE.md",
    "NOSTOS_CARTILAGE_ABLATION_REPORT.md",
    "NOSTOS_EXTERNAL_BONE_VALIDATION.md",
    "NOSTOS_EXTERNAL_FILAMENT_VALIDATION.md",
    "NOSTOS_EXTERNAL_CARTILAGE_VALIDATION.md",
    "NOSTOS_EXTERNAL_NUCLEI_VALIDATION.md",
    "NOSTOS_METHODS_LANDSCAPE.md",
    "NOSTOS0_METHODS_ARTICLE.md",
    "NOSTOS0_EXTERNAL_REPLICATION_PROTOCOL.md",
    "BBBC007_PROSPECTIVE_PROTOCOL.md",
    "BBBC020_PROSPECTIVE_PROTOCOL.md",
    "NOSTOS0_RESPONSE_GEOMETRY_BENCHMARK_V2_PROTOCOL.md",
    "NOSTOS0_ARCHITECTURE_DECISION_ROTATION_QUOTIENT.md",
    "NOSTOS0_CANONICAL_GEOMETRY_CONFIRMATION_V3_PROTOCOL.md",
    "NOSTOS0_SELECTIVE_FFT_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_FILAMENT_SELECTIVE_TRANSFER_PROTOCOL.md",
    "NOSTOS0_SHG_SELECTIVE_TRANSFER_PROTOCOL.md",
    "NOSTOS0_CONSENSUS_RELIABILITY_PROTOCOL.md",
    "NOSTOS0_LOCAL_ORIENTATION_PROTOCOL.md",
    "NOSTOS0_LOCAL_ORIENTATION_EXTERNAL_TEST_PROTOCOL.md",
    "NOSTOS0_PSHG_EXTERNAL_ORIENTATION_PROTOCOL.md",
    "NOSTOS0_PSHG_BREAST_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_OSTEOCHONDRAL_LEARNED_ADAPTER_BENCHMARK.md",
    "NOSTOS0_OSTEOCHONDRAL_BOUNDARY_ADAPTER_V2_PROTOCOL.md",
    "NOSTOS0_OSTEOCHONDRAL_REFERENCE_DEFINITION_AUDIT.md",
    "NOSTOS0_COMPLETE_PUBLIC_DATA_READINESS_AUDIT.md",
    "NOSTOS0_HRF_NETWORK_VALIDATION_PROTOCOL.md",
    "NOSTOS0_STARE_NETWORK_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_BBBC035_DYNAMIC_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_BONEJ_THICKNESS_COMPARATOR_PROTOCOL.md",
    "NOSTOS0_BBBC006_SPATIAL_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_PUBLIC_TOOL_WORKFLOW_PROTOCOL.md",
    "NOSTOS0_STRUCTURE_TENSOR_COMPARATOR_PROTOCOL.md",
    "NOSTOS0_BBBC006_QC_VALIDATION_PROTOCOL.md",
    "NOSTOS0_BBBC006_QC_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_DENSE_DEFORMATION_PROTOCOL.md",
    "NOSTOS0_DENSE_TOOL_WORKFLOW_PROTOCOL.md",
    "NOSTOS0_NATIVE_OBJECT_TRACKING_PROTOCOL.md",
    "NOSTOS0_TRACKING_TOOL_WORKFLOW_PROTOCOL.md",
    "reference_mask_review_instructions.md",
    "NOSTOS0_SOFTWARE_RESOURCE_ARTICLE.md",
    "NOSTOS0_computational_methods_submission_candidate_v30.docx",
    "NOSTOS0_computational_methods_submission_candidate_v30.pdf",
    "NOSTOS0_BONE_CONTRACT_ABLATION_PROTOCOL.md",
    "NOSTOS0_BONE_ORIENTATION_V2_AMENDMENT.md",
    "NOSTOS0_BONE_ORIENTATION_V2_RESULT.md",
    "NOSTOS0_BONE_3D_NETWORK_CONTRACT.md",
    "NOSTOS0_BONE_3D_NETWORK_V2_AMENDMENT.md",
    "NOSTOS0_BONE_3D_NETWORK_RESULT.md",
    "NOSTOS0_HUMAN_NANOCT_TRANSFER_PROTOCOL.md",
    "NOSTOS0_HUMAN_NANOCT_V1_RESULT.md",
    "NOSTOS0_HUMAN_NANOCT_SCALE_RESPONSE_V2.md",
    "NOSTOS0_HUMAN_NANOCT_SCALE_V2_RESULT.md",
    "NOSTOS0_UVPAM_ABSTENTION_PROTOCOL.md",
    "NOSTOS0_UVPAM_ABSTENTION_RESULT.md",
    "NOSTOS0_OPERATOR_GUIDE.md",
    "NOSTOS0_NATURE_LEVEL_EVIDENCE_MATRIX_V1.md",
    "NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_PROTOCOL.md",
    "NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_RESULT.md",
    "NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_1_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_2_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_3_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_4_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_5_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_6_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_6_RESULT.md",
    "NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_LINEAGE_V2_TO_V2_6.md",
    "NOSTOS0_PSHG_INDEPENDENT_UNIT_RISK_AUDIT_V1_PROTOCOL.md",
    "NOSTOS0_CROSS_DOMAIN_EVIDENCE_REGISTRY_V1.md",
)
EVIDENCE_INDEX = Path("outputs/nostos0-evidence-bundle-v30/evidence_index.json")
LATEST_EVIDENCE_FILES = (
    "outputs/nostos0-synthetic-physical-truth-v2/validation.json",
    "outputs/nostos0-synthetic-physical-truth-v2-1-confirmation/validation.json",
    "outputs/nostos0-synthetic-physical-truth-v2-2-confirmation/validation.json",
    "outputs/nostos0-synthetic-physical-truth-v2-3-confirmation/validation.json",
    "outputs/nostos0-synthetic-physical-truth-v2-4-confirmation/validation.json",
    "outputs/nostos0-synthetic-physical-truth-v2-5-confirmation/validation.json",
    "outputs/nostos0-synthetic-physical-truth-v2-6-confirmation/validation.json",
    "outputs/nostos0-synthetic-physical-truth-v2-6-audit/audit.json",
    "outputs/nostos0-spatial-estimator-development-v2-6/development.json",
    "outputs/nostos0-v2-6-integration-audit/integration_audit.json",
    "outputs/nostos0-v2-6-integration-audit/pytest.xml",
    "outputs/nostos0-pshg-independent-unit-risk-audit-v1/audit.json",
    "outputs/nostos0-cross-domain-evidence-registry-v1/registry.json",
)
TEXT_SUFFIXES = {".py", ".md", ".toml", ".txt", ".json", ".csv", ".yml", ".yaml", ".cff", ".ps1"}
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", "nostos.egg-info"}
POST_RELEASE_AUDIT_PATHS = {
    "outputs/nostos0-computational-release-audit-v1/final_audit.json",
    "outputs/nostos0-release-candidate-v30/cleanroom_interpreter_visibility_failure.json",
    "docs/NOSTOS0_FINAL_COMPUTATIONAL_METHODS_AUDIT_V4.md",
    "src/nostos/validation/final_audit.py",
    "tests/test_final_audit.py",
    "scripts/build_final_max_audit.py",
    "manifests/release_candidate_v29_audit_manifest.json",
    "outputs/nostos0-release-candidate-v29/release_receipt.json",
    "outputs/nostos0-release-candidate-v29/release_manifest.json",
    "outputs/nostos0-release-candidate-v29/nostos-0.3.0-release-candidate.zip",
    "outputs/nostos0-release-candidate-v29/cleanroom_initial_failure.json",
    "outputs/nostos0-release-candidate-v29/cleanroom_second_failure.json",
    "outputs/nostos0-release-candidate-v29/cleanroom_verification.json",
    "manifests/release_candidate_v30_audit_manifest.json",
    "outputs/nostos0-release-candidate-v30/release_receipt.json",
    "outputs/nostos0-release-candidate-v30/release_manifest.json",
    "outputs/nostos0-release-candidate-v30/nostos-0.3.0-release-candidate.zip",
    "outputs/nostos0-release-candidate-v30/cleanroom_verification.json",
}
SCANNER_SOURCE_PATHS = {
    "src/nostos/release.py",
    "src/nostos/validation/computational_release_audit.py",
    "src/nostos/validation/manuscript_qa.py",
}
SECRET_PATTERNS = (
    re.compile(r"s2k-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
)
PRIVATE_PATH_PATTERNS = (
    re.compile(r"(?i)[A-Z]:\\Users\\"),
    re.compile(r"(?i)[A-Z]:\\\\Users\\\\"),
    re.compile(r"(?i)[A-Z]:/Users/"),
    re.compile(r"(?i)E:\\NOSTOS"),
    re.compile(r"(?i)E:\\\\NOSTOS"),
    re.compile(r"(?i)E:/NOSTOS"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cleanup_stage(stage_parent: Path, work_root: Path) -> None:
    """Remove only the verified per-build staging directory and empty work root."""

    stage_parent = stage_parent.resolve()
    work_root = work_root.resolve()
    if stage_parent.parent != work_root or not stage_parent.name.startswith(
        "nostos-release-stage-"
    ):
        raise RuntimeError(f"Refusing to remove unexpected release stage: {stage_parent}")
    shutil.rmtree(stage_parent, ignore_errors=True)
    try:
        work_root.rmdir()
    except OSError:
        pass


def _raw_copy_is_safe(source: Path, project_root: Path) -> bool:
    if source.suffix.lower() not in TEXT_SUFFIXES and source.name not in {"LICENSE", ".gitignore"}:
        return True
    relative = source.relative_to(project_root).as_posix()
    if relative in SCANNER_SOURCE_PATHS:
        return True
    text = source.read_text(encoding="utf-8", errors="replace")
    return not any(pattern.search(text) for pattern in (*SECRET_PATTERNS, *PRIVATE_PATH_PATTERNS))


def _integrity_preserved_paths(root: Path) -> set[Path]:
    """Return path-safe files whose original bytes are part of an integrity contract."""

    candidates: set[Path] = set()
    configs = root / "configs"
    if configs.is_dir():
        candidates.update(path for path in configs.rglob("*") if path.is_file())
    manifests = root / "manifests"
    if manifests.is_dir():
        candidates.update(path for path in manifests.rglob("*") if path.is_file())

    documents: list[Path] = [path for path in candidates if path.suffix.lower() == ".json"]
    index_path = root / EVIDENCE_INDEX
    if index_path.is_file():
        candidates.add(index_path)
        documents.append(index_path)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for entry in index.get("entries", []):
            path = root / Path(entry["path"])
            if path.is_file():
                candidates.add(path)
                if path.suffix.lower() == ".json":
                    documents.append(path)
    for relative in LATEST_EVIDENCE_FILES:
        path = root / relative
        if path.is_file():
            candidates.add(path)
            if path.suffix.lower() == ".json":
                documents.append(path)

    def referenced_paths(value: object) -> list[Path]:
        found: list[Path] = []
        if isinstance(value, dict):
            def append_if_verified(
                raw_path: object,
                expected_sha256: object,
                expected_bytes: object,
            ) -> None:
                if not isinstance(raw_path, str) or not isinstance(expected_sha256, str):
                    return
                relative = Path(raw_path)
                if relative.is_absolute() or relative.drive or ".." in relative.parts:
                    return
                candidate = root / relative
                if (
                    candidate.is_file()
                    and (expected_bytes is None or candidate.stat().st_size == int(expected_bytes))
                    and _sha256(candidate) == expected_sha256
                ):
                    found.append(candidate)
            append_if_verified(value.get("path"), value.get("sha256"), value.get("bytes"))
            for key, raw_path in value.items():
                if not isinstance(key, str) or not key.endswith("_path"):
                    continue
                prefix = key[:-5]
                append_if_verified(
                    raw_path,
                    value.get(prefix + "_sha256"),
                    value.get(prefix + "_bytes"),
                )
            for child in value.values():
                found.extend(referenced_paths(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(referenced_paths(child))
        return found

    for document in documents:
        try:
            payload = json.loads(document.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        candidates.update(referenced_paths(payload))
    return {
        path.resolve()
        for path in candidates
        if path.is_file()
        and path.relative_to(root).as_posix() not in POST_RELEASE_AUDIT_PATHS
        and _raw_copy_is_safe(path, root)
    }


def _copy_file(
    source: Path,
    destination: Path,
    project_root: Path,
    *,
    preserve_bytes: bool = False,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if preserve_bytes:
        shutil.copyfile(source, destination)
    elif source.suffix.lower() in TEXT_SUFFIXES or source.name in {"LICENSE", ".gitignore"}:
        text = source.read_text(encoding="utf-8")
        relative = source.relative_to(project_root).as_posix()
        if relative not in SCANNER_SOURCE_PATHS:
            project = str(project_root)
            text = text.replace(project.replace("\\", "\\\\"), "<PROJECT_ROOT>")
            text = text.replace(project, "<PROJECT_ROOT>")
            text = re.sub(r"(?i)C:\\Users\\yanyl\\OneDrive\\NOSTOS", "<PROJECT_ROOT>", text)
            text = re.sub(
                r"(?i)C:\\\\Users\\\\yanyl\\\\OneDrive\\\\NOSTOS",
                "<PROJECT_ROOT>",
                text,
            )
            text = re.sub(r"(?i)[A-Z]:\\Users\\[^\\\s\"']+", "<USER_ROOT>", text)
            text = re.sub(
                r"(?i)[A-Z]:\\\\Users\\\\[^\\\s\"']+", "<USER_ROOT>", text
            )
            text = re.sub(r"(?i)[A-Z]:/Users/[^/\s\"']+", "<USER_ROOT>", text)
            text = re.sub(r"(?i)E:\\\\NOSTOS", "<DATA_ROOT>", text)
            text = re.sub(r"(?i)E:\\NOSTOS", "<DATA_ROOT>", text)
            text = re.sub(r"(?i)E:/NOSTOS", "<DATA_ROOT>", text)
        destination.write_text(text, encoding="utf-8", newline="\n")
    else:
        shutil.copyfile(source, destination)


def _selected_files(root: Path) -> list[Path]:
    selected: set[Path] = set()
    for relative in ROOT_FILES:
        path = root / relative
        if path.is_file():
            selected.add(path)
    for tree in TREES:
        base = root / tree
        if base.is_dir():
            selected.update(
                path for path in base.rglob("*")
                if path.is_file() and not any(part in SKIP_PARTS for part in path.parts)
                and path.suffix.lower() not in {".pyc", ".pyo"}
            )
    for tree in SMALL_METHODS_V34_TREES:
        base = root / tree
        if base.is_dir():
            selected.update(path for path in base.rglob("*") if path.is_file())
    for relative in SMALL_METHODS_V34_FILES:
        path = root / relative
        if path.is_file():
            selected.add(path)
    for name in SCRIPTS:
        path = root / "scripts" / name
        if path.is_file():
            selected.add(path)
    for name in DOCS:
        path = root / "docs" / name
        if path.is_file():
            selected.add(path)
    for relative in FIGURES:
        path = root / relative
        if path.is_file():
            selected.add(path)
    for relative in LATEST_EVIDENCE_FILES:
        path = root / relative
        if path.is_file():
            selected.add(path)
    if EVIDENCE_INDEX.is_absolute():
        raise ValueError("Evidence index must be relative")
    index_path = root / EVIDENCE_INDEX
    if index_path.is_file():
        selected.add(index_path)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for entry in index.get("entries", []):
            relative = Path(entry["path"])
            candidate = root / relative
            if candidate.is_file():
                selected.add(candidate)
    return sorted(
        (
            path
            for path in selected
            if path.relative_to(root).as_posix() not in POST_RELEASE_AUDIT_PATHS
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _audit(stage: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in sorted(stage.rglob("*")):
        if not path.is_file() or path.name == "release_manifest.json":
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE", ".gitignore"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append({"path": path.relative_to(stage).as_posix(), "kind": "possible_secret"})
                break
        relative = path.relative_to(stage).as_posix()
        if relative not in SCANNER_SOURCE_PATHS and any(
            pattern.search(text) for pattern in PRIVATE_PATH_PATTERNS
        ):
            findings.append({"path": path.relative_to(stage).as_posix(), "kind": "private_absolute_path"})
    return findings


def build_release(project_root: Path, output: Path) -> dict:
    root = project_root.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    configured_work_root = os.environ.get("NOSTOS_RELEASE_TMPDIR")
    work_root = (
        Path(configured_work_root).expanduser().resolve()
        if configured_work_root
        else (output.parent / ".nostos-release-tmp").resolve()
    )
    work_root.mkdir(parents=True, exist_ok=True)
    stage_parent = Path(
        tempfile.mkdtemp(prefix="nostos-release-stage-", dir=work_root)
    )
    stage = stage_parent / "nostos-0.3.0"
    stage.mkdir()
    try:
        preserved_paths = _integrity_preserved_paths(root)
        selected_files = sorted(
            set(_selected_files(root)) | preserved_paths,
            key=lambda path: path.relative_to(root).as_posix(),
        )
        for source in selected_files:
            _copy_file(
                source,
                stage / source.relative_to(root),
                root,
                preserve_bytes=source.resolve() in preserved_paths,
            )
    except Exception:
        _cleanup_stage(stage_parent, work_root)
        raise
    portable_storage = {
        "project_root": ".",
        "bulk_storage_root": "bulk",
        "data_root": "bulk",
        "python_environment": ".venv",
        "cpu_app": "http://127.0.0.1:8765",
        "gpu_comparison_app": "http://127.0.0.1:8766",
    }
    (stage / "storage.json").write_text(
        json.dumps(portable_storage, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    portable_data = stage / "bulk"
    portable_data.mkdir(parents=True)
    (portable_data / ".gitkeep").write_text("", encoding="utf-8")

    findings = _audit(stage)
    files = []
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            files.append({
                "path": path.relative_to(stage).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            })
    manifest = {
        "protocol_version": PROTOCOL,
        "software_version": "0.3.0",
        "status": "pass" if not findings else "fail",
        "data_included": False,
        "file_count": len(files),
        "files": files,
        "audit_findings": findings,
        "limitations": [
            "Archive integrity is not independent scientific replication.",
            "BioSR confirmation contains eight independent fields and final FMD confirmation contains four independent fields from one widefield acquisition family.",
            "FMD lacks pixel-spacing metadata, so its measurement coordinates remain pixel-relative.",
            "Every validity profile is bounded to its declared acquisition family, endpoint and measurement coordinate; unseen or unsupported cells must abstain.",
            "The included structural estimators do not acquire universal biological meaning merely by sharing a response schema.",
            "No diagnosis, mechanics, clinical usefulness or intraoperative-performance claim is established by this computation-only release.",
            "Unaided external execution of the frozen archive has not yet been returned.",
            "Repository and archival DOI placeholders must be replaced before publication.",
        ],
    }
    manifest_path = stage / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    if findings:
        _cleanup_stage(stage_parent, work_root)
        raise RuntimeError(f"Release audit failed: {findings}")

    archive = output / "nostos-0.3.0-release-candidate.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        archive.unlink()
    timestamp = (2026, 8, 29, 0, 0, 0)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(stage.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo((Path(stage.name) / path.relative_to(stage)).as_posix(), timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())
    receipt = {
        "protocol_version": PROTOCOL,
        "status": "pass",
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": _sha256(archive),
        "stage_manifest_sha256": _sha256(manifest_path),
        "file_count": len(files) + 1,
    }
    (output / "release_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    shutil.copyfile(manifest_path, output / "release_manifest.json")
    _cleanup_stage(stage_parent, work_root)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("outputs/nostos0-release-candidate-v30"))
    args = parser.parse_args()
    print(json.dumps(build_release(args.project_root, args.output), indent=2))


if __name__ == "__main__":
    main()
