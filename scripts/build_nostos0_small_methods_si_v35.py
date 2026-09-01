"""Build the evidence-corrected Small Methods Supporting Information v35."""

from __future__ import annotations

import build_nostos0_small_methods_si_v34 as v34


TITLE = "NOSTOS Exposes and Contains Acquisition-, Scale- and Sample-Specific Failure in Quantitative Microscopy"


def main() -> None:
    v34.TITLE = TITLE
    v34.OUTPUT = v34.ROOT / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v35.docx"
    v34.RECEIPTS.extend(
        [
            v34.ROOT / "outputs" / "nostos0-fmd-widefield-v1-5-extended-confirmation-audit" / "extended_confirmation_audit.json",
            v34.ROOT / "outputs" / "nostos0-fmd-full-archive-strict-support-v1-6-development" / "strict_support_profile.json",
            v34.ROOT / "outputs" / "nostos0-fmd-strict-external-transfer-v1-6-audit-v1-6-1" / "external_transfer_audit.json",
            v34.ROOT / "outputs" / "nostos0-fmd-profile-domain-guard-v1-7-development" / "profile_domain_guard_audit.json",
        ]
    )
    original = v34.configure_document

    def configure_document(doc):
        original(doc)
        doc.core_properties.subject = "Small Methods Supporting Information v35; complete frozen computational validation and failure receipts"

    v34.configure_document = configure_document
    print(v34.build())


if __name__ == "__main__":
    main()

