"""Unified command-line interface for the NOSTOS research toolkit."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import importlib.util
import json
import os
import sys
from pathlib import Path


def _json_print(payload: dict) -> None:
    print(json.dumps(payload, indent=2, allow_nan=False))


def _doctor(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[2]
    storage_file = root / "storage.json"
    checks: list[dict] = []
    for module in ("numpy", "pandas", "PIL", "scipy", "sklearn", "tifffile"):
        checks.append({"check": f"python:{module}", "ok": importlib.util.find_spec(module) is not None})
    checks.append({"check": "web_app", "ok": (root / "microscopy_app" / "index.html").is_file()})
    checks.append({"check": "storage_config", "ok": storage_file.is_file()})
    storage: dict = {}
    if storage_file.is_file():
        storage = json.loads(storage_file.read_text(encoding="utf-8"))
        for name, value in storage.items():
            if isinstance(value, str):
                if value.startswith(("http://", "https://")):
                    checks.append({"check": f"config:{name}", "ok": True, "value": value})
                else:
                    checks.append({"check": f"storage:{name}", "ok": Path(value).exists(), "path": value})
    payload = {
        "status": "ready" if all(item["ok"] for item in checks) else "attention_required",
        "python": sys.version.split()[0],
        "project_root": str(root),
        "checks": checks,
    }
    _json_print(payload)
    return 0 if payload["status"] == "ready" else 1


def _decode_data_uri(value: str) -> bytes:
    return base64.b64decode(value.split(",", 1)[-1])


def _analyze(args: argparse.Namespace) -> int:
    from PIL import Image
    from nostos.app.server import Analyzer

    image_path = args.image.resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")
    with Image.open(image_path) as opened:
        opened.verify()
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    analyzer = Analyzer(args.learned_checkpoint.resolve() if args.learned_checkpoint else None)
    result = analyzer.analyze({
        "image_data": "data:application/octet-stream;base64," + encoded,
        "stain": args.stain,
        "pixel_size_um": args.pixel_size_um,
    })
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    assets = {
        "overlay_png": output / "overlay.png",
        "mask_png": output / "mask.png",
        "spectrum_png": output / "spectrum.png",
    }
    for key, path in assets.items():
        path.write_bytes(_decode_data_uri(str(result.pop(key))))
    result["source_image"] = str(image_path)
    result["source_file_sha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
    result["artifacts"] = {key.removesuffix("_png"): str(path) for key, path in assets.items()}
    result_path = output / "analysis.json"
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    metrics = result["metrics"]
    report_path = output / "case_report.html"
    metric_rows = "".join(
        f"<tr><th>{html.escape(str(name).replace('_', ' '))}</th><td>{html.escape(str(value))}</td></tr>"
        for name, value in metrics.items()
    )
    warning_items = "".join(f"<li>{html.escape(str(value))}</li>" for value in result["warnings"])
    report_path.write_text(f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>NOSTOS research case report</title>
<style>body{{font-family:Arial,sans-serif;max-width:980px;margin:40px auto;color:#172326}}h1{{font-family:Georgia,serif}}.status{{padding:12px;border-left:5px solid #b64342;background:#f6eeee}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}img{{width:100%;border:1px solid #d7dddd}}table{{border-collapse:collapse;width:100%;margin-top:18px}}th,td{{padding:7px;border-bottom:1px solid #d7dddd;text-align:left}}th{{width:55%}}code{{overflow-wrap:anywhere}}</style>
<body><h1>NOSTOS research case report</h1>
<div class="status"><strong>Clinical decision withheld.</strong> Research-use-only output. QC status: {html.escape(result['qc']['status'])}.</div>
<p><strong>Source:</strong> <code>{html.escape(str(image_path))}</code><br><strong>SHA-256:</strong> <code>{result['source_file_sha256']}</code><br><strong>Stain:</strong> {result['stain']} &nbsp; <strong>Calibration:</strong> {result['pixel_size_um']} µm/pixel &nbsp; <strong>Device:</strong> {result['device']}</p>
<div class="grid"><figure><img src="overlay.png" alt="Segmentation proposal overlay"><figcaption>Proposal overlay</figcaption></figure><figure><img src="mask.png" alt="Indexed tissue proposal"><figcaption>Tissue proposal</figcaption></figure><figure><img src="spectrum.png" alt="Fourier power preview"><figcaption>Spectral preview</figcaption></figure></div>
<table>{metric_rows}</table><h2>Warnings</h2><ul>{warning_items}</ul>
<p>This report does not provide diagnosis, margin selection, treatment advice or a validated estimate of tissue mechanics.</p></body></html>""", encoding="utf-8")
    result["artifacts"]["case_report"] = str(report_path)
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    _json_print({
        "status": result["status"],
        "analysis": str(result_path),
        "analyzed_tiles": result["metrics"]["analyzed_tiles"],
        "device": result["device"],
        "qc_status": result["qc"]["status"],
        "clinical_decision": result["clinical_decision"],
        "case_report": str(report_path),
        "warnings": result["warnings"],
    })
    return 0


def _serve(args: argparse.Namespace) -> int:
    from nostos.app.server import main as server_main

    forwarded = ["nostos-app", "--host", args.host, "--port", str(args.port)]
    if args.no_browser:
        forwarded.append("--no-browser")
    if args.learned_checkpoint:
        forwarded.extend(["--learned-checkpoint", str(args.learned_checkpoint)])
    old_argv = sys.argv
    try:
        sys.argv = forwarded
        server_main()
    finally:
        sys.argv = old_argv
    return 0


def _batch(args: argparse.Namespace) -> int:
    from nostos.app.batch_cpu import main as batch_main

    forwarded = [
        "nostos-cpu-batch", str(args.manifest), "--output", str(args.output),
        "--stain", args.stain, "--site", args.site, "--workers", str(args.workers),
        "--section-rank", str(args.section_rank),
    ]
    if args.limit is not None:
        forwarded.extend(["--limit", str(args.limit)])
    old_argv = sys.argv
    try:
        sys.argv = forwarded
        batch_main()
    finally:
        sys.argv = old_argv
    return 0


def _validate_synthetic(args: argparse.Namespace) -> int:
    from nostos.validation.harness import run_frozen_validation

    payload = run_frozen_validation(args.output.resolve())
    _json_print({"status": payload["status"], "output": str(args.output.resolve() / "validation.json"), **payload["summary"]})
    return 0 if payload["status"] == "pass" else 1


def _benchmark_synthetic(args: argparse.Namespace) -> int:
    from nostos.validation.comparators import write_benchmark_receipt

    payload = write_benchmark_receipt(args.output.resolve())
    _json_print({
        "status": "complete",
        "output": str(args.output.resolve() / "representation_benchmark.json"),
        "contrasts": payload["contrasts"],
    })
    return 0


def _validate_bone(args: argparse.Namespace) -> int:
    from nostos.validation.external_bone import validate_bone_subset

    payload = validate_bone_subset(args.data.resolve(), args.output.resolve())
    _json_print({"status": payload["validity"]["status"], "output": str(args.output.resolve() / "external_bone_validation.json"), **payload["summary"]})
    return 0


def _validate_filament(args: argparse.Namespace) -> int:
    from nostos.validation.external_filament import validate_filament_dataset

    payload = validate_filament_dataset(args.data.resolve(), args.output.resolve())
    _json_print({"status": payload["validity"]["status"], "output": str(args.output.resolve() / "external_filament_validation.json"), **payload["summary"]})
    return 0


def _validate_cartilage(args: argparse.Namespace) -> int:
    from nostos.validation.external_cartilage import validate_cartilage_response_geometry

    payload = validate_cartilage_response_geometry(args.medial.resolve(), args.lateral.resolve(), args.scores.resolve(), args.output.resolve())
    _json_print({"status": payload["validity"]["status"], "output": str(args.output.resolve() / "external_cartilage_validation.json"), "processing": payload["processing"], "association_rows": payload["association_rows"]})
    return 0


def _validate_nuclei(args: argparse.Namespace) -> int:
    from nostos.validation.external_nuclei import validate_nuclei_dataset

    payload = validate_nuclei_dataset(args.data.resolve(), args.output.resolve())
    _json_print({"status": payload["validity"]["status"],
                 "output": str(args.output.resolve() / "external_nuclei_validation.json"),
                 "case_count": payload["case_count"], "summary": payload["summary"]})
    return 0


def _validate_modules(args: argparse.Namespace) -> int:
    from nostos.validation.module_perturbations import run_module_perturbation_matrix

    payload = run_module_perturbation_matrix(args.output.resolve())
    _json_print({"status": payload["status"], "output": str(args.output.resolve() / "module_perturbation_matrix.json"), **payload["summary"]})
    return 0 if payload["status"] == "pass" else 1


def _audit_comparators(args: argparse.Namespace) -> int:
    from nostos.validation.comparator_conformance import write_comparator_conformance_receipt

    payload = write_comparator_conformance_receipt(
        args.output.resolve(),
        None if args.python is None else args.python.resolve(),
        kymatio_python=None if args.kymatio_python is None else args.kymatio_python.resolve(),
        pyradiomics_python=None if args.pyradiomics_python is None else args.pyradiomics_python.resolve(),
    )
    _json_print({"status": payload["status"],
                 "output": str(args.output.resolve() / "comparator_conformance.json"),
                 "gates": payload["gates"]})
    return 0 if payload["status"] == "pass" else 2


def _build_evidence_bundle(args: argparse.Namespace) -> int:
    from nostos.validation.evidence_bundle import build_evidence_bundle

    payload = build_evidence_bundle(args.project_root.resolve(), args.output.resolve())
    _json_print({"status": payload["status"], "output": str(args.output.resolve() / "evidence_index.json"),
                 "entries": len(payload["entries"]), "missing": payload["missing"],
                 "nature_readiness": payload["nature_readiness"]})
    return 0 if payload["status"] == "complete_index" else 2


def _replication_challenge(args: argparse.Namespace) -> int:
    from nostos.validation.replication import run_replication_challenge

    payload = run_replication_challenge(args.output.resolve(), args.project_root.resolve(), args.operator)
    _json_print({"status": payload["status"],
                 "output": str(args.output.resolve() / "replication_receipt.json"),
                 "gates": payload["gates"]})
    return 0 if payload["status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nostos",
        description="CPU-first spatial-frequency microscopy analysis for research use only.",
    )
    parser.add_argument("--version", action="version", version="NOSTOS 0.3.0")
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="Check the installation and configured storage")
    doctor.set_defaults(func=_doctor)

    analyze = commands.add_parser("analyze", help="Analyze one microscopy image and export visual artifacts")
    analyze.add_argument("image", type=Path)
    analyze.add_argument("--stain", choices=["HE", "SafO", "PLM"], default="SafO")
    analyze.add_argument("--pixel-size-um", type=float, default=5.16)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--learned-checkpoint", type=Path)
    analyze.set_defaults(func=_analyze)

    serve = commands.add_parser("serve", help="Launch the local browser workstation")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--no-browser", action="store_true")
    serve.add_argument("--learned-checkpoint", type=Path)
    serve.set_defaults(func=_serve)

    batch = commands.add_parser("batch", help="Analyze a participant-safe cohort manifest")
    batch.add_argument("manifest", type=Path)
    batch.add_argument("--output", type=Path, required=True)
    batch.add_argument("--stain", choices=["HE", "SafO", "PLM"], default="SafO")
    batch.add_argument("--site", choices=["Medial", "Lateral"], default="Medial")
    batch.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    batch.add_argument("--limit", type=int)
    batch.add_argument("--section-rank", type=int, default=1)
    batch.set_defaults(func=_batch)

    validate = commands.add_parser("validate-synthetic", help="Run the frozen CPU synthetic validation protocol")
    validate.add_argument("--output", type=Path, required=True)
    validate.set_defaults(func=_validate_synthetic)

    benchmark = commands.add_parser("benchmark-synthetic", help="Compare response curves, scalar summaries and module ablations")
    benchmark.add_argument("--output", type=Path, required=True)
    benchmark.set_defaults(func=_benchmark_synthetic)

    bone = commands.add_parser("validate-bone", help="Validate thickness against an external public micro-CT reference subset")
    bone.add_argument("--data", type=Path, required=True)
    bone.add_argument("--output", type=Path, required=True)
    bone.set_defaults(func=_validate_bone)

    filament = commands.add_parser("validate-filament", help="Run frozen response geometry on public annotated mycelium networks")
    filament.add_argument("--data", type=Path, required=True)
    filament.add_argument("--output", type=Path, required=True)
    filament.set_defaults(func=_validate_filament)

    cartilage = commands.add_parser("validate-cartilage", help="Evaluate frozen response modules with site-matched public OA outcomes")
    cartilage.add_argument("--medial", type=Path, required=True)
    cartilage.add_argument("--lateral", type=Path, required=True)
    cartilage.add_argument("--scores", type=Path, required=True)
    cartilage.add_argument("--output", type=Path, required=True)
    cartilage.set_defaults(func=_validate_cartilage)

    nuclei = commands.add_parser("validate-nuclei", help="Validate frozen Hessian morphology on BBBC039 test masks")
    nuclei.add_argument("--data", type=Path, required=True)
    nuclei.add_argument("--output", type=Path, required=True)
    nuclei.set_defaults(func=_validate_nuclei)

    modules = commands.add_parser("validate-modules", help="Run the frozen per-module perturbation matrix")
    modules.add_argument("--output", type=Path, required=True)
    modules.set_defaults(func=_validate_modules)

    comparators = commands.add_parser("audit-comparators", help="Audit external comparator availability and claim eligibility")
    comparators.add_argument("--output", type=Path, required=True)
    comparators.add_argument("--python", type=Path, help="Optional isolated comparator interpreter")
    comparators.add_argument("--kymatio-python", type=Path, help="Kymatio interpreter override")
    comparators.add_argument("--pyradiomics-python", type=Path, help="PyRadiomics interpreter override")
    comparators.set_defaults(func=_audit_comparators)

    evidence = commands.add_parser("build-evidence-bundle", help="Index and checksum all required NOSTOS-0 receipts")
    evidence.add_argument("--project-root", type=Path, default=Path.cwd())
    evidence.add_argument("--output", type=Path, required=True)
    evidence.set_defaults(func=_build_evidence_bundle)

    replication = commands.add_parser("replication-challenge", help="Run the data-free external replication challenge")
    replication.add_argument("--output", type=Path, required=True)
    replication.add_argument("--project-root", type=Path, default=Path.cwd())
    replication.add_argument("--operator", default="anonymous")
    replication.set_defaults(func=_replication_challenge)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        code = int(args.func(args))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "error", "error": str(error)}), file=sys.stderr)
        code = 2
    raise SystemExit(code)


if __name__ == "__main__":
    main()
