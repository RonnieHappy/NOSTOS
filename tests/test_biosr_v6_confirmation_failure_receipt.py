from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_biosr_v6_confirmation_failure_receipt.py"


def _module():
    spec = importlib.util.spec_from_file_location("v6_failure_receipt", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require_external_archive(module) -> None:
    if not Path(module.LINEAR_ARCHIVE).is_file():
        pytest.skip("The checksum-locked external BioSR archive is not bundled in the data-free release.")


def test_linear_archive_indexing_reads_names_and_finds_uniform_twelve_levels() -> None:
    module = _module()
    _require_external_archive(module)
    levels = module.index_linear_levels(module.LINEAR_ARCHIVE)
    assert len(levels) == 51
    assert all(values == list(range(1, 13)) for values in levels.values())


def test_failure_payload_preserves_v6_and_f_actin_boundaries() -> None:
    module = _module()
    _require_external_archive(module)
    payload = module.build_payload()
    assert payload["status"] == "prospective_v6_failed_after_first_untouched_structure"
    assert payload["lineage"]["locked_file_mismatches"] == 0
    assert payload["microtubules_result"]["safety_gate_passed"] is False
    assert payload["decision"]["remaining_f_actin_pixels_reserved"] is True
    assert payload["linear_layout_error"]["scientific_outcome_observed"] is False
    families = {item["family"] for item in payload["decisive_failures"]}
    assert {"tensor_coherence", "tensor_orientation"} <= families
