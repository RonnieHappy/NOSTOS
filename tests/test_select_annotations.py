from pathlib import Path

import pandas as pd

from nostos.segmentation.select_annotations import select_annotation_images


def test_annotation_selection_never_uses_morphology_test_participants(tmp_path: Path):
    participants = [f"{index:03}" for index in range(1, 13)]
    records = []
    for participant in participants:
        for modality, sites in (("HE", ["Medial", "Lateral"]), ("SafO", ["Medial", "Lateral"]), ("PLM", ["Medial"])):
            for site in sites:
                records.append({"participant_id": participant, "modality": modality, "site": site, "relative_path": f"P{participant}/{site}/{modality}/a.tif", "pixel_size_um_x": 5.16})
    manifest = {"dataset_root": str(tmp_path), "records": records}
    metadata = pd.DataFrame({"participant_id": participants, "mean_total_plm": range(12)})
    splits = {"splits": {"train": participants[:7], "validation": participants[7:10], "test": participants[10:]}}
    selection, report = select_annotation_images(manifest, metadata, splits, training_participants=4, validation_participants=2)
    assert report["training_images"] == 12
    assert report["validation_images"] == 10
    assert report["morphology_test_participants_used"] == 0
    assert not set(selection["participant_id"]).intersection(participants[10:])
