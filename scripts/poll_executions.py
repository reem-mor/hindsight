"""Poll n8n executions and print batch fan-out details."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from n8n_cloud_api import WORKFLOW_ID, load_dotenv  # noqa: E402


def main() -> int:
    load_dotenv(ROOT / ".env")
    key = os.environ.get("N8N_API_KEY", "")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    eids = sys.argv[1:] or ["522", "523", "524"]

    for i in range(30):
        statuses: dict[str, str] = {}
        for eid in eids:
            req = urllib.request.Request(
                f"{base}/api/v1/executions/{eid}",
                headers={"X-N8N-API-KEY": key},
            )
            data = json.loads(urllib.request.urlopen(req, timeout=60).read())
            statuses[eid] = data.get("status", "?")
        print(f"poll {i}: {statuses}", flush=True)
        if all(s != "running" for s in statuses.values()):
            break
        time.sleep(10)

    for eid in eids:
        req = urllib.request.Request(
            f"{base}/api/v1/executions/{eid}?includeData=true",
            headers={"X-N8N-API-KEY": key},
        )
        data = json.loads(urllib.request.urlopen(req, timeout=120).read())
        status = data.get("status")
        rd = data.get("data", {}).get("resultData", {}).get("runData", {})
        prep = rd.get("Prepare Document", [{}])[0]
        main = (prep.get("data") or {}).get("main", [[]])[0] or []
        files = [(row.get("json") or {}).get("sourceFilename") for row in main]
        print(f"exec {eid} {status} prepare_items={len(files)} files={files}", flush=True)
        for node, runs in rd.items():
            if runs and runs[0].get("error"):
                print(f"  ERR {node}: {runs[0]['error'].get('message', '')[:160]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
