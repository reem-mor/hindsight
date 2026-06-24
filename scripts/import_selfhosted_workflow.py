"""Import or update the self-hosted HINDSIGHT workflow in Docker n8n.

Applies local-only patches from .env (sheet ID, alert email, credential IDs)
without mutating the tracked workflow JSON on disk.

Usage:
    python scripts/import_selfhosted_workflow.py
    python scripts/import_selfhosted_workflow.py --container hindsight-n8n
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from n8n_cloud_api import SHEET_ID_DEFAULT, load_dotenv  # noqa: E402

WORKFLOW_JSON = ROOT / "n8n" / "hindsight_workflow.json"
CONTAINER_IMPORT = "/data/n8n/_import_workflow.json"
WORKFLOW_NAME = "HINDSIGHT — Cyber Incident Intelligence"
WORKFLOW_ID = "2401581a-0001-4000-8000-hindsight001"

# Stable local credential IDs — create OAuth creds in UI, then re-import or set env overrides.
DEFAULT_GEMINI_CRED_ID = "hindsight-gemini-local-001"
DEFAULT_SHEETS_CRED_ID = "hindsight-sheets-local-001"
DEFAULT_GMAIL_CRED_ID = "hindsight-gmail-local-001"

# Match n8n Cloud credential display names so rebinding is obvious in the UI.
GEMINI_CRED_NAME = "Gemini API"
SHEETS_CRED_NAME = "Google Sheets Amdocs Course API"
GMAIL_CRED_NAME = "Gmail Amdocs course API"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def prepare_local_workflow(wf: dict) -> dict:
    """Patch placeholders for Docker import — does not write back to repo JSON."""
    load_dotenv(ROOT / ".env")
    sheet_id = os.environ.get("HINDSIGHT_SHEET_ID", SHEET_ID_DEFAULT).strip()
    alert_email = os.environ.get("HINDSIGHT_ALERT_EMAIL", "reem.mor3@gmail.com").strip()
    gemini_id = os.environ.get("N8N_LOCAL_GEMINI_CRED_ID", DEFAULT_GEMINI_CRED_ID).strip()
    sheets_id = os.environ.get("N8N_LOCAL_SHEETS_CRED_ID", DEFAULT_SHEETS_CRED_ID).strip()
    gmail_id = os.environ.get("N8N_LOCAL_GMAIL_CRED_ID", DEFAULT_GMAIL_CRED_ID).strip()

    out = copy.deepcopy(wf)
    out["name"] = WORKFLOW_NAME
    if not out.get("id"):
        out["id"] = WORKFLOW_ID

    for node in out.get("nodes", []):
        params = node.setdefault("parameters", {})

        doc = params.get("documentId")
        if isinstance(doc, dict) and str(doc.get("value", "")).startswith("REPLACE_WITH_SHEET"):
            params["documentId"] = {
                "__rl": True,
                "mode": "id",
                "value": sheet_id,
            }

        if node.get("type") == "n8n-nodes-base.gmail" and params.get("sendTo"):
            params["sendTo"] = alert_email if alert_email.startswith("=") else f"={alert_email}"

        creds = node.get("credentials") or {}
        for cred_type, cred in creds.items():
            if not isinstance(cred, dict):
                continue
            cred_id = str(cred.get("id", ""))
            if cred_type == "httpHeaderAuth" and "GEMINI" in cred_id.upper():
                cred["id"] = gemini_id
                cred["name"] = GEMINI_CRED_NAME
            elif cred_type == "googleSheetsOAuth2Api":
                cred["id"] = sheets_id
                cred["name"] = SHEETS_CRED_NAME
            elif cred_type == "gmailOAuth2":
                cred["id"] = gmail_id
                cred["name"] = GMAIL_CRED_NAME

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Import self-hosted n8n workflow from repo JSON")
    parser.add_argument("--container", default="hindsight-n8n", help="Docker container name")
    args = parser.parse_args()

    if not WORKFLOW_JSON.is_file():
        print(f"Missing {WORKFLOW_JSON} — run: python n8n/build_workflow.py")
        return 1

    chk = _run(["docker", "inspect", "-f", "{{.State.Running}}", args.container])
    if chk.returncode != 0 or chk.stdout.strip() != "true":
        print(f"Container {args.container} is not running. Start with: docker compose up -d")
        return 1

    wf = json.loads(WORKFLOW_JSON.read_text(encoding="utf-8"))
    patched = prepare_local_workflow(wf)
    nodes = patched["nodes"]
    sheet_node = next(n for n in nodes if n.get("type") == "n8n-nodes-base.googleSheets")
    sheet_value = sheet_node["parameters"]["documentId"]["value"]

    tmp = ROOT / "n8n" / "_import_workflow.json"
    tmp.write_text(json.dumps(patched, indent=2), encoding="utf-8")

    imp = _run(
        [
            "docker",
            "exec",
            args.container,
            "n8n",
            "import:workflow",
            f"--input={CONTAINER_IMPORT}",
        ]
    )
    tmp.unlink(missing_ok=True)

    if imp.returncode != 0:
        print(imp.stderr or imp.stdout or "import:workflow failed")
        return imp.returncode

    print(f"Imported {WORKFLOW_NAME} into {args.container}")
    print(f"  Sheet ID: {sheet_value}")
    print(f"  Gemini cred id: {os.environ.get('N8N_LOCAL_GEMINI_CRED_ID', DEFAULT_GEMINI_CRED_ID)}")
    print(f"  Sheets cred id: {os.environ.get('N8N_LOCAL_SHEETS_CRED_ID', DEFAULT_SHEETS_CRED_ID)} ({SHEETS_CRED_NAME})")
    print(f"  Gmail cred id:  {os.environ.get('N8N_LOCAL_GMAIL_CRED_ID', DEFAULT_GMAIL_CRED_ID)} ({GMAIL_CRED_NAME})")
    print("OAuth (Sheets/Gmail): create credentials with the names above, then Connect with Google once.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
