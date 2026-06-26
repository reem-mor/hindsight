"""Tests for semantic search (BON-5) with mocked embeddings."""
from __future__ import annotations

import json
from unittest.mock import patch

from app.embeddings import EMBED_DIM, embed_text
from app.search_store import InMemoryVectorStore, SupabaseVectorStore


class _FakeResponse:
    """Minimal context-manager stand-in for urllib's urlopen result."""

    def __init__(self, payload: str) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload.encode()


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


def test_supabase_store_upsert_request() -> None:
    """upsert() hits the REST collection with a merge-duplicates upsert + 768-dim vector."""
    captured: list = []

    def fake_urlopen(req, timeout=0):  # noqa: ANN001, ARG001
        captured.append(req)
        return _FakeResponse("")

    store = SupabaseVectorStore("https://proj.supabase.co/", "service-key")
    with patch("app.search_store.embed_text", return_value=[0.1] * EMBED_DIM), patch(
        "app.search_store.urllib.request.urlopen", side_effect=fake_urlopen
    ):
        store.upsert(
            document_id="doc-9",
            filename="vuln.md",
            classification="vulnerability-scan",
            department="SecOps",
            sensitivity="confidential",
            routing_tag="escalate",
            summary="Critical OpenSSL RCE",
            processed_at="2026-06-26T00:00:00+00:00",
            text="Critical OpenSSL RCE CVE-2026-21841",
        )

    assert len(captured) == 1
    req = captured[0]
    assert req.full_url == "https://proj.supabase.co/rest/v1/hindsight_incidents?on_conflict=document_id"
    assert req.get_method() == "POST"
    # Upsert semantics + auth must be present.
    assert "merge-duplicates" in req.headers.get("Prefer", "")
    assert req.headers.get("Apikey") == "service-key"
    body = json.loads(req.data.decode())
    assert body["document_id"] == "doc-9"
    assert body["sensitivity"] == "confidential"
    assert len(body["embedding"]) == EMBED_DIM


def test_supabase_store_search_maps_rpc_rows() -> None:
    """search() calls the match RPC and maps rows -> SearchHit, preserving rank order."""
    captured: list = []
    rpc_rows = [
        {
            "document_id": "live-openssl-001",
            "filename": "vuln_scan_critical_openssl.md",
            "classification": "vulnerability-scan",
            "summary": "Critical OpenSSL RCE CVSS 9.8",
            "routing_tag": "escalate",
            "sensitivity": "confidential",
            "similarity": 0.81,
        },
        {
            "document_id": "intrusion-002",
            "filename": "siem_bruteforce_intrusion.md",
            "classification": "intrusion",
            "summary": "Credential stuffing brute force",
            "routing_tag": "needs-review",
            "sensitivity": "internal",
            "similarity": 0.42,
        },
    ]

    def fake_urlopen(req, timeout=0):  # noqa: ANN001, ARG001
        captured.append(req)
        return _FakeResponse(json.dumps(rpc_rows))

    store = SupabaseVectorStore("https://proj.supabase.co", "service-key")
    with patch("app.search_store.embed_text", return_value=[0.2] * EMBED_DIM), patch(
        "app.search_store.urllib.request.urlopen", side_effect=fake_urlopen
    ):
        hits = store.search("openssl rce vulnerability", top_k=5, min_similarity=0.25)

    req = captured[0]
    assert req.full_url == "https://proj.supabase.co/rest/v1/rpc/match_hindsight_incidents"
    sent = json.loads(req.data.decode())
    assert sent["match_count"] == 5
    assert sent["match_threshold"] == 0.25
    assert len(sent["query_embedding"]) == EMBED_DIM
    assert [h.document_id for h in hits] == ["live-openssl-001", "intrusion-002"]
    assert hits[0].similarity == 0.81
    assert hits[0].sensitivity == "confidential"
