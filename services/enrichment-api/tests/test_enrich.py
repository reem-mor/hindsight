def test_enrich_sev1_vuln_scan(client, sev1_vuln_payload):
    r = client.post("/enrich", json=sev1_vuln_payload)
    assert r.status_code == 200
    body = r.json()

    assert body["reported_severity"] == "SEV3"
    assert body["computed_severity"] == "SEV1"
    assert body["severity_review_needed"] is True

    assert "vulnerability-scanner" in body["affected_services_resolved"]
    assert body["department"] in ("SecOps", "NetSec")

    assert body["sensitivity"] == "confidential"
    assert body["routing_tag"] == "escalate"

    assert "page-oncall" in body["routing_tags"]
    assert "exec-escalation" in body["routing_tags"]

    assert body["action_item_total"] == 2
    assert body["action_items_without_owner"] == 1
    assert body["open_p0_actions"] == 1
    assert "unowned-actions" in body["routing_tags"]

    assert body["cvss_score"] == 9.8
    assert body["cve_ids"] == ["CVE-2026-21841"]


def test_enrich_minor_internal(client):
    payload = {
        "incident_title": "SOAR ticket queue delay",
        "summary": "Internal SOAR queue was slow for a few minutes. No security impact.",
        "severity": "SEV3",
        "incident_type": "other",
        "affected_services": ["internal-tooling"],
        "affected_jurisdictions": [],
        "root_cause": "Ticketing integration rate limit.",
        "action_items": [{"action": "Tune queue polling", "owner": "SecOps", "priority": "P2"}],
        "confidence_score": 0.8,
        "metrics": {"ttr_minutes": 6},
    }
    r = client.post("/enrich", json=payload)
    body = r.json()
    assert body["computed_severity"] in ("SEV3", "SEV4")
    assert body["sensitivity"] == "public"
    assert body["department"] == "SecOps"
    assert "page-oncall" not in body["routing_tags"]


def test_confidence_penalised_for_missing_fields(client):
    payload = {
        "incident_title": "Vague incident",
        "summary": "Something broke briefly.",
        "severity": "SEV3",
        "incident_type": "other",
        "affected_services": [],
        "root_cause": "",
        "action_items": [],
        "confidence_score": 0.95,
        "metrics": {},
    }
    r = client.post("/enrich", json=payload)
    body = r.json()
    assert body["confidence_score"] < 0.95
    assert body["confidence_delta"] < 0
    assert "needs-review" in body["routing_tags"]


def test_blameless_coaching_tag(client):
    payload = {
        "incident_title": "Outage blamed on analyst",
        "summary": "SIEM misconfiguration caused alert storm.",
        "severity": "SEV3",
        "incident_type": "configuration",
        "affected_services": ["siem"],
        "root_cause": "An analyst typo in the correlation rule.",
        "blameless_quality": "poor",
        "confidence_score": 0.8,
        "metrics": {"ttr_minutes": 20},
    }
    r = client.post("/enrich", json=payload)
    assert "blameless-coaching" in r.json()["routing_tags"]


def test_response_schema_has_ids(client):
    r = client.post("/enrich", json={"incident_title": "x", "summary": "y"})
    body = r.json()
    assert body["document_id"]
    assert body["processed_at"]
    assert body["correlation_id"]
    assert body["recurrence_fingerprint"]
