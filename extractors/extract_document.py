#!/usr/bin/env python3
"""HINDSIGHT document extractor.

Called by the n8n "Execute Command" node. Given a file path, it extracts plain
text and any embedded images (so the workflow can optionally send dashboard
screenshots to Gemini Vision), and prints a single JSON object to stdout for n8n
to parse.

Usage:
    python extract_document.py /path/to/postmortem.pdf [--image-dir /tmp/hs_images]

Output (stdout, JSON):
    {
      "filename": "postmortem.pdf",
      "file_type": "pdf",
      "extracted_text": "....",
      "char_count": 1234,
      "images": [{"path": "/tmp/hs_images/postmortem_p1_0.png", "page": 1}],
      "ok": true
    }

Dependencies are imported lazily so the script degrades gracefully if a parser
is missing (it reports the problem in JSON instead of crashing the workflow).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile


def _err(filename: str, file_type: str, message: str) -> dict:
    return {
        "filename": filename,
        "file_type": file_type,
        "extracted_text": "",
        "char_count": 0,
        "images": [],
        "ok": False,
        "error": message,
    }


def extract_pdf(path: str, image_dir: str) -> dict:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return _err(os.path.basename(path), "pdf", "PyMuPDF (fitz) not installed: pip install pymupdf")

    text_parts: list[str] = []
    images: list[dict] = []
    base = os.path.splitext(os.path.basename(path))[0]

    with fitz.open(path) as doc:
        for page_index, page in enumerate(doc, start=1):
            text_parts.append(page.get_text("text"))
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n - pix.alpha >= 4:  # CMYK/other → convert to RGB
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    out = os.path.join(image_dir, f"{base}_p{page_index}_{img_index}.png")
                    pix.save(out)
                    images.append({"path": out, "page": page_index})
                    pix = None
                except Exception as exc:  # noqa: BLE001
                    # Don't fail the whole extraction on one bad image.
                    images.append({"path": None, "page": page_index, "error": str(exc)})

    text = "\n".join(text_parts).strip()
    return {
        "filename": os.path.basename(path),
        "file_type": "pdf",
        "extracted_text": text,
        "char_count": len(text),
        "images": images,
        "ok": True,
    }


def extract_docx(path: str) -> dict:
    try:
        import docx  # python-docx
    except ImportError:
        return _err(os.path.basename(path), "docx", "python-docx not installed: pip install python-docx")

    document = docx.Document(path)
    parts = [p.text for p in document.paragraphs]
    # Include table cell text — postmortems often use tables for timelines.
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    text = "\n".join(parts).strip()
    return {
        "filename": os.path.basename(path),
        "file_type": "docx",
        "extracted_text": text,
        "char_count": len(text),
        "images": [],
        "ok": True,
    }


def extract_text(path: str, file_type: str) -> dict:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read().strip()
    return {
        "filename": os.path.basename(path),
        "file_type": file_type,
        "extracted_text": text,
        "char_count": len(text),
        "images": [],
        "ok": True,
    }


def extract(path: str, image_dir: str) -> dict:
    if not os.path.isfile(path):
        return _err(os.path.basename(path), "unknown", f"file not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    os.makedirs(image_dir, exist_ok=True)
    if ext == ".pdf":
        return extract_pdf(path, image_dir)
    if ext == ".docx":
        return extract_docx(path)
    if ext in (".txt", ".md", ".markdown", ".log"):
        return extract_text(path, ext.lstrip("."))
    return _err(os.path.basename(path), ext.lstrip("."), f"unsupported file type: {ext}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract text + images from a document.")
    parser.add_argument("path", help="Path to the document")
    parser.add_argument(
        "--image-dir",
        default=os.path.join(tempfile.gettempdir(), "hindsight_images"),
        help="Directory to write extracted images",
    )
    args = parser.parse_args()
    result = extract(args.path, args.image_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
