"""Audit whether named external comparators are actually runnable."""
from __future__ import annotations

import importlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path


def _package_gate(distribution: str, module: str, reference: str) -> dict:
    try:
        version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return {"distribution": distribution, "module": module, "installed": False,
                "importable": False, "version": None, "reference_conformance": reference,
                "error": "distribution_not_installed"}
    try:
        importlib.import_module(module)
    except Exception as exc:  # third-party import failures are the audit result
        return {"distribution": distribution, "module": module, "installed": True,
                "importable": False, "version": version, "reference_conformance": reference,
                "error": f"{type(exc).__name__}: {exc}"}
    return {"distribution": distribution, "module": module, "installed": True,
            "importable": True, "version": version, "reference_conformance": reference,
            "error": None}


def _probe_with_interpreter(python_executable: Path, distribution: str, module: str, reference: str) -> dict:
    script = (
        "import importlib,importlib.metadata,json; "
        f"d={distribution!r}; m={module!r}; "
        "v=importlib.metadata.version(d); mod=importlib.import_module(m); "
        "print(json.dumps({'distribution_version':v,'module_version':getattr(mod,'__version__',None)}))"
    )
    completed = subprocess.run(
        [str(python_executable), "-c", script], capture_output=True, text=True, check=False
    )
    if completed.returncode:
        error = (completed.stderr.strip().splitlines() or ["unknown_probe_error"])[-1]
        return {"distribution": distribution, "module": module, "installed": "PackageNotFoundError" not in completed.stderr,
                "importable": False, "version": None, "reference_conformance": reference,
                "error": error, "interpreter": str(python_executable)}
    versions = json.loads(completed.stdout.strip())
    return {"distribution": distribution, "module": module, "installed": True,
            "importable": True, "version": versions["distribution_version"],
            "module_version": versions["module_version"], "reference_conformance": reference,
            "error": None, "interpreter": str(python_executable)}


def write_comparator_conformance_receipt(
    output: Path,
    comparator_python: Path | None = None,
    *,
    kymatio_python: Path | None = None,
    pyradiomics_python: Path | None = None,
) -> dict:
    references = [
        ("kymatio", "kymatio.numpy", "Official Kymatio Scattering2D; no local substitute is admissible."),
        ("pyradiomics", "radiomics", "IBSI digital phantom/reference values; PyRadiomics differences must be disclosed."),
    ]
    selected = [kymatio_python or comparator_python, pyradiomics_python or comparator_python]
    gates = [
        _package_gate(*item) if python is None else _probe_with_interpreter(python, *item)
        for item, python in zip(references, selected, strict=True)
    ]
    interpreters = [str(python or sys.executable) for python in selected]
    payload = {
        "protocol_version": "nostos-comparator-conformance/1.0",
        "python": platform.python_version(),
        "comparator_interpreters": {gate["distribution"]: interpreter for gate, interpreter in zip(gates, interpreters, strict=True)},
        "platform": platform.platform(),
        "status": "pass" if all(gate["importable"] for gate in gates) else "fail",
        "gates": gates,
        "claim_rule": ("NOSTOS outputs may not be called IBSI radiomics or wavelet scattering "
                       "unless the corresponding upstream implementation and reference checks pass."),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparator_conformance.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return payload
