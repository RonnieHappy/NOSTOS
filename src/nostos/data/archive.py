from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def identify_archive(path: str | Path) -> str:
    with Path(path).open("rb") as stream:
        signature = stream.read(8)
    if signature.startswith(b"PK\x03\x04") or signature.startswith(b"PK\x05\x06"):
        return "zip"
    if signature.startswith(b"\x1f\x8b"):
        return "tar.gz"
    if signature.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7z"
    if tarfile.is_tarfile(path):
        return "tar"
    return "unknown"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _safe_member(name: str) -> bool:
    member = PurePosixPath(name.replace("\\", "/"))
    return not member.is_absolute() and ".." not in member.parts and not (member.parts and ":" in member.parts[0])


def validate_archive(path: str | Path) -> dict[str, int | str]:
    path = Path(path)
    kind = identify_archive(path)
    if kind == "zip":
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            unsafe = [member.filename for member in members if not _safe_member(member.filename)]
            if unsafe:
                raise ValueError(f"unsafe archive members: {unsafe[:5]}")
            corrupt = archive.testzip()
            if corrupt:
                raise ValueError(f"CRC failure in archive member: {corrupt}")
            return {"format": kind, "member_count": len(members), "uncompressed_bytes": sum(member.file_size for member in members)}
    if kind in {"tar", "tar.gz"}:
        with tarfile.open(path, "r:*") as archive:
            members = archive.getmembers()
            unsafe = [member.name for member in members if not _safe_member(member.name)]
            if unsafe:
                raise ValueError(f"unsafe archive members: {unsafe[:5]}")
            return {"format": kind, "member_count": len(members), "uncompressed_bytes": sum(member.size for member in members if member.isfile())}
    raise ValueError(f"unsupported archive format: {kind}")


def extract_transactionally(path: str | Path, destination: str | Path) -> dict:
    path, destination = Path(path).resolve(), Path(destination).resolve()
    staging = destination.with_name(destination.name + ".extracting")
    if destination.exists() or staging.exists():
        raise FileExistsError("destination or extraction staging directory already exists")
    validation = validate_archive(path)
    staging.mkdir(parents=True)
    try:
        if validation["format"] == "zip":
            with zipfile.ZipFile(path) as archive:
                archive.extractall(staging)
        else:
            with tarfile.open(path, "r:*") as archive:
                archive.extractall(staging, filter="data")
        extracted_files = [item for item in staging.rglob("*") if item.is_file()]
        extracted_bytes = sum(item.stat().st_size for item in extracted_files)
        if len(extracted_files) == 0 or extracted_bytes != validation["uncompressed_bytes"]:
            raise ValueError("extracted file count/byte validation failed")
        staging.rename(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        **validation,
        "archive": str(path),
        "archive_bytes": path.stat().st_size,
        "archive_sha256": sha256(path),
        "destination": str(destination),
        "extracted_file_count": len(extracted_files),
        "extracted_bytes": extracted_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Integrity-check and transactionally extract the public archive.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = extract_transactionally(args.archive, args.destination)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
