"""Build Small Methods v33 with the sealed tendon pSHG transfer experiment."""

from __future__ import annotations

import re
from pathlib import Path

import build_nostos0_methods_docx as base
import build_nostos0_small_methods_docx_v32 as v32


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "NOSTOS_SMALL_METHODS_ARTICLE_V33.md"
OUTPUT = ROOT / "manuscripts" / "NOSTOS_Small_Methods_submission_candidate_v33.docx"
TLT_FIGURE = ROOT / "figures" / "nostos0_tlt_pshg_xrd_transfer" / "figure_tlt_pshg_xrd_transfer.png"

ABSTRACT = (
    "Quantitative microscopy software often reports a value whenever an algorithm can run, although image sampling may not support the requested measurement. "
    "NOSTOS compiles paired acquisition–reference data into input-only validity profiles for continuous measurements. On eight untouched BioSR fields, a frozen "
    "profile retained 95.0% of eligible tensor-coherence measurements while reducing silent-invalid risk from 0.0735 to 0.0387. In the Fluorescence Microscopy "
    "Denoising archive, pooled validation concealed a condition in which every emitted measurement was invalid; hierarchical support removed it on four new fields. "
    "In unstained PSHG-TISS, NOSTOS retained 7 invalid outputs versus 47 for acquisition quality control and 24 for endpoint quality control at matched 63.9% coverage. "
    "A sealed, independently acquired tendon pSHG archive then tested single-image structural recovery. Across 37 untouched fields, NOSTOS coherence from one mean "
    "SHG image correlated with withheld polarization-derived organization (Spearman ρ=0.891; specimen values 0.904 and 0.842). Under 592 programmed cases, NOSTOS "
    "retained 2 invalid outputs among 229 versus 86 and 26 for the comparators. Preregistered coverage and clean-preservation gates were missed, so the experiment "
    "remains a qualified failure rather than a converted pass. NOSTOS makes support, abstention and failure history executable without assigning universal biological meaning."
)

TOC_TEXT = (
    "NOSTOS turns quantitative microscopy outputs into measurements that can refuse unsupported input. In a sealed second SHG acquisition family, one intensity image "
    "recovered polarization-derived collagen organization across two specimens. At matched coverage, invalid outputs fell from 86 under acquisition quality control and "
    "26 under endpoint quality control to two, while missed preregistered coverage gates remained explicit."
)

TLT_RESULTS = """### Single-image structure transfers to an independent tendon pSHG acquisition

We next asked whether the orientation contract and an interpretable structural coordinate transferred beyond PSHG-TISS. A separate public study deposited mean SHG intensity, polarization-derived orientation (`Phi2`) and organization (`I2`) maps from non-mineralizing, early-mineralizing and late-mineralizing turkey leg tendon, together with synchrotron X-ray measurements of collagen hierarchy[31,32]. Each 512 × 512-pixel field spans 384.5 × 384.5 µm. Only the mean SHG intensity image entered NOSTOS; `Phi2`, `I2`, zone identity and X-ray measurements were unavailable to the support decision.

The four specimens were separated before array inspection by a deterministic SHA-256 rule. Samples 1 and 3 supplied 36 development fields, while Samples 2 and 4 remained sealed. Development selected a log-intensity transform, a 12 µm primary tensor scale, a 6 µm scale-consistency comparator and zero coordinate offset. An initial smoothed-gradient disagreement component worsened development risk–coverage area and was rejected before confirmation. The locked contract retained acquisition QC, local coherence and physical-scale consistency. Sixteen clean and programmed blur, noise, resampling, contrast and compound conditions were fixed. A field-condition case was invalid when its median axial error exceeded 20° or its 75th-percentile error exceeded 35°.

The sealed confirmation contained 37 fields and 592 cases, of which 273 were invalid. The contract accepted 229 cases and retained 2 invalid outputs (0.87% risk). At the nearest complete tied-score groups with the same 229 cases, acquisition QC retained 86 invalid outputs (37.55%) and endpoint QC retained 26 (11.35%). Absolute risk reductions were 36.68 and 10.48 percentage points. Specimen-bootstrap intervals were 18.35–47.50 and 5.83–10.48 percentage points; with two independent specimens these are descriptive, not population inference. Tied-score risk–coverage areas were 0.4004, 0.1845 and 0.1607, respectively. Removing scale consistency worsened area by 0.0238.

The clean images supplied a second, distinct test. NOSTOS median coherence from one mean SHG image correlated with the withheld polarization-derived `I2` organization value across 37 fields (Spearman ρ=0.891). Correlations were 0.904 and 0.842 in the two sealed specimens. Mean coherence increased from 0.287 in non-mineralizing Sample2 fields to 0.609 and 0.708 in early- and late-mineralizing fields; Sample4 values were 0.421, 0.446 and 0.734. Deposited `I2` changed in the same direction. Thus a scale-declared single-image coordinate recovered substantial information normally derived from a twelve-angle polarization series.

The experiment did not pass every preregistered gate. Coverage was 38.68%, below the frozen 40% requirement, and 59.46% of clean fields were retained, below the 70% requirement. Accepted clean fields nevertheless had 12.12° median field error, and full-contract risk was 1.67% in Sample2 and zero in Sample4. No threshold was changed after unsealing. An independent code path reconstructed all decisions, tied-score analyses, organization correlations and 5,000 specimen bootstraps; 22 of 22 audit checks passed. The result is therefore a qualified second-acquisition-family confirmation: strong measurement and selective-risk evidence accompanied by explicit deployment coverage failure, not a validated replacement for pSHG.

**[Figure 6 near here: authentic tendon SHG, NOSTOS and pSHG maps, organization recovery, matched invalid outputs and tied-score risk–coverage curves.]**
"""

TLT_METHODS = """### Tendon pSHG-XRD transfer

The tendon resource and associated study are available at Zenodo DOI 10.5281/zenodo.10979115 and publication DOI 10.1098/rsfs.2023.0046[31,32]. Four specimens contain aligned 512 × 512-pixel mean SHG, thresholded `Phi2` orientation and thresholded `I2` organization maps from three mineralization zones. The field of view gives 0.75098 µm pixel spacing. SHA-256 ordering of specimen identity under the fixed salt assigned Samples 3 and 1 to development and Samples 2 and 4 to confirmation. All zones and fields from a specimen remained together. Repository byte counts and MD5 checksums were verified before opening confirmation arrays.

The single-image estimator applied `log1p` to nonnegative SHG intensity and computed local axial structure tensors at 12 and 6 µm integration scales. A 16-pixel edge was excluded. Input support was defined from finite intensity and the twentieth percentile of positive pixels; at least 10,000 pixels were required. Deposited finite `Phi2` pixels defined adjudicable reference support only and never entered eligibility. The full support score was the maximum of normalized acquisition-QC, minimum-coherence and interscale-disagreement components, with an emission cutoff of 0.40.

The 16 conditions were clean input; Gaussian blur at 1, 2, 4 and 8 pixels; additive noise at 30, 20, 10 and 5 dB; downsample-and-restore factors 2, 4 and 8; contrast factors 0.5 and 0.25; and moderate and severe compound degradations. Noise seeds were derived from field identity, condition and the frozen seed. Comparators used the identical orientation estimator with acquisition QC alone or acquisition QC plus coherence. Matching retained complete tied-score groups nearest to the full-contract count. Risk–coverage curves never split ties.

Organization recovery was evaluated once on clean confirmation fields. NOSTOS median local coherence was calculated on input-derived support, whereas mean deposited `I2` was calculated independently on finite reference support. Spearman correlation was evaluated pooled and separately in each specimen. Bootstrap draws resampled the two specimens with all nested fields and conditions retained. Because the independent sample count is two, these intervals are explicitly descriptive. The hash lock froze 12 gates, including coverage, matched risk reduction, scale ablation, clean preservation, within-specimen risk, organization correlation and label blindness, before the six confirmation files were downloaded. The independent audit reimplemented source verification, invalidity, policy scores, tied selection, risk–coverage area, correlation and bootstrap calculations without importing the production summary functions.
"""

FIGURE6_LEGEND = (
    "**Figure 6 | A single SHG image recovers polarization-derived collagen structure in a sealed second acquisition family.** "
    "**a,** Deposited mean SHG intensity from the SHA-256-first confirmation field; the scale bar is 100 µm. **b,** NOSTOS 12 µm local axial orientation from that single image. "
    "**c,** Withheld pSHG `Phi2` orientation. **d,** Pixelwise axial error on common support. **e,** NOSTOS local coherence. **f,** Withheld pSHG `I2` organization. "
    "**g,** Field-level NOSTOS coherence versus pSHG `I2` across all 37 untouched clean fields; colors denote mineralization zones and marker shapes denote the two specimens. "
    "**h,** Invalid outputs among complete tied-score groups nearest to the same 229 accepted cases: 86 for acquisition quality control, 26 for endpoint quality control and 2 for NOSTOS. "
    "**i,** Tied-score risk–coverage curves over 592 programmed cases; the vertical line marks NOSTOS coverage. The preregistered overall status remains fail because coverage was "
    "38.68% versus the 40% gate and clean-field retention was 59.46% versus the 70% gate."
)


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w–-]+\b", text))


def build_source() -> Path:
    if word_count(ABSTRACT) > 200:
        raise RuntimeError(f"Small Methods abstract exceeds 200 words: {word_count(ABSTRACT)}")
    if not 50 <= word_count(TOC_TEXT) <= 60:
        raise RuntimeError(f"Table-of-contents text must contain 50–60 words: {word_count(TOC_TEXT)}")
    text = v32.SOURCE.read_text(encoding="utf-8")
    abstract_start = text.index("## Abstract")
    intro_start = text.index("## Introduction")
    text = text[:abstract_start] + "## Abstract\n\n" + ABSTRACT + "\n\n" + text[intro_start:]
    text = text.replace("### The software preserves failure as part of the result", TLT_RESULTS.rstrip() + "\n\n### The software preserves failure as part of the result", 1)
    text = text.replace("### Failure lineage and terminal audit", TLT_METHODS.rstrip() + "\n\n### Failure lineage and terminal audit", 1)
    text = text.replace(
        "The PSHG challenge then tested the same governing idea on unstained tissue: a physically adjudicated local orientation field failed under controlled acquisition shifts, and an input-only contract removed most invalid outputs without inspecting the reference.",
        "The PSHG-TISS challenge then tested the same governing idea on unstained tissue: a physically adjudicated local orientation field failed under controlled acquisition shifts, and an input-only contract removed most invalid outputs without inspecting the reference. A sealed tendon resource extended the test to a separately acquired pSHG family and a tangible structural endpoint. One mean SHG image recovered polarization-derived collagen organization in both untouched specimens, while the same contract sharply reduced invalid orientation outputs. The missed coverage gates remain equally important: they delimit deployment even when accepted-case accuracy is excellent.",
        1,
    )
    text = text.replace(
        "The PSHG result uses programmed shifts in previously characterized tissue from one microscope family; it is not a second-instrument or prospectively acquired degradation series. These boundaries are stated in the serialized profiles and must travel with any output.",
        "The PSHG-TISS result uses programmed shifts in one microscope family. The tendon resource is independently acquired and provides a second pSHG family, but confirmation contains only two specimens and its degradations are still computational. The tendon contract missed its frozen coverage and clean-preservation gates. The organization correlation is therefore evidence that a single-image coordinate contains polarization-related structural information, not proof that NOSTOS can replace pSHG, infer mechanics or generalize to an unseen instrument population. These boundaries are stated in the serialized profiles and must travel with every output.",
        1,
    )
    text = text.replace(
        "NOSTOS makes the validity of a requested quantitative microscopy measurement an executable, versioned decision rather than an assumption. Across three public resources, the framework reduced silent-invalid outputs, exposed a pooled pass that concealed deterministic subgroup failure, removed that failure on untouched fields and transferred the selective-validity test to unstained PSHG tissue. The result is a practical fail-closed layer bounded to the acquisitions, instruments and measurement coordinates on which each profile was established.",
        "NOSTOS makes the validity of a requested quantitative microscopy measurement an executable, versioned decision rather than an assumption. Across four public resources, the framework reduced silent-invalid outputs, exposed a pooled pass that concealed deterministic subgroup failure, removed that failure on untouched fields and transferred a scale-declared structural measurement across two unstained pSHG acquisition families. In the second family, a single SHG intensity image recovered polarization-derived collagen organization while the preregistered coverage miss remained visible. NOSTOS is therefore a practical fail-closed measurement layer, bounded to the acquisitions, instruments and coordinates on which each profile was established.",
        1,
    )
    text = re.sub(
        r"The evidence bundle currently indexes 112 required receipts with no\s+missing entry\.",
        "The evidence bundle indexes every required receipt with a checksum and no missing entry.",
        text,
        count=1,
    )
    text = text.replace("PSHG-TISS is available at DOI 10.17605/OSF.IO/UDTQP.", "PSHG-TISS is available at DOI 10.17605/OSF.IO/UDTQP; the tendon pSHG-XRD resource is available under CC BY 4.0 at DOI 10.5281/zenodo.10979115.", 1)
    text = text.replace("\n## References\n", "\n" + FIGURE6_LEGEND + "\n\n## References\n", 1)
    text = text.replace(
        "30. Hristu, R. et al. PSHG-TISS: a collection of polarization-resolved second harmonic generation microscopy images of fixed tissues. *Sci. Data* **9**, 376 (2022). https://doi.org/10.1038/s41597-022-01477-1",
        "30. Hristu, R. et al. PSHG-TISS: a collection of polarization-resolved second harmonic generation microscopy images of fixed tissues. *Sci. Data* **9**, 376 (2022). https://doi.org/10.1038/s41597-022-01477-1\n31. Zheng, K. et al. Effects of mineralization on the hierarchical organization of collagen—a synchrotron X-ray scattering and polarized second harmonic generation study. *Interface Focus* **14**, 20230046 (2024). https://doi.org/10.1098/rsfs.2023.0046\n32. Zheng, K. Raw data of journal paper of Effects of Mineralisation on the Hierarchical Organisation of Collagen—a Synchrotron X-ray Scattering and Polarised Second Harmonic Generation Study. Zenodo (2024). https://doi.org/10.5281/zenodo.10979115",
        1,
    )
    toc_start = text.index("## Table of Contents")
    graphical = text.index("**[Graphical abstract near here]**", toc_start)
    text = text[:toc_start] + "## Table of Contents\n\n" + TOC_TEXT + "\n\n" + text[graphical:]
    if (
        "Figure 6 near here" not in text
        or "0.891" not in text
        or "38.68%" not in text
        or "currently indexes 112" in text
    ):
        raise RuntimeError("Tendon pSHG integration failed")
    SOURCE.write_text(text, encoding="utf-8")
    return SOURCE


def configure_builder() -> None:
    v32.configure_builder()
    base.FIGURES["Figure 6 near here"] = TLT_FIGURE
    base.FIGURE_ALT["Figure 6"] = "Authentic tendon SHG, NOSTOS orientation and coherence, withheld polarization maps, single-image organization recovery, matched invalid outputs and tied-score risk-coverage curves."
    base.FIGURE_WIDTHS["Figure 6"] = 6.82
    base.DOC_SUBJECT = "Small Methods submission candidate v33; computation-only public-data validation"
    base.DOC_KEYWORDS = "quantitative microscopy; measurement validity; selective prediction; abstention; second harmonic generation; collagen organization; reproducible software"


def main() -> None:
    source = build_source()
    configure_builder()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    missing = [str(path) for path in base.FIGURES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing Small Methods figure assets: {missing}")
    print(base.build(source, OUTPUT))
    print(f"abstract_words={word_count(ABSTRACT)}")
    print(f"toc_words={word_count(TOC_TEXT)}")


if __name__ == "__main__":
    main()
