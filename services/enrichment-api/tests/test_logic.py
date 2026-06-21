from app.config import get_settings
from app.routing import ServiceCatalog


def _catalog():
    return ServiceCatalog(get_settings().service_catalog_path)


# ---- routing --------------------------------------------------------------- #
def test_alias_resolution():
    cat = _catalog()
    assert cat.resolve("payment gateway").name == "payments-gateway"
    assert cat.resolve("wallet-svc").name == "wallet"
    assert cat.resolve("the casino platform").name == "casino-platform"
    assert cat.resolve("auth").name == "identity"


def test_unknown_service_returns_none():
    assert _catalog().resolve("totally-made-up-service") is None


def test_resolve_many_dedups():
    cat = _catalog()
    entries = cat.resolve_many(["payments", "payment gateway", "psp"])
    # all three aliases map to the same single service
    assert len([e for e in entries if e.name == "payments-gateway"]) == 1


def test_type_routing_fallback():
    cat = _catalog()
    assert cat.team_for_type("security") == "Security-IR"
    assert cat.team_for_type("data-incident") == "Compliance-Eng"


# ---- severity rubric ------------------------------------------------------- #
def test_severity_endpoint_upgrades(client):
    payload = {
        "reported_severity": "SEV3",
        "incident_type": "security",
        "affected_services": ["identity"],
        "affected_jurisdictions": ["UKGC", "NJ-DGE"],
        "metrics": {"ttr_minutes": 140},
        "summary": "Potential data breach affecting login; PII possibly exposed.",
    }
    r = client.post("/score-severity", json=payload)
    body = r.json()
    assert body["computed_severity"] == "SEV1"
    assert body["review_needed"] is True
    assert body["severity_score"] >= 9


def test_severity_endpoint_minor_stays_low(client):
    payload = {
        "reported_severity": "SEV4",
        "incident_type": "degradation",
        "affected_services": ["notifications"],
        "affected_jurisdictions": [],
        "metrics": {"ttr_minutes": 4},
        "summary": "Minor delay in non-critical email delivery.",
    }
    r = client.post("/score-severity", json=payload)
    body = r.json()
    assert body["computed_severity"] in ("SEV3", "SEV4")


# ---- sensitivity ----------------------------------------------------------- #
def test_sensitivity_confidential_on_security(client):
    r = client.post(
        "/sensitivity",
        json={"incident_type": "security", "summary": "intrusion detected", "affected_jurisdictions": []},
    )
    assert r.json()["sensitivity"] == "confidential"


def test_sensitivity_internal_default(client):
    r = client.post(
        "/sensitivity",
        json={"incident_type": "degradation", "summary": "slow internal tool", "affected_jurisdictions": []},
    )
    assert r.json()["sensitivity"] == "internal"


# ---- recurrence ------------------------------------------------------------ #
def test_recurrence_fingerprint_stable_and_counts(client, sev1_payment_payload):
    r1 = client.post("/enrich", json=sev1_payment_payload)
    r2 = client.post("/enrich", json=sev1_payment_payload)
    fp1 = r1.json()["recurrence_fingerprint"]
    fp2 = r2.json()["recurrence_fingerprint"]
    assert fp1 == fp2  # same incident → same fingerprint
    assert r1.json()["recurrence_seen_count"] == 1
    assert r2.json()["recurrence_seen_count"] == 2
    assert "repeat-offender" in r2.json()["routing_tags"]
    assert "repeat-offender" not in r1.json()["routing_tags"]


def test_different_incident_different_fingerprint(client, sev1_payment_payload):
    r1 = client.post("/enrich", json=sev1_payment_payload)
    other = dict(sev1_payment_payload)
    other["affected_services"] = ["sportsbook"]
    other["root_cause"] = "Odds feed provider timeout during peak load."
    other["incident_type"] = "dependency-failure"
    r2 = client.post("/enrich", json=other)
    assert r1.json()["recurrence_fingerprint"] != r2.json()["recurrence_fingerprint"]
