"""Build the visually audited Small Methods Supporting Information v38."""

from __future__ import annotations

from datetime import datetime, timezone

import build_nostos0_small_methods_si_v37 as v37


def main() -> None:
    root = v37.v36.v35.v34.ROOT
    v37.v36.v35.v34.TITLE = v37.v36.v35.TITLE
    v37.v36.v35.v34.OUTPUT = root / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v38.docx"
    v37.v36.v35.v34.RECEIPTS[:] = list(dict.fromkeys(v37.v36.v35.v34.RECEIPTS))
    original = v37.v36.v35.v34.configure_document

    def configure_document(doc):
        original(doc)
        props = doc.core_properties
        props.subject = "Small Methods Supporting Information v38; frozen computational validation, negative results and audit receipts"
        props.last_modified_by = "Yan Jun Lin"
        props.revision = 1
        props.created = datetime(2026, 8, 31, tzinfo=timezone.utc)
        props.modified = datetime(2026, 8, 31, tzinfo=timezone.utc)

    v37.v36.v35.v34.configure_document = configure_document
    print(v37.v36.v35.v34.build())


if __name__ == "__main__":
    main()
