# NOSTOS-0 BioSR calibration correction and quarantine record

## Stop event

During authorized score-design execution on 28 August 2026, the deposited imaging-conditions workbook was rechecked against the MRC headers. The workbook labels **62.6 nm as the pixel size of the raw SIM image**. The raw-image MRC headers independently store 0.0626 µm in x and y. The 2× GT-SIM headers store 0.0313 µm. The initial protocol had incorrectly assigned 0.0626 µm to the GT-SIM reference and then multiplied it by the upscaling factor for the raw input.

This was an exact factor-of-two physical-calibration error for the 2× data. Both active development workers were stopped immediately. No threshold-calibration field or confirmation archive had been accessed.

## Quarantined outputs

The following directories are historical debugging evidence only and are prohibited from score selection, threshold selection, confirmation, figures or manuscript results:

- `outputs/nostos0-biosr-ccp-smoke-v1`
- `outputs/nostos0-biosr-ccp-smoke-v2`
- `outputs/nostos0-biosr-ccp-development-v1`
- `outputs/nostos0-biosr-ccp-score-design-v1`
- `outputs/nostos0-biosr-ccp-score-design-v2`
- `outputs/nostos0-biosr-er-score-design-v1`
- `outputs/nostos0-biosr-er-score-design-v2`

They are retained rather than deleted so the error and its discovery remain auditable.

## Corrected calibration contract

The raw SIM sampling is 0.0626 µm. For a declared upscaling factor \(u\), the registered GT-SIM sampling is

\[
\Delta_{\mathrm{GT}} = \frac{0.0626\ \mu\mathrm{m}}{u}.
\]

Therefore the 2× reference sampling is 0.0313 µm and the 3× reference sampling is 0.0208666667 µm. Upscaling changes the reference grid; it does not make the stored raw input pixels larger. The raw-input grid spacing and its effective sampling are both 0.0626 µm.

Every indexed pair must now pass all of these independent checks before pixels are measured:

1. Raw MRC x/y spacing agrees with 0.0626 µm within 0.000001 µm.
2. Reference MRC x/y spacing agrees with raw spacing divided by the declared factor.
3. Raw and reference x/y physical fields of view agree within relative tolerance 0.000001.
4. The array-dimension ratio equals the declared upscaling factor.
5. Raw and reference sampling are isotropic in x/y.

The requested scale vector is corrected from 0.5008–2.0032 µm to 0.2504–1.0016 µm. This preserves the prospectively intended 4, 6, 8, 12 and 16 raw-pixel support levels while restoring their correct physical labels. The correction is not chosen using endpoint outcomes.

## Scope clarification

The BioSR archive supplies sampling calibration but not a specimen-specific measured PSF for every acquisition. Version 2 therefore calls this component `physical_sampling`, not diffraction support. It makes no claim to infer the optical resolution limit from the integer upscaling factor. A future PSF/OTF-aware gate must be validated separately.

## Development information already seen

The first correctly authorized but miscalibrated score-design fields revealed one general issue: stable tensor angles can be uninterpretable in weakly directional inputs. The orientation-observability candidate remains permissible because it is a dimensionless input-coherence rule and its 0.15 boundary was already the frozen reference-eligibility boundary. All score-design endpoint results are nevertheless rerun from the source archive with corrected calibration and a new implementation hash.
