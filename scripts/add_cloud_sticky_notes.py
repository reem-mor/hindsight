"""Apply a short, clear set of sticky notes to the live Cloud workflow.

Idempotent: removes any existing sticky notes and writes the canonical set below,
positioned around the linear node row. Re-runnable after layout changes.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from n8n_cloud_api import (  # noqa: E402
    WORKFLOW_ID,
    load_dotenv,
    api_get,
    api_request,
    strip_workflow_meta,
)

# (content, x, y, width, height, color)
# Heights are deliberately generous so the box always fully contains its text
# (n8n sticky notes do not auto-grow — short text + a tall box never clips).
STICKIES = [
    (
        "## HINDSIGHT — Cyber Incident Intelligence (Cloud)\n\n"
        "Upload a SIEM export / vuln scan / phishing report → **Gemini 3 Flash** extracts strict JSON → "
        "the deterministic brain re-scores severity → filed to **Google Sheets** + **Gmail**.\n\n"
        "**Setup:** open *Append to Registry* → pick your Sheet (tab `Incidents`). "
        "Gemini / Sheets / Gmail credentials are already bound.",
        140, -120, 700, 250, 4,
    ),
    (
        "### 1 · Intake + Vision\n\n"
        "Form upload. Guards reject empty / wrong-MIME files and fan out ZIPs.\n\n"
        "PDFs are sent as `inline_data` so Gemini Vision reads embedded charts **(BON-1)**.",
        280, 680, 460, 240, 5,
    ),
    (
        "### 2 · Gemini 3 Flash\n\n"
        "Strict JSON, temperature 0.2. Key via n8n credential — never hardcoded.\n\n"
        "Retries **5× / 3s** on 429 rate-limit errors **(BON-4)**.",
        580, 130, 460, 230, 6,
    ),
    (
        "### 3 · Deterministic brain\n\n"
        "The LLM extracts; the **service decides**. CVSS 9.8 floors to SEV1 + `escalate` even if the "
        "author typed SEV3.\n\n"
        "Adds sensitivity, routing tag, SLO burn. Mirrors FastAPI `/enrich`.",
        980, 680, 480, 250, 3,
    ),
    (
        "### 4 · Google Sheets registry\n\n"
        "*Flatten for Sheets* trims to exactly **14 columns**, then appends one row per document to the "
        "`Incidents` tab — the source of truth + dashboard feed **(BON-3)**.",
        1540, -120, 470, 230, 4,
    ),
    (
        "### 5 · Gmail routing\n\n"
        "**Is SEV1?** → SEV1 / confidential / escalate fire a high-priority **Page On-Call (BON-8)**.\n\n"
        "Everything else files a *Postmortem Filed* notice. A separate scheduled workflow sends the 24h digest **(BON-2)**.",
        1640, 740, 500, 250, 7,
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


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("N8N_API_KEY missing")
        return 1

    wf = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    before = len(wf.get("nodes", []))
    wf["nodes"] = [n for n in wf.get("nodes", []) if not n.get("type", "").endswith("stickyNote")]
    removed = before - len(wf["nodes"])
    wf["nodes"].extend(_sticky(*s) for s in STICKIES)

    api_request(base, key, "PUT", f"/api/v1/workflows/{WORKFLOW_ID}", strip_workflow_meta(wf))
    print(f"Cloud workflow {WORKFLOW_ID}: removed {removed} old sticky note(s), added {len(STICKIES)} clear ones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
