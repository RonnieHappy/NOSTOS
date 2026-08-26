# NOSTOS-0 cross-domain biological retrieval confirmation

Protocol version: `nostos-biological-retrieval-confirmation/1.0`

Frozen: 26 August 2026, after development-only evaluation and before calculating any confirmation-query feature or rank.

## Question

Does one label-free, stability-weighted NOSTOS comparison geometry preserve specimen identity under an unseen compound acquisition shift across four biological image domains, without tissue labels or tissue-specific feature retraining?

## Cohorts and separation

Four public domains are included: polarization-averaged breast SHG from PSHG-TISS, BBBC039 Hoechst microscopy, MyceliumSeg bright-field filament images and manually annotated collagen-SHG patches. Within each domain, identifiers are ordered by SHA-256. The first 30 are retained; positions 1–15 formed development and positions 16–30 are the untouched confirmation identities. The gallery contains the unperturbed confirmation images. Each query is a transformed copy of its paired gallery image. Retrieval is restricted to the 15 candidates in the same domain; identity rank is the endpoint.

Development used a 19° rotation, isotropic sigma-0.55 blur, gamma 1.18 and Poisson shot noise at 120 counts. It selected Euclidean distance on label-free stability-weighted canonical coordinates from among Euclidean and cosine variants. Development top-1 macro accuracy was 0.567 for the selected representation, versus 0.467 for conventional Euclidean, 0.517 for collapsed Euclidean, 0.533 for raw Euclidean and 0.450 for unweighted canonical Euclidean. These are development results only.

## Frozen confirmation shift

Every confirmation query receives, in order: 61° rotation; anisotropic Gaussian blur with sigma 0.8 and 1.6 pixels; anisotropic resampling by 0.72 and 1.18 followed by fixed 128 × 128 crop/pad; translation by +7 and -9 pixels; gamma 0.65; an illumination gradient of magnitude 0.35 at 0.8 radians; and Poisson shot noise at 45 counts. A deterministic SHA-256-derived seed is unique to each identity.

## Representations and metric

All images are resized to 128 × 128, median centered, divided by their own standard deviation and clipped to [-5, 5]. The same scale, tensor, Hessian, spectral and spatial response implementation is used in every domain. Geometry and network modules abstain because no common mask is supplied.

The primary representation is rotation-quotiented canonical geometry, standardized and weighted by coordinate reliability learned without identity or tissue labels from paired development reference/query vectors. Reliability is between-specimen variance divided by between-specimen plus perturbation-error variance; coordinates below 0.05 are zeroed. Euclidean distance is fixed. Comparators are conventional intensity/gradient summaries, collapsed response summaries, raw response geometry and unweighted canonical geometry, each with development-envelope scaling. Their development-best cosine variants are also reported. No scaler or weight is refit on confirmation.

## Endpoints and uncertainty

The primary endpoint is macro-average top-1 identity retrieval across the four domains. Secondary endpoints are mean reciprocal rank, median rank and domain-specific top-1 accuracy. A 10,000-draw paired bootstrap (seed 8,262,601) resamples confirmation identities within each domain and produces intervals for primary accuracy and paired differences from comparators.

## Frozen success gates

All gates must pass:

1. exactly 60 confirmation identities, 15 in each of four domains;
2. at least 15 nonzero stability-weighted coordinates;
3. macro top-1 accuracy at least 0.35 (chance is 1/15 = 0.0667);
4. bootstrap lower 95% limit for macro top-1 accuracy at least 0.20;
5. mean reciprocal rank at least 0.55;
6. at least three of four domains have top-1 accuracy at least 0.25;
7. paired bootstrap lower limit versus the development-best conventional cosine comparator exceeds -0.05;
8. paired bootstrap lower limit versus the development-best collapsed cosine comparator exceeds -0.05;
9. paired bootstrap lower limit versus the development-best raw cosine comparator exceeds -0.05.

All module ablations are reported but are not success gates. Failure of any gate remains the formal result. Passing supports a shared, label-free comparison coordinate system for same-specimen retrieval under one controlled compound shift across four public image domains. It does not establish phenotype prediction, scanner invariance, clinical matching or universal superiority.
