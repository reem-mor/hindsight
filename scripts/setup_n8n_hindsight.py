"""Create HINDSIGHT registry sheet via n8n Google Sheets node + patch Cloud workflow."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from n8n_cloud_api import (
    WORKFLOW_ID,
    SHEET_ID_DEFAULT,
    load_dotenv,
    api_get,
    api_request,
    strip_workflow_meta,
    patch_workflow_nodes,
)

HEADERS = [
    "document_id",
    "filename",
    "file_type",
    "processed_at",
    "classification",
    "department",
    "sentiment",
    "confidence_score",
    "summary",
    "routing_tag",
    "sensitivity",
    "action_items",
    "cvss_score",
    "cve_ids",
]

# Resolved from N8N_SHEETS_CRED_ID after .env loads (no vault IDs hardcoded in repo).
SHEETS_CRED_ID = os.environ.get("N8N_SHEETS_CRED_ID", "")


def patch_hindsight_sheet(base: str, key: str, sheet_id: str) -> None:
    wf = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    patch_workflow_nodes(wf, {}, sheet_id=sheet_id)
    api_request(base, key, "PUT", f"/api/v1/workflows/{WORKFLOW_ID}", strip_workflow_meta(wf))
    print(f"Patched workflow {WORKFLOW_ID} with spreadsheet {sheet_id}")


def try_create_via_bootstrap(base: str, key: str) -> str | None:
    """Attempt one-shot workflow: Manual Trigger -> Google Sheets create spreadsheet."""
    wf_id = str(uuid.uuid4())
    node_id = str(uuid.uuid4())
    bootstrap = {
        "name": "HINDSIGHT Bootstrap — Create Registry Sheet (delete me)",
        "nodes": [
            {
                "id": str(uuid.uuid4()),
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [0, 0],
                "parameters": {
                    "path": f"hindsight-bootstrap-{uuid.uuid4().hex[:8]}",
                    "httpMethod": "POST",
                    "responseMode": "lastNode",
                },
                "webhookId": str(uuid.uuid4()),
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Create Spreadsheet",
                "type": "n8n-nodes-base.googleSheets",
                "typeVersion": 4.7,
                "position": [220, 0],
                "parameters": {
                    "resource": "spreadsheet",
                    "operation": "create",
                    "title": "HINDSIGHT Incident Registry",
                    "options": {},
                },
                "credentials": {
                    "googleSheetsOAuth2Api": {
                        "id": SHEETS_CRED_ID,
                        "name": "Google Sheets Amdocs Course API",
                    }
                },
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Create Spreadsheet", "type": "main", "index": 0}]]},
        },
        "settings": {"executionOrder": "v1"},
    }
    try:
        created = api_request(base, key, "POST", "/api/v1/workflows", bootstrap)
        new_id = created.get("id")
        if not new_id:
            print("Bootstrap create returned no id")
            return None
        print(f"Created bootstrap workflow {new_id}")
        webhook_path = bootstrap["nodes"][0]["parameters"]["path"]
        api_request(base, key, "POST", f"/api/v1/workflows/{new_id}/activate", {})
        webhook_url = f"{base}/webhook/{webhook_path}"
        print(f"Calling webhook {webhook_url}")
        req = Request(webhook_url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=120) as resp:
            run_body = json.loads(resp.read().decode())
        print("Webhook response:", json.dumps(run_body)[:500])
        sheet_id = run_body.get("spreadsheetId") or run_body.get("id")
        if not sheet_id and isinstance(run_body, list) and run_body:
            sheet_id = run_body[0].get("spreadsheetId")
        if sheet_id:
            try:
                api_request(base, key, "DELETE", f"/api/v1/workflows/{new_id}", None)
            except HTTPError:
                pass
            return sheet_id
        print("Could not parse spreadsheetId from run — check bootstrap workflow in n8n UI")
        return None
    except HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        print(f"Bootstrap failed HTTP {exc.code}: {body[:500]}")
        return None


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("N8N_API_KEY missing")
        return 1

    global SHEETS_CRED_ID
    SHEETS_CRED_ID = os.environ.get("N8N_SHEETS_CRED_ID", "").strip()
    if not SHEETS_CRED_ID:
        print("N8N_SHEETS_CRED_ID missing — set it in .env to the n8n Google Sheets credential ID")
        return 1

    sheet_id = os.environ.get("HINDSIGHT_SHEET_ID", "").strip()
    if len(sys.argv) > 1:
        sheet_id = sys.argv[1].strip()

    if not sheet_id:
        print("Attempting to create spreadsheet via n8n bootstrap workflow...")
        sheet_id = try_create_via_bootstrap(base, key) or ""

    if not sheet_id:
        print(
            "NEEDS_REVIEW: Could not auto-create sheet. Create manually, then run:\n"
            "  python scripts/setup_n8n_hindsight.py <SPREADSHEET_ID>"
        )
        return 1

    patch_hindsight_sheet(base, key, sheet_id)
    print("Bootstrapping Incidents tab + headers (if missing)...")
    import subprocess

    subprocess.run(
        [sys.executable, str(root / "scripts" / "bootstrap_incidents_tab.py"), sheet_id],
        check=False,
    )
    meta = root / "docs" / "hindsight-sheet-id.txt"
    meta.write_text(
        f"spreadsheet_id={sheet_id}\n"
        f"url=https://docs.google.com/spreadsheets/d/{sheet_id}/edit\n"
        f"tab=Incidents\n",
        encoding="utf-8",
    )
    print(f"Saved {meta}")
    print("NEEDS_REVIEW: Add Incidents tab + header row in Google Sheets UI if not created automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
