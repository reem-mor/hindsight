"""Activate the HINDSIGHT Cloud workflow for grading runs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from n8n_cloud_api import WORKFLOW_ID, load_dotenv, api_get, api_request


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("N8N_API_KEY missing")
        return 1

    wf = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    if wf.get("active"):
        print(f"Workflow {WORKFLOW_ID} already active")
        return 0

    api_request(base, key, "POST", f"/api/v1/workflows/{WORKFLOW_ID}/activate")
    wf2 = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    print(f"Activated workflow {WORKFLOW_ID}: active={wf2.get('active')}")
    return 0 if wf2.get("active") else 1


if __name__ == "__main__":
    sys.exit(main())
