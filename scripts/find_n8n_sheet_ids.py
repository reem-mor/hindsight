"""Scan n8n Cloud workflows for Google Sheets document IDs."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from verify_n8n_cloud import load_dotenv

SHEET_ID_RE = re.compile(r"1[a-zA-Z0-9_-]{20,}")


def api_get(base: str, key: str, path: str) -> dict:
    req = Request(
        f"{base.rstrip('/')}{path}",
        headers={"X-N8N-API-KEY": key, "Accept": "application/json"},
    )
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def walk(obj, found: set[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            walk(v, found)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, found)
    elif isinstance(obj, str):
        for m in SHEET_ID_RE.finditer(obj):
            if len(m.group()) >= 25:
                found.add(m.group())


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud")
    key = os.environ.get("N8N_API_KEY", "")
    if not key or "your-instance" in base:
        base = "https://reemmor.app.n8n.cloud"
    if not key:
        print("N8N_API_KEY missing")
        return 1

    data = api_get(base, key, "/api/v1/workflows?limit=100")
    workflows = data.get("data", [])
    hits: dict[str, list[str]] = {}
    for wf in workflows:
        ids: set[str] = set()
        walk(wf, ids)
        if ids:
            hits[wf.get("name", wf.get("id"))] = sorted(ids)

    print(json.dumps(hits, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
