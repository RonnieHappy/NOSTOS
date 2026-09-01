# NOSTOS-0 final technical, scientific and clinical audit

**Audit date:** 2026-08-29  
**Protocol:** `nostos-final-max-audit/2.0`  
**Audit status:** `complete_with_external_blockers`

## Bottom line

NOSTOS 0.3.0 is now a verified technical release candidate. The exact public
unstained-PSHG profile has a bounded measurement claim, a complete operator
export, and a fail-closed local workstation. The release survived a fresh
frozen install, 292 applicable clean-room tests, dependency and readiness
checks, and a byte-identical rebuild. Two earlier clean-room failures are
retained rather than overwritten.

It is not clinically usable today. It has not been validated on a second
microscope or independent operator, its ten-frame acquisition time has not been
measured, and no fresh target-tissue endpoint, surgical decision or patient
outcome has been studied. A high-impact methods or clinical submission is not
yet defensible on public data alone.

## Terminal disposition

| Object | Disposition |
| --- | --- |
| Data-free release archive | Verified technical pass; 738 files including manifest; SHA-256 `03c2ea315c550ab8b503b5856a53e481ad67e5395f72e24d30decfdc1437dfa3` |
| Local runtime | 297 tests passed, 4 skipped; finite CPU FFT |
| T7 CUDA runtime | 308 tests passed, no skips; finite CPU and RTX 5070 Ti CUDA FFT |
| Clean-room release | 292 tests passed, 8 appropriate dependency/data-dependent skips; all 9 verification checks passed |
| BioSR selective validity | Bounded pass: 95.0% coverage and silent-invalid risk 0.0387 versus 0.0735 |
| Public unstained PSHG | Bounded technical pass on the deposited acquisition family |
| New microscope/operator | Not validated |
| Intraoperative workflow | Not validated; acquisition and human workflow time absent |
| Clinical decision support | Not ready; outputs remain withheld |
| Nature Methods / Nature Biomedical Engineering | Not ready |

## Evidence-backed claims

- **Supported:** NOSTOS 0.3.0 is a deterministic, data-free, locally executable structural-measurement software release candidate. Scope: 738 files plus release manifest; fresh frozen install; 292 clean-room tests passed and 8 dependency/data-dependent tests skipped; byte-identical second build
- **Supported:** The supported local and T7 runtimes execute the full applicable repository test matrices and finite 2048 by 2048 FFT smoke tests. Scope: Python 3.13; 297 local tests with 4 skips and 308 T7 tests with no skips; RTX 5070 Ti CUDA execution verified
- **Supported:** A frozen scale-conditioned validity contract reduced silent-invalid tensor-coherence risk relative to conventional acquisition QC on untouched BioSR F-actin fields. Scope: 8 reference fields, 980 primary eligible rows, 95.0% coverage, risk 0.0387 versus 0.0735, 47.4% relative reduction; controlled degradations on one public SIM resource
- **Supported:** A declared local structure-tensor endpoint reproduces the deposited PSHG orientation reference within the frozen public acquisition profile. Scope: 48 breast ROIs and 1,367,747 eligible pixels in the scientific confirmation; median axial error 7.59 degrees after a transform frozen on a separate skin subset
- **Supported:** The unstained PSHG production path exports complete, hash-registered measurement artifacts and withholds unsupported clinical conclusions. Scope: 4 additional hash-selected fields in v1.4; pooled median reference error 7.53 degrees; p95 end-to-end compute/export 0.452 seconds; acquisition time excluded
- **Supported:** A format-compatible but provenance-unverified acquisition remains measurable for research while being explicitly demoted and clinically withheld. Scope: author-operated deterministic local HTTP audit; four decoded visual products; not a human-factors or browser-matrix study
- **Supported:** Reference-mask vascular-network and trabecular-thickness endpoints retain bounded cross-data or cross-software evidence. Scope: STARE reference masks and eight public trabecular-bone volumes; these are endpoint-specific measurements, not universal biological or diagnostic validation

## Claims rejected or not supported

- one universal score or representation that identifies every specimen across tissues
- universal superiority over focused estimators, radiomics, scattering or established domain tools
- validated automatic cartilage segmentation or a continuous osteochondral-interface claim
- transfer of the PSHG profile to a new microscope, operator, tissue or surgical environment
- intraoperative acquisition speed; current timing starts after image files exist
- diagnosis, disease severity, tissue viability, margin status, mechanics or treatment guidance
- clinical utility, safety, decision impact, patient outcome or regulatory clearance
- Nature Methods or Nature Biomedical Engineering readiness on current public-data evidence
- a double-digit-impact-factor submission that is presently defensible without new external acquisition evidence

## Readiness gates

| Gate | Status | Evidence boundary |
| --- | --- | --- |
| G0 software integrity | `pass` | Definitive v29 archive, two retained failure receipts, verified clean-room execution and byte-identical rebuild. |
| G1 locked public unstained measurement | `pass_bounded` | PSHG orientation and production artifacts pass on the deposited acquisition family only. |
| G2 independent instrument and operator bridge | `open` | No independently operated second instrument or acquisition family has passed a frozen bridge protocol. |
| G3 fresh target-tissue reference validity | `open` | No co-registered fresh surgical tissue study links NOSTOS output to an adjudicated structural, histologic or mechanical reference. |
| G4 intraoperative workflow and human factors | `open` | Ten-frame acquisition, motion, focusing, field selection, sterility, operator time, failure recovery and usability are unmeasured. |
| G5 prospective clinical endpoint and decision impact | `open` | No locked clinical endpoint, prospective cohort, comparison to standard care or patient-level decision study exists. |
| G6 high-impact methodological generalization | `partial` | BioSR v9 supports one selective-validity result, but several cross-domain support and universal-representation gates failed and remain retained. |

## Novelty audit

The strongest potentially novel object is not a new FFT, tensor, Hessian or
topology algorithm. Those are established methods. It is the combined
response-and-validity contract: physical scale, perturbation behavior, evidence
maturity, complete provenance and explicit abstention travel with each
measurement. The strongest positive test of that idea is BioSR v9, where the
frozen contract reduced silent-invalid tensor-coherence risk at useful coverage.

That is not yet a platform-level victory. Several cross-domain validity and
universal-representation experiments failed and remain in the ledger. A strong
methods paper needs the same prospective advantage on a second modality and an
important endpoint, not a larger montage of analyses.

## Intraoperative practicality audit

The compute path is fast enough to justify further work: the v1.4 public fields
had p95 compute-plus-export time below half a second. That number begins after
the ten image frames and support maps already exist. It excludes polarization
switching, focusing, specimen placement, motion, transfer, operator interaction,
sterile-field constraints and failure recovery. Therefore it cannot be reported
as specimen-to-result or intraoperative latency.

The workstation behaves correctly at the evidence boundary. A hash-identical
public field can be confirmed; a new but format-compatible input is demoted to
`review` and `unvalidated_new_acquisition`; clinical output remains withheld.
This is safe research behavior, not clinical validation.

## Use a few informative samples, not millions of tiles

Do not add millions of tiles. Add a small number of independent, information-rich specimens in staged gates.

| Stage | Minimum design | Purpose |
| --- | --- | --- |
| engineering bridge | 3 to 5 independent specimens spanning low, medium and high signal; 2 operators; 3 repositioning repeats; no clinical-performance claim | Find coordinate, focus, motion, support-map and timing failures cheaply before freezing thresholds. |
| locked external pilot | approximately 12 to 20 independent specimens or donors, with specimen-level inference and an adjudicated co-registered reference | Estimate coverage, silent-invalid risk, agreement and failure modes with uncertainty; exact size must be justified by the endpoint precision target. |
| prospective confirmation | sample size derived from the locked clinical endpoint, expected prevalence/effect and confidence-width target; independent operators and temporal separation required | Support a clinical or high-impact translational claim without patch-level pseudoreplication. |

Pixels, tiles, perturbations and repeat frames are technical observations. The specimen, donor or patient remains the inferential unit unless the study design proves otherwise.

## Blocking requirements

| Category | Open blocker | Required closure evidence |
| --- | --- | --- |
| independent acquisition | The PSHG claim is tied to one public instrument family and author-operated analysis. | Freeze a bridge protocol, then pass it on a second instrument with independent operators, specimen-level clustering and an acquisition-appropriate reference. |
| target tissue | The verified unstained profile is breast PSHG, not the intended intraoperative osteochondral or bone use case. | Acquire fresh target tissue with co-registered histology, polarimetry/SHG reference and, if claimed, mechanical testing. Lock one clinically meaningful endpoint before analysis. |
| workflow | Only compute and export latency are measured; the ten-frame acquisition and operator pathway are not timed or stress tested. | Measure specimen-to-result latency, motion failures, refocus/reposition repeats, abstention rate and operator errors in a simulated-use study before any operating-room claim. |
| clinical performance | There is no prospective clinical reference, safety, decision-impact or outcome evidence. | After technical bridging, register and run a prospective patient-level study with locked intended use, adjudicated reference, uncertainty, subgroup analysis and failure accounting. |
| methodological novelty | Most component estimators are established; one BioSR validity-contract success is not yet a general platform-level advantage. | Prospectively demonstrate lower silent-invalid risk at matched useful coverage on at least one second modality and show that response-geometry or abstention information changes a scientifically important conclusion beyond individual methods and ordinary QC. |
| external reproducibility | No unaided external user has executed the frozen release and returned an unedited receipt. | Obtain an identified external execution from the release archive and archive the public tag with a DOI. |
| governance | Institutional determination, privacy/security review, authorship declarations and regulatory intended-use analysis are incomplete. | Complete institutional, clinical engineering, cybersecurity and regulatory review before patient-data or operating-room deployment. |

## Technical checks

| Check | Result |
| --- | --- |
| `evidence_index_complete` | PASS |
| `evidence_index_retains_not_ready_boundary` | PASS |
| `biosr_v9_confirmation_passed` | PASS |
| `biosr_v9_independent_code_path_audit_passed` | PASS |
| `pshg_v1_4_deployment_passed` | PASS |
| `pshg_v1_4_audit_passed` | PASS |
| `operator_export_audit_passed` | PASS |
| `operator_reference_excluded` | PASS |
| `operator_clinical_output_withheld` | PASS |
| `new_acquisition_workstation_fails_closed` | PASS |
| `local_runtime_verified` | PASS |
| `t7_cuda_runtime_verified` | PASS |
| `legacy_runtime_rejected` | PASS |
| `bone_source_integrity_retained` | PASS |
| `failed_bone_primary_gates_not_promoted` | PASS |
| `release_is_data_free_and_scanner_clean` | PASS |
| `cleanroom_failures_retained` | PASS |
| `definitive_cleanroom_passed` | PASS |
| `release_rebuild_is_byte_identical` | PASS |
| `release_terminal_manifest_passed` | PASS |
| `manuscript_production_qa_retained` | PASS |

## Immutable receipt index

| Receipt | Path | SHA-256 |
| --- | --- | --- |
| `evidence_index` | `outputs/nostos0-evidence-bundle-v29/evidence_index.json` | `58a126ea283e0a41108f837efa894223d5f1305b2a72f5a25aee8e52855b1a7d` |
| `biosr_v9_confirmation` | `outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation/confirmation_receipt.json` | `17c2e876e50ce86dd9d6a5856f7e9ea98937ee8563377c748fd108cdc6cb6f17` |
| `biosr_v9_audit` | `outputs/nostos0-biosr-tensor-v9-final-audit/final_audit.json` | `231fed52ee363c38009067fe7bb2e6f5c2cd2e0c94eaa650ac6fd5d524ec192a` |
| `pshg_v1_4_deployment` | `outputs/nostos0-intraop-pshg-deployment-v1_4/deployment_benchmark.json` | `7ec709c78f3e3e36ffbce2d47f7bc8288b0eb2b60ec3f9ae69cd09711812e536` |
| `pshg_v1_4_audit` | `outputs/nostos0-intraop-pshg-deployment-v1_4-final-audit/final_audit.json` | `15b137671f8b1fca7e2f063b656065344c76e58e301b20c7a4cf38207f934acb` |
| `pshg_v1_4_audit_manifest` | `manifests/intraop_pshg_deployment_v1_4_audit_manifest.json` | `fb77ff338ead4adaa62759e03a5cc239932d393f41af11e6af9692fbd029c08f` |
| `operator_result` | `outputs/nostos0-intraop-operator-workflow-v1/intraop_result.json` | `4bb59494121fb3cb7184c3578e9c27d4acf0a22ac9a597bfb92106336be1f9e8` |
| `operator_audit` | `outputs/nostos0-intraop-operator-workflow-v1/workflow_audit.json` | `6f82ecb55966d5ae58e419504ed7ab93a4667134f152d82f17fe1997754d226a` |
| `operator_manifest` | `manifests/intraop_operator_workflow_v1_audit_manifest.json` | `f2be2a941773a62796b2bdd9cf85b04900c3de56fc455937f20dce93a35720fd` |
| `workstation_audit` | `outputs/nostos0-intraop-workstation-audit-v1/workstation_audit.json` | `dcad1b2e5b6b77c05afcf2f9f1753da29fd69b01f01d29f852b820d3076bb8c0` |
| `workstation_manifest` | `manifests/intraop_workstation_v1_audit_manifest.json` | `d0127cedbbe7f96b9a0f564a4fbbf25ea3fda454c1033b9090f557eab780ec38` |
| `runtime_local` | `outputs/nostos0-runtime-audit-v1/local_cpu.json` | `3f0e9c7de9c9c20dd25c26b1f06bbcc8ad52d828df685acc9fc586ad367be6a1` |
| `runtime_t7` | `outputs/nostos0-runtime-audit-v1/t7_cuda.json` | `ada64a5c5583a97e87a6d4a0bcfb8dd84d43ed503da52a62da4b4e5f19122c5b` |
| `runtime_legacy` | `outputs/nostos0-runtime-audit-v1/t7_legacy_py314.json` | `4ca378ac756c5b95474173a4eea4f9faa774882b805ef6af42a075354d2c45c3` |
| `runtime_manifest` | `manifests/runtime_audit_v1_manifest.json` | `fd1a5489ce0199dab9fcdeb7780f4ddfc256fcb8d45c1aff6470206dce0e57e7` |
| `bone_program` | `outputs/nostos0-bone-contract-summary/bone_contract_program_summary.json` | `b0a8f66e634df5b2ea78eebccd68c526038c1e689dd72cd2e76c947c1f4fbb94` |
| `bone_integrity` | `outputs/nostos0-bone-download-integrity/integrity_verification.json` | `64849ec4598fd13bcf7a4f6aa82fa8a73ef690b8d7a29b7374eabb35054c4dd9` |
| `manuscript_qa` | `outputs/nostos0-manuscript-qa-v1/manuscript_qa.json` | `8742fe695b4a0c2c4aa7af3e6b09631b8d7d9e4eef6f1f4b4eb1db0ea0f8cac1` |
| `release_receipt` | `outputs/nostos0-release-candidate-v29/release_receipt.json` | `3dbacc69c4b76415869228e6501f900b4a24ca0c99d33b74c5b1995e989c1e76` |
| `release_manifest` | `outputs/nostos0-release-candidate-v29/release_manifest.json` | `9145548a5c5ddcf07e7256ddb7ff71d9529748d9894ff6bba096e6c26d6187be` |
| `cleanroom_initial_failure` | `outputs/nostos0-release-candidate-v29/cleanroom_initial_failure.json` | `ce81fb1fa379d77c50acb47202e85636269b2965e3b9b984a9b1dd7d26a1c3e9` |
| `cleanroom_second_failure` | `outputs/nostos0-release-candidate-v29/cleanroom_second_failure.json` | `6a8820f55c1824f4ef12e4b0b13393db28aba4c5901ebf7351592e8e2bb7a82b` |
| `cleanroom_verification` | `outputs/nostos0-release-candidate-v29/cleanroom_verification.json` | `b01297377e321f94a451f1c337685a5d34ed40d045270d3f6ff778c3a13b0856` |
| `release_terminal_manifest` | `manifests/release_candidate_v29_audit_manifest.json` | `e412190724d72c5bac94f4e0bc0537e6ef72ae5a837ba62d3c9add05231e7d0c` |

## Final decision

The release is suitable for research use, external replication and a small
independent instrument-bridge study. It is not suitable for patient care,
intraoperative decision support or a Nature-level submission claim. Public data
have taken the software layer close to its responsible ceiling. The remaining
high-impact gates require new specimens, independent operators, a second
instrument, a locked target-tissue reference and prospective clinical workflow
evidence.
