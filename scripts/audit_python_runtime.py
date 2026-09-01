"""Create a path-safe, machine-readable NOSTOS Python runtime audit receipt."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CORE_IMPORTS = (
    "numpy",
    "scipy",
    "skimage",
    "tifffile",
    "PIL",
    "nostos",
)
PACKAGE_DISTRIBUTIONS = (
    "nostos",
    "numpy",
    "scipy",
    "scikit-image",
    "tifffile",
    "pillow",
    "pytest",
    "torch",
    "torchvision",
)


def _imports() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for name in CORE_IMPORTS:
        try:
            importlib.import_module(name)
        except Exception as error:  # pragma: no cover - diagnostic boundary
            rows[name] = {"available": False, "error_type": type(error).__name__}
        else:
            rows[name] = {"available": True, "error_type": None}
    return rows


def _versions() -> dict[str, str | None]:
    rows: dict[str, str | None] = {}
    for name in PACKAGE_DISTRIBUTIONS:
        try:
            rows[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            rows[name] = None
    return rows


def _run(command: list[str], *, cwd: Path, timeout: int) -> tuple[int, str, float]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return completed.returncode, completed.stdout, time.perf_counter() - started


def _cpu_fft() -> dict[str, Any]:
    try:
        import numpy as np

        rng = np.random.default_rng(20260829)
        data = rng.normal(size=(2048, 2048)).astype(np.float32)
        started = time.perf_counter()
        spectrum = np.fft.rfft2(data)
        elapsed = time.perf_counter() - started
        return {
            "status": "pass" if np.isfinite(spectrum).all() else "fail",
            "operation": "numpy_rfft2",
            "input_shape": [2048, 2048],
            "input_dtype": str(data.dtype),
            "output_shape": list(spectrum.shape),
            "finite": bool(np.isfinite(spectrum).all()),
            "elapsed_seconds": float(elapsed),
        }
    except Exception as error:  # pragma: no cover - diagnostic boundary
        return {"status": "fail", "error_type": type(error).__name__}


def _gpu_fft() -> dict[str, Any]:
    try:
        import torch
    except Exception as error:  # pragma: no cover - diagnostic boundary
        return {"status": "unavailable", "error_type": type(error).__name__}
    if not torch.cuda.is_available():
        return {
            "status": "unavailable",
            "torch_version": torch.__version__,
            "cuda_runtime": torch.version.cuda,
        }
    try:
        device = torch.device("cuda:0")
        generator = torch.Generator(device=device).manual_seed(20260829)
        data = torch.randn((2048, 2048), dtype=torch.float32, device=device, generator=generator)
        torch.cuda.synchronize(device)
        started = time.perf_counter()
        spectrum = torch.fft.rfft2(data)
        finite = bool(torch.isfinite(spectrum).all().item())
        torch.cuda.synchronize(device)
        elapsed = time.perf_counter() - started
        properties = torch.cuda.get_device_properties(device)
        return {
            "status": "pass" if finite else "fail",
            "operation": "torch_cuda_rfft2",
            "input_shape": [2048, 2048],
            "input_dtype": str(data.dtype).replace("torch.", ""),
            "output_shape": list(spectrum.shape),
            "finite": finite,
            "elapsed_seconds": float(elapsed),
            "device_name": torch.cuda.get_device_name(device),
            "compute_capability": list(torch.cuda.get_device_capability(device)),
            "device_memory_bytes": int(properties.total_memory),
            "torch_version": torch.__version__,
            "cuda_runtime": torch.version.cuda,
            "cudnn_version": torch.backends.cudnn.version(),
        }
    except Exception as error:  # pragma: no cover - diagnostic boundary
        return {"status": "fail", "error_type": type(error).__name__}


def _pytest_summary(output: str) -> dict[str, int | None]:
    passed = re.search(r"(\d+) passed", output)
    skipped = re.search(r"(\d+) skipped", output)
    failed = re.search(r"(\d+) failed", output)
    warnings = re.search(r"(\d+) warnings?", output)
    return {
        "passed": None if passed is None else int(passed.group(1)),
        "skipped": 0 if skipped is None else int(skipped.group(1)),
        "failed": 0 if failed is None else int(failed.group(1)),
        "warnings": 0 if warnings is None else int(warnings.group(1)),
    }


def audit(
    root: Path,
    *,
    runtime_label: str,
    run_tests: bool,
    require_gpu: bool,
    output: Path,
) -> dict[str, Any]:
    imports = _imports()
    versions = _versions()
    uv_path = shutil.which("uv")
    if uv_path is not None:
        dependency_command = [uv_path, "pip", "check", "--python", sys.executable]
        dependency_tool = "uv_pip_check"
    else:
        dependency_command = [sys.executable, "-m", "pip", "check"]
        dependency_tool = "python_pip_check"
    pip_code, pip_output, pip_seconds = _run(dependency_command, cwd=root, timeout=300)
    cpu = _cpu_fft()
    gpu = _gpu_fft()
    tests: dict[str, Any]
    if run_tests:
        test_code, test_output, test_seconds = _run(
            [sys.executable, "-m", "pytest", "-q"], cwd=root, timeout=1800
        )
        tests = {
            "status": "pass" if test_code == 0 else "fail",
            "exit_code": test_code,
            "elapsed_seconds": float(test_seconds),
            **_pytest_summary(test_output),
        }
    else:
        tests = {"status": "not_run", "reason": "probe_only"}

    checks = {
        "core_imports": all(row["available"] for row in imports.values()),
        "dependency_consistency": pip_code == 0,
        "cpu_fft_finite": cpu["status"] == "pass",
        "gpu_fft_finite_if_required": (not require_gpu) or gpu["status"] == "pass",
        "full_test_suite": (not run_tests) or tests["status"] == "pass",
    }
    payload = {
        "schema_version": "nostos-python-runtime-audit/1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_label": runtime_label,
        "status": "verified_pass" if all(checks.values()) else "incompatible",
        "checks": checks,
        "environment": {
            "python_version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "operating_system": platform.system(),
            "operating_system_release": platform.release(),
            "machine": platform.machine(),
            "environment_name": Path(sys.prefix).name,
            "absolute_paths_recorded": False,
        },
        "imports": imports,
        "package_versions": versions,
        "dependency_check": {
            "status": "pass" if pip_code == 0 else "fail",
            "tool": dependency_tool,
            "exit_code": pip_code,
            "elapsed_seconds": float(pip_seconds),
            "summary": pip_output.strip().splitlines()[-1] if pip_output.strip() else "",
        },
        "cpu_smoke": cpu,
        "gpu_smoke": gpu,
        "tests": tests,
        "interpretation": (
            "This receipt verifies software execution and numerical finiteness in one runtime. "
            "It does not establish measurement validity on a new acquisition, clinical utility, "
            "diagnostic performance or intraoperative acquisition latency."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--runtime-label", required=True)
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--require-gpu", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    payload = audit(
        root,
        runtime_label=args.runtime_label,
        run_tests=args.run_tests,
        require_gpu=args.require_gpu,
        output=(root / args.output).resolve(),
    )
    print(
        json.dumps(
            {
                "runtime_label": payload["runtime_label"],
                "status": payload["status"],
                "checks": payload["checks"],
                "tests": payload["tests"],
                "gpu": payload["gpu_smoke"]["status"],
            },
            indent=2,
        )
    )
    if payload["status"] != "verified_pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
