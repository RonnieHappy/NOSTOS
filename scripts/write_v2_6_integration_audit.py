"""Write a machine-readable v2.6 integration and regression receipt."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs/nostos0-v2-6-integration-audit"
JUNIT = OUTPUT_DIR / "pytest.xml"
OUTPUT = OUTPUT_DIR / "integration_audit.json"
FILES = (
    "src/nostos/features/validated_responses_v2_6.py",
    "src/nostos/features/universal.py",
    "src/nostos/features/canonical_geometry.py",
    "src/nostos/validation/comparators.py",
    "tests/test_validated_responses_v2_6.py",
    "tests/test_universal_geometry.py",
    "outputs/nostos0-synthetic-physical-truth-v2-6-confirmation/validation.json",
    "outputs/nostos0-synthetic-physical-truth-v2-6-audit/audit.json",
    "requirements-lock.txt",
    "pyproject.toml",
)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> None:
    suite = ET.parse(JUNIT).getroot().find("testsuite")
    if suite is None:
        raise ValueError("JUnit receipt does not contain a testsuite element")
    tests = int(suite.attrib["tests"])
    skipped = int(suite.attrib["skipped"])
    failures = int(suite.attrib["failures"])
    errors = int(suite.attrib["errors"])
    skip_reasons = sorted(
        {
            child.attrib.get("message", "unspecified")
            for case in suite.findall("testcase")
            for child in case.findall("skipped")
        }
    )
    confirmation = json.loads(
        (ROOT / FILES[6]).read_text(encoding="utf-8")
    )
    independent_audit = json.loads(
        (ROOT / FILES[7]).read_text(encoding="utf-8")
    )
    head = _git("rev-parse", "--verify", "HEAD")
    status = _git("status", "--porcelain")
    file_hashes = {
        relative: _hash(ROOT / relative)
        for relative in FILES
    }
    checks = {
        "junit_has_no_failures": failures == 0 and errors == 0,
        "expected_test_count": tests == 436 and skipped == 4,
        "v2_6_confirmation_passed": confirmation["status"] == "pass",
        "v2_6_independent_audit_passed": independent_audit["status"] == "pass",
        "all_registered_files_present": all(
            (ROOT / relative).is_file() for relative in FILES
        ),
    }
    receipt = {
        "audit": "nostos-v2-6-integration-audit/1.0",
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "tests": {
            "junit_path": str(JUNIT.relative_to(ROOT)).replace("\\", "/"),
            "junit_sha256": _hash(JUNIT),
            "collected": tests,
            "passed": tests - skipped - failures - errors,
            "skipped": skipped,
            "failures": failures,
            "errors": errors,
            "skip_reasons": skip_reasons,
        },
        "registered_files": file_hashes,
        "source_control": {
            "head": head.stdout.strip() if head.returncode == 0 else None,
            "state": "committed" if head.returncode == 0 else "unborn_no_commit",
            "porcelain_entries": len(
                [line for line in status.stdout.splitlines() if line.strip()]
            ),
            "release_consequence": (
                "A commit-addressed public archive is still required before submission."
                if head.returncode != 0
                else "The recorded commit still requires a public archival DOI."
            ),
        },
        "scope": (
            "Software integration and regression evidence only; the four skipped "
            "Torch-dependent segmentation tests remain outside this CPU environment, "
            "and no clinical or acquisition-transfer claim follows."
        ),
    }
    canonical = json.dumps(
        receipt, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    receipt["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if receipt["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
