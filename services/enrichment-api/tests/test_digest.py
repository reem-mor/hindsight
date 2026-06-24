"""Tests for daily digest aggregation (BON-2)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.digest import aggregate_digest, build_digest_html, filter_last_24h


def test_filter_last_24h_window() -> None:
    now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)
    rows = [
        {"processed_at": "2026-06-23T11:00:00+00:00", "classification": "intrusion"},
        {"processed_at": "2026-06-22T10:00:00+00:00", "classification": "phishing"},
        {"processed_at": "2026-06-23T08:00:00+00:00", "classification": "vulnerability-scan"},
    ]
    recent = filter_last_24h(rows, now=now)
    assert len(recent) == 2
    classes = {r["classification"] for r in recent}
    assert classes == {"intrusion", "vulnerability-scan"}


def test_aggregate_digest_counts() -> None:
    rows = [
        {"classification": "intrusion", "sensitivity": "confidential", "routing_tag": "escalate", "computed_severity": "SEV1"},
        {"classification": "intrusion", "sensitivity": "internal", "routing_tag": "auto-approved", "computed_severity": "SEV3"},
        {"classification": "phishing", "sensitivity": "confidential", "routing_tag": "needs-review", "computed_severity": "SEV2"},
    ]
    agg = aggregate_digest(rows)
    assert agg["total"] == 3
    assert agg["by_classification"]["intrusion"] == 2
    assert agg["by_sensitivity"]["confidential"] == 2
    assert agg["by_routing_tag"]["escalate"] == 1
    assert agg["by_severity"]["SEV1"] == 1


def test_build_digest_html_contains_sections() -> None:
    agg = aggregate_digest([{"classification": "intrusion", "filename": "a.md"}])
    html = build_digest_html(agg)
    assert "Daily digest" in html
    assert "By classification" in html
    assert "intrusion" in html
