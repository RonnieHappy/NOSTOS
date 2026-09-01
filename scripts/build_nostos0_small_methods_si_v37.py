"""Build the final-audit Small Methods Supporting Information v37."""

from __future__ import annotations

from datetime import datetime, timezone

import build_nostos0_small_methods_si_v36 as v36


def main() -> None:
    v36.v35.v34.TITLE = v36.v35.TITLE
    v36.v35.v34.OUTPUT = v36.v35.v34.ROOT / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v37.docx"
    v36.v35.v34.RECEIPTS[:] = list(dict.fromkeys(v36.v35.v34.RECEIPTS))
    original = v36.v35.v34.configure_document

    def configure_document(doc):
        original(doc)
        props = doc.core_properties
        props.subject = "Small Methods Supporting Information v37; frozen computational validation, negative results and audit receipts"
        props.last_modified_by = "Yan Jun Lin"
        props.revision = 1
        props.created = datetime(2026, 8, 31, tzinfo=timezone.utc)
        props.modified = datetime(2026, 8, 31, tzinfo=timezone.utc)

    v36.v35.v34.configure_document = configure_document
    print(v36.v35.v34.build())


if __name__ == "__main__":
    main()
