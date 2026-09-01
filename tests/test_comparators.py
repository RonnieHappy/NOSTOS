import numpy as np

from nostos.validation.comparators import benchmark_representations, conventional_vector, write_benchmark_receipt, write_external_comparator_dataset
from nostos.validation.phantoms import generate_phantom


def test_conventional_comparator_is_finite():
    phantom = generate_phantom("network")
    vector = conventional_vector(phantom.image, phantom.mask)
    assert vector.ndim == 1 and np.isfinite(vector).all()


def test_comparator_benchmark_has_frozen_separate_test_perturbations():
    results = benchmark_representations()
    assert {
        "conventional_scalar", "naive_response_summaries", "nostos_response_curves"
    } <= {item.representation for item in results}
    assert all(0 <= item.balanced_accuracy <= 1 for item in results)
    assert all(len(item.predictions) == 16 for item in results)


def test_benchmark_receipt_includes_prespecified_contrasts_and_ablations(tmp_path):
    payload = write_benchmark_receipt(tmp_path)
    assert set(payload["contrasts"]) == {
        "nostos_minus_conventional", "nostos_minus_naive_summaries", "worst_ablation_change"
    }
    assert sum(item["representation"].startswith("nostos_without_") for item in payload["results"]) == 6
    assert (tmp_path / "representation_benchmark.json").is_file()


def test_external_comparator_dataset_is_fixed_shape_and_split(tmp_path):
    target = write_external_comparator_dataset(tmp_path / "benchmark.npz")
    bundle = np.load(target, allow_pickle=False)
    assert bundle["images"].shape == (32, 192, 192)
    assert set(bundle["splits"].tolist()) == {"train", "test"}
