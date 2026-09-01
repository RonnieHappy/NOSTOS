from pathlib import Path

import numpy as np

from nostos.intraop.label_free import load_intraop_profile
from nostos.intraop.label_free_v1_4 import analyze_unstained_field, export_case_artifacts


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "configs/intraop_pshg_orientation_profile_v1.locked.json"


def test_all_release_artifacts_have_unique_registered_paths(tmp_path: Path) -> None:
    profile = load_intraop_profile(PROFILE_PATH)
    y, x = np.mgrid[:128, :128]
    image = 100.0 + 40.0 * np.sin((x + 2.0 * y) / 7.0)
    r2 = np.ones(image.shape, dtype=float)
    snr = np.full(image.shape, 10.0)
    result = analyze_unstained_field(
        image,
        pixel_size_um=1.0,
        modality=profile["modality"],
        profile=profile,
        verified_stack_frame_count=10,
        r2_map=r2,
        snr_map=snr,
    )
    artifacts = export_case_artifacts(result, tmp_path)
    assert set(artifacts) == {
        "orientation_array",
        "coherence_array",
        "eligible_array",
        "source_image",
        "orientation_image",
        "coherence_image",
        "support_image",
    }
    paths = [item["path"] for item in artifacts.values()]
    assert len(paths) == len(set(paths)) == 7
    assert set(paths) == {
        "orientation_degrees.npy",
        "coherence.npy",
        "eligible.npy",
        "source.png",
        "orientation.png",
        "coherence.png",
        "support.png",
    }
    assert all((tmp_path / name).is_file() for name in paths)
