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
    EvidenceSpec("figure1_traceability", "figures/nostos0/figure_1_response_geometry_reference.manifest.json", "figure_provenance", "Figure 1 is deterministically generated from hash-locked public microscopy, micro-CT and frozen validation receipts; no generative imagery."),
    EvidenceSpec("dynamic_bulk_translation", "outputs/nostos0-dynamic-synthetic-v1/dynamic_validation.json", "synthetic_validation", "Explicit 2-D+t contract: calibrated integer bulk translation and blank-field abstention."),
    EvidenceSpec("bbbc035_dynamic_confirmation", "outputs/nostos0-bbbc035-dynamic-confirmation-v1/bbbc035_dynamic_confirmation.json", "external_public_content_confirmation", "Frozen bulk-registration endpoint passed all six gates on untouched BBBC035 microscopy content under programmed translations; not dense flow, tracking or native biological motion."),
    EvidenceSpec("dense_deformation_initial", "outputs/nostos0-dense-deformation-analytic-v1/dense_deformation_validation.json", "synthetic_prospective_failed_gate", "Frozen dense-deformation run passed six of seven gates with 0.109-pixel median error, but forward-backward uncertainty ranking failed at Spearman 0.202."),
    EvidenceSpec("dense_uncertainty_development", "outputs/nostos0-dense-uncertainty-development-v1/dense_uncertainty_development.json", "synthetic_post_failure_development", "Opened-cohort comparison selected estimator disagreement and froze a 95% additive conformal offset; development only."),
    EvidenceSpec("dense_deformation_analytic_confirmation", "outputs/nostos0-dense-deformation-analytic-confirmation-v1/dense_deformation_analytic_confirmation.json", "synthetic_identity_disjoint_confirmation", "Disjoint analytic confirmation passed all six gates with 0.107-pixel median error, 99.97% uncertainty coverage and 0.441-pixel median bound."),
    EvidenceSpec("bbbc035_dense_deformation_confirmation", "outputs/nostos0-bbbc035-dense-deformation-confirmation-v1/bbbc035_dense_deformation_confirmation.json", "external_public_content_confirmation", "Eight prespecified BBBC035 planes passed all seven dense-deformation gates under programmed smooth warps; not native motion, tracking, strain or mechanics."),
    EvidenceSpec("dense_tool_workflow_initial", "outputs/nostos0-dense-tool-workflow-v1/dense_tool_workflow_initial_failure.json", "software_public_data_failed_execution", "Initial frozen file workflow exposed a time-axis loader defect before measurement and is retained as failure evidence."),
    EvidenceSpec("dense_tool_workflow", "outputs/nostos0-dense-tool-workflow-v1/dense_tool_workflow.json", "software_public_data_end_to_end", "Unchanged dense file workflow passed all seven gates after introducing the explicit time-first loader."),
    EvidenceSpec("ctc_tracking_development", "outputs/nostos0-ctc-tracking-development-v1/ctc_tracking_development.json", "external_public_development", "Initial SIM+ sequence-01 tracking development showed strong continuation links but failed division inference and was inferior to the centroid-only continuation baseline."),
    EvidenceSpec("ctc_division_geometry_development", "outputs/nostos0-ctc-division-geometry-v1/ctc_division_geometry.json", "external_public_post_failure_development", "Outcome-aware geometry audit on opened SIM+ sequence 01; development only."),
    EvidenceSpec("ctc_division_rule_development", "outputs/nostos0-ctc-division-rule-development-v1/ctc_division_rule_development.json", "external_public_post_failure_development", "A 32-cell lineage-rule grid on opened SIM+ sequence 01 achieved development link F1 0.996 and division F1 0.897."),
    EvidenceSpec("ctc_native_tracking_confirmation", "outputs/nostos0-ctc-native-tracking-confirmation-v1/ctc_native_tracking_confirmation.json", "external_public_prospective_partial_gate", "Locked SIM+ sequence 02 and real HeLa sequence 01 tracking passed all continuation and real-data gates but failed the synthetic division-F1 gate, 0.758 versus 0.80."),
    EvidenceSpec("ctc_division_geometry_post_confirmation", "outputs/nostos0-ctc-division-geometry-v1_1/ctc_division_geometry.json", "external_public_post_failure_development", "Outcome-aware audit of now-open SIM+ sequence 02 after the division gate failed."),
    EvidenceSpec("ctc_division_rule_post_confirmation", "outputs/nostos0-ctc-division-rule-development-v1_2/ctc_division_rule_development.json", "external_public_post_failure_development", "Expanded rule grid on opened SIM+ sequence 02 reached division F1 0.848; not confirmation."),
    EvidenceSpec("ctc_hela02_lineage_initial", "outputs/nostos0-ctc-hela02-lineage-transfer-v1/ctc_hela02_lineage_transfer_initial_runtime.json", "external_public_pristine_failed_gate", "Reserved HeLa sequence 02 transfer failed division and runtime gates before removal of provably unused overlap computation."),
    EvidenceSpec("ctc_hela02_lineage_transfer", "outputs/nostos0-ctc-hela02-lineage-transfer-v1/ctc_hela02_lineage_transfer.json", "external_public_pristine_failed_gate", "Optimized identical assignments passed six of seven transfer gates; continuation F1 was 0.977 but division F1 0.410 missed the frozen 0.45 gate."),
    EvidenceSpec("ctc_tracking_tool_workflow", "outputs/nostos0-ctc-tracking-tool-workflow-v1/ctc_tracking_tool_workflow.json", "software_public_data_end_to_end", "The continuation-only application processed 92 real HeLa frames and 8,436 edges in 22.5 s; all eight workflow gates passed."),
    EvidenceSpec("bbbc006_spatial_confirmation", "outputs/nostos0-bbbc006-spatial-confirmation-v1/bbbc006_spatial_confirmation.json", "external_public_pristine_confirmation", "Frozen spatial-response confirmation passed all six gates on 64 hash-selected matched BBBC006 focal triplets, demonstrating adjacent-focus repeatability and defocus sensitivity."),
    EvidenceSpec("public_tool_workflows", "outputs/nostos0-public-tool-workflows-v1/public_tool_workflows.json", "software_public_data_end_to_end", "Four frozen public-data contracts passed all seven schema, module, calibration and runtime gates across 2-D, masked 2-D, masked 3-D and 2-D+t inputs."),
    EvidenceSpec("structure_tensor_comparator", "outputs/nostos0-structure-tensor-comparator-v1/structure_tensor_comparator.json", "upstream_cross_software_confirmation", "Frozen PSHG cross-software audit passed all six gates against scikit-image 0.25.2 over 1,367,747 eligible pixels."),
    EvidenceSpec("bbbc006_qc_initial", "outputs/nostos0-bbbc006-qc-v1/bbbc006_qc_validation.json", "external_public_endpoint_new_failed_gate", "Normalized-Laplacian focus ordering failed on the 64-case opened BBBC006 development subset and is retained as a rejected QC endpoint."),
    EvidenceSpec("focus_metric_development", "outputs/nostos0-focus-metric-development-v1/focus_metric_development.json", "external_public_post_failure_development", "Five focus metrics compared only on opened development identities; mean Tenengrad energy selected by frozen rule."),
    EvidenceSpec("bbbc006_qc_confirmation", "outputs/nostos0-bbbc006-qc-confirmation-v1/bbbc006_qc_confirmation.json", "external_public_identity_disjoint_confirmation", "Tenengrad focus and failure semantics passed all six gates on 128 hash-selected identities disjoint from development."),
    EvidenceSpec("hrf_network_initial", "outputs/nostos0-hrf-network-v1/hrf_network_validation.json", "external_public_prospective_failed_gate", "Frozen HRF reference-mask experiment failed absolute erosion-survival stability despite strong ranking and skeleton-length stability; image-derived vessel Dice was poor and remains separate."),
    EvidenceSpec("network_resampling_development", "outputs/nostos0-network-resampling-development-v1_1/network_resampling_development.json", "external_public_post_failure_development", "HRF-only correction of center-to-boundary distance and selection of a twofold occupancy policy; not confirmation."),
    EvidenceSpec("stare_network_confirmation", "outputs/nostos0-stare-network-confirmation-v1/stare_network_confirmation.json", "external_public_pristine_confirmation", "Untouched STARE confirmation passed all seven gates on 20 manual vascular networks, including sampling stability, skeleton-length concordance and inter-observer survival ranking."),
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
    EvidenceSpec("osteochondral_learned_adapter", "outputs/nostos0-osteochondral-learned-adapter-v1_1/osteochondral_learned_adapter_summary.json", "external_public_post_failure_development", "Five-fold patient-grouped U-Net development improved median Dice to 0.912 and interface error to 21.6 micrometres but failed six of nine gates, including uncertainty, band overlap, complete coverage, comparator superiority and downstream measurement agreement. Independent-acquisition confirmation remains required."),
    EvidenceSpec("osteochondral_boundary_adapter_v2", "outputs/nostos0-osteochondral-boundary-adapter-v2/osteochondral_learned_adapter_summary.json", "external_public_post_failure_development", "A prespecified boundary-aware loss did not repair the endpoint: median interface error worsened to 27.2 micrometres, five substantive gates remained failed and only three of six downstream measurements reached CCC 0.85."),
    EvidenceSpec("osteochondral_reference_definition_audit", "outputs/nostos0-osteochondral-reference-audit-v1/osteochondral_reference_definition_audit_summary.json", "external_public_post_test_reference_audit", "The threshold-derived mineralized-tissue masks are not unique traced interfaces. Across four frozen extraction policies, patient-median error ranged from 16.0 to 512.8 micrometres and model ranking changed; the public masks are inadequate for definitive continuous-interface validation."),
    EvidenceSpec("kymatio", "outputs/nostos0-benchmark-v1/kymatio_benchmark.json", "upstream_comparator", "Official scattering comparator on the synthetic split."),
    EvidenceSpec("pyradiomics", "outputs/nostos0-benchmark-v1/pyradiomics_benchmark.json", "upstream_comparator", "IBSI first-order subset conformance and synthetic comparator."),
    EvidenceSpec("pyradiomics_ibsi_texture", "outputs/nostos0-ibsi-texture-conformance-v1/ibsi_texture_conformance.json", "upstream_comparator", "Official IBSI workbook audit of 75 definitionally matched 3-D texture features, with unsupported features retained as not comparable."),
    EvidenceSpec("replication_reference", "outputs/nostos0-replication-reference-v1/replication_receipt.json", "software_conformance", "Author-operated reference execution of the public replication challenge; not independent replication."),
    EvidenceSpec("replication_reference_attested", "outputs/nostos0-replication-reference-v2/replication_receipt.json", "software_conformance_not_independent", "Author-operated dry run passes artifact integrity but is machine-rejected as independent external execution."),
    EvidenceSpec("comparator_imports", "outputs/nostos0-comparator-conformance-v1/comparator_conformance.json", "software_conformance", "Pinned upstream implementations import in declared interpreters."),
    EvidenceSpec("bone", "outputs/external-bone-v1/external_bone_validation.json", "external_public_validation", "Thickness agreement in eight public micro-CT volumes."),
    EvidenceSpec("bonej_thickness", "outputs/nostos0-bonej-thickness-v1/bonej_thickness_comparator.json", "upstream_cross_software_confirmation", "Frozen BoneJ 1.4.3 cross-software comparison passed all six gates on eight public masks; NOSTOS-BoneJ CCC 0.926 and median relative difference 7.14%."),
    EvidenceSpec("bone_download_integrity", "outputs/nostos0-bone-download-integrity/integrity_verification.json", "data_integrity", "All 73 public bone-program files (54,948,569,793 bytes) passed receipt SHA-256 and available deposited-MD5 verification."),
    EvidenceSpec("bone_orientation_compact", "outputs/nostos0-bone-contract-orientation-confirmation-v1/bone_orientation_confirmation.json", "external_public_prospective_failed_coverage", "Paired SHG/TPF diagnostic run eliminated observed accepted-case instability but retained only 35.8% SHG coverage, below the frozen 70% gate; its acceptance and invalidity perturbations were partly circular and the result is not confirmatory."),
    EvidenceSpec("bone_orientation_v2", "outputs/nostos0-bone-orientation-v2/bone_orientation_v2.json", "external_public_group_separated_failed_gate", "Mouse-separated SHG development found no promotable perturbation-only threshold; locally coherent annotations were too sparse and support discrimination was inadequate."),
    EvidenceSpec("bone_network_3d_v1", "outputs/nostos0-bone-network-3d/bone_network_3d.json", "external_public_stress_test_noninformative", "The first frozen 3D imported-mask corruption series generated no invalid cases and is retained as a stress-test design failure."),
    EvidenceSpec("bone_network_3d_v2", "outputs/nostos0-bone-network-3d-v2/bone_network_3d.json", "external_public_post_failure_development", "Escalated corruption development reduced risk-coverage area but full-contract coverage was 53.8%, below the master 80% gate; not independent confirmation."),
    EvidenceSpec("human_nanoct_scalar_v1", "outputs/nostos0-human-nanoct-transfer/human_nanoct_transfer.json", "external_public_prospective_failed_gate", "A scalar 3D tensor retained 92.0% coverage but failed to reject blur and resampling bias; full silent-invalid risk remained 38.9%."),
    EvidenceSpec("human_nanoct_scale_v2", "outputs/nostos0-human-nanoct-scale-response-v2/human_nanoct_scale_response.json", "external_public_post_failure_development", "Scale-indexed 3D response lowered risk at 0.4 and 0.8 micrometres but coverage remained 36.5% and 39.9%, below the frozen 80% gate."),
    EvidenceSpec("uvpam_abstention", "outputs/nostos0-uvpam-abstention/uvpam_abstention.json", "external_public_semantic_contract_control", "The complete contract correctly withheld a physical collagen endpoint from uncalibrated UV-PAM PNGs while emitting only explicitly pixel-domain generic descriptors; this is governance evidence, not accuracy validation."),
    EvidenceSpec("bone_contract_program_summary", "outputs/nostos0-bone-contract-summary/bone_contract_program_summary.json", "frozen_program_gate_table", "The consolidated five-record program is complete with failed primary gates: source integrity passed, but useful-coverage and matched cross-stratum validity advantage were not demonstrated."),
    EvidenceSpec("bone_contract_figure_traceability", "figures/nostos0/supplementary_figure_1_bone_contract_stress.manifest.json", "figure_provenance", "Supplementary Figure 1 is deterministically generated from checksum-verified public bone images and frozen receipts; no generative scientific imagery is used."),
    EvidenceSpec("manuscript_render_qa", "outputs/nostos0-manuscript-qa-v1/manuscript_qa.json", "document_production_qa", "The eight-page Word submission candidate passed machine and visual production checks, including figure identity, page continuity, Times New Roman use, caption presence and local-path/credential scans. The receipt explicitly retains external and administrative submission blockers."),
    EvidenceSpec("nuclei_sign_agnostic", "outputs/external-nuclei-v1/external_nuclei_validation.json", "external_public_development", "Initial BBBC039 test showing the failure of sign-agnostic Hessian localization."),
    EvidenceSpec("nuclei_polarity_refinement", "outputs/external-nuclei-v1_1/external_nuclei_validation.json", "external_public_post_test_refinement", "Polarity-aware BBBC039 result; same test set, therefore not pristine confirmatory evidence."),
    EvidenceSpec("nuclei_bbbc007_prospective", "outputs/external-nuclei-confirmatory-v1/external_nuclei_confirmatory.json", "external_public_prospective_failed_gate", "Prospectively frozen BBBC007 transfer: strong localization, but the prespecified ROC-AUC superiority interval versus LoG crossed zero."),
    EvidenceSpec("nuclei_bbbc020_independent", "outputs/external-nuclei-bbbc020-v1/external_nuclei_bbbc020.json", "external_public_prospective_failed_gate", "Independent murine BBBC020 acquisition: strong local localization, but no prespecified AP superiority over LoG."),
    EvidenceSpec("filament", "outputs/external-filament-v1/external_filament_validation.json", "external_public_exploratory", "Cross-species structural information; acquisition confounded."),
    EvidenceSpec("cartilage", "outputs/external-cartilage-v1/external_cartilage_validation.json", "external_public_exploratory", "Site-matched OA associations with unvalidated ROI proposal."),
    EvidenceSpec("cartilage_mask_review", "manifests/cartilage_mask_review_packet.json", "validation_infrastructure_pending", "Locked 40-case review packet; human reference masks remain pending."),
    EvidenceSpec("cartilage_review_evaluator_dry_run", "outputs/nostos0-cartilage-review-evaluator-dry-run-v1/dry_run_receipt.json", "software_conformance_not_human_validation", "Analytic-mask dry run exercises the blinded review evaluator; explicitly inadmissible as human-reference segmentation evidence."),
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
            "a manually adjudicated continuous-interface reference set: threshold-derived public mineralized-tissue masks produced materially policy-dependent errors and model rankings",
            "a validated ROI adapter: training-free and two learned development adapters failed their declared endpoint gates and still require independent-acquisition confirmation",
            "fit-for-purpose, prospectively successful independent-acquisition tests of shared measurements; universal specimen-identity retrieval is explicitly rejected",
            "a validated comparison geometry tied to a prespecified scientific endpoint; raw concatenation, canonical quotienting and same-specimen retrieval have failed prospective gates",
            "prospective validation of the perturbation-calibrated stability and abstention layer after canonical confirmation v3 failed",
            "a successful independent bone support contract: perturbation-only SHG support, 3D imported-mask stress coverage and human nanoCT scale-response coverage all failed frozen gates",
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
