"""Apply a short, clear set of sticky notes to the Daily Digest workflow (BON-2).

Idempotent: strips any existing sticky notes and writes the canonical set below,
laid out around the linear 4-node row. Updates BOTH the live Cloud workflow and the
committed n8n/cloud/digest_workflow.json snapshot so they stay in lockstep.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from n8n_cloud_api import load_dotenv, api_get, api_request, strip_workflow_meta  # noqa: E402

DIGEST_WORKFLOW_ID = "L46dvnaJbKGvkCxH"

# (content, x, y, width, height, color) — short + clear; tall boxes never clip.
STICKIES = [
    (
        "## HINDSIGHT — Daily Digest (BON-2)\n\n"
        "A **separate scheduled** workflow. Once a day it reads the `Incidents` registry, "
        "aggregates the last 24 hours, and emails one SOC summary — so managers get the big "
        "picture, not 50 separate alerts. Complements the per-incident emails from the main pipeline.",
        180, 60, 820, 170, 4,
    ),
    (
        "### 1 · Schedule\n\nCron trigger — fires **daily at 08:00 UTC**.",
        180, 470, 240, 130, 5,
    ),
    (
        "### 2 · Read registry\n\nReads every row from the `Incidents` tab — the same sheet the "
        "main workflow appends to.",
        440, 470, 250, 160, 4,
    ),
    (
        "### 3 · Aggregate · 24h\n\n`digest_aggregate.js` keeps the last 24 h and counts by "
        "**severity / routing_tag / sensitivity**, then builds the HTML digest.",
        700, 470, 280, 175, 6,
    ),
    (
        "### 4 · Email digest\n\nOne clean Gmail summary to the SOC inbox.",
        990, 470, 250, 130, 7,
    ),
]


def _sticky(content: str, x: int, y: int, w: int, h: int, color: int) -> dict:
    return {
        "parameters": {"content": content, "height": h, "width": w, "color": color},
        "id": str(uuid.uuid4()),
        "name": "Sticky Note " + str(uuid.uuid4())[:6],
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [x, y],
    }


def _apply(nodes: list) -> list:
    kept = [n for n in nodes if not n.get("type", "").endswith("stickyNote")]
    kept.extend(_sticky(*s) for s in STICKIES)
    return kept


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("N8N_API_KEY missing")
        return 1

    # 1) Live Cloud digest workflow.
    wf = api_get(base, key, f"/api/v1/workflows/{DIGEST_WORKFLOW_ID}")
    before = sum(1 for n in wf.get("nodes", []) if n.get("type", "").endswith("stickyNote"))
    wf["nodes"] = _apply(wf.get("nodes", []))
    api_request(base, key, "PUT", f"/api/v1/workflows/{DIGEST_WORKFLOW_ID}", strip_workflow_meta(wf))

    # 2) Committed snapshot, so the repo matches the deployed workflow.
    snap_path = root / "n8n" / "cloud" / "digest_workflow.json"
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    snap["nodes"] = _apply(snap.get("nodes", []))
    snap_path.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"Digest workflow {DIGEST_WORKFLOW_ID}: replaced {before} sticky note(s) with "
        f"{len(STICKIES)} clear ones (live + digest_workflow.json)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
