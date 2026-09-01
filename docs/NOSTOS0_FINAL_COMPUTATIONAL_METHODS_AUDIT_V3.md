# NOSTOS-0 final computational-methods audit v3

**Audit scope:** computation-only methods/tool paper  
**Wet-lab requirement:** none for the present claim  
**Clinical or intraoperative claim:** explicitly excluded  
**Current status:** high-impact computational-methods reach candidate, pending
public archival release and unaided external execution

## Terminal verdict

NOSTOS-0 now has a coherent methodological center: an executable compiler for
measurement-specific validity profiles. It is no longer submitted as a loose
collection of FFT, tensor, Hessian, thickness, topology and spatial features.
Those established estimators are the measurement substrate. The contribution
is the machinery that decides, prospectively and audibly, when a requested
measurement is supported by the acquisition.

The decisive evidence is not a large sample count. It is a staged failure and
repair in which the independent unit was preserved, confirmation remained
untouched, and the repair addressed a reproducible subgroup failure rather than
optimizing a headline metric. A pooled widefield result passed while hiding a
fully invalid average-of-8 by 8-pixel cell. The hierarchical acquisition×scale
support layer removed that failure on four new FOVs without reference labels at
deployment. This establishes the intended behavior in one bounded acquisition
family.

## Evidence status

| Evidence object | Independent units | Frozen result | Audit decision |
|---|---:|---|---|
| Synthetic truth and perturbation registry | Analytic constructs | 24/24 declared module tests passed | Foundation only; not external validity |
| BioSR v9 controlled-degradation confirmation | 8 untouched F-actin fields | 95.0% coverage; risk 0.0387 versus 0.0735; 47.4% relative reduction; positive clustered AURC interval | Prospective bounded pass |
| FMD v1.2 modality audit | FMD acquisition strata | Aggregate pass concealed widefield risk 0.4167 | Retained negative result |
| FMD v1.3 widefield confirmation | 4 untouched FOVs | Pooled pass; all four errors in the same avg8×8-pixel cell | Retained subgroup failure; not terminal success |
| FMD v1.4 hierarchical confirmation | 4 new untouched FOVs | 64/240 emitted; 0 errors; matched QC 31/64 errors; AURC difference 0.281 (0.187–0.416) | Prospective bounded pass |
| FMD terminal code-path audit | 17 independent integrity checks | 17/17 passed, including reference-label blindness and exact decision reproduction | Verified author-operated audit |
| Exact finite-sample audit | 64 nested emissions; 4 FOVs | upper 95% limits 5.6% by emission and 60.2% by FOV-any-failure | Mandatory uncertainty boundary |

## Novelty audit

The manuscript must acknowledge selective prediction, risk-controlling
prediction sets, Learn-then-Test, subgroup calibration, microscope QC and
radiomics. The defensible distinction is operational:

- the object is a continuous scientific measurement, not a class prediction;
- support is indexed by acquisition and requested measurement coordinates;
- labels and reference errors are unavailable to the deployed decision;
- fields/specimens, not repeated tiles or captures, define independent units;
- unseen or unsupported cells fail closed;
- failures, amendments and confirmations remain hash-linked rather than being
  silently replaced; and
- the same compiler is exposed as a public CLI around arbitrary compatible
  measurement rows.

The current implementation does not provide a distribution-free guarantee and
must not borrow that language from conformal or risk-controlling prediction-set
methods. It provides a prospectively tested, grouped empirical validity
contract with exact finite-sample caveats.

## Statistical audit

All repeated captures, scales, perturbations and endpoint rows are nested
within their field of view. Selection, cross-fitting and resampling preserve the
field boundary. Ordinary acquisition QC is compared at matched emission count;
the boundary-tie analysis brackets best- and worst-case comparator risk. The
primary AURC difference is bootstrapped by FOV. Supported-cell tests operate in
the conservative direction: one unsafe declared cell fails the complete
profile even if pooled risk passes.

The zero-event FMD result is reported with exact Clopper–Pearson intervals.
The zero-width cluster-bootstrap percentile is retained in its frozen audit but
is never presented as population certainty. With four independent confirmation
FOVs, population generalization remains deliberately narrow.

## Reproducibility audit

The public tool provides separate commands to compile a profile and audit a
confirmation set. Hierarchical support is a second composable object over an
immutable base profile. Confirmation emits the audit, row-level decisions and
finite-sample uncertainty in separate machine-readable files. Every FMD archive
member used for analysis is indexed from the tar archive, hashed before pixel
decoding and linked to the source archive checksum. The terminal FMD audit
reproduces deterministic FOV selection, row counts, score formulae and deployed
decisions while proving that mutating reference labels does not change those
decisions.

The release is data-free. Public images remain at their originating archives;
download instructions, repository identifiers, licences and checksums are
included. A final release archive must pass the secret/private-path scanner,
clean-room installation, full tests and deterministic rebuild before archival
deposit.

## Claim boundary

Supported:

> Within the tested public acquisition families, frozen NOSTOS validity
> profiles reduced silent-invalid structural measurements relative to ordinary
> acquisition QC. Hierarchical acquisition×scale support prevented a pooled
> profile from concealing a reproducible unsafe subgroup in FMD widefield
> microscopy.

Not supported:

- zero population risk;
- transfer to arbitrary microscopes or tissues;
- universal superiority of the underlying feature estimators;
- biological meaning of FMD tensor coherence;
- physical-scale accuracy where pixel spacing is unavailable;
- image restoration or denoising superiority;
- diagnosis, clinical utility, intraoperative deployment or regulatory use.

## Remaining submission gates

Only two gates require action outside the present local computation:

1. archive the exact public release and replace the DOI placeholder; and
2. obtain one unaided external execution receipt from the archived package.

Authorship, affiliation, funding, acknowledgements, competing interests and the
institution's preferred wording for public-data secondary analysis are
administrative completion items. No wet-lab study is required to support the
computational-methods claim. A new microscope or prospective clinical cohort
would belong to a later translational paper and must not be described as a
blocker for NOSTOS-0.

## Venue judgment

Nature Methods is a legitimate reach because the paper now addresses a general
and consequential failure mode in quantitative microscopy with an executable
method, prospective failures, two public-resource confirmations and unusually
complete provenance. Acceptance is not assured: the small FMD independent-unit
count and lack of external-user evidence are visible weaknesses. Patterns,
Cell Reports Methods, PLOS Computational Biology and GigaScience remain strong
alternatives. Nature Biomedical Engineering is not the appropriate target for
this computation-only paper because no biomedical device or clinical workflow
is claimed.

