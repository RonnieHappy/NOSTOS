import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_biosr_paired_support.py"
SPEC = importlib.util.spec_from_file_location("run_biosr_paired_support", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_audited_profile_lineage_preserves_historical_pilot_lock() -> None:
    historical, amendment = MODULE._verify_pilot_repair_lineage()
    assert historical["schema_version"] == "nostos-developmental-repair-lock/5.0"
    assert amendment["status"] == "prospective_lineage_amendment_before_threshold_pixel_access"
    assert amendment["amendment_scope"][-1].startswith("Do not change the paired-acquisition estimator")
