"""Import local n8n credentials from .env (Gemini Header Auth). Never prints secrets."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from n8n_cloud_api import load_dotenv  # noqa: E402

CONTAINER = "hindsight-n8n"
IMPORT_PATH = ROOT / "n8n" / "_import_credentials.json"
CONTAINER_IMPORT = "/data/n8n/_import_credentials.json"
DEFAULT_GEMINI_CRED_ID = "hindsight-gemini-local-001"
SHEETS_CRED_NAME = "Google Sheets Amdocs Course API"
GMAIL_CRED_NAME = "Gmail Amdocs course API"
DEFAULT_SHEETS_CRED_ID = "hindsight-sheets-local-001"
DEFAULT_GMAIL_CRED_ID = "hindsight-gmail-local-001"


def main() -> int:
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("GEMINI_API_KEY missing in .env")
        return 1

    gemini_id = os.environ.get("N8N_LOCAL_GEMINI_CRED_ID", DEFAULT_GEMINI_CRED_ID).strip()
    sheets_id = os.environ.get("N8N_LOCAL_SHEETS_CRED_ID", DEFAULT_SHEETS_CRED_ID).strip()
    gmail_id = os.environ.get("N8N_LOCAL_GMAIL_CRED_ID", DEFAULT_GMAIL_CRED_ID).strip()

    payload = [
        {
            "id": gemini_id,
            "name": "Gemini API",
            "type": "httpHeaderAuth",
            "data": {
                "name": "x-goog-api-key",
                "value": api_key,
            },
        },
        {
            "id": sheets_id,
            "name": SHEETS_CRED_NAME,
            "type": "googleSheetsOAuth2Api",
            "data": {},
        },
        {
            "id": gmail_id,
            "name": GMAIL_CRED_NAME,
            "type": "gmailOAuth2",
            "data": {},
        },
    ]
    IMPORT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cmd = [
        "docker",
        "exec",
        CONTAINER,
        "n8n",
        "import:credentials",
        f"--input={CONTAINER_IMPORT}",
        "--decrypted",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    IMPORT_PATH.unlink(missing_ok=True)

    if proc.returncode != 0:
        print(proc.stderr or proc.stdout or "import:credentials failed")
        return proc.returncode

    print(f"Imported credentials: Gemini ({gemini_id}), Sheets ({sheets_id}), Gmail ({gmail_id})")
    print("Connect Sheets + Gmail in n8n UI (Credentials) with the same Google account as Cloud.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
