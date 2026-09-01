from pathlib import Path

import pandas as pd

from nostos.reporting.segmentation import generate_segmentation_report, summarize_segmentation


def test_segmentation_summary_is_participant_weighted(tmp_path: Path):
    frame = pd.DataFrame({
        "participant_id": ["P1", "P1", "P2"],
        "stain": ["HE", "SafO", "PLM"],
        "cartilage_dice": [0.8, 1.0, 0.9],
        "cartilage_iou": [0.7, 0.9, 0.8],
        "cartilage_boundary_hd95_um": [50, 70, 60],
        "catastrophic": [False, False, False],
    })
    summary = summarize_segmentation(frame)
    assert summary["cartilage_dice"] == 0.9
    result = generate_segmentation_report(frame, tmp_path)
    assert (tmp_path / "figure_segmentation.svg").is_file()
    assert result["validation_participants"] == 2
