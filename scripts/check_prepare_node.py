"""Verify live Cloud Prepare Document node body."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from n8n_cloud_api import WORKFLOW_ID, load_dotenv, api_get  # noqa: E402


def main() -> int:
    load_dotenv(ROOT / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    wf = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    nodes = wf.get("nodes", [])
    for n in nodes:
        if n.get("name") == "Prepare Document":
            js = n["parameters"].get("jsCode", "")
            print("zlib require:", "require(\"zlib\")" in js)
            print("offset = 0:", "let offset = 0;" in js)
            print("eocd + 16:", "eocd + 16" in js)
            return 0
    print("Prepare Document node not found")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
