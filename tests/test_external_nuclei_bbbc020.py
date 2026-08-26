import numpy as np

from nostos.validation.external_nuclei_bbbc020 import _local_support


def test_local_support_excludes_other_annotated_nuclei_from_background():
    first = np.zeros((20, 20), dtype=bool)
    second = np.zeros_like(first)
    first[5:8, 5:8] = True
    second[5:8, 10:13] = True
    foreground, support = _local_support([first, second], ring_width=4)
    assert foreground.sum() == 18
    assert np.all(support[foreground])
    assert foreground[6, 11]
