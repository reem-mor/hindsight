"""Create Incidents tab + header row in the HINDSIGHT registry spreadsheet via n8n."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from n8n_cloud_api import SHEET_ID_DEFAULT, load_dotenv, api_request

SHEETS_CRED_ID = "6CH1fQ50fz9t2M9G"
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


def _header_row_code() -> str:
    pairs = ", ".join(f"{h}: '{h}'" for h in HEADERS)
    return f"return [{{ json: {{ {pairs} }} }}];"


def try_bootstrap_incidents_tab(base: str, key: str, sheet_id: str) -> bool:
    """Write header row via n8n. Uses Sheet1 if Incidents tab missing — rename tab after."""
    webhook_path = f"hindsight-incidents-tab-{uuid.uuid4().hex[:8]}"
    set_node = "Build Header Row"
    append_node = "Append Header Row"
    bootstrap = {
        "name": "HINDSIGHT Bootstrap — Incidents headers (delete me)",
        "nodes": [
            {
                "id": str(uuid.uuid4()),
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [0, 0],
                "parameters": {
                    "path": webhook_path,
                    "httpMethod": "POST",
                    "responseMode": "lastNode",
                },
                "webhookId": str(uuid.uuid4()),
            },
            {
                "id": str(uuid.uuid4()),
                "name": set_node,
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [220, 0],
                "parameters": {
                    "mode": "runOnceForAllItems",
                    "language": "javaScript",
                    "jsCode": _header_row_code(),
                },
            },
            {
                "id": str(uuid.uuid4()),
                "name": append_node,
                "type": "n8n-nodes-base.googleSheets",
                "typeVersion": 4.7,
                "position": [440, 0],
                "parameters": {
                    "resource": "sheet",
                    "operation": "append",
                    "documentId": {
                        "__rl": True,
                        "mode": "id",
                        "value": sheet_id,
                    },
                    "sheetName": {
                        "__rl": True,
                        "mode": "name",
                        "value": "Sheet1",
                    },
                    "columns": {
                        "mappingMode": "defineBelow",
                        "value": {h: h for h in HEADERS},
                    },
                    "options": {
                        "handlingExtraData": "ignoreIt",
                        "useAppend": True,
                        "cellFormat": "USER_ENTERED",
                    },
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
            "Webhook": {"main": [[{"node": set_node, "type": "main", "index": 0}]]},
            set_node: {"main": [[{"node": append_node, "type": "main", "index": 0}]]},
        },
        "settings": {"executionOrder": "v1"},
    }
    try:
        created = api_request(base, key, "POST", "/api/v1/workflows", bootstrap)
        new_id = created.get("id")
        if not new_id:
            print("Bootstrap returned no workflow id")
            return False
        print(f"Created bootstrap workflow {new_id}")
        api_request(base, key, "POST", f"/api/v1/workflows/{new_id}/activate", {})
        webhook_url = f"{base}/webhook/{webhook_path}"
        print(f"Calling {webhook_url}")
        req = Request(webhook_url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode())
        print("Bootstrap response:", json.dumps(body)[:600])
        try:
            api_request(base, key, "DELETE", f"/api/v1/workflows/{new_id}", None)
        except HTTPError:
            pass
        print("NEXT: In Google Sheets rename tab 'Sheet1' to 'Incidents' (exact name).")
        return True
    except HTTPError as exc:
        body = exc.read().decode() if exc.fp else str(exc)
        print(f"Bootstrap failed: {body[:800]}")
        return False


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("N8N_API_KEY missing")
        return 1
    sheet_id = os.environ.get("HINDSIGHT_SHEET_ID", SHEET_ID_DEFAULT).strip()
    if len(sys.argv) > 1:
        sheet_id = sys.argv[1].strip()
    ok = try_bootstrap_incidents_tab(base, key, sheet_id)
    if ok:
        print("OK: Header row written — rename Sheet1 to Incidents then re-run workflow")
        return 0
    print("NEEDS_REVIEW: Rename Sheet1 to Incidents manually and paste headers from SETUP-GUIDE row 1.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
