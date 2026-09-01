from __future__ import annotations

import numpy as np

from nostos.features.validated_responses_v2_5 import (
    gradient_moment_anisotropy_2d,
    validated_hessian_morphology,
)
from nostos.validation.phantoms import generate_phantom


def test_v25_hessian_rejects_opened_borderline_sampling_pattern() -> None:
    phantom = generate_phantom(
        "blob",
        shape=(64, 64, 64),
        spacing_um=(1.7, 1.7, 1.7),
        scale_um=22.0,
    )
    response = validated_hessian_morphology(
        phantom.image,
        spacing_um=(1.7, 1.7, 1.7),
        scales_um=(5.5, 8.25, 11.0, 13.75, 16.5),
    )
    assert response.samples_per_winning_scale < 5.0
    assert response.supported is False
    assert response.abstention_reasons == (
        "winning_hessian_scale_below_5_samples",
    )


def test_v25_axis_abstains_for_weak_periodic_anisotropy() -> None:
    yy, xx = np.mgrid[0:128, 0:128]
    image = (
        np.sin(2.0 * np.pi * xx / 16.0)
        + 0.625 * np.sin(2.0 * np.pi * yy / 16.0)
    )
    response = gradient_moment_anisotropy_2d(
        image,
        spacing_um=(1.0, 1.0),
    )
    assert 1.55 <= response.ratio < 1.65
    assert response.axis_identifiable is False
    assert response.major_axis_degrees is None
