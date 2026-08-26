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
    EvidenceSpec("response_geometry_benchmark_v2", "outputs/nostos0-response-benchmark-v2/response_geometry_benchmark_v2.json", "synthetic_prospective_failed_gate", "Larger prospectively frozen distribution-shift test: raw response concatenation failed three of five gates and was inferior to matched collapsed summaries and PyRadiomics."),
    EvidenceSpec("canonical_confirmation_v3", "outputs/nostos0-canonical-confirmation-v3/canonical_confirmation_v3.json", "synthetic_prospective_failed_gate", "New-seed confirmation of rotation-quotiented comparison geometry failed four of seven gates; improvement over raw coordinates was uncertain and perturbation distance fell only 3%."),
    EvidenceSpec("stability_weighting_development", "outputs/nostos0-stability-development-v1_1/stability_weighting_development.json", "synthetic_development", "Training-only paired-perturbation audit: corrected label-free stability weighting matched, but did not improve upon, augmented canonical performance."),
    EvidenceSpec("selective_fft_confirmation", "outputs/nostos0-selective-fft-confirmation-v1/selective_fft_confirmation.json", "synthetic_prospective_partial_gate", "Prospective selective-measurement confirmation passed five of six gates: 93.8% coverage, 1.07% selective risk, Wilson upper 2.31%, and invalid-detection AUC 0.980; an absolute risk-reduction gate was unattainable because cohort risk was 4.67%."),
    EvidenceSpec("selective_filament_transfer", "outputs/nostos0-selective-filament-transfer-v1/selective_filament_transfer.json", "external_public_prospective_failed_gate", "Frozen transfer of the FFT abstention rule to MyceliumSeg failed because only two of 30 branching-network masks supplied an eligible global reference axis; the dataset is unsuitable for inferential global-orientation validation."),
    EvidenceSpec("selective_shg_transfer", "outputs/nostos0-selective-shg-transfer-v1/selective_shg_transfer.json", "external_public_prospective_failed_gate", "Frozen transfer to 199 annotated SHG collagen test patches failed three of six gates: 95.1% coverage carried 33.3% selective risk, cluster-bootstrap upper 40.5%, median disagreement 6.44 degrees, and invalid-detection AUC 0.677."),
    EvidenceSpec("consensus_reliability", "outputs/nostos0-consensus-reliability-v1/consensus_reliability.json", "external_public_group_separated_failed_gate", "Estimator-consensus redesign failed before confirmation: development AUC was 0.740 and no threshold attained 10% risk at 30% coverage; the locked confirmation therefore accepted no cases and had AUC 0.705."),
    EvidenceSpec("local_orientation_adaptive", "outputs/nostos0-local-orientation-v1/local_orientation_validation.json", "external_public_group_separated_failed_gate", "Adaptive local scale selection failed because no development confidence threshold attained the frozen risk/coverage criterion; the failure motivated a scale-declared endpoint."),
    EvidenceSpec("local_orientation_external_test", "outputs/nostos0-local-orientation-external-v1/local_orientation_external_test.json", "external_public_endpoint_new_pass", "Scale-declared sigma-2 local orientation passed all eight gates on 19,657 annotated tangent pixels from 115 source groups: median axial error 6.72 degrees, group-bootstrap interval 6.24–7.25 degrees, and axial alignment 0.832."),
    EvidenceSpec("pshg_skin_orientation", "outputs/nostos0-pshg-external-orientation-v1/pshg_external_orientation.json", "external_public_prospective_failed_gate", "Pristine PSHG skin transfer failed because the archived polarization-phase axis was approximately orthogonal to the raster ridge axis; median error was 82.25 degrees across 53 ROIs. Retained as development and coordinate-calibration evidence."),
    EvidenceSpec("pshg_breast_orientation", "outputs/nostos0-pshg-breast-orientation-v1/pshg_external_orientation.json", "external_public_pristine_confirmation", "After freezing the 90-degree instrument-to-raster calibration learned only from skin, untouched breast confirmation passed all nine gates across 48 ROIs and 1,367,747 pixels: median error 7.59 degrees, ROI-bootstrap interval 7.26–7.91 degrees, and axial alignment 0.877."),
    EvidenceSpec("biological_retrieval_development", "outputs/nostos0-biological-retrieval-development-v1/biological_retrieval_development.json", "external_public_development", "Development-only same-specimen retrieval across four biological domains under a mild synthetic acquisition shift."),
    EvidenceSpec("biological_retrieval_confirmation", "outputs/nostos0-biological-retrieval-confirmation-v1/biological_retrieval_confirmation.json", "external_public_prospective_failed_gate", "Prospectively frozen, identity-disjoint confirmation under a severe compound acquisition shift failed six substantive gates: primary macro top-1 accuracy was 0.100 (bootstrap interval 0.033–0.183). This rejects use of the compact response geometry as a universal specimen-identity fingerprint."),
    EvidenceSpec("biological_retrieval_orbit_redesign", "outputs/nostos0-orbit-redesign-development-v1/orbit_redesign_development.json", "external_public_post_test_development", "Post-failure orbit-aggregation redesign on the opened confirmation cases remained weak and is retained as development evidence only; the best tested ablation reached macro top-1 accuracy 0.233."),
    EvidenceSpec("osteochondral_interface_development", "outputs/nostos0-osteochondral-interface-development-v1/osteochondral_interface_development.json", "external_public_group_separated_development", "Development of a training-free dynamic-path adapter on nine patients failed to reach usable boundary error and was worse than a global-threshold comparator."),
    EvidenceSpec("osteochondral_interface_confirmation", "outputs/nostos0-osteochondral-interface-confirmation-v1/osteochondral_interface_confirmation.json", "external_public_prospective_failed_gate", "Patient-disjoint confirmation on 532 slices from ten patients failed seven substantive gates: median interface error 537.2 micrometres, bootstrap interval 465.2–846.2, 0.39% of columns within 30 micrometres and zero of six downstream measurements concordant. The training-free PTA micro-CT adapter is rejected."),
    EvidenceSpec("kymatio", "outputs/nostos0-benchmark-v1/kymatio_benchmark.json", "upstream_comparator", "Official scattering comparator on the synthetic split."),
    EvidenceSpec("pyradiomics", "outputs/nostos0-benchmark-v1/pyradiomics_benchmark.json", "upstream_comparator", "IBSI first-order subset conformance and synthetic comparator."),
    EvidenceSpec("pyradiomics_ibsi_texture", "outputs/nostos0-ibsi-texture-conformance-v1/ibsi_texture_conformance.json", "upstream_comparator", "Official IBSI workbook audit of 75 definitionally matched 3-D texture features, with unsupported features retained as not comparable."),
    EvidenceSpec("replication_reference", "outputs/nostos0-replication-reference-v1/replication_receipt.json", "software_conformance", "Author-operated reference execution of the public replication challenge; not independent replication."),
    EvidenceSpec("comparator_imports", "outputs/nostos0-comparator-conformance-v1/comparator_conformance.json", "software_conformance", "Pinned upstream implementations import in declared interpreters."),
    EvidenceSpec("bone", "outputs/external-bone-v1/external_bone_validation.json", "external_public_validation", "Thickness agreement in eight public micro-CT volumes."),
    EvidenceSpec("nuclei_sign_agnostic", "outputs/external-nuclei-v1/external_nuclei_validation.json", "external_public_development", "Initial BBBC039 test showing the failure of sign-agnostic Hessian localization."),
    EvidenceSpec("nuclei_polarity_refinement", "outputs/external-nuclei-v1_1/external_nuclei_validation.json", "external_public_post_test_refinement", "Polarity-aware BBBC039 result; same test set, therefore not pristine confirmatory evidence."),
    EvidenceSpec("nuclei_bbbc007_prospective", "outputs/external-nuclei-confirmatory-v1/external_nuclei_confirmatory.json", "external_public_prospective_failed_gate", "Prospectively frozen BBBC007 transfer: strong localization, but the prespecified ROC-AUC superiority interval versus LoG crossed zero."),
    EvidenceSpec("nuclei_bbbc020_independent", "outputs/external-nuclei-bbbc020-v1/external_nuclei_bbbc020.json", "external_public_prospective_failed_gate", "Independent murine BBBC020 acquisition: strong local localization, but no prespecified AP superiority over LoG."),
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
        "project_root": "<PROJECT_ROOT>",
        "entries": entries,
        "missing": missing,
        "nature_readiness": "not_ready",
        "blocking_evidence": [
            "blinded cartilage mask validation",
            "a validated ROI adapter: the prospective training-free osteochondral-interface adapter failed decisively, and imported or learned segmentation requires separate validation",
            "fit-for-purpose, prospectively successful independent-acquisition tests of shared measurements; universal specimen-identity retrieval is explicitly rejected",
            "a validated comparison geometry tied to a prespecified scientific endpoint; raw concatenation, canonical quotienting and same-specimen retrieval have failed prospective gates",
            "prospective validation of the perturbation-calibrated stability and abstention layer after canonical confirmation v3 failed",
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
