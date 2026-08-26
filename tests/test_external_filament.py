import numpy as np
from PIL import Image

from nostos.validation.external_filament import _find_pairs, validate_filament_dataset


def _write_case(root, species, index):
    image_dir = root / species / "image"
    mask_dir = root / species / "mask"
    image_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    y, x = np.mgrid[:64, :64]
    if species == "GS":
        mask = abs(y - 20 - index) < 3
    elif species == "PO":
        mask = (abs(x - 20 - index) < 3) | (abs(y - 40) < 2)
    else:
        mask = ((x - 32) ** 2 + (y - 32) ** 2) < (10 + index) ** 2
    image = mask.astype(np.uint8) * 180 + np.random.default_rng(index).integers(0, 30, mask.shape, dtype=np.uint8)
    name = f"{index:08d}"
    Image.fromarray(image).save(image_dir / f"{name}.jpg")
    Image.fromarray(mask.astype(np.uint8) * 255).save(mask_dir / f"{name}.png")


def test_filament_pair_discovery_and_validation(tmp_path):
    for species in ("GS", "PO", "TS"):
        for index in range(5):
            _write_case(tmp_path, species, index)
    assert len(_find_pairs(tmp_path)) == 15
    payload = validate_filament_dataset(tmp_path, tmp_path / "output", repeats=2, permutations=3)
    assert payload["summary"]["n_images"] == 15
    assert payload["summary"]["species_counts"] == {"GS": 5, "PO": 5, "TS": 5}
    assert payload["coordinate_system"].startswith("dimensionless")
