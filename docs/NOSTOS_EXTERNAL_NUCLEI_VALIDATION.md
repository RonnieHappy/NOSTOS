# External nuclei validation

NOSTOS was evaluated on the official held-out test split of BBBC039v1: 50 Hoechst fluorescence fields with manually annotated U2OS nuclear instances. The analysis used no learned model, fitted threshold or case selection. Pixel spacing is not supplied, so scales were declared in dimensionless image coordinates and physical outputs abstained.

The initial sign-agnostic Hessian response (protocol 1.0) reached mean average precision 0.513 and mean ROC AUC 0.783. It was inferior to normalized intensity and a multiscale Laplacian-of-Gaussian baseline. Inspection identified a general mathematical defect: taking absolute eigenvalues combined bright-object curvature with dark structures and edges.

Protocol 1.1 added an explicit polarity option to the shared Hessian field implementation. The default remains `either`, preserving earlier analyses. BBBC039 was rerun with `bright`, declared from Hoechst acquisition rather than fitted from masks. Average precision increased to 0.868 (95% image-bootstrap interval for the mean, 0.864–0.873) and ROC AUC to 0.943 (0.938–0.948). This exceeded multiscale Laplacian-of-Gaussian by 0.083 average-precision units (0.066–0.099) and 0.062 ROC-AUC units (0.047–0.077), but remained inferior to raw fluorescence intensity.

Because the polarity refinement followed inspection of version 1.0 on the same held-out images, version 1.1 is transparent post-test method development, not pristine confirmatory evidence. Both receipts are retained. A future independent dataset must test the polarity-aware implementation without further method changes.

Reproduce with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fetch_bbbc039_reference.ps1 -Destination <DATA_ROOT>/BBBC039v1
uv run nostos validate-nuclei --data <DATA_ROOT>/BBBC039v1 --output outputs/external-nuclei-v1_1
```
