"""Build the compact Small Methods Supporting Information v36."""

from __future__ import annotations

import build_nostos0_small_methods_si_v35 as v35


def main() -> None:
    v35.v34.TITLE = v35.TITLE
    v35.v34.OUTPUT = v35.v34.ROOT / "manuscripts" / "NOSTOS_Small_Methods_Supporting_Information_v36.docx"
    v35.v34.RECEIPTS.extend(
        [
            v35.v34.ROOT / "outputs" / "nostos0-fmd-widefield-v1-5-extended-confirmation-audit" / "extended_confirmation_audit.json",
            v35.v34.ROOT / "outputs" / "nostos0-fmd-full-archive-strict-support-v1-6-development" / "strict_support_profile.json",
            v35.v34.ROOT / "outputs" / "nostos0-fmd-strict-external-transfer-v1-6-audit-v1-6-1" / "external_transfer_audit.json",
            v35.v34.ROOT / "outputs" / "nostos0-fmd-profile-domain-guard-v1-7-development" / "profile_domain_guard_audit.json",
        ]
    )
    # Deduplicate receipts because the v35 wrapper may already have appended them.
    v35.v34.RECEIPTS[:] = list(dict.fromkeys(v35.v34.RECEIPTS))
    original = v35.v34.configure_document

    def configure_document(doc):
        original(doc)
        doc.core_properties.subject = "Small Methods Supporting Information v36; frozen computational validation, negative results and audit receipts"

    v35.v34.configure_document = configure_document
    print(v35.v34.build())


if __name__ == "__main__":
    main()
