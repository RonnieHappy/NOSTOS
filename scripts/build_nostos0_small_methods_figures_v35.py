"""Build the evidence-corrected NOSTOS Small Methods v35 main figures.

Figures 1 and 2 retain the established authentic BioSR/FMD visual language but
use the conservative three-cell support profile. Figures 3 and 4 are rebuilt
around the failed v1.5 extension, failed v1.6 external transfer and explicit
post-failure claim-boundary guard. No generated microscopy is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

import build_nostos0_small_methods_figures as sm
import build_nostos0_validity_figures as vf


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "nostos0_small_methods_v35"
sm.OUT = OUT

INK = sm.INK
MID = sm.MID
LIGHT = sm.LIGHT
PALE = sm.PALE
TEAL = sm.TEAL
TEAL_LIGHT = sm.TEAL_LIGHT
BLUE = sm.BLUE
RED = sm.RED
RED_DARK = sm.RED_DARK
AMBER = sm.AMBER
WHITE = sm.WHITE

mpl.rcParams.update(
    {
        "font.family": "Times New Roman",
        "font.serif": ["Times New Roman"],
        "font.size": 7.4,
        "axes.titlesize": 7.6,
        "axes.labelsize": 7.2,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "svg.fonttype": "none",
        "svg.hashsalt": "nostos-small-methods-v35",
        "pdf.fonttype": 42,
    }
)


def panel(ax: mpl.axes.Axes, letter: str) -> None:
    writer = getattr(ax, "text2D", ax.text)
    writer(
        -0.065,
        1.012,
        letter,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9.0,
        fontweight="bold",
        color=INK,
        clip_on=False,
        zorder=50,
    )


sm.panel = panel


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def accepted(row: Mapping[str, Any], threshold: float) -> bool:
    return not bool(row["candidate_hard_abstention"]) and float(
        row["calibrated_risk"]
    ) <= threshold


def load_external_pair(
    archive: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    source_key: str,
    field: int,
) -> tuple[np.ndarray, np.ndarray]:
    row = next(
        item
        for item in rows
        if item["metadata"]["transfer_source_key"] == source_key
        and int(item["metadata"]["field_of_view"]) == int(field)
        and item["metadata"]["acquisition_level"] == "avg16"
        and item["endpoint_family"] == "tensor_coherence"
        and float(item["requested_scale_value"]) == 16.0
    )
    with tarfile.open(archive, mode="r:") as opened:
        input_image = vf.read_tar_image(opened, row["metadata"]["input_member"])
        reference_image = vf.read_tar_image(opened, row["metadata"]["reference_member"])
    return input_image, reference_image


def support_strip(ax: mpl.axes.Axes, *, before: bool) -> None:
    ax.set_xlim(-0.55, 3.55)
    ax.set_ylim(-0.55, 0.55)
    ax.axis("off")
    values = [
        ("16·4", TEAL),
        ("16·8", TEAL),
        ("16·16", TEAL),
        ("8·16", RED if before else LIGHT),
    ]
    for index, (label, color) in enumerate(values):
        ax.add_patch(
            Rectangle(
                (index - 0.38, -0.25),
                0.76,
                0.50,
                facecolor=color,
                edgecolor=WHITE,
                linewidth=0.7,
            )
        )
        ax.text(index, -0.41, label, ha="center", va="top", fontsize=6.4)


def figure3(
    fmd: Mapping[str, Any],
    extension_rows: Sequence[Mapping[str, Any]],
    extension_audit: Mapping[str, Any],
    strict_profile: Mapping[str, Any],
    strict_audit: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    threshold = float(extension_audit["frozen_profile"]["predicted_risk_threshold"])
    focus = [
        row
        for row in extension_rows
        if row["endpoint_family"] == "tensor_coherence"
        and row["metadata"]["acquisition_level"] == "avg8"
        and float(row["requested_scale_value"]) == 16.0
        and accepted(row, threshold)
    ]
    assert (len(focus), sum(bool(row["invalid"]) for row in focus)) == (26, 6)

    fig = plt.figure(figsize=(7.08, 3.95))
    fig.subplots_adjust(left=0.065, right=0.99, top=0.975, bottom=0.105, hspace=0.13, wspace=0.55)
    gs = fig.add_gridspec(2, 15, height_ratios=[0.92, 1.18])

    ladder = gs[0, :].subgridspec(1, 6, wspace=0.035)
    for index, level in enumerate(("raw", "avg2", "avg4", "avg8", "avg16", "avg50")):
        ax = fig.add_subplot(ladder[0, index])
        sm.image_axis(
            ax,
            vf.robust_unit(fmd["ladder"][level], 1, 99.5),
            level.replace("avg", "×"),
            cmap="gray",
        )
        if index == 0:
            panel(ax, "a")

    ax = fig.add_subplot(gs[1, :5])
    panel(ax, "b")
    fields = [3, 12, 6, 8, 4, 2, 10]
    for index, field in enumerate(fields):
        subset = [row for row in focus if int(row["metadata"]["field_of_view"]) == field]
        for repeat_index, row in enumerate(subset):
            jitter = (repeat_index - (len(subset) - 1) / 2) * 0.055
            ax.scatter(
                index + jitter,
                float(row["error"]),
                s=25,
                color=RED if bool(row["invalid"]) else TEAL,
                edgecolor=WHITE,
                linewidth=0.5,
                zorder=3,
            )
    ax.axhline(0.15, color=RED_DARK, lw=1.0, ls=(0, (3, 2)))
    ax.set_xticks(range(len(fields)), fields)
    ax.set_xlabel("field")
    ax.set_ylabel("|Δ coherence|")
    ax.set_ylim(0, 0.19)
    ax.set_yticks([0, 0.05, 0.10, 0.15])
    sm.clean_axes(ax)

    ax = fig.add_subplot(gs[1, 5:9])
    panel(ax, "c")
    ax.text(0.5, 0.94, "v1.5", transform=ax.transAxes, ha="center", va="top", fontweight="bold")
    inset = ax.inset_axes([0.04, 0.50, 0.92, 0.26])
    support_strip(inset, before=True)
    ax.annotate("", xy=(0.5, 0.36), xytext=(0.5, 0.48), xycoords="axes fraction", arrowprops={"arrowstyle": "-|>", "color": MID, "lw": 1.0})
    inset = ax.inset_axes([0.04, 0.07, 0.92, 0.26])
    support_strip(inset, before=False)
    ax.text(0.5, 0.01, "v1.6", transform=ax.transAxes, ha="center", va="bottom", fontweight="bold")
    ax.axis("off")

    ax = fig.add_subplot(gs[1, 9:12])
    panel(ax, "d")
    summary = extension_audit["extension"]["field_event_summary"]
    rate = float(summary["field_event_rate"])
    low, high = map(float, summary["field_event_exact_ci"])
    ax.errorbar(rate, 0, xerr=[[rate - low], [high - rate]], fmt="o", color=RED, ecolor=INK, elinewidth=1.3, capsize=4, markersize=6)
    ax.axvline(0, color=LIGHT, lw=0.8)
    ax.set_xlim(-0.03, 0.75)
    ax.set_ylim(-0.6, 0.6)
    ax.set_yticks([])
    ax.set_xlabel("field failure rate")
    ax.text(rate, 0.30, "2/7", ha="center", color=RED_DARK, fontweight="bold", fontsize=8.2)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)

    ax = fig.add_subplot(gs[1, 12:])
    panel(ax, "e")
    groups = int(strict_profile["supported_cells"][0]["field_event_summary"]["fields"])
    upper = float(
        strict_profile["supported_cells"][0]["field_event_summary"][
            "two_sided_exact_ci95"
        ][1]
    )
    cols = 5
    for index in range(groups):
        x, y = index % cols, 3 - index // cols
        ax.scatter(x, y, s=170, facecolor=TEAL_LIGHT, edgecolor=WHITE, linewidth=0.5)
    ax.set_xlim(-0.5, 4.5)
    ax.set_ylim(-1.2, 4.0)
    ax.axis("off")
    ax.text(2, -0.35, "0/19", ha="center", va="top", color=TEAL, fontweight="bold", fontsize=8.3)
    ax.text(2, -0.85, f"upper 95% {upper:.1%}", ha="center", va="top", color=MID, fontsize=6.4)
    assert [cell["values"] for cell in strict_profile["supported_cells"]] == [["avg16", 16.0], ["avg16", 4.0], ["avg16", 8.0]]
    return sm.save_figure(fig, "figure_3_failure_extension_and_repair")


def figure4(
    certified_image: np.ndarray,
    confocal_image: np.ndarray,
    widefield_g_image: np.ndarray,
    external_rows: Sequence[Mapping[str, Any]],
    external_audit: Mapping[str, Any],
    guard_audit: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    fig = plt.figure(figsize=(7.08, 4.10))
    fig.subplots_adjust(left=0.065, right=0.99, top=0.975, bottom=0.105, hspace=0.14, wspace=0.55)
    gs = fig.add_gridspec(2, 15, height_ratios=[1.22, 1.0])
    top = gs[0, :].subgridspec(1, 6, wspace=0.035)
    source_images = [
        (certified_image, "widefield · mitochondria"),
        (confocal_image, "confocal · mitochondria"),
        (widefield_g_image, "widefield · F-actin"),
    ]
    coherence_axes = []
    coherence_mappable = None
    for group, (image, label) in enumerate(source_images):
        rgb, coherence = vf.orientation_rgb(image, sigma=4.0)
        ax = fig.add_subplot(top[0, group * 2])
        sm.image_axis(ax, vf.robust_unit(image, 1, 99.5), label, cmap="gray")
        if group == 0:
            ax.text(0.018, 0.982, "a", transform=ax.transAxes, ha="left", va="top", color=WHITE, fontsize=9.0, fontweight="bold")
        ax = fig.add_subplot(top[0, group * 2 + 1])
        coherence_mappable = ax.imshow(coherence, cmap="magma", vmin=0.0, vmax=1.0, interpolation="nearest")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.text(0.5, 1.025, "coherence", transform=ax.transAxes, ha="center", va="bottom", fontweight="bold")
        coherence_axes.append(ax)
    color_axis = coherence_axes[-1].inset_axes([0.18, -0.085, 0.64, 0.025])
    colorbar = fig.colorbar(coherence_mappable, cax=color_axis, orientation="horizontal")
    colorbar.set_ticks([0, 1])
    colorbar.ax.tick_params(labelsize=5.8, length=1.5, pad=1)
    colorbar.outline.set_linewidth(0.4)

    ax = fig.add_subplot(gs[1, :6])
    panel(ax, "b")
    source_order = ["Confocal_BPAE_R", "WideField_BPAE_G"]
    display_names = ["confocal R", "widefield G"]
    source_summaries = {item["dataset_key"]: item["field_event_summary"] for item in external_audit["per_source"]}
    xpos = 0
    xticks = []
    xlabels = []
    for source, display in zip(source_order, display_names, strict=True):
        for field in source_summaries[source]["fields"]:
            accepted_n = int(field["accepted"])
            invalid_n = int(field["invalid"])
            if accepted_n == 0:
                ax.scatter(xpos, 0, marker="x", color=MID, s=28, linewidth=1.2)
            else:
                risk = invalid_n / accepted_n
                ax.scatter(xpos, risk, color=RED if risk else TEAL, s=34, edgecolor=WHITE, linewidth=0.5)
            xticks.append(xpos)
            xlabels.append(field["reference_group_id"].split("fov")[-1])
            xpos += 1
        xpos += 1
    ax.axhline(0.15, color=RED_DARK, lw=0.9, ls=(0, (3, 2)))
    ax.axvline(7, color=LIGHT, lw=0.9)
    ax.set_xticks(xticks, xlabels)
    ax.set_xlabel("field")
    ax.set_ylabel("accepted risk")
    ax.set_ylim(-0.08, 1.08)
    ax.text(3, 1.02, display_names[0], ha="center", va="bottom", fontsize=6.7)
    ax.text(11, 1.02, display_names[1], ha="center", va="bottom", fontsize=6.7)
    sm.clean_axes(ax)

    ax = fig.add_subplot(gs[1, 6:10])
    panel(ax, "c")
    before = guard_audit["external"]["before_guard"]
    after = guard_audit["external"]["after_guard"]
    ax.bar([0, 1], [before["accepted"], after["accepted"]], color=[AMBER, LIGHT], width=0.58)
    ax.bar([0, 1], [before["invalid"], after["invalid"]], color=[RED, RED], width=0.58)
    ax.set_xticks([0, 1], ["unscoped", "guarded"])
    ax.set_ylabel("outputs")
    ax.set_ylim(0, 92)
    ax.text(0, before["accepted"] + 4, f"{before['invalid']}/{before['accepted']}", ha="center", color=RED_DARK, fontweight="bold")
    ax.text(1, 4, "0", ha="center", color=MID, fontweight="bold")
    sm.clean_axes(ax)

    ax = fig.add_subplot(gs[1, 10:])
    panel(ax, "d")
    matrix = np.array([[1, 1, 1], [0, 1, 0], [1, 0, 0]], dtype=int)
    cmap = mpl.colors.ListedColormap([LIGHT, TEAL_LIGHT])
    ax.imshow(matrix, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks([0, 1, 2], ["modality", "sample", "emit"])
    ax.set_yticks([0, 1, 2], ["widefield R", "confocal R", "widefield G"])
    for i in range(3):
        for j in range(3):
            ax.text(j, i, "●" if matrix[i, j] else "×", ha="center", va="center", color=INK if matrix[i, j] else MID, fontsize=8.5, fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    assert external_audit["status"] == "fail"
    assert before["accepted"] == 84 and before["invalid"] == 36
    assert after["accepted"] == 0 and after["invalid"] == 0
    return sm.save_figure(fig, "figure_4_external_scope_failure")


def toc_figure(
    fmd: Mapping[str, Any], strict_profile: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    """Export the wide Small Methods ToC graphic at exactly 110 x 20 mm.

    The journal's wide ToC format is aspect-ratio sensitive. The general figure
    saver uses a tight bounding box, which expands this very shallow artwork to
    about 110 x 25 mm when it includes the short labels above the image axes.
    This dedicated export preserves the exact canvas instead.
    """

    image = vf.center_crop(fmd["ladder"]["avg8"], 430)
    orientation, _ = vf.orientation_rgb(image, sigma=2.0)
    supported = {
        (str(cell["values"][0]), float(cell["values"][1]))
        for cell in strict_profile["supported_cells"]
    }
    fig = plt.figure(figsize=(110 / 25.4, 20 / 25.4))
    fig.subplots_adjust(
        left=0.005, right=0.995, bottom=0.025, top=0.84, wspace=0.12
    )
    gs = fig.add_gridspec(1, 8)
    ax = fig.add_subplot(gs[0, 0:2])
    sm.image_axis(ax, vf.robust_unit(image), "image", cmap="gray")
    ax = fig.add_subplot(gs[0, 2:4])
    sm.image_axis(ax, orientation, "measure", cmap=None)
    ax = fig.add_subplot(gs[0, 4:6])
    sm.draw_support_lattice(ax, supported, failed=("avg8", 8.0))
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.text(
        0.5,
        1.05,
        "support",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontweight="bold",
        fontsize=8,
    )
    ax = fig.add_subplot(gs[0, 6:])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(
        FancyBboxPatch(
            (0.12, 0.56),
            0.76,
            0.27,
            boxstyle="round,pad=0.01,rounding_size=0.03",
            facecolor="#D8EFEE",
            edgecolor=TEAL,
            linewidth=1.3,
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (0.12, 0.12),
            0.76,
            0.27,
            boxstyle="round,pad=0.01,rounding_size=0.03",
            facecolor="#F1F3F5",
            edgecolor="#AAB3BA",
            linewidth=1.3,
        )
    )
    ax.text(
        0.5,
        0.695,
        "emit",
        ha="center",
        va="center",
        color=TEAL,
        fontweight="bold",
        fontsize=8,
    )
    ax.text(
        0.5,
        0.255,
        "abstain",
        ha="center",
        va="center",
        color=MID,
        fontweight="bold",
        fontsize=8,
    )

    outputs: dict[str, dict[str, Any]] = {}
    for suffix, kwargs in (
        ("png", {"dpi": 600, "metadata": {"Software": "NOSTOS"}}),
        (
            "pdf",
            {
                "metadata": {
                    "Creator": "NOSTOS",
                    "Producer": "Matplotlib",
                    "CreationDate": None,
                    "ModDate": None,
                }
            },
        ),
        ("svg", {"metadata": {"Creator": "NOSTOS", "Date": None}}),
    ):
        path = OUT / f"nostos_small_methods_toc.{suffix}"
        fig.savefig(path, bbox_inches=None, pad_inches=0, **kwargs)
        outputs[suffix] = {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    plt.close(fig)
    return outputs


def build_manifest(outputs: Mapping[str, Any], sources: Sequence[Path], archives: Sequence[Path]) -> Path:
    payload = {
        "schema_version": "nostos-small-methods-figures/1.2",
        "status": "complete",
        "generated_by": Path(__file__).relative_to(ROOT).as_posix(),
        "generated_by_sha256": sha256(Path(__file__)),
        "declaration": "Every microscopy pixel originates in a cited public BioSR or FMD archive. All maps and summaries are deterministic. No generated microscopy, anatomy or measurement appears in these figures.",
        "font": {"family": "Times New Roman", "resolved_path": sm.TIMES_PATH},
        "outputs": outputs,
        "sources": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in sources],
        "archives": [{"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in archives],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "small_methods_figures_v35.manifest.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark"))
    args = parser.parse_args()
    paths = {
        "biosr_rows": ROOT / "outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation/tensor_cases.jsonl",
        "biosr_receipt": ROOT / "outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation/confirmation_receipt.json",
        "v14_rows": ROOT / "outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation-audit/confirmation_scored.jsonl",
        "v15_rows": ROOT / "outputs/nostos0-fmd-widefield-v1-5-extended-confirmation-audit/extension_scored.jsonl",
        "v15_audit": ROOT / "outputs/nostos0-fmd-widefield-v1-5-extended-confirmation-audit/extended_confirmation_audit.json",
        "strict_profile": ROOT / "outputs/nostos0-fmd-full-archive-strict-support-v1-6-development/strict_support_profile.json",
        "strict_audit": ROOT / "outputs/nostos0-fmd-full-archive-strict-support-v1-6-development/development_audit.json",
        "external_rows": ROOT / "outputs/nostos0-fmd-strict-external-transfer-v1-6-audit-v1-6-1/external_transfer_scored.jsonl",
        "external_audit": ROOT / "outputs/nostos0-fmd-strict-external-transfer-v1-6-audit-v1-6-1/external_transfer_audit.json",
        "guard_audit": ROOT / "outputs/nostos0-fmd-profile-domain-guard-v1-7-development/profile_domain_guard_audit.json",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(missing)
    biosr_rows = vf.read_jsonl(paths["biosr_rows"])
    biosr_receipt = read_json(paths["biosr_receipt"])
    v14_rows = vf.read_jsonl(paths["v14_rows"])
    extension_rows = vf.read_jsonl(paths["v15_rows"])
    extension_audit = read_json(paths["v15_audit"])
    strict_profile = read_json(paths["strict_profile"])
    strict_audit = read_json(paths["strict_audit"])
    external_rows = vf.read_jsonl(paths["external_rows"])
    external_audit = read_json(paths["external_audit"])
    guard_audit = read_json(paths["guard_audit"])
    biosr = vf.load_biosr_example(args.data_root, biosr_rows)
    widefield_r_archive = args.data_root / "fmd" / "WideField_BPAE_R.tar"
    fmd = vf.load_fmd_images(widefield_r_archive, v14_rows, (1, 5, 14, 20))
    external_root = args.data_root / "fmd" / "external-transfer"
    confocal_archive = external_root / "Confocal_BPAE_R.tar"
    widefield_g_archive = external_root / "WideField_BPAE_G.tar"
    confocal_image, _ = load_external_pair(confocal_archive, external_rows, source_key="Confocal_BPAE_R", field=7)
    widefield_g_image, _ = load_external_pair(widefield_g_archive, external_rows, source_key="WideField_BPAE_G", field=1)
    outputs = {
        "figure_1": sm.figure1(biosr, biosr_rows, fmd, strict_profile),
        "figure_2": sm.figure2(biosr, biosr_rows, biosr_receipt),
        "figure_3": figure3(fmd, extension_rows, extension_audit, strict_profile, strict_audit),
        "figure_4": figure4(fmd["fields"][14]["avg16"], confocal_image, widefield_g_image, external_rows, external_audit, guard_audit),
        "toc": toc_figure(fmd, strict_profile),
    }
    manifest = build_manifest(outputs, list(paths.values()), [biosr["archive"], widefield_r_archive, confocal_archive, widefield_g_archive])
    print(json.dumps({"status": "complete", "outputs": outputs, "manifest": str(manifest)}, indent=2))


if __name__ == "__main__":
    main()
