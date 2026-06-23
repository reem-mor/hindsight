"""Tests for document extractor (BON-1 Vision path)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "extractors" / "extract_document.py"
SAMPLES = ROOT / "samples"


def test_extractor_plain_markdown() -> None:
    sample = SAMPLES / "vuln_scan_critical_openssl.md"
    proc = subprocess.run(
        [sys.executable, str(EXTRACTOR), str(sample)],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(ROOT),
    )
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["file_type"] == "md"
    assert "CVSS" in data["extracted_text"]
    assert data["char_count"] > 100


def test_extractor_pdf_sample_if_present() -> None:
    pdf = SAMPLES / "vuln_scan_sev1_critical_rce.pdf"
    if not pdf.is_file():
        return
    proc = subprocess.run(
        [sys.executable, str(EXTRACTOR), str(pdf), "--image-dir", str(SAMPLES / "_extract_images")],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(ROOT),
    )
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["file_type"] == "pdf"
    assert data["char_count"] > 0
