import numpy as np
import pytest

from nostos.validation.harness import run_frozen_validation
from nostos.validation.metrics import axial_angular_error_degrees, should_abstain
from nostos.validation.phantoms import generate_phantom
from nostos.validation.perturbations import Perturbation, apply_perturbation


@pytest.mark.parametrize("construct", ["orientation", "spectral_scale", "blob", "tube", "sheet", "thickness", "roughness", "network", "heterogeneity"])
def test_phantoms_are_deterministic_and_registered(construct):
    first = generate_phantom(construct, seed=9)
    second = generate_phantom(construct, seed=9)
    np.testing.assert_array_equal(first.image, second.image)
    assert first.truth.construct == construct
    assert np.isfinite(first.image).all()


def test_resampling_updates_spacing_and_preserves_physical_extent():
    phantom = generate_phantom("orientation", shape=(128, 128), spacing_um=(2.0, 2.0))
    changed = apply_perturbation(phantom, Perturbation("resampling", 0.5))
    assert changed.image.shape == (64, 64)
    assert changed.truth.spacing_um == (4.0, 4.0)


def test_abstention_and_axial_error_rules():
    assert axial_angular_error_degrees(179, 1) == pytest.approx(2)
    abstain, reasons = should_abstain(pixels_per_scale=3, signal_to_noise=10)
    assert abstain and "fewer than four" in reasons[0]


def test_frozen_validation_writes_audit_receipt(tmp_path):
    result = run_frozen_validation(tmp_path)
    assert result["status"] == "pass"
    assert result["summary"]["constructs_registered"] == 9
    assert (tmp_path / "validation.json").is_file()
