"""Vector store: Supabase pgvector when configured, else in-memory fallback."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .embeddings import cosine_similarity, embed_text

logger = logging.getLogger("hindsight.search")


@dataclass
class SearchHit:
    document_id: str
    filename: str
    classification: str
    summary: str
    routing_tag: str
    sensitivity: str
    similarity: float


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    def upsert(
        self,
        document_id: str,
        filename: str,
        classification: str,
        department: str,
        sensitivity: str,
        routing_tag: str,
        summary: str,
        processed_at: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        emb = embed_text(text)
        self._rows = [r for r in self._rows if r["document_id"] != document_id]
        self._rows.append(
            {
                "document_id": document_id,
                "filename": filename,
                "classification": classification,
                "department": department,
                "sensitivity": sensitivity,
                "routing_tag": routing_tag,
                "summary": summary,
                "processed_at": processed_at,
                "embedding": emb,
                "metadata": metadata or {},
            }
        )

    def search(self, query: str, top_k: int = 5, min_similarity: float = 0.25) -> list[SearchHit]:
        q = embed_text(query)
        scored: list[SearchHit] = []
        for row in self._rows:
            sim = cosine_similarity(q, row["embedding"])
            if sim >= min_similarity:
                scored.append(
                    SearchHit(
                        document_id=row["document_id"],
                        filename=row["filename"],
                        classification=row["classification"],
                        summary=row["summary"],
                        routing_tag=row["routing_tag"],
                        sensitivity=row["sensitivity"],
                        similarity=round(sim, 4),
                    )
                )
        scored.sort(key=lambda h: h.similarity, reverse=True)
        return scored[:top_k]


class SupabaseVectorStore:
    """Upsert/search via Supabase REST + match_hindsight_incidents RPC."""

    def __init__(self, url: str, key: str) -> None:
        self.url = url.rstrip("/")
        self.key = key

    def _request(self, path: str, body: dict | None = None, method: str = "POST", *, prefer: str = "return=minimal") -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            method=method,
            headers={
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "Prefer": prefer,
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}

    def upsert(
        self,
        document_id: str,
        filename: str,
        classification: str,
        department: str,
        sensitivity: str,
        routing_tag: str,
        summary: str,
        processed_at: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        emb = embed_text(text)
        row = {
            "document_id": document_id,
            "filename": filename,
            "classification": classification,
            "department": department,
            "sensitivity": sensitivity,
            "routing_tag": routing_tag,
            "summary": summary,
            "processed_at": processed_at,
            "embedding": emb,
            "metadata": metadata or {},
        }
        self._request(
            "/rest/v1/hindsight_incidents?on_conflict=document_id",
            row,
            method="POST",
            prefer="return=minimal,resolution=merge-duplicates",
        )

    def search(self, query: str, top_k: int = 5, min_similarity: float = 0.25) -> list[SearchHit]:
        q_emb = embed_text(query)
        rows = self._request(
            "/rest/v1/rpc/match_hindsight_incidents",
            {
                "query_embedding": q_emb,
                "match_count": top_k,
                "match_threshold": min_similarity,
            },
        )
        return [
            SearchHit(
                document_id=r["document_id"],
                filename=r.get("filename", ""),
                classification=r.get("classification", ""),
                summary=r.get("summary", ""),
                routing_tag=r.get("routing_tag", ""),
                sensitivity=r.get("sensitivity", ""),
                similarity=float(r.get("similarity", 0)),
            )
            for r in rows
        ]


def get_vector_store() -> InMemoryVectorStore | SupabaseVectorStore:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if url and key:
        try:
            return SupabaseVectorStore(url, key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Supabase unavailable (%s); using in-memory store", exc)
    return InMemoryVectorStore()
