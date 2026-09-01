"""Build the journal-polished Small Methods Supporting Information v39."""

from __future__ import annotations

from datetime import datetime, timezone

from docx import Document

import build_nostos0_small_methods_docx_v39 as main_v39
import build_nostos0_small_methods_si_v38 as v38


def main() -> None:
    root = v38.v37.v36.v35.v34.ROOT
    engine = v38.v37.v36.v35.v34
    engine.TITLE = v38.v37.v36.v35.TITLE
    engine.OUTPUT = root / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v39.docx"
    engine.RECEIPTS[:] = list(dict.fromkeys(engine.RECEIPTS))
    original = engine.configure_document

    def configure_document(doc):
        original(doc)
        props = doc.core_properties
        props.subject = "Small Methods Supporting Information v39; frozen computational validation, negative results and audit receipts"
        props.last_modified_by = "Yan Jun Lin"
        props.revision = 1
        props.created = datetime(2026, 8, 31, tzinfo=timezone.utc)
        props.modified = datetime(2026, 8, 31, tzinfo=timezone.utc)

    engine.configure_document = configure_document
    built = engine.build()
    doc = Document(built)
    main_v39.normalize_all_style_fonts(doc)
    doc.save(built)
    print(built)


if __name__ == "__main__":
    main()
