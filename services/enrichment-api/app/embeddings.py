"""Gemini embedding helper with deterministic mock fallback for CI."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.request

logger = logging.getLogger("hindsight.embeddings")

EMBED_DIM = 768
# gemini-embedding-001 is the current GA model (text-embedding-004 now 404s). It is
# natively 3072-dim but supports Matryoshka truncation via outputDimensionality, so we
# request 768 to match the pgvector(768) column in migrations/001_pgvector_incidents.sql.
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
GEMINI_EMBED_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedContent"
)


def _mock_embedding(text: str) -> list[float]:
    """Deterministic pseudo-embedding for tests when no API key is set."""
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    out: list[float] = []
    for i in range(EMBED_DIM):
        b = seed[i % len(seed)]
        out.append((b / 255.0) - 0.5)
    norm = sum(x * x for x in out) ** 0.5 or 1.0
    return [x / norm for x in out]


def embed_text(text: str, api_key: str | None = None) -> list[float]:
    key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
    cleaned = (text or "").strip()
    if not cleaned:
        return _mock_embedding("empty")

    if not key:
        return _mock_embedding(cleaned)

    body = json.dumps(
        {
            "model": f"models/{EMBED_MODEL}",
            "content": {"parts": [{"text": cleaned[:8000]}]},
            "outputDimensionality": EMBED_DIM,
            "taskType": "SEMANTIC_SIMILARITY",
        }
    ).encode()
    # Stay fast in the request path (default 1 try → mock fallback keeps /enrich resilient).
    # Seeding/back-fill sets GEMINI_EMBED_MAX_TRIES > 1 to ride out free-tier 429 bursts.
    max_tries = max(1, int(os.getenv("GEMINI_EMBED_MAX_TRIES", "1")))
    for attempt in range(max_tries):
        req = urllib.request.Request(
            GEMINI_EMBED_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            values = data.get("embedding", {}).get("values")
            if not values:
                logger.warning("empty embedding response; using mock")
                return _mock_embedding(cleaned)
            vec = [float(v) for v in values]
            # gemini-embedding-001 returns non-unit vectors for truncated dims; normalize
            # so cosine math and the mock fallback live on the same unit sphere.
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            return [x / norm for x in vec]
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt + 1 < max_tries:
                wait = min(30, 5 * (attempt + 1))
                logger.warning("embedding 429; retry %d/%d in %ds", attempt + 1, max_tries, wait)
                time.sleep(wait)
                continue
            logger.warning("embedding API failed (%s); using mock", exc)
            return _mock_embedding(cleaned)
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("embedding API failed (%s); using mock", exc)
            return _mock_embedding(cleaned)
    return _mock_embedding(cleaned)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
