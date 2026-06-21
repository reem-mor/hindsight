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
def sev1_payment_payload():
    """A clear SEV1: payments down, two jurisdictions, monetary impact."""
    return {
        "incident_title": "Payments gateway full outage — UK & NJ",
        "summary": (
            "Complete outage of the payment gateway prevented all deposits and "
            "withdrawals for 95 minutes. Revenue impact and customer funds were "
            "affected across UKGC and NJ-DGE jurisdictions."
        ),
        "severity": "SEV2",
        "incident_type": "outage",
        "status": "resolved",
        "affected_services": ["payment gateway", "wallet-svc"],
        "affected_jurisdictions": ["UKGC", "NJ-DGE"],
        "root_cause": "Connection pool exhaustion in the payments PSP adapter after a config change.",
        "trigger": "Deploy of release 2024.11.3 reduced pool size.",
        "detection_method": "alert",
        "entities": {
            "people": ["A. Cohen"],
            "teams": ["Payments-SRE"],
            "systems": ["payments-gateway", "wallet"],
            "dates": ["2024-11-19"],
            "error_codes": ["POOL_TIMEOUT"],
        },
        "action_items": [
            {"action": "Add pool-size guardrail to deploy checklist", "owner": "A. Cohen", "priority": "P0"},
            {"action": "Add saturation alert on PSP pool", "owner": None, "priority": "P1"},
        ],
        "contributing_factors": ["No pre-deploy load test"],
        "sentiment": "neutral",
        "blameless_quality": "good",
        "confidence_score": 0.9,
        "filename": "pm-payments-2024-11-19.pdf",
        "metrics": {
            "detected_at": "2024-11-19T09:05:00Z",
            "resolved_at": "2024-11-19T10:40:00Z",
            "ttd_minutes": 5,
            "ttr_minutes": 95,
            "customer_impact": "All deposits/withdrawals failed",
        },
    }
