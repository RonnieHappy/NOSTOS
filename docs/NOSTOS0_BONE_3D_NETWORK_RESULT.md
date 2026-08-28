# NOSTOS-0 3D bone-network result

## Result

The calibrated v2 stress test generated 52 invalid cases among 104 deterministic cases from 26 paired volumes and 13 rats. Always-emit and intensity/occupancy QC each emitted all cases with silent-invalid risk 0.50. Topology QC accepted 94.2% with risk 0.469. The full contract accepted 53.8% with risk 0.250.

The full score improved risk-coverage area from 0.483 for endpoint QC and 0.440 for topology QC to 0.210. Nested-field stability was the active added safeguard; the boundary component did not change acceptance in this experiment.

## Gate interpretation

This is evidence that the full diagnostic score ranks corrupted imported masks better than ordinary occupancy or topology checks in a calibrated stress test. It is not a confirmatory success:

- full-contract coverage was 0.538, below the master protocol's 0.80 overall target;
- v2 corruption severity was selected after v1 failed to generate invalid cases;
- all cases derive from one source dataset and its U-Net-plus-correction masks;
- corruption was synthetic and does not establish error rates of the deposited masks;
- one component (boundary contact) added no measurable value.

The defensible claim is therefore limited to development evidence for a useful nested-field validity signal. Independent acquisition-family confirmation remains required.

