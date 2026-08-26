"""Build and audit a deterministic, data-free NOSTOS release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


PROTOCOL = "nostos-release-candidate/1.0"
ROOT_FILES = (
    ".gitignore", "README.md", "LICENSE", "CITATION.cff", "pyproject.toml",
    "uv.lock", "requirements-lock.txt", "requirements-comparators.lock.txt",
)
TREES = ("src", "tests", "configs", ".github")
SCRIPTS = (
    "benchmark_kymatio.py", "benchmark_pyradiomics.py",
    "benchmark_pyradiomics_ibsi_texture.py",
    "audit_comparator_environments.py",
    "build_nostos0_main_figures.py",
    "fetch_bbbc039_reference.ps1",
    "fetch_bbbc007_reference.ps1",
    "fetch_bbbc020_reference.ps1",
    "run_response_benchmark_v2.py",
    "run_canonical_development.py",
    "run_canonical_confirmation_v3.py",
    "run_stability_weighting_development.py",
    "run_selective_fft_development.py",
    "run_selective_fft_confirmation.py",
    "run_selective_filament_transfer.py",
    "run_selective_shg_transfer.py",
    "run_consensus_reliability.py",
    "run_local_orientation_validation.py",
    "run_local_orientation_external_test.py",
)
DOCS = (
    "NOSTOS0_REPRODUCIBILITY_AND_METHODS.md",
    "NOSTOS0_CLAIM_EVIDENCE_LEDGER.md",
    "NOSTOS0_FIGURE_SOURCE_TABLE.md",
    "NOSTOS_CARTILAGE_ABLATION_REPORT.md",
    "NOSTOS_EXTERNAL_BONE_VALIDATION.md",
    "NOSTOS_EXTERNAL_FILAMENT_VALIDATION.md",
    "NOSTOS_EXTERNAL_CARTILAGE_VALIDATION.md",
    "NOSTOS_EXTERNAL_NUCLEI_VALIDATION.md",
    "NOSTOS_METHODS_LANDSCAPE.md",
    "NOSTOS0_METHODS_ARTICLE.md",
    "NOSTOS0_EXTERNAL_REPLICATION_PROTOCOL.md",
    "BBBC007_PROSPECTIVE_PROTOCOL.md",
    "BBBC020_PROSPECTIVE_PROTOCOL.md",
    "NOSTOS0_RESPONSE_GEOMETRY_BENCHMARK_V2_PROTOCOL.md",
    "NOSTOS0_ARCHITECTURE_DECISION_ROTATION_QUOTIENT.md",
    "NOSTOS0_CANONICAL_GEOMETRY_CONFIRMATION_V3_PROTOCOL.md",
    "NOSTOS0_SELECTIVE_FFT_CONFIRMATION_PROTOCOL.md",
    "NOSTOS0_FILAMENT_SELECTIVE_TRANSFER_PROTOCOL.md",
    "NOSTOS0_SHG_SELECTIVE_TRANSFER_PROTOCOL.md",
    "NOSTOS0_CONSENSUS_RELIABILITY_PROTOCOL.md",
    "NOSTOS0_LOCAL_ORIENTATION_PROTOCOL.md",
    "NOSTOS0_LOCAL_ORIENTATION_EXTERNAL_TEST_PROTOCOL.md",
)
EVIDENCE_INDEX = Path("outputs/nostos0-evidence-bundle-v7/evidence_index.json")
TEXT_SUFFIXES = {".py", ".md", ".toml", ".txt", ".json", ".csv", ".yml", ".yaml", ".cff", ".ps1"}
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", "nostos.egg-info"}
SECRET_PATTERNS = (
    re.compile(r"s2k-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
)
PRIVATE_PATH = re.compile(r"(?i)(?:[A-Z]:\\Users\\[^\\\s]+|E:\\NOSTOS)")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_file(source: Path, destination: Path, project_root: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in TEXT_SUFFIXES or source.name in {"LICENSE", ".gitignore"}:
        text = source.read_text(encoding="utf-8")
        text = text.replace(str(project_root), "<PROJECT_ROOT>")
        text = re.sub(r"(?i)C:\\Users\\yanyl\\OneDrive\\NOSTOS", "<PROJECT_ROOT>", text)
        text = re.sub(r"(?i)E:\\NOSTOS", "<DATA_ROOT>", text)
        destination.write_text(text, encoding="utf-8", newline="\n")
    else:
        shutil.copyfile(source, destination)


def _selected_files(root: Path) -> list[Path]:
    selected: set[Path] = set()
    for relative in ROOT_FILES:
        path = root / relative
        if path.is_file():
            selected.add(path)
    for tree in TREES:
        base = root / tree
        if base.is_dir():
            selected.update(
                path for path in base.rglob("*")
                if path.is_file() and not any(part in SKIP_PARTS for part in path.parts)
                and path.suffix.lower() not in {".pyc", ".pyo"}
            )
    for name in SCRIPTS:
        path = root / "scripts" / name
        if path.is_file():
            selected.add(path)
    for name in DOCS:
        path = root / "docs" / name
        if path.is_file():
            selected.add(path)
    if EVIDENCE_INDEX.is_absolute():
        raise ValueError("Evidence index must be relative")
    index_path = root / EVIDENCE_INDEX
    if index_path.is_file():
        selected.add(index_path)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for entry in index.get("entries", []):
            relative = Path(entry["path"])
            candidate = root / relative
            if candidate.is_file():
                selected.add(candidate)
    return sorted(selected, key=lambda path: path.relative_to(root).as_posix())


def _audit(stage: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in sorted(stage.rglob("*")):
        if not path.is_file() or path.name == "release_manifest.json":
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE", ".gitignore"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append({"path": path.relative_to(stage).as_posix(), "kind": "possible_secret"})
                break
        if PRIVATE_PATH.search(text):
            findings.append({"path": path.relative_to(stage).as_posix(), "kind": "private_absolute_path"})
    return findings


def build_release(project_root: Path, output: Path) -> dict:
    root = project_root.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="nostos-release-stage-")) / "nostos-0.3.0"
    stage.mkdir()
    for source in _selected_files(root):
        _copy_file(source, stage / source.relative_to(root), root)

    findings = _audit(stage)
    files = []
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            files.append({
                "path": path.relative_to(stage).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            })
    manifest = {
        "protocol_version": PROTOCOL,
        "software_version": "0.3.0",
        "status": "pass" if not findings else "fail",
        "data_included": False,
        "file_count": len(files),
        "files": files,
        "audit_findings": findings,
        "limitations": [
            "Archive integrity is not independent scientific replication.",
            "Cartilage reference-mask validation and independent-acquisition validation remain pending.",
            "Repository and archival DOI placeholders must be replaced before publication.",
        ],
    }
    manifest_path = stage / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    if findings:
        raise RuntimeError(f"Release audit failed: {findings}")

    archive = output / "nostos-0.3.0-release-candidate.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        archive.unlink()
    timestamp = (2026, 8, 26, 0, 0, 0)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(stage.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo((Path(stage.name) / path.relative_to(stage)).as_posix(), timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())
    receipt = {
        "protocol_version": PROTOCOL,
        "status": "pass",
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": _sha256(archive),
        "stage_manifest_sha256": _sha256(manifest_path),
        "file_count": len(files) + 1,
    }
    (output / "release_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    shutil.copyfile(manifest_path, output / "release_manifest.json")
    try:
        shutil.rmtree(stage.parent)
    except OSError:
        pass
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("outputs/nostos0-release-candidate-v1"))
    args = parser.parse_args()
    print(json.dumps(build_release(args.project_root, args.output), indent=2))


if __name__ == "__main__":
    main()
