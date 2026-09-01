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
    for module in ("numpy", "pandas", "PIL", "scipy", "skimage", "sklearn", "tifffile"):
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
                    configured = Path(value).expanduser()
                    resolved = configured if configured.is_absolute() else root / configured
                    checks.append({"check": f"storage:{name}", "ok": resolved.exists(), "path": str(resolved)})
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


def _measure(args: argparse.Namespace) -> int:
    from nostos.app.measure import measure_file

    payload = measure_file(
        args.input.resolve(),
        args.output.resolve(),
        spacing=args.spacing,
        spatial_unit=args.unit,
        mask_path=None if args.mask is None else args.mask.resolve(),
        specimen_reference=args.specimen_reference,
        specimen_direction_degrees=args.specimen_direction,
        measurement_profile_path=(
            None if args.measurement_profile is None else args.measurement_profile.resolve()
        ),
    )
    _json_print(payload)
    return 0


def _intraop_pshg(args: argparse.Namespace) -> int:
    from nostos.intraop.operator import analyze_operator_pshg_directory

    root = Path(__file__).resolve().parents[2]
    profile_path = (
        root / "configs/intraop_pshg_orientation_profile_v1.locked.json"
        if args.profile is None
        else args.profile.resolve()
    )
    public_lock_path = (
        root / "manifests/intraop_pshg_deployment_v1_4_lock.json"
        if args.public_lock is None
        else args.public_lock.resolve()
    )
    payload = analyze_operator_pshg_directory(
        args.input.resolve(),
        args.output.resolve(),
        profile_path=profile_path,
        public_lock_path=public_lock_path,
        pixel_size_um=args.pixel_size_um,
        include_reference_evaluation=args.include_reference_evaluation,
    )
    _json_print({
        "status": payload["status"],
        "evidence_status": payload["measurement"]["evidence_status"],
        "clinical_decision": payload["clinical_output"]["status"],
        "eligible_pixels": payload["measurement"]["summary"]["eligible_pixels"],
        "output": str((args.output.resolve() / "intraop_result.json")),
        "provenance": payload["operator_provenance"],
    })
    return 0


def _measure_series(args: argparse.Namespace) -> int:
    from nostos.app.measure import measure_series_file

    payload = measure_series_file(
        args.input.resolve(), args.output.resolve(), spacing=args.spacing,
        spatial_unit=args.unit, temporal_spacing=args.temporal_spacing,
        temporal_unit=args.temporal_unit, dense=args.dense,
    )
    _json_print(payload)
    return 0


def _track_series(args: argparse.Namespace) -> int:
    from nostos.app.measure import track_series_files

    payload = track_series_files(
        args.masks.resolve(), args.output.resolve(), spacing=args.spacing,
        spatial_unit=args.unit, temporal_spacing=args.temporal_spacing,
        temporal_unit=args.temporal_unit,
        image_directory=None if args.images is None else args.images.resolve(),
        experimental_divisions=args.experimental_divisions,
    )
    _json_print(payload)
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


def _validate_nuclei_confirmatory(args: argparse.Namespace) -> int:
    from nostos.validation.external_nuclei_confirmatory import validate_nuclei_confirmatory

    payload = validate_nuclei_confirmatory(args.data.resolve(), args.output.resolve())
    _json_print({"status": payload["validity"]["status"],
                 "output": str(args.output.resolve() / "external_nuclei_confirmatory.json"),
                 "case_count": payload["case_count"], "gates": payload["success_gates"],
                 "summary": payload["summary"]})
    return 0 if payload["validity"]["status"] == "pass" else 1


def _validate_nuclei_bbbc020(args: argparse.Namespace) -> int:
    from nostos.validation.external_nuclei_bbbc020 import validate_bbbc020

    payload = validate_bbbc020(args.data.resolve(), args.output.resolve())
    _json_print({"status": payload["validity"]["status"],
                 "output": str(args.output.resolve() / "external_nuclei_bbbc020.json"),
                 "case_count": payload["case_count"], "gates": payload["success_gates"],
                 "summary": payload["summary"]})
    return 0 if payload["validity"]["status"] == "pass" else 1


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

    payload = run_replication_challenge(
        args.output.resolve(), args.project_root.resolve(), args.operator,
        affiliation=args.affiliation, unaided=args.unaided,
        author_environment=args.author_environment, assistance=args.assistance,
        source_kind=args.source_kind,
    )
    _json_print({"status": payload["status"],
                 "output": str(args.output.resolve() / "replication_receipt.json"),
                 "gates": payload["gates"]})
    return 0 if payload["status"] == "pass" else 1


def _verify_replication(args: argparse.Namespace) -> int:
    from nostos.validation.replication import verify_replication_package

    payload = verify_replication_package(args.receipt, require_independent=not args.allow_author_run)
    _json_print(payload)
    return 0 if payload["status"] in {"eligible_independent_pass", "integrity_pass_not_independent"} else 1


def _compile_validity_profile(args: argparse.Namespace) -> int:
    from nostos.validation.validity_profile_compiler import compile_profile_files

    payload = compile_profile_files(
        args.development_rows.resolve(),
        args.config.resolve(),
        args.output.resolve(),
    )
    _json_print(payload)
    return 0 if payload["status"] == "operating_point_selected" else 1


def _audit_validity_profile(args: argparse.Namespace) -> int:
    from nostos.validation.validity_profile_compiler import audit_profile_files

    payload = audit_profile_files(
        args.confirmation_rows.resolve(),
        args.profile.resolve(),
        args.output.resolve(),
    )
    _json_print(payload)
    return 0 if payload["status"] == "pass" else 1


def _compile_conditional_support(args: argparse.Namespace) -> int:
    from nostos.validation.conditional_support_io import (
        compile_conditional_support_files,
    )

    payload = compile_conditional_support_files(
        args.development_rows.resolve(),
        args.config.resolve(),
        args.base_profile.resolve(),
        args.output.resolve(),
    )
    _json_print(payload)
    return 0 if payload["status"] == "operating_point_selected" else 1


def _audit_conditional_support(args: argparse.Namespace) -> int:
    from nostos.validation.conditional_support_io import (
        audit_conditional_support_files,
    )

    payload = audit_conditional_support_files(
        args.confirmation_rows.resolve(),
        args.config.resolve(),
        args.base_profile.resolve(),
        args.conditional_profile.resolve(),
        args.output.resolve(),
    )
    _json_print(payload)
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

    measure = commands.add_parser("measure", help="Measure a calibrated 2-D image or 3-D volume without tissue-specific retraining")
    measure.add_argument("input", type=Path, help="PNG/JPEG/TIFF, NumPy .npy, or NIfTI .nii/.nii.gz input")
    measure.add_argument("--spacing", required=True, help="One isotropic spacing or comma-separated spacing values")
    measure.add_argument("--unit", choices=("um", "mm", "relative"), default="um")
    measure.add_argument("--mask", type=Path, help="Optional shape-matched binary image/volume")
    measure.add_argument("--specimen-reference", type=float, help="Optional physical reference length for relative scale")
    measure.add_argument("--specimen-direction", type=float, default=0.0, help="Image-to-specimen axial rotation in degrees")
    measure.add_argument(
        "--measurement-profile",
        type=Path,
        help="Optional compatible acquisition-profile JSON; unprofiled measurements remain explicitly unvalidated",
    )
    measure.add_argument("--output", type=Path, required=True)
    measure.set_defaults(func=_measure)

    series = commands.add_parser("measure-series", help="Measure an explicitly declared 2-D+t array; first axis is time")
    series.add_argument("input", type=Path, help="NumPy .npy or multipage TIFF with axis order time,y,x")
    series.add_argument("--spacing", required=True, help="One isotropic spatial spacing or y,x values")
    series.add_argument("--unit", choices=("um", "mm", "relative"), default="um")
    series.add_argument("--temporal-spacing", type=float, required=True)
    series.add_argument("--temporal-unit", default="s")
    series.add_argument("--dense", action="store_true", help="Estimate calibrated dense deformation with forward-backward uncertainty")
    series.add_argument("--output", type=Path, required=True)
    series.set_defaults(func=_measure_series)

    tracking = commands.add_parser("track-series", help="Link imported instance masks into calibrated object trajectories")
    tracking.add_argument("--masks", type=Path, required=True, help="Directory of framewise TIFF instance masks")
    tracking.add_argument("--images", type=Path, help="Optional matching microscopy frames")
    tracking.add_argument("--spacing", required=True, help="One isotropic spatial spacing or y,x values")
    tracking.add_argument("--unit", choices=("um", "mm", "relative"), default="um")
    tracking.add_argument("--temporal-spacing", type=float, required=True)
    tracking.add_argument("--temporal-unit", default="min")
    tracking.add_argument("--experimental-divisions", action="store_true", help="Enable lineage proposals that failed the pristine transfer gate")
    tracking.add_argument("--output", type=Path, required=True)
    tracking.set_defaults(func=_track_series)

    analyze = commands.add_parser("analyze", help="Analyze one microscopy image and export visual artifacts")
    analyze.add_argument("image", type=Path)
    analyze.add_argument("--stain", choices=["HE", "SafO", "PLM"], default="SafO")
    analyze.add_argument("--pixel-size-um", type=float, default=5.16)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--learned-checkpoint", type=Path)
    analyze.set_defaults(func=_analyze)

    intraop = commands.add_parser(
        "intraop-pshg",
        help="Map an unstained ten-frame PSHG acquisition with fail-closed evidence labels",
    )
    intraop.add_argument("input", type=Path, help="Directory with ten FSHG TIFFs plus R2.tif and SNR.tif")
    intraop.add_argument("--pixel-size-um", type=float, default=1.0)
    intraop.add_argument("--profile", type=Path, help="Validated acquisition-profile JSON")
    intraop.add_argument("--public-lock", type=Path, help="Optional public source lock used only for hash identity")
    intraop.add_argument(
        "--include-reference-evaluation",
        action="store_true",
        help="Use FI.tif for evaluation only; never treated as a deployment input",
    )
    intraop.add_argument("--output", type=Path, required=True)
    intraop.set_defaults(func=_intraop_pshg)

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

    nuclei_confirm = commands.add_parser("validate-nuclei-confirmatory", help="Run the prospectively frozen BBBC007 transfer test")
    nuclei_confirm.add_argument("--data", type=Path, required=True)
    nuclei_confirm.add_argument("--output", type=Path, required=True)
    nuclei_confirm.set_defaults(func=_validate_nuclei_confirmatory)

    nuclei_bbbc020 = commands.add_parser("validate-nuclei-bbbc020", help="Run the frozen BBBC020 independent-acquisition transfer")
    nuclei_bbbc020.add_argument("--data", type=Path, required=True)
    nuclei_bbbc020.add_argument("--output", type=Path, required=True)
    nuclei_bbbc020.set_defaults(func=_validate_nuclei_bbbc020)

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
    replication.add_argument("--affiliation", default="")
    replication.add_argument("--unaided", action="store_true", help="Attest that no NOSTOS author operated or debugged the run")
    replication.add_argument("--author-environment", action=argparse.BooleanOptionalAction, default=True)
    replication.add_argument("--assistance", default="not declared")
    replication.add_argument("--source-kind", choices=("fresh_clone", "release_archive", "unspecified"), default="unspecified")
    replication.set_defaults(func=_replication_challenge)

    verify_replication = commands.add_parser("verify-replication", help="Verify a returned external replication package")
    verify_replication.add_argument("receipt", type=Path)
    verify_replication.add_argument("--allow-author-run", action="store_true", help="Check integrity without requiring independent-operator eligibility")
    verify_replication.set_defaults(func=_verify_replication)

    compile_profile = commands.add_parser(
        "compile-validity-profile",
        help="Cross-fit and freeze an input-only measurement-validity profile",
    )
    compile_profile.add_argument("development_rows", type=Path, help="Endpoint-level paired development evidence in JSONL format")
    compile_profile.add_argument("--config", type=Path, required=True, help="Prospectively frozen profile configuration")
    compile_profile.add_argument("--output", type=Path, required=True)
    compile_profile.set_defaults(func=_compile_validity_profile)

    audit_profile = commands.add_parser(
        "audit-validity-profile",
        help="Apply a frozen validity profile to untouched paired confirmation evidence",
    )
    audit_profile.add_argument("confirmation_rows", type=Path, help="Endpoint-level paired confirmation evidence in JSONL format")
    audit_profile.add_argument("--profile", type=Path, required=True, help="Frozen validity_profile.json")
    audit_profile.add_argument("--output", type=Path, required=True)
    audit_profile.set_defaults(func=_audit_validity_profile)

    compile_conditional = commands.add_parser(
        "compile-conditional-support",
        help="Freeze acquisition-by-measurement support cells over a calibrated base profile",
    )
    compile_conditional.add_argument("development_rows", type=Path)
    compile_conditional.add_argument("--config", type=Path, required=True)
    compile_conditional.add_argument("--base-profile", type=Path, required=True)
    compile_conditional.add_argument("--output", type=Path, required=True)
    compile_conditional.set_defaults(func=_compile_conditional_support)

    audit_conditional = commands.add_parser(
        "audit-conditional-support",
        help="Apply a frozen hierarchical support overlay to untouched confirmation evidence",
    )
    audit_conditional.add_argument("confirmation_rows", type=Path)
    audit_conditional.add_argument("--config", type=Path, required=True)
    audit_conditional.add_argument("--base-profile", type=Path, required=True)
    audit_conditional.add_argument("--conditional-profile", type=Path, required=True)
    audit_conditional.add_argument("--output", type=Path, required=True)
    audit_conditional.set_defaults(func=_audit_conditional_support)
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
