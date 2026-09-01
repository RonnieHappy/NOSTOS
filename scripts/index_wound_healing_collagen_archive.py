"""Index the wound-healing collagen ZIP without reading member payloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path


RECORD_ID = 22161880
RECORD_DOI = "10.5281/zenodo.22161880"
EXPECTED_MD5 = "4f55b224dd15ce220fab22db29d6d6bd"
SHG_PATTERN = re.compile(
    r"^Wound_Healing_Collagen_Dataset/SHG_dataset/SHG_images/"
    r"(?P<day>[^/]+)/(?P<animal>mice\d+)/(?P<name>[^/]+\.png)$",
    re.IGNORECASE,
)
MT_PATTERN = re.compile(
    r"^Wound_Healing_Collagen_Dataset/MT_dataset/MT_images/"
    r"(?P<group>[^/]+)/(?P<animal>mice\d+)/(?P<name>[^/]+\.jpg)$",
    re.IGNORECASE,
)


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

    shg_rows = []
    mt_rows = []
    for item in entries:
        shg_match = SHG_PATTERN.match(item["name"])
        if shg_match:
            row = shg_match.groupdict()
            shg_rows.append({**row, "animal_key": f"{row['day']}/{row['animal']}"})
        mt_match = MT_PATTERN.match(item["name"])
        if mt_match:
            row = mt_match.groupdict()
            mt_rows.append({**row, "animal_key": f"{row['group']}/{row['animal']}"})

    shg_fold_files = sorted(
        item["name"]
        for item in entries
        if "/SHG_animal_level_cross_validation_splits/" in item["name"]
        and item["name"].endswith(".txt")
    )
    mt_fold_files = sorted(
        item["name"]
        for item in entries
        if "/MT_animal_level_cross_validation_splits/" in item["name"]
        and item["name"].endswith(".txt")
    )
    metadata_files = sorted(
        item["name"]
        for item in entries
        if Path(item["name"]).name in {"README.md", "SHG_image_metadata.csv", "MT_image_metadata.csv"}
    )
    md5 = digest(archive, "md5")
    checks = {
        "record_md5_matches": md5 == EXPECTED_MD5,
        "shg_image_count_188": len(shg_rows) == 188,
        "shg_animal_count_38": len({row["animal_key"] for row in shg_rows}) == 38,
        "shg_timepoints_exact": set(row["day"] for row in shg_rows) == {"0day", "3day", "7day", "10day"},
        "shg_four_fold_train_test_files": len(shg_fold_files) == 8,
        "mt_image_count_521": len(mt_rows) == 521,
        "mt_animal_count_80": len({row["animal_key"] for row in mt_rows}) == 80,
        "mt_five_fold_train_test_files": len(mt_fold_files) == 10,
        "metadata_files_present": len(metadata_files) == 3,
        "no_member_payload_opened": True,
    }
    payload = {
        "schema_version": "nostos.wound_healing_collagen_archive_index.v1",
        "status": "pass" if all(checks.values()) else "fail",
        "record": {
            "zenodo_id": RECORD_ID,
            "doi": RECORD_DOI,
            "title": "Wound-Healing Collagen Fiber Imaging Dataset",
            "record_publication_date": "2026-08-29",
            "license": None,
            "license_status": "not_declared_in_record_metadata_at_prelock",
        },
        "archive": {
            "name": archive.name,
            "bytes": archive.stat().st_size,
            "md5": md5,
            "sha256": digest(archive, "sha256"),
        },
        "counts": {
            "entries": len(entries),
            "shg_images": len(shg_rows),
            "shg_animals": len({row["animal_key"] for row in shg_rows}),
            "shg_images_by_timepoint": dict(sorted(Counter(row["day"] for row in shg_rows).items())),
            "shg_animals_by_timepoint": {
                day: len({row["animal_key"] for row in shg_rows if row["day"] == day})
                for day in sorted({row["day"] for row in shg_rows})
            },
            "mt_images": len(mt_rows),
            "mt_animals": len({row["animal_key"] for row in mt_rows}),
        },
        "shg_fold_files": shg_fold_files,
        "mt_fold_files": mt_fold_files,
        "metadata_files": metadata_files,
        "shg_member_names": [item["name"] for item in entries if SHG_PATTERN.match(item["name"])],
        "checks": checks,
        "central_directory_entries": entries,
        "claim_boundary": (
            "ZIP central-directory metadata only. No README, CSV, fold-list, image, label or other member "
            "payload was read by this indexer. Timepoint and animal counts were parsed from member names."
        ),
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
    print(json.dumps({
        "status": result["status"],
        "counts": result["counts"],
        "sha256": result["archive"]["sha256"],
        "checks": result["checks"],
    }, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
