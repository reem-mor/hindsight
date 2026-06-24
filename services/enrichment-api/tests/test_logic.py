from app.config import get_settings
from app.routing import ServiceCatalog


def _catalog():
    return ServiceCatalog(get_settings().service_catalog_path)


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
