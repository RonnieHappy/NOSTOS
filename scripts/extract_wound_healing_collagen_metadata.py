"""Extract only README/CSV/fold metadata from the wound-healing archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath


ROOT = PurePosixPath("Wound_Healing_Collagen_Dataset")
MAX_MEMBER_BYTES = 100_000


def is_allowed(name: str) -> bool:
    path = PurePosixPath(name)
    if path == ROOT / "README.md":
        return True
    if path in {
        ROOT / "SHG_dataset" / "SHG_image_metadata.csv",
        ROOT / "MT_dataset" / "MT_image_metadata.csv",
    }:
        return True
    parents = {
        ROOT / "SHG_dataset" / "SHG_animal_level_cross_validation_splits",
        ROOT / "MT_dataset" / "MT_animal_level_cross_validation_splits",
    }
    return path.parent in parents and path.suffix == ".txt" and path.name.startswith("fold")


def _safe_target(output: Path, member_name: str) -> Path:
    relative = Path(*PurePosixPath(member_name).parts)
    target = (output / relative).resolve()
    root = output.resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"Unsafe archive member path: {member_name}")
    return target


def extract_metadata(archive: Path, output: Path, manifest: Path) -> dict:
    records = []
    with zipfile.ZipFile(archive) as bundle:
        selected = [item for item in bundle.infolist() if not item.is_dir() and is_allowed(item.filename)]
        for item in selected:
            if item.file_size > MAX_MEMBER_BYTES:
                raise ValueError(f"Metadata member exceeds {MAX_MEMBER_BYTES} bytes: {item.filename}")
            payload = bundle.read(item)
            target = _safe_target(output, item.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            records.append({
                "member": item.filename,
                "bytes": len(payload),
                "crc32": f"{item.CRC:08x}",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "output": target.relative_to(output.resolve()).as_posix(),
            })
    expected = 21
    checks = {
        "expected_metadata_members": len(records) == expected,
        "readme_present": sum(row["member"].endswith("/README.md") for row in records) == 1,
        "metadata_csvs_present": sum(row["member"].endswith("_image_metadata.csv") for row in records) == 2,
        "fold_lists_present": sum(row["member"].endswith(".txt") for row in records) == 18,
        "no_image_member_payload_opened": True,
    }
    result = {
        "schema_version": "nostos.wound_healing_collagen_metadata_extract.v1",
        "status": "pass" if all(checks.values()) else "fail",
        "archive": str(archive),
        "members": records,
        "checks": checks,
        "claim_boundary": (
            "Only README.md, the two image-metadata CSV files and deposited animal-level fold text files "
            "were read. No PNG/JPEG image member payload was opened."
        ),
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = extract_metadata(args.archive.resolve(), args.output.resolve(), args.manifest.resolve())
    print(json.dumps({"status": result["status"], "members": len(result["members"]), "checks": result["checks"]}, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
