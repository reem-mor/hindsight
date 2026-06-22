"""Smoke-test the live n8n Cloud HINDSIGHT workflow via the REST API."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

WORKFLOW_ID = "aYEv22StywIPL3Rq"
EXPECTED_NAME_FRAGMENT = "HINDSIGHT"
REQUIRED_NODE_NAMES = {
    "Prepare Document",
    "Gemini — Extract Incident",
    "Parse Gemini JSON",
    "HINDSIGHT Enrich",
    "Compose Outputs",
    "Append to Registry",
    "Is SEV1?",
}


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api_get(base_url: str, api_key: str, path: str) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    req = Request(url, headers={"X-N8N-API-KEY": api_key, "Accept": "application/json"})
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")

    base_url = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud")
    api_key = os.environ.get("N8N_API_KEY", "")
    if not api_key:
        print("SKIP: N8N_API_KEY not set (.env or environment). Add it to run Cloud verification.")
        return 0

    try:
        workflow = api_get(base_url, api_key, f"/api/v1/workflows/{WORKFLOW_ID}")
    except HTTPError as exc:
        print(f"FAIL: n8n API HTTP {exc.code} — check N8N_API_URL and N8N_API_KEY")
        return 1
    except URLError as exc:
        print(f"FAIL: network error — {exc.reason}")
        return 1

    name = workflow.get("name", "")
    if EXPECTED_NAME_FRAGMENT not in name:
        print(f"FAIL: workflow name mismatch — got '{name}'")
        return 1

    nodes = workflow.get("nodes", [])
    node_names = {n.get("name") for n in nodes}
    missing = REQUIRED_NODE_NAMES - node_names
    if missing:
        print(f"FAIL: missing nodes: {sorted(missing)}")
        return 1

    # Credential binding hints (non-fatal)
    bound = []
    for node in nodes:
        creds = node.get("credentials") or {}
        if creds:
            bound.append(node.get("name"))

    print(f"OK: workflow '{name}' ({WORKFLOW_ID}) — {len(nodes)} nodes")
    print(f"    credentials bound on: {', '.join(sorted(bound)) or 'none'}")
    print("    Gemini HTTP node must be bound manually in the n8n UI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
