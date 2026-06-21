def test_enrich_sev1_payment(client, sev1_payment_payload):
    r = client.post("/enrich", json=sev1_payment_payload)
    assert r.status_code == 200
    body = r.json()

    # Rubric should upgrade SEV2 → SEV1 and flag the disagreement.
    assert body["reported_severity"] == "SEV2"
    assert body["computed_severity"] == "SEV1"
    assert body["severity_review_needed"] is True

    # Routing resolves both services to the Payments team.
    assert "payments-gateway" in body["affected_services_resolved"]
    assert body["department"] == "Payments-SRE"

    # Monetary + multi-jurisdiction → confidential.
    assert body["sensitivity"] == "confidential"

    # SEV1 + multi-jurisdiction tags drive paging and regulatory review.
    assert "page-oncall" in body["routing_tags"]
    assert "exec-escalation" in body["routing_tags"]
    assert "regulatory-review" in body["routing_tags"]

    # Action-item quality: one of two has no owner.
    assert body["action_item_total"] == 2
    assert body["action_items_without_owner"] == 1
    assert body["open_p0_actions"] == 1
    assert "unowned-actions" in body["routing_tags"]

    # 95 min downtime on a 99.95% service blows the monthly budget.
    assert body["slo_impact"]["budget_breach"] is True
    assert body["slo_impact"]["primary_service"] == "payments-gateway"


def test_enrich_minor_internal(client):
    payload = {
        "incident_title": "Grafana dashboard slow to load",
        "summary": "Internal Grafana was slow for a few minutes. No customer impact.",
        "severity": "SEV3",
        "incident_type": "degradation",
        "affected_services": ["grafana"],
        "affected_jurisdictions": [],
        "root_cause": "Browser cache misconfiguration on the internal dashboard.",
        "action_items": [{"action": "Tune cache headers", "owner": "DevEx", "priority": "P2"}],
        "confidence_score": 0.8,
        "metrics": {"ttr_minutes": 6},
    }
    r = client.post("/enrich", json=payload)
    body = r.json()
    assert body["computed_severity"] in ("SEV3", "SEV4")
    assert body["sensitivity"] == "internal"
    assert body["department"] == "DevEx"
    assert "page-oncall" not in body["routing_tags"]


def test_confidence_penalised_for_missing_fields(client):
    payload = {
        "incident_title": "Vague incident",
        "summary": "Something broke briefly.",
        "severity": "SEV3",
        "incident_type": "other",
        "affected_services": [],
        "root_cause": "",          # missing → penalty
        "action_items": [],         # missing → penalty
        "confidence_score": 0.95,
        "metrics": {},              # missing → penalty
    }
    r = client.post("/enrich", json=payload)
    body = r.json()
    assert body["confidence_score"] < 0.95
    assert body["confidence_delta"] < 0
    assert "needs-review" in body["routing_tags"]


def test_blameless_coaching_tag(client):
    payload = {
        "incident_title": "Outage caused by junior engineer",
        "summary": "Site down 20 min.",
        "severity": "SEV3",
        "incident_type": "configuration",
        "affected_services": ["casino"],
        "root_cause": "A config typo.",
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
