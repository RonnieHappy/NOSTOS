"""Execute and repeat the frozen NOSTOS physical-truth benchmark v2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nostos.validation.synthetic_physical_truth_v2 import (
    build_synthetic_physical_truth_v2,
)


ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "outputs/nostos0-synthetic-physical-truth-v2/validation.json"
REPEAT = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-repeat/validation.json"


def _canonical(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _finalize(payload: dict, repeat_identical: bool) -> dict:
    result = dict(payload)
    result.pop("content_sha256", None)
    gates = dict(result.pop("success_gates_before_repeat"))
    gates["byte_identical_independent_repeat"] = repeat_identical
    result.pop("status_before_repeat_gate", None)
    result["execution_reproducibility"] = {
        "independent_recomputation": True,
        "canonical_payloads_identical_before_repeat_annotation": repeat_identical,
    }
    result["success_gates"] = gates
    result["status"] = "pass" if all(gates.values()) else "fail"
    result["content_sha256"] = hashlib.sha256(_canonical(result)).hexdigest()
    return result


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    first = build_synthetic_physical_truth_v2(ROOT)
    second = build_synthetic_physical_truth_v2(ROOT)
    repeat_identical = _canonical(first) == _canonical(second)
    finalized = _finalize(first, repeat_identical)
    _write(PRIMARY, finalized)
    _write(REPEAT, finalized)
    primary_sha256 = hashlib.sha256(PRIMARY.read_bytes()).hexdigest()
    repeat_sha256 = hashlib.sha256(REPEAT.read_bytes()).hexdigest()
    if primary_sha256 != repeat_sha256:
        raise RuntimeError("Final output files are not byte-identical")
    print(
        json.dumps(
            {
                "status": finalized["status"],
                "metrics": finalized["metrics"],
                "success_gates": finalized["success_gates"],
                "primary_sha256": primary_sha256,
                "repeat_sha256": repeat_sha256,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
