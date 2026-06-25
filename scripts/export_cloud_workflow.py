"""Export the live Cloud workflow to an importable JSON (credentials stripped).

Lets a reviewer import the EXACT graded workflow into their own n8n and inspect
every node + sticky note without any login. Writes n8n/cloud/hindsight_cloud_workflow.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from n8n_cloud_api import WORKFLOW_ID, load_dotenv, api_get  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv(ROOT / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("N8N_API_KEY missing")
        return 1

    wf = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    nodes = wf.get("nodes", [])
    stripped = 0
    for n in nodes:
        if "credentials" in n:
            n.pop("credentials", None)
            stripped += 1

    export = {
        "name": wf.get("name", "HINDSIGHT — Cyber Incident Intelligence (Cloud)"),
        "nodes": nodes,
        "connections": wf.get("connections", {}),
        "settings": wf.get("settings", {}),
    }
    out = ROOT / "n8n" / "cloud" / "hindsight_cloud_workflow.json"
    out.write_text(json.dumps(export, indent=2), encoding="utf-8")
    sticky = sum(1 for n in nodes if n.get("type", "").endswith("stickyNote"))
    print(f"Exported {len(nodes)} nodes ({sticky} sticky notes), stripped credentials from {stripped} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
