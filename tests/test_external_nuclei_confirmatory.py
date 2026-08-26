import numpy as np
from pathlib import Path

from nostos.validation.external_nuclei_confirmatory import _filled_outline, _is_dna_channel, _success_gates


def test_locked_dna_channel_rule():
    assert _is_dna_channel(Path("A9 p5d.tif"))
    assert _is_dna_channel(Path("20P1_POS0002_D_1UL.tif"))
    assert _is_dna_channel(Path("AS_A02f00d0.tif"))
    assert not _is_dna_channel(Path("A9 p5f.tif"))
    assert not _is_dna_channel(Path("AS_A02f00d1.tif"))


def test_outline_is_filled():
    outline = np.ones((9, 9), dtype=bool)
    outline[2:7, 2] = False
    outline[2:7, 6] = False
    outline[2, 2:7] = False
    outline[6, 2:7] = False
    mask = _filled_outline(outline)
    assert mask[4, 4]
    assert not mask[0, 0]


def test_success_gates_are_joint_and_image_level():
    rows = [{"nostos_blob_roc_auc": .9, "nostos_blob_average_precision": .8,
             "foreground_fraction": .1, "multiscale_log_roc_auc": .7} for _ in range(8)]
    gates = _success_gates(rows)
    assert all(gate["pass"] for gate in gates.values())
