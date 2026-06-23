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


def aggregate_digest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_class = Counter(str(r.get("classification", "other")) for r in rows)
    by_sensitivity = Counter(str(r.get("sensitivity", "internal")) for r in rows)
    by_routing = Counter(str(r.get("routing_tag", "auto-approved")) for r in rows)
    by_sev: Counter[str] = Counter()
    for r in rows:
        sev = r.get("computed_severity") or r.get("severity") or "unknown"
        by_sev[str(sev)] += 1

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
            return "<li>none</li>"
        return "".join(f"<li>{k}: {v}</li>" for k, v in sorted(counter.items()))

    files = agg.get("filenames") or []
    file_list = "".join(f"<li>{f}</li>" for f in files) if files else "<li>none</li>"
    return (
        f"<h2>HINDSIGHT — Daily digest (last {window_hours}h)</h2>"
        f"<p><b>Documents processed:</b> {agg.get('total', 0)}</p>"
        f"<h3>By classification</h3><ul>{rows(agg.get('by_classification', {}))}</ul>"
        f"<h3>By severity</h3><ul>{rows(agg.get('by_severity', {}))}</ul>"
        f"<h3>By sensitivity</h3><ul>{rows(agg.get('by_sensitivity', {}))}</ul>"
        f"<h3>By routing tag</h3><ul>{rows(agg.get('by_routing_tag', {}))}</ul>"
        f"<h3>Recent files</h3><ul>{file_list}</ul>"
        "<hr><p><i>Sent automatically by HINDSIGHT daily digest workflow</i></p>"
    )
