# Human nanoCT directional transfer v1

The scalar 3D gradient-tensor contract failed. Across 288 technical cases from six deposited volumes, always-emit risk was 0.413 (volume-cluster 95% interval 0.372--0.451). The full contract retained 0.920 coverage but risk remained 0.389 (0.327--0.447).

The full contract correctly rejected enough additive-noise cases that all accepted noisy cases were valid, but it accepted all severe-blur and half-resolution cases. Accepted risk was 0.896 for severe blur and 0.688 for half-resolution restoration. This demonstrates that self-consistency after degradation cannot identify stable bias caused by information already lost.

The scalar endpoint is retired. NOSTOS must preserve a scale-indexed directional response and declare support independently at each physical scale. Effective resolution or PSF information is a required precondition for claims near the acquisition limit.

This dataset has been opened for development and cannot serve as pristine confirmation of the replacement estimator.

