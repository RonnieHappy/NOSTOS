# NOSTOS-0 bone contract program: final evidence summary

**Program status:** `complete_with_failed_primary_gates`  
**Nature Methods readiness:** `not_ready`  
**Clinical readiness:** `not_ready`

Complete negative/development evidence for the broad bone validity-contract hypothesis; bounded endpoint and governance results remain reportable.

## Frozen gate table

| Gate | Status | Value |
| --- | --- | --- |
| all_source_files_integrity_verified | `pass` | 73 files; 54948569793 bytes |
| macro_risk_coverage_auc_reduction_at_least_20_percent | `fail_not_estimable_across_all_frozen_strata` | Not estimable |
| paired_specimen_bootstrap_interval_excludes_zero | `fail_not_estimable_across_all_frozen_strata` | Not estimable |
| overall_full_contract_coverage_at_least_0_80 | `fail` | paired_shg=0.358; rat_network_v2=0.538; human_nanoct_scale_0.4=0.365; human_nanoct_scale_0.8=0.399 |
| every_endpoint_acquisition_stratum_coverage_at_least_0_70 | `fail` | Multiple SHG, network and nanoCT strata were below 0.70. |
| lower_silent_invalid_risk_for_every_endpoint_at_matched_coverage | `fail_not_demonstrated` | Not estimable |
| uncertainty_coverage_between_0.90_and_0.975 | `fail_not_estimated_for_complete_program` | Not estimable |
| missing_calibration_and_semantic_support_trigger_abstention | `pass_narrow_control` | 0/144 requested physical-collagen UV-PAM outputs emitted. |

## Stage disposition

| Stage | Role | Status | Highest unit | Technical cases |
| --- | --- | --- | --- | ---: |
| download_integrity | source_integrity | `pass` | not applicable | 73 |
| paired_shg_tpf_v1 | compact_confirmation_with_partly_circular_invalidity | `failed_coverage_gate` | 12 | 576 |
| mouse_shg_support_v2 | support_rule_development | `fail_no_promotable_threshold` | 8 | not reported |
| rat_network_v1 | stress_design_calibration | `non_informative_no_invalid_cases` | 13 | 104 |
| rat_network_v2 | post_failure_stress_calibration | `risk_reduction_but_failed_coverage_gate` | 13 | 104 |
| human_nanoct_scalar_v1 | opened_acquisition_transfer | `failed_withheld_stress` | six_deposited_volumes_independence_not_asserted | 288 |
| human_nanoct_scale_v2 | post_failure_scale_response_development | `risk_reduction_but_failed_coverage_gate` | same_six_opened_deposited_volumes | 864 |
| uvpam_semantic_abstention | negative_control | `pass_narrow_governance_control` | six_filename_groups_not_asserted_specimens | 144 |

## Blocking requirements

- A frozen support contract that reaches useful coverage on an untouched acquisition family.
- A paired specimen-level primary risk-coverage analysis across eligible strata.
- Independent execution of the clean release by an external operator.
- Independent multi-laboratory or acquisition-family validation for a flagship methods claim.

## Prohibited claims

- universal validity advantage
- automatic segmentation validity
- population-level bone biology
- diagnosis or treatment guidance
- tissue mechanics or intraoperative utility
- Nature Methods readiness

Every input receipt is SHA-256 indexed in `bone_contract_program_summary.json`.
