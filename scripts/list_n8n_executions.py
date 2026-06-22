"""List recent executions for the HINDSIGHT Cloud workflow."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from verify_n8n_cloud import load_dotenv, WORKFLOW_ID

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("SKIP: N8N_API_KEY not set")
        return 0
    req = Request(
        f"{base}/api/v1/executions?workflowId={WORKFLOW_ID}&limit=10",
        headers={"X-N8N-API-KEY": key, "Accept": "application/json"},
    )
    data = json.loads(urlopen(req, timeout=60).read())
    rows = data.get("data", [])
    if not rows:
        print("No executions found for workflow", WORKFLOW_ID)
        return 0
    for ex in rows:
        print(
            ex.get("id"),
            ex.get("status"),
            ex.get("mode"),
            ex.get("startedAt"),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
