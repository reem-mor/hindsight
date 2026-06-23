"""Push n8n/cloud/nodes/*.js bodies to the live Cloud workflow."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from n8n_cloud_api import (
    WORKFLOW_ID,
    SHEET_ID_DEFAULT,
    load_dotenv,
    api_get,
    api_request,
    strip_workflow_meta,
    read_node_bodies,
    patch_workflow_nodes,
    ensure_flatten_sheets_node,
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("N8N_API_KEY missing")
        return 1

    sheet_id = os.environ.get("HINDSIGHT_SHEET_ID", SHEET_ID_DEFAULT).strip()
    bodies = read_node_bodies(root)
    wf = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    added_flatten = ensure_flatten_sheets_node(wf, root)
    n = patch_workflow_nodes(wf, bodies, sheet_id=sheet_id)
    payload = strip_workflow_meta(wf)
    api_request(base, key, "PUT", f"/api/v1/workflows/{WORKFLOW_ID}", payload)
    extra = " + Flatten for Sheets node" if added_flatten else ""
    print(f"Synced {n} patch(es) to workflow {WORKFLOW_ID} (sheet {sheet_id}){extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
