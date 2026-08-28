"""Create a frozen outcome-blinded cartilage mask review packet."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.ndimage import binary_erosion


PROTOCOL = "nostos-cartilage-mask-review/1.1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _blind_id(source_sha256: str) -> str:
    return "CMR-" + hashlib.sha256(f"{PROTOCOL}:{source_sha256}".encode()).hexdigest()[:10].upper()


def _thumbnail(image: Image.Image, max_side: int = 1400) -> Image.Image:
    result = image.convert("RGB")
    result.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return result


def build_review_packet(annotation_root: Path, output: Path) -> dict:
    manifest = pd.read_csv(annotation_root / "annotation_manifest.csv", dtype={"participant_id": str})
    provenance = json.loads((annotation_root / "source_provenance.json").read_text(encoding="utf-8"))
    source_by_key = {
        (str(row["participant_id"]).zfill(3), row["specimen_id"]): row for row in provenance
    }
    selected = manifest[manifest["split"] == "validation"].copy()
    if selected.empty:
        raise ValueError("No locked validation cases were found in the annotation manifest.")
    output.mkdir(parents=True, exist_ok=True)
    review_dir = output / "review_images"
    correction_dir = output / "reviewed_masks"
    review_dir.mkdir(exist_ok=True)
    correction_dir.mkdir(exist_ok=True)
    review_rows, crosswalk_rows = [], []
    for row in selected.itertuples(index=False):
        participant = str(row.participant_id).zfill(3)
        provenance_row = source_by_key[(participant, row.specimen_id)]
        source_sha = provenance_row["source_sha256"]
        blind_id = _blind_id(source_sha)
        image_path = annotation_root / row.image_path
        stem = Path(row.image_path).stem
        proposal_path = annotation_root / "proposals" / f"{stem}_proposal.png"
        if not proposal_path.is_file():
            raise FileNotFoundError(proposal_path)
        image = Image.open(image_path).convert("RGB")
        # Proposal PNGs use the shared semantic ontology. Only class 1 is
        # articular cartilage; outlining every non-background class would
        # misleadingly include calcified cartilage, bone and void/artifact.
        proposal = np.asarray(Image.open(proposal_path).convert("L")) == 1
        if proposal.shape != (image.height, image.width):
            raise ValueError(f"Proposal/image shape mismatch for {blind_id}")
        boundary = proposal ^ binary_erosion(proposal, iterations=2)
        overlay = np.asarray(image).copy()
        overlay[boundary] = (0, 255, 255)
        original_out = review_dir / f"{blind_id}_image.png"
        overlay_out = review_dir / f"{blind_id}_proposal.png"
        _thumbnail(image).save(original_out, optimize=True)
        _thumbnail(Image.fromarray(overlay)).save(overlay_out, optimize=True)
        correction_path = correction_dir / f"{blind_id}_reviewed.png"
        review_rows.append({
            "case_id": blind_id,
            "stain": row.stain,
            "site": row.site,
            "image": original_out.relative_to(output).as_posix(),
            "proposal_overlay": overlay_out.relative_to(output).as_posix(),
            "reviewed_mask": correction_path.relative_to(output).as_posix(),
            "review_audit": f"reviewed_masks/{blind_id}_review.json",
            "second_reviewed_mask": "",
            "second_review_audit": "",
            "adjudicated_mask": "",
            "adjudication_audit": "",
            "reviewer_id": "",
            "second_reviewer_id": "",
            "adjudicator_id": "",
            "review_status": "pending",
            "cartilage_present": "",
            "artifact_burden": "",
            "reviewer_notes": "",
        })
        crosswalk_rows.append({
            "case_id": blind_id, "participant_id": participant, "specimen_id": row.specimen_id,
            "source_sha256": source_sha, "prepared_image_sha256": _sha256(image_path),
            "proposal_sha256": _sha256(proposal_path), "pixel_size_um": provenance_row["model_pixel_size_um"],
            "prepared_image": str(image_path), "proposal_mask": str(proposal_path),
        })
    review = pd.DataFrame(review_rows).sort_values("case_id")
    crosswalk = pd.DataFrame(crosswalk_rows).sort_values("case_id")
    review.to_csv(output / "review_manifest.csv", index=False)
    crosswalk.to_csv(output / "case_crosswalk.csv", index=False)
    receipt = {
        "protocol_version": PROTOCOL,
        "selection": "all images from the pre-existing participant-locked validation split",
        "outcome_fields_in_review_manifest": 0,
        "case_count": len(review),
        "participant_count": int(crosswalk["participant_id"].nunique()),
        "stain_counts": review["stain"].value_counts().sort_index().to_dict(),
        "site_counts": review["site"].value_counts().sort_index().to_dict(),
        "review_status": "pending_human_reference_masks",
        "required_audit_fields": ["case_id", "reviewer_id", "completed_utc", "completed_review", "source_sha256", "proposal_sha256", "reference_mask_sha256"],
        "limitation": "Case identifiers are pseudonymized and outcomes are absent; this is not independent double blinding.",
    }
    (output / "packet_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the frozen outcome-blinded cartilage mask review packet.")
    parser.add_argument("annotation_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = build_review_packet(args.annotation_root.resolve(), args.output.resolve())
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
