from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.build_heaton_shg_manifest import sha256_file


def test_manifest_hash_is_exact(tmp_path: Path) -> None:
    path = tmp_path / "example.tif"
    payload = b"not interpreted as pixels\x00\x01\x02"
    path.write_bytes(payload)
    assert sha256_file(path) == hashlib.sha256(payload).hexdigest()

