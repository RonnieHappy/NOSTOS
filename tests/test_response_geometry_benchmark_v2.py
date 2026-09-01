import json
import numpy as np

from nostos.validation.response_geometry_benchmark_v2 import CLASSES, _stratified_interval, generate_dataset


def test_v2_dataset_is_balanced_and_split(tmp_path):
    path = generate_dataset(tmp_path / "v2.npz")
    bundle = np.load(path, allow_pickle=False)
    assert bundle["images"].shape == (480, 96, 96)
    for split in ("train", "test"):
        selected = bundle["labels"][bundle["splits"] == split]
        assert {label: int(np.sum(selected == label)) for label in CLASSES} == {label: 40 for label in CLASSES}
    assert np.isfinite(bundle["images"]).all()


def test_stratified_interval_recognizes_identical_predictions():
    truth = np.repeat(np.asarray(CLASSES), 4)
    interval = _stratified_interval(truth, truth, truth)
    assert interval == [0.0, 0.0]
