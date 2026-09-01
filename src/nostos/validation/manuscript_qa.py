"""Build a machine-readable QA receipt for a rendered NOSTOS manuscript."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image


PROTOCOL_VERSION = "nostos-manuscript-render-qa/1.0"
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PRIVATE_PATH_PATTERN = re.compile(
    r"(?i)(?:[A-Z]:\\Users\\[^\\\s]+|E:\\NOSTOS|C:/Users/[^/\s]+|E:/NOSTOS)"
)
SECRET_PATTERNS = (
    re.compile(r"s2k-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
)
DEFAULT_REQUIRED_TEXT = (
    "NOSTOS: a calibrated and auditable measurement contract",
    "Abstract",
    "Introduction",
    "Results",
    "Discussion",
    "Methods",
    "Data and code availability",
    "Ethics, authorship and competing interests",
    "Figure 1 |",
    "Figure 2 |",
    "Figure 3 |",
    "Figure 4 |",
    "Supplementary Figure 1 |",
    "References",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return f"<EXTERNAL>/{path.name}"


def _xml_root(archive: zipfile.ZipFile, member: str) -> ET.Element | None:
    try:
        return ET.fromstring(archive.read(member))
    except (KeyError, ET.ParseError):
        return None


def _document_audit(docx_path: Path) -> dict:
    with zipfile.ZipFile(docx_path) as archive:
        members = archive.namelist()
        xml_members = [
            name
            for name in members
            if name.startswith("word/") and name.endswith(".xml")
        ]
        styles = _xml_root(archive, "word/styles.xml")
        default_fonts: list[str] = []
        style_fonts: dict[str, list[str]] = {}
        style_parent: dict[str, str] = {}
        if styles is not None:
            defaults = styles.find(
                f".//{WORD_NS}docDefaults/{WORD_NS}rPrDefault/{WORD_NS}rPr/{WORD_NS}rFonts"
            )
            if defaults is not None:
                default_fonts = sorted(set(defaults.attrib.values()))
            for style in styles.findall(f".//{WORD_NS}style"):
                style_id = style.attrib.get(f"{WORD_NS}styleId")
                if not style_id:
                    continue
                fonts = style.find(f"./{WORD_NS}rPr/{WORD_NS}rFonts")
                if fonts is not None:
                    style_fonts[style_id] = sorted(set(fonts.attrib.values()))
                parent = style.find(f"./{WORD_NS}basedOn")
                if parent is not None and parent.attrib.get(f"{WORD_NS}val"):
                    style_parent[style_id] = parent.attrib[f"{WORD_NS}val"]

        def resolved_style_fonts(style_id: str) -> list[str]:
            visited: set[str] = set()
            current = style_id
            while current and current not in visited:
                visited.add(current)
                if current in style_fonts:
                    return style_fonts[current]
                current = style_parent.get(current, "")
            return default_fonts

        visible_text: list[str] = []
        visible_run_fonts: dict[str, int] = {}
        inherited_visible_runs = 0
        inherited_effective_fonts: dict[str, int] = {}
        unresolved_inherited_visible_runs = 0
        inherited_runs_without_times_new_roman = 0
        for member in xml_members:
            root = _xml_root(archive, member)
            if root is None:
                continue
            for node in root.iter(f"{WORD_NS}t"):
                if node.text:
                    visible_text.append(node.text)
            for paragraph in root.iter(f"{WORD_NS}p"):
                style_node = paragraph.find(
                    f"./{WORD_NS}pPr/{WORD_NS}pStyle"
                )
                style_id = (
                    style_node.attrib.get(f"{WORD_NS}val", "Normal")
                    if style_node is not None
                    else "Normal"
                )
                for run in paragraph.iter(f"{WORD_NS}r"):
                    run_text = "".join(
                        node.text or "" for node in run.iter(f"{WORD_NS}t")
                    ).strip()
                    if not run_text:
                        continue
                    fonts = run.find(f".//{WORD_NS}rFonts")
                    if fonts is not None:
                        names = sorted(set(fonts.attrib.values()))
                        for name in names:
                            visible_run_fonts[name] = visible_run_fonts.get(name, 0) + 1
                        continue
                    inherited_visible_runs += 1
                    effective = resolved_style_fonts(style_id)
                    if not effective:
                        unresolved_inherited_visible_runs += 1
                    if "Times New Roman" not in effective:
                        inherited_runs_without_times_new_roman += 1
                    for name in effective:
                        inherited_effective_fonts[name] = (
                            inherited_effective_fonts.get(name, 0) + 1
                        )

        media = sorted(
            name
            for name in members
            if name.startswith("word/media/") and not name.endswith("/")
        )
    text = " ".join(visible_text)
    non_times_visible_fonts = {
        name: count
        for name, count in visible_run_fonts.items()
        if name != "Times New Roman"
    }
    non_times_inherited_fonts = {
        name: count
        for name, count in inherited_effective_fonts.items()
        if name != "Times New Roman"
    }
    return {
        "visible_text": text,
        "visible_text_characters": len(text),
        "embedded_media_count": len(media),
        "embedded_media": media,
        "default_fonts": default_fonts,
        "style_fonts": style_fonts,
        "visible_run_fonts": visible_run_fonts,
        "inherited_visible_runs": inherited_visible_runs,
        "inherited_effective_fonts": inherited_effective_fonts,
        "unresolved_inherited_visible_runs": unresolved_inherited_visible_runs,
        "inherited_runs_without_times_new_roman": (
            inherited_runs_without_times_new_roman
        ),
        "non_times_new_roman_visible_run_fonts": non_times_visible_fonts,
        "non_times_new_roman_inherited_effective_fonts": non_times_inherited_fonts,
    }


def _render_audit(render_dir: Path, pdf_path: Path) -> dict:
    def page_number(path: Path) -> int:
        match = re.search(r"(\d+)$", path.stem)
        return int(match.group(1)) if match else 10**9

    pages = sorted(render_dir.glob("page-*.png"), key=page_number)
    page_records = []
    for page in pages:
        with Image.open(page) as image:
            image.verify()
        with Image.open(page) as image:
            width, height = image.size
        page_records.append(
            {
                "page": page_number(page),
                "file": page.name,
                "bytes": page.stat().st_size,
                "sha256": _sha256(page),
                "width_px": width,
                "height_px": height,
            }
        )
    pdf_header = b""
    pdf_tail = b""
    if pdf_path.is_file():
        with pdf_path.open("rb") as stream:
            pdf_header = stream.read(5)
            if pdf_path.stat().st_size >= 16:
                stream.seek(-16, 2)
                pdf_tail = stream.read(16)
    return {
        "render_directory": render_dir.name,
        "page_count": len(page_records),
        "pages": page_records,
        "page_sequence": [record["page"] for record in page_records],
        "pdf": {
            "file": pdf_path.name,
            "exists": pdf_path.is_file(),
            "bytes": pdf_path.stat().st_size if pdf_path.is_file() else 0,
            "sha256": _sha256(pdf_path) if pdf_path.is_file() else None,
            "has_pdf_header": pdf_header == b"%PDF-",
            "has_eof_marker": b"%%EOF" in pdf_tail,
        },
    }


def _scan_text(text: str) -> dict:
    return {
        "private_absolute_path_found": bool(PRIVATE_PATH_PATTERN.search(text)),
        "possible_secret_found": any(pattern.search(text) for pattern in SECRET_PATTERNS),
    }


def build_manuscript_qa(
    *,
    project_root: Path,
    manuscript_source: Path,
    docx_path: Path,
    render_dir: Path,
    pdf_path: Path,
    output_path: Path,
    expected_pages: int,
    expected_media: int,
    visual_review_passed: bool,
    visual_review_date: str,
    required_text: tuple[str, ...] = DEFAULT_REQUIRED_TEXT,
) -> dict:
    source_text = manuscript_source.read_text(encoding="utf-8")
    document = _document_audit(docx_path)
    rendered = _render_audit(render_dir, pdf_path)
    combined_text = f"{source_text}\n{document['visible_text']}"
    scan = _scan_text(combined_text)

    required_text_presence = {
        fragment: fragment in document["visible_text"] for fragment in required_text
    }
    page_sequence = list(range(1, expected_pages + 1))
    machine_checks = {
        "docx_is_valid_zip": zipfile.is_zipfile(docx_path),
        "expected_page_count": rendered["page_count"] == expected_pages,
        "continuous_page_sequence": rendered["page_sequence"] == page_sequence,
        "all_page_renders_nonempty": all(
            page["bytes"] > 0 and page["width_px"] > 0 and page["height_px"] > 0
            for page in rendered["pages"]
        ),
        "rendered_pdf_valid_envelope": bool(
            rendered["pdf"]["exists"]
            and rendered["pdf"]["bytes"] > 0
            and rendered["pdf"]["has_pdf_header"]
            and rendered["pdf"]["has_eof_marker"]
        ),
        "expected_embedded_media_count": document["embedded_media_count"] == expected_media,
        "times_new_roman_effective_for_visible_text": bool(
            not document["unresolved_inherited_visible_runs"]
            and not document["inherited_runs_without_times_new_roman"]
        ),
        "no_explicit_non_times_visible_runs": not document[
            "non_times_new_roman_visible_run_fonts"
        ],
        "required_sections_and_legends_present": all(required_text_presence.values()),
        "no_private_absolute_paths": not scan["private_absolute_path_found"],
        "no_possible_secrets": not scan["possible_secret_found"],
    }
    machine_status = "pass" if all(machine_checks.values()) else "fail"

    administrative_blockers = []
    blocker_phrases = {
        "archival DOI has not been minted": (
            "archival DOI" in source_text or "DOI must be minted" in source_text
        ),
        "unaided external-user execution has not been received": (
            "unaided external" in source_text
        ),
        "institutional secondary-analysis determination requires confirmation": (
            "institutional requirements for secondary-analysis determination must be confirmed"
            in source_text
        ),
        "affiliation, funding, acknowledgements and competing-interest declarations require author confirmation": (
            "Funding, affiliation, acknowledgements and competing-interest statements require final author confirmation"
            in source_text
        ),
    }
    for label, present in blocker_phrases.items():
        if present:
            administrative_blockers.append(label)

    status = (
        "pass"
        if machine_status == "pass" and visual_review_passed
        else "fail"
    )
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "status": status,
        "scope": "manuscript production and rendered-layout QA only",
        "inputs": {
            "manuscript_source": {
                "path": _relative(manuscript_source, project_root),
                "bytes": manuscript_source.stat().st_size,
                "sha256": _sha256(manuscript_source),
            },
            "docx": {
                "path": _relative(docx_path, project_root),
                "bytes": docx_path.stat().st_size,
                "sha256": _sha256(docx_path),
            },
        },
        "document": {key: value for key, value in document.items() if key != "visible_text"},
        "render": rendered,
        "required_text_presence": required_text_presence,
        "text_safety_scan": scan,
        "machine_checks": machine_checks,
        "machine_status": machine_status,
        "visual_review": {
            "status": "pass" if visual_review_passed else "not_attested",
            "date": visual_review_date,
            "pages_reviewed": page_sequence if visual_review_passed else [],
            "criteria": [
                "no overlap or clipping",
                "panel labels and captions remain legible",
                "figures and captions stay together",
                "page ordering and supplementary-figure identity are correct",
            ],
            "rendering_engine_note": (
                "All pages were reviewed from the LibreOffice-generated QA render; "
                "Microsoft Word and journal-production conversion may reflow the document."
            ),
        },
        "submission_readiness": (
            "blocked_external_and_administrative"
            if administrative_blockers
            else "not_assessed_by_layout_qa"
        ),
        "administrative_blockers": administrative_blockers,
        "nature_readiness": "not_ready",
        "interpretation": (
            "A pass establishes that the current DOCX and its rendered pages satisfy the "
            "declared production checks. It does not establish scientific validity, external "
            "replication, clinical utility, journal fit or acceptance readiness."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return payload
