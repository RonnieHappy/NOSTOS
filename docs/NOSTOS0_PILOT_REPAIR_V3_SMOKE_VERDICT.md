# Version-3 smoke verdict: rejected before balanced-pilot execution

Version 3 was run on one previously selected CCP score-design field only. Its receipt is `outputs/nostos0-biosr-ccp-pilot-repair-v3-smoke/archive_receipt.json` (SHA-256 `c27176eee8f697a85137937a4f5cc190ca945fb8db44e5f3c1fc8f8784cab9f7`).

The smoke confirmed that the common physical FFT band and scale-boundary handling executed as designed. It also exposed a remaining semantic failure: a tensor-derived orientation resultant could be high in the reference while the independent Fourier anisotropy indicated no global direction. Tensor resultant alone was therefore insufficient to establish orientation observability. The diagnostic resultant had also been added as an evaluated endpoint even though its role in this protocol is measurement support rather than a claimed structural endpoint.

Version 3 is not evidence and was not run on the remaining eleven selected fields. Version 4 removes the resultant from the endpoint set and requires three input-only conditions before emitting orientation: tensor resultant, Fourier anisotropy, and tensor-Fourier angular agreement. The same conditions are required for reference eligibility during validation.

Threshold-calibration fields and confirmation archives remained sealed.
