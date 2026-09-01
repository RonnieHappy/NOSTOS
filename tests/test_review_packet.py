import json

import numpy as np
import pandas as pd
from PIL import Image

from nostos.segmentation.review_packet import build_review_packet


def test_review_packet_excludes_outcomes_and_freezes_hashes(tmp_path):
    root = tmp_path / "annotations"
    (root / "images").mkdir(parents=True)
    (root / "proposals").mkdir()
    image = np.zeros((40, 50, 3), dtype=np.uint8)
    image[10:30, 8:42] = 120
    proposal = np.zeros((40, 50), dtype=np.uint8)
    proposal[12:28, 10:40] = 1
    proposal[2:8, 2:8] = 3
    Image.fromarray(image).save(root / "images" / "case.png")
    Image.fromarray(proposal).save(root / "proposals" / "case_proposal.png")
    pd.DataFrame([{"participant_id": "001", "specimen_id": "Medial_SafO", "site": "Medial",
                   "stain": "SafO", "split": "validation", "image_path": "images/case.png",
                   "mask_path": "masks/case.png", "review_path": "masks/case.json"}]).to_csv(root / "annotation_manifest.csv", index=False)
    (root / "source_provenance.json").write_text(json.dumps([{"participant_id": "001",
        "specimen_id": "Medial_SafO", "source_sha256": "a" * 64, "model_pixel_size_um": 5.16}]))
    receipt = build_review_packet(root, tmp_path / "packet")
    review = pd.read_csv(tmp_path / "packet" / "review_manifest.csv")
    assert receipt["case_count"] == 1
    assert not {"participant_id", "HHGS", "OARSI", "PLM"}.intersection(review.columns)
    assert review.loc[0, "case_id"].startswith("CMR-")
