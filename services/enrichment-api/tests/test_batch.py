"""Tests for multi-file batch unzip (BON-7)."""
from __future__ import annotations

import io
import zipfile

from pathlib import Path

from app.batch import unpack_zip_bytes


def _make_zip(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in entries.items():
            zf.writestr(name, text)
    return buf.getvalue()


def test_unpack_zip_fan_out() -> None:
    data = _make_zip({
        "incidents/scan_a.md": "# Scan A\nCVSS 9.8",
        "incidents/scan_b.txt": "phishing attempt",
        "incidents/readme.pdf": "ignored",
    })
    files = unpack_zip_bytes(data)
    assert len(files) == 2
    names = {f["filename"] for f in files}
    assert names == {"scan_a.md", "scan_b.txt"}
    assert all(f["ok"] for f in files)
    assert files[0]["char_count"] > 0


def test_unpack_batch_fixture_zip() -> None:
    fixture = Path(__file__).resolve().parents[3] / "samples" / "batch_incidents.zip"
    assert fixture.is_file()
    files = unpack_zip_bytes(fixture.read_bytes())
    assert len(files) == 2
