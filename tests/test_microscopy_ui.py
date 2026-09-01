import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workstation_dom_has_unique_ids_and_required_operator_states() -> None:
    html = (ROOT / "microscopy_app/index.html").read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    for required in (
        'value="label_free_pshg"',
        'id="orientationMap"',
        'id="coherenceMap"',
        'id="supportMap"',
        'id="measurementState"',
        'id="evidenceState"',
        "Clinical output withheld",
    ):
        assert required in html


def test_workstation_visible_copy_and_css_pass_static_preflight() -> None:
    html = (ROOT / "microscopy_app/index.html").read_text(encoding="utf-8")
    js = (ROOT / "microscopy_app/app.js").read_text(encoding="utf-8")
    css = (ROOT / "microscopy_app/style.css").read_text(encoding="utf-8")
    assert "—" not in html + js
    assert "–" not in html + js
    assert "prefers-reduced-motion" in css
    assert "@media (max-width: 760px)" in css
    assert "#000000" not in css and "#ffffff" not in css
    assert "window.addEventListener('scroll'" not in js
