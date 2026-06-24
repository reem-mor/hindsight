"""End-to-end verification: core pipeline + all 8 bonus challenges."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from n8n_cloud_api import (  # noqa: E402
    WORKFLOW_ID,
    load_dotenv,
    api_get,
    api_request,
)

MAIN_WF = WORKFLOW_ID
DIGEST_WF = "L46dvnaJbKGvkCxH"
API = os.environ.get("ENRICHMENT_API_URL", "http://127.0.0.1:8000").rstrip("/")
EXTRACTOR = ROOT / "extractors" / "extract_document.py"
VENV = ROOT / ".venv" / "Scripts" / "python.exe"


def ok(label: str, cond: bool, detail: str = "") -> bool:
    status = "PASS" if cond else "FAIL"
    line = f"[{status}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return cond


def post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def activate_workflow(base: str, key: str, wf_id: str) -> bool:
    wf = api_get(base, key, f"/api/v1/workflows/{wf_id}")
    if wf.get("active"):
        return True
    api_request(base, key, "POST", f"/api/v1/workflows/{wf_id}/activate", {})
    wf2 = api_get(base, key, f"/api/v1/workflows/{wf_id}")
    return bool(wf2.get("active"))


def check_gemini_retry(wf: dict) -> bool:
    for node in wf.get("nodes", []):
        if node.get("name") == "Gemini — Extract Incident":
            return (
                node.get("retryOnFail") is True
                and node.get("maxTries") == 5
                and node.get("waitBetweenTries") == 3000
            )
    return False


def check_bon8_if(wf: dict) -> bool:
    for node in wf.get("nodes", []):
        if node.get("name") != "Is SEV1?":
            continue
        conds = node.get("parameters", {}).get("conditions", {})
        if conds.get("combinator") != "or":
            return False
        rights = {c.get("rightValue") for c in conds.get("conditions", [])}
        return {"SEV1", "confidential", "escalate"}.issubset(rights)
    return False


def main() -> int:
    load_dotenv(ROOT / ".env")
    base = os.environ.get("N8N_API_URL", "https://reemmor.app.n8n.cloud").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        print("N8N_API_KEY missing")
        return 1

    passed = 0
    total = 0

    print("\n=== Workflow activation ===")
    total += 1
    if ok("Main Cloud workflow active", activate_workflow(base, key, MAIN_WF)):
        passed += 1
    total += 1
    if ok("Digest Cloud workflow active", activate_workflow(base, key, DIGEST_WF)):
        passed += 1

    wf = api_get(base, key, f"/api/v1/workflows/{MAIN_WF}")

    print("\n=== Bonus challenges (live/config) ===")

    # BON-1 Vision
    pdf = ROOT / "samples" / "vuln_scan_sev1_critical_rce.pdf"
    total += 1
    if pdf.is_file():
        proc = subprocess.run(
            [str(VENV), str(EXTRACTOR), str(pdf), "--image-dir", str(ROOT / "samples" / "_extract_images")],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        data = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
        bon1 = data.get("ok") and data.get("char_count", 0) > 0 and len(data.get("images", [])) > 0
        if ok("BON-1 Gemini Vision (extractor PDF+images)", bon1, f"chars={data.get('char_count')} images={len(data.get('images', []))}"):
            passed += 1
    else:
        if ok("BON-1 Gemini Vision (extractor PDF+images)", False, "sample PDF missing"):
            pass

    # BON-2 Digest
    total += 1
    try:
        digest = post_json(
            f"{API}/digest/preview",
            {
                "rows": [
                    {
                        "processed_at": "2026-06-24T10:00:00+00:00",
                        "classification": "intrusion",
                        "sensitivity": "confidential",
                        "routing_tag": "escalate",
                        "computed_severity": "SEV1",
                        "filename": "a.md",
                    }
                ],
                "window_hours": 24,
            },
        )
        bon2 = "Daily digest" in digest.get("html", "") and digest.get("aggregate", {}).get("total") == 1
        if ok("BON-2 Daily Email Digest (API preview + Cloud wf active)", bon2, f"total={digest.get('aggregate', {}).get('total')}"):
            passed += 1
    except Exception as exc:
        ok("BON-2 Daily Email Digest", False, str(exc))

    # BON-3 Dashboard
    total += 1
    dash = ROOT / "dashboard" / "index.html"
    fixture = ROOT / "dashboard" / "fixtures" / "incidents.csv"
    bon3 = dash.is_file() and fixture.is_file() and "Chart.js" in dash.read_text(encoding="utf-8")
    if ok("BON-3 Live Dashboard (HTML + CSV fixture)", bon3):
        passed += 1

    # BON-4 Retry
    total += 1
    if ok("BON-4 Retry Logic (Gemini 5x/3s)", check_gemini_retry(wf)):
        passed += 1

    # BON-5 Semantic Search
    total += 1
    try:
        idx = post_json(
            f"{API}/index",
            {
                "document_id": "verify-bonus5-001",
                "filename": "test.md",
                "classification": "intrusion",
                "department": "SecOps",
                "summary": "Credential stuffing brute force attack",
                "processed_at": "2026-06-24T10:00:00+00:00",
                "text": "Credential stuffing brute force attack on identity service",
            },
        )
        search = post_json(
            f"{API}/search",
            {"query": "brute force credential stuffing", "top_k": 3, "min_similarity": 0.0},
        )
        bon5 = idx.get("status") == "indexed" and len(search.get("hits", [])) >= 1
        if ok("BON-5 Semantic Search (/index + /search)", bon5, f"hits={len(search.get('hits', []))}"):
            passed += 1
    except Exception as exc:
        ok("BON-5 Semantic Search", False, str(exc))

    # BON-6 Compare
    total += 1
    try:
        cmp = post_json(
            f"{API}/compare",
            {
                "flash": {
                    "incident_type": "phishing",
                    "confidence_score": 0.8,
                    "summary": "a",
                    "entities": {"systems": ["mail"]},
                },
                "pro": {
                    "incident_type": "phishing",
                    "confidence_score": 0.9,
                    "summary": "b",
                    "entities": {"systems": ["mail"]},
                },
            },
        )
        bon6 = cmp.get("classification_agreement") is True
        if ok("BON-6 Multi-model Compare (/compare)", bon6, f"delta={cmp.get('confidence_delta')}"):
            passed += 1
    except Exception as exc:
        ok("BON-6 Multi-model Compare", False, str(exc))

    # BON-7 Batch
    total += 1
    zip_path = ROOT / "samples" / "batch_incidents.zip"
    bon7 = zip_path.is_file()
    if bon7 and zip_path.is_file():
        sys.path.insert(0, str(ROOT / "services" / "enrichment-api"))
        from app.batch import unpack_zip_bytes  # noqa: E402

        entries = unpack_zip_bytes(zip_path.read_bytes())
        bon7 = len(entries) >= 2
    else:
        entries = []
    if ok("BON-7 Multi-file Batch (ZIP unpack)", bon7, f"entries={len(entries) if bon7 else 0}"):
        passed += 1

    # BON-8 Alerting
    total += 1
    if ok("BON-8 Sensitivity Alerting (Is SEV1? OR conditions)", check_bon8_if(wf)):
        passed += 1

    print(f"\n=== Summary: {passed}/{total} checks passed ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
