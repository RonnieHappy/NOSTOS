from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.manuscript_qa import build_manuscript_qa


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the NOSTOS manuscript production and render-QA receipt."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("docs/NOSTOS0_SOFTWARE_RESOURCE_ARTICLE.md"),
    )
    parser.add_argument(
        "--docx",
        type=Path,
        default=Path("docs/NOSTOS0_software_resource_submission_candidate.docx"),
    )
    parser.add_argument(
        "--render-dir", type=Path, default=Path("tmp/docx_render_v27")
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path(
            "tmp/docx_render_v27/NOSTOS0_software_resource_submission_candidate.pdf"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/nostos0-manuscript-qa-v1/manuscript_qa.json"),
    )
    parser.add_argument("--expected-pages", type=int, default=8)
    parser.add_argument("--expected-media", type=int, default=5)
    parser.add_argument(
        "--visual-review-passed",
        action="store_true",
        help="Attest only after every rendered page has been inspected.",
    )
    parser.add_argument("--visual-review-date", default="2026-08-28")
    args = parser.parse_args()
    payload = build_manuscript_qa(
        project_root=args.project_root,
        manuscript_source=args.source,
        docx_path=args.docx,
        render_dir=args.render_dir,
        pdf_path=args.pdf,
        output_path=args.output,
        expected_pages=args.expected_pages,
        expected_media=args.expected_media,
        visual_review_passed=args.visual_review_passed,
        visual_review_date=args.visual_review_date,
    )
    print(json.dumps(payload, indent=2))
    if payload["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
