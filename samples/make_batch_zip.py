"""Create sample batch zip fixture for BON-7 tests."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "samples" / "batch_incidents.zip"

FILES = {
    "siem_alert.md": (ROOT / "samples" / "siem_bruteforce_intrusion.md").read_text(encoding="utf-8"),
    "phishing_report.txt": (ROOT / "samples" / "phishing_kyc_credential_harvest.md").read_text(encoding="utf-8"),
}


def main() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for name, text in FILES.items():
            zf.writestr(name, text)
    OUT.write_bytes(buf.getvalue())
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
