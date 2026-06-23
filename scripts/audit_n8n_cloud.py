"""Deep audit of HINDSIGHT Cloud workflow — credentials, sheet, emails, activation."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

from n8n_cloud_api import api_get, load_dotenv, WORKFLOW_ID, SHEET_ID_DEFAULT

GEMINI_NODE = "Gemini — Extract Incident"
SHEETS_NODE = "Append to Registry"
PAGE_NODE = "Page On-Call (SEV1)"
DIGEST_NODE = "Postmortem Filed"
REQUIRED_NODE_NAMES = {
    "Prepare Document",
    GEMINI_NODE,
    "Parse Gemini JSON",
    "HINDSIGHT Enrich",
    "Compose Outputs",
    SHEETS_NODE,
    "Is SEV1?",
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("NEEDS_REVIEW: N8N_API_KEY not in .env — add from n8n Settings → API")
        return 1

    try:
        wf = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    except HTTPError as exc:
        print(f"FAIL: n8n API HTTP {exc.code}")
        return 1
    except URLError as exc:
        print(f"FAIL: network error — {exc.reason}")
        return 1

    nodes = {n["name"]: n for n in wf.get("nodes", [])}

    report = {
        "workflow_id": WORKFLOW_ID,
        "name": wf.get("name"),
        "active": wf.get("active"),
        "nodes_total": len(nodes),
        "checks": [],
    }

    def add(status: str, item: str, detail: str = "") -> None:
        report["checks"].append({"status": status, "item": item, "detail": detail})
        mark = "OK" if status == "ok" else "NEEDS_REVIEW" if status == "review" else "FAIL"
        print(f"[{mark}] {item}" + (f" — {detail}" if detail else ""))

    missing = REQUIRED_NODE_NAMES - set(nodes)
    if missing:
        add("fail", "Required nodes", f"missing: {sorted(missing)}")
    else:
        add("ok", "Required nodes", str(len(REQUIRED_NODE_NAMES)))

    add("ok", "Workflow reachable via API", wf.get("name", ""))
    add("ok" if wf.get("active") else "review", "Workflow active", str(wf.get("active")))

    for name in [
        "Submit a Postmortem",
        GEMINI_NODE,
        "HINDSIGHT Enrich",
        SHEETS_NODE,
        PAGE_NODE,
        DIGEST_NODE,
        "Is SEV1?",
    ]:
        if name not in nodes:
            add("fail", f"Node present: {name}", "missing")
        else:
            add("ok", f"Node present: {name}")

    gemini = nodes.get(GEMINI_NODE, {})
    gem_creds = gemini.get("credentials") or {}
    if gem_creds:
        add("ok", "Gemini credential bound", json.dumps(gem_creds))
    else:
        add("review", "Gemini credential bound", "Open node → HTTP Header Auth x-goog-api-key")

    if gemini.get("retryOnFail") and gemini.get("maxTries") == 5 and gemini.get("waitBetweenTries") == 3000:
        add("ok", "Gemini retry policy (BON-4)", "retryOnFail 5× / 3000ms")
    else:
        add("review", "Gemini retry policy (BON-4)", json.dumps({
            "retryOnFail": gemini.get("retryOnFail"),
            "maxTries": gemini.get("maxTries"),
            "waitBetweenTries": gemini.get("waitBetweenTries"),
        }))

    gem_params = gemini.get("parameters", {})
    url = str(gem_params.get("url", ""))
    if "gemini-3-flash" in url:
        add("review", "Gemini model string", "gemini-3-flash — try gemini-3-flash-preview if 404")

    sheets = nodes.get(SHEETS_NODE, {})
    sheets_creds = sheets.get("credentials") or {}
    sheets_p = sheets.get("parameters", {})
    doc = sheets_p.get("documentId") or sheets_p.get("sheetName") or sheets_p
    if sheets_creds:
        add("ok", "Google Sheets credential bound", json.dumps(sheets_creds))
    else:
        add("review", "Google Sheets credential bound", "OAuth2 required")
    doc_val = doc.get("value", "") if isinstance(doc, dict) else str(doc)
    if doc_val:
        add("ok", "Sheets spreadsheet ID", doc_val)
    else:
        add("review", "Sheets spreadsheet ID", f"empty — run setup with {SHEET_ID_DEFAULT}")

    sheet_name = sheets_p.get("sheetName", {})
    tab = sheet_name.get("value", "Incidents") if isinstance(sheet_name, dict) else "Incidents"
    add("review", "Sheets tab name (verify in Google UI)", f"'{tab}' — must exist; run scripts/bootstrap_incidents_tab.py if missing")

    opts = sheets_p.get("options") or {}
    handling = opts.get("handlingExtraData", "unknown")
    if handling == "ignoreIt":
        add("ok", "Sheets handling extra fields", "ignoreIt")
    else:
        add("review", "Sheets handling extra fields", f"{handling} — set to ignoreIt (sync_n8n_cloud_nodes.py)")

    if nodes.get("Flatten for Sheets"):
        add("ok", "Flatten for Sheets node", "present — Sheets gets 14 columns only")
    else:
        add("review", "Flatten for Sheets node", "missing — run sync_n8n_cloud_nodes.py")

    for label, node_name in [(PAGE_NODE, PAGE_NODE), (DIGEST_NODE, DIGEST_NODE)]:
        n = nodes.get(node_name, {})
        creds = n.get("credentials") or {}
        to = n.get("parameters", {}).get("sendTo") or n.get("parameters", {}).get("toEmail")
        if creds:
            add("ok", f"Gmail credential ({label})", json.dumps(creds))
        else:
            add("review", f"Gmail credential ({label})", "OAuth2 required")
        add("review", f"Email To ({label})", str(to or "set sendTo in node"))

    # Credentials list from API
    try:
        creds_resp = api_get(base, key, "/api/v1/credentials")
        cred_list = creds_resp.get("data", creds_resp if isinstance(creds_resp, list) else [])
        types = {}
        for c in cred_list:
            t = c.get("type", "unknown")
            types.setdefault(t, []).append(c.get("name", c.get("id")))
        add("ok", "Credentials in instance", json.dumps(types))
    except Exception as exc:
        add("review", "Credentials list API", str(exc))

    # Recent executions
    try:
        ex = api_get(base, key, f"/api/v1/executions?workflowId={WORKFLOW_ID}&limit=3")
        rows = ex.get("data", [])
        add("ok", "Recent executions", ", ".join(f"{e['id']}={e['status']}" for e in rows) or "none")
    except Exception as exc:
        add("review", "Executions API", str(exc))

    out = root / "docs" / "n8n-cloud-audit.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nAudit saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
