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
    ensure_bon6_compare_branch,
)
from patch_cloud_workflow import (
    patch_sev1_routing,
    patch_gemini_retry,
    patch_gemini_model,
    patch_form_zip,
    patch_form_copy,
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
    added_bon6 = ensure_bon6_compare_branch(wf, root)
    n = patch_workflow_nodes(wf, bodies, sheet_id=sheet_id)

    # Apply the node-CONFIG patches too, so the single documented deploy step makes
    # BON-4 (retry), BON-7 (.zip), BON-8 (confidential/escalate paging) and the
    # 404-safe model URL reproducible from committed scripts — not a separate manual run.
    cfg = []
    if patch_sev1_routing(wf):
        cfg.append("BON-8 routing")
    if patch_gemini_retry(wf):
        cfg.append("BON-4 retry")
    if patch_gemini_model(wf):
        cfg.append("Gemini model URL")
    if patch_form_zip(wf):
        cfg.append("BON-7 .zip")
    if patch_form_copy(wf):
        cfg.append("form copy")

    payload = strip_workflow_meta(wf)
    api_request(base, key, "PUT", f"/api/v1/workflows/{WORKFLOW_ID}", payload)
    extra = " + Flatten for Sheets node" if added_flatten else ""
    bon6_note = " + BON-6 Flash/Pro compare branch" if added_bon6 else ""
    cfg_note = f" + config[{', '.join(cfg)}]" if cfg else ""
    print(f"Synced {n} node-body patch(es) to workflow {WORKFLOW_ID} (sheet {sheet_id}){extra}{bon6_note}{cfg_note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
