"""Run and receipt the official CurveAlign/CT-FIRE command-line executable."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(executable: Path, stage: Path, mode: int, image_index: str) -> dict[str, object]:
    command = [str(executable), str(stage), ".tif", str(mode), image_index]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=executable.parent,
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"Official CurveAlign mode {mode} failed with code {completed.returncode}:\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return {
        "command": command,
        "mode": mode,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run(executable: Path, stage: Path, output_receipt: Path, image_index: str) -> dict[str, object]:
    if not executable.is_file():
        raise FileNotFoundError(executable)
    stage_receipt = json.loads((stage / "stage_receipt.json").read_text(encoding="utf-8"))
    if stage_receipt.get("status") != "development_stage_parameters_locked" and stage_receipt.get("status") != "confirmation_stage_parameters_locked":
        raise PermissionError("The stage parameters have not been locked.")
    input_hashes = {
        path.name: sha256_file(path) for path in sorted(stage.glob("*.tif"))
    }
    runs = [_run(executable, stage, mode, image_index) for mode in (1, 2)]
    outputs = []
    for path in sorted(stage.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not path.is_file() or path.name == "stage_receipt.json" or path.suffix.lower() == ".tif" and path.parent == stage:
            continue
        if path.name in {"CAP_cluster.txt", "CTFP_cluster.txt", "CAroiP_cluster.txt"}:
            continue
        outputs.append(
            {
                "path": path.relative_to(stage).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    payload = {
        "schema_version": "nostos.official_curvealign_run.v1",
        "executable": str(executable),
        "executable_sha256": sha256_file(executable),
        "stage": str(stage),
        "stage_receipt_sha256_before_run": sha256_file(stage / "stage_receipt.json"),
        "image_index": image_index,
        "input_images": len(input_hashes),
        "input_sha256": input_hashes,
        "runs": runs,
        "output_files": outputs,
        "output_file_count": len(outputs),
        "status": "complete",
    }
    output_receipt.parent.mkdir(parents=True, exist_ok=True)
    output_receipt.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--image-index", default="all")
    args = parser.parse_args()
    result = run(
        args.executable.resolve(),
        args.stage.resolve(),
        args.receipt.resolve(),
        args.image_index,
    )
    print(json.dumps({"status": result["status"], "outputs": result["output_file_count"]}, indent=2))


if __name__ == "__main__":
    main()

