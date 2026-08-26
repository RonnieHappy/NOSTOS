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


PROTOCOL = "nostos-external-replication/1.0"


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


def run_replication_challenge(output: Path, project_root: Path, operator: str = "anonymous") -> dict:
    """Regenerate the frozen foundations and write a self-verifying receipt."""
    output.mkdir(parents=True, exist_ok=True)
    synthetic_dir = output / "synthetic"
    benchmark_dir = output / "benchmark"
    modules_dir = output / "modules"
    synthetic = run_frozen_validation(synthetic_dir)
    benchmark = write_benchmark_receipt(benchmark_dir)
    modules = run_module_perturbation_matrix(modules_dir)

    accuracies = {row["representation"]: row["balanced_accuracy"] for row in benchmark["results"]}
    gates = {
        "synthetic_protocol_passes": synthetic["status"] == "pass",
        "nine_truth_constructs_registered": synthetic["summary"]["constructs_registered"] == 9,
        "all_five_module_gates_pass": synthetic["summary"]["module_gates_passed"] == synthetic["summary"]["module_gates_total"] == 5,
        "all_24_required_perturbation_tests_pass": modules["summary"]["passed"] == modules["summary"]["required_tests"] == 24,
        "mask_tests_retained_as_sensitivity": modules["summary"]["mask_sensitivity_tests"] == 2,
        "frozen_response_accuracy_reproduced": accuracies.get("nostos_response_curves") == 1.0,
        "frozen_conventional_accuracy_reproduced": accuracies.get("conventional_scalar") == 0.9375,
        "frozen_naive_accuracy_reproduced": accuracies.get("naive_response_summaries") == 0.9375,
    }
    artifacts = []
    for path in (synthetic_dir / "validation.json", benchmark_dir / "representation_benchmark.json",
                 modules_dir / "module_perturbation_matrix.json"):
        artifacts.append({"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size,
                          "sha256": _sha256(path)})
    payload = {
        "protocol_version": PROTOCOL,
        "challenge": "NOSTOS-0 data-free frozen-foundation replication",
        "status": "pass" if all(gates.values()) else "fail",
        "operator": operator,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version, "platform": platform.platform(),
            "nostos_version": importlib.metadata.version("nostos"),
            "git_revision": _revision(project_root),
        },
        "gates": gates,
        "artifacts": artifacts,
        "submission_rule": "Return this receipt and its three hashed artifacts without editing them.",
        "claim_boundary": "A passing receipt establishes independent software execution only; it does not establish independent biological validation or clinical utility.",
    }
    receipt = output / "replication_receipt.json"
    receipt.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
