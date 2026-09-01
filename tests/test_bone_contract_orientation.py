import numpy as np

from nostos.validation.bone_contract_orientation import _conditions


def test_full_contract_abstains_on_unstable_orientation():
    config = {
        "minimum_dynamic_range_fraction": .05,
        "endpoint_qc_minimum_coherence": .15,
        "full_contract_minimum_coherence": .20,
        "maximum_perturbation_axial_drift_degrees": 10,
        "maximum_interscale_axial_drift_degrees": 15,
    }
    stable = _conditions(.8, .6, 3, 4, config)
    unstable = _conditions(.8, .6, 18, 4, config)
    assert stable["full_contract"] is True
    assert unstable["always_emit"] is True
    assert unstable["full_contract"] is False


def test_endpoint_qc_does_not_see_perturbation_instability():
    config = {
        "minimum_dynamic_range_fraction": .05,
        "endpoint_qc_minimum_coherence": .15,
        "full_contract_minimum_coherence": .20,
        "maximum_perturbation_axial_drift_degrees": 10,
        "maximum_interscale_axial_drift_degrees": 15,
    }
    result = _conditions(.8, .6, 25, 2, config)
    assert result["endpoint_qc"] is True
    assert result["full_contract"] is False
