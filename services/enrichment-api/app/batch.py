"""ZIP unpack + text extraction for multi-file batch bonus."""
from __future__ import annotations

import io
import zipfile
from typing import Any


def unpack_zip_bytes(data: bytes, max_files: int = 25, max_bytes_per_file: int = 2_000_000) -> list[dict[str, Any]]:
    """Extract supported text/md files from a ZIP archive."""
    out: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir() or len(out) >= max_files:
                continue
            name = info.filename
            if name.startswith("__MACOSX/") or "/." in name:
                continue
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in {"md", "txt", "markdown"}:
                continue
            if info.file_size > max_bytes_per_file:
                continue
            raw = zf.read(info)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
            out.append(
                {
                    "filename": name.split("/")[-1],
                    "file_type": ext,
                    "extracted_text": text,
                    "char_count": len(text),
                    "ok": True,
                }
            )
    return out
