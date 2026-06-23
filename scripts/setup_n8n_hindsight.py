"""Create HINDSIGHT registry sheet via n8n Google Sheets node + patch Cloud workflow."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from verify_n8n_cloud import load_dotenv, api_get, WORKFLOW_ID

HEADERS = [
    "document_id",
    "processed_at",
    "correlation_id",
    "source_filename",
    "incident_title",
    "incident_type",
    "status",
    "reported_severity",
    "computed_severity",
    "severity_score",
    "severity_review",
    "department",
    "routed_teams",
    "affected_services",
    "affected_jurisdictions",
    "sensitivity",
    "slo_target",
    "budget_burn_pct",
    "budget_breach",
    "recurrence_fingerprint",
    "routing_tags",
    "action_items_total",
    "action_items_unowned",
    "open_p0_actions",
    "confidence_score",
    "ttr_minutes",
    "summary",
]

SHEETS_CRED_ID = "6CH1fQ50fz9t2M9G"  # Google Sheets Amdocs Course API (HINDSIGHT workflow)


def api_call(base: str, key: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = Request(
        url,
        data=data,
        method=method,
        headers={
            "X-N8N-API-KEY": key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urlopen(req, timeout=120) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def patch_hindsight_sheet(base: str, key: str, sheet_id: str) -> None:
    wf = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    for node in wf.get("nodes", []):
        if node.get("name") == "Append to Registry":
            node.setdefault("parameters", {})
            node["parameters"]["documentId"] = {
                "__rl": True,
                "mode": "id",
                "value": sheet_id,
                "cachedResultName": "HINDSIGHT Incident Registry",
            }
            node["parameters"]["sheetName"] = {
                "__rl": True,
                "mode": "name",
                "value": "Incidents",
                "cachedResultName": "Incidents",
            }
    # Send full workflow body (n8n API rejects partial PUT on Cloud)
    for drop in ("createdAt", "updatedAt", "versionId", "meta", "pinData", "tags", "shared", "active"):
        wf.pop(drop, None)
    api_call(base, key, "PUT", f"/api/v1/workflows/{WORKFLOW_ID}", wf)
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
        created = api_call(base, key, "POST", "/api/v1/workflows", bootstrap)
        new_id = created.get("id")
        if not new_id:
            print("Bootstrap create returned no id")
            return None
        print(f"Created bootstrap workflow {new_id}")
        webhook_path = bootstrap["nodes"][0]["parameters"]["path"]
        api_call(base, key, "POST", f"/api/v1/workflows/{new_id}/activate", {})
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
                api_call(base, key, "DELETE", f"/api/v1/workflows/{new_id}", None)
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
