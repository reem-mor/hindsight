"""Multi-model compare — Gemini Flash vs Pro structured output diff."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def _field_diff(a: Any, b: Any, path: str = "") -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    if type(a) is not type(b):
        diffs.append({"field": path or "root", "flash": a, "pro": b, "kind": "type_mismatch"})
        return diffs
    if isinstance(a, dict):
        keys = sorted(set(a.keys()) | set(b.keys()))
        for k in keys:
            sub = f"{path}.{k}" if path else k
            diffs.extend(_field_diff(a.get(k), b.get(k), sub))
    elif isinstance(a, list):
        if a != b:
            diffs.append({"field": path, "flash": a, "pro": b, "kind": "list_diff"})
    else:
        if a != b:
            diffs.append({"field": path, "flash": a, "pro": b, "kind": "value_diff"})
    return diffs


def compare_extractions(flash: dict[str, Any], pro: dict[str, Any]) -> dict[str, Any]:
    classification_match = (
        str(flash.get("incident_type") or flash.get("classification", ""))
        == str(pro.get("incident_type") or pro.get("classification", ""))
    )
    flash_conf = float(flash.get("confidence_score") or 0)
    pro_conf = float(pro.get("confidence_score") or 0)
    flash_entities = flash.get("entities") or {}
    pro_entities = pro.get("entities") or {}
    entity_overlap = 0
    if isinstance(flash_entities, dict) and isinstance(pro_entities, dict):
        flash_set = set()
        pro_set = set()
        for vals in flash_entities.values():
            if isinstance(vals, list):
                flash_set.update(str(v) for v in vals)
        for vals in pro_entities.values():
            if isinstance(vals, list):
                pro_set.update(str(v) for v in vals)
        union = flash_set | pro_set
        entity_overlap = len(flash_set & pro_set) / len(union) if union else 1.0

    field_diffs = _field_diff(flash, pro)
    return {
        "classification_agreement": classification_match,
        "confidence_delta": round(pro_conf - flash_conf, 4),
        "entity_overlap_ratio": round(entity_overlap, 4),
        "field_diff_count": len(field_diffs),
        "field_diffs": field_diffs[:50],
        "flash_summary": str(flash.get("summary", ""))[:300],
        "pro_summary": str(pro.get("summary", ""))[:300],
    }


def call_gemini_pro_json(prompt_text: str, api_key: str | None = None) -> dict[str, Any]:
    key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("GEMINI_API_KEY required for Pro compare")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3-pro:generateContent"
    )
    body = json.dumps(
        {
            "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    raw = data["candidates"][0]["content"]["parts"][0]["text"]
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)
