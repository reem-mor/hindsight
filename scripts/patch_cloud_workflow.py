"""Patch live Cloud workflow: BON-8 alert routing, BON-7 zip intake, retry audit fields."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from n8n_cloud_api import WORKFLOW_ID, load_dotenv, api_get, api_request, strip_workflow_meta


def patch_sev1_routing(wf: dict) -> bool:
    """Expand Is SEV1? to page on SEV1, confidential, or escalate routing_tag (BON-8)."""
    changed = False
    for node in wf.get("nodes", []):
        if node.get("name") != "Is SEV1?":
            continue
        params = node.setdefault("parameters", {})
        params["conditions"] = {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "combinator": "or",
            "conditions": [
                {
                    "leftValue": "={{ $json.computed_severity }}",
                    "operator": {"type": "string", "operation": "equals"},
                    "rightValue": "SEV1",
                },
                {
                    "leftValue": "={{ $json.sensitivity }}",
                    "operator": {"type": "string", "operation": "equals"},
                    "rightValue": "confidential",
                },
                {
                    "leftValue": "={{ $json.routing_tag }}",
                    "operator": {"type": "string", "operation": "equals"},
                    "rightValue": "escalate",
                },
            ],
        }
        changed = True
    return changed


def patch_form_zip(wf: dict) -> bool:
    """Allow .zip uploads on the form trigger (BON-7)."""
    changed = False
    for node in wf.get("nodes", []):
        if node.get("type") != "n8n-nodes-base.formTrigger":
            continue
        fields = node.get("parameters", {}).get("formFields", {}).get("values", [])
        for field in fields:
            if field.get("fieldType") == "file":
                accept = str(field.get("acceptFileTypes", ""))
                if ".zip" not in accept:
                    field["acceptFileTypes"] = accept + ",.zip" if accept else ".pdf,.md,.txt,.markdown,.zip"
                    changed = True
    return changed


def patch_gemini_retry(wf: dict) -> bool:
    """Ensure Gemini HTTP node has retryOnFail 5× / 3s (BON-4)."""
    changed = False
    for node in wf.get("nodes", []):
        if node.get("name") != "Gemini — Extract Incident":
            continue
        if not node.get("retryOnFail"):
            node["retryOnFail"] = True
            changed = True
        if node.get("maxTries") != 5:
            node["maxTries"] = 5
            changed = True
        if node.get("waitBetweenTries") != 3000:
            node["waitBetweenTries"] = 3000
            changed = True
    return changed


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("N8N_API_KEY missing")
        return 1

    wf = api_get(base, key, f"/api/v1/workflows/{WORKFLOW_ID}")
    patches = []
    if patch_sev1_routing(wf):
        patches.append("BON-8 Is SEV1? routing")
    if patch_form_zip(wf):
        patches.append("BON-7 form .zip accept")
    if patch_gemini_retry(wf):
        patches.append("BON-4 Gemini retry")

    if not patches:
        print("No workflow patches needed")
        return 0

    payload = strip_workflow_meta(wf)
    api_request(base, key, "PUT", f"/api/v1/workflows/{WORKFLOW_ID}", payload)
    print(f"Patched workflow {WORKFLOW_ID}: {', '.join(patches)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
