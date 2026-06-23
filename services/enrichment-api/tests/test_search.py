"""Tests for semantic search (BON-5) with mocked embeddings."""
from __future__ import annotations

from unittest.mock import patch

from app.embeddings import embed_text
from app.search_store import InMemoryVectorStore


def test_mock_embedding_deterministic() -> None:
    a = embed_text("CVE-2026-21841 critical openssl RCE")
    b = embed_text("CVE-2026-21841 critical openssl RCE")
    c = embed_text("minor email delay internal queue")
    assert a == b
    assert a != c


def test_in_memory_search_top_k() -> None:
    store = InMemoryVectorStore()
    with patch("app.search_store.embed_text", side_effect=lambda t: embed_text(t)):
        store.upsert(
            document_id="doc-1",
            filename="vuln.md",
            classification="vulnerability-scan",
            department="SecOps",
            sensitivity="confidential",
            routing_tag="escalate",
            summary="Critical OpenSSL RCE CVSS 9.8",
            processed_at="2026-06-23T10:00:00+00:00",
            text="Critical OpenSSL RCE CVSS 9.8 CVE-2026-21841",
        )
        store.upsert(
            document_id="doc-2",
            filename="minor.md",
            classification="other",
            department="SecOps",
            sensitivity="internal",
            routing_tag="auto-approved",
            summary="Minor email delay",
            processed_at="2026-06-23T11:00:00+00:00",
            text="Minor internal email gateway queue backlog",
        )
        hits = store.search(
            "Critical OpenSSL RCE CVSS 9.8 CVE-2026-21841",
            top_k=2,
            min_similarity=0.0,
        )
    assert hits
    assert hits[0].document_id == "doc-1"
    assert hits[0].similarity >= hits[-1].similarity


def test_search_endpoint(client) -> None:
    with patch("app.main.get_vector_store") as mock_store:
        mock_store.return_value.search.return_value = []
        resp = client.post("/search", json={"query": "openssl rce", "top_k": 3})
    assert resp.status_code == 200
    assert resp.json()["query"] == "openssl rce"
