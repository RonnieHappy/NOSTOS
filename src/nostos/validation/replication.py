"""One-command, data-free replication challenge for an external NOSTOS user."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from nostos.validation.comparators import write_benchmark_receipt
from nostos.validation.harness import run_frozen_validation
from nostos.validation.module_perturbations import run_module_perturbation_matrix


PROTOCOL = "nostos-external-replication/2.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _revision(project_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


def run_replication_challenge(
    output: Path,
    project_root: Path,
    operator: str = "anonymous",
    *,
    affiliation: str = "",
    unaided: bool = False,
    author_environment: bool = True,
    assistance: str = "not declared",
    source_kind: str = "unspecified",
) -> dict:
    """Regenerate the frozen foundations and write a self-verifying receipt."""
    output.mkdir(parents=True, exist_ok=True)
    synthetic_dir = output / "synthetic"
    benchmark_dir = output / "benchmark"
    modules_dir = output / "modules"
    synthetic = run_frozen_validation(synthetic_dir)
    benchmark = write_benchmark_receipt(benchmark_dir)
    modules = run_module_perturbation_matrix(modules_dir)

    gates = {
        "synthetic_protocol_passes": synthetic["status"] == "pass",
        "nine_truth_constructs_registered": synthetic["summary"]["constructs_registered"] == 9,
        "all_five_module_gates_pass": synthetic["summary"]["module_gates_passed"] == synthetic["summary"]["module_gates_total"] == 5,
        "all_24_required_perturbation_tests_pass": modules["summary"]["passed"] == modules["summary"]["required_tests"] == 24,
        "mask_tests_retained_as_sensitivity": modules["summary"]["mask_sensitivity_tests"] == 2,
        "benchmark_receipt_generated": bool(benchmark.get("results")),
    }
    artifacts = []
    for path in (synthetic_dir / "validation.json", benchmark_dir / "representation_benchmark.json",
                 modules_dir / "module_perturbation_matrix.json"):
        artifacts.append({"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size,
                          "sha256": _sha256(path)})
    payload = {
        "protocol_version": PROTOCOL,
        "challenge": "NOSTOS-0 data-free conformance replication",
        "status": "pass" if all(gates.values()) else "fail",
        "operator": operator,
        "operator_attestation": {
            "affiliation": affiliation,
            "unaided": bool(unaided),
            "author_environment": bool(author_environment),
            "assistance": assistance,
            "source_kind": source_kind,
            "independent_execution_eligible": bool(
                operator.strip().lower() not in {"", "anonymous"}
                and affiliation.strip()
                and unaided
                and not author_environment
                and source_kind in {"fresh_clone", "release_archive"}
            ),
            "statement": "I attest that these declarations accurately describe this execution.",
        },
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version, "platform": platform.platform(),
            "nostos_version": importlib.metadata.version("nostos"),
            "git_revision": _revision(project_root),
        },
        "gates": gates,
        "artifacts": artifacts,
        "submission_rule": "Return this receipt and its three hashed artifacts without editing them.",
        "claim_boundary": "A passing receipt reproduces module truths, perturbation behavior, retained benchmark outputs, hashes and abstention semantics. It does not establish representation superiority, biological validity or clinical utility.",
    }
    receipt = output / "replication_receipt.json"
    receipt.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def verify_replication_package(receipt_path: Path, *, require_independent: bool = True) -> dict:
    """Verify artifact integrity, frozen gates and external-operator eligibility."""
    receipt_path = receipt_path.resolve()
    root = receipt_path.parent
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {
        "protocol_matches": payload.get("protocol_version") == PROTOCOL,
        "challenge_passed": payload.get("status") == "pass",
        "all_frozen_gates_passed": bool(payload.get("gates")) and all(payload.get("gates", {}).values()),
    }
    artifacts_ok = True
    for artifact in payload.get("artifacts", []):
        relative = Path(str(artifact.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            artifacts_ok = False; continue
        path = root / relative
        artifacts_ok &= path.is_file() and path.stat().st_size == artifact.get("bytes") and _sha256(path) == artifact.get("sha256")
    checks["all_artifact_hashes_match"] = bool(payload.get("artifacts")) and artifacts_ok
    attestation = payload.get("operator_attestation", {})
    checks["operator_identified"] = str(payload.get("operator", "")).strip().lower() not in {"", "anonymous"}
    checks["affiliation_declared"] = bool(str(attestation.get("affiliation", "")).strip())
    checks["fresh_external_environment_declared"] = bool(
        attestation.get("unaided") is True
        and attestation.get("author_environment") is False
        and attestation.get("source_kind") in {"fresh_clone", "release_archive"}
    )
    independent = checks["operator_identified"] and checks["affiliation_declared"] and checks["fresh_external_environment_declared"]
    integrity = all(checks[key] for key in ("protocol_matches", "challenge_passed", "all_frozen_gates_passed", "all_artifact_hashes_match"))
    status = "eligible_independent_pass" if integrity and independent else "integrity_pass_not_independent" if integrity else "fail"
    if require_independent and not independent and integrity:
        status = "fail_independence"
    return {
        "protocol_version": "nostos-external-replication-verifier/1.0",
        "status": status,
        "integrity_pass": integrity,
        "independent_execution_eligible": independent,
        "checks": checks,
        "claim_boundary": "Eligibility and integrity establish unaided external software execution only, not biological or clinical validation.",
    }
