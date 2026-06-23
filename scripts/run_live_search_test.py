"""Live BON-5 test: index openssl incident in Supabase and POST /search."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from n8n_cloud_api import load_dotenv  # noqa: E402


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    load_dotenv(ROOT / ".env")
    base = os.environ.get("ENRICHMENT_API_URL", "http://127.0.0.1:8000").rstrip("/")
    health = urllib.request.urlopen(f"{base}/health", timeout=10)
    if health.status != 200:
        print("API not healthy")
        return 1

    index_payload = {
        "document_id": "live-openssl-001",
        "filename": "vuln_scan_critical_openssl.md",
        "classification": "vulnerability-scan",
        "department": "SecOps",
        "sensitivity": "confidential",
        "routing_tag": "escalate",
        "summary": "Critical OpenSSL RCE CVSS 9.8 CVE-2026-21841",
        "processed_at": "2026-06-23T10:00:00+00:00",
        "text": "Critical OpenSSL RCE CVSS 9.8 CVE-2026-21841 remote code execution",
    }
    idx = post_json(f"{base}/index", index_payload)
    print("index:", idx)

    search = post_json(
        f"{base}/search",
        {
            "query": index_payload["text"],
            "top_k": 5,
            "min_similarity": 0.0,
        },
    )
    print("search hits:", len(search.get("hits", [])))
    for h in search.get("hits", [])[:3]:
        print(f"  {h['document_id']} sim={h['similarity']} summary={h['summary'][:60]}")

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if url and key:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/hindsight_incidents?select=document_id,filename&limit=5",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        try:
            rows = json.loads(urllib.request.urlopen(req, timeout=30).read())
            print("supabase rows:", rows)
        except urllib.error.HTTPError as exc:
            print("supabase read failed:", exc.read().decode()[:200])

    return 0 if search.get("hits") else 1


if __name__ == "__main__":
    raise SystemExit(main())
