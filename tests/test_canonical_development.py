import numpy as np

from nostos.validation.canonical_development import _vectors


def test_development_vectors_are_finite_and_distinct():
    y, x = np.mgrid[-1:1:64j, -1:1:64j]
    image = np.cos(18 * (x + .4 * y)).astype(np.float32)
    raw, canonical = _vectors(image)
    assert raw.ndim == canonical.ndim == 1
    assert np.isfinite(raw).all() and np.isfinite(canonical).all()
    assert raw.size != canonical.size
