import numpy as np

from nostos.validation.biological_retrieval import _retrieve, _standardize


def test_retrieval_is_domain_restricted_and_exact() -> None:
    reference = np.asarray([[0.0], [10.0], [0.0], [10.0]])
    query = reference.copy()
    domains = np.asarray(["a", "a", "b", "b"])
    result = _retrieve(reference, query, domains)
    assert result["top1_macro"] == 1.0
    assert result["median_rank"] == 1.0


def test_standardize_has_fixed_shape_and_finite_values() -> None:
    image = _standardize(np.arange(64).reshape(8, 8))
    assert image.shape == (128, 128)
    assert np.isfinite(image).all()
