"""Build a content-addressed manifest without interpreting SHG image pixels."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha256_file(path: Path, chunk_bytes: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(root: Path, *args: str) -> str:
    command = [
        "git",
        "-c",
        f"safe.directory={root.as_posix()}",
        "-C",
        str(root),
        *args,
    ]
    return subprocess.check_output(command, text=True).strip()


def build_manifest(root: Path) -> dict[str, object]:
    raw_root = root / "Raw SHG Images"
    files = []
    for path in sorted(raw_root.rglob("*.tif"), key=lambda item: item.as_posix().casefold()):
        relative = path.relative_to(root).as_posix()
        parts = path.relative_to(raw_root).parts
        if len(parts) < 3 or parts[0] not in {"Exp10", "Exp15"}:
            raise ValueError(f"Unexpected raw-image path: {relative}")
        files.append(
            {
                "path": relative,
                "experiment": parts[0],
                "mouse": parts[1],
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    counts = {
        experiment: sum(item["experiment"] == experiment for item in files)
        for experiment in ("Exp10", "Exp15")
    }
    mice = {
        experiment: len({item["mouse"] for item in files if item["experiment"] == experiment})
        for experiment in ("Exp10", "Exp15")
    }
    if counts != {"Exp10": 34, "Exp15": 45} or mice != {"Exp10": 8, "Exp15": 8}:
        raise ValueError(f"Unexpected dataset topology: fields={counts}, mice={mice}")
    return {
        "schema_version": "nostos.heaton_in_vivo_shg.files.v1",
        "repository": git_value(root, "remote", "get-url", "origin"),
        "commit": git_value(root, "rev-parse", "HEAD"),
        "raw_image_counts": counts,
        "mouse_counts": mice,
        "files": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.dataset.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "files": len(manifest["files"])}, indent=2))


if __name__ == "__main__":
    main()

