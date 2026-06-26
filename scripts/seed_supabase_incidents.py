r"""Seed the BON-5 Supabase pgvector store with the canonical sample incidents.

Each sample is run through the REAL deterministic enrichment brain (`enrich`) so the
stored department / sensitivity / routing_tag / severity are service-computed, not
hand-typed — then indexed with a real `gemini-embedding-001` vector over the full
document text. Stable document_ids make re-runs idempotent (upsert on conflict).

Usage (from repo root, with SUPABASE_URL + SUPABASE_SERVICE_KEY + GEMINI_API_KEY in .env):
    .\.venv\Scripts\python.exe scripts\seed_supabase_incidents.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "enrichment-api"))
sys.path.insert(0, str(ROOT / "extractors"))

from n8n_cloud_api import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.enrichment import enrich  # noqa: E402
from app.main import CATALOG, settings  # noqa: E402
from app.models import Entities, GeminiResult, Severity  # noqa: E402
from app.search_store import get_vector_store  # noqa: E402

from extract_document import extract  # noqa: E402


def _doc_text(rel: str) -> str:
    path = ROOT / "samples" / rel
    if path.suffix.lower() == ".pdf":
        res = extract(str(path), str(ROOT / "samples" / "_extract_images"))
        return str(res.get("text") or res.get("extracted_text") or "")
    return path.read_text(encoding="utf-8")


# (document_id, source file, GeminiResult kwargs). Reported severity is intentionally
# under-stated on the criticals so the deterministic flooring to SEV1 is observable.
SAMPLES = [
    (
        "sample-openssl-rce",
        "vuln_scan_critical_openssl.md",
        dict(
            incident_title="Critical RCE in payments estate (CVE-2026-21841)",
            summary="Authenticated Nessus scan found a critical unauthenticated RCE (CVE-2026-21841) "
            "in the TLS termination library on 23 internet-facing payments/wallet hosts in the PCI segment.",
            incident_type="vulnerability-scan",
            severity=Severity.SEV2,
            affected_services=["payments-gateway", "wallet"],
            affected_jurisdictions=["UKGC", "NJ-DGE", "MGM"],
            root_cause="Vulnerable TLS termination library exposed to the internet on PCI-scoped hosts.",
            cvss_score=9.8,
            cve_ids=["CVE-2026-21841"],
            entities=Entities(systems=["payments-gateway", "wallet", "TLS termination library"]),
            sentiment="negative",
            confidence_score=0.94,
        ),
    ),
    (
        "sample-bruteforce-intrusion",
        "siem_bruteforce_intrusion.md",
        dict(
            incident_title="Credential brute force against identity service",
            summary="Splunk ES correlation fired on a distributed brute force: ~140k failed logins from "
            "1,900 IPs in one ASN preceded three successful logins (limited account takeover); sessions killed.",
            incident_type="intrusion",
            severity=Severity.SEV2,
            affected_services=["identity"],
            affected_jurisdictions=["GLOBAL"],
            root_cause="Distributed credential stuffing against the identity service from a single hosting ASN.",
            entities=Entities(systems=["identity service", "Splunk ES"]),
            sentiment="negative",
            confidence_score=0.88,
        ),
    ),
    (
        "sample-phishing-kyc",
        "phishing_kyc_credential_harvest.md",
        dict(
            incident_title="Spoofed KYC portal harvesting staff credentials",
            summary="Phishing campaign impersonated the internal KYC review portal; two compliance analysts "
            "entered credentials on a look-alike domain before it was blocked. Accounts disabled and reset.",
            incident_type="phishing",
            severity=Severity.SEV3,
            affected_services=["kyc"],
            affected_jurisdictions=["UKGC", "NJ-DGE"],
            root_cause="Look-alike domain hosting a credential-harvesting clone of the KYC onboarding tool.",
            entities=Entities(systems=["KYC review portal"]),
            sentiment="negative",
            confidence_score=0.9,
        ),
    ),
    (
        "sample-sev1-rce-pdf",
        "vuln_scan_sev1_critical_rce.pdf",
        dict(
            incident_title="SEV1 critical RCE — vulnerability scan (PDF)",
            summary="Vulnerability scan report (PDF, with severity chart) flagging a critical remote code "
            "execution exposure on internet-facing infrastructure.",
            incident_type="vulnerability-scan",
            severity=Severity.SEV2,
            affected_services=["payments-gateway"],
            affected_jurisdictions=["UKGC"],
            root_cause="Critical RCE-class vulnerability on internet-facing hosts.",
            cvss_score=9.6,
            cve_ids=["CVE-2026-31007"],
            entities=Entities(systems=["edge gateway"]),
            sentiment="negative",
            confidence_score=0.91,
        ),
    ),
    (
        "sample-edge-cdn-sev2",
        "edge_cdn_sev2_eu_errors.pdf",
        dict(
            incident_title="Edge CDN elevated 5xx errors in EU",
            summary="Edge/CDN availability incident: elevated 5xx error rates affecting EU edge nodes, "
            "degrading customer-facing traffic. No data exposure indicated.",
            incident_type="availability",
            severity=Severity.SEV2,
            affected_services=["edge-cdn"],
            affected_jurisdictions=["EU"],
            root_cause="Edge/CDN node errors driving elevated 5xx rates for EU traffic.",
            entities=Entities(systems=["edge-cdn"]),
            sentiment="negative",
            confidence_score=0.85,
        ),
    ),
]


def main() -> int:
    store = get_vector_store()
    print(f"Vector store: {type(store).__name__}")
    for doc_id, rel, kwargs in SAMPLES:
        text = _doc_text(rel)
        payload = GeminiResult(filename=rel, **kwargs)
        result = enrich(payload, settings, CATALOG)
        store.upsert(
            document_id=doc_id,
            filename=rel,
            classification=payload.incident_type,
            department=result.department,
            sensitivity=result.sensitivity.value,
            routing_tag=result.routing_tag,
            summary=result.summary[:500],
            processed_at=result.processed_at,
            text=text,
            metadata={"cvss_score": payload.cvss_score, "cve_ids": payload.cve_ids},
        )
        print(
            f"  indexed {doc_id:28s} type={payload.incident_type:16s} "
            f"sev={result.computed_severity.value} tag={result.routing_tag:13s} "
            f"sens={result.sensitivity.value} dept={result.department} (chars={len(text)})"
        )
    print("Seed complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
