"""Independent audit configuration for the physical-truth v2.5 receipt."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_synthetic_physical_truth_v2_4 as audit  # noqa: E402


audit.SOURCE = (
    ROOT / "outputs/nostos0-synthetic-physical-truth-v2-5-confirmation/validation.json"
)
audit.REPEAT = (
    ROOT
    / "outputs/nostos0-synthetic-physical-truth-v2-5-confirmation-repeat/validation.json"
)
audit.OUTPUT = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-5-audit/audit.json"
audit.AUDIT_NAME = "nostos-synthetic-physical-truth-v2-5-independent-audit/1.0"


if __name__ == "__main__":
    audit.main()
