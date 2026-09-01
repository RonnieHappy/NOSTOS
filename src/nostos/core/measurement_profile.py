"""Explicit acquisition-profile evidence for NOSTOS measurements."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class MeasurementProfile:
    profile_id: str
    status: str
    eligible_endpoints: frozenset[str]
    disabled_endpoints: dict[str, str]
    required_input_dimensions: int | None = None
    required_spatial_unit: str | None = None
    required_spacing: tuple[float, ...] | None = None
    spacing_absolute_tolerance: float = 0.0
    required_input_construction: str | None = None
    analysis_scales: tuple[float, ...] | None = None
    spectral_band_fraction_of_nyquist: tuple[float, float] | None = None
    intensity_preprocessing: str | None = None
    curve_normalization: str | None = None
    verified_artifacts: tuple[tuple[str, str], ...] = ()
    source_path: str | None = None
    source_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("Measurement profile_id cannot be empty.")
        overlap = self.eligible_endpoints & set(self.disabled_endpoints)
        if overlap:
            raise ValueError(f"Profile endpoints cannot be both eligible and disabled: {sorted(overlap)}")
        if self.required_input_dimensions is not None and self.required_input_dimensions not in {2, 3}:
            raise ValueError("Measurement-profile input dimensionality must be 2 or 3.")
        if self.required_spacing is not None:
            if any(value <= 0 for value in self.required_spacing):
                raise ValueError("Measurement-profile spacing values must be positive.")
            if (
                self.required_input_dimensions is not None
                and len(self.required_spacing) != self.required_input_dimensions
            ):
                raise ValueError("Measurement-profile spacing must match the required dimensionality.")
        if self.spacing_absolute_tolerance < 0:
            raise ValueError("Measurement-profile spacing tolerance cannot be negative.")
        if self.analysis_scales is not None and (
            not self.analysis_scales or any(value <= 0 for value in self.analysis_scales)
        ):
            raise ValueError("Measurement-profile analysis scales must be positive.")
        if self.spectral_band_fraction_of_nyquist is not None:
            low, high = self.spectral_band_fraction_of_nyquist
            if not 0 <= low < high <= 1:
                raise ValueError("Profile spectral fractions must satisfy 0 <= low < high <= 1.")

    @classmethod
    def from_path(cls, path: Path) -> "MeasurementProfile":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "nostos-acquisition-measurement-profile/1.0":
            raise ValueError(f"Unsupported measurement-profile schema: {path}")
        eligible = frozenset(str(value) for value in payload["eligible_for_threshold_calibration"])
        disabled = {
            str(key): str(value)
            for key, value in payload["disabled_for_this_acquisition_profile"].items()
        }
        compatibility: dict[str, Any] = payload.get("compatibility_contract", {})
        analysis: dict[str, Any] = payload.get("analysis_contract", {})
        basis: dict[str, Any] = payload.get("basis", {})
        spectral_fractions = analysis.get("spectral_band_fraction_of_input_nyquist")
        project_root = path.resolve().parent.parent if path.resolve().parent.name == "configs" else path.resolve().parent
        declared_artifacts = [
            (
                basis.get("artifact_receipt_path"),
                basis.get("artifact_receipt_sha256"),
                basis.get("artifact_receipt_bytes"),
            ),
            (
                basis.get("pilot_audit_path"),
                basis.get("pilot_audit_sha256"),
                basis.get("pilot_audit_bytes"),
            ),
            (
                analysis.get("protocol_config_path"),
                analysis.get("protocol_config_sha256"),
                None,
            ),
        ]
        for item in basis.get("artifacts", []):
            declared_artifacts.append(
                (item.get("path"), item.get("sha256"), item.get("bytes"))
            )
        verified_artifacts: list[tuple[str, str]] = []
        for relative_path, expected_sha256, expected_bytes in declared_artifacts:
            if relative_path is None and expected_sha256 is None:
                continue
            if relative_path is None or expected_sha256 is None:
                raise ValueError("Profile evidence links require both path and SHA-256.")
            artifact = project_root / str(relative_path)
            if not artifact.is_file():
                raise ValueError(f"Profile evidence artifact is missing: {artifact}")
            if expected_bytes is not None and artifact.stat().st_size != int(expected_bytes):
                raise ValueError(f"Profile evidence artifact size mismatch: {artifact}")
            actual_sha256 = _sha256_file(artifact)
            if actual_sha256 != str(expected_sha256):
                raise ValueError(f"Profile evidence artifact SHA-256 mismatch: {artifact}")
            verified_artifacts.append((str(artifact.resolve()), actual_sha256))
        return cls(
            profile_id=str(payload["profile_id"]),
            status=str(payload["status"]),
            eligible_endpoints=eligible,
            disabled_endpoints=disabled,
            required_input_dimensions=(
                None
                if compatibility.get("input_dimensions") is None
                else int(compatibility["input_dimensions"])
            ),
            required_spatial_unit=(
                None
                if compatibility.get("spatial_unit") is None
                else str(compatibility["spatial_unit"])
            ),
            required_spacing=(
                None
                if compatibility.get("spacing") is None
                else tuple(float(value) for value in compatibility["spacing"])
            ),
            spacing_absolute_tolerance=float(
                compatibility.get("spacing_absolute_tolerance", 0.0)
            ),
            required_input_construction=(
                None
                if compatibility.get("required_input_construction") is None
                else str(compatibility["required_input_construction"])
            ),
            analysis_scales=(
                None
                if analysis.get("physical_scales") is None
                else tuple(float(value) for value in analysis["physical_scales"])
            ),
            spectral_band_fraction_of_nyquist=(
                None
                if spectral_fractions is None
                else (float(spectral_fractions[0]), float(spectral_fractions[1]))
            ),
            intensity_preprocessing=(
                None
                if analysis.get("intensity_preprocessing") is None
                else str(analysis["intensity_preprocessing"])
            ),
            curve_normalization=(
                None
                if analysis.get("curve_normalization") is None
                else str(analysis["curve_normalization"])
            ),
            verified_artifacts=tuple(verified_artifacts),
            source_path=str(path.resolve()),
            source_sha256=_sha256_file(path),
        )

    def compatibility_reasons(
        self,
        *,
        input_dimensions: int,
        spacing: tuple[float, ...],
        spatial_unit: str,
        analysis_scales: tuple[float, ...],
    ) -> tuple[str, ...]:
        """Return machine-checkable reasons the profile cannot support an input."""

        reasons: list[str] = []
        if (
            self.required_input_dimensions is not None
            and input_dimensions != self.required_input_dimensions
        ):
            reasons.append(
                f"input_dimensions_{input_dimensions}_does_not_match_{self.required_input_dimensions}"
            )
        if self.required_spatial_unit is not None and spatial_unit != self.required_spatial_unit:
            reasons.append(
                f"spatial_unit_{spatial_unit}_does_not_match_{self.required_spatial_unit}"
            )
        if self.required_spacing is not None:
            if len(spacing) != len(self.required_spacing):
                reasons.append("spacing_dimensionality_does_not_match_profile")
            elif any(
                abs(observed - required) > self.spacing_absolute_tolerance
                for observed, required in zip(spacing, self.required_spacing, strict=True)
            ):
                reasons.append("spacing_does_not_match_profile")
        if self.analysis_scales is not None:
            if len(analysis_scales) != len(self.analysis_scales) or any(
                abs(observed - required) > max(1e-12, self.spacing_absolute_tolerance)
                for observed, required in zip(
                    analysis_scales, self.analysis_scales, strict=False
                )
            ):
                reasons.append("analysis_scale_grid_does_not_match_profile")
        if self.intensity_preprocessing not in {
            None,
            "percentile_1_99_clip_unit_interval",
        }:
            reasons.append("unsupported_profile_intensity_preprocessing")
        if self.curve_normalization not in {None, "l2"}:
            reasons.append("unsupported_profile_curve_normalization")
        return tuple(reasons)

    def evidence_status(self, endpoint: str | None) -> str:
        if endpoint is None or endpoint not in self.eligible_endpoints:
            return "unvalidated"
        if self.status.startswith("provisional_"):
            return "developmental"
        if self.status == "threshold_calibrated":
            return "calibrated"
        if self.status == "externally_confirmed":
            return "confirmed"
        return "unvalidated"

    def disabled_reason(self, endpoint: str | None) -> str | None:
        return None if endpoint is None else self.disabled_endpoints.get(endpoint)
