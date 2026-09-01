"""Verify a NOSTOS release archive in a fresh, temporary Python environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except OSError as error:
        return {
            "exit_code": 127,
            "elapsed_seconds": float(time.perf_counter() - started),
            "output": f"{type(error).__name__}: {error}",
        }
    return {
        "exit_code": completed.returncode,
        "elapsed_seconds": float(time.perf_counter() - started),
        "output": completed.stdout,
    }


def _wait_for_file(path: Path, *, timeout: float = 30.0) -> dict[str, Any]:
    """Wait for a newly synchronized executable to become visible on slow media."""

    started = time.perf_counter()
    deadline = started + timeout
    while time.perf_counter() <= deadline:
        if path.is_file():
            return {
                "ready": True,
                "elapsed_seconds": float(time.perf_counter() - started),
            }
        time.sleep(0.1)
    return {
        "ready": False,
        "elapsed_seconds": float(time.perf_counter() - started),
    }


def _safe_extract(archive: Path, destination: Path) -> Path:
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        roots: set[str] = set()
        for member in bundle.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"Unsafe archive member: {member.filename}")
            roots.add(member_path.parts[0])
            target = (destination / member_path).resolve()
            if target != destination_resolved and destination_resolved not in target.parents:
                raise ValueError(f"Archive member escapes extraction root: {member.filename}")
        if len(roots) != 1:
            raise ValueError("Release archive must contain exactly one top-level directory.")
        bundle.extractall(destination)
    return destination / next(iter(roots))


def _parse_test_summary(output: str) -> dict[str, int]:
    def count(pattern: str, default: int = 0) -> int:
        match = re.search(pattern, output)
        return default if match is None else int(match.group(1))

    return {
        "passed": count(r"(\d+) passed"),
        "skipped": count(r"(\d+) skipped"),
        "failed": count(r"(\d+) failed"),
        "warnings": count(r"(\d+) warnings?"),
    }


def _manifest_integrity(project: Path) -> dict[str, Any]:
    manifest_path = project / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad: list[str] = []
    for item in manifest["files"]:
        path = project / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or _sha256(path) != item["sha256"]
        ):
            bad.append(item["path"])
    observed = {
        path.relative_to(project).as_posix()
        for path in project.rglob("*")
        if path.is_file() and ".venv" not in path.parts
    }
    expected = {item["path"] for item in manifest["files"]} | {"release_manifest.json"}
    return {
        "status": "pass" if not bad and observed == expected else "fail",
        "manifest_status": manifest.get("status"),
        "data_included": manifest.get("data_included"),
        "declared_files_excluding_manifest": len(manifest["files"]),
        "bad_files": bad,
        "unregistered_files": sorted(observed - expected),
        "missing_files": sorted(expected - observed),
        "audit_findings": len(manifest.get("audit_findings", [])),
        "software_version": manifest.get("software_version"),
    }


def verify(archive: Path, output: Path, work_root: Path, *, keep_workdir: bool) -> dict[str, Any]:
    archive = archive.resolve()
    work_root = work_root.resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="nostos-cleanroom-", dir=work_root))
    project: Path | None = None
    try:
        project = _safe_extract(archive, temporary)
        manifest = _manifest_integrity(project)
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError("uv is required for frozen clean-room verification.")
        install = _run(
            [uv, "sync", "--extra", "dev", "--frozen", "--link-mode", "copy"],
            cwd=project,
            timeout=1800,
        )
        python = project / ".venv" / "Scripts" / "python.exe"
        interpreter = (
            _wait_for_file(python)
            if install["exit_code"] == 0
            else {"ready": False, "elapsed_seconds": 0.0}
        )
        tests = _run([str(python), "-m", "pytest", "-q"], cwd=project, timeout=1800)
        test_counts = _parse_test_summary(tests["output"])
        doctor = _run([str(python), "-m", "nostos.cli", "doctor"], cwd=project, timeout=300)
        try:
            doctor_payload = json.loads(doctor["output"])
        except json.JSONDecodeError:
            doctor_payload = {"status": "unparseable"}
        dependency = _run(
            [uv, "pip", "check", "--python", str(python)], cwd=project, timeout=300
        )
        version = _run(
            [str(python), "-c", "import importlib.metadata; print(importlib.metadata.version('nostos'))"],
            cwd=project,
            timeout=60,
        )
        second_output = temporary / "second-build"
        rebuild = _run(
            [
                str(python),
                "-m",
                "nostos.release",
                "--project-root",
                str(project),
                "--output",
                str(second_output),
            ],
            cwd=project,
            timeout=900,
        )
        second_archive = second_output / archive.name
        deterministic_hash = _sha256(second_archive) if second_archive.is_file() else None
        checks = {
            "safe_extraction": True,
            "manifest_integrity": manifest["status"] == "pass",
            "release_audit_passed": manifest["manifest_status"] == "pass"
            and manifest["data_included"] is False
            and manifest["audit_findings"] == 0,
            "frozen_install": install["exit_code"] == 0,
            "environment_interpreter_ready": interpreter["ready"] is True,
            "packaged_tests": tests["exit_code"] == 0 and test_counts["passed"] > 0,
            "doctor_ready": doctor["exit_code"] == 0 and doctor_payload.get("status") == "ready",
            "dependency_consistency": dependency["exit_code"] == 0,
            "runtime_version": version["exit_code"] == 0
            and version["output"].strip() == manifest["software_version"],
            "deterministic_second_build": rebuild["exit_code"] == 0
            and deterministic_hash == _sha256(archive),
        }
        payload = {
            "schema_version": "nostos-cleanroom-verification/2.0",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "verified_pass" if all(checks.values()) else "verification_fail",
            "archive": {
                "name": archive.name,
                "bytes": archive.stat().st_size,
                "sha256": _sha256(archive),
            },
            "checks": checks,
            "verification": {
                "release_manifest": manifest,
                "installation": {
                    "tool": "uv sync --extra dev --frozen --link-mode copy",
                    "exit_code": install["exit_code"],
                    "elapsed_seconds": install["elapsed_seconds"],
                    "interpreter_ready": interpreter["ready"],
                    "interpreter_visibility_wait_seconds": interpreter[
                        "elapsed_seconds"
                    ],
                },
                "pytest": {
                    **test_counts,
                    "exit_code": tests["exit_code"],
                    "elapsed_seconds": tests["elapsed_seconds"],
                },
                "nostos_doctor": {
                    "status": doctor_payload.get("status"),
                    "exit_code": doctor["exit_code"],
                },
                "dependency_check": {
                    "status": "pass" if dependency["exit_code"] == 0 else "fail",
                    "exit_code": dependency["exit_code"],
                },
                "installed_version": version["output"].strip(),
                "deterministic_second_build_sha256": deterministic_hash,
            },
            "work_directory_retained": keep_workdir,
            "absolute_work_path_recorded": False,
            "scope": (
                "Author-operated clean-room installation, package integrity and execution only. "
                "This is not unaided external replication, new-acquisition validation or clinical validation."
            ),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return payload
    finally:
        if not keep_workdir:
            resolved = temporary.resolve()
            if resolved.parent == work_root and resolved.name.startswith("nostos-cleanroom-"):
                shutil.rmtree(resolved, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--keep-workdir", action="store_true")
    args = parser.parse_args()
    payload = verify(
        args.archive,
        args.output,
        args.work_root,
        keep_workdir=args.keep_workdir,
    )
    print(json.dumps({"status": payload["status"], "checks": payload["checks"], "pytest": payload["verification"]["pytest"]}, indent=2))
    if payload["status"] != "verified_pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
