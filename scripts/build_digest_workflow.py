"""Inject digest_aggregate.js body into digest_workflow.json for import."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    wf_path = root / "n8n" / "cloud" / "digest_workflow.json"
    js_path = root / "n8n" / "cloud" / "nodes" / "digest_aggregate.js"
    wf = json.loads(wf_path.read_text(encoding="utf-8"))
    body = js_path.read_text(encoding="utf-8")
    for node in wf.get("nodes", []):
        if node.get("name") == "Aggregate Digest":
            node.setdefault("parameters", {})["jsCode"] = body
    wf_path.write_text(json.dumps(wf, indent=2), encoding="utf-8")
    print(f"Updated {wf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
