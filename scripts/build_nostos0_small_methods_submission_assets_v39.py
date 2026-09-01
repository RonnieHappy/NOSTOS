"""Export the v39 Small Methods artwork as 600 dpi LZW TIFF files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures" / "nostos0_small_methods_v39"
OUT = ROOT / "manuscripts" / "Small_Methods_v39_submission_assets" / "figures"
MANIFEST = OUT.parent / "artwork_manifest.json"

SOURCES = {
    "Figure_1.tif": FIG / "figure_1_measurement_contract.png",
    "Figure_2.tif": FIG / "figure_2_biosr_confirmation.png",
    "Figure_3.tif": FIG / "figure_3_falsification_and_repair.png",
    "Figure_4.tif": FIG / "figure_4_external_domain_failure.png",
    "Figure_5.tif": FIG / "figure_5_pshg_acquisition_shift.png",
    "Figure_6.tif": FIG / "figure_6_tendon_pshg_transfer.png",
    "Figure_S1.tif": ROOT / "figures" / "nostos0_small_methods_si" / "figure_s1_synthetic_validation.png",
    "Figure_S2.tif": ROOT / "figures" / "nostos0" / "figure_3_bone_validation.png",
    "Figure_S3.tif": ROOT / "figures" / "nostos0" / "supplementary_figure_1_bone_contract_stress.png",
    "Table_of_Contents.tif": FIG / "nostos_small_methods_toc.png",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    missing = [str(path) for path in SOURCES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(missing)
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for name, source in SOURCES.items():
        target = OUT / name
        with Image.open(source) as image:
            rgba = image.convert("RGBA")
            source_size = rgba.size
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            background.save(target, format="TIFF", compression="tiff_lzw", dpi=(600, 600))
        with Image.open(target) as check:
            if check.size != source_size:
                raise RuntimeError(f"TIFF dimension mismatch: {name}")
            dpi = tuple(round(value) for value in check.info.get("dpi", (0, 0)))
            if dpi != (600, 600):
                raise RuntimeError(f"TIFF dpi mismatch: {name}: {dpi}")
        records.append(
            {
                "file": target.relative_to(ROOT).as_posix(),
                "source": source.relative_to(ROOT).as_posix(),
                "width_px": background.size[0],
                "height_px": background.size[1],
                "dpi": 600,
                "compression": "LZW",
                "sha256": sha256(target),
            }
        )
    payload = {"schema": "nostos.small-methods.artwork.v39", "files": records}
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(MANIFEST)


if __name__ == "__main__":
    main()
