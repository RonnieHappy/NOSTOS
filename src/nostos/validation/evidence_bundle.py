"""Build an integrity-checked index of the NOSTOS-0 evidence receipts."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvidenceSpec:
    identifier: str
    relative_path: str
    evidence_level: str
    interpretation: str


SPECS = (
    EvidenceSpec("synthetic_truth", "outputs/nostos0-synthetic-v1/validation.json", "synthetic_validation", "Analytic recovery and perturbation gates."),
    EvidenceSpec("module_perturbations", "outputs/nostos0-module-perturbations-v1/module_perturbation_matrix.json", "synthetic_validation", "Per-module invariance and sensitivity matrix."),
    EvidenceSpec("representation_benchmark", "outputs/nostos0-benchmark-v1/representation_benchmark.json", "synthetic_descriptive", "Frozen held-out construct discrimination; not biological validation."),
    EvidenceSpec("kymatio", "outputs/nostos0-benchmark-v1/kymatio_benchmark.json", "upstream_comparator", "Official scattering comparator on the synthetic split."),
    EvidenceSpec("pyradiomics", "outputs/nostos0-benchmark-v1/pyradiomics_benchmark.json", "upstream_comparator", "IBSI first-order subset conformance and synthetic comparator."),
    EvidenceSpec("pyradiomics_ibsi_texture", "outputs/nostos0-ibsi-texture-conformance-v1/ibsi_texture_conformance.json", "upstream_comparator", "Official IBSI workbook audit of 75 definitionally matched 3-D texture features, with unsupported features retained as not comparable."),
    EvidenceSpec("replication_reference", "outputs/nostos0-replication-reference-v1/replication_receipt.json", "software_conformance", "Author-operated reference execution of the public replication challenge; not independent replication."),
    EvidenceSpec("comparator_imports", "outputs/nostos0-comparator-conformance-v1/comparator_conformance.json", "software_conformance", "Pinned upstream implementations import in declared interpreters."),
    EvidenceSpec("bone", "outputs/external-bone-v1/external_bone_validation.json", "external_public_validation", "Thickness agreement in eight public micro-CT volumes."),
    EvidenceSpec("nuclei_sign_agnostic", "outputs/external-nuclei-v1/external_nuclei_validation.json", "external_public_development", "Initial BBBC039 test showing the failure of sign-agnostic Hessian localization."),
    EvidenceSpec("nuclei_polarity_refinement", "outputs/external-nuclei-v1_1/external_nuclei_validation.json", "external_public_post_test_refinement", "Polarity-aware BBBC039 result; same test set, therefore not pristine confirmatory evidence."),
    EvidenceSpec("filament", "outputs/external-filament-v1/external_filament_validation.json", "external_public_exploratory", "Cross-species structural information; acquisition confounded."),
    EvidenceSpec("cartilage", "outputs/external-cartilage-v1/external_cartilage_validation.json", "external_public_exploratory", "Site-matched OA associations with unvalidated ROI proposal."),
    EvidenceSpec("cartilage_mask_review", "manifests/cartilage_mask_review_packet.json", "validation_infrastructure_pending", "Locked 40-case review packet; human reference masks remain pending."),
    EvidenceSpec("cartilage_ablation_medial", "outputs/cartilage-ablations-v1_1/safo_medial.receipt.json", "external_public_exploratory", "Frozen medial boundary, purity, dark-object and conventional-feature extraction."),
    EvidenceSpec("cartilage_ablation_lateral", "outputs/cartilage-ablations-v1_1/safo_lateral.receipt.json", "external_public_exploratory", "Frozen lateral boundary, purity, dark-object and conventional-feature extraction."),
    EvidenceSpec("cartilage_ablation_analysis", "outputs/cartilage-ablation-analysis-v1_1/cartilage_ablation_analysis.json", "external_public_exploratory", "Paired correlations and participant-level nested prediction ablations."),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reported_status(payload: dict) -> str:
    if payload.get("status"):
        return str(payload["status"])
    validity = payload.get("validity")
    if isinstance(validity, dict) and validity.get("status"):
        return str(validity["status"])
    if isinstance(validity, str) and validity:
        return validity
    return "not_declared"


def build_evidence_bundle(project_root: Path, output: Path) -> dict:
    entries = []
    missing = []
    for spec in SPECS:
        path = project_root / spec.relative_path
        if not path.is_file():
            missing.append(spec.relative_path)
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries.append({
            "identifier": spec.identifier,
            "path": spec.relative_path,
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
            "protocol_version": payload.get("protocol_version"),
            "reported_status": _reported_status(payload),
            "evidence_level": spec.evidence_level,
            "interpretation": spec.interpretation,
        })
    payload = {
        "bundle_version": "nostos0-evidence-index/1.0",
        "status": "complete_index" if not missing else "incomplete_index",
        "project_root": str(project_root.resolve()),
        "entries": entries,
        "missing": missing,
        "nature_readiness": "not_ready",
        "blocking_evidence": [
            "blinded cartilage mask validation",
            "prospective independent-acquisition validation of the polarity-aware method",
            "cartilage structure-specific ablations",
            "external-user replication and archival release",
        ],
        "scope_rule": "A complete index proves receipt availability and integrity, not Nature-level readiness.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "evidence_index.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    checksum_lines = [f"{entry['sha256']}  {entry['path']}" for entry in entries]
    (output / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return payload
