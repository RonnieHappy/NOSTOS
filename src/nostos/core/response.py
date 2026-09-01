"""Typed, serializable representation of the NOSTOS methodological object."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import numpy as np


@dataclass(frozen=True)
class Calibration:
    spacing: tuple[float, ...]
    spatial_unit: Literal["um", "mm", "relative"] = "um"
    specimen_reference: float | None = None
    specimen_reference_name: str | None = None
    specimen_direction_degrees: float = 0.0
    temporal_spacing: float | None = None
    temporal_unit: str | None = None

    def __post_init__(self) -> None:
        if not self.spacing or any(not np.isfinite(v) or v <= 0 for v in self.spacing):
            raise ValueError("All spatial spacing values must be finite and positive.")
        if self.specimen_reference is not None and self.specimen_reference <= 0:
            raise ValueError("specimen_reference must be positive when provided.")
        if self.temporal_spacing is not None and self.temporal_spacing <= 0:
            raise ValueError("temporal_spacing must be positive when provided.")

    def relative_scale(self, physical_scale: float) -> float | None:
        return None if self.specimen_reference is None else physical_scale / self.specimen_reference

    def specimen_direction(self, image_direction_degrees: float) -> float:
        return float((image_direction_degrees + self.specimen_direction_degrees) % 180.0)


@dataclass(frozen=True)
class Axis:
    name: Literal["scale", "direction", "threshold", "separation", "time", "other"]
    values: tuple[float, ...]
    unit: str

    def __post_init__(self) -> None:
        if not self.values or not np.isfinite(self.values).all():
            raise ValueError("Response axes must contain finite values.")


@dataclass(frozen=True)
class StabilityRecord:
    perturbation: str
    magnitude: float
    distance: float
    passed: bool
    reason: str | None = None


@dataclass(frozen=True)
class Abstention:
    code: str
    reason: str
    requested_measurement: str


@dataclass(frozen=True)
class ResponseSurface:
    module: Literal["spectral", "tensor", "hessian", "geometry", "network", "spatial", "dynamic"]
    measurement: str
    axes: tuple[Axis, ...]
    values: tuple[float, ...]
    shape: tuple[int, ...]
    amplitude_unit: str = "dimensionless"
    uncertainty: tuple[float, ...] | None = None
    validity: Literal["valid", "review", "abstain"] = "valid"
    validity_reasons: tuple[str, ...] = ()
    validity_mask: tuple[bool, ...] | None = None
    validity_reasons_by_value: tuple[tuple[str, ...], ...] | None = None
    evidence_status: Literal["unvalidated", "developmental", "calibrated", "confirmed"] = "unvalidated"
    evidence_profile_id: str | None = None
    stability: tuple[StabilityRecord, ...] = ()

    def __post_init__(self) -> None:
        expected = int(np.prod(self.shape))
        if expected != len(self.values):
            raise ValueError(f"Response shape requires {expected} values; received {len(self.values)}.")
        if len(self.axes) != len(self.shape):
            raise ValueError("One response axis is required per response dimension.")
        if any(len(axis.values) != size for axis, size in zip(self.axes, self.shape, strict=True)):
            raise ValueError("Axis lengths must match response shape.")
        if self.uncertainty is not None and len(self.uncertainty) != len(self.values):
            raise ValueError("Uncertainty must match the flattened response length.")
        if self.validity_mask is not None and len(self.validity_mask) != len(self.values):
            raise ValueError("Validity mask must match the flattened response length.")
        if self.validity_reasons_by_value is not None and len(self.validity_reasons_by_value) != len(self.values):
            raise ValueError("Per-value validity reasons must match the flattened response length.")
        if self.validity_mask is not None and self.validity_reasons_by_value is not None:
            for valid, reasons in zip(self.validity_mask, self.validity_reasons_by_value, strict=True):
                if valid and reasons:
                    raise ValueError("A valid response value cannot have pointwise invalidity reasons.")
        if not np.isfinite(self.values).all():
            raise ValueError("Response values must be finite.")


@dataclass
class ResponseGeometry:
    calibration: Calibration
    input_dimensions: tuple[int, ...]
    responses: list[ResponseSurface] = field(default_factory=list)
    abstentions: list[Abstention] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "nostos-response-geometry/1.0"

    def add(self, response: ResponseSurface) -> None:
        key = (response.module, response.measurement)
        if any((item.module, item.measurement) == key for item in self.responses):
            raise ValueError(f"Duplicate response: {key}.")
        self.responses.append(response)

    def abstain(self, code: str, reason: str, requested_measurement: str) -> None:
        self.abstentions.append(Abstention(code, reason, requested_measurement))

    @property
    def status(self) -> Literal["valid", "review", "abstain"]:
        if not self.responses and self.abstentions:
            return "abstain"
        if self.abstentions or any(r.validity != "valid" for r in self.responses):
            return "review"
        return "valid"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status
        evidence_order = {"unvalidated": 0, "developmental": 1, "calibrated": 2, "confirmed": 3}
        if self.responses:
            payload["evidence_status"] = min(
                (response.evidence_status for response in self.responses),
                key=lambda value: evidence_order[value],
            )
        else:
            payload["evidence_status"] = "unvalidated"
        return payload
