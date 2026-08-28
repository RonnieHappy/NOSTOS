# NOSTOS-0 final maximum-rigor audit

**Audit date:** 2026-08-28  
**Protocol:** `nostos-final-max-audit/1.0`  
**Status:** `complete_with_external_blockers`

## Executive verdict

The NOSTOS 0.3.0 release candidate is technically reproducible in an author-operated fresh environment, and the eight-page Word manuscript passes production QA. The scientific resource is bounded and auditable. It is **not submission-ready**, **not Nature Methods/Nature Biomedical Engineering-ready**, and **not clinically or intraoperatively validated**.

This distinction is deliberate. A technically clean release does not convert failed biological gates into positive evidence. The current contribution is a calibrated, provenance-preserving and failure-aware measurement contract around established estimators. The strongest positive external endpoints are local PSHG orientation, reference-mask vascular-network responses and same-mask local-thickness concordance. The larger public bone contract program is complete but failed its primary useful-coverage and matched-risk requirements.

## Terminal disposition

| Object | Disposition |
| --- | --- |
| Data-free software release | Technical pass; deterministic archive; no bundled source data or release-audit findings |
| Fresh-extraction verification | Pass after one retained dependency-declaration failure; 180 tests passed, 4 skipped; runtime and installed package both report 0.3.0 |
| Manuscript production | Pass; 8 pages, 5 embedded figures, Times New Roman, visual and machine QA complete |
| Evidence index | Complete; 79 entries, zero missing; explicitly reports `not_ready` for Nature |
| Five-record public bone program | Complete with failed primary gates |
| Current journal submission | Blocked by DOI, unaided external execution and author/institutional declarations |
| Flagship high-impact claim | Blocked by failed useful-coverage/matched-risk evidence and absent multi-acquisition confirmation |
| Clinical or intraoperative use | Unsupported |

## What the evidence supports

- **Supported:** NOSTOS exposes calibrated structural estimators through a typed, provenance-preserving and failure-aware measurement contract. Scope: software architecture and output schema
- **Supported:** Registered analytic operating envelopes passed all 24 required module-by-perturbation tests. Scope: synthetic truth only
- **Supported:** A declared local structure-tensor orientation endpoint reproduced an instrument-derived raster axis in the frozen PSHG breast confirmation. Scope: 48 ROIs, 1,367,747 eligible pixels; median axial error 7.59 degrees and axial alignment 0.877 after a frozen 90-degree transform
- **Supported:** Reference-mask vascular network responses were sampling-stable on STARE. Scope: 20 supplied manual masks; survival-area and skeleton-length Spearman correlations 0.988 and 0.995
- **Supported:** Local thickness numerically agrees with archived maps and BoneJ on one public trabecular-bone archive. Scope: eight matched volumes; median voxelwise Spearman correlation 0.927, BoneJ concordance correlation coefficient 0.926 and median relative difference 7.14%
- **Supported:** The complete public bone stress program and all source archives are reproducibly indexed. Scope: 73 verified files, 54,948,569,793 bytes; eight staged analyses; primary cross-program gates failed
- **Supported:** The data-free software release installs and executes in a fresh environment. Scope: 180 passed tests, 4 skipped tests, matching runtime/package version, compatible dependency set and ready doctor report; author-operated clean room, not external replication

## Claims the current evidence rejects or does not support

- universal phenotype representation or universal specimen-identity fingerprint
- universal validity or abstention advantage at useful coverage
- automatic segmentation validity from perturbation stability
- validated cartilage segmentation or definitive cartilage biological inference
- population-level bone biology, disease discrimination or diagnostic performance
- tissue stiffness, strain, mechanics, treatment response or patient outcome
- clinical, intraoperative or surgical decision support
- Nature Methods or Nature Biomedical Engineering readiness

## Sample and analysis sufficiency

The limiting issue is independent-unit and acquisition-family breadth, not raw image count. Thousands of tiles, sections and perturbations are technical observations. They do not replace independent mice, specimens, donors, laboratories or acquisitions. NOSTOS now preserves the highest available unit and does not treat patches as biological replicates. That analysis choice is appropriate; it also exposes why the current sample base cannot support a universal or clinical claim.

The five-record bone program verified 73 files totaling 54,948,569,793 bytes and executed eight staged analyses. Its full-contract coverage was 0.358 in paired SHG, 0.538 in the escalated rat-network stress test, 0.365 at 0.4 µm and 0.399 at 0.8 µm in human nanoCT. The narrow UV-PAM abstention control passed by withholding all 144 unsupported physical-collagen requests, but this is governance evidence rather than accuracy validation.

## Blocking requirements

| Category | Open blocker | Required closure evidence |
| --- | --- | --- |
| submission administration | The frozen release lacks an archival DOI. | Archive the tagged release in Zenodo or an equivalent repository and replace the manuscript placeholder with the DOI. |
| external reproducibility | No unaided external-operator replication receipt has been received. | An identified external operator must run the frozen replication challenge from a fresh clone or release archive and return the unedited receipt. |
| institutional and author declarations | Secondary-analysis determination, affiliation, funding, acknowledgements and competing-interest declarations are not finalized. | The corresponding author and institution must provide the final determinations and text. |
| flagship scientific evidence | The frozen bone support contract did not lower silent-invalid risk at matched useful coverage across acquisition strata. | Prospectively freeze and pass a support contract on an untouched acquisition family at the prespecified coverage and risk gates. |
| flagship external validity | Independent multi-laboratory or acquisition-family confirmation is absent. | Obtain prospectively acquired or truly unseen data with independent experimental units and endpoint-appropriate references. |
| clinical translation | No prospective intraoperative acquisition, clinical reference, decision-impact or outcome study exists. | Run a separately governed prospective clinical study; public archives cannot close this gate. |

## Technical audit checks

| Check | Result |
| --- | --- |
| `evidence_index_complete` | PASS |
| `evidence_index_retains_not_ready_boundary` | PASS |
| `bone_source_integrity_passed` | PASS |
| `bone_program_complete_with_failed_primary_gates` | PASS |
| `manuscript_production_qa_passed` | PASS |
| `manuscript_submission_blockers_retained` | PASS |
| `release_audit_passed` | PASS |
| `release_build_is_deterministic` | PASS |
| `initial_cleanroom_failure_retained` | PASS |
| `rebuilt_cleanroom_passed` | PASS |
| `runtime_version_matches_installed_metadata` | PASS |
| `bone_figure_is_traceable_and_non_generative` | PASS |

## Immutable receipt index

| Receipt | Path | SHA-256 |
| --- | --- | --- |
| `evidence_index` | `outputs/nostos0-evidence-bundle-v27/evidence_index.json` | `be57bd32012ad4729e5c7d41a30d50ba3b8274bc67e46df5ed4d1fda381622fe` |
| `bone_program` | `outputs/nostos0-bone-contract-summary/bone_contract_program_summary.json` | `b0a8f66e634df5b2ea78eebccd68c526038c1e689dd72cd2e76c947c1f4fbb94` |
| `bone_integrity` | `outputs/nostos0-bone-download-integrity/integrity_verification.json` | `64849ec4598fd13bcf7a4f6aa82fa8a73ef690b8d7a29b7374eabb35054c4dd9` |
| `manuscript_qa` | `outputs/nostos0-manuscript-qa-v1/manuscript_qa.json` | `8742fe695b4a0c2c4aa7af3e6b09631b8d7d9e4eef6f1f4b4eb1db0ea0f8cac1` |
| `release_receipt` | `outputs/nostos0-release-candidate-v27/release_receipt.json` | `edf8248553d09e96298245ce34a2227724e3548e3add573b55dcc0391ebcd85f` |
| `release_manifest` | `outputs/nostos0-release-candidate-v27/release_manifest.json` | `928d1c2566fdd321e73d26372479fcb99b5b1dbb2380c01dd24cd59333490af7` |
| `cleanroom_initial_failure` | `outputs/nostos0-release-candidate-v27/cleanroom_initial_failure.json` | `768f4bcd4b18e69995be4b6d9347c2a533aaf767d8d52a81ace2e71ae8a7b983` |
| `cleanroom_verification` | `outputs/nostos0-release-candidate-v27/cleanroom_verification.json` | `1cefde8d7af4fb28b3d6733045d73d82b4f89c772c52f29f0ffa23eade68192a` |
| `bone_figure_manifest` | `figures/nostos0/supplementary_figure_1_bone_contract_stress.manifest.json` | `33bba5fb8f3b60a2db55db103c8da081af25eda843c384cddbbc5e4eb7470ead` |

## Release identity

- Planned public tag: `v0.3.0-rc16`
- Archive: `nostos-0.3.0-release-candidate.zip`
- Archive size: 28,060,913 bytes
- Archive SHA-256: `8314887fe135c4032f8b58780f24a8a7a7d01598a675652065176e5d6d05e707`
- Packaged file count: 444
- Public-release state at audit: prepared for push; the release URL and tag must be verified after publication.

## Final decision rule

Do not submit this manuscript, claim Nature readiness or describe NOSTOS as clinically usable until every applicable blocker above is closed with a new immutable receipt. The current artifact may be shared as an explicitly labeled research-software release candidate. Public data can finish the software and methods-resource layer; prospective independent and clinical evidence requires external specimens, operators and institutional authority.
