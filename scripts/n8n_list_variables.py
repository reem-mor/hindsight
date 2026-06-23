"""Fetch n8n instance variables and optional workflow patch for sheet ID."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from verify_n8n_cloud import load_dotenv, api_get, WORKFLOW_ID


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("N8N_API_KEY missing")
        return 1

    try:
        vars_resp = api_get(base, key, "/api/v1/variables")
        print("Variables:")
        for v in vars_resp.get("data", vars_resp if isinstance(vars_resp, list) else []):
            print(f"  {v.get('key')} = {v.get('value')}")
    except Exception as exc:
        print(f"Variables API: {exc}")

    wf = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    for node in wf.get("nodes", []):
        if node.get("name") == "Append to Registry":
            print("Append to Registry documentId:", json.dumps(node.get("parameters", {}).get("documentId")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
