# NOSTOS-0 BioSR threshold-calibration verdict

**Status:** FAIL  
**Analysis role:** One-time untouched threshold calibration  
**Confirmation data:** Not accessed

## Operating point

No threshold satisfied the frozen aggregate and structure–endpoint constraints.

No conventional-QC operating point passed the same constraints.

Full-contract AURC was 0.013173, compared with 0.054949 for always emit and 0.014076 for conventional acquisition QC. The reduction relative to always emit was 76.03%.

## Frozen safeguards

Threshold selection used only endpoints retained by the locked acquisition profile. Every accepted, assessable structure–endpoint combination had to meet the 10% observed-risk limit and 70% coverage floor. Overall coverage had to reach 80%, and the stratified reference-field bootstrap upper 95% risk had to remain at or below 15%. The threshold maximizes coverage among tied-score cutoffs satisfying every rule.

## Decision boundary

Passing this gate authorizes the unchanged threshold for the untouched BioSR confirmation structures. It does not establish biological ground truth, acquisition-family generalization, clinical validity, diagnosis, treatment utility or intraoperative performance. A failed gate does not authorize threshold tuning on these calibration fields.
