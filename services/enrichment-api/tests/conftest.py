import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.enrichment import reset_recurrence_memory


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_recurrence():
    """Each test starts with a clean ephemeral recurrence counter."""
    reset_recurrence_memory()
    yield
    reset_recurrence_memory()


@pytest.fixture()
def sev1_vuln_payload():
    """Critical vuln scan finding — CVSS 9.8 floors to SEV1."""
    return {
        "incident_title": "Critical OpenSSL RCE on perimeter hosts",
        "summary": (
            "Nessus scan flagged CVE-2026-21841 with CVSS 9.8 on 23 hosts. "
            "Remote code execution possible without authentication on edge TLS endpoints."
        ),
        "severity": "SEV3",
        "incident_type": "vulnerability-scan",
        "status": "monitoring",
        "affected_services": ["nessus", "network"],
        "affected_jurisdictions": ["GLOBAL"],
        "root_cause": "Unpatched OpenSSL library in the perimeter gateway image.",
        "trigger": "Scheduled vulnerability scan",
        "detection_method": "alert",
        "entities": {
            "people": ["SecOps on-call"],
            "teams": ["SecOps"],
            "systems": ["vulnerability-scanner", "network"],
            "dates": ["2026-06-20"],
            "error_codes": [],
        },
        "action_items": [
            {"action": "Emergency patch perimeter gateways", "owner": "NetSec", "priority": "P0"},
            {"action": "Validate scanner coverage", "owner": None, "priority": "P1"},
        ],
        "contributing_factors": ["Delayed image rebuild pipeline"],
        "sentiment": "negative",
        "blameless_quality": "good",
        "cvss_score": 9.8,
        "cve_ids": ["CVE-2026-21841"],
        "confidence_score": 0.92,
        "filename": "vuln_scan_critical_openssl.md",
        "metrics": {
            "detected_at": "2026-06-20T08:00:00Z",
            "resolved_at": None,
            "ttd_minutes": 0,
            "ttr_minutes": 0,
            "customer_impact": "Potential remote compromise of edge TLS",
        },
    }
