"""Build the evidence-corrected Small Methods v35 submission manuscript."""

from __future__ import annotations

import re
from pathlib import Path

import build_nostos0_methods_docx as base
import build_nostos0_small_methods_docx_v34 as v34


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V35.md"
OUTPUT = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_ready_v35.docx"
FIGURE_DIR = ROOT / "figures" / "nostos0_small_methods_v35"
TITLE = "NOSTOS Exposes and Contains Acquisition-, Scale- and Sample-Specific Failure in Quantitative Microscopy"

ABSTRACT = (
    "Quantitative microscopy software often reports a value whenever an algorithm can run, although the image may not support the requested measurement. "
    "NOSTOS couples continuous image estimators to executable, input-only validity profiles that preserve calibration, support and abstention. On eight untouched BioSR fields, a frozen profile retained 95.0% of eligible tensor-coherence measurements while reducing silent-invalid risk from 0.0735 to 0.0387. "
    "FMD then provided a prospective falsification: after four fields showed no error, a seven-field extension produced six invalid emissions among 110, confined to one acquisition-by-scale cell. A conservative three-cell profile had zero observed errors across 19 development fields but failed no-refit transfer: confocal mitochondria yielded zero coverage, whereas widefield F-actin retained 36 invalid outputs among 84. "
    "A post-failure claim-boundary guard preserved all in-scope decisions and blocked both mismatched domains; this is engineering containment, not transfer confirmation. In unstained PSHG tissue, NOSTOS retained 7 invalid outputs versus 47 for acquisition quality control at matched coverage. An independent tendon archive showed strong single-image recovery of polarization-derived organization (Spearman ρ = 0.891) while failed coverage gates remained explicit. NOSTOS makes measurement scope and failure history executable rather than implicit."
)

TOC_TEXT = (
    "NOSTOS turns microscopy validity into an executable decision. A prospective seven-field extension falsified an apparently safe profile, and no-refit application to confocal mitochondria and widefield F-actin failed. The framework preserves these failures, narrows support and enforces profile claim boundaries before emission, while BioSR and label-free SHG studies show when selective structural measurement remains supported."
)

FMD_RESULTS = """### 2.2. Prospective FMD extensions define the measurement boundary

The FMD archive offered a harder test because it contains repeated real fluorescence acquisitions from commercial confocal, two-photon and widefield microscopes[10,11]. Images formed from one, two, four, eight or sixteen captures can be compared with an average-of-fifty reference from the same field. Repeated captures were nested technical observations and field of view was the independent unit. Pixel spacing is absent; all requested scales remain in pixels.

The first cross-modality profile passed its aggregate gates but failed its post-confirmation stratified audit: accepted confocal and two-photon measurements contained no error, whereas 20 of 48 accepted widefield values were invalid. A widefield-only v1.3 profile subsequently passed pooled confirmation on four untouched fields, but every accepted error again occupied one average-of-8 by 8-pixel tensor-coherence cell. The cell failed in development and confirmation even though the pooled risk passed. These failures motivated conditional support over declared capture level and requested scale.

A v1.4 conditional profile retained average-of-16 measurements at 4, 8 and 16 pixels and average-of-8 measurements at 16 pixels. On four new fields it emitted 64 values with no observed error. That result was technically correct but statistically weak: the exact two-sided upper 95% limit for a field with any accepted failure was 0.602. We therefore froze a seven-field extension before decoding the remaining non-excluded fields.

**[Figure 3 near here: FMD acquisition ladder, seven-field extension errors, four-cell failure, conservative three-cell repair and independent-field uncertainty.]**

The extension falsified the apparent repair. It emitted 110 of 420 eligible primary values and retained six invalid outputs. All six belonged to the average-of-8 by 16-pixel cell; two occurred in field 3 and four in field 4. Thus two of seven independent fields contained an accepted failure, with an exact two-sided 95% interval of 0.0367–0.7096. The inherited v1.4 audit failed even though the pooled risk was only 0.0545. Across the eleven v1.4 and v1.5 confirmation fields, the profile retained six errors among 174 accepted values and two field-level events; the exact upper field bound remained 0.518.

No WideField_BPAE_R field remained sealed after this test. All nineteen non-excluded fields were therefore reclassified as post-failure development. A conservative v1.6 compiler retained a cell only if it emitted across all nineteen fields, contained no accepted error, produced no field-level event and had an exact field-event upper 95% bound no greater than 0.20. Only the three average-of-16 cells survived. They emitted 228 of 1,140 eligible development values without observed error. The exact field-event upper bound was 0.176 for each cell. This is a narrowed development profile, not another confirmation.

We next tested the three-cell profile without refitting on two unopened FMD archives. Confocal_BPAE_R retained the mitochondrial channel but changed microscope; WideField_BPAE_G retained the microscope but changed the imaged structure to F-actin. Seven hash-selected fields and four repeated realizations per capture level were frozen for each source before image decoding.

**[Figure 4 near here: authentic certified and external FMD images, deterministic coherence fields, per-field transfer failures and executable claim-boundary containment.]**

The no-refit transfer failed in different ways. Every eligible confocal primary row hard-abstained, yielding zero coverage. Widefield F-actin exposed a more serious error: all three supported average-of-16 cells emitted, but 36 of 84 accepted values were invalid. Each requested scale retained 12 errors among 28 values. Fields 1, 11 and 5 failed in every accepted repeat, whereas the other four fields contained no accepted error. The field-event rate was 3/7 (exact 95% interval 0.099–0.816). Combined transfer risk was 36/84, and every prospective gate was preserved as failed.

This experiment fixes the interpretation of a NOSTOS profile. The estimator may be sample agnostic, but its validity profile is not. A post-failure software repair now makes the certified context executable: acquisition modality, sample/channel identity and calibration state must be present and exactly match the profile before its support lattice can run. Applied retrospectively for engineering verification, the guard preserved all 1,140 in-scope development decisions, including 228 emissions, and blocked all 840 external primary rows. The widefield F-actin errors fell from 36 among 84 emissions to zero emissions, not to a claimed zero-risk measurement. Because the guard was added after transfer labels were known, this is containment of a demonstrated failure rather than prospective evidence of broader transfer.

The FMD lineage is the methodological result: pooled performance concealed modality failure; a small confirmation missed a second acquisition-by-scale failure; a larger prospective extension exposed it; and a cross-domain transfer showed that even a conservative lattice cannot outrun its declared sample domain. NOSTOS therefore serializes not only a threshold, but also the domain in which that threshold is permitted to act.
"""

HIERARCHICAL_METHODS = """### 4.4. Hierarchical conditional support and claim boundary

The conditional compiler consumes an immutable base profile and rows already scored by that profile. Cell dimensions are declared in the protocol and may draw from acquisition metadata or requested measurement coordinates. A cell is supported only when it satisfies minimum accepted-case and independent-group counts together with prespecified risk and uncertainty limits. Deployment requires the conjunction of no hard abstention, calibrated risk at or below the base threshold and membership in the supported-cell set.

The v1.4 FMD table used capture level and requested tensor scale. The later v1.6 post-failure compiler required accepted observations from all nineteen non-excluded WideField_BPAE_R fields, zero accepted errors, zero fields with any accepted failure and an exact two-sided field-event upper 95% bound no greater than 0.20. This retained only average-of-16 at 4, 8 and 16 pixels. The compiler status remains development because all in-domain fields had been opened.

Profile deployment now begins with an exact claim-boundary guard. The required context fields are serialized with the profile. For the FMD v1.6 profile they are acquisition modality, sample/channel identifier and calibration status. A missing or unequal field produces a hard abstention before the acquisition-by-scale lattice is evaluated. The guard never infers tissue identity from pixels and does not convert an out-of-domain image into an in-domain measurement.
"""

FMD_SOURCE_METHODS = """### 4.7. FMD source, selection and failure-preserving splits

FMD was obtained from the University of Notre Dame repository (DOI 10.7274/r0-ed2r-4052)[10,11]. The in-domain archive was `WideField_BPAE_R.tar` (709,232,640 bytes; SHA-256 `4914cd7d951b4ddc1a01f6c7f121b7e9936fd2a7d1505f3e802984ffee69cad7`). FOV 19 was excluded because it supplied an earlier exploratory subset. Fields were ordered by SHA-256 of a frozen seed, archive identity and field identifier. V1.3 used fields 7, 15, 13 and 9 for development and 16, 17, 18 and 11 for confirmation. V1.4 used fields 20, 14, 5 and 1 for confirmation. The v1.5 extension used fields 3, 12, 6, 8, 4, 2 and 10. Once v1.5 was opened, all nineteen non-excluded fields were available only for v1.6 development.

Within each selected field, realization indices 0–49 were ordered by a second frozen hash rule and the first four were used at every acquisition level. Each pair was evaluated at 4, 8 and 16 pixels for tensor orientation, tensor coherence, spectral anisotropy and spectral entropy. The primary family was tensor coherence. Archive member identities were indexed before pixel decoding and every evidence row retained its member checksum.

The external archives were `Confocal_BPAE_R.tar` (627,537,920 bytes; SHA-256 `9b36bb4df24ae81947d6829b1e7ae33c31eb03430614f0de7a3382034f3f81d2`) and `WideField_BPAE_G.tar` (792,780,800 bytes; SHA-256 `019863658ab0ba45c2b323ef787bad2ed40b017c0cdcfae66eb7818eaf9bdeee`). The frozen seed selected seven fields per source and four realizations per field and level, yielding 280 paired acquisitions and 2,240 endpoint rows. Both archive hashes, the selected members, code and profile identities were locked before measurement output directories existed.
"""

FMD_MEASUREMENT_METHODS = """### 4.8. FMD measurement, invalidity and exact field audit

Input levels were raw, average-of-2, average-of-4, average-of-8 and average-of-16; `avg50.png` was the reference. The primary input-only score was max(0, sqrt(16/n) − 1) plus measured perturbation instability, where n is the declared number of independent captures. Capture count is a deployment precondition. The frozen base threshold was 0.6303073201.

Reference orientation was eligible only with sufficient resultant and spectral anisotropy, agreement between estimators and stable reference probes. Tensor coherence was invalid when absolute error relative to the average-of-50 reference exceeded 0.15. FMD provides no pixel calibration; requested scales cannot be converted to micrometres.

The v1.5 extension audit evaluated accepted emissions within each independent field and reported exact two-sided Clopper–Pearson intervals for the probability that a field contained any accepted failure. The v1.6 cell compiler used the same field-event definition. Nested row-level exact intervals were retained only as descriptive summaries.
"""

FMD_TRANSFER_METHODS = """### 4.9. FMD external transfer, audit repair and domain guard

The no-refit v1.6 transfer applied the byte-identical base threshold and three supported cells to Confocal_BPAE_R and WideField_BPAE_G. The source-specific gates required seven independent fields, zero invalid accepted emissions, zero fields with an accepted failure and presence of all three cells in every field. The combined gate required fourteen fields and an exact field-event upper 95% bound no greater than 0.25. Ordinary acquisition QC and tied-score risk–coverage comparators were inherited unchanged.

The measurement runner completed and serialized 2,240 rows with SHA-256 `2309b23dcf6facf9fc5406e571cc94c277822cd055fac0e3f3de912539672e39`. The first audit invocation then stopped before writing output because the exact row-level interval helper did not define the zero-accepted branch encountered for confocal images. A versioned audit-only repair serialized risk and its descriptive row interval as null when accepted count was zero. It changed no row, source, measurement, invalidity label, profile, support cell, threshold, comparator or gate. The repair was locked against the immutable row hash before the formal audit was rerun. Its audit SHA-256 is `22cee916adc25a3d50e798f3daf6e6cee8938f75e1ff41f01114a22159ad175b`.

The post-failure domain guard compared declared acquisition modality, sample/channel and calibration status with the certified context. Missing or mismatched values forced hard abstention and risk 1.0 before the support lattice. Development verification required identical decisions for all in-scope rows and rejection of every known external row. This verification used already opened transfer labels and is reported only as engineering development.
"""

CONCLUSION = """## 3. Conclusion

NOSTOS makes the scope of a quantitative microscopy measurement executable. BioSR and unstained SHG studies show that input-only validity profiles can remove disproportionately invalid measurements while retaining useful structural information. The FMD lineage defines the limit just as clearly: pooled statistics concealed failures, four apparently clean fields did not establish a cell, a seven-field extension falsified it and an external structural channel failed despite conservative acquisition-by-scale support. The resulting profile was narrowed, and the software now refuses mismatched declared domains before measurement support is evaluated. That guard is containment, not evidence of transfer.

The framework therefore does not promise one universal score or one universal biological meaning. It couples a measurement to its coordinates, certified acquisition and sample context, uncertainty, provenance and complete failure history. That is a smaller claim than unrestricted generalization, but it is the claim required for quantitative microscopy software to fail visibly rather than return a plausible unsupported number.
"""

FIGURE3_LEGEND = (
    "**Figure 3. Prospective extension falsifies the apparent FMD repair.** "
    "**a,** One authentic widefield mitochondrial field from a raw capture through average-of-50 reference; FMD remains pixel-relative. "
    "**b,** Absolute tensor-coherence errors for all 26 accepted average-of-8 by 16-pixel measurements in seven untouched fields; red values exceed the frozen 0.15 tolerance. "
    "**c,** The failed four-cell v1.5 support lattice and the conservative three-cell v1.6 development repair. "
    "**d,** Two of seven extension fields contained an accepted failure; bars show the exact two-sided 95% interval. "
    "**e,** Nineteen in-domain development fields had no event under the three-cell profile; the exact upper 95% field bound was 17.6%. Panel e is post-failure development, not confirmation."
)

FIGURE4_LEGEND = (
    "**Figure 4. Acquisition-by-scale support does not transfer across an undeclared sample domain.** "
    "**a,** Authentic average-of-16 widefield mitochondrial, confocal mitochondrial and widefield F-actin images with deterministic local coherence fields on a common 0–1 display scale. "
    "**b,** Field-level no-refit results: crosses denote zero accepted measurements; colored points show risk among 12 accepted values. Three of seven widefield F-actin fields failed in every accepted repeat. "
    "**c,** Across both external sources, the unscoped profile emitted 84 values and retained 36 invalid outputs; the post-failure claim-boundary guard emitted none. "
    "**d,** Executable context match for acquisition modality, sample/channel and output permission. The guard result is engineering containment after failure and is not prospective transfer confirmation."
)


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w–-]+\b", text))


def replace_section(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.escape(start) + r".*?(?=" + re.escape(end) + r")"
    updated, count = re.subn(pattern, replacement.rstrip() + "\n\n", text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"Could not replace section beginning {start!r}")
    return updated


def build_source() -> Path:
    if word_count(ABSTRACT) > 200:
        raise RuntimeError(f"Abstract exceeds 200 words: {word_count(ABSTRACT)}")
    if not 50 <= word_count(TOC_TEXT) <= 60:
        raise RuntimeError(f"ToC text must contain 50–60 words: {word_count(TOC_TEXT)}")
    text = v34.SOURCE.read_text(encoding="utf-8")
    text = re.sub(r"^# .+$", f"# {TITLE}", text, count=1, flags=re.M)
    text = replace_section(text, "## Abstract", "## 1. Introduction", "## Abstract\n\n" + ABSTRACT)
    text = text.replace(
        "The measurement engine currently exposes spectral organization, structure tensors,",
        "The estimator library is sample agnostic, whereas each validity profile remains bounded to its certified acquisition and sample context. The measurement engine currently exposes spectral organization, structure tensors,",
        1,
    )
    text = replace_section(text, "### 2.2. Hidden FMD failure and hierarchical repair", "### 2.3. Selective validity in unstained PSHG tissue", FMD_RESULTS)
    text = replace_section(text, "## 3. Conclusion", "## 4. Experimental Section", CONCLUSION)
    text = replace_section(text, "### 4.4. Hierarchical conditional support", "### 4.5. Confirmation statistics", HIERARCHICAL_METHODS)
    text = replace_section(text, "### 4.7. FMD source and selection", "### 4.8. FMD measurement and score", FMD_SOURCE_METHODS)
    text = replace_section(text, "### 4.8. FMD measurement and score", "### 4.9. PSHG acquisition-shift confirmation", FMD_MEASUREMENT_METHODS + "\n\n" + FMD_TRANSFER_METHODS)
    text = text.replace("### 4.12. Synthetic and supplementary estimator validation", "### 4.13. Synthetic and supplementary estimator validation", 1)
    text = text.replace("### 4.11. Failure lineage and terminal audit", "### 4.12. Failure lineage and terminal audit", 1)
    text = text.replace("### 4.10. Tendon pSHG-XRD transfer", "### 4.11. Tendon pSHG-XRD transfer", 1)
    text = text.replace("### 4.9. PSHG acquisition-shift confirmation", "### 4.10. PSHG acquisition-shift confirmation", 1)
    text = text.replace(
        "The v1.4 terminal audit used a code path separate from the analysis scripts to",
        "The v1.4 terminal audit used a code path separate from the analysis scripts to",
        1,
    )
    text = text.replace(
        "Seventeen of seventeen checks passed.",
        "Seventeen of seventeen checks passed. The later v1.5 and v1.6 failures, the v1.6.1 zero-coverage audit repair and the v1.7 post-failure domain guard are preserved in separate immutable output directories. No failed status was overwritten or converted to a pass.",
        1,
    )
    text = re.sub(
        r"\*\*Figure 3\..*?(?=\n\n\*\*Figure 4\.)",
        FIGURE3_LEGEND,
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r"\*\*Figure 4\..*?(?=\n\n\*\*Figure 5\.)",
        FIGURE4_LEGEND,
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r"## Table of Contents\n\n.*?(?=\n\n\*\*\[Graphical abstract near here\]\*\*)",
        "## Table of Contents\n\n" + TOC_TEXT,
        text,
        count=1,
        flags=re.S,
    )
    required = (
        "six invalid outputs",
        "36 of 84",
        "zero coverage",
        "post-failure claim-boundary guard",
        "### 4.9. FMD external transfer, audit repair and domain guard",
        "Panel e is post-failure development, not confirmation",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(f"v35 evidence correction failed: {missing}")
    SOURCE.write_text(text, encoding="utf-8")
    return SOURCE


def configure_builder() -> None:
    v34.configure_builder()
    base.FIGURES.update(
        {
            "Figure 1 near here": FIGURE_DIR / "figure_1_measurement_to_decision.png",
            "Figure 2 near here": FIGURE_DIR / "figure_2_biosr_confirmation.png",
            "Figure 3 near here": FIGURE_DIR / "figure_3_failure_extension_and_repair.png",
            "Figure 4 near here": FIGURE_DIR / "figure_4_external_scope_failure.png",
            "Graphical abstract near here": FIGURE_DIR / "nostos_small_methods_toc.png",
        }
    )
    base.FIGURE_ALT.update(
        {
            "Figure 3": "Authentic FMD acquisition ladder, accepted errors in seven untouched fields, failed four-cell support, conservative three-cell development repair and field-level exact uncertainty.",
            "Figure 4": "Authentic certified and external FMD images with coherence fields, failed no-refit transfer by field and post-failure exact claim-boundary containment.",
        }
    )
    base.FIGURE_WIDTHS.update({"Figure 3": 6.25, "Figure 4": 6.25})
    base.DOC_TITLE = TITLE
    base.DOC_SUBJECT = "Small Methods evidence-corrected submission-ready candidate v35; computation-only public-data validation"
    base.DOC_KEYWORDS = "quantitative microscopy; measurement validity; selective prediction; abstention; domain applicability; second harmonic generation; reproducible software"


def main() -> None:
    source = build_source()
    configure_builder()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    missing = [str(path) for path in base.FIGURES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(missing)
    print(base.build(source, OUTPUT))
    print(f"abstract_words={word_count(ABSTRACT)}")
    print(f"toc_words={word_count(TOC_TEXT)}")


if __name__ == "__main__":
    main()

