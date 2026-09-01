from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from nostos.intraop.label_free_v1_2 import analyze_pshg_directory, analyze_unstained_field


BASE_RUNNER = Path(__file__).with_name("run_intraop_pshg_deployment_benchmark.py")
SPEC = importlib.util.spec_from_file_location("nostos_intraop_deployment_v1_runner", BASE_RUNNER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load the immutable v1 benchmark runner: {BASE_RUNNER}")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.analyze_pshg_directory = analyze_pshg_directory
BASE.analyze_unstained_field = analyze_unstained_field


class _V12JsonAdapter:
    """Translate only the amended lock state for the immutable v1 evaluator."""

    @staticmethod
    def loads(value: str):
        payload = json.loads(value)
        if payload.get("schema_version") == "nostos-intraop-pshg-deployment-lock/1.2":
            if payload.get("status") != "locked_before_reference_error_evaluation":
                raise ValueError("The v1.2 lock is not frozen before reference-error evaluation.")
            payload = dict(payload)
            payload["amended_lock_status"] = payload["status"]
            payload["status"] = "locked_before_selected_pixel_decode"
        return payload

    @staticmethod
    def dumps(*args, **kwargs):
        return json.dumps(*args, **kwargs)


BASE.json = _V12JsonAdapter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/intraop_pshg_deployment_benchmark_v1_2.locked.json"),
    )
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path("manifests/intraop_pshg_deployment_v1_2_lock.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/nostos0-intraop-pshg-deployment-v1_2"),
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    result = BASE.run_benchmark(
        root,
        args.dataset_root.resolve(),
        args.output.resolve(),
        config_path=(root / args.config).resolve(),
        lock_path=(root / args.lock).resolve(),
    )
    print(json.dumps({"status": result["status"], **result["summary"]}, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
