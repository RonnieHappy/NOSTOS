import json
from pathlib import Path

import numpy as np

from nostos.validation.bone_orientation_v2 import _majority_label, evaluate_tile


def _config():
    return json.loads(Path("configs/bone_contract_orientation_v2.locked.json").read_text())


def test_majority_label_semantics():
    mask = np.zeros((16, 16, 3), dtype=np.uint8)
    mask[:] = (0, 255, 0)
    mask[:2] = (255, 0, 0)
    assert _majority_label(mask)[0] == "green"


def test_withheld_truth_is_not_part_of_contract_score():
    x = np.linspace(0, 8 * np.pi, 128)
    tile = np.tile((np.sin(x) + 1) / 2, (128, 1))
    green = np.zeros((128, 128, 3), dtype=np.uint8); green[:] = (0, 255, 0)
    red = green.copy(); red[:] = (255, 0, 0)
    accepted_truth = evaluate_tile(tile, green, _config())
    invalid_truth = evaluate_tile(tile, red, _config())
    assert accepted_truth["contract_score_degrees"] == invalid_truth["contract_score_degrees"]
    assert not accepted_truth["invalid"]
    assert invalid_truth["invalid"]
