"""
Adversarial edge-case & guardrail coverage for the HINDSIGHT enrichment brain.
Complements test_logic / test_enrich / test_ops with boundary conditions,
malformed input, and routing fallbacks. All assertions hit the live FastAPI app.
"""


def _enrich(client, **over):
    base = {"incident_title": "t", "summary": "s", "severity": "SEV3", "incident_type": "other"}
    base.update(over)
    r = client.post("/enrich", json=base)
    assert r.status_code == 200, r.text
    return r.json()


# ---- defaults / empty input ------------------------------------------------ #
def test_empty_payload_is_safe(client):
    r = client.post("/enrich", json={})
    assert r.status_code == 200
    b = r.json()
    assert b["department"] == "SRE-Platform"          # type-routing fallback for 'other'
    assert b["sensitivity"] == "internal"
    assert b["computed_severity"] in ("SEV1", "SEV2", "SEV3", "SEV4")
    assert len(b["recurrence_fingerprint"]) == 12


# ---- jurisdiction handling -------------------------------------------------- #
def test_global_only_jurisdiction_earns_no_regulatory_tag(client):
    b = _enrich(client, affected_services=["identity"], affected_jurisdictions=[])
    assert b["affected_jurisdictions"] == ["GLOBAL"]
    assert "regulatory-review" not in b["routing_tags"]


def test_global_is_dropped_when_a_real_jurisdiction_is_present(client):
    b = _enrich(client, affected_services=["identity"], affected_jurisdictions=["UKGC"])
    assert b["affected_jurisdictions"] == ["UKGC"]
    assert "GLOBAL" not in b["affected_jurisdictions"]


# ---- severity disagreement (both directions) ------------------------------- #
def test_severity_downgrade_also_flags_review(client):
    b = _enrich(client, affected_services=["notifications"], severity="SEV1",
                incident_type="degradation", summary="tiny blip, no impact")
    assert b["computed_severity"] in ("SEV3", "SEV4")
    assert b["severity_review_needed"] is True


# ---- routing fallback + security floor ------------------------------------- #
def test_unknown_service_security_routes_to_security_ir_and_is_confidential(client):
    b = _enrich(client, incident_type="security",
                affected_services=["totally-made-up-xyz"], severity="SEV4",
                summary="suspicious login pattern")
    assert b["department"] == "Security-IR"
    assert b["sensitivity"] == "confidential"
    assert "severity-review" in b["routing_tags"]


def test_data_incident_is_confidential(client):
    b = _enrich(client, incident_type="data-incident",
                affected_services=["reporting-db"], summary="export job exposed a table")
    assert b["sensitivity"] == "confidential"


# ---- SLO error-budget boundary (>= 50% of budget) -------------------------- #
def test_budget_breach_boundary(client):
    # reporting-db SLO 99.0% -> 432 min monthly budget; 50% threshold = 216 min.
    at = _enrich(client, affected_services=["reporting-db"], incident_type="degradation",
                 metrics={"ttr_minutes": 216})
    below = _enrich(client, affected_services=["reporting-db"], incident_type="degradation",
                    metrics={"ttr_minutes": 215})
    assert at["slo_impact"]["monthly_budget_minutes"] == 432
    assert at["slo_impact"]["budget_breach"] is True
    assert below["slo_impact"]["budget_breach"] is False


def test_no_catalogued_service_has_null_slo_but_still_fingerprints(client):
    b = _enrich(client, affected_services=["nope-unknown"], incident_type="other",
                root_cause="x")
    assert b["slo_impact"]["slo_target"] is None
    assert b["slo_impact"]["budget_breach"] is False
    assert len(b["recurrence_fingerprint"]) == 12


# ---- recurrence fingerprint properties ------------------------------------- #
def test_fingerprint_is_word_order_independent(client):
    a = _enrich(client, incident_type="outage", affected_services=["payments-gateway"],
                root_cause="connection pool exhaustion timeout cascade")
    b = _enrich(client, incident_type="outage", affected_services=["payments-gateway"],
                root_cause="cascade timeout exhaustion connection pool")
    c = _enrich(client, incident_type="outage", affected_services=["payments-gateway"],
                root_cause="disk full on the primary database node")
    assert a["recurrence_fingerprint"] == b["recurrence_fingerprint"]
    assert a["recurrence_fingerprint"] != c["recurrence_fingerprint"]


# ---- confidence flooring + action accounting ------------------------------- #
def test_confidence_floors_at_zero_with_notes(client):
    b = _enrich(client, confidence_score=0.3, root_cause="", action_items=[],
                affected_services=[], metrics={}, incident_type="other")
    assert b["confidence_score"] == 0.0
    assert len(b["confidence_notes"]) >= 4
    assert "needs-review" in b["routing_tags"]


def test_action_owner_whitespace_is_unowned_and_priority_is_case_insensitive(client):
    b = _enrich(client, affected_services=["casino"], incident_type="configuration",
                metrics={"ttr_minutes": 10}, action_items=[
                    {"action": "a", "owner": "   ", "priority": "p0"},
                    {"action": "b", "owner": "Dana", "priority": "P0"},
                    {"action": "c", "owner": None, "priority": "p1"},
                ])
    assert b["action_item_total"] == 3
    assert b["action_items_without_owner"] == 2
    assert b["open_p0_actions"] == 2


# ---- robustness ------------------------------------------------------------- #
def test_long_unicode_summary_does_not_crash(client):
    b = _enrich(client, affected_services=["casino"], incident_type="outage",
                summary=("🔥 " * 4000) + "múlti-byte ünïcödé", root_cause="x")
    assert b["computed_severity"] in ("SEV1", "SEV2", "SEV3", "SEV4")
