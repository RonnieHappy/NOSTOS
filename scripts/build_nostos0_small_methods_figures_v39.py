"""Build the Small Methods v39 figure set with a single visual grammar.

V39 preserves every source pixel and numerical value from v38.  The only
scientific-artwork change is semantic color harmonization in the independently
built tendon panel: acquisition QC remains neutral gray, endpoint QC uses the
paper's coral, and NOSTOS uses the same teal used everywhere else.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import build_nostos0_small_methods_figures_v38 as v38
import build_tlt_pshg_xrd_figure as tendon


ROOT = v38.ROOT
OUT = ROOT / "figures" / "nostos0_small_methods_v39"
TENDON_BUILD = ROOT / "figures" / "nostos0_tlt_pshg_xrd_v39"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _build_inherited_panels() -> None:
    v38.OUT = OUT
    v38._patch_v37()
    v38.v37.main()


def _copy_figure_five() -> None:
    source_base = ROOT / "figures" / "nostos0_pshg_acquisition_shift" / "figure_pshg_acquisition_shift"
    for suffix in ("png", "pdf", "svg"):
        shutil.copy2(source_base.with_suffix(f".{suffix}"), OUT / f"figure_5_pshg_acquisition_shift.{suffix}")


def _build_figure_six() -> None:
    # The estimator, data, selections, statistics, panel geometry and maps are
    # unchanged.  Only the three policy colors are aligned with Figures 1-5.
    tendon.OUTPUT_ROOT = TENDON_BUILD
    tendon.BLUE = "#087F8C"      # NOSTOS
    tendon.TEAL = "#087F8C"
    tendon.ORANGE = "#D96355"    # endpoint QC
    tendon.GRAY = "#66727E"      # acquisition QC
    tendon.INK = "#17212B"
    tendon.LIGHT = "#D7DEE5"
    tendon.main()
    source_base = TENDON_BUILD / "figure_tlt_pshg_xrd_transfer"
    for suffix in ("png", "pdf", "svg"):
        shutil.copy2(source_base.with_suffix(f".{suffix}"), OUT / f"figure_6_tendon_pshg_transfer.{suffix}")


def _write_manifest() -> Path:
    inherited = OUT / "small_methods_figures_v37.manifest.json"
    payload = json.loads(inherited.read_text(encoding="utf-8"))
    payload["schema_version"] = "nostos-small-methods-figures/1.6"
    payload["generated_by"] = Path(__file__).relative_to(ROOT).as_posix()
    payload["generated_by_sha256"] = sha256(Path(__file__))
    payload["declaration"] = (
        "Every microscopy pixel originates in a cited public archive and every map, plot and numerical label is "
        "deterministic. V39 changes no source pixel or scientific value; it harmonizes policy colors and retains "
        "the rejected BioRender composition study outside the submitted artwork."
    )
    payload["semantic_policy_colors"] = {
        "acquisition_qc": "#66727E",
        "endpoint_qc": "#D96355",
        "nostos": "#087F8C",
        "invalid": "#D96355",
        "withheld_or_inactive": "#D7DEE5",
    }
    payload["copied_locked_outputs"] = {}
    for stem in ("figure_5_pshg_acquisition_shift", "figure_6_tendon_pshg_transfer"):
        payload["copied_locked_outputs"][stem] = {}
        for suffix in ("png", "pdf", "svg"):
            path = OUT / f"{stem}.{suffix}"
            payload["copied_locked_outputs"][stem][suffix] = {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    payload.pop("content_sha256", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    output = OUT / "small_methods_figures_v39.manifest.json"
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _build_inherited_panels()
    _copy_figure_five()
    _build_figure_six()
    manifest = _write_manifest()
    print(json.dumps({"status": "complete", "output": str(OUT), "manifest": str(manifest)}, indent=2))


if __name__ == "__main__":
    main()
