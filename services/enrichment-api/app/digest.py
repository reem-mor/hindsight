"""Daily digest aggregation — mirrors n8n/cloud/nodes/digest_aggregate.js."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except ValueError:
        return None


def filter_last_24h(rows: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    out: list[dict[str, Any]] = []
    for row in rows:
        ts = _parse_ts(str(row.get("processed_at", "")))
        if ts and ts >= cutoff:
            out.append(row)
    return out


def _derive_severity(row: dict[str, Any]) -> str:
    """Registry rows store only the 14 sheet columns (no computed_severity), so
    recover a severity bucket from the stored CVSS / routing decision."""
    direct = row.get("computed_severity") or row.get("severity")
    if direct:
        return str(direct)
    try:
        cvss = float(row.get("cvss_score") or 0)
    except (TypeError, ValueError):
        cvss = 0.0
    if cvss > 0:
        if cvss >= 9.0:
            return "SEV1"
        if cvss >= 7.0:
            return "SEV2"
        if cvss >= 4.0:
            return "SEV3"
        return "SEV4"
    if str(row.get("routing_tag", "")) == "escalate":
        return "SEV1"
    return "unknown"


def aggregate_digest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_class = Counter(str(r.get("classification", "other")) for r in rows)
    by_sensitivity = Counter(str(r.get("sensitivity", "internal")) for r in rows)
    by_routing = Counter(str(r.get("routing_tag", "auto-approved")) for r in rows)
    by_sev: Counter[str] = Counter()
    for r in rows:
        by_sev[_derive_severity(r)] += 1

    return {
        "total": len(rows),
        "by_classification": dict(by_class),
        "by_sensitivity": dict(by_sensitivity),
        "by_routing_tag": dict(by_routing),
        "by_severity": dict(by_sev),
        "filenames": [str(r.get("filename", "")) for r in rows[:20]],
    }


def build_digest_html(agg: dict[str, Any], window_hours: int = 24) -> str:
    def rows(counter: dict[str, int]) -> str:
        if not counter:
            return '<li style="color:#64748b;">None in window</li>'
        return "".join(
            f'<li style="margin:4px 0;"><strong>{k}</strong> · {v}</li>'
            for k, v in sorted(counter.items())
        )

    files = agg.get("filenames") or []
    file_list = (
        "".join(f'<li style="margin:4px 0;">{f}</li>' for f in files)
        if files
        else '<li style="color:#64748b;">None in window</li>'
    )
    total = agg.get("total", 0)
    sev1 = (agg.get("by_severity") or {}).get("SEV1", 0)
    confidential = (agg.get("by_sensitivity") or {}).get("confidential", 0)
    escalated = (agg.get("by_routing_tag") or {}).get("escalate", 0)
    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f'<title>HINDSIGHT Daily Digest</title></head>'
        f'<body style="margin:0;background:#f1f5f9;font-family:Inter,Arial,sans-serif;">'
        f'<table role="presentation" width="100%" style="padding:24px 12px;"><tr><td align="center">'
        f'<table role="presentation" width="600" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;">'
        f'<tr><td style="background:#0B0F14;color:#E6EDF3;padding:18px 24px;">'
        f'<p style="margin:0;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#8696A7;">'
        f"HINDSIGHT · Daily digest</p>"
        f'<h1 style="margin:6px 0 0;font-size:22px;">Last {window_hours} hours</h1></td></tr>'
        f'<tr><td style="padding:20px 24px;">'
        f"<p><b>Documents processed:</b> {total} · SEV1: {sev1} · Confidential: {confidential} · Escalated: {escalated}</p>"
        f"<h2>By classification</h2><ul>{rows(agg.get('by_classification', {}))}</ul>"
        f"<h2>By severity</h2><ul>{rows(agg.get('by_severity', {}))}</ul>"
        f"<h2>By sensitivity</h2><ul>{rows(agg.get('by_sensitivity', {}))}</ul>"
        f"<h2>By routing tag</h2><ul>{rows(agg.get('by_routing_tag', {}))}</ul>"
        f"<h2>Recent files</h2><ul>{file_list}</ul>"
        f"</td></tr></table></td></tr></table></body></html>"
    )
