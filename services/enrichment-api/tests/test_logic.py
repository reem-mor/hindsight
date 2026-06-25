import pytest

from app.config import get_settings
from app.routing import ServiceCatalog


def _catalog():
    return ServiceCatalog(get_settings().service_catalog_path)


# ---- catalog load hardening ------------------------------------------------ #
def test_catalog_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(RuntimeError) as exc:
        ServiceCatalog(tmp_path / "does_not_exist.yaml")
    assert "catalog" in str(exc.value).lower()


def test_catalog_entry_without_name_raises_clear_error(tmp_path):
    bad = tmp_path / "bad_catalog.yaml"
    bad.write_text("services:\n  - team: SecOps\n    tier: high\n", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        ServiceCatalog(bad)
    assert "catalog" in str(exc.value).lower()


# ---- routing --------------------------------------------------------------- #
def test_alias_resolution():
    cat = _catalog()
    assert cat.resolve("nessus").name == "vulnerability-scanner"
    assert cat.resolve("splunk").name == "siem"
    assert cat.resolve("waf").name == "network"
    assert cat.resolve("auth").name == "auth"


def test_unknown_service_returns_none():
    assert _catalog().resolve("totally-made-up-service") is None


def test_resolve_many_dedups():
    cat = _catalog()
    entries = cat.resolve_many(["nessus", "qualys", "vuln scanner"])
    assert len([e for e in entries if e.name == "vulnerability-scanner"]) == 1


def test_type_routing_fallback():
    cat = _catalog()
    assert cat.team_for_type("security") == "Security-IR"
    assert cat.team_for_type("data-incident") == "Security-IR"
    assert cat.team_for_type("ddos") == "NetSec"


# ---- severity rubric ------------------------------------------------------- #
def test_severity_endpoint_upgrades(client):
    payload = {
        "reported_severity": "SEV3",
        "incident_type": "intrusion",
        "affected_services": ["siem"],
        "affected_jurisdictions": ["GLOBAL"],
        "metrics": {"ttr_minutes": 140},
        "summary": "Active intrusion with data exfiltration indicators; PII possibly exposed.",
        "cvss_score": 9.1,
    }
    r = client.post("/score-severity", json=payload)
    body = r.json()
    assert body["computed_severity"] == "SEV1"
    assert body["review_needed"] is True
    assert body["severity_score"] >= 9


def test_severity_endpoint_minor_stays_low(client):
    payload = {
        "reported_severity": "SEV4",
        "incident_type": "other",
        "affected_services": ["email-gateway"],
        "affected_jurisdictions": [],
        "metrics": {"ttr_minutes": 4},
        "summary": "Minor delay in phishing filter quarantine queue.",
    }
    r = client.post("/score-severity", json=payload)
    body = r.json()
    assert body["computed_severity"] in ("SEV3", "SEV4")


# ---- sensitivity ----------------------------------------------------------- #
def test_sensitivity_confidential_on_cve_ids(client):
    r = client.post(
        "/sensitivity",
        json={
            "incident_type": "vulnerability-scan",
            "summary": "Informational scan note.",
            "affected_jurisdictions": ["GLOBAL"],
            "cve_ids": ["CVE-2026-11002"],
        },
    )
    assert r.json()["sensitivity"] == "confidential"


def test_sensitivity_confidential_on_security(client):
    r = client.post(
        "/sensitivity",
        json={"incident_type": "security", "summary": "intrusion detected", "affected_jurisdictions": []},
    )
    assert r.json()["sensitivity"] == "confidential"


def test_sensitivity_internal_default(client):
    r = client.post(
        "/sensitivity",
        json={
            "incident_type": "capacity",
            "summary": "CPU saturation on batch workers during nightly job.",
            "affected_jurisdictions": ["UK"],
        },
    )
    assert r.json()["sensitivity"] == "internal"


def test_sensitivity_public_on_benign_incident(client):
    r = client.post(
        "/sensitivity",
        json={
            "incident_type": "other",
            "summary": "Routine synthetic probe latency blip on staging.",
            "affected_jurisdictions": [],
        },
    )
    body = r.json()
    assert body["sensitivity"] == "public"
    assert "non-sensitive" in " ".join(body["rationale"]).lower()


def test_sensitivity_public_global_only_jurisdiction(client):
    r = client.post(
        "/sensitivity",
        json={
            "incident_type": "configuration",
            "summary": "Non-production config drift corrected during maintenance.",
            "affected_jurisdictions": ["GLOBAL"],
        },
    )
    assert r.json()["sensitivity"] == "public"


def test_sensitivity_not_confidential_on_edge_and_budget_words(client):
    """Regression: 'edge'/'budget' must not trip the regulatory regex (substring 'dge')."""
    r = client.post(
        "/sensitivity",
        json={
            "incident_type": "degradation",
            "summary": "Edge CDN cache nodes degraded on staging; cache-refresh budget exhausted.",
            "affected_jurisdictions": [],
        },
    )
    assert r.json()["sensitivity"] == "public"


def test_sensitivity_not_confidential_on_discharged(client):
    """Regression: 'discharged' must not trip the monetary regex (substring 'charge')."""
    r = client.post(
        "/sensitivity",
        json={
            "incident_type": "degradation",
            "summary": "UPS battery discharged during a scheduled maintenance window; failover engaged.",
            "affected_jurisdictions": [],
        },
    )
    assert r.json()["sensitivity"] == "public"


def test_sensitivity_still_confidential_on_real_regulator(client):
    """Guard: the fix must still catch genuine regulatory language."""
    r = client.post(
        "/sensitivity",
        json={
            "incident_type": "degradation",
            "summary": "Regulator notified; potential fines pending after the customer data exposure.",
            "affected_jurisdictions": [],
        },
    )
    assert r.json()["sensitivity"] == "confidential"


# ---- recurrence ------------------------------------------------------------ #
def test_recurrence_fingerprint_stable_and_counts(client, sev1_vuln_payload):
    r1 = client.post("/enrich", json=sev1_vuln_payload)
    r2 = client.post("/enrich", json=sev1_vuln_payload)
    fp1 = r1.json()["recurrence_fingerprint"]
    fp2 = r2.json()["recurrence_fingerprint"]
    assert fp1 == fp2
    assert r1.json()["recurrence_seen_count"] == 1
    assert r2.json()["recurrence_seen_count"] == 2
    assert "repeat-offender" in r2.json()["routing_tags"]
    assert "repeat-offender" not in r1.json()["routing_tags"]


def test_different_incident_different_fingerprint(client, sev1_vuln_payload):
    r1 = client.post("/enrich", json=sev1_vuln_payload)
    other = dict(sev1_vuln_payload)
    other["affected_services"] = ["siem"]
    other["root_cause"] = "Brute-force login attempts from botnet IPs."
    other["incident_type"] = "intrusion"
    r2 = client.post("/enrich", json=other)
    assert r1.json()["recurrence_fingerprint"] != r2.json()["recurrence_fingerprint"]
