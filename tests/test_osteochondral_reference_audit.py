import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest


pytest.importorskip("torch")


SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_osteochondral_reference_definition.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("reference_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_policy_interfaces_distinguish_top_bottom_and_largest_component() -> None:
    mask = np.zeros((12, 8), dtype=bool)
    mask[2:5, 0:2] = True
    mask[6:11, 2:8] = True
    top_any = MODULE.policy_interface(mask, "top_any")
    bottom_any = MODULE.policy_interface(mask, "bottom_any")
    top_largest = MODULE.policy_interface(mask, "top_largest")
    bottom_largest = MODULE.policy_interface(mask, "bottom_largest")
    assert np.all(top_any[:2] == 2)
    assert np.all(bottom_any[:2] == 4)
    assert np.isnan(top_largest[:2]).all()
    assert np.isnan(bottom_largest[:2]).all()
    assert np.all(top_largest[2:] == 6)
    assert np.all(bottom_largest[2:] == 10)


def test_largest_component_uses_eight_connectivity() -> None:
    mask = np.zeros((5, 5), dtype=bool)
    mask[0, 0] = True
    mask[1, 1] = True
    mask[4, 4] = True
    selected = MODULE.largest_component(mask)
    assert selected.sum() == 2
    assert selected[0, 0] and selected[1, 1]
