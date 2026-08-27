"""Generate a self-contained, machine-verifiable NOSTOS external audit package."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "NOSTOS_EXTERNAL_AUDIT_PACKAGE.md"
INCLUDED_ROOTS = ("src", "tests", "configs", "scripts")
INCLUDED_FILES = (
    ".gitignore",
    "README.md",
    "pyproject.toml",
    "requirements-lock.txt",
    "requirements-segmentation-cu128.txt",
    "storage.json",
    "launch_nostos.ps1",
    "run_cpu_pilot.ps1",
    "run_flagship_validation.ps1",
    "docs/analysis_plan.md",
    "docs/confirmatory_replication_protocol.md",
    "docs/confirmatory_deviations.md",
    "docs/mechanistic_discrimination_protocol.md",
    "docs/manuscript_draft.md",
    "docs/FINAL_RELEASE_AUDIT.md",
    "docs/NOSTOS0_METHODS_ARTICLE.md",
    "docs/NOSTOS0_CLAIM_EVIDENCE_LEDGER.md",
    "docs/NOSTOS0_BIOLOGICAL_RETRIEVAL_CONFIRMATION_PROTOCOL.md",
    "docs/NOSTOS0_OSTEOCHONDRAL_INTERFACE_CONFIRMATION_PROTOCOL.md",
    "docs/NOSTOS0_OSTEOCHONDRAL_LEARNED_ADAPTER_BENCHMARK.md",
    "outputs/nostos0-evidence-bundle-v11/evidence_index.json",
    "outputs/nostos0-evidence-bundle-v11/checksums.sha256",
    "outputs/nostos0-biological-retrieval-confirmation-v1/biological_retrieval_confirmation.json",
    "outputs/nostos0-osteochondral-interface-confirmation-v1/osteochondral_interface_confirmation.json",
    "outputs/nostos0-osteochondral-learned-adapter-v1_1/osteochondral_learned_adapter_summary.json",
    "outputs/nostos0-release-candidate-v14/release_receipt.json",
    "outputs/nostos0-release-candidate-v14/cleanroom_verification.json",
)
EXCLUDED_SUFFIXES = {".pyc", ".docx", ".pdf", ".png", ".jpg", ".svg"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def critical_files() -> list[Path]:
    paths: set[Path] = set()
    for root_name in INCLUDED_ROOTS:
        root = ROOT / root_name
        if root.exists():
            for path in root.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix.lower() not in EXCLUDED_SUFFIXES:
                    paths.add(path)
    for value in INCLUDED_FILES:
        path = ROOT / value
        if path.is_file():
            paths.add(path)
    return sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix())


def command_output(command: list[str]) -> tuple[int, str]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    text = (completed.stdout + completed.stderr).strip()
    return completed.returncode, text


def main() -> None:
    files = critical_files()
    pytest_code, pytest_text = command_output([sys.executable, "-m", "pytest", "-q"])
    pip_code, pip_text = command_output(["uv", "pip", "check"])
    doctor_code, doctor_text = command_output([sys.executable, "-m", "nostos.cli", "doctor"])
    smoke_path = ROOT / "outputs" / "tool_smoke" / "analysis.json"
    smoke = json.loads(smoke_path.read_text(encoding="utf-8")) if smoke_path.is_file() else None
    manifest_lines = [f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in files]
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# NOSTOS external reproducibility and tool audit package",
        "",
        f"Generated: {generated}",
        "",
        "## Instructions for the independent auditor",
        "",
        "Audit the code, methods, claims and user-facing tool independently. Do not assume that a passing test proves scientific validity. Re-run the frozen protocols, verify group separation and physical calibration, inspect every failed gate, and test whether each biological interpretation is narrower than its measurement endpoint. Treat generated figures as representations that must be traced to a receipt, source table or public image.",
        "",
        "## Release identity",
        "",
        "- Package: NOSTOS 0.3.0-rc14",
        "- Public repository: https://github.com/RonnieHappy/NOSTOS",
        "- Immutable tag: v0.3.0-rc14",
        "- Commit: resolve with `git rev-list -n 1 v0.3.0-rc14` and compare it with the signed release page",
        "- Release: https://github.com/RonnieHappy/NOSTOS/releases/tag/v0.3.0-rc14",
        "- Intended use: CPU-first, calibrated structural measurement in biological images",
        "- Implemented domains: analytic phantoms, cartilage histology, trabecular-bone micro-CT, filament microscopy, nuclei fluorescence and polarization-SHG",
        "- Platform used for this audit: Windows, Python " + platform.python_version(),
        "",
        "## Explicit non-claims",
        "",
        "NOSTOS is not a diagnostic device, intraoperative decision aid, universal image fingerprint, universal classifier or validated estimator of stiffness, modulus, permeability, load support, treatment response or patient outcome. The public cartilage cohort provides adjacent-section repeatability, not independent external validation. Classical cartilage masks are tissue proposals, not expert reference segmentations. The training-free PTA micro-CT interface adapter failed prospective confirmation and is rejected. The subsequent learned adapter is post-failure development: despite Dice 0.912 and median interface error 21.6 micrometres, it failed six of nine gates and does not establish downstream measurement validity. Mechanistic language remains associative and non-causal.",
        "",
        "## Novelty thesis to audit",
        "",
        "The proposed contribution is not that Fourier transforms, structure tensors, Hessians, local thickness or variograms are new. It is a typed, physically indexed response geometry that preserves scale-resolved curves, perturbation stability, validity flags, abstention reasons and provenance across measurement modules. The novelty survives only if this common grammar is useful beyond packaging familiar algorithms. The auditor should therefore compare NOSTOS against individual conventional methods, naive concatenation, IBSI radiomics and scattering, and should treat the retained prospective failures as constraints on—not support for—the central claim.",
        "",
        "## Clinical translation threshold",
        "",
        "The current software is a clinically oriented research prototype, not a clinically validated product. A defensible clinical-use claim requires, at minimum: a prespecified intended use and target population; expert reference segmentation with inter-reader analysis; prospective acquisition on the intended microscope or arthroscope; locked calibration and QC; independent-site validation; time-to-result and failure-rate reporting; comparison with standard care; clinical decision-impact analysis; human-factors testing; cybersecurity and audit logging; model/version control; and the applicable regulatory quality system. Until those elements exist, the software deliberately withholds a clinical decision and reports only research measurements.",
        "",
        "## Public tool surface",
        "",
        "```text",
        "nostos doctor",
        "nostos analyze IMAGE --stain {SafO,HE,PLM} --pixel-size-um FLOAT --output DIRECTORY",
        "nostos serve [--host 127.0.0.1] [--port 8765] [--no-browser]",
        "nostos batch MANIFEST --output CSV --stain {SafO,HE,PLM} --site {Medial,Lateral} --section-rank N --workers N",
        "```",
        "",
        "The learned segmentation checkpoint is optional. Without it, `analyze` and `serve` use deterministic stain-aware proposals and CPU Fourier/texture features.",
        "",
        "## Clean reproduction sequence",
        "",
        "```powershell",
        "git clone --branch v0.3.0-rc14 https://github.com/RonnieHappy/NOSTOS.git",
        "cd NOSTOS",
        "$env:UV_LINK_MODE='copy'  # only if Windows/cloud storage rejects hardlinks",
        "uv sync --frozen --extra dev",
        "nostos doctor",
        "nostos analyze path\\to\\section.tif --stain SafO --pixel-size-um 5.16 --output outputs\\case",
        "nostos serve --no-browser",
        "uv run python -m pytest -q",
        "uv run nostos build-evidence-bundle --project-root . --output outputs/independent-evidence-index",
        "```",
        "",
        "Raw data are intentionally excluded from Git and must be obtained from the original repository under its applicable licence. Inspect `storage.json`, `README.md`, the audit manifest and locked protocols before running the cohort workflows.",
        "",
        "## Automated verification captured during package generation",
        "",
        f"### Test suite — exit code {pytest_code}",
        "",
        "```text",
        pytest_text,
        "```",
        "",
        f"### Dependency consistency — exit code {pip_code}",
        "",
        "```text",
        pip_text,
        "```",
        "",
        f"### Installation and storage doctor — exit code {doctor_code}",
        "",
        "```json",
        doctor_text,
        "```",
        "",
        "## End-to-end smoke-test evidence",
        "",
    ]
    if smoke:
        lines.extend([
            f"- Source: `{smoke.get('source_image')}`",
            f"- Status: `{smoke.get('status')}`",
            f"- Device: `{smoke.get('device')}`",
            f"- Segmentation supervision: `{smoke.get('model_supervision')}`",
            f"- Analysed tiles: `{smoke.get('metrics', {}).get('analyzed_tiles')}`",
            f"- Elapsed analysis time: `{smoke.get('elapsed_seconds')} s`",
            "- Outputs: `outputs/tool_smoke/analysis.json`, `mask.png`, `overlay.png`, `spectrum.png`",
        ])
    else:
        lines.append("No saved smoke-test result was present when this package was generated.")
    lines.extend([
        "",
        "## Reproducibility architecture",
        "",
        "- `src/nostos/data`: source auditing, metadata normalization, participant splits, analysis-table assembly and archival.",
        "- `src/nostos/segmentation`: weak proposals, annotation preparation, learned training/inference and evaluation.",
        "- `src/nostos/features`: calibrated spectral, tensor, Hessian, thickness, network and spatial response modules.",
        "- `src/nostos/validation`: phantoms, perturbation harnesses, official comparators, prospective transfers and machine-readable evidence indexing.",
        "- `src/nostos/modeling`: participant-grouped prediction, ablations, locked analyses and severity benchmarking.",
        "- `src/nostos/evaluation`: robustness, confounding, agreement, adjacent-section replication, reader reliability and mechanistic subscores.",
        "- `src/nostos/reporting`: manuscript-facing tables, cohort reports, segmentation reports and publication bundles.",
        "- `src/nostos/app`: single-image analyzer, local HTTP workstation and CPU cohort batch runner.",
        "- `tests`: automated invariants for participant grouping, feature extraction, segmentation, statistics, reporting and release gates.",
        "",
        "## Highest-priority independent audit questions",
        "",
        "1. Does every split and cross-validation path group by participant before preprocessing or feature selection?",
        "2. Are pixel sizes read from authoritative metadata and propagated consistently into cycles-per-millimetre features?",
        "3. Do the prospective retrieval, training-free osteochondral-interface and post-failure learned-adapter failures appear completely and consistently in code, receipts, discussion and claim ledger?",
        "4. Are all bootstrap, false-discovery-rate and permutation families defined before outcome inspection?",
        "5. Does adjacent-section replication remain independent enough to support repeatability without being described as external validation?",
        "6. Are PLM comparisons honest about adjacency and absence of deformable registration?",
        "7. Are 3D feature terrains and interpolated fields clearly distinguished from physical topography?",
        "8. Do failure cases abstain or return explicit invalidity reasons rather than apparently valid measurements?",
        "9. Can a clean environment reproduce manuscript tables and figure source data from the licensed raw dataset?",
        "10. Do the manuscript title, abstract, figures and discussion stay within the evidence boundaries above?",
        "",
        "## Known release limitations",
        "",
        "- No independent external cartilage cohort or prospective acquisition.",
        "- No expert reference-mask study covering the full cohort.",
        "- The frozen universal identity-retrieval confirmation failed six substantive gates.",
        "- The frozen training-free osteochondral-interface confirmation failed seven substantive gates and the adapter is rejected.",
        "- The patient-grouped learned adapter improved whole-mask overlap but failed six of nine development gates, including downstream measurement agreement; it is not independent confirmation.",
        "- No validated learned/imported ROI adapter on an untouched acquisition.",
        "- No independent external user has reproduced a complete archived result.",
        "- No direct tissue-mechanics measurements.",
        "- No hardened multi-user server, authentication layer or regulatory quality system.",
        "- No streaming reader for pyramidal whole-slide TIFFs; single-image analysis decodes into memory.",
        "- No signed release artifact, container image, DICOM interface or plugin API.",
        "- The depth-atlas outcome analysis remains gated because its complete-depth coverage criterion failed.",
        "",
        "## SHA-256 manifest of reproducibility-critical files",
        "",
        f"Files hashed: {len(files)}",
        "",
        "```text",
        *manifest_lines,
        "```",
        "",
        "## Integrity check",
        "",
        "Recompute any entry with `Get-FileHash -Algorithm SHA256 PATH`. A mismatch means the repository changed after this audit package was generated and the automated evidence above must be rerun.",
        "",
    ])
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "files_hashed": len(files), "pytest_exit": pytest_code, "doctor_exit": doctor_code, "pip_check_exit": pip_code}, indent=2))


if __name__ == "__main__":
    main()
