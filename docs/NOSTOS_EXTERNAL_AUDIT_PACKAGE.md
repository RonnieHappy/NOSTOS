# NOSTOS external reproducibility and tool audit package

Generated: 2026-08-28T20:28:02+00:00

## Instructions for the independent auditor

Audit the code, methods, claims and user-facing tool independently. Do not assume that a passing test proves scientific validity. Re-run the frozen protocols, verify group separation and physical calibration, inspect every failed gate, and test whether each biological interpretation is narrower than its measurement endpoint. Treat generated figures as representations that must be traced to a receipt, source table or public image.

## Release identity

- Package: NOSTOS 0.3.0-rc15
- Public repository: https://github.com/RonnieHappy/NOSTOS
- Immutable tag: v0.3.0-rc15
- Commit: resolve with `git rev-list -n 1 v0.3.0-rc15` and compare it with the signed release page
- Release: https://github.com/RonnieHappy/NOSTOS/releases/tag/v0.3.0-rc15
- Intended use: CPU-first, calibrated structural measurement in biological images
- Implemented domains: analytic phantoms, cartilage histology, trabecular-bone micro-CT, filament microscopy, nuclei fluorescence and polarization-SHG
- Platform used for this audit: Windows, Python 3.13.13

## Explicit non-claims

NOSTOS is not a diagnostic device, intraoperative decision aid, universal image fingerprint, universal classifier or validated estimator of stiffness, modulus, permeability, load support, treatment response or patient outcome. The public cartilage cohort provides adjacent-section repeatability, not independent external validation. Classical cartilage masks are tissue proposals, not expert reference segmentations. The training-free PTA micro-CT interface adapter failed prospective confirmation and is rejected. Two subsequent learned adapters remain post-failure development. A frozen audit showed that their apparent boundary accuracy depends materially on how a surface is extracted from threshold-derived, often disconnected mineralized-tissue masks; the original 21.6-micrometre value is not a definitive interface-accuracy claim. Mechanistic language remains associative and non-causal.

## Novelty thesis to audit

The proposed contribution is not that Fourier transforms, structure tensors, Hessians, local thickness or variograms are new. It is a typed, physically indexed response geometry that preserves scale-resolved curves, perturbation stability, validity flags, abstention reasons and provenance across measurement modules. The novelty survives only if this common grammar is useful beyond packaging familiar algorithms. The auditor should therefore compare NOSTOS against individual conventional methods, naive concatenation, IBSI radiomics and scattering, and should treat the retained prospective failures as constraints on—not support for—the central claim.

## Clinical translation threshold

The current software is a clinically oriented research prototype, not a clinically validated product. A defensible clinical-use claim requires, at minimum: a prespecified intended use and target population; expert reference segmentation with inter-reader analysis; prospective acquisition on the intended microscope or arthroscope; locked calibration and QC; independent-site validation; time-to-result and failure-rate reporting; comparison with standard care; clinical decision-impact analysis; human-factors testing; cybersecurity and audit logging; model/version control; and the applicable regulatory quality system. Until those elements exist, the software deliberately withholds a clinical decision and reports only research measurements.

## Public tool surface

```text
nostos doctor
nostos analyze IMAGE --stain {SafO,HE,PLM} --pixel-size-um FLOAT --output DIRECTORY
nostos serve [--host 127.0.0.1] [--port 8765] [--no-browser]
nostos batch MANIFEST --output CSV --stain {SafO,HE,PLM} --site {Medial,Lateral} --section-rank N --workers N
```

The learned segmentation checkpoint is optional. Without it, `analyze` and `serve` use deterministic stain-aware proposals and CPU Fourier/texture features.

## Clean reproduction sequence

```powershell
git clone --branch v0.3.0-rc15 https://github.com/RonnieHappy/NOSTOS.git
cd NOSTOS
$env:UV_LINK_MODE='copy'  # only if Windows/cloud storage rejects hardlinks
uv sync --frozen --extra dev
nostos doctor
nostos analyze path\to\section.tif --stain SafO --pixel-size-um 5.16 --output outputs\case
nostos serve --no-browser
uv run python -m pytest -q
uv run nostos build-evidence-bundle --project-root . --output outputs/independent-evidence-index
```

Raw data are intentionally excluded from Git and must be obtained from the original repository under its applicable licence. Inspect `storage.json`, `README.md`, the audit manifest and locked protocols before running the cohort workflows.

## Automated verification captured during package generation

### Test suite — exit code 0

```text
........................................................................ [ 39%]
........................................................................ [ 79%]
.....................................                                    [100%]
181 passed, 4 skipped in 22.85s
```

### Dependency consistency — exit code 0

```text
Using Python 3.13.13 environment at: outputs\cleanroom-v27-release-final5\nostos-0.3.0\.venv
Checked 34 packages in 2ms
All installed packages are compatible
```

### Installation and storage doctor — exit code 0

```json
{
  "status": "ready",
  "python": "3.13.13",
  "project_root": "<PROJECT_ROOT>",
  "checks": [
    {
      "check": "python:numpy",
      "ok": true
    },
    {
      "check": "python:pandas",
      "ok": true
    },
    {
      "check": "python:PIL",
      "ok": true
    },
    {
      "check": "python:scipy",
      "ok": true
    },
    {
      "check": "python:skimage",
      "ok": true
    },
    {
      "check": "python:sklearn",
      "ok": true
    },
    {
      "check": "python:tifffile",
      "ok": true
    },
    {
      "check": "web_app",
      "ok": true
    },
    {
      "check": "storage_config",
      "ok": true
    },
    {
      "check": "storage:project_root",
      "ok": true,
      "path": "<PROJECT_ROOT>"
    },
    {
      "check": "storage:bulk_storage_root",
      "ok": true,
      "path": "<DATA_ROOT>"
    },
    {
      "check": "storage:data_root",
      "ok": true,
      "path": "<DATA_ROOT>\\data"
    },
    {
      "check": "storage:python_environment",
      "ok": true,
      "path": "<DATA_ROOT>\\.venv"
    },
    {
      "check": "config:cpu_app",
      "ok": true,
      "value": "http://127.0.0.1:8765"
    },
    {
      "check": "config:gpu_comparison_app",
      "ok": true,
      "value": "http://127.0.0.1:8766"
    }
  ]
}
```

## End-to-end smoke-test evidence

- Source: `<DATA_ROOT>\data\annotations\images\002_Lateral_SafO_SafO.png`
- Status: `complete`
- Device: `cpu`
- Segmentation supervision: `classical_stain_aware_segmentation`
- Analysed tiles: `12`
- Elapsed analysis time: `0.763 s`
- Outputs: `outputs/tool_smoke/analysis.json`, `mask.png`, `overlay.png`, `spectrum.png`

## Reproducibility architecture

- `src/nostos/data`: source auditing, metadata normalization, participant splits, analysis-table assembly and archival.
- `src/nostos/segmentation`: weak proposals, annotation preparation, learned training/inference and evaluation.
- `src/nostos/features`: calibrated spectral, tensor, Hessian, thickness, network and spatial response modules.
- `src/nostos/validation`: phantoms, perturbation harnesses, official comparators, prospective transfers and machine-readable evidence indexing.
- `src/nostos/modeling`: participant-grouped prediction, ablations, locked analyses and severity benchmarking.
- `src/nostos/evaluation`: robustness, confounding, agreement, adjacent-section replication, reader reliability and mechanistic subscores.
- `src/nostos/reporting`: manuscript-facing tables, cohort reports, segmentation reports and publication bundles.
- `src/nostos/app`: single-image analyzer, local HTTP workstation and CPU cohort batch runner.
- `tests`: automated invariants for participant grouping, feature extraction, segmentation, statistics, reporting and release gates.

## Highest-priority independent audit questions

1. Does every split and cross-validation path group by participant before preprocessing or feature selection?
2. Are pixel sizes read from authoritative metadata and propagated consistently into cycles-per-millimetre features?
3. Do the prospective retrieval, training-free osteochondral-interface, learned-adapter and reference-definition failures appear completely and consistently in code, receipts, discussion and claim ledger?
4. Are all bootstrap, false-discovery-rate and permutation families defined before outcome inspection?
5. Does adjacent-section replication remain independent enough to support repeatability without being described as external validation?
6. Are PLM comparisons honest about adjacency and absence of deformable registration?
7. Are 3D feature terrains and interpolated fields clearly distinguished from physical topography?
8. Do failure cases abstain or return explicit invalidity reasons rather than apparently valid measurements?
9. Can a clean environment reproduce manuscript tables and figure source data from the licensed raw dataset?
10. Do the manuscript title, abstract, figures and discussion stay within the evidence boundaries above?

## Known release limitations

- No independent external cartilage cohort or prospective acquisition.
- No expert reference-mask study covering the full cohort.
- The frozen universal identity-retrieval confirmation failed six substantive gates.
- The frozen training-free osteochondral-interface confirmation failed seven substantive gates and the adapter is rejected.
- The patient-grouped learned adapter improved whole-mask overlap but failed six of nine development gates; a boundary-aware redesign also failed five substantive gates.
- The threshold-derived mineralized-tissue masks do not define a unique continuous interface: four frozen extraction policies produced median errors from 16.0 to 512.8 micrometres and changed model ranking.
- A manually adjudicated interface set with a locked anatomical coordinate convention is required before further adapter promotion.
- No validated learned/imported ROI adapter on an untouched acquisition.
- No independent external user has reproduced a complete archived result.
- No direct tissue-mechanics measurements.
- No hardened multi-user server, authentication layer or regulatory quality system.
- No streaming reader for pyramidal whole-slide TIFFs; single-image analysis decodes into memory.
- No signed release artifact, container image, DICOM interface or plugin API.
- The depth-atlas outcome analysis remains gated because its complete-depth coverage criterion failed.

## SHA-256 manifest of reproducibility-critical files

Files hashed: 370

```text
1d1ae2f538b14db165c74f9136f9d2cfef7cb482072b81061bcc3f9aad88b2ca  .gitignore
43b5e3e1fcf53d2f7196c14bdb30e70ef3ac4ebec593c23cf432eb531853c619  README.md
3637f3270143af89ceca25c61a5388581362af3913e6cbb56f194b4f53616d07  configs/bone_3d_network_contract.locked.json
84da41b72d50211fbcb0fa1e5af05eaf1d27d5ab00ae7dca46f44307dc1c96bb  configs/bone_3d_network_contract_v2.locked.json
ccca344f5381c48edf4dbdc1dcbed652733fda3204fc95af83310c0f80bf58b6  configs/bone_contract_orientation.locked.json
abc971daf86984e6a893d943cb387d03c97b1b994ad20fd600d3641933917b4c  configs/bone_contract_orientation_v2.locked.json
c4b14c2cd774e52c4994dae0160454eeb8872851e22e8a0eda8dd307143743e0  configs/depth_atlas_v1.json
140f4e9c21497ad711c0c7cabf0ed201f8ce0ce935a60872ff8c05624ac5b9fe  configs/human_nanoct_scale_response_v2.locked.json
365478fe91ab6b3b91aac27c40e1edb523be93340c38a4255d061ab9a8685178  configs/human_nanoct_transfer.locked.json
c21003b751a2c179057dfa7fca51c31901ca09641666784b100a54060fe28824  configs/manuscript_gates.json
b313479c529b7291dd57492534de8cfc23a3f604e19ef6896c0cf985723558dd  configs/pipeline.json
9259036353a9459602899906e149cae71fb5be7ca144d633764d9e8bd66b9661  configs/public_histology_v1.json
b79dde87bf8766c4d7b1c3c135b1fa6ccfaa950677d410adcc1baef85fb4674a  configs/radiomics39-environment.yml
c545828a5d69f147da714f11403cabe07733b0433b9bdafd86599266ef94e58a  configs/radiomics39-explicit.txt
43d711c7b1458ae2ea48de134e6ebfc8d6bc8bf07a432b259a803cc0b0fd087d  configs/uvpam_abstention.locked.json
7908a9ed157b029cf352d9ce13348a85665cae8be62d557a963dff13b7efd193  docs/FINAL_RELEASE_AUDIT.md
e6c45e2f2edcd2fdae155dd81e772c65001b823420051c68ec9543de61a8a653  docs/NOSTOS0_BIOLOGICAL_RETRIEVAL_CONFIRMATION_PROTOCOL.md
1bcc2fd784ee3a6dfa3c6425accb7c1574aa0ffcad8f407fc88df169dbafdfe9  docs/NOSTOS0_CLAIM_EVIDENCE_LEDGER.md
a87732ac8e466185f5d2127e4082f4c52226a21a01b3c969276b86ea7e11f03b  docs/NOSTOS0_COMPLETE_PUBLIC_DATA_READINESS_AUDIT.md
06b721be60d4c124506be8233c01dea30ae1de926dee14ba799375570079fce9  docs/NOSTOS0_FINAL_MAX_AUDIT.md
f028ee3fe5290e045a14dd659e811b9026e58386e4a6d35eaa3f23404378d31b  docs/NOSTOS0_METHODS_ARTICLE.md
d23d930fa6ee30a106eca24dad3dda7856bf733e0a28e849b9d2628a3a1c1fc5  docs/NOSTOS0_OSTEOCHONDRAL_INTERFACE_CONFIRMATION_PROTOCOL.md
b896df299ec9e9a8dae0209d3d969ebc3aa750b5afa4b200080211ff66ab49fd  docs/NOSTOS0_OSTEOCHONDRAL_LEARNED_ADAPTER_BENCHMARK.md
0a321563c9471fd53b3ed8ea00e4283a63976dd55663feaa4e50f330c8c887a6  docs/NOSTOS0_SOFTWARE_RESOURCE_ARTICLE.md
ae7226f9cca037c823022728cdbd0bffeabafd78b9d1aaf348f33a142ae7315a  docs/NOSTOS0_software_resource_submission_candidate.docx
d2ae92f82b918041598cf5f8224d4dcc86a6d4a233a90933c72845a7cac251bb  docs/analysis_plan.md
f5b555dc824c626d40a560024ebe361d3453e18e6b8d1039e36de8f0a2e7019a  docs/confirmatory_deviations.md
844a169d584f1c52f8b7fce116d0b181b93dbd4603b4d268bcf0fa316de76e53  docs/confirmatory_replication_protocol.md
4f4d4b0771464c2551d694fa0ca725e65c445e25d9b99be8652009fa3022c4c1  docs/manuscript_draft.md
ea8660c566223c7ea149045f42eacea8204902b0cd979fee2d7ea535db8163f0  docs/mechanistic_discrimination_protocol.md
33bba5fb8f3b60a2db55db103c8da081af25eda843c384cddbbc5e4eb7470ead  figures/nostos0/supplementary_figure_1_bone_contract_stress.manifest.json
76694403d5238e32190c5e75b5203eb7f20d682966426d4487e2ebe019324cf5  launch_nostos.ps1
ddbe43e9c54d428625ce34769aa61fcdcf1ef0494ed0909b8450f99b2e6ca856  outputs/nostos0-bbbc006-qc-confirmation-v1/bbbc006_qc_confirmation.json
511e1ed21391f082f221d64b76fb39b509b6e9d0f82e0c4848f4227fe91877fb  outputs/nostos0-bbbc006-spatial-confirmation-v1/bbbc006_spatial_confirmation.json
7babed3f53f28c6a2976169a94f5b17e8d182a5d3fd6f84538499d4e39c11f04  outputs/nostos0-bbbc035-dense-deformation-confirmation-v1/bbbc035_dense_deformation_confirmation.json
373a1dfa7bcad32cf272be0b320e21ae5b9b4f9aa4d2c220f7118a5c862a94b4  outputs/nostos0-bbbc035-dynamic-confirmation-v1/bbbc035_dynamic_confirmation.json
2a5931cea56dac5262d32577697e555afed19beff61e0d8ccb03c100737ded03  outputs/nostos0-biological-retrieval-confirmation-v1/biological_retrieval_confirmation.json
b0a8f66e634df5b2ea78eebccd68c526038c1e689dd72cd2e76c947c1f4fbb94  outputs/nostos0-bone-contract-summary/bone_contract_program_summary.json
561f5592e9d05f66240d1c17caa9f1fbd84d18a5af203cabaec37caf499a04f7  outputs/nostos0-bonej-thickness-v1/bonej_thickness_comparator.json
f44724c295ad46495c4307d410b35a9ee5a5d7415d79ef907a433e0a6a4358ce  outputs/nostos0-complete-readiness-audit-v1/readiness_audit.json
3b259905763057d4a2a25df2bda37ab7a457c25872202945b589a8c9eccb0aa0  outputs/nostos0-ctc-hela02-lineage-transfer-v1/ctc_hela02_lineage_transfer.json
c90c17f8e3bef0cf64bec4c381dbc03ebb9244d5c95d4bc54c74b3917ef2a3a6  outputs/nostos0-ctc-native-tracking-confirmation-v1/ctc_native_tracking_confirmation.json
519fe1706ba73adc7c62c0c5a0e05f29d8523407f8db630eeb18d58341ba02fa  outputs/nostos0-ctc-tracking-development-v1/ctc_tracking_development.json
a25adb65aa27c10308f0bdff7d4bd5687d41baea7b418695d1e73e6eb925c936  outputs/nostos0-ctc-tracking-tool-workflow-v1/ctc_tracking_tool_workflow.json
872065df08c39be5bcd427d5a0f7c25f41fdcdff16e5d8499c5a03f92861c16e  outputs/nostos0-dense-deformation-analytic-confirmation-v1/dense_deformation_analytic_confirmation.json
deec8cac94c8123344cc58f64e1c84f8c1f8e4f71c63ed1341f8624dfd5481e1  outputs/nostos0-dense-deformation-analytic-v1/dense_deformation_validation.json
255e6abd22cf95a5cf9a654c85a2fbdcdfe311bd77b74a9ae28ebc883776fcde  outputs/nostos0-dense-tool-workflow-v1/dense_tool_workflow.json
af827a081a2af5e371464f0c036b1eceedfde174dbf8afde9a3614c5263954e2  outputs/nostos0-dense-tool-workflow-v1/dense_tool_workflow_initial_failure.json
e9fecb1156a70f752aff50d74b00e652d3f1a7ed15796ee62e48d45005d90dea  outputs/nostos0-dense-uncertainty-development-v1/dense_uncertainty_development.json
3651c5d2885cbd6d97af337d63ae5a627e41d70a0778bb2dcf433418c01a312b  outputs/nostos0-dynamic-synthetic-v1/dynamic_validation.json
d30a7e26eb45343c1d9654b91c776b2c54e4e984ca660c1c726bb7259dcbfaa6  outputs/nostos0-evidence-bundle-v27/checksums.sha256
be57bd32012ad4729e5c7d41a30d50ba3b8274bc67e46df5ed4d1fda381622fe  outputs/nostos0-evidence-bundle-v27/evidence_index.json
a2e05e68f66e70fd64492f325da7b3f69db9a6c5c527fbb098231f227e2b161f  outputs/nostos0-final-max-audit-v1/final_audit.json
73c6c146a452b119e40754d6dcb040d675556c763eb21790a865299126e00f00  outputs/nostos0-hrf-network-v1/hrf_network_validation.json
8742fe695b4a0c2c4aa7af3e6b09631b8d7d9e4eef6f1f4b4eb1db0ea0f8cac1  outputs/nostos0-manuscript-qa-v1/manuscript_qa.json
b72dac67ec14d0c6026557cd1572f0179c81ebe14fee150faa76f9ed1d9fec3a  outputs/nostos0-network-resampling-development-v1_1/network_resampling_development.json
9dbf2e38c65c04d692be9fce544b83dd0603fad2e152f19b894e18ea078158b8  outputs/nostos0-osteochondral-boundary-adapter-v2/osteochondral_learned_adapter_summary.json
de8971122445aceaffec6320b668ee7dcbc18ee308304f2bb586d7a1cb69111c  outputs/nostos0-osteochondral-interface-confirmation-v1/osteochondral_interface_confirmation.json
e978bbddd301f3baa1376683b8dc5a65d785352ce4d8496261c1628ac56f8a06  outputs/nostos0-osteochondral-learned-adapter-v1_1/osteochondral_learned_adapter_summary.json
8afa7525ada6851db9a4eb60b241c0105273c89204390c0469c296fed72e1ee6  outputs/nostos0-osteochondral-reference-audit-v1/osteochondral_reference_definition_audit_summary.json
d071a495745586d61bcbce7987e6fe4dff87adca92f24b4a38ca0f4fe9171eb4  outputs/nostos0-public-tool-workflows-v1/public_tool_workflows.json
768f4bcd4b18e69995be4b6d9347c2a533aaf767d8d52a81ace2e71ae8a7b983  outputs/nostos0-release-candidate-v27/cleanroom_initial_failure.json
e65cb875723a1072e7f63bae0ac9d5a51095c86f7337cd40f71d7d3aca9a82f2  outputs/nostos0-release-candidate-v27/cleanroom_verification.json
38f8b92269030a84b8ea9ac3e6264994e0c27eab867320236e36110456f5578d  outputs/nostos0-release-candidate-v27/nostos-0.3.0-release-candidate.zip
c4e8079a6e05d7aef09a1c3bed9b8f2789f675523b806ec6f08a1fc25948a6f0  outputs/nostos0-release-candidate-v27/release_manifest.json
64244fb3baa80621535ce4a55864f99b9b8646e1ffc378d2e78aac2d55e5e0c2  outputs/nostos0-release-candidate-v27/release_receipt.json
da9c59ad2508685325ab2ee805b94c23d90b5ce80a583cd51f5b41a0305fdb96  outputs/nostos0-stare-network-confirmation-v1/stare_network_confirmation.json
288cdc44be9bb405bb95e032fcfefcda39037a39cf95c48f35adc88373156d66  outputs/nostos0-structure-tensor-comparator-v1/structure_tensor_comparator.json
9204767675b912b7f1ece4469799dc1009fa3e2afd966d7956bf6337faa5844c  pyproject.toml
74ad593191a75ee06e373f819e6bd7466e4779b403006651665476a1dcbccc3f  requirements-lock.txt
eeee796a01d8e443973056a98b5661788948ec5ffd0e562dcd92179f33f81ab5  requirements-segmentation-cu128.txt
12e3efe33aaef0c1d1ae0c4a3e6e832603f9ce9e68807778300bcd21f4d286e7  run_cpu_pilot.ps1
d9ce245d3e32a942f636cd17c714ebd72d2a33436c2300ef77665d5fdc62bc66  run_flagship_validation.ps1
fda95fa6874cd54b4a8eea6c0c093a7992423f5392889ef8fe33de10e84f1ef0  scripts/audit_bonej_thickness.py
4fb54c033ced4c97f2e21b47c01f3cce1be910c55f28d0013eb3c83ad885fab5  scripts/audit_ctc_division_geometry.py
c88dd4c39602e244f194e4fd2b95f09d6b35d9ed4d78b3594b3730d5ddaf0b8e  scripts/audit_osteochondral_reference_definition.py
57cb81f48381f1a76249b4ec36906a91a6b938684f11a213c1e3b97aa5424967  scripts/audit_structure_tensor_comparator.py
6e0dacd0d3d69c74d100740af6f5aa6ccac81fd1f0c7f88ce8c6de61604be132  scripts/benchmark_kymatio.py
9e6c05ae5d01087ad5344b2fecfdbe69a97a563a0c43beb9784a8faace1e6bbb  scripts/benchmark_pyradiomics.py
2042d63ac9ea505231031484db7c0d486b1afc5223ed6ea2cfc527f8dbe3f423  scripts/benchmark_pyradiomics_ibsi_texture.py
bde5a5ff5ae6f5c5764eab2ffb09c236a7a362643a0a39cb266c82c20da689b5  scripts/build_bone_contract_figure.py
62645a727b963ae4039dc4fac102b51632efcd156c64e8d0a5473c872f7cab89  scripts/build_bone_contract_summary.py
b9737d4b319aa5d25f6b8bd61d4db069ccb92ffb1776d038112d1f68e8b5bac4  scripts/build_eight_visual_figures.py
8fae48ba9a7fee2ec6ea4dbbe6ad832fe14834ae06d3bb0205971cf373530f17  scripts/build_experiential_figures.py
5cd8da4a70572dd89d5f3e6ea34321af324097d537980468efa0a5908de1131b  scripts/build_external_audit_package.py
c1111521f596bbf5558ad79753250a9183e48d99fad0426b586ca03f90429d78  scripts/build_final_max_audit.py
5c563c82a44c3d8de9a97f1765ebf5c936a879ae80cdec3e3ede3fd81d0dbc50  scripts/build_guided_review_deck.ps1
fcbd394bbe200611ee98dd023e19e38cc321f8cc2deef91f7a62a04097a8eb3c  scripts/build_manuscript_docx.py
e128a57becd468a77bb36866479079ae4612d212faf8e05aa2c30e751ded8031  scripts/build_manuscript_qa_receipt.py
29d164f64f5b21729d1b875240e0ac5b224908c7f07a89828aa92a8a8a4c5295  scripts/build_megafigures.py
5c0ef7994e642b88cabb541ba358f29908980dadc0b22b2d1d40a620648a8e1f  scripts/build_nature_figures.py
3aa192fb956bd3c7a2e69ae0782461c1183a80c8af224231e4bffcb56a66dd70  scripts/build_nbe_documents.py
dd9015194acbb8fbd1c57b4929a4b4afb9dd2281bc3ac26c89b0e75df80b0d4a  scripts/build_nostos0_figure1.py
b117e61a6de85f789d5cd23a6e6c54b8d607412128cf2cff88306a28f5329bac  scripts/build_nostos0_main_figures.py
0576fe8ecde5bcaa70a37b740f7760cb31ce7594241e1e9148cfb771c93aeeaa  scripts/build_nostos0_methods_docx.py
9988afe401334f27c6b612b80d5abf632170c6c6cce351fa17b62935fabc4ca6  scripts/build_osteochondral_adapter_diagnostics.py
1aabe5a1791d0854f82173e54270caa5654fe4861c08fae0bc1f6764995822d2  scripts/build_supplement_docx.py
c0130e59c805cb1c2b1034a8ead99ad8db1f1588c35c0142dad60c3f4a9e6139  scripts/confirm_bbbc006_qc.py
18e6924d967f0ec86208c46da9a6f859c582f537a931c09c3ccfcc0e3066eea7  scripts/confirm_bbbc006_spatial.py
373088fbc48d44f43f7527edbdda874ecbf18775e0b03b8b3ca19b812b59ad21  scripts/confirm_bbbc035_dense_deformation.py
3b66601bfbe368d59b53c78cbc30d2897efc474b630927a3f8503fc0de28b841  scripts/confirm_bbbc035_dynamic.py
3f70d15325f5d6ecf0a4efa26c725dd019d0449591e3fe21ae03b2731e7bf2aa  scripts/confirm_ctc_tracking.py
541c2f5a65fccb848389d6763a88cc574f1a2fa1ab999abd65ca587ecce93ea2  scripts/confirm_ctc_tracking_hela02.py
51ccf8272b5215c72504a82a2b8cff103cf528cd8e5674d10371a7d63389e35e  scripts/confirm_dense_deformation_analytic.py
abcbd89afc2d5bbe7dcd77ab8c57ececc8f3b8c72fb60912ed517f7e3696a103  scripts/confirm_stare_network.py
d91046e1834d11a80c1850db9b5a1151b4cbf6465f03f970739f13a6c142ef1b  scripts/debug_bonej_thickness.ijm
ab70c2edfbe552b626137e8692804b04bb870d11cef1f8862d9767589b18ea61  scripts/develop_ctc_division_rule.py
df5e1fed9ac6a8ec8f30a8c329b979e7d387899b458a8a0482a73ddd1205d457  scripts/develop_ctc_tracking.py
bb653a6f585881df6390a5e31858f2315b12f8fef65240409d2a1e279fdd8580  scripts/develop_dense_uncertainty.py
d61d76c13b2ad8390f5e7c2c225e28c3d71b80b590b54bb521924c6873bf3f52  scripts/develop_focus_metric.py
957209376349584bcbe857aeddb071036c037e1f04fd3bb507f27322215b17d9  scripts/develop_network_resampling.py
6c46932b7afc9138d8962ff3c7d8e19b2b2da7a407b8657b3745ea3f77b1eefd  scripts/download_bone_contract_datasets.ps1
9380ae1b1e112bea59253abcf45befcfcba0c41cdf90e39a72d3e314f8bf7870  scripts/download_pshg_tiss.py
e8ff5ae8a0117160eab25a175e0f154a405937c2b691f6f69f3e883cecd507e0  scripts/dry_run_cartilage_review_evaluator.py
dd1328c7de2fb03cd20d3266b4c6a5aa5951f2a364865ec98fd87cb1205be33b  scripts/fetch_bbbc007_reference.ps1
4d2f4ecfc11eb7ac049892fb16c641c0040722af919994a4dddc65a0f68df647  scripts/fetch_bbbc020_reference.ps1
679709d989d20f161e89136828776f66b61b64911dc13207e0aa7230156d31e9  scripts/fetch_bbbc039_reference.ps1
5bcfa011391338053bdc26b51fe992ea8e6cb5332a2ce6a8871012586dc7de11  scripts/fetch_bone_reference_subset.ps1
16241db267c34c9ec30663e77046d98ac97a0a4a919ffb81bc6f98a022976311  scripts/fetch_filament_reference_subset.ps1
2e70af4ab4efdf990e341145a04039d8c7f0c5bcba6ecdd3378c7b55935ac007  scripts/prepare_bbbc006_spatial.py
909cf1dca5d3c8fd6e2aac05580a55fe6a317411b156fa0bbbd9363d207a71fe  scripts/prepare_bonej_inputs.py
411f3e1762a6f2a90d35c914bb7af999c677cca263304459bf496116fe382ef8  scripts/run_biological_retrieval_confirmation.py
316edc3efa747ef33c170576e34962425fe5e90be3628fa01b2c03b75402dc22  scripts/run_biological_retrieval_development.py
93eb65bba1ca325a595f0a819975a2133eb944723bfa208fc57c1fb887d601a9  scripts/run_bone_contract_orientation.py
87e4e4e01fc9b01c32e598434f98417c225361887ce857f656754b84e6134766  scripts/run_bone_contract_program.ps1
e82463e2b8cdfd8348aefaf203cbfb6b86fefc4962de9ab2cd7b551a2c086553  scripts/run_bone_network_3d.py
8520425222ac0f724d17740fd07e4995a88dfbce64e64e2ab90f5d2bf38bdace  scripts/run_bone_orientation_v2.py
ec02e856153150a8cbaee3db27882898c10fcc27374de3a2f23ddbd5361583e0  scripts/run_bonej_thickness.ijm
f7de93975c46709a388748ee3a30c8c08839f219eba4556fbd5db97df660a111  scripts/run_canonical_confirmation_v3.py
a1692505597041f1560bccd3270f1d40981f1bb7e1c1265ce868e2a2196ad1e1  scripts/run_canonical_development.py
a7fc45b9c524670c98dad9c57241ccecc287a7fc65d9bb8606078bb9e307ce9c  scripts/run_consensus_reliability.py
62fe6efe3a35b78bbaf2f403e9de2aeb4264c84ad09f4b2f46912197a8370cee  scripts/run_ctc_tracking_tool_workflow.py
cf014de1177bee88998b72759cbabfca4950242093f7eda2227da229efed81dd  scripts/run_dense_tool_workflow.py
6514a652440d8971cd29823afbe56e9f911d159fce3f138817b2eece2782f138  scripts/run_human_nanoct_scale_response.py
c45edbf48727e2d8be5c697338aadc1f4ba297682e483c2ee0681f9d0628caf6  scripts/run_human_nanoct_transfer.py
478e6b8cba141b5866c9c2136b9bc24993708a4ea4ad87e394ddc13e6c8958bf  scripts/run_local_orientation_external_test.py
1c4d65df39d74cf26b946aa8d2dbf79d584275b02143ebd55321390f8bff7228  scripts/run_local_orientation_validation.py
af83cc25eb5a4180eb4028c75cad83b526692e2ba54431601c9ceb01ef592ef5  scripts/run_orbit_redesign_development.py
dc0853c231e1fc302a7607c2a8a20bb0df50a9bd592245cd834cdca4b5f6ef00  scripts/run_osteochondral_interface_confirmation.py
ec8a9c0470460da86f217e853309e417d882ca6945e484b45c17671a77169d1a  scripts/run_osteochondral_interface_development.py
34b12187cba21fce9f161a33674d8846322e765dbc79b7061cd463fa61bd389c  scripts/run_osteochondral_learned_adapter.py
7c9aba2ac1b1a8bfadc96a7c6543607fe5c5d615a19e9b2cbc50f105a249b8d6  scripts/run_pshg_external_orientation.py
adc8de028dec0faedf4b92b79d89aca8b5fb09218a5c8f8779bfb1dbde81763f  scripts/run_public_tool_workflows.py
5dc83a5b083d5cca68247668e7aa50d4a31f9e68c2cbd888e06644eb94ff5abb  scripts/run_response_benchmark_v2.py
4c74c597fda5c6fc08dd53c15dac75a045111af6584dcb7cc1894e67b7596fe4  scripts/run_selective_fft_confirmation.py
a9fe5c50ecdcf0d4e889173ad7fe98df8cad07ade7b350204d5652a17c44efad  scripts/run_selective_fft_development.py
a4190451e5eabc94a661f53b2b5485a6e89d4ac5dd45ea26dfed0e42f70e1cee  scripts/run_selective_filament_transfer.py
2c4d3b14e7ada48c68d2da1b0ef02c39bbdf1eea1fb7ddda0f6a5def296ce30f  scripts/run_selective_shg_transfer.py
6bd19c210d08cecd06895c127dde177a6e75c147d4bbd3101c8a0aa885f924b4  scripts/run_stability_weighting_development.py
a373ab133be43d8ecc4bf053f6a5726f35c215e36b6509aebf0829929f97822b  scripts/run_uvpam_abstention.py
571b389c5f8df8c5ed9b84efc35ef6027036e0c155ff44f3b0607d668f804cdf  scripts/validate_bbbc006_qc.py
8764026ec407fd54bef396b754b61cad7d89b8cccfd4401e36bdd715933cd09c  scripts/validate_dense_deformation.py
0848ce895fb60e55755a61aa438a1f509d238f0e891d83d1286d25be040b1f08  scripts/validate_dynamic_synthetic.py
eed3fa525212dec53d8e8048c4e6abc2f6cb7946317e09dc06dfe2156bfb2231  scripts/validate_hrf_network.py
c0d44dd44fc8d465911a714b3d5f55dc3473419293902f73d10b67fffea9b5c4  scripts/verify_bone_contract_downloads.ps1
5f6e61a08b125ff471409dcfbf54acfac4f04e2e58acab65eaecf285072b8fb7  src/nostos.egg-info/PKG-INFO
498364ee5d7c50c971b92ceb72eeb64ecd02d5792221daa314ec5716dd42526e  src/nostos.egg-info/SOURCES.txt
01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b  src/nostos.egg-info/dependency_links.txt
667bb406fb63c96d77bb1f715fdb1bb9221156bd0c69be620465ef0ed0b7cb22  src/nostos.egg-info/entry_points.txt
dc3ce598d91199a791ac910b8ac57e591500bfae62d18e4528a81c09ce76e950  src/nostos.egg-info/requires.txt
576646d8ff7824b3ec19736884ad52d43a5b17c6fdafbe71ebc8317b22df361f  src/nostos.egg-info/top_level.txt
67c83c424bf3023df0d1bd9d6a6464dec68409e15c84b6b6c23535ad62687530  src/nostos/__init__.py
5f529d1f2ecfca575733108f415c66fb3cdb979e37b3a6420f7a88a43739fcb9  src/nostos/app/__init__.py
24f5a9be0c38f00f2735ec9b11a9986f647503a0538dbb7b3eaaa2f8d1cafeac  src/nostos/app/batch_cpu.py
202c6157c8a55c66692e0354575f0d1949dac90746e7402d3e2b851ca6026ce6  src/nostos/app/measure.py
5a6c84ac20b9e77adfaf963c24824a4250d04baa2164543e1a34e6bbfe87a6d9  src/nostos/app/server.py
7caa22b3e1dee86837be584b56189df18f511ff76de6096dc8dc0c1c05cbba8c  src/nostos/cli.py
65bc2e25fd69310acdcd67f09ba8107be110defaff4fc703a51b93c6613df21a  src/nostos/core/__init__.py
9e9fc39a35a2c000cf5ad47f07595c2052e327bad9c08b42b62011429e272353  src/nostos/core/qc.py
f7c31ba27c272d897c166b63fe61a9a718fae61d2c47cd946fd6048afc419930  src/nostos/core/response.py
b26d31b0d28d2a17c5c09ae32f8ea55333b3a6da929b2a98e004685b5f412d29  src/nostos/data/__init__.py
e265a09741f2db637b17333d12bce54a737a6aff69a3c92958fadfb4f4e00e7c  src/nostos/data/analysis_table.py
27b039eb39e1eb2a46c8db009ea2787480d867d65275f83cb4e6da7b6f052d91  src/nostos/data/archive.py
b4b28b581a5415745321235de82b3a8b3a172d5e2755503891f6caf6a17af634  src/nostos/data/audit.py
45ebb00ffa6262dc6fbe495b5f5f316ba8bf4eb23d1d6253b201fd0b52ac2b9d  src/nostos/data/metadata.py
3ce54ba52d192a2d0db4c977d64a064c90cb8e954f47b8c9a1a370aad1cb1feb  src/nostos/data/split.py
c584d8037081347c706a3e81f35228f48168dfc115ab6ec3eeb4b1968ea104c4  src/nostos/data/tiles.py
cc91c7288f4f6ec16a94f4614696e62de12ad10282cd4c551ec1cb4c3c9be773  src/nostos/evaluation/__init__.py
5ef26495e40d6796f731066f23074652cc07a051f70fdb8efd568366d49c5972  src/nostos/evaluation/adjacent_replication.py
66feb0b42692cf4c3a10f07957d570a780bfca548a8a4f8d39aaa963822dca7d  src/nostos/evaluation/agreement.py
2277083fd03d2cda11a8b1a53c2a6fb8e5926420edae742f20a544ee5d92ec5e  src/nostos/evaluation/cartilage_ablation_analysis.py
4b8dbf9e2335c53204f81b7e84b509479929940be784f0a8589cc01c09d1f09f  src/nostos/evaluation/cartilage_ablations.py
a546d56be0b8cf620a42a9bd1cbbb0c60a12e0e7af84bc0951e135a251a708c2  src/nostos/evaluation/cpu_confounding.py
4fabf3da073ab39d8cd6c40c22a91788a2cb46f3959e91d5bb710223cc3aedfe  src/nostos/evaluation/cpu_mask_sensitivity.py
1222fba4c49b18c871a0ee6c05a33ad4a9536732235002776b0955b2afabd823  src/nostos/evaluation/cpu_robustness.py
fbcc4c185e69f281c6a2f2a07c472a1e36a01575aa7ad4c506b659b7a6c49cb2  src/nostos/evaluation/gates.py
7c564c13fd7eaa2561edab61702cb320e2f46c6fd9807493e76c86c50143f2f7  src/nostos/evaluation/mask_uncertainty.py
1ba96cf429df1688cb5d2a73fef25d0e8ef503a72cf8d69107462fe49a0a10c9  src/nostos/evaluation/mechanistic_subscores.py
897196584170d20aee7327f9353afe64fa2c8c92e0f2f9c7f0ecf054ada3a7db  src/nostos/evaluation/participant.py
1ce7b4bdde52049adec6f6724baa3e8e87f8815ecca17fe2385ac80e01ab0da3  src/nostos/evaluation/reader_reliability.py
92694b82987d0d35c798a042457dccca0342f17b62897faafd7825783184bbeb  src/nostos/evaluation/reliability.py
1714ee470a738a4737dc0f6b15d270e5be23130f470b57e2e5d2944fdb70099d  src/nostos/evaluation/robustness.py
70589121b2cee00fe63a525d2ecaa01aff4b3fefacc6697e74da66595b9c2117  src/nostos/features/__init__.py
864ed063e6f4132413f031fcdbdfb3d75cf2bb8ef8aa38948db3aa1b2a8cd662  src/nostos/features/baselines.py
a238ab675157a31b7210ff2766145de236a43cbfaf3cb3cdc514ac5d7fd1dfad  src/nostos/features/canonical_geometry.py
d2cb32f0ca0f1a7fa685c3a4a3b982b802cbeb26a1aadd3ef14da725810f55a0  src/nostos/features/depth.py
420753059151bae5dd7a0a5ebd2f8eec38f666fb6d0a21b7a5f1f8b9277f507d  src/nostos/features/depth_atlas.py
fe0df1501707dda816a00c23ec9dd6ebdb426b6b96c8622b0872c35ef8c8eb54  src/nostos/features/dynamic.py
43210a407d077ba32caac10beffb93a7b732fa759d53e9a81e9adbf33194d2d9  src/nostos/features/response_modules.py
61c92724e4cb3e4c06f907c501e6231da1e8a7f91f55c314439c19e53ebcb50f  src/nostos/features/section.py
8314c18774e33501f88cdcb78950cfe23ac17d938cb0e071a4bb835e31c1900b  src/nostos/features/spatial_fft.py
7ec4cb942deb49400d762015377aa044767489a41662843547992d8850df6f2c  src/nostos/features/stability_weighting.py
3659fa2fd18636888e8f0482763c2f2eddff809efe044deca325f24c321deed0  src/nostos/features/tracking.py
196dadecaa5528d73cd268123221733a8b3254cb5350ac6950a52bfb2a55244c  src/nostos/features/universal.py
4b44846f3e14c100217dd13a9fbe507ae69a032efcfc6ea0e592be0da27d77b6  src/nostos/features/zsd.py
e965615238b25a23f83390b3b4a2c8cf8df61000d36c80b2589e16b4bcc6c123  src/nostos/modeling/__init__.py
4617c6516f06952e1742913e5bc5621e4a7eafddf2de2c32e807ea1386280ec1  src/nostos/modeling/ablations.py
c36ccdaa2e722cd047ded1a7674cdaa93086df959fb5738f9935620470f5143d  src/nostos/modeling/cpu_validation.py
789e4147d0965c61b8139bfcfa01d6d55c6b70756c386b59e220fb095f2e7b9e  src/nostos/modeling/grouped_ridge.py
3ef8929e051a283d86e76b3c6a0664f422213a537a0c340b1e2093d67fe8458b  src/nostos/modeling/locked_analysis.py
6048e5c23c78f496654e28dea8301cd9c9545601210ed76836b184e2613ecfe2  src/nostos/modeling/severity_benchmark.py
ed3972b469c013c20dbd02005bff223b86665d4172a79ae7c4494a3c4f1f8e7e  src/nostos/pipeline.py
ba7fc6f07e555ab9dc4e12f39b8f0163e97f77c2b3aca3b03ddde7314c4459fa  src/nostos/release.py
7f4a05133c27086cd0442c284356c346dead2aaf9ffda9d9c6fa717259fa4843  src/nostos/reporting/__init__.py
8948c096136efd8e4642e5dbf791ec370f6b5a416f69f7edd1fe66538a84341a  src/nostos/reporting/ablations.py
ed4ee2e93d7fc40de460f2ef0c8a83659c0cefa314a314028b9dc2da534f51ec  src/nostos/reporting/cohort.py
e73c53b744d13f1724369be42ac8540c6b46ba41da930c6c688f4ceb09b2931b  src/nostos/reporting/cpu_pilot.py
e83c5290db32412d3ee7f9e5ff8392757c865dae5831553b5d599f3920d18689  src/nostos/reporting/primary.py
6a45c7b74127d26d8cccf8e4d6d958a84c41b3fa53f07356487dbb8d6ce9a87c  src/nostos/reporting/publication_bundle.py
ebe2d801857437e768fc1d5a7c5a3e3f24675176d6fb80f752d4b33d1d521533  src/nostos/reporting/segmentation.py
22b2f6b25931e745e1130a8c3ae7c973c0bbcf27d16bc1656067396a68a48f7f  src/nostos/segmentation/__init__.py
9feccd2948e682a28a3f6ba2bf5f022ecc815b80b6e46b156f1b068432a17c31  src/nostos/segmentation/annotations.py
79eae8b8eea44b7fa4990780c8cefd11058267367a6f9bcb0091fdbd8a36f316  src/nostos/segmentation/dataset.py
526ee71ab575bbca7268adb8180b7d7b7a904d8f9c9f7f456e0cf0fd38b23b3e  src/nostos/segmentation/evaluate.py
b5311443000c05ba37772ae024eb46857e28cb1aec96f8fa6bbb01f8f3986276  src/nostos/segmentation/infer.py
48309216e541641ed5b3973f85b0a2566066ac2ee8c676539b3650af37f8e7e1  src/nostos/segmentation/metrics.py
850d5ec77ad46453e88283820b4a5d0eaff1721eb0ce24a5fc0fdcf46aff9c68  src/nostos/segmentation/model.py
a0ba45f91b76b344d46ff057b3da46c850b496d5db7fdff18e39fcbefc1dad64  src/nostos/segmentation/osteochondral.py
5e7c62d5c20d25eb433cbdc333b0d6694907b0bd9b7f2c433d5b9f46ef62266a  src/nostos/segmentation/prepare.py
f044120186e7c318ed0dce3c7d99e69ae1a2b91433a34a0ab235001e6b1a2fd4  src/nostos/segmentation/pseudo_labels.py
bab143aa8b732dd2492c592707e29658e99680c31d44f6803515884bf7c033c6  src/nostos/segmentation/review_evaluate.py
88ecc62585e93c890ff6ebf4781f363029d3b8603e06d791d4c4c9670af613b6  src/nostos/segmentation/review_packet.py
7f244fa49fab03947f1c5c4f57d772f2ebc75617d466834426382b72066d9217  src/nostos/segmentation/select_annotations.py
c021839a01ff3a1cd7fbc343ade5c82419984a67f3ff85d4fa40922944e1c595  src/nostos/segmentation/train.py
64822b72958a14ae3ea75305f4f57c4459e9fcbe139291165b69c76a1fb0944f  src/nostos/segmentation/weak_labels.py
7990952413b900015ce92f1f2156bc0a521e21ffb393b18d72af5317289d4ee7  src/nostos/validation/__init__.py
523455d1823efbfb3eebaf502b2e7d186dfd21cbf75dfe83bfa6242ca7fa3846  src/nostos/validation/biological_retrieval.py
5dc3576a13b394f23361776046241839dcd5cd4703e1153f2e32f02ee179939b  src/nostos/validation/bone_contract_orientation.py
6fd738bd6f6a2848eab820a56b3f2af95287a8032caa2bd0488ba42585d615c4  src/nostos/validation/bone_network_3d.py
f6f22f99461607669f3357ce0380f973a30cad09ab245a0e13e7ba8443e46ab1  src/nostos/validation/bone_orientation_v2.py
8001d2e57459e4b77f12627bcbce0c0c0b361adac7eb90da184fb01b78e89290  src/nostos/validation/bone_program_summary.py
00059a83630b6ba25ca6f0cef030fd514a1f805c72c2ba9e2c2a1063d46b063c  src/nostos/validation/canonical_confirmation_v3.py
322fb23cc06e32ef1abb6d13dfe387f2f583fee31883888d4c2fc9bc817bc203  src/nostos/validation/canonical_development.py
9c6512afcb600d2e859b74462146dbfe2084ff19cd3fa6c0a71921b1d41c6416  src/nostos/validation/comparator_conformance.py
57171c60bc10a54641d3d3a5cce5b7bc752337f45f242c0077d2db49e86d110f  src/nostos/validation/comparators.py
175dc6029aca4dde9007253b801a662409b3ddb4531b7461da17f0a09504508e  src/nostos/validation/consensus_reliability.py
f587f168f44b1b171c967ed7b68ddaa37155d601bb01ade6b73712adf877b620  src/nostos/validation/evidence_bundle.py
1011d7c0bb14d7b0399b187fc8f7fc263af772f65608a48a0eb665337844a0c0  src/nostos/validation/external_bone.py
3f2f3d08293de2b08ff9455d7ce51d02d8458be00741d546df08b580b584ce3b  src/nostos/validation/external_cartilage.py
2524c8c41e28bf4fc747e9a6cca56a4586e3adf7518aad892682563d52047096  src/nostos/validation/external_filament.py
518ff10eed8d980c477edbf19f91227402bca87a9d1fbf2c2b4fd5565333b635  src/nostos/validation/external_nuclei.py
05d3b47ba2c9e49403df1124d2f33b845b41e1bbfab4409ad69a395dbf5a81ff  src/nostos/validation/external_nuclei_bbbc020.py
d59dd41396caad19cd9aed7e9563b3d519d4ec098d7b5d38f57be51366ec8e94  src/nostos/validation/external_nuclei_confirmatory.py
3c40f2e0bb75f354b739e6d0c5c691e6024ca7b93771760043e98cffe99ccaa8  src/nostos/validation/final_audit.py
a39ddad29c5d579eb4b43f682bfb31bb122d69721ddcc7e12ef09a4059ff7b8c  src/nostos/validation/harness.py
aaf49acdc8866dfda68bd1f05b04d885a79adffb8f073cfd9ba79ffbc3c02d70  src/nostos/validation/human_nanoct_scale_response.py
e7ae93c0f053c3ab9951e1810b7bcc1c8f1589ddad22e383e31c1820bf160550  src/nostos/validation/human_nanoct_transfer.py
d8129b1f9bc74307e61c829e23ce4d4e825f8a466bb8d6062fb75cee7a4fb964  src/nostos/validation/local_orientation.py
2a47b1b03e22081b376972a97d1aabd7917d270dbbba69e945fa921d3ec01bcf  src/nostos/validation/local_orientation_external.py
2c4e215fe7895c2c1916a53ac8476c8899b0836d67884c49063997555defd3ec  src/nostos/validation/manuscript_qa.py
74e16c4479a6e5cb1c35246d70a2f3b1ab491627e8a815a3c4c429d1d759962e  src/nostos/validation/metrics.py
0bcc7dfc1a4132855b363b461697db6a842b99b5f43e7a476a92b0a34b9c5e8d  src/nostos/validation/module_perturbations.py
da56d5a920ebeaab3a3564fe8967c389b3d592c12b77923641bb9b57dec7fbb4  src/nostos/validation/osteochondral_interface.py
93f488a92f6ab46be4eba2b4796116f315274ffa8484c64dfca2897fa66c07e4  src/nostos/validation/perturbations.py
3dfc82b57fbe3af283dbd4f7a92bf35e4a9535bf77ac41af2bb0dcf0fec89327  src/nostos/validation/phantoms.py
8aed075cd3db10bfa400d41d1b95752f1cb8b450a5ea0b6d32c0566eddbe9ca7  src/nostos/validation/pshg_external_orientation.py
51d8af1676b6d46b300d8e55b90bdf98e9b252d03cdd4ba8b36b14fb56ad4280  src/nostos/validation/replication.py
52bed10f5c5e05cd91f0cb7e9da8f01527e82a13eb3bc96a8afdacf7fbce6cda  src/nostos/validation/response_geometry_benchmark_v2.py
3aafae848eca13549a014aaacbbd86c42ff398da28c3e172341a56808d9e32d4  src/nostos/validation/selective_fft_confirmation.py
080ace8bd3aa1d54b963ec43004720b5edf201c7f8e9c5a9168c785143d9c1b1  src/nostos/validation/selective_fft_development.py
5f61bb6f4e3191db628f934db9dd974628fed0c1673e14ab3cc218395b884dc2  src/nostos/validation/selective_filament_transfer.py
18d9ef33739471f54e14af535e5904e26b939bef2566723a1a512ab217afe966  src/nostos/validation/selective_shg_transfer.py
169dafb7ba0a7e0b6dbeec673fae23f470f22d29c111a36ad4341b503ecf7b25  src/nostos/validation/stability_weighting_development.py
331a6bb3a5db3256523224d13d78d1b4e07e91e3cbe1b41eb30cb8bfe30c0d9f  src/nostos/validation/uvpam_abstention.py
cdca30f8cf7ca528284790add6d8b359b1383c7a8f757846f74b255f7b78df07  storage.json
f65fe7a9c7526b7935ea5780842cf5c3647e0f012ed472d2860ed5d14c716624  tests/test_ablation_reporting.py
1b1e592bb72194b731050c81dbcd5502be5fd249f13c01b5787032c16850133c  tests/test_ablations.py
321ce1f85bece331c74812be1ca464371267f8544cbe92e133d21f6514857414  tests/test_adjacent_replication.py
40f9c28969429979b7d47bf9a5b2646acd46afe528568eb36aae3d512c7eaa39  tests/test_agreement.py
4d181e1df1cf4fb44286539fedf4ef4008e0225c47882cdcaefb805fd89fab61  tests/test_analysis_table.py
3e6fc2cd0e95a58f715917542f5dfe4438e70cca453039dd5881151d7701890b  tests/test_annotation_manifest.py
6672ecbc29c53936e25f67b48cf8b85c41cc14491d73a51c63a30f3087e8d18e  tests/test_app_generic.py
e8a1f33fa1e7e04e3997589dead56c3eb73cb343b203f5fd6ac30e37ab31f022  tests/test_archive.py
638d4a15cb51e34714391d573863648aa9468bf2116de5b5e23132a1c7236ef3  tests/test_audit_tiff.py
c667b75350fff7f14bf17d2f3b62b082a9d040c7a93607c3c4a31ec2c3ee7fdd  tests/test_baselines_and_tiles.py
f9031962cc060bfefd233fd877a1b6a432d024e0cd0b36383da7822442d3c8ec  tests/test_biological_retrieval.py
258026817f4b77e4823af0808d40e164ab6f8669252d2e87421be45974c3d4d3  tests/test_bone_contract_orientation.py
7012c1baf01eab0f07bf3865582728a0840e6548f89fb08eff6f11f94a3d0bc3  tests/test_bone_network_3d.py
bee80f1e31a40f3960bfc15a0cff5bebaec6d50def90490f11f9b051e12f0095  tests/test_bone_orientation_v2.py
06dd2a7f1ca164beaa204fade13c3e44b90fc0672cbe99b1da5a60df6fe1c741  tests/test_bone_program_summary.py
250a4fb102a1f2e96be0ef82b201d7f5b1f6e799d83df434d3497e67a09522bf  tests/test_canonical_confirmation_v3.py
a35452c9c82198ce07ccdb2984a712baf77ffd6cc1dd13df274fca5de6d1b101  tests/test_canonical_development.py
e2efc0ac4b1e4c7ff5cf9771a4fc49bda8f7905a2d4c7253d66e47c85fe87029  tests/test_canonical_geometry.py
309fe1b1356fd1d253b013490095b9e071e03e7d1e0f054cc57a0cce79b6c69d  tests/test_cartilage_ablation_analysis.py
2bb760a07f38c3c3c525e74459697abbc3e2fbc8f297142a9540173764922f6d  tests/test_cartilage_ablations.py
23b4b52fa1c71598387797681e8dc905df69022f646742eac612f70b325ab963  tests/test_cli.py
41e7f1167e8c4531ed3811c7551af872ea5a8dfec27c292a4be92e19add7fb31  tests/test_cohort_reporting.py
72ad6a50c4ab8002facfa9ea2269338e6a1b5ade4f358292873707d6b2133eb9  tests/test_comparator_conformance.py
5a7d4fc19528db6cdc63212c2c1df1b99825f2f0bbfde285f3953caf5fd34592  tests/test_comparators.py
292e5bc4a7b454be9a60da5ee44c032f2296091d0c51f5445d7753903371a55b  tests/test_consensus_reliability.py
1078d63b7ad92dd7c16da0685c420fc93023b7d642543f47b9e3bc4fdb5455bf  tests/test_cpu_pilot_statistics.py
bbcb7458add953e9f92d669728cf64d53059a1f4160ce9df64c73bc36483dfd6  tests/test_depth_atlas.py
5ecb6fd10e2e2c0967e7fe1498836a73d15d6be07f7c3027c0a615eeff092472  tests/test_depth_coordinate.py
1d51fa693a841a81696767462a17e2dc1d7584f33b51669d142fdb137727cd6e  tests/test_dynamic.py
d86e4dab7934c9de55b470ba58c26f8f2c4ee1696aa5b9eb027740b3682bb009  tests/test_evidence_bundle.py
4b2afc3eabd9a6979b202db019e2675a87b10f0d82443e5db8389514ca506d56  tests/test_external_bone.py
c4d15e02a82cdb617af96ced38ae4d21f5381cc882f9bafeaed36ccf49f606b3  tests/test_external_cartilage.py
7c0de1699334411c715465944033463b23cb3399403903e69d02856f5dfb3cbd  tests/test_external_filament.py
d1c46122baadbc0f5d46a7b1bfbe88705d342444ca0daff31fea0e5c15e9ed05  tests/test_external_nuclei_bbbc020.py
e1aa3f273168a264fb03e36e6ffbf00e98bd6aea210d8d12af031d3c6bbe79a3  tests/test_external_nuclei_confirmatory.py
08d501e2178b3195be76e1b3f29296ef44b60e11f67570fa3c50f65e137e71aa  tests/test_figure_provenance.py
ece6293ec5c438dcb6ad065849715df9c5f6a4415b44db9971f137fb693a4570  tests/test_final_audit.py
1e951e49f92f4b78a72e072d773ad3792c3085e4518069f7a1256ff92f2ee5d8  tests/test_grouped_ridge.py
3178ebbe0f63852e3ec25673ea1c083171da8577607e14daa26d73071bae9f90  tests/test_hessian_polarity.py
207b782389037fb063e77064fdb64ab152703f8739119d7016573c7d60f2b88e  tests/test_human_nanoct_scale_response.py
d4b5dd84c52166bb55ecbdfd6c29c455fb1253879870677d9b40141f5e75d36a  tests/test_human_nanoct_transfer.py
222fd01268892761c73a5d1ed648bd4b5c6a52482421727dd5f2f8e67d63a9cb  tests/test_ibsi_workbook_parser.py
76b24698004deee40e592ec339cacdb35de3320c5a434f81e47bf9ea9e29e1ca  tests/test_local_orientation.py
3427592b2ac5a57a245f77be232b0e1f0ce071e1c093219f521b11762880f282  tests/test_local_orientation_external.py
161fb96a267ca272d0e35e977623728dd9da9f8feb05d59e29f1eb4ffd41f509  tests/test_locked_analysis.py
719c8f322627e8ada2a863b83a3f591c16953fa06af65f949cb17a8943bdefc0  tests/test_manuscript_gates.py
16a4207368b28b263f10e3bcb7f519eb99d5aa212fae55eb7bd8495b5a1d45b1  tests/test_manuscript_qa.py
1b1ec590ad9b67d5a9a8efa885eb32d992e26b42aac7d4e20f64f912385e1324  tests/test_mask_uncertainty.py
cecbc0152e56c66a0738f48b1e37de69f386fb98c83e8b8aedea7bbecff1c8f6  tests/test_measure.py
d624a1b64c2e98c1d967148aeefdc2cf862c7949b92b5548490aff706b6bf193  tests/test_mechanistic_subscores.py
c5e3578994043525d8a83aaf61f4ced2d9b3d5e923855d41657e109636468118  tests/test_metadata.py
09bed5f58df9c67de3525a74e6948c53b33b13b9de6190d04710f092e2196f23  tests/test_module_perturbations.py
1ca07cd01da0ed556e987ad00adcfeec319dff92e610ef28b155b315a6be366c  tests/test_osteochondral_interface.py
a5281679df060948854e3898d2e316c278484349a551c8d262ca774069403e25  tests/test_osteochondral_learned.py
6b42899fa7910230529256912ae143887dd0afe8723d33e789e97b5aca1c9ea6  tests/test_osteochondral_reference_audit.py
83216649e494ea95477cf5f13bdd91860c6a8eb2f32c4e6626b45bca57be4891  tests/test_participant_evaluation.py
d022c72ea2a15fec6b7d63facfb0d70cc16239913f4481d4e60b1eee52f61448  tests/test_pipeline.py
b6978e59e01d8d3542e5f5b794f6696361e98e6444e8301e3e6ae1c4f8bf2857  tests/test_primary_reporting.py
ce2683d21e767fd4e88087422ca4b12d184d37aa3eda8f25de3e0e43691dceb3  tests/test_pseudo_labels.py
9ba1ad12ee292920cfda395830980f25cafca27402b33c0fb381df45ed6b5cd2  tests/test_pshg_external_orientation.py
c730b746ef13bcb9845407de81251bb276308cb1b1884af8b3194a910f8e93ae  tests/test_publication_bundle.py
f69dd7b5d26af7c41347d6f22ed13564e4dd47c9b41036e5d8026b4bee163f98  tests/test_qc.py
43af68e0047aa58bd55211ba133c2524db0d28aa2192d260ccc685722bab62b2  tests/test_reader_reliability.py
8f675a1ebaf509a9d8e664d139212cb9f02271b1c89dd0d13051764810e9bfc1  tests/test_release.py
c3584789c0866f972766b5d408c76a5c58a19854fec3e92376d23a8e23ee6c8a  tests/test_reliability.py
6ae19d78c5b0159cf079568cda37623ae54ca535a0c4b08b1eea20c5f7532c3c  tests/test_replication.py
8d70757d469bcc38441ed1e31da31cfd85cb2e0729fddb79728239e34e454f65  tests/test_response_geometry.py
7f5069edbb31d8e5a2ba01439bf1bc31d84af1d3b11bde9c9791c2ecd456f873  tests/test_response_geometry_benchmark_v2.py
202b37c8bad61916fc5f3564dff7fe4512f0a07fed00e7a71da10faa5952d265  tests/test_response_modules.py
6dca4bf6c0e7bce50abcce8fa734ab14f98843c246cea74a90a396024504b979  tests/test_review_evaluate.py
d6bbf30775f4c44aa4d82c96fa5be87786efaa083675c6e66dd7d06956b90fa6  tests/test_review_packet.py
00a245424b1ecdc1cfdb3d15ef72d60b7131898bf35f0a147fa09cd58eea3b33  tests/test_robustness.py
048bc6457c93fb0748b0f1002dc16bd048c1aa3c7d8635b58641da45539d1443  tests/test_section_features.py
cb812ea5332d313e7b018eb78dbc7ba2359745fc2ec57fbdf7f494130af00501  tests/test_segmentation_dataset.py
4ffe32d4d5f995bad33389657e4cf2f548e28b5c8248084dd3e02f94bab22f15  tests/test_segmentation_metrics.py
3ba05f787d09e5f4add9d713c48d27ff3ac13dba0b562a9cb0806993df51250e  tests/test_segmentation_model.py
9a491b2299081c9145f6a9acb8e023677deaddb29fce3767b70fee9b6dbad590  tests/test_segmentation_prepare.py
b062cbedfa2d3045ff53f23836861010eb546dbe9ac5d780747097d0dfd77870  tests/test_segmentation_reporting.py
a634b3babc31224fecb95e9c0b45c97f40fc462836d35011ba480b826bd7a9a0  tests/test_select_annotations.py
ff7d70f235130ca2b856febbcc2a3e8262d924909e5bb3c580c149c88e0bc93f  tests/test_selective_fft_confirmation.py
eaec0c97374e8490d14d07adf95cad1cb6a1200786fd7f6df7b3f51c0b74b3a0  tests/test_selective_fft_development.py
65fdb7e38e1b43420ae3bb24d5ddb72a409c1046af93621b2e16182f7c956ddb  tests/test_selective_filament_transfer.py
6e7e2149a04b997b8fc5acb7da6aa9b67b63ab0bc238733c4d0afc0a5b8eb569  tests/test_selective_shg_transfer.py
862997761b951021ccf1914de6b1705db62653de375343ae4aaac9925f095c8e  tests/test_severity_benchmark.py
8b25a41deca6a163daf12c931377be6c11ef9cedc8465b5d22a19d0786792486  tests/test_spatial_fft.py
c6c52233af73603a393f3b7a4b5724a99f389a9c431aaa748cd10d01e20688e3  tests/test_split.py
dc7e511f7a95320ca35be84e802cbd4a9dd4d74b0b49dd08feb8241d8d4fd36f  tests/test_stability_weighting.py
36409b523a24d9d6fbede8a9c04676dd4875aba7c59a6a89c85e2f862b7bf3a1  tests/test_stability_weighting_development.py
74a8d8f0c43f5b51b8e1d4db6137138f7cb8e7c2a2cdd1f049c28cd0a4895f5d  tests/test_synthetic_validation.py
056524dd874d4c7ea015c689cd163928c0d535c71285ed0be4ebd47214f32722  tests/test_tracking.py
77d3ae15cf5b954ebe0e373ecac7735b1a42f37eaddf7032f7db5705edb302e9  tests/test_universal_geometry.py
41319890a571ef48f930892ce10574fd2ab8e9c7803d0c9f5aa394e37058bca4  tests/test_uvpam_abstention.py
cffd49ce15d4f512e3d6e1666d93f0eca67e3312634f51f47c16959387e427e2  tests/test_version.py
cc91dba77dff072d4f841e6e1364ebf312284434875669fe10ca44dd31d7733a  tests/test_weak_labels.py
cf83c4d5fb0c5437265f026166b132202b34ae8694630d1519b1efe2e7bb308b  tests/test_zsd.py
```

## Integrity check

Recompute any entry with `Get-FileHash -Algorithm SHA256 PATH`. A mismatch means the repository changed after this audit package was generated and the automated evidence above must be rerun.
