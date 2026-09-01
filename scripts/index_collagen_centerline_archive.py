"""Index the collagen-centerline ZIP without reading any member payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            value.update(block)
    return value.hexdigest()


def index_archive(archive: Path, output: Path) -> dict:
    with zipfile.ZipFile(archive) as bundle:
        entries = [
            {
                "name": item.filename,
                "bytes": item.file_size,
                "compressed_bytes": item.compress_size,
                "crc32": f"{item.CRC:08x}",
            }
            for item in bundle.infolist()
            if not item.is_dir()
        ]
    prefix = "collagen-centerlines/final_train_test/"
    counts = {}
    ids = {}
    for split in ("train", "test"):
        for role in ("images", "labels", "overlays", "properties"):
            ending = ".json" if role == "properties" else ".png"
            key = f"{split}_{role}"
            selected = [
                item["name"]
                for item in entries
                if item["name"].startswith(f"{prefix}{split}/{role}/")
                and item["name"].endswith(ending)
            ]
            counts[key] = len(selected)
            ids[key] = sorted(int(Path(name).stem) for name in selected)
    expected = {
        "train_images": 1188,
        "train_labels": 1188,
        "train_overlays": 1188,
        "train_properties": 1188,
        "test_images": 199,
        "test_labels": 199,
        "test_overlays": 199,
        "test_properties": 199,
    }
    checks = {
        "expected_counts": counts == expected,
        "train_roles_aligned": all(ids[f"train_{role}"] == ids["train_images"] for role in ("labels", "overlays", "properties")),
        "test_roles_aligned": all(ids[f"test_{role}"] == ids["test_images"] for role in ("labels", "overlays", "properties")),
        "no_member_payload_opened": True,
    }
    payload = {
        "schema_version": "nostos.collagen_centerline_archive_index.v1",
        "status": "pass" if all(checks.values()) else "fail",
        "record": {
            "zenodo_id": 7243211,
            "doi": "10.5281/zenodo.7243211",
            "license": "CC-BY-4.0",
        },
        "archive": {
            "name": archive.name,
            "bytes": archive.stat().st_size,
            "md5": digest(archive, "md5"),
            "sha256": digest(archive, "sha256"),
        },
        "counts": counts,
        "train_ids": ids["train_images"],
        "test_ids": ids["test_images"],
        "checks": checks,
        "central_directory_entries": entries,
        "claim_boundary": "ZIP central-directory metadata only; no image, label, overlay or property member payload was read by this indexer.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = index_archive(args.archive.resolve(), args.output.resolve())
    print(json.dumps({"status": result["status"], "counts": result["counts"], "sha256": result["archive"]["sha256"]}, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
