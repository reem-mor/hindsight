"""Tests for multi-model compare (BON-6)."""
from __future__ import annotations

from app.compare import compare_extractions


def test_compare_classification_agreement() -> None:
    flash = {"incident_type": "phishing", "confidence_score": 0.8, "summary": "a", "entities": {"systems": ["mail"]}}
    pro = {"incident_type": "phishing", "confidence_score": 0.9, "summary": "b", "entities": {"systems": ["mail", "web"]}}
    report = compare_extractions(flash, pro)
    assert report["classification_agreement"] is True
    assert report["confidence_delta"] == 0.1
    assert 0 <= report["entity_overlap_ratio"] <= 1
    assert report["field_diff_count"] > 0


def test_compare_classification_disagreement() -> None:
    flash = {"incident_type": "other", "confidence_score": 0.5, "summary": "x"}
    pro = {"incident_type": "intrusion", "confidence_score": 0.7, "summary": "y"}
    report = compare_extractions(flash, pro)
    assert report["classification_agreement"] is False
    assert report["confidence_delta"] == 0.2
