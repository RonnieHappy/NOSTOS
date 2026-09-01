"""Build a hash-verified registry of positive, mixed and negative NOSTOS evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "outputs/nostos0-cross-domain-evidence-registry-v1/registry.json"
OUTPUT_MD = ROOT / "docs/NOSTOS0_CROSS_DOMAIN_EVIDENCE_REGISTRY_V1.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(relative: str) -> tuple[Path, dict[str, Any]]:
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return path, json.loads(path.read_text(encoding="utf-8"))


def source(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    return {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> None:
    _, synthetic = load("outputs/nostos0-synthetic-physical-truth-v2-6-confirmation/validation.json")
    _, synthetic_audit = load("outputs/nostos0-synthetic-physical-truth-v2-6-audit/audit.json")
    _, bonej = load("outputs/nostos0-bonej-thickness-v1/bonej_thickness_comparator.json")
    _, stare = load("outputs/nostos0-stare-network-confirmation-v1/stare_network_confirmation.json")
    _, dynamic = load("outputs/nostos0-bbbc035-dynamic-confirmation-v1/bbbc035_dynamic_confirmation.json")
    _, tensor = load("outputs/nostos0-structure-tensor-comparator-v1/structure_tensor_comparator.json")
    _, pshg = load("outputs/nostos0-pshg-acquisition-shift-v1-confirmation/confirmation.json")
    _, pshg_roi = load("outputs/nostos0-pshg-independent-unit-risk-audit-v1/audit.json")
    _, fmd = load("outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation-audit/confirmation_audit.json")
    _, tendon = load("outputs/nostos0-tlt-pshg-xrd-v1-confirmation/confirmation.json")
    _, heaton = load("outputs/nostos0-heaton-in-vivo-shg-v1-confirmation/confirmation.json")
    _, transfer = load("outputs/nostos0-cross-domain-risk-transfer-v1/transfer.json")
    _, kymatio = load("outputs/nostos0-benchmark-v1/kymatio_benchmark.json")
    _, radiomics = load("outputs/nostos0-benchmark-v1/pyradiomics_benchmark.json")

    entries: list[dict[str, Any]] = [
        {
            "id": "analytic_morphology_spatial_v2_6",
            "domain": "analytic 2-D morphology and random fields",
            "endpoint": "Hessian class/scale and gradient anisotropy/axis",
            "reference": "programmed analytic truth",
            "independent_units": "36 morphology, 270 spatial and 24 equivariance cases",
            "frozen_status": synthetic["status"],
            "decision": "supported_analytic_only",
            "metrics": {
                "hessian_balanced_accuracy": synthetic["metrics"]["hessian"]["balanced_accuracy"],
                "spatial_coverage": synthetic["metrics"]["spatial"]["coverage"],
                "spatial_spearman": synthetic["metrics"]["spatial"]["gradient_spearman_rho"],
                "spatial_p95_relative_error": synthetic["metrics"]["spatial"]["gradient_p95_relative_error"],
                "rotation_p95_turn_error_degrees": synthetic["metrics"]["equivariance"]["rotation_p95_turn_error_degrees"],
            },
            "boundary": "No biological meaning, segmentation, instrument transfer, mechanics or clinical claim.",
            "sources": [
                source("outputs/nostos0-synthetic-physical-truth-v2-6-confirmation/validation.json"),
                source("outputs/nostos0-synthetic-physical-truth-v2-6-audit/audit.json"),
            ],
        },
        {
            "id": "bonej_thickness",
            "domain": "public 3-D bone volumes",
            "endpoint": "local thickness",
            "reference": "archived IPL maps and BoneJ 1.4.3",
            "independent_units": f"{bonej['summary']['case_count']} volumes",
            "frozen_status": bonej["status"],
            "decision": "supported_external_comparator",
            "metrics": {
                "ccc": bonej["summary"]["nostos_bonej_ccc"],
                "median_relative_difference": bonej["summary"]["median_absolute_relative_difference"],
                "mean_absolute_difference_mm": bonej["summary"]["mean_absolute_nostos_bonej_difference_mm"],
            },
            "boundary": "Effectively isotropic archived volumes; no anisotropic-acquisition or biological-function claim.",
            "sources": [source("outputs/nostos0-bonej-thickness-v1/bonej_thickness_comparator.json")],
        },
        {
            "id": "stare_network",
            "domain": "public retinal vessel reference masks",
            "endpoint": "network survival and skeleton length under sampling",
            "reference": "STARE AH/VK observer masks",
            "independent_units": f"{stare['summary']['case_count']} images",
            "frozen_status": stare["status"],
            "decision": "supported_external_reference_masks",
            "metrics": {
                "survival_auc_spearman": stare["summary"]["survival_auc_spearman"],
                "skeleton_length_spearman": stare["summary"]["skeleton_length_spearman"],
                "median_length_relative_error": stare["summary"]["median_skeleton_length_relative_error"],
                "observer_survival_spearman": stare["summary"]["ah_vk_survival_auc_spearman"],
            },
            "boundary": "Imported masks only; automatic segmentation and bone-network transfer are not established.",
            "sources": [source("outputs/nostos0-stare-network-confirmation-v1/stare_network_confirmation.json")],
        },
        {
            "id": "bbbc035_bulk_motion",
            "domain": "public fluorescence microscopy with programmed translation",
            "endpoint": "bulk registration",
            "reference": "known applied pixel shifts",
            "independent_units": "public image series with disjoint programmed shifts",
            "frozen_status": dynamic["status"],
            "decision": "supported_programmed_motion",
            "metrics": {
                "median_error_pixels": dynamic["summary"]["median_nostos_error_pixels"],
                "maximum_error_pixels": dynamic["summary"]["maximum_nostos_error_pixels"],
            },
            "boundary": "Registration, not native tissue deformation, strain, mechanics or object correspondence.",
            "sources": [source("outputs/nostos0-bbbc035-dynamic-confirmation-v1/bbbc035_dynamic_confirmation.json")],
        },
        {
            "id": "pshg_orientation",
            "domain": "unstained PSHG-TISS breast microscopy",
            "endpoint": "local axial orientation under computational acquisition shifts",
            "reference": "paired FI orientation field",
            "independent_units": f"{pshg['summary']['rois']} ROIs; {pshg['summary']['cases']} nested conditions",
            "frozen_status": "pass_row_level_with_failed_independent_unit_bound",
            "decision": "supported_bounded_row_comparison_not_formal_roi_control",
            "metrics": {
                "coverage": pshg["summary"]["operating"]["full_contract"]["coverage"],
                "row_risk": pshg["summary"]["operating"]["full_contract"]["risk"],
                "matched_acquisition_qc_risk": pshg["summary"]["matched_coverage"]["acquisition_qc"]["risk"],
                "matched_endpoint_qc_risk": pshg["summary"]["matched_coverage"]["endpoint_qc"]["risk"],
                "failing_rois": pshg_roi["independent_roi_level"]["failing"],
                "roi_risk_upper95": pshg_roi["independent_roi_level"]["one_sided_95_clopper_pearson_upper"],
            },
            "boundary": "One acquisition family; nested-row bootstrap is descriptive and not an independent-ROI guarantee.",
            "sources": [
                source("outputs/nostos0-pshg-acquisition-shift-v1-confirmation/confirmation.json"),
                source("outputs/nostos0-pshg-independent-unit-risk-audit-v1/audit.json"),
            ],
        },
        {
            "id": "fmd_hierarchical_support",
            "domain": "public widefield fluorescence microscopy",
            "endpoint": "acquisition-by-scale conditional validity",
            "reference": "paired higher-support acquisitions",
            "independent_units": f"{fmd['confirmation']['independent_group_count']} FOVs; {fmd['confirmation']['eligible_primary_cases']} nested cases",
            "frozen_status": fmd["status"],
            "decision": "supported_small_external_confirmation",
            "metrics": {
                "coverage": fmd["primary_operating_point"]["coverage"],
                "observed_row_risk": fmd["primary_operating_point"]["risk"],
                "aurc_advantage": fmd["risk_coverage"]["cluster_bootstrap_aurc_difference"]["observed"],
                "aurc_advantage_ci95": fmd["risk_coverage"]["cluster_bootstrap_aurc_difference"]["bootstrap_ci95"],
            },
            "boundary": "Only four confirmation FOVs from one widefield family; no population-wide zero-risk claim.",
            "sources": [source("outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation-audit/confirmation_audit.json")],
        },
        {
            "id": "tendon_pshg_xrd",
            "domain": "unstained tendon pSHG with XRD-associated organization",
            "endpoint": "orientation validity and organization recovery",
            "reference": "pSHG orientation and zone-level organization",
            "independent_units": f"{tendon['summary']['specimens']} specimens; {tendon['summary']['fields']} fields",
            "frozen_status": tendon["status"],
            "decision": "mixed_overall_gate_failed",
            "metrics": {
                "coverage": tendon["summary"]["operating"]["full_contract"]["coverage"],
                "row_risk": tendon["summary"]["operating"]["full_contract"]["risk"],
                "organization_spearman": tendon["summary"]["organization"]["pooled_spearman"],
            },
            "boundary": "Organization recovery passed, but overall confirmation failed coverage and clean-preservation gates; only two specimens.",
            "sources": [source("outputs/nostos0-tlt-pshg-xrd-v1-confirmation/confirmation.json")],
        },
        {
            "id": "heaton_shg",
            "domain": "in-vivo collagen SHG",
            "endpoint": "multi-endpoint structure and selective validity",
            "reference": "recognized collagen descriptors across experiments",
            "independent_units": f"{heaton['summary']['mice']} mice; {heaton['summary']['clean_fields']} clean fields",
            "frozen_status": heaton["status"],
            "decision": "rejected_overall",
            "metrics": {
                "coverage": heaton["summary"]["operating"]["full_contract"]["coverage"],
                "matched_risk_reduction": heaton["summary"]["matched_acquisition_qc"]["risk_reduction"],
                "successful_endpoints": heaton["summary"]["successful_endpoints"],
            },
            "boundary": "Directionally useful descriptors do not rescue the failed frozen deployment gates.",
            "sources": [source("outputs/nostos0-heaton-in-vivo-shg-v1-confirmation/confirmation.json")],
        },
        {
            "id": "structure_tensor_comparator",
            "domain": "PSHG orientation",
            "endpoint": "cross-software orientation consistency",
            "reference": "scikit-image 0.25.2 structure tensor",
            "independent_units": f"{tensor['summary']['roi_count']} ROIs; {tensor['summary']['eligible_pixels']} nested pixels",
            "frozen_status": tensor["status"],
            "decision": "supported_noninferiority_not_superiority",
            "metrics": {
                "nostos_median_error_degrees": tensor["summary"]["nostos_median_error"],
                "skimage_median_error_degrees": tensor["summary"]["skimage_median_error"],
                "cross_software_disagreement_degrees": tensor["summary"]["median_cross_software_disagreement"],
            },
            "boundary": "Agreement with one upstream implementation; not superiority or tissue truth.",
            "sources": [source("outputs/nostos0-structure-tensor-comparator-v1/structure_tensor_comparator.json")],
        },
        {
            "id": "feature_family_comparators",
            "domain": "small synthetic construct benchmark",
            "endpoint": "four-class structural discrimination",
            "reference": "frozen programmed classes",
            "independent_units": "16 held-out synthetic cases",
            "frozen_status": "mixed",
            "decision": "universal_superiority_rejected",
            "metrics": {
                "kymatio_balanced_accuracy": kymatio["balanced_accuracy"],
                "pyradiomics_balanced_accuracy": radiomics["synthetic_benchmark"]["balanced_accuracy"],
                "pyradiomics_ibsi_first_order_passed": radiomics["ibsi_conformance"]["passed"],
                "pyradiomics_ibsi_first_order_total": radiomics["ibsi_conformance"]["total"],
            },
            "boundary": "PyRadiomics tied NOSTOS on the small construct benchmark; universal feature superiority is not supported.",
            "sources": [
                source("outputs/nostos0-benchmark-v1/kymatio_benchmark.json"),
                source("outputs/nostos0-benchmark-v1/pyradiomics_benchmark.json"),
            ],
        },
        {
            "id": "cross_domain_learned_transfer",
            "domain": "five held-out validity domains",
            "endpoint": "zero-shot invalidity-risk transfer",
            "reference": "domain-specific invalidity labels",
            "independent_units": "leave-one-domain-out transfer",
            "frozen_status": transfer["status"],
            "decision": "universal_learned_risk_rejected",
            "metrics": {
                "transfer_beats_nostos_in_three_domains": transfer["success_gates"]["better_transfer_beats_nostos_aurc_in_at_least_three_domains"],
                "transfer_beats_acquisition_qc_in_four_domains": transfer["success_gates"]["one_transfer_model_beats_acquisition_qc_in_at_least_four_domains"],
            },
            "boundary": "Supports an interpretable zero-shot fallback hierarchy, not universal learned calibration.",
            "sources": [source("outputs/nostos0-cross-domain-risk-transfer-v1/transfer.json")],
        },
    ]

    checks = {
        "synthetic_confirmation_and_audit_pass": synthetic["status"] == "pass" and synthetic_audit["status"] == "pass",
        "external_reference_passes_present": bonej["status"] == stare["status"] == dynamic["status"] == "pass",
        "pshg_row_pass_and_roi_bound_failure_preserved": pshg["status"] == "pass" and pshg_roi["status"] == "fail",
        "fmd_small_confirmation_preserved": fmd["status"] == "pass" and fmd["confirmation"]["independent_group_count"] == 4,
        "tendon_and_heaton_failures_preserved": tendon["status"] == "fail" and heaton["status"] == "fail",
        "universal_learned_transfer_failure_preserved": transfer["status"] == "fail",
        "radiomics_tie_prevents_superiority_claim": radiomics["synthetic_benchmark"]["balanced_accuracy"] == 1.0,
    }

    payload = {
        "schema_version": "nostos-cross-domain-evidence-registry/1.0",
        "status": "pass" if all(checks.values()) else "fail",
        "meaning_of_registry_pass": "All source receipts were found and their positive, mixed and negative decisions were reconciled without promotion.",
        "checks": checks,
        "entries": entries,
        "global_claim_boundary": (
            "NOSTOS has validated analytic estimators and several bounded public-data measurement demonstrations. "
            "It does not yet have a distribution-free independent-unit guarantee, independent laboratory execution, "
            "mechanical ground truth, clinical utility or intraoperative validation."
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    lines = [
        "# NOSTOS-0 cross-domain evidence registry v1",
        "",
        f"**Registry status:** {payload['status']}  ",
        "A registry pass means that every listed source was found and its actual positive, mixed or negative decision was preserved. It is not a claim that every scientific experiment passed.",
        "",
        "| Domain / endpoint | Independent evidence | Frozen result | Defensible decision |",
        "|---|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            f"| {entry['domain']} — {entry['endpoint']} | {entry['independent_units']} | "
            f"{entry['frozen_status']} | {entry['decision']} |"
        )
    lines.extend([
        "",
        "## What the evidence supports",
        "",
        "- Calibrated analytic recovery with explicit abstention for the released Hessian and spatial-gradient responses.",
        "- External reference agreement for local thickness, imported-mask network sampling and cross-software orientation.",
        "- Bounded row-level validity improvements in PSHG and a small FMD confirmation.",
        "- Deterministic, data-free software packaging and clean-room execution.",
        "",
        "## What it rejects or leaves open",
        "",
        "- Universal feature-family superiority: PyRadiomics tied the small synthetic benchmark.",
        "- Universal learned risk transfer: the frozen leave-one-domain-out study failed.",
        "- A 20% independent-ROI PSHG risk guarantee: the exact upper bound was 47.9%.",
        "- Broad collagen deployment: the tendon and in-vivo SHG confirmations failed at least one frozen master gate.",
        "- Mechanics, diagnosis, patient benefit and intraoperative use: no relevant ground truth exists in NOSTOS-0.",
        "",
        "## Submission use",
        "",
        "The methods manuscript may claim a calibrated measurement framework with explicit validity contracts and bounded public-data demonstrations. It must not describe the response geometry as universally superior, the risk score as distribution-free control, or the system as clinically or intraoperatively validated.",
        "",
        f"Machine-readable registry: `{OUTPUT_JSON.relative_to(ROOT).as_posix()}`.",
    ])
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "entries": len(entries), "content_sha256": payload["content_sha256"], "output": str(OUTPUT_JSON)}, indent=2))


if __name__ == "__main__":
    main()
