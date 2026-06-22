"""Cyber/SecOps hybrid coverage: CVSS-driven severity floor, CVE -> confidential,
the single-value routing_tag rubric, and SecOps/cyber type routing. All assertions
hit the live FastAPI app via the shared `client` fixture.
"""


def _enrich(client, **over):
    base = {"incident_title": "t", "summary": "s", "severity": "SEV4", "incident_type": "other"}
    base.update(over)
    r = client.post("/enrich", json=base)
    assert r.status_code == 200, r.text
    return r.json()


# ---- CVSS severity floor --------------------------------------------------- #
def test_critical_cvss_floors_to_sev1_and_escalates(client):
    b = _enrich(
        client,
        incident_type="vulnerability-scan",
        severity="SEV3",
        affected_services=["nessus"],
        cvss_score=9.8,
        cve_ids=["CVE-2026-21841"],
        summary="Authenticated scan flagged a remote code execution vulnerability.",
        root_cause="unpatched TLS library",
        metrics={"ttr_minutes": 5},
    )
    assert b["computed_severity"] == "SEV1"
    assert b["routing_tag"] == "escalate"
    assert b["sensitivity"] == "confidential"          # CVSS >= 7 signal
    assert b["cvss_score"] == 9.8
    assert b["cve_ids"] == ["CVE-2026-21841"]
    assert "page-oncall" in b["routing_tags"]


def test_high_cvss_floors_to_at_least_sev2(client):
    b = _enrich(client, incident_type="vulnerability-scan", severity="SEV4",
                affected_services=["nessus"], cvss_score=7.5, summary="high sev finding")
    assert b["computed_severity"] in ("SEV1", "SEV2")
    assert b["sensitivity"] == "confidential"


def test_medium_cvss_floors_to_at_least_sev3(client):
    b = _enrich(client, incident_type="vulnerability-scan", severity="SEV4",
                affected_services=["nessus"], cvss_score=4.5, summary="medium finding")
    assert b["computed_severity"] in ("SEV1", "SEV2", "SEV3")


def test_low_cvss_does_not_floor(client):
    # CVSS 2.0 is below the SEV3 band -> no floor, and not confidential by CVSS.
    b = _enrich(client, incident_type="vulnerability-scan", severity="SEV4",
                affected_services=["nessus"], cvss_score=2.0,
                summary="informational finding", root_cause="x",
                action_items=[{"action": "note", "owner": "SecOps", "priority": "P2"}],
                metrics={"ttr_minutes": 0})
    assert b["computed_severity"] in ("SEV3", "SEV4")
    # CVSS 2.0 alone should not raise confidentiality.
    assert "high-severity CVE (CVSS >= 7.0)" not in b["sensitivity_rationale"]


def test_cvss_is_clamped(client):
    b = _enrich(client, incident_type="vulnerability-scan", affected_services=["nessus"],
                cvss_score=15.0)
    assert b["cvss_score"] == 10.0


# ---- routing_tag rubric (escalate / needs-review / auto-approved) ----------- #
def test_routing_tag_needs_review_on_low_confidence(client):
    b = _enrich(client, incident_type="other", severity="SEV3",
                confidence_score=0.3, root_cause="", action_items=[],
                affected_services=[], metrics={})
    assert b["computed_severity"] != "SEV1"
    assert b["routing_tag"] == "needs-review"


def test_routing_tag_auto_approved_on_clean_minor(client):
    b = _enrich(
        client,
        incident_type="degradation",
        severity="SEV4",
        affected_services=["notifications"],
        affected_jurisdictions=[],
        summary="Minor internal email delay, no customer impact.",
        root_cause="queue backlog cleared itself",
        action_items=[{"action": "tune retry", "owner": "Dana", "priority": "P2"}],
        confidence_score=0.9,
        metrics={"ttr_minutes": 0},
    )
    assert b["computed_severity"] == "SEV4"
    assert b["severity_review_needed"] is False
    assert b["routing_tag"] == "auto-approved"


# ---- cyber type routing ---------------------------------------------------- #
def test_vuln_scan_unknown_service_routes_to_secops(client):
    b = _enrich(client, incident_type="vulnerability-scan",
                affected_services=["totally-made-up-scanner"], summary="finding")
    assert b["department"] == "SecOps"


def test_intrusion_routes_to_security_ir(client):
    b = _enrich(client, incident_type="intrusion",
                affected_services=["nope-xyz"], summary="active intrusion detected")
    assert b["department"] == "Security-IR"


def test_ddos_routes_to_platform_sre(client):
    b = _enrich(client, incident_type="ddos",
                affected_services=["nope-xyz"], summary="volumetric flood")
    assert b["department"] == "Platform-SRE"


def test_siem_alias_resolves_to_secops_service(client):
    b = _enrich(client, incident_type="security", affected_services=["splunk"],
                summary="correlation search fired")
    assert "siem" in b["affected_services_resolved"]
    assert b["department"] == "SecOps"


def test_phishing_is_confidential(client):
    b = _enrich(client, incident_type="phishing", affected_services=["kyc"],
                summary="staff credential harvesting via look-alike domain")
    assert b["sensitivity"] == "confidential"


# ---- sensitivity endpoint with CVSS ---------------------------------------- #
def test_sensitivity_endpoint_high_cvss_is_confidential(client):
    r = client.post("/sensitivity", json={
        "incident_type": "vulnerability-scan",
        "summary": "scanner finding",
        "affected_jurisdictions": [],
        "cvss_score": 8.1,
        "cve_ids": ["CVE-2026-0001"],
    })
    assert r.json()["sensitivity"] == "confidential"


# ---- score-severity endpoint also applies the CVSS floor ------------------- #
def test_score_severity_endpoint_applies_cvss_floor(client):
    r = client.post("/score-severity", json={
        "reported_severity": "SEV4",
        "incident_type": "vulnerability-scan",
        "affected_services": ["nessus"],
        "cvss_score": 9.5,
        "summary": "remote code execution",
    })
    b = r.json()
    assert b["computed_severity"] == "SEV1"
    assert b["review_needed"] is True


def test_score_severity_endpoint_clamps_cvss(client):
    # cvss 15 -> clamped to 10 -> still SEV1 band, no crash.
    r = client.post("/score-severity", json={
        "reported_severity": "SEV4", "incident_type": "vulnerability-scan",
        "affected_services": ["nessus"], "cvss_score": 15.0, "summary": "x",
    })
    assert r.status_code == 200
    assert r.json()["computed_severity"] == "SEV1"


# ---- categories advertise the cyber vocabulary ----------------------------- #
def test_categories_include_cyber_types_and_secops(client):
    b = client.get("/categories").json()
    for t in ("vulnerability-scan", "malware", "phishing", "intrusion", "ddos"):
        assert t in b["incident_types"]
    assert "SecOps" in b["teams"]
