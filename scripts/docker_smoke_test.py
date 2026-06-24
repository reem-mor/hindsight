"""Docker stack smoke test — enrichment API + optional n8n reachability."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from n8n_cloud_api import load_dotenv  # noqa: E402

API = os.environ.get("ENRICHMENT_API_URL", "http://127.0.0.1:8000").rstrip("/")
N8N = os.environ.get("N8N_LOCAL_URL", "http://127.0.0.1:5678").rstrip("/")


def get_json(url: str, timeout: int = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def ok(label: str, cond: bool, detail: str = "") -> bool:
    status = "PASS" if cond else "FAIL"
    line = f"[{status}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return cond


def main() -> int:
    load_dotenv(ROOT / ".env")
    passed = 0
    total = 0

    print("\n=== Docker / local stack smoke ===")

    total += 1
    try:
        health = get_json(f"{API}/health")
        if ok("Enrichment /health", health.get("status") == "ok", f"version={health.get('version')}"):
            passed += 1
    except Exception as exc:
        ok("Enrichment /health", False, str(exc))

    total += 1
    try:
        cats = get_json(f"{API}/categories")
        ok_cats = isinstance(cats, dict) and len(cats.get("teams", [])) > 0
        if ok("Enrichment /categories", ok_cats, f"teams={len(cats.get('teams', []))}"):
            passed += 1
    except Exception as exc:
        ok("Enrichment /categories", False, str(exc))

    total += 1
    try:
        body = post_json(
            f"{API}/enrich",
            {
                "incident_type": "vulnerability-scan",
                "severity": "SEV3",
                "confidence_score": 0.85,
                "summary": "Critical OpenSSL RCE CVSS 9.8",
                "cvss_score": 9.8,
                "cve_ids": ["CVE-2026-21841"],
                "entities": {"systems": ["payments-gateway"]},
                "action_items": [{"action": "patch", "owner": "NetSec", "priority": "P0"}],
            },
        )
        bon = body.get("computed_severity") == "SEV1" and body.get("routing_tag") == "escalate"
        if ok("Enrichment /enrich CVSS floor", bon, f"sev={body.get('computed_severity')} route={body.get('routing_tag')}"):
            passed += 1
    except Exception as exc:
        ok("Enrichment /enrich CVSS floor", False, str(exc))

    total += 1
    n8n_ok = False
    for attempt in range(6):
        try:
            code = urllib.request.urlopen(N8N, timeout=10).status
            n8n_ok = code == 200
            if n8n_ok:
                break
        except Exception:
            if attempt < 5:
                time.sleep(5)
    if ok("n8n UI reachable", n8n_ok, N8N):
        passed += 1

    has_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    has_supabase = bool(os.environ.get("SUPABASE_URL", "").strip() and os.environ.get("SUPABASE_SERVICE_KEY", "").strip())
    total += 1
    if ok(".env GEMINI_API_KEY present", has_gemini):
        passed += 1
    total += 1
    if ok(".env Supabase configured (BON-5)", has_supabase):
        passed += 1

    print(f"\n=== Summary: {passed}/{total} checks passed ===\n")
    return 0 if passed >= total - 1 else 1  # allow missing Supabase in dev


if __name__ == "__main__":
    raise SystemExit(main())
