"""Gemini embedding helper with deterministic mock fallback for CI."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("hindsight.embeddings")

EMBED_DIM = 768
GEMINI_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "text-embedding-004:embedContent"
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
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": cleaned[:8000]}]},
        }
    ).encode()
    req = urllib.request.Request(
        GEMINI_EMBED_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        values = data.get("embedding", {}).get("values")
        if not values:
            logger.warning("empty embedding response; using mock")
            return _mock_embedding(cleaned)
        return [float(v) for v in values]
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("embedding API failed (%s); using mock", exc)
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
