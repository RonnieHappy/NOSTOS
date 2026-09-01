"""Software-only dry run of the blinded cartilage review evaluator.

The generated masks are analytic rectangles and are never admissible as human
segmentation evidence. This script verifies only the packet/evaluator contract.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from nostos.segmentation.review_evaluate import evaluate_review_packet


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> dict:
    packet = output / "synthetic_packet"
    masks = packet / "reviewed_masks"
    sources = packet / "sources"
    masks.mkdir(parents=True, exist_ok=True)
    sources.mkdir(parents=True, exist_ok=True)
    reviews, crosswalk = [], []
    for index, (stain, site) in enumerate((("SafO", "Medial"), ("SafO", "Lateral"), ("HE", "Medial"), ("PLM", "Medial")), 1):
        case = f"DRY-{index:02d}"
        yy, xx = np.mgrid[:128, :128]
        image = np.stack(((xx + 2 * yy + index) % 255, (2 * xx + yy) % 255, (xx + yy) % 255), axis=-1).astype(np.uint8)
        proposal = np.zeros((128, 128), dtype=np.uint8); proposal[18:110, 12:116] = 1
        reference = proposal > 0
        image_path, proposal_path, reference_path = sources / f"{case}_image.png", sources / f"{case}_proposal.png", masks / f"{case}_reviewed.png"
        Image.fromarray(image).save(image_path); Image.fromarray(proposal).save(proposal_path); Image.fromarray(reference.astype(np.uint8) * 255).save(reference_path)
        audit_path = masks / f"{case}_review.json"
        audit = {
            "case_id": case, "reviewer_id": "AUTHOR_SOFTWARE_DRY_RUN",
            "completed_utc": datetime.now(timezone.utc).isoformat(), "completed_review": True,
            "source_sha256": sha256(image_path), "proposal_sha256": sha256(proposal_path),
            "reference_mask_sha256": sha256(reference_path),
            "inadmissible_as_human_evidence": True,
        }
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        reviews.append({
            "case_id": case, "stain": stain, "site": site,
            "reviewed_mask": reference_path.relative_to(packet).as_posix(),
            "review_audit": audit_path.relative_to(packet).as_posix(),
            "adjudicated_mask": "", "adjudication_audit": "",
            "review_status": "complete", "artifact_burden": "none",
        })
        crosswalk.append({
            "case_id": case, "participant_id": f"{index:03d}", "specimen_id": case,
            "prepared_image": str(image_path), "proposal_mask": str(proposal_path),
            "prepared_image_sha256": sha256(image_path), "proposal_sha256": sha256(proposal_path),
            "pixel_size_um": 2.0,
        })
    pd.DataFrame(reviews).to_csv(packet / "review_manifest.csv", index=False)
    pd.DataFrame(crosswalk).to_csv(packet / "case_crosswalk.csv", index=False)
    result_dir = output / "result"
    receipt = evaluate_review_packet(packet, result_dir)
    wrapper = {
        "protocol_version": "nostos-cartilage-review-evaluator-dry-run/1.0",
        "status": "software_pass" if receipt["status"] == "pass" else "software_fail",
        "case_count": 4,
        "human_review": False,
        "admissible_as_segmentation_validation": False,
        "evaluation_receipt_sha256": sha256(result_dir / "review_evaluation_receipt.json"),
        "claim_boundary": "Analytic masks exercise the evaluator contract only; they provide no human-reference evidence.",
    }
    (output / "dry_run_receipt.json").write_text(json.dumps(wrapper, indent=2) + "\n", encoding="utf-8")
    return wrapper


if __name__ == "__main__":
    destination = Path("outputs/nostos0-cartilage-review-evaluator-dry-run-v1")
    print(json.dumps(run(destination.resolve()), indent=2))
