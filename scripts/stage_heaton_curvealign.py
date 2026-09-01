"""Stage canonical SHG inputs for the official CurveAlign/CT-FIRE executable."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


VENDOR_FILES = ("CAP_cluster.txt", "CTFP_cluster.txt", "CAroiP_cluster.txt")


def sha256_file(path: Path, chunk_bytes: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def stage(
    dataset: Path,
    vendor_root: Path,
    destination: Path,
    *,
    experiment: str,
    confirmation_lock: Path | None,
) -> dict[str, object]:
    if experiment not in {"Exp10", "Exp15"}:
        raise ValueError("experiment must be Exp10 or Exp15.")
    if experiment == "Exp15":
        if confirmation_lock is None or not confirmation_lock.is_file():
            raise PermissionError("Exp15 staging requires an existing confirmation lock.")
        lock = json.loads(confirmation_lock.read_text(encoding="utf-8"))
        if lock.get("status") != "locked_confirmation_authorized":
            raise PermissionError("The supplied profile does not authorize confirmation.")
    source_root = dataset / "Raw SHG Images" / experiment
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.glob("*.tif")):
        raise FileExistsError(f"Destination already contains TIFF files: {destination}")
    rows = []
    for mouse_root in sorted(source_root.iterdir(), key=lambda item: item.name.casefold()):
        if not mouse_root.is_dir():
            continue
        for index, source in enumerate(sorted(mouse_root.glob("*.tif"), key=lambda item: item.name.casefold()), start=1):
            staged_name = f"{experiment}__{mouse_root.name}__FOV{index:02d}.tif"
            target = destination / staged_name
            shutil.copy2(source, target)
            source_hash = sha256_file(source)
            if sha256_file(target) != source_hash:
                raise IOError(f"Staged copy failed hash verification: {source}")
            rows.append(
                {
                    "experiment": experiment,
                    "mouse": mouse_root.name,
                    "source": source.relative_to(dataset).as_posix(),
                    "staged_name": staged_name,
                    "field_stem": target.stem,
                    "bytes": target.stat().st_size,
                    "sha256": source_hash,
                }
            )
    expected = 34 if experiment == "Exp10" else 45
    if len(rows) != expected:
        raise ValueError(f"Expected {expected} {experiment} fields, found {len(rows)}.")
    vendor_hashes = {}
    for name in VENDOR_FILES:
        source = vendor_root / name
        if not source.is_file():
            raise FileNotFoundError(source)
        target = destination / name
        shutil.copy2(source, target)
        vendor_hashes[name] = sha256_file(target)
    receipt = {
        "schema_version": "nostos.heaton_curvealign_stage.v1",
        "experiment": experiment,
        "fields": len(rows),
        "mice": len({row["mouse"] for row in rows}),
        "vendor_parameter_sha256": vendor_hashes,
        "confirmation_lock": str(confirmation_lock) if confirmation_lock else None,
        "rows": rows,
    }
    receipt_path = destination / "stage_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--vendor-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--experiment", choices=("Exp10", "Exp15"), required=True)
    parser.add_argument("--confirmation-lock", type=Path)
    args = parser.parse_args()
    result = stage(
        args.dataset.resolve(),
        args.vendor_root.resolve(),
        args.destination.resolve(),
        experiment=args.experiment,
        confirmation_lock=args.confirmation_lock,
    )
    print(json.dumps({"experiment": result["experiment"], "fields": result["fields"]}, indent=2))


if __name__ == "__main__":
    main()

