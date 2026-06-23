"""Find real Google Sheets document IDs in n8n workflows."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from verify_n8n_cloud import load_dotenv, api_get


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    data = api_get(base, key, "/api/v1/workflows?limit=100")
    hits = []
    for wf in data.get("data", []):
        for n in wf.get("nodes", []):
            if "googleSheets" not in n.get("type", ""):
                continue
            doc = n.get("parameters", {}).get("documentId", {})
            val = doc.get("value", "") if isinstance(doc, dict) else ""
            if val and not str(val).startswith("={{") and len(str(val)) > 20:
                hits.append(
                    {
                        "workflow": wf.get("name"),
                        "node": n.get("name"),
                        "documentId": val,
                        "sheet": n.get("parameters", {}).get("sheetName"),
                    }
                )
    print(json.dumps(hits, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
